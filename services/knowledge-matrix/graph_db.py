"""
Knowledge Matrix - Graph Database Manager

This module manages the Neo4j graph database for:
- Network topology mapping (hosts, services, relationships)
- Attack path visualization
- Trust relationship analysis
- Lateral movement planning

Graph Schema:
- Nodes: Host, Service, User, Credential, Vulnerability
- Relationships: RUNS_ON, TRUSTS, EXPLOITS, ACCESSES
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Graph node types"""
    HOST = "Host"
    SERVICE = "Service"
    USER = "User"
    CREDENTIAL = "Credential"
    VULNERABILITY = "Vulnerability"
    EXPLOIT = "Exploit"


class RelationType(Enum):
    """Graph relationship types"""
    RUNS_ON = "RUNS_ON"           # Service -> Host
    TRUSTS = "TRUSTS"             # Host -> Host
    EXPLOITS = "EXPLOITS"         # Exploit -> Vulnerability
    ACCESSES = "ACCESSES"         # User -> Host
    AUTHENTICATES = "AUTHENTICATES"  # Credential -> Service
    HAS_VULN = "HAS_VULN"        # Service -> Vulnerability


@dataclass
class Host:
    """Represents a network host"""
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    mac_address: Optional[str] = None
    status: str = "unknown"  # alive, dead, unknown
    discovered_at: datetime = None
    
    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now()


@dataclass
class Service:
    """Represents a network service"""
    name: str
    port: int
    protocol: str = "tcp"
    version: Optional[str] = None
    banner: Optional[str] = None
    state: str = "open"


@dataclass
class Vulnerability:
    """Represents a vulnerability"""
    cve_id: str
    severity: str
    description: str
    cvss_score: float


class GraphDBManager:
    """Manages Neo4j graph database operations"""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password"
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[Driver] = None
        
        self._connect()
        self._create_constraints()
    
    def _connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def _create_constraints(self):
        """Create uniqueness constraints and indexes"""
        constraints = [
            "CREATE CONSTRAINT host_ip IF NOT EXISTS FOR (h:Host) REQUIRE h.ip IS UNIQUE",
            "CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT vuln_cve IF NOT EXISTS FOR (v:Vulnerability) REQUIRE v.cve_id IS UNIQUE",
            "CREATE INDEX host_status IF NOT EXISTS FOR (h:Host) ON (h.status)",
            "CREATE INDEX service_port IF NOT EXISTS FOR (s:Service) ON (s.port)",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    # Constraint might already exist
                    logger.debug(f"Constraint creation: {e}")
        
        logger.info("Graph constraints and indexes created")
    
    def add_host(self, host: Host) -> bool:
        """Add or update a host node"""
        query = """
        MERGE (h:Host {ip: $ip})
        SET h.hostname = $hostname,
            h.os = $os,
            h.os_version = $os_version,
            h.mac_address = $mac_address,
            h.status = $status,
            h.discovered_at = datetime($discovered_at),
            h.updated_at = datetime()
        RETURN h
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    ip=host.ip,
                    hostname=host.hostname,
                    os=host.os,
                    os_version=host.os_version,
                    mac_address=host.mac_address,
                    status=host.status,
                    discovered_at=host.discovered_at.isoformat()
                )
                logger.info(f"Added/updated host: {host.ip}")
                return True
        except Exception as e:
            logger.error(f"Failed to add host: {e}")
            return False
    
    def add_service(self, host_ip: str, service: Service) -> bool:
        """Add service and link to host"""
        query = """
        MATCH (h:Host {ip: $host_ip})
        MERGE (s:Service {id: $service_id})
        SET s.name = $name,
            s.port = $port,
            s.protocol = $protocol,
            s.version = $version,
            s.banner = $banner,
            s.state = $state,
            s.updated_at = datetime()
        MERGE (s)-[:RUNS_ON]->(h)
        RETURN s
        """
        
        service_id = f"{host_ip}:{service.port}/{service.protocol}"
        
        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    host_ip=host_ip,
                    service_id=service_id,
                    name=service.name,
                    port=service.port,
                    protocol=service.protocol,
                    version=service.version,
                    banner=service.banner,
                    state=service.state
                )
                logger.info(f"Added service: {service.name}:{service.port} on {host_ip}")
                return True
        except Exception as e:
            logger.error(f"Failed to add service: {e}")
            return False
    
    def add_vulnerability(self, service_id: str, vuln: Vulnerability) -> bool:
        """Link vulnerability to service"""
        query = """
        MATCH (s:Service {id: $service_id})
        MERGE (v:Vulnerability {cve_id: $cve_id})
        SET v.severity = $severity,
            v.description = $description,
            v.cvss_score = $cvss_score,
            v.updated_at = datetime()
        MERGE (s)-[:HAS_VULN]->(v)
        RETURN v
        """
        
        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    service_id=service_id,
                    cve_id=vuln.cve_id,
                    severity=vuln.severity,
                    description=vuln.description,
                    cvss_score=vuln.cvss_score
                )
                logger.info(f"Linked vulnerability {vuln.cve_id} to {service_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to add vulnerability: {e}")
            return False
    
    def add_trust_relationship(self, source_ip: str, target_ip: str, trust_type: str = "unknown") -> bool:
        """Add trust relationship between hosts"""
        query = """
        MATCH (source:Host {ip: $source_ip})
        MATCH (target:Host {ip: $target_ip})
        MERGE (source)-[t:TRUSTS]->(target)
        SET t.type = $trust_type,
            t.created_at = datetime()
        RETURN t
        """
        
        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    source_ip=source_ip,
                    target_ip=target_ip,
                    trust_type=trust_type
                )
                logger.info(f"Added trust: {source_ip} -> {target_ip}")
                return True
        except Exception as e:
            logger.error(f"Failed to add trust relationship: {e}")
            return False
    
    def find_attack_paths(
        self,
        source_ip: str,
        target_ip: str,
        max_hops: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find potential attack paths from source to target
        
        Uses Cypher's shortestPath algorithm to find lateral movement routes
        """
        query = """
        MATCH (source:Host {ip: $source_ip})
        MATCH (target:Host {ip: $target_ip})
        MATCH path = shortestPath((source)-[*..{max_hops}]-(target))
        RETURN path, length(path) as hops
        ORDER BY hops
        LIMIT 10
        """.replace("{max_hops}", str(max_hops))
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    source_ip=source_ip,
                    target_ip=target_ip
                )
                
                paths = []
                for record in result:
                    path_nodes = []
                    for node in record["path"].nodes:
                        path_nodes.append({
                            "type": list(node.labels)[0],
                            "properties": dict(node)
                        })
                    
                    paths.append({
                        "hops": record["hops"],
                        "nodes": path_nodes
                    })
                
                logger.info(f"Found {len(paths)} attack paths")
                return paths
                
        except Exception as e:
            logger.error(f"Failed to find attack paths: {e}")
            return []
    
    def get_vulnerable_services(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all services with vulnerabilities"""
        query = """
        MATCH (s:Service)-[:HAS_VULN]->(v:Vulnerability)
        MATCH (s)-[:RUNS_ON]->(h:Host)
        """
        
        if severity:
            query += f"WHERE v.severity = '{severity}' "
        
        query += """
        RETURN h.ip as host_ip,
               s.name as service_name,
               s.port as port,
               v.cve_id as cve_id,
               v.severity as severity,
               v.cvss_score as cvss_score
        ORDER BY v.cvss_score DESC
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Failed to get vulnerable services: {e}")
            return []
    
    def get_network_topology(self) -> Dict[str, Any]:
        """Get complete network topology"""
        query = """
        MATCH (h:Host)
        OPTIONAL MATCH (h)<-[:RUNS_ON]-(s:Service)
        OPTIONAL MATCH (s)-[:HAS_VULN]->(v:Vulnerability)
        RETURN h, collect(DISTINCT s) as services, collect(DISTINCT v) as vulnerabilities
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query)
                
                topology = {"hosts": []}
                for record in result:
                    host_data = dict(record["h"])
                    host_data["services"] = [dict(s) for s in record["services"] if s]
                    host_data["vulnerabilities"] = [dict(v) for v in record["vulnerabilities"] if v]
                    topology["hosts"].append(host_data)
                
                return topology
        except Exception as e:
            logger.error(f"Failed to get topology: {e}")
            return {"hosts": []}
    
    def clear_database(self):
        """Clear all nodes and relationships (USE WITH CAUTION)"""
        query = "MATCH (n) DETACH DELETE n"
        
        with self.driver.session() as session:
            session.run(query)
            logger.warning("Database cleared!")
    
    def close(self):
        """Close driver connection"""
        if self.driver:
            self.driver.close()
            logger.info("Disconnected from Neo4j")


# Example usage
if __name__ == "__main__":
    # Initialize
    db = GraphDBManager(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="insecure_dev_password"
    )
    
    # Add hosts
    host1 = Host(ip="192.168.1.10", hostname="web-server", os="Ubuntu", os_version="22.04", status="alive")
    host2 = Host(ip="192.168.1.20", hostname="db-server", os="Ubuntu", os_version="20.04", status="alive")
    
    db.add_host(host1)
    db.add_host(host2)
    
    # Add services
    web_service = Service(name="nginx", port=80, version="1.18.0")
    db_service = Service(name="postgresql", port=5432, version="13.2")
    
    db.add_service("192.168.1.10", web_service)
    db.add_service("192.168.1.20", db_service)
    
    # Add vulnerability
    vuln = Vulnerability(
        cve_id="CVE-2021-23017",
        severity="HIGH",
        description="Nginx DNS resolver off-by-one heap write",
        cvss_score=8.1
    )
    
    db.add_vulnerability("192.168.1.10:80/tcp", vuln)
    
    # Add trust relationship
    db.add_trust_relationship("192.168.1.10", "192.168.1.20", "ssh_key")
    
    # Query vulnerable services
    vulns = db.get_vulnerable_services(severity="HIGH")
    print("\n=== Vulnerable Services ===")
    for v in vulns:
        print(f"{v['host_ip']}:{v['port']} - {v['service_name']} - {v['cve_id']} (CVSS: {v['cvss_score']})")
    
    # Find attack paths
    paths = db.find_attack_paths("192.168.1.10", "192.168.1.20")
    print(f"\n=== Attack Paths ({len(paths)} found) ===")
    for i, path in enumerate(paths, 1):
        print(f"Path {i} ({path['hops']} hops):")
        for node in path['nodes']:
            print(f"  -> {node['type']}: {node['properties'].get('ip', node['properties'].get('name'))}")
    
    db.close()
