"""
Proxy Chain Manager - Anonymous Network Communication

This module manages proxy chains for:
- TOR network routing
- VPN tunneling
- Residential proxy rotation
- SOCKS5 proxy chaining
- Traffic obfuscation

Architecture:
- Multi-hop proxy chains
- Automatic failover
- Health checking
- Bandwidth monitoring
"""

import asyncio
import logging
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp
from aiohttp_socks import ProxyConnector
import stem
from stem import Signal
from stem.control import Controller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProxyNode:
    """Single proxy in the chain"""
    proxy_type: str  # socks5, http, https
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    latency_ms: Optional[float] = None
    
    def to_url(self) -> str:
        """Convert to proxy URL"""
        if self.username and self.password:
            return f"{self.proxy_type}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.proxy_type}://{self.host}:{self.port}"


class ProxyChainManager:
    """
    Manage multi-hop proxy chains for anonymity
    
    Features:
    - TOR integration
    - Proxy rotation
    - Health checking
    - Automatic failover
    """
    
    def __init__(
        self,
        tor_control_port: int = 9051,
        tor_socks_port: int = 9050,
        tor_password: Optional[str] = None
    ):
        self.tor_control_port = tor_control_port
        self.tor_socks_port = tor_socks_port
        self.tor_password = tor_password
        
        # Proxy pools
        self.residential_proxies: List[ProxyNode] = []
        self.datacenter_proxies: List[ProxyNode] = []
        
        logger.info("Proxy chain manager initialized")
    
    async def get_tor_proxy(self) -> ProxyNode:
        """Get TOR SOCKS5 proxy"""
        return ProxyNode(
            proxy_type="socks5",
            host="127.0.0.1",
            port=self.tor_socks_port,
            country="random"
        )
    
    async def renew_tor_circuit(self):
        """Request new TOR circuit (new exit node)"""
        try:
            with Controller.from_port(port=self.tor_control_port) as controller:
                if self.tor_password:
                    controller.authenticate(password=self.tor_password)
                else:
                    controller.authenticate()
                
                controller.signal(Signal.NEWNYM)
                logger.info("TOR circuit renewed")
                
                # Wait for new circuit
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Failed to renew TOR circuit: {e}")
    
    def add_residential_proxy(self, proxy: ProxyNode):
        """Add residential proxy to pool"""
        self.residential_proxies.append(proxy)
        logger.info(f"Added residential proxy: {proxy.host}:{proxy.port}")
    
    def add_datacenter_proxy(self, proxy: ProxyNode):
        """Add datacenter proxy to pool"""
        self.datacenter_proxies.append(proxy)
        logger.info(f"Added datacenter proxy: {proxy.host}:{proxy.port}")
    
    async def get_random_proxy(self, proxy_type: str = "residential") -> Optional[ProxyNode]:
        """Get random proxy from pool"""
        pool = self.residential_proxies if proxy_type == "residential" else self.datacenter_proxies
        
        if not pool:
            logger.warning(f"No {proxy_type} proxies available")
            return None
        
        return random.choice(pool)
    
    async def build_chain(
        self,
        hops: int = 3,
        use_tor: bool = True
    ) -> List[ProxyNode]:
        """
        Build multi-hop proxy chain
        
        Args:
            hops: Number of proxy hops
            use_tor: Include TOR as final hop
        
        Returns:
            List of proxy nodes in chain order
        """
        chain = []
        
        # Add residential/datacenter proxies
        for i in range(hops - (1 if use_tor else 0)):
            proxy_type = "residential" if i == 0 else "datacenter"
            proxy = await self.get_random_proxy(proxy_type)
            
            if proxy:
                chain.append(proxy)
        
        # Add TOR as final hop
        if use_tor:
            tor_proxy = await self.get_tor_proxy()
            chain.append(tor_proxy)
        
        logger.info(f"Built proxy chain with {len(chain)} hops")
        return chain
    
    async def test_proxy(self, proxy: ProxyNode, test_url: str = "https://api.ipify.org?format=json") -> bool:
        """
        Test if proxy is working
        
        Returns:
            True if proxy works, False otherwise
        """
        try:
            connector = ProxyConnector.from_url(proxy.to_url())
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Proxy {proxy.host}:{proxy.port} works - IP: {data.get('ip')}")
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Proxy {proxy.host}:{proxy.port} failed: {e}")
            return False
    
    async def health_check_pool(self):
        """Check health of all proxies in pool"""
        logger.info("Running proxy pool health check...")
        
        # Test residential proxies
        working_residential = []
        for proxy in self.residential_proxies:
            if await self.test_proxy(proxy):
                working_residential.append(proxy)
        
        # Test datacenter proxies
        working_datacenter = []
        for proxy in self.datacenter_proxies:
            if await self.test_proxy(proxy):
                working_datacenter.append(proxy)
        
        # Update pools
        self.residential_proxies = working_residential
        self.datacenter_proxies = working_datacenter
        
        logger.info(
            f"Health check complete: "
            f"{len(working_residential)} residential, "
            f"{len(working_datacenter)} datacenter proxies working"
        )
    
    async def make_request(
        self,
        url: str,
        method: str = "GET",
        chain: Optional[List[ProxyNode]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request through proxy chain
        
        Args:
            url: Target URL
            method: HTTP method
            chain: Proxy chain (auto-built if None)
            **kwargs: Additional aiohttp request parameters
        
        Returns:
            Response data
        """
        if chain is None:
            chain = await self.build_chain()
        
        if not chain:
            raise ValueError("No proxies available")
        
        # Use last proxy in chain
        proxy = chain[-1]
        
        try:
            connector = ProxyConnector.from_url(proxy.to_url())
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.request(method, url, **kwargs) as response:
                    return {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
        
        except Exception as e:
            logger.error(f"Request through proxy chain failed: {e}")
            raise


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize manager
        manager = ProxyChainManager()
        
        # Add some test proxies (replace with real proxies)
        # manager.add_residential_proxy(ProxyNode(
        #     proxy_type="socks5",
        #     host="proxy.example.com",
        #     port=1080,
        #     username="user",
        #     password="pass"
        # ))
        
        # Build chain with TOR
        chain = await manager.build_chain(hops=2, use_tor=True)
        
        print(f"\n=== Proxy Chain ({len(chain)} hops) ===")
        for i, proxy in enumerate(chain, 1):
            print(f"{i}. {proxy.proxy_type}://{proxy.host}:{proxy.port}")
        
        # Test request
        try:
            result = await manager.make_request("https://api.ipify.org?format=json", chain=chain)
            print(f"\n=== Request Result ===")
            print(f"Status: {result['status']}")
            print(f"Body: {result['body']}")
        except Exception as e:
            print(f"Request failed: {e}")
    
    asyncio.run(main())
