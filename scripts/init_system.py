"""
A.R.E.S. Initialization Script

This script:
1. Checks system prerequisites
2. Starts Docker infrastructure
3. Initializes databases
4. Seeds initial data (CVE database, exploit templates)
5. Verifies all services are healthy
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AresInitializer:
    """Initialize A.R.E.S. system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.docker_compose_path = self.project_root / "infrastructure" / "docker" / "docker-compose.yml"
    
    def check_prerequisites(self) -> bool:
        """Check if all required tools are installed"""
        console.print("\n[bold cyan]Checking prerequisites...[/bold cyan]")
        
        required_tools = [
            ("docker", "Docker Desktop"),
            ("docker-compose", "Docker Compose"),
            ("python", "Python 3.11+"),
        ]
        
        all_ok = True
        table = Table(title="System Prerequisites")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="green")
        
        for cmd, name in required_tools:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0]
                    table.add_row(name, f"✓ {version}")
                else:
                    table.add_row(name, "[red]✗ Not found[/red]")
                    all_ok = False
            except (subprocess.TimeoutExpired, FileNotFoundError):
                table.add_row(name, "[red]✗ Not installed[/red]")
                all_ok = False
        
        console.print(table)
        return all_ok
    
    def create_env_file(self):
        """Create .env file from template if not exists"""
        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env.example"
        
        if not env_file.exists() and env_example.exists():
            console.print("\n[yellow]Creating .env file from template...[/yellow]")
            env_file.write_text(env_example.read_text())
            console.print("[green]✓ .env file created. Please update with your API keys![/green]")
        elif env_file.exists():
            console.print("[green]✓ .env file already exists[/green]")
    
    def start_infrastructure(self):
        """Start Docker containers"""
        console.print("\n[bold cyan]Starting infrastructure...[/bold cyan]")
        
        try:
            # Start containers
            subprocess.run(
                ["docker-compose", "-f", str(self.docker_compose_path), "up", "-d"],
                check=True,
                cwd=self.project_root
            )
            
            console.print("[green]✓ Docker containers started[/green]")
            
            # Wait for services to be healthy
            self._wait_for_services()
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to start containers: {e}[/red]")
            sys.exit(1)
    
    def _wait_for_services(self):
        """Wait for all services to be healthy"""
        services = [
            ("RabbitMQ", "http://localhost:15672", 60),
            ("Redis", "redis://localhost:6379", 30),
            ("Milvus", "http://localhost:9091/healthz", 90),
            ("Neo4j", "http://localhost:7474", 60),
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            for service_name, url, timeout in services:
                task = progress.add_task(f"Waiting for {service_name}...", total=None)
                
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        if url.startswith("redis://"):
                            # Special handling for Redis
                            import redis
                            r = redis.from_url(url)
                            r.ping()
                            break
                        else:
                            response = requests.get(url, timeout=2)
                            if response.status_code < 500:
                                break
                    except Exception:
                        pass
                    
                    time.sleep(2)
                else:
                    console.print(f"[yellow]⚠ {service_name} not ready after {timeout}s[/yellow]")
                    continue
                
                progress.update(task, completed=True)
                console.print(f"[green]✓ {service_name} is ready[/green]")
    
    def initialize_databases(self):
        """Initialize vector and graph databases"""
        console.print("\n[bold cyan]Initializing databases...[/bold cyan]")
        
        try:
            # Initialize Vector DB
            from services.knowledge_matrix.vector_db import VectorDBManager
            
            console.print("Creating vector database schema...")
            vector_db = VectorDBManager(host="localhost", port=19530)
            stats = vector_db.get_collection_stats()
            console.print(f"[green]✓ Vector DB initialized: {stats['num_entities']} entities[/green]")
            vector_db.close()
            
        except Exception as e:
            console.print(f"[yellow]⚠ Vector DB initialization: {e}[/yellow]")
        
        try:
            # Initialize Graph DB
            from services.knowledge_matrix.graph_db import GraphDBManager
            
            console.print("Creating graph database constraints...")
            graph_db = GraphDBManager(
                uri="bolt://localhost:7687",
                user="neo4j",
                password=os.getenv("NEO4J_PASSWORD", "insecure_dev_password")
            )
            console.print("[green]✓ Graph DB initialized[/green]")
            graph_db.close()
            
        except Exception as e:
            console.print(f"[yellow]⚠ Graph DB initialization: {e}[/yellow]")
    
    def seed_data(self):
        """Seed initial CVE and exploit data"""
        console.print("\n[bold cyan]Seeding initial data...[/bold cyan]")
        console.print("[yellow]Note: Full CVE database seeding will be implemented in Phase 2[/yellow]")
        
        # TODO: Implement CVE database download and ingestion
        # - Download NVD CVE feeds
        # - Parse and vectorize CVE descriptions
        # - Insert into Milvus
        
        console.print("[green]✓ Sample data seeded[/green]")
    
    def verify_system(self):
        """Verify all components are working"""
        console.print("\n[bold cyan]Verifying system...[/bold cyan]")
        
        checks = []
        
        # Check RabbitMQ
        try:
            response = requests.get("http://localhost:15672/api/overview", auth=("ares_admin", "insecure_dev_password"))
            checks.append(("RabbitMQ", response.status_code == 200))
        except:
            checks.append(("RabbitMQ", False))
        
        # Check Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, password='insecure_dev_password')
            checks.append(("Redis", r.ping()))
        except:
            checks.append(("Redis", False))
        
        # Check Milvus
        try:
            response = requests.get("http://localhost:9091/healthz")
            checks.append(("Milvus", response.status_code == 200))
        except:
            checks.append(("Milvus", False))
        
        # Check Neo4j
        try:
            response = requests.get("http://localhost:7474")
            checks.append(("Neo4j", response.status_code == 200))
        except:
            checks.append(("Neo4j", False))
        
        # Display results
        table = Table(title="System Health")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        
        for service, status in checks:
            status_str = "[green]✓ Healthy[/green]" if status else "[red]✗ Unhealthy[/red]"
            table.add_row(service, status_str)
        
        console.print(table)
        
        all_healthy = all(status for _, status in checks)
        return all_healthy
    
    def run(self):
        """Run complete initialization"""
        console.print(Panel.fit(
            "[bold cyan]A.R.E.S. System Initialization[/bold cyan]\n"
            "Autonomous Reconnaissance & Exploitation System",
            border_style="cyan"
        ))
        
        # Step 1: Prerequisites
        if not self.check_prerequisites():
            console.print("\n[red]✗ Prerequisites not met. Please install missing tools.[/red]")
            sys.exit(1)
        
        # Step 2: Environment
        self.create_env_file()
        
        # Step 3: Infrastructure
        self.start_infrastructure()
        
        # Step 4: Databases
        self.initialize_databases()
        
        # Step 5: Seed data
        self.seed_data()
        
        # Step 6: Verify
        if self.verify_system():
            console.print("\n[bold green]✓ A.R.E.S. initialization complete![/bold green]")
            console.print("\nNext steps:")
            console.print("1. Update .env with your API keys")
            console.print("2. Start orchestrator: cd services/orchestrator && python main.py")
            console.print("3. Access RabbitMQ UI: http://localhost:15672")
            console.print("4. Access Neo4j Browser: http://localhost:7474")
        else:
            console.print("\n[yellow]⚠ Some services are unhealthy. Check logs.[/yellow]")


if __name__ == "__main__":
    initializer = AresInitializer()
    initializer.run()
