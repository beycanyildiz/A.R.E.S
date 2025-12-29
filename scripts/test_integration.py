"""
A.R.E.S. Integration Test

This script tests all Phase 1 components:
1. Vector DB operations
2. Graph DB operations
3. Orchestrator API
4. Event messaging
5. Recon engine
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def test_vector_db():
    """Test Vector Database"""
    console.print("\n[bold cyan]Testing Vector Database...[/bold cyan]")
    
    try:
        from services.knowledge_matrix.vector_db import VectorDBManager, ExploitDocument
        
        db = VectorDBManager(host="localhost", port=19530)
        
        # Insert test document
        test_doc = ExploitDocument(
            id="TEST-CVE-2024-0001",
            title="Test SQL Injection Vulnerability",
            description="A critical SQL injection vulnerability in test application",
            cve_id="CVE-2024-0001",
            severity="CRITICAL",
            exploit_code="' OR '1'='1",
            source="TestDB",
            tags=["SQLi", "Web", "Critical"],
            created_at=datetime.now()
        )
        
        success = db.insert_documents([test_doc])
        
        if success:
            # Search
            results = db.search("SQL injection", top_k=3)
            
            console.print(f"[green]✓ Vector DB working - Found {len(results)} results[/green]")
            
            if results:
                console.print(f"  Top result: {results[0]['title']} (Score: {results[0]['similarity_score']:.3f})")
        
        db.close()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Vector DB test failed: {e}[/red]")
        return False


async def test_graph_db():
    """Test Graph Database"""
    console.print("\n[bold cyan]Testing Graph Database...[/bold cyan]")
    
    try:
        from services.knowledge_matrix.graph_db import (
            GraphDBManager, Host, Service, Vulnerability
        )
        
        db = GraphDBManager(
            uri="bolt://localhost:7687",
            user="neo4j",
            password=os.getenv("NEO4J_PASSWORD", "insecure_dev_password")
        )
        
        # Add test host
        test_host = Host(
            ip="10.0.0.100",
            hostname="test-server",
            os="Ubuntu",
            os_version="22.04",
            status="alive"
        )
        
        db.add_host(test_host)
        
        # Add test service
        test_service = Service(
            name="apache",
            port=80,
            version="2.4.41"
        )
        
        db.add_service("10.0.0.100", test_service)
        
        # Add vulnerability
        test_vuln = Vulnerability(
            cve_id="CVE-2021-44228",
            severity="CRITICAL",
            description="Log4Shell RCE",
            cvss_score=10.0
        )
        
        db.add_vulnerability("10.0.0.100:80/tcp", test_vuln)
        
        # Query
        vulns = db.get_vulnerable_services(severity="CRITICAL")
        
        console.print(f"[green]✓ Graph DB working - Found {len(vulns)} vulnerable services[/green]")
        
        if vulns:
            console.print(f"  {vulns[0]['host_ip']}:{vulns[0]['port']} - {vulns[0]['cve_id']}")
        
        db.close()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Graph DB test failed: {e}[/red]")
        return False


async def test_orchestrator():
    """Test Orchestrator API"""
    console.print("\n[bold cyan]Testing Orchestrator API...[/bold cyan]")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Health check
            async with session.get("http://localhost:8000/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    console.print(f"[green]✓ Orchestrator API working[/green]")
                    console.print(f"  Status: {data.get('status')}")
                    console.print(f"  Redis: {data.get('redis')}")
                    console.print(f"  RabbitMQ: {data.get('rabbitmq')}")
                    return True
                else:
                    console.print(f"[red]✗ Orchestrator returned {resp.status}[/red]")
                    return False
                    
    except Exception as e:
        console.print(f"[red]✗ Orchestrator test failed: {e}[/red]")
        console.print("  [yellow]Make sure orchestrator is running: cd services/orchestrator && python main.py[/yellow]")
        return False


async def test_recon_engine():
    """Test Recon Engine"""
    console.print("\n[bold cyan]Testing Recon Engine...[/bold cyan]")
    
    try:
        from services.recon_engine.scanner import ReconEngine
        
        engine = ReconEngine()
        
        # Test localhost scan (safe)
        result = await engine.scan_host("127.0.0.1", ports=[80, 443, 8000])
        
        console.print(f"[green]✓ Recon Engine working[/green]")
        console.print(f"  Target: {result.ip}")
        console.print(f"  Status: {result.status}")
        console.print(f"  Open ports: {len(result.open_ports)}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Recon Engine test failed: {e}[/red]")
        console.print("  [yellow]Note: Requires nmap to be installed[/yellow]")
        return False


async def test_messaging():
    """Test RabbitMQ messaging"""
    console.print("\n[bold cyan]Testing Message Queue...[/bold cyan]")
    
    try:
        import aio_pika
        
        connection = await aio_pika.connect_robust(
            "amqp://ares_admin:insecure_dev_password@localhost:5672/ares"
        )
        
        channel = await connection.channel()
        
        # Declare test queue
        queue = await channel.declare_queue("test_queue", auto_delete=True)
        
        # Send message
        await channel.default_exchange.publish(
            aio_pika.Message(body=b"Test message"),
            routing_key="test_queue"
        )
        
        # Receive message
        message = await queue.get(timeout=5)
        
        if message:
            await message.ack()
            console.print("[green]✓ Message queue working[/green]")
            result = True
        else:
            console.print("[red]✗ No message received[/red]")
            result = False
        
        await connection.close()
        return result
        
    except Exception as e:
        console.print(f"[red]✗ Message queue test failed: {e}[/red]")
        return False


async def run_all_tests():
    """Run all integration tests"""
    console.print(Panel.fit(
        "[bold cyan]A.R.E.S. Integration Tests[/bold cyan]\n"
        "Testing all Phase 1 components",
        border_style="cyan"
    ))
    
    tests = [
        ("Vector Database", test_vector_db),
        ("Graph Database", test_graph_db),
        ("Message Queue", test_messaging),
        ("Orchestrator API", test_orchestrator),
        ("Recon Engine", test_recon_engine),
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
        console.print("\n[bold green]🎉 All tests passed! Phase 1 is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠ Some tests failed. Check the logs above.[/bold yellow]")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
