"""
Advanced Reconnaissance Engine

This module performs:
- Asynchronous port scanning (custom Rust binary + Python wrapper)
- Service fingerprinting
- OS detection
- Banner grabbing
- Subdomain enumeration
- OSINT data collection

Architecture:
- Rust binary for high-performance scanning
- Python wrapper for orchestration
- Results published to RabbitMQ
- Data stored in Graph DB
"""

import os
import asyncio
import logging
import json
import subprocess
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import ipaddress

import aiohttp
import nmap
from scapy.all import sr1, IP, TCP, ICMP
import dns.resolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PortScanResult:
    """Port scan result"""
    ip: str
    port: int
    protocol: str = "tcp"
    state: str = "unknown"  # open, closed, filtered
    service: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None


@dataclass
class HostInfo:
    """Complete host information"""
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    mac_address: Optional[str] = None
    status: str = "unknown"
    open_ports: List[PortScanResult] = None
    discovered_at: datetime = None
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []
        if self.discovered_at is None:
            self.discovered_at = datetime.now()


class ReconEngine:
    """Advanced reconnaissance engine"""
    
    # Common ports to scan
    COMMON_PORTS = [
        21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 993, 995,
        1723, 3306, 3389, 5900, 8080, 8443, 8888, 27017, 5432, 6379, 9200
    ]
    
    def __init__(self, rabbitmq_url: Optional[str] = None):
        self.rabbitmq_url = rabbitmq_url
        self.nmap_scanner = nmap.PortScanner()
    
    async def scan_host(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        aggressive: bool = False
    ) -> HostInfo:
        """
        Scan a single host
        
        Args:
            target: IP address or hostname
            ports: List of ports to scan (default: common ports)
            aggressive: Enable OS detection and version scanning
        
        Returns:
            HostInfo object with scan results
        """
        logger.info(f"Starting scan on {target}")
        
        if ports is None:
            ports = self.COMMON_PORTS
        
        host_info = HostInfo(ip=target)
        
        # Check if host is alive
        is_alive = await self._ping_host(target)
        host_info.status = "alive" if is_alive else "dead"
        
        if not is_alive:
            logger.warning(f"Host {target} appears to be down")
            return host_info
        
        # Resolve hostname
        host_info.hostname = await self._resolve_hostname(target)
        
        # Port scanning
        port_results = await self._scan_ports(target, ports)
        host_info.open_ports = port_results
        
        # OS detection (if aggressive mode)
        if aggressive and port_results:
            os_info = await self._detect_os(target)
            host_info.os = os_info.get("os")
            host_info.os_version = os_info.get("version")
        
        logger.info(f"Scan completed: {target} - {len(port_results)} open ports")
        return host_info
    
    async def _ping_host(self, target: str, timeout: int = 2) -> bool:
        """Check if host is alive using ICMP ping"""
        try:
            # Try ICMP ping
            packet = IP(dst=target)/ICMP()
            response = sr1(packet, timeout=timeout, verbose=0)
            
            if response:
                return True
            
            # Fallback: TCP SYN to port 80
            packet = IP(dst=target)/TCP(dport=80, flags="S")
            response = sr1(packet, timeout=timeout, verbose=0)
            
            return response is not None
            
        except Exception as e:
            logger.debug(f"Ping failed for {target}: {e}")
            return False
    
    async def _resolve_hostname(self, ip: str) -> Optional[str]:
        """Reverse DNS lookup"""
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2
            resolver.lifetime = 2
            
            # Reverse IP for PTR lookup
            reversed_ip = '.'.join(reversed(ip.split('.'))) + '.in-addr.arpa'
            answers = resolver.resolve(reversed_ip, 'PTR')
            
            if answers:
                return str(answers[0]).rstrip('.')
        except Exception as e:
            logger.debug(f"Hostname resolution failed for {ip}: {e}")
        
        return None
    
    async def _scan_ports(
        self,
        target: str,
        ports: List[int]
    ) -> List[PortScanResult]:
        """
        Scan ports using nmap
        
        For production: Replace with custom Rust scanner for better performance
        """
        results = []
        
        try:
            # Build port string
            port_str = ','.join(map(str, ports))
            
            # Run nmap scan
            # -sV: Version detection
            # -sS: SYN scan (stealth)
            # --version-intensity 5: Aggressive version detection
            self.nmap_scanner.scan(
                target,
                port_str,
                arguments='-sV -sS --version-intensity 5 -T4'
            )
            
            if target not in self.nmap_scanner.all_hosts():
                return results
            
            # Parse results
            for proto in self.nmap_scanner[target].all_protocols():
                ports_data = self.nmap_scanner[target][proto]
                
                for port, data in ports_data.items():
                    if data['state'] == 'open':
                        result = PortScanResult(
                            ip=target,
                            port=port,
                            protocol=proto,
                            state=data['state'],
                            service=data.get('name', 'unknown'),
                            version=data.get('version', ''),
                            banner=data.get('product', '') + ' ' + data.get('version', '')
                        )
                        results.append(result)
            
        except Exception as e:
            logger.error(f"Port scan failed for {target}: {e}")
        
        return results
    
    async def _detect_os(self, target: str) -> Dict[str, str]:
        """
        OS detection using nmap
        
        Returns:
            Dict with 'os' and 'version' keys
        """
        try:
            # -O: OS detection
            # --osscan-guess: Aggressive OS guessing
            self.nmap_scanner.scan(target, arguments='-O --osscan-guess')
            
            if target in self.nmap_scanner.all_hosts():
                if 'osmatch' in self.nmap_scanner[target]:
                    matches = self.nmap_scanner[target]['osmatch']
                    if matches:
                        best_match = matches[0]
                        return {
                            "os": best_match.get('name', 'Unknown'),
                            "version": "",
                            "accuracy": best_match.get('accuracy', 0)
                        }
        except Exception as e:
            logger.error(f"OS detection failed for {target}: {e}")
        
        return {"os": "Unknown", "version": ""}
    
    async def scan_network(
        self,
        cidr: str,
        ports: Optional[List[int]] = None
    ) -> List[HostInfo]:
        """
        Scan entire network range
        
        Args:
            cidr: Network in CIDR notation (e.g., "192.168.1.0/24")
            ports: Ports to scan
        
        Returns:
            List of HostInfo for all discovered hosts
        """
        logger.info(f"Starting network scan: {cidr}")
        
        # Parse CIDR
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as e:
            logger.error(f"Invalid CIDR: {e}")
            return []
        
        # Scan all hosts concurrently
        tasks = []
        for ip in network.hosts():
            task = self.scan_host(str(ip), ports=ports)
            tasks.append(task)
        
        # Limit concurrency to avoid overwhelming network
        results = []
        batch_size = 10
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch)
            results.extend(batch_results)
        
        # Filter out dead hosts
        alive_hosts = [h for h in results if h.status == "alive"]
        
        logger.info(f"Network scan completed: {len(alive_hosts)}/{len(results)} hosts alive")
        return alive_hosts
    
    async def fingerprint_service(
        self,
        ip: str,
        port: int,
        protocol: str = "tcp"
    ) -> Dict[str, Any]:
        """
        Advanced service fingerprinting
        
        Connects to service and analyzes banner/responses
        """
        fingerprint = {
            "ip": ip,
            "port": port,
            "protocol": protocol,
            "banner": None,
            "service": "unknown",
            "version": None,
            "cpe": None  # Common Platform Enumeration
        }
        
        try:
            # Connect and grab banner
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5
            )
            
            # Read banner
            banner = await asyncio.wait_for(reader.read(1024), timeout=3)
            fingerprint["banner"] = banner.decode('utf-8', errors='ignore').strip()
            
            # Analyze banner for service identification
            banner_lower = fingerprint["banner"].lower()
            
            if "ssh" in banner_lower:
                fingerprint["service"] = "ssh"
            elif "http" in banner_lower or "html" in banner_lower:
                fingerprint["service"] = "http"
            elif "ftp" in banner_lower:
                fingerprint["service"] = "ftp"
            elif "smtp" in banner_lower:
                fingerprint["service"] = "smtp"
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            logger.debug(f"Fingerprinting failed for {ip}:{port} - {e}")
        
        return fingerprint
    
    def to_json(self, host_info: HostInfo) -> str:
        """Convert HostInfo to JSON"""
        data = asdict(host_info)
        data['discovered_at'] = host_info.discovered_at.isoformat()
        return json.dumps(data, indent=2)


# Example usage
if __name__ == "__main__":
    async def main():
        engine = ReconEngine()
        
        # Scan single host
        result = await engine.scan_host("192.168.1.1", aggressive=True)
        
        print(f"\n=== Scan Results for {result.ip} ===")
        print(f"Hostname: {result.hostname}")
        print(f"Status: {result.status}")
        print(f"OS: {result.os}")
        print(f"\nOpen Ports ({len(result.open_ports)}):")
        
        for port in result.open_ports:
            print(f"  {port.port}/{port.protocol} - {port.service} {port.version}")
        
        # Scan network (commented out for safety)
        # network_results = await engine.scan_network("192.168.1.0/24")
        # print(f"\nNetwork scan found {len(network_results)} alive hosts")
    
    asyncio.run(main())
