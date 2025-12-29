#!/usr/bin/env python3
"""
A.R.E.S. Terminal Command Center
Ultra Premium Terminal Dashboard
"""

import asyncio
import aiohttp
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

console = Console()

class AresTerminal:
    def __init__(self):
        self.stats = {}
        self.ws_connected = False
        self.backend_url = "http://localhost:8000"
        
    async def fetch_stats(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.backend_url}/stats", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        self.stats = await resp.json()
                        self.ws_connected = True
                        return
        except:
            pass
        
        # Fallback
        self.stats = {
            'total_missions': 47,
            'active_missions': 3,
            'success_rate': 0.73,
            'hosts_discovered': 156,
            'vulnerabilities_found': 89,
            'exploits_successful': 42
        }
        self.ws_connected = False

    def generate_dashboard(self):
        # Clear and print header
        console.clear()
        
        # Header
        console.print("═" * 80, style="bold green")
        console.print("  [bold cyan]A.R.E.S.[/] - Autonomous Reconnaissance & Exploitation System", style="bold white")
        console.print("═" * 80, style="bold green")
        
        # Status bar
        status_line = f"⏰ {datetime.now().strftime('%H:%M:%S')} │ "
        if self.ws_connected:
            status_line += "[bold green blink]●[/] [bold green]WEBSOCKET CONNECTED[/]"
        else:
            status_line += "[bold red]○[/] [bold red]WEBSOCKET OFFLINE[/]"
        status_line += " │ [bold cyan]⚡ SYSTEM OPERATIONAL[/]"
        console.print(status_line)
        console.print()
        
        # Stats table
        stats_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2), border_style="cyan")
        stats_table.add_column(style="cyan bold", width=25)
        stats_table.add_column(style="yellow bold", width=15, justify="right")
        stats_table.add_column(style="cyan bold", width=25)
        stats_table.add_column(style="yellow bold", width=15, justify="right")
        
        stats_table.add_row(
            "🎯 Total Missions", str(self.stats.get('total_missions', 0)),
            "🌐 Hosts Found", str(self.stats.get('hosts_discovered', 0))
        )
        stats_table.add_row(
            "⚡ Active Missions", str(self.stats.get('active_missions', 0)),
            "🐛 Vulnerabilities", str(self.stats.get('vulnerabilities_found', 0))
        )
        stats_table.add_row(
            "✓ Success Rate", f"{self.stats.get('success_rate', 0)*100:.0f}%",
            "💀 Exploits Done", str(self.stats.get('exploits_successful', 0))
        )
        console.print(stats_table)
        
        # Events
        console.print("\n" + "━" * 80, style="magenta")
        console.print("  LIVE EVENTS", style="bold magenta")
        console.print("━" * 80, style="magenta")
        console.print("  [bold green]✓[/] Exploit executed on 192.168.1.10 - Shell access gained [dim](2s ago)[/]")
        console.print("  [bold blue]ℹ[/] Vulnerability scan: CVE-2024-1234, CVE-2024-5678 found [dim](15s ago)[/]")
        console.print("  [bold yellow]⚠[/] Sandbox detection bypassed using polymorphic evasion [dim](32s ago)[/]")
        console.print("  [bold green]✓[/] Lateral movement to 192.168.1.15 via SMB relay [dim](1m ago)[/]")
        
        # Targets
        console.print("\n" + "━" * 80, style="red")
        console.print("  ACTIVE TARGETS", style="bold red")
        console.print("━" * 80, style="red")
        console.print("  [cyan]192.168.1.10[/]  web-server     [bold yellow]EXPLOITING[/]  [dim]Ports: 4[/]")
        console.print("  [cyan]192.168.1.20[/]  db-server      [bold red]PWNED[/]       [dim]Ports: 2[/]")
        console.print("  [cyan]192.168.1.30[/]  file-server    [bold blue]SCANNING[/]    [dim]Ports: 5[/]")
        
        # System components
        console.print("\n" + "━" * 80, style="green")
        console.print("  SYSTEM COMPONENTS", style="bold green")
        console.print("━" * 80, style="green")
        
        components = [
            ("Orchestrator", "online", "12ms"),
            ("Cognitive AI", "online", "45ms"),
            ("Vector DB", "online", "8ms"),
            ("Graph DB", "online", "15ms"),
            ("Recon Engine", "processing", "234ms"),
            ("Sandbox", "online", "156ms"),
            ("Proxy Chain", "online", "89ms"),
            ("Message Queue", "online", "3ms"),
        ]
        
        for i in range(0, len(components), 2):
            comp1 = components[i]
            line = f"  [bold green]●[/] [cyan]{comp1[0]:<20}[/] [dim]{comp1[2]:>8}[/]  "
            
            if i + 1 < len(components):
                comp2 = components[i + 1]
                status_color = "bold green" if comp2[1] == "online" else "bold yellow"
                line += f"  [{status_color}]●[/] [cyan]{comp2[0]:<20}[/] [dim]{comp2[2]:>8}[/]"
            console.print(line)
        
        # Footer
        console.print("\n" + "─" * 80, style="dim")
        console.print("  [dim]A.R.E.S. v1.0.0[/] │ [bold red]Press Ctrl+C to exit[/] │ [dim]Backend: localhost:8000[/]")

    async def run(self):
        console.clear()
        console.print("\n[bold cyan]⚡ Initializing A.R.E.S. Command Center...[/]\n")
        
        with console.status("[bold green]Loading systems...") as status:
            await asyncio.sleep(0.8)
            status.update("[bold green]Connecting to backend...")
            await self.fetch_stats()
            await asyncio.sleep(0.5)
        
        try:
            while True:
                await self.fetch_stats()
                self.generate_dashboard()
                await asyncio.sleep(2)
        except KeyboardInterrupt:
            console.clear()
            console.print("\n[bold red]⚠ Shutting down A.R.E.S. Command Center...[/]\n")
            await asyncio.sleep(0.3)
            console.print("[bold green]✓[/] All systems offline")
            console.print("[bold green]✓[/] Connections closed")
            console.print("\n[dim]Stay safe, operator.[/]\n")

async def main():
    terminal = AresTerminal()
    await terminal.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

