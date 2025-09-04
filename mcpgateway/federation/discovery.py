# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/federation/discovery.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

페데레이션 검색 서비스.
MCP 게이트웨이를 위한 자동 피어 검색을 구현합니다.
다양한 검색 메커니즘을 지원합니다:
- DNS-SD 서비스 검색
- 정적 피어 목록
- 피어 교환 프로토콜
- 수동 등록

검색 서비스는 네트워크에서 다른 MCP 게이트웨이를 자동으로 찾아 연결하고,
활성 피어 목록을 유지하며, 게이트웨이 연합을 구축하기 위해 피어 정보를 교환합니다.

# Run doctests with coverage and show missing lines
pytest --doctest-modules --cov=mcpgateway.federation.discovery --cov-report=term-missing mcpgateway/federation/discovery.py -v

# For more detailed line-by-line coverage annotation
pytest --doctest-modules --cov=mcpgateway.federation.discovery --cov-report=annotate mcpgateway/federation/discovery.py -v


사용 예시:
    검색 서비스의 기본 사용법::

        >>> import asyncio
        >>> from mcpgateway.federation.discovery import DiscoveryService
        >>>
        >>> async def main():
        ...     discovery = DiscoveryService()
        ...     await discovery.start()
        ...
        ...     # 수동으로 피어 추가
        ...     await discovery.add_peer("http://gateway.example.com:8080", "manual")
        ...
        ...     # 검색된 피어 조회
        ...     peers = discovery.get_discovered_peers()
        ...     for peer in peers:
        ...         print(f"피어 발견: {peer.url} ({peer.source}을 통해)")
        ...
        ...     await discovery.stop()
        >>>
        >>> # asyncio.run(main())

    피어 검색 테스트::

        >>> from datetime import datetime, timezone
        >>> peer = DiscoveredPeer(
        ...     url="http://localhost:8080",
        ...     name="test-gateway",
        ...     protocol_version="2025-03-26",
        ...     capabilities=None,
        ...     discovered_at=datetime.now(timezone.utc),
        ...     last_seen=datetime.now(timezone.utc),
        ...     source="manual"
        ... )
        >>> print(peer.url)
        http://localhost:8080
"""

# Standard
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import ipaddress
import os
import socket
from typing import Dict, List, Optional
from urllib.parse import urlparse

# Third-Party
import httpx
from zeroconf import ServiceInfo, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

# First-Party
from mcpgateway import __version__
from mcpgateway.config import settings
from mcpgateway.models import ServerCapabilities
from mcpgateway.services.logging_service import LoggingService

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)

PROTOCOL_VERSION = os.getenv("PROTOCOL_VERSION", "2025-03-26")


@dataclass
class DiscoveredPeer:
    """발견된 피어 게이트웨이에 대한 정보.

    다양한 검색 메커니즘을 통해 발견된 피어 MCP 게이트웨이를 표현합니다.
    피어가 언제 발견되었고, 마지막으로 언제 접촉되었으며, 어떤 기능을 가지고 있는지 추적합니다.

    속성:
        url (str): 피어 게이트웨이의 기본 URL.
        name (Optional[str]): 피어 게이트웨이의 사람이 읽을 수 있는 이름.
        protocol_version (Optional[str]): 피어가 지원하는 MCP 프로토콜 버전.
        capabilities (Optional[ServerCapabilities]): 피어의 서버 기능 정보.
        discovered_at (datetime): 피어가 처음 발견된 시각.
        last_seen (datetime): 피어와 마지막으로 성공적으로 접촉한 시각.
        source (str): 피어가 어떻게 발견되었는지 (예: "dns-sd", "static", "manual").

    사용 예시:
        >>> from datetime import datetime, timezone
        >>> peer = DiscoveredPeer(
        ...     url="http://gateway1.local:8080",
        ...     name="Gateway 1",
        ...     protocol_version="2025-03-26",
        ...     capabilities=None,
        ...     discovered_at=datetime.now(timezone.utc),
        ...     last_seen=datetime.now(timezone.utc),
        ...     source="dns-sd"
        ... )
        >>> print(f"{peer.name} at {peer.url}")
        Gateway 1 at http://gateway1.local:8080
        >>> peer.protocol_version
        '2025-03-26'
        >>> peer.source
        'dns-sd'
        >>> isinstance(peer.discovered_at, datetime)
        True
        >>> isinstance(peer.last_seen, datetime)
        True
    """

    url: str
    name: Optional[str]
    protocol_version: Optional[str]
    capabilities: Optional[ServerCapabilities]
    discovered_at: datetime
    last_seen: datetime
    source: str


class LocalDiscoveryService:
    """DNS-SD를 사용한 로컬 네트워크 검색의 기본 클래스.

    DNS Service Discovery(mDNS/Bonjour)를 사용하여 로컬 게이트웨이를 네트워크에 광고하는 기능을 제공합니다.
    이를 통해 같은 네트워크의 다른 게이트웨이들이 이 게이트웨이를 자동으로 검색할 수 있습니다.

    속성:
        _service_type (str): MCP 게이트웨이들을 위한 DNS-SD 서비스 타입.
        _service_info (ServiceInfo): 광고를 위한 Zeroconf 서비스 정보.

    사용 예시:
        >>> service = LocalDiscoveryService()
        >>> service._service_type
        '_mcp._tcp.local.'
        >>> isinstance(service._service_info, ServiceInfo)
        True
        >>> service._service_info.type
        '_mcp._tcp.local.'
        >>> service._service_info.port == settings.port
        True
        >>> b'name' in service._service_info.properties
        True
        >>> b'version' in service._service_info.properties
        True
        >>> b'protocol' in service._service_info.properties
        True
    """

    def __init__(self):
        """로컬 검색 서비스 초기화.

        서비스 타입, 이름, 포트, 속성 등을 포함한 DNS-SD 광고를 위한 서비스 정보를 설정합니다.
        """
        # 로컬 검색을 위한 서비스 정보 설정
        self._service_type = "_mcp._tcp.local."
        self._service_info = ServiceInfo(
            self._service_type,
            f"{settings.app_name}.{self._service_type}",
            addresses=[socket.inet_aton(addr) for addr in self._get_local_addresses()],
            port=settings.port,
            properties={
                "name": settings.app_name,
                "version": __version__,
                "protocol": PROTOCOL_VERSION,
            },
        )

    def _get_local_addresses(self) -> List[str]:
        """로컬 네트워크 주소 목록을 가져옵니다.

        로컬 머신의 모든 비-localhost IP 주소를 검색합니다.
        다른 주소가 없거나 오류가 발생하면 localhost로 폴백합니다.

        Returns:
            List[str]: IP 주소들의 문자열 목록.

        사용 예시:
            >>> service = LocalDiscoveryService()
            >>> addrs = service._get_local_addresses()
            >>> isinstance(addrs, list)
            True
            >>> all(isinstance(addr, str) for addr in addrs)
            True
            >>> len(addrs) >= 1  # 최소 localhost
            True
            >>> # IP 형식 확인
            >>> all('.' in addr for addr in addrs)  # IPv4 형식
            True
            >>> # 빈 주소 없음 확인
            >>> all(addr for addr in addrs)
            True
            >>> '' not in addrs
            True
        """
        addresses = []
        try:
            # 모든 네트워크 인터페이스 가져오기
            for iface in socket.getaddrinfo(socket.gethostname(), None):
                addr = iface[4][0]
                ip_obj = ipaddress.ip_address(addr)
                is_ipv4 = isinstance(ip_obj, ipaddress.IPv4Address)
                # localhost와 비-IPv4 주소 건너뛰기
                if is_ipv4 and not addr.startswith("127."):
                    addresses.append(addr)
        except Exception as e:
            logger.warning(f"로컬 주소 가져오기 실패: {e}")
            # localhost로 폴백
            addresses.append("127.0.0.1")

        return addresses or ["127.0.0.1"]


class DiscoveryService(LocalDiscoveryService):
    """자동 게이트웨이 검색 서비스.

    다양한 검색 메커니즘을 지원합니다:
    - 로컬 네트워크 검색을 위한 DNS-SD
    - 구성에서의 정적 피어 목록
    - 알려진 게이트웨이들과의 피어 교환
    - API를 통한 수동 등록

    서비스는 검색된 피어 목록을 유지하고, 주기적으로 정보를 새로고침하며,
    최근에 접촉하지 않은 오래된 피어들을 제거합니다.

    속성:
        _zeroconf (Optional[AsyncZeroconf]): DNS-SD를 위한 Zeroconf 인스턴스.
        _browser (Optional[AsyncServiceBrowser]): 피어 검색을 위한 서비스 브라우저.
        _http_client (httpx.AsyncClient): 피어들과 통신하기 위한 HTTP 클라이언트.
        _discovered_peers (Dict[str, DiscoveredPeer]): URL에서 피어 정보로의 매핑.
        _cleanup_task (Optional[asyncio.Task]): 오래된 피어들을 정리하는 백그라운드 태스크.
        _refresh_task (Optional[asyncio.Task]): 피어 정보를 새로고침하는 백그라운드 태스크.

    사용 예시:
        >>> import asyncio
        >>> async def test_discovery():
        ...     service = DiscoveryService()
        ...     await service.start()
        ...
        ...     # 수동으로 피어 추가
        ...     added = await service.add_peer("http://peer1.local:8080", "manual")
        ...
        ...     # 모든 검색된 피어 조회
        ...     peers = service.get_discovered_peers()
        ...
        ...     await service.stop()
        ...     return len(peers)
        >>>
        >>> # result = asyncio.run(test_discovery())
    """

    def __init__(self):
        """검색 서비스 초기화.

        HTTP 클라이언트, 피어 추적 딕셔너리를 설정하고 백그라운드 태스크를 준비합니다.
        네트워크 작업은 시작하지 않습니다.
        """
        super().__init__()

        self._zeroconf: Optional[AsyncZeroconf] = None
        self._browser: Optional[AsyncServiceBrowser] = None
        # 설정된 타임아웃과 SSL 검증 설정으로 HTTP 클라이언트 초기화
        self._http_client = httpx.AsyncClient(timeout=settings.federation_timeout, verify=not settings.skip_ssl_verify)

        # 검색된 피어들을 추적
        self._discovered_peers: Dict[str, DiscoveredPeer] = {}

        # 백그라운드 태스크 시작
        self._cleanup_task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """검색 서비스 시작.

        DNS-SD를 활성화된 경우 초기화하고, 피어 유지 관리를 위한 백그라운드 태스크를 시작하며,
        정적으로 구성된 피어들을 로드합니다.

        Raises:
            Exception: 검색 서비스를 시작할 수 없는 경우.

        사용 예시:
            >>> import asyncio
            >>> async def test_start():
            ...     service = DiscoveryService()
            ...     await service.start()
            ...     # 서비스가 이제 실행 중입니다
            ...     await service.stop()
            >>> # asyncio.run(test_start())
        """
        try:
            # DNS-SD 초기화
            if settings.federation_discovery:
                self._zeroconf = AsyncZeroconf()
                await self._zeroconf.async_register_service(self._service_info)
                # 서비스 상태 변경 핸들러와 함께 서비스 브라우저 생성
                self._browser = AsyncServiceBrowser(
                    self._zeroconf.zeroconf,
                    self._service_type,
                    handlers=[self._on_service_state_change],
                )

            # 백그라운드 태스크 시작
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._refresh_task = asyncio.create_task(self._refresh_loop())

            # 정적 피어들 로드
            for peer_url in settings.federation_peers:
                await self.add_peer(peer_url, source="static")

            logger.info("검색 서비스 시작됨")

        except Exception as e:
            logger.error(f"Failed to start discovery service: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop discovery service.

        Cancels background tasks, unregisters DNS-SD service, and closes
        all network connections. Safe to call multiple times.

        Examples:
            >>> import asyncio
            >>> async def test_stop():
            ...     service = DiscoveryService()
            ...     await service.start()
            ...     await service.stop()
            ...     # All resources cleaned up
            >>> # asyncio.run(test_stop())
        """
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        # Stop DNS-SD
        if self._browser:
            await self._browser.async_cancel()
            self._browser = None

        if self._zeroconf:
            await self._zeroconf.async_unregister_service(self._service_info)
            await self._zeroconf.async_close()
            self._zeroconf = None

        # Close HTTP client
        await self._http_client.aclose()

        logger.info("Discovery service stopped")

    async def add_peer(self, url: str, source: str, name: Optional[str] = None) -> bool:
        """Add a new peer gateway.

        Validates the URL, checks if the peer is already known, and attempts
        to retrieve the peer's capabilities. If successful, adds the peer to
        the discovered peers list.

        Args:
            url (str): Gateway URL (e.g., "http://gateway.example.com:8080").
            source (str): Discovery source (e.g., "static", "dns-sd", "manual").
            name (Optional[str]): Optional human-readable gateway name.

        Returns:
            bool: True if peer was successfully added, False otherwise.

        Examples:
            >>> import asyncio
            >>> async def test_add_peer():
            ...     service = DiscoveryService()
            ...     # Valid URL
            ...     result = await service.add_peer("http://localhost:8080", "manual")
            ...     # Invalid URL
            ...     invalid = await service.add_peer("not-a-url", "manual")
            ...     return result, invalid
            >>> # valid, invalid = asyncio.run(test_add_peer())
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid peer URL: {url}")
                return False
        except Exception:
            logger.warning(f"Failed to parse peer URL: {url}")
            return False

        # Skip if already known
        if url in self._discovered_peers:
            peer = self._discovered_peers[url]
            peer.last_seen = datetime.now(timezone.utc)
            return False

        try:
            # Try to get gateway info
            capabilities = await self._get_gateway_info(url)

            # Add to discovered peers
            self._discovered_peers[url] = DiscoveredPeer(
                url=url,
                name=name,
                protocol_version=PROTOCOL_VERSION,
                capabilities=capabilities,
                discovered_at=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                source=source,
            )

            logger.info(f"Added peer gateway: {url} (via {source})")
            return True

        except Exception as e:
            logger.warning(f"Failed to add peer {url}: {e}")
            return False

    def get_discovered_peers(self) -> List[DiscoveredPeer]:
        """Get list of discovered peers.

        Returns a snapshot of all currently known peer gateways.

        Returns:
            List[DiscoveredPeer]: List of discovered peer information.

        Examples:
            >>> service = DiscoveryService()
            >>> peers = service.get_discovered_peers()
            >>> isinstance(peers, list)
            True
            >>> # After adding peers
            >>> # len(peers) > 0
            >>> # Initially empty
            >>> len(peers)
            0
            >>> # Add a peer manually (sync example)
            >>> from datetime import datetime, timezone
            >>> service._discovered_peers["http://test.com"] = DiscoveredPeer(
            ...     url="http://test.com",
            ...     name="Test",
            ...     protocol_version="2025-03-26",
            ...     capabilities=None,
            ...     discovered_at=datetime.now(timezone.utc),
            ...     last_seen=datetime.now(timezone.utc),
            ...     source="manual"
            ... )
            >>> peers = service.get_discovered_peers()
            >>> len(peers)
            1
            >>> peers[0].url
            'http://test.com'
        """
        return list(self._discovered_peers.values())

    async def refresh_peer(self, url: str) -> bool:
        """Refresh peer gateway information.

        Attempts to update the capabilities and last seen time for a known peer.

        Args:
            url (str): Gateway URL to refresh.

        Returns:
            bool: True if refresh succeeded, False otherwise.

        Examples:
            >>> import asyncio
            >>> async def test_refresh():
            ...     service = DiscoveryService()
            ...     # Add a peer first
            ...     await service.add_peer("http://localhost:8080", "manual")
            ...     # Refresh it
            ...     refreshed = await service.refresh_peer("http://localhost:8080")
            ...     # Unknown peer
            ...     unknown = await service.refresh_peer("http://unknown:8080")
            ...     return refreshed, unknown
            >>> # refreshed, unknown = asyncio.run(test_refresh())
        """
        if url not in self._discovered_peers:
            return False

        try:
            capabilities = await self._get_gateway_info(url)
            self._discovered_peers[url].capabilities = capabilities
            self._discovered_peers[url].last_seen = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.warning(f"Failed to refresh peer {url}: {e}")
            return False

    async def remove_peer(self, url: str) -> None:
        """Remove a peer gateway.

        Removes a peer from the discovered peers list. Safe to call even
        if the peer doesn't exist.

        Args:
            url (str): Gateway URL to remove.

        Examples:
            >>> import asyncio
            >>> async def test_remove():
            ...     service = DiscoveryService()
            ...     await service.add_peer("http://localhost:8080", "manual")
            ...     await service.remove_peer("http://localhost:8080")
            ...     peers = service.get_discovered_peers()
            ...     return len(peers)
            >>> # count = asyncio.run(test_remove())

            >>> # Sync example
            >>> from datetime import datetime, timezone
            >>> service = DiscoveryService()
            >>> # Add a peer directly
            >>> service._discovered_peers["http://test.com"] = DiscoveredPeer(
            ...     url="http://test.com",
            ...     name="Test",
            ...     protocol_version="2025-03-26",
            ...     capabilities=None,
            ...     discovered_at=datetime.now(timezone.utc),
            ...     last_seen=datetime.now(timezone.utc),
            ...     source="manual"
            ... )
            >>> len(service._discovered_peers)
            1
            >>> # Remove it (sync version for testing)
            >>> service._discovered_peers.pop("http://test.com", None) is not None
            True
            >>> len(service._discovered_peers)
            0
            >>> # Safe to remove non-existent
            >>> service._discovered_peers.pop("http://nonexistent.com", None) is None
            True
        """
        self._discovered_peers.pop(url, None)

    async def _on_service_state_change(
        self,
        zeroconf: AsyncZeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Handle DNS-SD service changes.

        Called by Zeroconf when services are added or removed from the network.
        When a new MCP gateway is discovered, extracts its information and adds
        it as a peer.

        Args:
            zeroconf (AsyncZeroconf): Zeroconf instance.
            service_type (str): Service type that changed.
            name (str): Service name that changed.
            state_change (ServiceStateChange): Type of state change (Added/Removed).
        """
        if state_change is ServiceStateChange.Added:
            info = await zeroconf.async_get_service_info(service_type, name)
            if info:
                try:
                    # Extract gateway info
                    addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
                    if addresses:
                        port = info.port
                        url = f"http://{addresses[0]}:{port}"
                        name = info.properties.get(b"name", b"").decode()

                        # Add peer
                        await self.add_peer(url, source="dns-sd", name=name)

                except Exception as e:
                    logger.warning(f"Failed to process discovered service {name}: {e}")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up stale peers.

        Runs in the background and removes peers that haven't been seen
        for more than 10 minutes. Runs every 60 seconds.

        Raises:
            asyncio.CancelledError: When the task is cancelled during shutdown.
        """
        while True:
            try:
                now = datetime.now(timezone.utc)
                stale_urls = [url for url, peer in self._discovered_peers.items() if now - peer.last_seen > timedelta(minutes=10)]
                for url in stale_urls:
                    await self.remove_peer(url)
                    logger.info(f"Removed stale peer: {url}")

            except Exception as e:
                logger.error(f"Peer cleanup error: {e}")

            await asyncio.sleep(60)

    async def _refresh_loop(self) -> None:
        """Periodically refresh peer information.

        Runs in the background and refreshes all peer information and
        performs peer exchange every 5 minutes.

        Raises:
            asyncio.CancelledError: When the task is cancelled during shutdown.
        """
        while True:
            try:
                # Refresh all peers
                for url in list(self._discovered_peers.keys()):
                    await self.refresh_peer(url)

                # Exchange peers
                await self._exchange_peers()

            except Exception as e:
                logger.error(f"Peer refresh error: {e}")

            await asyncio.sleep(300)  # 5 minutes

    async def _get_gateway_info(self, url: str) -> ServerCapabilities:
        """Get gateway capabilities.

        Sends an initialize request to the peer gateway to retrieve its
        capabilities and verify protocol compatibility.

        Args:
            url (str): Gateway URL.

        Returns:
            ServerCapabilities: Gateway capabilities object.

        Raises:
            ValueError: If protocol version is unsupported.
            httpx.HTTPStatusError: If the HTTP request fails.
            httpx.RequestError: If the request cannot be sent.
        """
        # Build initialize request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocol_version": PROTOCOL_VERSION,
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "client_info": {"name": settings.app_name, "version": __version__},
            },
        }

        # Send request using the persistent HTTP client directly
        response = await self._http_client.post(f"{url}/initialize", json=request, headers=self._get_auth_headers())
        response.raise_for_status()
        result = response.json()

        # Validate response
        if result.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {result.get('protocol_version')}")

        return ServerCapabilities.model_validate(result["capabilities"])

    async def _exchange_peers(self) -> None:
        """Exchange peer lists with known gateways.

        Contacts each known peer to retrieve their list of known peers,
        potentially discovering new gateways through transitive connections.
        This enables building a mesh network of federated gateways.
        """
        for url in list(self._discovered_peers.keys()):
            try:
                # Get peer's peer list using the persistent HTTP client directly
                response = await self._http_client.get(f"{url}/peers", headers=self._get_auth_headers())
                response.raise_for_status()
                peers = response.json()

                # Add new peers from the response
                for peer in peers:
                    if isinstance(peer, dict) and "url" in peer:
                        await self.add_peer(peer["url"], source="exchange", name=peer.get("name"))

            except Exception as e:
                logger.warning(f"Failed to exchange peers with {url}: {e}")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers for gateway authentication.

        Constructs authentication headers using the configured credentials
        for communicating with peer gateways.

        Returns:
            Dict[str, str]: Dictionary containing Authorization and X-API-Key headers.

        Examples:
            >>> service = DiscoveryService()
            >>> headers = service._get_auth_headers()
            >>> "Authorization" in headers
            True
            >>> "X-API-Key" in headers
            True
            >>> headers["Authorization"].startswith("Basic ")
            True
            >>> headers["X-API-Key"] == f"{settings.basic_auth_user}:{settings.basic_auth_password}"
            True
            >>> isinstance(headers, dict)
            True
            >>> len(headers)
            2
        """
        api_key = f"{settings.basic_auth_user}:{settings.basic_auth_password}"
        return {"Authorization": f"Basic {api_key}", "X-API-Key": api_key}
