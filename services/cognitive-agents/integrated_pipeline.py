"""
Integrated Cognitive Pipeline - Complete AI-Driven Exploit Workflow

This module orchestrates the complete cognitive workflow:
1. Reconnaissance → Knowledge Matrix
2. Cognitive Agents → Strategy & Planning
3. Exploit Synthesizer → Code Generation
4. Sandbox Execution → Testing
5. Reinforcement Learning → Feedback Loop

This is the "brain" that connects all Phase 1 and Phase 2 components.
"""

import os
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from .agent_framework import CognitiveAgentOrchestrator, AgentState
from .exploit_synthesizer import (
    ExploitSynthesizer,
    VulnerabilityContext,
    ExploitLanguage,
    ExploitCode
)
from .reinforcement_learning import (
    ReinforcementLearningLoop,
    ExploitAttempt,
    OutcomeType
)

# Import Phase 1 components
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.knowledge_matrix.vector_db import VectorDBManager
from services.knowledge_matrix.graph_db import GraphDBManager, Host, Service, Vulnerability
from services.recon_engine.scanner import ReconEngine, HostInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MissionConfig:
    """Configuration for a complete mission"""
    mission_id: str
    target: str  # IP, domain, or CIDR
    
    # Recon settings
    scan_ports: list = None
    aggressive_scan: bool = False
    
    # Exploit settings
    auto_exploit: bool = True
    exploit_language: ExploitLanguage = ExploitLanguage.PYTHON
    obfuscate_exploits: bool = True
    
    # Safety settings
    max_exploit_attempts: int = 3
    timeout_seconds: int = 30
    
    def __post_init__(self):
        if self.scan_ports is None:
            self.scan_ports = [21, 22, 23, 80, 443, 3306, 3389, 5432, 8080]


class IntegratedCognitivePipeline:
    """
    Complete AI-driven penetration testing pipeline
    
    This is the highest-level orchestrator that combines:
    - Phase 1: Infrastructure (Vector DB, Graph DB, Recon)
    - Phase 2: Cognitive Agents (LLM-based decision making)
    """
    
    def __init__(
        self,
        vector_db_host: str = "localhost",
        vector_db_port: int = 19530,
        graph_db_uri: str = "bolt://localhost:7687",
        graph_db_user: str = "neo4j",
        graph_db_password: str = "insecure_dev_password",
        redis_url: str = "redis://:insecure_dev_password@localhost:6379/0"
    ):
        # Phase 1 components
        self.vector_db = VectorDBManager(host=vector_db_host, port=vector_db_port)
        self.graph_db = GraphDBManager(uri=graph_db_uri, user=graph_db_user, password=graph_db_password)
        self.recon_engine = ReconEngine()
        
        # Phase 2 components
        self.cognitive_orchestrator = CognitiveAgentOrchestrator()
        self.exploit_synthesizer = ExploitSynthesizer(
            llm_provider=self.cognitive_orchestrator.llm_provider,
            vector_db_manager=self.vector_db
        )
        
        # Reinforcement Learning
        self.rl_loop = ReinforcementLearningLoop(redis_url=redis_url)
        
        logger.info("Integrated Cognitive Pipeline initialized")
    
    async def initialize(self):
        """Initialize async components"""
        await self.rl_loop.initialize()
        logger.info("Pipeline async initialization complete")
    
    async def execute_mission(self, config: MissionConfig) -> Dict[str, Any]:
        """
        Execute complete autonomous penetration testing mission
        
        Workflow:
        1. Reconnaissance (scan target)
        2. Knowledge ingestion (store in Graph DB)
        3. Cognitive analysis (LLM agents decide strategy)
        4. Exploit synthesis (generate custom exploits)
        5. Execution simulation (sandbox testing)
        6. Learning (update RL model)
        
        Args:
            config: Mission configuration
        
        Returns:
            Mission results with all findings
        """
        logger.info(f"🚀 Starting mission: {config.mission_id} targeting {config.target}")
        
        mission_results = {
            "mission_id": config.mission_id,
            "target": config.target,
            "started_at": datetime.now().isoformat(),
            "phases": {}
        }
        
        try:
            # ============================================
            # PHASE 1: RECONNAISSANCE
            # ============================================
            logger.info("📡 Phase 1: Reconnaissance")
            
            recon_results = await self._phase_reconnaissance(config)
            mission_results["phases"]["reconnaissance"] = recon_results
            
            if not recon_results["hosts_found"]:
                logger.warning("No hosts found during reconnaissance")
                mission_results["status"] = "no_targets_found"
                return mission_results
            
            # ============================================
            # PHASE 2: KNOWLEDGE INGESTION
            # ============================================
            logger.info("🧠 Phase 2: Knowledge Ingestion")
            
            knowledge_results = await self._phase_knowledge_ingestion(recon_results)
            mission_results["phases"]["knowledge_ingestion"] = knowledge_results
            
            # ============================================
            # PHASE 3: COGNITIVE ANALYSIS
            # ============================================
            logger.info("🤖 Phase 3: Cognitive Analysis")
            
            cognitive_results = await self._phase_cognitive_analysis(config, recon_results)
            mission_results["phases"]["cognitive_analysis"] = cognitive_results
            
            # ============================================
            # PHASE 4: EXPLOIT SYNTHESIS
            # ============================================
            logger.info("⚔️ Phase 4: Exploit Synthesis")
            
            exploit_results = await self._phase_exploit_synthesis(config, knowledge_results)
            mission_results["phases"]["exploit_synthesis"] = exploit_results
            
            # ============================================
            # PHASE 5: EXECUTION & LEARNING
            # ============================================
            logger.info("🎯 Phase 5: Execution & Learning")
            
            execution_results = await self._phase_execution_learning(config, exploit_results)
            mission_results["phases"]["execution"] = execution_results
            
            # ============================================
            # FINALIZE
            # ============================================
            mission_results["completed_at"] = datetime.now().isoformat()
            mission_results["status"] = "completed"
            
            # Generate performance report
            performance = await self.rl_loop.get_performance_report()
            mission_results["performance_metrics"] = performance
            
            logger.info(f"✅ Mission {config.mission_id} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Mission failed: {e}", exc_info=True)
            mission_results["status"] = "failed"
            mission_results["error"] = str(e)
        
        return mission_results
    
    async def _phase_reconnaissance(self, config: MissionConfig) -> Dict[str, Any]:
        """Phase 1: Scan target and discover hosts/services"""
        
        # Determine if CIDR or single host
        if "/" in config.target:
            # Network scan
            hosts = await self.recon_engine.scan_network(
                cidr=config.target,
                ports=config.scan_ports
            )
        else:
            # Single host scan
            host = await self.recon_engine.scan_host(
                target=config.target,
                ports=config.scan_ports,
                aggressive=config.aggressive_scan
            )
            hosts = [host] if host.status == "alive" else []
        
        # Extract results
        results = {
            "hosts_found": len(hosts),
            "hosts": [
                {
                    "ip": h.ip,
                    "hostname": h.hostname,
                    "os": h.os,
                    "status": h.status,
                    "open_ports": [
                        {"port": p.port, "service": p.service, "version": p.version}
                        for p in h.open_ports
                    ]
                }
                for h in hosts
            ]
        }
        
        logger.info(f"Reconnaissance complete: {len(hosts)} hosts found")
        return results
    
    async def _phase_knowledge_ingestion(self, recon_results: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: Store findings in Graph DB"""
        
        vulnerabilities_found = []
        
        for host_data in recon_results["hosts"]:
            # Add host to graph
            host = Host(
                ip=host_data["ip"],
                hostname=host_data.get("hostname"),
                os=host_data.get("os"),
                status=host_data["status"]
            )
            self.graph_db.add_host(host)
            
            # Add services
            for port_data in host_data["open_ports"]:
                service = Service(
                    name=port_data["service"],
                    port=port_data["port"],
                    version=port_data.get("version", "")
                )
                self.graph_db.add_service(host_data["ip"], service)
                
                # Check for known vulnerabilities (simplified)
                # In production: query CVE database based on service + version
                if "apache" in port_data["service"].lower():
                    vuln = Vulnerability(
                        cve_id="CVE-2021-41773",
                        severity="CRITICAL",
                        description="Apache HTTP Server path traversal",
                        cvss_score=9.8
                    )
                    
                    service_id = f"{host_data['ip']}:{port_data['port']}/tcp"
                    self.graph_db.add_vulnerability(service_id, vuln)
                    
                    vulnerabilities_found.append({
                        "host": host_data["ip"],
                        "service": port_data["service"],
                        "cve": vuln.cve_id,
                        "severity": vuln.severity
                    })
        
        return {
            "hosts_stored": len(recon_results["hosts"]),
            "vulnerabilities_found": len(vulnerabilities_found),
            "vulnerabilities": vulnerabilities_found
        }
    
    async def _phase_cognitive_analysis(
        self,
        config: MissionConfig,
        recon_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 3: LLM agents analyze and plan"""
        
        # Execute cognitive agent workflow
        agent_state = await self.cognitive_orchestrator.execute_mission(
            mission_id=config.mission_id,
            target=config.target,
            recon_data=recon_results
        )
        
        return {
            "strategy": agent_state.strategy,
            "tactical_plan": agent_state.tactical_plan,
            "critique": agent_state.critique,
            "iterations": agent_state.iteration_count,
            "agent_messages": agent_state.messages
        }
    
    async def _phase_exploit_synthesis(
        self,
        config: MissionConfig,
        knowledge_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 4: Generate exploits for vulnerabilities"""
        
        exploits_generated = []
        
        for vuln in knowledge_results.get("vulnerabilities", []):
            # Create vulnerability context
            vuln_context = VulnerabilityContext(
                cve_id=vuln["cve"],
                service_name=vuln["service"],
                service_version="unknown",  # TODO: Extract from recon
                vulnerability_type="RCE",  # TODO: Determine from CVE
                description=f"Vulnerability in {vuln['service']}",
                target_os="Linux",  # TODO: From recon
                target_ip=vuln["host"],
                target_port=80  # TODO: From service data
            )
            
            # Synthesize exploit
            exploit = await self.exploit_synthesizer.synthesize(
                vuln_context=vuln_context,
                language=config.exploit_language,
                obfuscate=config.obfuscate_exploits
            )
            
            exploits_generated.append({
                "cve": vuln["cve"],
                "target": vuln["host"],
                "language": exploit.language,
                "code_length": len(exploit.code),
                "obfuscated": exploit.obfuscated_code is not None,
                "detection_risk": exploit.detection_risk
            })
        
        return {
            "exploits_generated": len(exploits_generated),
            "exploits": exploits_generated
        }
    
    async def _phase_execution_learning(
        self,
        config: MissionConfig,
        exploit_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 5: Execute exploits and learn from results"""
        
        execution_results = []
        
        for exploit_data in exploit_results.get("exploits", []):
            # Simulate execution (in production: use sandbox executor)
            # For now, we'll simulate outcomes
            
            attempt_id = str(uuid.uuid4())
            
            # Simulate outcome (70% success rate for demo)
            import random
            outcome = OutcomeType.SUCCESS if random.random() > 0.3 else OutcomeType.FAILURE
            
            # Create attempt record
            attempt = ExploitAttempt(
                attempt_id=attempt_id,
                mission_id=config.mission_id,
                timestamp=datetime.now(),
                target=exploit_data["target"],
                vulnerability_type="RCE",
                cve_id=exploit_data["cve"],
                exploit_code="[code redacted for security]",
                obfuscation_techniques=["base64"] if exploit_data["obfuscated"] else [],
                language=exploit_data["language"],
                outcome=outcome,
                execution_time=random.uniform(1.0, 5.0),
                agent_strategy="cognitive_synthesis"
            )
            
            # Record in RL loop
            await self.rl_loop.record_attempt(attempt)
            
            execution_results.append({
                "attempt_id": attempt_id,
                "target": exploit_data["target"],
                "outcome": outcome.value,
                "reward": attempt.reward
            })
        
        return {
            "attempts": len(execution_results),
            "results": execution_results
        }
    
    async def close(self):
        """Cleanup resources"""
        self.vector_db.close()
        self.graph_db.close()
        await self.rl_loop.close()
        logger.info("Pipeline closed")


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize pipeline
        pipeline = IntegratedCognitivePipeline()
        await pipeline.initialize()
        
        # Create mission
        config = MissionConfig(
            mission_id="demo-mission-001",
            target="192.168.1.0/24",
            scan_ports=[22, 80, 443],
            auto_exploit=True,
            obfuscate_exploits=True
        )
        
        # Execute
        results = await pipeline.execute_mission(config)
        
        # Display results
        print("\n" + "="*60)
        print("🎯 MISSION RESULTS")
        print("="*60)
        print(f"Mission ID: {results['mission_id']}")
        print(f"Target: {results['target']}")
        print(f"Status: {results['status']}")
        print(f"\nPhases Completed:")
        for phase, data in results.get("phases", {}).items():
            print(f"  ✓ {phase}")
        
        if "performance_metrics" in results:
            perf = results["performance_metrics"]["overall_performance"]
            print(f"\n📊 Performance:")
            print(f"  Success Rate: {perf.get('success_rate', 0):.1%}")
            print(f"  Total Attempts: {perf.get('total_attempts', 0)}")
        
        await pipeline.close()
    
    asyncio.run(main())
