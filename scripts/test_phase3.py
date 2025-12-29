"""
A.R.E.S. Phase 3 Integration Test

Tests sandbox execution and evasion:
1. Sandbox executor (Docker/K8s)
2. Proxy chain manager
3. Evasion techniques
4. Environment analysis
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def test_docker_availability():
    """Test if Docker is available"""
    console.print("\n[bold cyan]Testing Docker Availability...[/bold cyan]")
    
    try:
        import docker
        client = docker.from_env()
        client.ping()
        
        console.print("[green]✓ Docker is available[/green]")
        
        # List images
        images = client.images.list()
        console.print(f"  Docker images: {len(images)}")
        
        return True
        
    except Exception as e:
        console.print(f"[yellow]⚠ Docker not available: {e}[/yellow]")
        console.print("  [yellow]Install Docker Desktop to use sandbox executor[/yellow]")
        return False


async def test_kubernetes_availability():
    """Test if Kubernetes is available"""
    console.print("\n[bold cyan]Testing Kubernetes Availability...[/bold cyan]")
    
    try:
        from kubernetes import client, config
        
        # Try to load config
        try:
            config.load_incluster_config()
            console.print("[green]✓ Running inside Kubernetes cluster[/green]")
            return True
        except:
            config.load_kube_config()
            console.print("[green]✓ Kubernetes config loaded[/green]")
        
        # Test connection
        v1 = client.CoreV1Api()
        v1.list_namespace()
        
        console.print("[green]✓ Kubernetes is available[/green]")
        return True
        
    except Exception as e:
        console.print(f"[yellow]⚠ Kubernetes not available: {e}[/yellow]")
        console.print("  [yellow]Will use Docker fallback[/yellow]")
        return False


async def test_sandbox_executor():
    """Test sandbox executor"""
    console.print("\n[bold cyan]Testing Sandbox Executor...[/bold cyan]")
    
    try:
        from services.sandbox_executor import SandboxExecutor, SandboxConfig
        
        # Initialize
        executor = SandboxExecutor()
        console.print(f"  Mode: {executor.mode}")
        
        # Test code
        test_code = """
print("Hello from sandbox!")
print("Testing network...")
import socket
try:
    socket.gethostbyname('google.com')
    print("Network: OK")
except:
    print("Network: FAILED")
"""
        
        # Execute
        config = SandboxConfig(
            timeout_seconds=30,
            enable_network=True,
            auto_cleanup=True
        )
        
        console.print("  Executing test code...")
        result = await executor.execute(test_code, language="python", config=config)
        
        console.print(f"[green]✓ Sandbox executor working[/green]")
        console.print(f"  Execution ID: {result.execution_id}")
        console.print(f"  Success: {result.success}")
        console.print(f"  Exit Code: {result.exit_code}")
        console.print(f"  Execution Time: {result.execution_time:.2f}s")
        
        if result.stdout:
            console.print(f"  Output preview: {result.stdout[:100]}...")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Sandbox executor test failed: {e}[/red]")
        return False


async def test_proxy_chain():
    """Test proxy chain manager"""
    console.print("\n[bold cyan]Testing Proxy Chain Manager...[/bold cyan]")
    
    try:
        from services.sandbox_executor import ProxyChainManager, ProxyNode
        
        # Initialize
        manager = ProxyChainManager()
        
        # Get TOR proxy
        tor_proxy = await manager.get_tor_proxy()
        console.print(f"  TOR proxy: {tor_proxy.host}:{tor_proxy.port}")
        
        # Build chain
        chain = await manager.build_chain(hops=1, use_tor=True)
        console.print(f"[green]✓ Proxy chain built with {len(chain)} hops[/green]")
        
        for i, proxy in enumerate(chain, 1):
            console.print(f"  {i}. {proxy.proxy_type}://{proxy.host}:{proxy.port}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Proxy chain test failed: {e}[/red]")
        console.print("  [yellow]Note: TOR must be running (tor command)[/yellow]")
        return False


async def test_evasion_techniques():
    """Test evasion techniques"""
    console.print("\n[bold cyan]Testing Evasion Techniques...[/bold cyan]")
    
    try:
        from services.sandbox_executor import (
            EvasionOrchestrator,
            AntiDebuggingDetector,
            SandboxDetector,
            PolymorphicCodeGenerator
        )
        
        # Analyze environment
        profile = EvasionOrchestrator.analyze_environment()
        
        console.print(f"[green]✓ Environment analysis complete[/green]")
        console.print(f"  Debugger Detected: {profile.is_debugger}")
        console.print(f"  Sandbox Detected: {profile.is_sandbox}")
        console.print(f"  OS: {profile.os_type}")
        console.print(f"  CPUs: {profile.cpu_count}")
        console.print(f"  RAM: {profile.ram_mb} MB")
        console.print(f"  Uptime: {profile.uptime_seconds} seconds")
        console.print(f"  Risk Score: {profile.risk_score:.2f}")
        
        # Test polymorphic code
        original = "print('Test payload')"
        polymorphic = EvasionOrchestrator.create_polymorphic_payload(original)
        
        console.print(f"\n  Polymorphic code generated: {len(polymorphic)} bytes")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Evasion test failed: {e}[/red]")
        return False


async def test_anti_debugging():
    """Test anti-debugging detection"""
    console.print("\n[bold cyan]Testing Anti-Debugging Detection...[/bold cyan]")
    
    try:
        from services.sandbox_executor import AntiDebuggingDetector
        
        # Run checks
        timing_result = AntiDebuggingDetector.timing_check()
        process_result = AntiDebuggingDetector.process_check()
        
        console.print(f"[green]✓ Anti-debugging checks complete[/green]")
        console.print(f"  Timing check: {'DETECTED' if timing_result else 'OK'}")
        console.print(f"  Process check: {'DETECTED' if process_result else 'OK'}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Anti-debugging test failed: {e}[/red]")
        return False


async def test_sandbox_detection():
    """Test sandbox/VM detection"""
    console.print("\n[bold cyan]Testing Sandbox/VM Detection...[/bold cyan]")
    
    try:
        from services.sandbox_executor import SandboxDetector
        
        # Run checks
        vm_result = SandboxDetector.vm_detection()
        artifacts_result = SandboxDetector.sandbox_artifacts()
        resource_result = SandboxDetector.resource_check()
        uptime_result = SandboxDetector.uptime_check()
        
        console.print(f"[green]✓ Sandbox detection checks complete[/green]")
        console.print(f"  VM detected: {vm_result}")
        console.print(f"  Sandbox artifacts: {artifacts_result}")
        console.print(f"  Resource constraints: {resource_result}")
        console.print(f"  Suspicious uptime: {uptime_result}")
        
        overall = SandboxDetector.detect()
        console.print(f"  Overall: {'SANDBOX DETECTED' if overall else 'REAL MACHINE'}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Sandbox detection test failed: {e}[/red]")
        return False


async def run_all_tests():
    """Run all Phase 3 tests"""
    console.print(Panel.fit(
        "[bold cyan]A.R.E.S. Phase 3 - Sandbox Executor & Evasion Tests[/bold cyan]\n"
        "Testing isolated execution and stealth techniques",
        border_style="cyan"
    ))
    
    tests = [
        ("Docker Availability", test_docker_availability),
        ("Kubernetes Availability", test_kubernetes_availability),
        ("Evasion Techniques", test_evasion_techniques),
        ("Anti-Debugging", test_anti_debugging),
        ("Sandbox Detection", test_sandbox_detection),
        ("Proxy Chain Manager", test_proxy_chain),
        ("Sandbox Executor", test_sandbox_executor),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            console.print(f"[red]✗ {test_name} crashed: {e}[/red]")
            results.append((test_name, False))
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("="*60)
    
    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    for test_name, passed in results:
        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        table.add_row(test_name, status)
    
    console.print(table)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    console.print(f"\n[bold]Results: {passed_count}/{total_count} tests passed[/bold]")
    
    if passed_count == total_count:
        console.print("\n[bold green]🎉 All tests passed! Phase 3 is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠ Some tests failed. Check the logs above.[/bold yellow]")
        console.print("\n[yellow]Common issues:[/yellow]")
        console.print("  1. Docker not installed (docker.com)")
        console.print("  2. Kubernetes not configured (kubectl)")
        console.print("  3. TOR not running (tor command)")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
