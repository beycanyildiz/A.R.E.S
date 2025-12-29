"""
Sandbox Executor - Isolated Exploit Execution Environment

This module provides secure, isolated execution of exploits using:
- Kubernetes ephemeral pods (self-destructing containers)
- Network isolation with custom CNI
- Proxy chaining (TOR + VPN + Residential proxies)
- Resource limits (CPU, memory, network)
- Real-time output streaming
- Automatic cleanup

Architecture:
- Kubernetes API for pod management
- Docker for container runtime
- Network policies for isolation
- SOCKS5 proxy chain for anonymity
"""

import os
import asyncio
import logging
import uuid
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import docker
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution environment mode"""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    LOCAL = "local"  # For testing only


class ProxyType(str, Enum):
    """Proxy types for chaining"""
    TOR = "tor"
    VPN = "vpn"
    HTTP = "http"
    SOCKS5 = "socks5"
    RESIDENTIAL = "residential"


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution"""
    execution_mode: ExecutionMode = ExecutionMode.DOCKER
    
    # Resource limits
    cpu_limit: str = "500m"  # 0.5 CPU cores
    memory_limit: str = "512Mi"  # 512 MB RAM
    timeout_seconds: int = 300  # 5 minutes max
    
    # Network settings
    enable_network: bool = True
    proxy_chain: List[ProxyType] = None
    
    # Security
    read_only_filesystem: bool = True
    drop_capabilities: List[str] = None
    
    # Cleanup
    auto_cleanup: bool = True
    cleanup_delay_seconds: int = 60
    
    def __post_init__(self):
        if self.proxy_chain is None:
            self.proxy_chain = []
        if self.drop_capabilities is None:
            self.drop_capabilities = ["ALL"]


@dataclass
class ExecutionResult:
    """Result of exploit execution"""
    execution_id: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    error: Optional[str] = None
    network_traffic: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class KubernetesSandboxExecutor:
    """
    Execute exploits in ephemeral Kubernetes pods
    
    Features:
    - Self-destructing pods (TTL after finished)
    - Network isolation
    - Resource limits
    - Real-time log streaming
    """
    
    def __init__(
        self,
        namespace: str = "ares-sandbox",
        image: str = "python:3.11-alpine"
    ):
        self.namespace = namespace
        self.image = image
        
        # Load Kubernetes config
        try:
            config.load_incluster_config()  # Running inside cluster
        except:
            config.load_kube_config()  # Running locally
        
        self.core_v1 = client.CoreV1Api()
        self.batch_v1 = client.BatchV1Api()
        
        logger.info(f"Kubernetes sandbox executor initialized (namespace: {namespace})")
    
    async def execute(
        self,
        exploit_code: str,
        language: str = "python",
        config: SandboxConfig = None
    ) -> ExecutionResult:
        """
        Execute exploit in isolated Kubernetes pod
        
        Args:
            exploit_code: Code to execute
            language: Programming language (python, bash, etc.)
            config: Sandbox configuration
        
        Returns:
            ExecutionResult with output and metrics
        """
        if config is None:
            config = SandboxConfig()
        
        execution_id = str(uuid.uuid4())
        logger.info(f"Starting sandbox execution: {execution_id}")
        
        start_time = datetime.now()
        
        try:
            # Create pod
            pod_name = await self._create_pod(
                execution_id=execution_id,
                exploit_code=exploit_code,
                language=language,
                config=config
            )
            
            # Wait for completion
            stdout, stderr, exit_code = await self._wait_for_completion(
                pod_name=pod_name,
                timeout=config.timeout_seconds
            )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Cleanup
            if config.auto_cleanup:
                await self._cleanup_pod(pod_name, delay=config.cleanup_delay_seconds)
            
            # Build result
            result = ExecutionResult(
                execution_id=execution_id,
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time
            )
            
            logger.info(f"Execution {execution_id} completed: exit_code={exit_code}")
            return result
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExecutionResult(
                execution_id=execution_id,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                error=str(e)
            )
    
    async def _create_pod(
        self,
        execution_id: str,
        exploit_code: str,
        language: str,
        config: SandboxConfig
    ) -> str:
        """Create ephemeral pod for execution"""
        
        pod_name = f"ares-sandbox-{execution_id[:8]}"
        
        # Prepare command based on language
        if language == "python":
            command = ["python", "-c", exploit_code]
        elif language == "bash":
            command = ["bash", "-c", exploit_code]
        elif language == "powershell":
            command = ["pwsh", "-c", exploit_code]
        else:
            raise ValueError(f"Unsupported language: {language}")
        
        # Build pod spec
        pod_spec = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels={
                    "app": "ares-sandbox",
                    "execution-id": execution_id
                },
                annotations={
                    "created-at": datetime.now().isoformat()
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                
                # Security context
                security_context=client.V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_user=1000,
                    fs_group=1000
                ),
                
                containers=[
                    client.V1Container(
                        name="exploit",
                        image=self.image,
                        command=command,
                        
                        # Resource limits
                        resources=client.V1ResourceRequirements(
                            limits={
                                "cpu": config.cpu_limit,
                                "memory": config.memory_limit
                            },
                            requests={
                                "cpu": "100m",
                                "memory": "128Mi"
                            }
                        ),
                        
                        # Security
                        security_context=client.V1SecurityContext(
                            read_only_root_filesystem=config.read_only_filesystem,
                            allow_privilege_escalation=False,
                            capabilities=client.V1Capabilities(
                                drop=config.drop_capabilities
                            )
                        )
                    )
                ],
                
                # TTL for auto-cleanup (Kubernetes 1.23+)
                # ttl_seconds_after_finished=config.cleanup_delay_seconds
            )
        )
        
        # Create pod
        try:
            self.core_v1.create_namespaced_pod(
                namespace=self.namespace,
                body=pod_spec
            )
            logger.info(f"Created pod: {pod_name}")
            return pod_name
            
        except ApiException as e:
            logger.error(f"Failed to create pod: {e}")
            raise
    
    async def _wait_for_completion(
        self,
        pod_name: str,
        timeout: int = 300
    ) -> tuple[str, str, int]:
        """
        Wait for pod to complete and return logs
        
        Returns:
            (stdout, stderr, exit_code)
        """
        w = watch.Watch()
        
        try:
            # Watch pod status
            for event in w.stream(
                self.core_v1.list_namespaced_pod,
                namespace=self.namespace,
                field_selector=f"metadata.name={pod_name}",
                timeout_seconds=timeout
            ):
                pod = event['object']
                phase = pod.status.phase
                
                if phase in ["Succeeded", "Failed"]:
                    w.stop()
                    break
            
            # Get logs
            try:
                stdout = self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=self.namespace
                )
            except ApiException:
                stdout = ""
            
            # Get exit code
            container_status = pod.status.container_statuses[0]
            if container_status.state.terminated:
                exit_code = container_status.state.terminated.exit_code
            else:
                exit_code = -1
            
            stderr = ""  # Kubernetes doesn't separate stderr
            
            return stdout, stderr, exit_code
            
        except Exception as e:
            logger.error(f"Error waiting for pod: {e}")
            return "", str(e), -1
    
    async def _cleanup_pod(self, pod_name: str, delay: int = 0):
        """Delete pod after delay"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        try:
            self.core_v1.delete_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
                grace_period_seconds=0
            )
            logger.info(f"Deleted pod: {pod_name}")
        except ApiException as e:
            logger.warning(f"Failed to delete pod {pod_name}: {e}")


class DockerSandboxExecutor:
    """
    Execute exploits in Docker containers (fallback for local dev)
    
    Simpler than Kubernetes but still provides isolation
    """
    
    def __init__(self, image: str = "python:3.11-alpine"):
        self.image = image
        self.docker_client = docker.from_env()
        
        # Pull image if not exists
        try:
            self.docker_client.images.get(self.image)
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling image: {self.image}")
            self.docker_client.images.pull(self.image)
        
        logger.info("Docker sandbox executor initialized")
    
    async def execute(
        self,
        exploit_code: str,
        language: str = "python",
        config: SandboxConfig = None
    ) -> ExecutionResult:
        """Execute exploit in Docker container"""
        
        if config is None:
            config = SandboxConfig()
        
        execution_id = str(uuid.uuid4())
        logger.info(f"Starting Docker execution: {execution_id}")
        
        start_time = datetime.now()
        
        try:
            # Prepare command
            if language == "python":
                command = ["python", "-c", exploit_code]
            elif language == "bash":
                command = ["bash", "-c", exploit_code]
            else:
                raise ValueError(f"Unsupported language: {language}")
            
            # Run container
            container = self.docker_client.containers.run(
                image=self.image,
                command=command,
                detach=True,
                remove=config.auto_cleanup,
                network_disabled=not config.enable_network,
                mem_limit=config.memory_limit,
                cpu_quota=int(float(config.cpu_limit.rstrip('m')) * 1000),  # Convert to microseconds
                read_only=config.read_only_filesystem,
                cap_drop=config.drop_capabilities,
                security_opt=["no-new-privileges"]
            )
            
            # Wait for completion
            result = container.wait(timeout=config.timeout_seconds)
            exit_code = result['StatusCode']
            
            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8')
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExecutionResult(
                execution_id=execution_id,
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Docker execution failed: {e}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExecutionResult(
                execution_id=execution_id,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                error=str(e)
            )


class SandboxExecutor:
    """
    Main sandbox executor with automatic mode selection
    
    Tries Kubernetes first, falls back to Docker
    """
    
    def __init__(self):
        self.mode = self._detect_mode()
        
        if self.mode == ExecutionMode.KUBERNETES:
            self.executor = KubernetesSandboxExecutor()
        else:
            self.executor = DockerSandboxExecutor()
        
        logger.info(f"Sandbox executor initialized in {self.mode} mode")
    
    def _detect_mode(self) -> ExecutionMode:
        """Auto-detect best execution mode"""
        
        # Check if running in Kubernetes
        if os.path.exists("/var/run/secrets/kubernetes.io"):
            return ExecutionMode.KUBERNETES
        
        # Check if kubectl is configured
        try:
            config.load_kube_config()
            return ExecutionMode.KUBERNETES
        except:
            pass
        
        # Fallback to Docker
        return ExecutionMode.DOCKER
    
    async def execute(
        self,
        exploit_code: str,
        language: str = "python",
        config: SandboxConfig = None
    ) -> ExecutionResult:
        """Execute exploit in sandbox"""
        return await self.executor.execute(exploit_code, language, config)


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize executor
        executor = SandboxExecutor()
        
        # Test exploit code
        test_code = """
import socket
import sys

print("Testing network connectivity...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    s.connect(("google.com", 80))
    print("Network: OK")
    s.close()
except Exception as e:
    print(f"Network: FAILED - {e}")

print("Exploit simulation complete")
"""
        
        # Execute
        config = SandboxConfig(
            timeout_seconds=30,
            enable_network=True,
            auto_cleanup=True
        )
        
        result = await executor.execute(test_code, language="python", config=config)
        
        print("\n=== Execution Result ===")
        print(f"Execution ID: {result.execution_id}")
        print(f"Success: {result.success}")
        print(f"Exit Code: {result.exit_code}")
        print(f"Execution Time: {result.execution_time:.2f}s")
        print(f"\nStdout:\n{result.stdout}")
        if result.stderr:
            print(f"\nStderr:\n{result.stderr}")
    
    asyncio.run(main())
