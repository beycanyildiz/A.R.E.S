"""
Core Orchestrator - Event-Driven Microservices Hub

This is the central nervous system of A.R.E.S. It:
- Receives events from all agents via RabbitMQ
- Maintains global state in Redis
- Orchestrates multi-agent workflows
- Provides REST API for external control

Architecture:
- FastAPI for REST endpoints
- RabbitMQ for async event messaging
- Redis for state management and caching
- WebSocket for real-time updates
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import aio_pika
from aio_pika import Message, ExchangeType
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# CONFIGURATION
# ==========================================

class Config:
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://ares_admin:insecure_dev_password@localhost:5672/ares")
    REDIS_URL = os.getenv("REDIS_URL", "redis://:insecure_dev_password@localhost:6379/0")
    ORCHESTRATOR_HOST = os.getenv("ORCHESTRATOR_HOST", "0.0.0.0")
    ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8000"))


# ==========================================
# EVENTS & MODELS
# ==========================================

class EventType(str, Enum):
    """System event types"""
    RECON_STARTED = "recon.started"
    RECON_HOST_FOUND = "recon.host_found"
    RECON_SERVICE_FOUND = "recon.service_found"
    RECON_COMPLETED = "recon.completed"
    
    VULN_SCAN_STARTED = "vuln.scan_started"
    VULN_FOUND = "vuln.found"
    VULN_SCAN_COMPLETED = "vuln.scan_completed"
    
    EXPLOIT_GENERATION_STARTED = "exploit.generation_started"
    EXPLOIT_GENERATED = "exploit.generated"
    EXPLOIT_TESTED = "exploit.tested"
    EXPLOIT_SUCCESS = "exploit.success"
    EXPLOIT_FAILED = "exploit.failed"
    
    AGENT_TASK_ASSIGNED = "agent.task_assigned"
    AGENT_TASK_COMPLETED = "agent.task_completed"
    AGENT_ERROR = "agent.error"
    
    SYSTEM_ALERT = "system.alert"


class Event(BaseModel):
    """Base event model"""
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str  # Which agent/service generated this
    data: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None  # For tracking related events


class MissionStatus(str, Enum):
    """Mission execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Mission(BaseModel):
    """Represents a complete attack mission"""
    id: str
    name: str
    target: str  # IP, domain, or CIDR
    status: MissionStatus = MissionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    results: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# PROMETHEUS METRICS
# ==========================================

try:
    events_processed = Counter('ares_events_processed_total', 'Total events processed', ['event_type'])
    mission_duration = Histogram('ares_mission_duration_seconds', 'Mission execution time')
    active_missions = Counter('ares_active_missions', 'Currently active missions')
except ValueError:
    # Metrics already registered (happens with uvicorn reload)
    from prometheus_client import REGISTRY
    events_processed = REGISTRY._names_to_collectors.get('ares_events_processed_total')
    mission_duration = REGISTRY._names_to_collectors.get('ares_mission_duration_seconds')
    active_missions = REGISTRY._names_to_collectors.get('ares_active_missions')


# ==========================================
# ORCHESTRATOR CLASS
# ==========================================

class Orchestrator:
    """Main orchestrator managing all system components"""
    
    def __init__(self):
        self.rabbitmq_connection: Optional[aio_pika.Connection] = None
        self.rabbitmq_channel: Optional[aio_pika.Channel] = None
        self.redis_client: Optional[redis.Redis] = None
        self.event_exchange: Optional[aio_pika.Exchange] = None
        self.websocket_clients: List[WebSocket] = []
        
    async def initialize(self):
        """Initialize all connections"""
        await self._connect_rabbitmq()
        await self._connect_redis()
        logger.info("Orchestrator initialized")
    
    async def _connect_rabbitmq(self):
        """Connect to RabbitMQ"""
        try:
            self.rabbitmq_connection = await aio_pika.connect_robust(Config.RABBITMQ_URL)
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()
            
            # Declare event exchange
            self.event_exchange = await self.rabbitmq_channel.declare_exchange(
                "ares_events",
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Declare queue for orchestrator
            queue = await self.rabbitmq_channel.declare_queue(
                "orchestrator_events",
                durable=True
            )
            
            # Bind to all events
            await queue.bind(self.event_exchange, routing_key="*.*")
            
            # Start consuming
            await queue.consume(self._handle_event)
            
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {e}")
            raise
    
    async def _connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = await redis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    async def _handle_event(self, message: aio_pika.IncomingMessage):
        """Handle incoming events from message queue"""
        async with message.process():
            try:
                event_data = json.loads(message.body.decode())
                event = Event(**event_data)
                
                logger.info(f"Received event: {event.event_type} from {event.source}")
                
                # Update metrics
                events_processed.labels(event_type=event.event_type.value).inc()
                
                # Store in Redis for history
                await self._store_event(event)
                
                # Broadcast to WebSocket clients
                await self._broadcast_to_websockets(event)
                
                # Handle specific event types
                await self._process_event(event)
                
            except Exception as e:
                logger.error(f"Event handling error: {e}")
    
    async def _store_event(self, event: Event):
        """Store event in Redis"""
        key = f"event:{event.timestamp.isoformat()}:{event.event_type}"
        await self.redis_client.setex(
            key,
            3600 * 24,  # 24 hour TTL
            event.model_dump_json()
        )
    
    async def _broadcast_to_websockets(self, event: Event):
        """Broadcast event to all connected WebSocket clients"""
        if not self.websocket_clients:
            return
        
        message = {
            "type": "event",
            "data": event.model_dump(mode='json')
        }
        
        disconnected = []
        for client in self.websocket_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)
        
        # Remove disconnected clients
        for client in disconnected:
            self.websocket_clients.remove(client)
    
    async def _process_event(self, event: Event):
        """Process event based on type"""
        if event.event_type == EventType.RECON_HOST_FOUND:
            # Trigger vulnerability scan
            await self.publish_event(Event(
                event_type=EventType.VULN_SCAN_STARTED,
                source="orchestrator",
                data={"target": event.data.get("ip")},
                correlation_id=event.correlation_id
            ))
        
        elif event.event_type == EventType.VULN_FOUND:
            # Trigger exploit generation
            await self.publish_event(Event(
                event_type=EventType.EXPLOIT_GENERATION_STARTED,
                source="orchestrator",
                data={
                    "cve_id": event.data.get("cve_id"),
                    "target": event.data.get("target")
                },
                correlation_id=event.correlation_id
            ))
        
        elif event.event_type == EventType.EXPLOIT_SUCCESS:
            # Log success and potentially trigger lateral movement
            logger.info(f"🎯 EXPLOIT SUCCESS: {event.data}")
    
    async def publish_event(self, event: Event):
        """Publish event to message queue"""
        if not self.event_exchange:
            logger.error("Event exchange not initialized")
            return
        
        routing_key = event.event_type.value
        message = Message(
            body=event.model_dump_json().encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await self.event_exchange.publish(message, routing_key=routing_key)
        logger.debug(f"Published event: {event.event_type}")
    
    async def create_mission(self, mission: Mission) -> Mission:
        """Create new mission"""
        # Store in Redis
        await self.redis_client.setex(
            f"mission:{mission.id}",
            3600 * 24 * 7,  # 7 days
            mission.model_dump_json()
        )
        
        # Publish mission start event
        await self.publish_event(Event(
            event_type=EventType.RECON_STARTED,
            source="orchestrator",
            data={"mission_id": mission.id, "target": mission.target},
            correlation_id=mission.id
        ))
        
        active_missions.inc()
        logger.info(f"Created mission: {mission.id} targeting {mission.target}")
        return mission
    
    async def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Retrieve mission by ID"""
        data = await self.redis_client.get(f"mission:{mission_id}")
        if data:
            return Mission.model_validate_json(data)
        return None
    
    async def shutdown(self):
        """Graceful shutdown"""
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Orchestrator shutdown complete")


# ==========================================
# FASTAPI APPLICATION
# ==========================================

orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    await orchestrator.initialize()
    yield
    await orchestrator.shutdown()


app = FastAPI(
    title="A.R.E.S. Orchestrator",
    description="Autonomous Reconnaissance & Exploitation System - Core Orchestrator",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# REST ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {
        "service": "A.R.E.S. Orchestrator",
        "status": "operational",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_ok = await orchestrator.redis_client.ping() if orchestrator.redis_client else False
    rabbitmq_ok = orchestrator.rabbitmq_connection and not orchestrator.rabbitmq_connection.is_closed
    
    return {
        "status": "healthy" if (redis_ok and rabbitmq_ok) else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "rabbitmq": "connected" if rabbitmq_ok else "disconnected"
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/missions", response_model=Mission)
async def create_mission(mission: Mission, background_tasks: BackgroundTasks):
    """Create new attack mission"""
    created_mission = await orchestrator.create_mission(mission)
    return created_mission


@app.get("/missions/{mission_id}", response_model=Mission)
async def get_mission(mission_id: str):
    """Get mission details"""
    mission = await orchestrator.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@app.post("/events")
async def publish_event(event: Event):
    """Manually publish an event"""
    await orchestrator.publish_event(event)
    return {"status": "published", "event_type": event.event_type}


@app.get("/stats")
async def get_stats():
    """Get system statistics for dashboard"""
    # Get mission count from Redis
    mission_keys = await orchestrator.redis_client.keys("mission:*")
    total_missions = len(mission_keys)
    
    # Mock stats for now (can be enhanced with real data)
    return {
        "total_missions": total_missions,
        "active_missions": 2,
        "success_rate": 0.73,
        "hosts_discovered": 12,
        "vulnerabilities_found": 8,
        "exploits_successful": 6
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time event streaming"""
    await websocket.accept()
    orchestrator.websocket_clients.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        orchestrator.websocket_clients.remove(websocket)
        logger.info("WebSocket client disconnected")


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=Config.ORCHESTRATOR_HOST,
        port=Config.ORCHESTRATOR_PORT,
        reload=True,
        log_level="info"
    )
