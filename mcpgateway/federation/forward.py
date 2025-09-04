# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/federation/forward.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

페데레이션 요청 포워딩.

연합된 MCP 게이트웨이들을 위한 요청 포워딩을 구현합니다.
다음을 처리합니다:
- 적절한 게이트웨이로의 요청 라우팅
- 응답 집계
- 에러 처리 및 재시도 로직
- 요청/응답 변환

ForwardingService 클래스는 도구 호출 및 리소스 읽기를 포함한
연합 게이트웨이들 간 요청 포워딩을 위한 주요 인터페이스를 제공합니다.

사용 예시:
    >>> from mcpgateway.federation.forward import ForwardingService
    >>> service = ForwardingService()
    >>> # 게이트웨이로 요청 포워딩
    >>> # service.forward_request(db, "tools/list")
"""

# Standard
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Third-Party
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

# First-Party
from mcpgateway.config import settings
from mcpgateway.db import Gateway as DbGateway
from mcpgateway.db import Tool as DbTool
from mcpgateway.models import ToolResult
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.utils.passthrough_headers import get_passthrough_headers

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class ForwardingError(Exception):
    """포워딩 관련 에러들의 기본 클래스.

    요청 포워딩 작업이 실패할 때 발생하는 예외로,
    네트워크 에러, 게이트웨이 사용 불가, 잘못된 응답 등을 포함합니다.

    사용 예시:
        >>> raise ForwardingError("게이트웨이 타임아웃")
        Traceback (most recent call last):
            ...
        mcpgateway.federation.forward.ForwardingError: 게이트웨이 타임아웃

        >>> try:
        ...     raise ForwardingError("잘못된 응답 형식")
        ... except ForwardingError as e:
        ...     print(f"캐치됨: {e}")
        캐치됨: 잘못된 응답 형식
    """


class ForwardingService:
    """게이트웨이들 간 요청 포워딩을 처리하는 서비스.

    다음을 처리합니다:
    - 요청 라우팅
    - 응답 집계
    - 에러 처리
    - 요청 변환
    """

    def __init__(self):
        """포워딩 서비스 초기화.

        구성된 타임아웃과 SSL 검증 설정으로 HTTP 클라이언트를 설정하고,
        활성 요청, 요청 히스토리, 게이트웨이 도구 캐시를 위한 추적 구조를 초기화합니다.

        사용 예시:
            >>> service = ForwardingService()
            >>> isinstance(service._http_client, httpx.AsyncClient)
            True
            >>> service._active_requests
            {}
            >>> service._request_history
            {}
            >>> service._gateway_tools
            {}
        """
        # 설정된 타임아웃과 SSL 검증으로 HTTP 클라이언트 초기화
        self._http_client = httpx.AsyncClient(timeout=settings.federation_timeout, verify=not settings.skip_ssl_verify)

        # 활성 요청들을 추적
        self._active_requests: Dict[str, asyncio.Task] = {}

        # 속도 제한을 위한 요청 히스토리
        self._request_history: Dict[str, List[datetime]] = {}

        # 게이트웨이 정보 캐시
        self._gateway_tools: Dict[int, Set[str]] = {}

    async def start(self) -> None:
        """포워딩 서비스 시작."""
        logger.info("요청 포워딩 서비스 시작됨")

    async def stop(self) -> None:
        """포워딩 서비스 중지."""
        # 활성 요청들 취소
        for request_id, task in self._active_requests.items():
            logger.info(f"요청 취소: {request_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await self._http_client.aclose()
        logger.info("요청 포워딩 서비스 중지됨")

    async def forward_request(
        self,
        db: Session,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        target_gateway_id: Optional[int] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """게이트웨이(들)로 요청을 포워딩.

        target_gateway_id 매개변수를 기반으로 특정 게이트웨이로 라우팅하거나
        모든 활성 게이트웨이로 브로드캐스트합니다. 대상 지정 및 브로드캐스트
        포워딩 시나리오를 모두 적절한 에러 처리와 함께 처리합니다.

        Args:
            db: 게이트웨이 조회를 위한 데이터베이스 세션
            method: RPC 메소드 이름 (예: "tools/list", "resources/read")
            params: 선택적 메소드 매개변수들 (키-값 쌍)
            target_gateway_id: 대상 지정 포워딩을 위한 특정 게이트웨이 ID
            request_headers (Optional[Dict[str, str]], optional): 전달할 요청 헤더들.
                기본값: None.

        Returns:
            Any: 대상 지정 요청 시 단일 게이트웨이 응답 (target_gateway_id 제공 시),
                또는 브로드캐스트 요청 시 모든 활성 게이트웨이의 응답 목록
                (target_gateway_id가 None일 때).

        Raises:
            ForwardingError: 네트워크 문제, 잘못된 게이트웨이, 모든 게이트웨이 실패 등으로
                포워딩이 실패한 경우

        사용 예시:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock
            >>>
            >>> # 대상 지정 포워딩 테스트
            >>> service = ForwardingService()
            >>> service._forward_to_gateway = AsyncMock(return_value={"status": "ok"})
            >>> db = Mock()
            >>> result = asyncio.run(service.forward_request(db, "test/method", {"param": "value"}, 123))
            >>> result
            {'status': 'ok'}

            >>> # 브로드캐스트 포워딩 테스트
            >>> service._forward_to_all = AsyncMock(return_value=[{"gateway1": "ok"}, {"gateway2": "ok"}])
            >>> results = asyncio.run(service.forward_request(db, "tools/list"))
            >>> len(results)
            2

            >>> # 에러 처리 테스트
            >>> service._forward_to_gateway = AsyncMock(side_effect=Exception("Network error"))
            >>> try:
            ...     asyncio.run(service.forward_request(db, "test", target_gateway_id=1))
            ... except ForwardingError as e:
            ...     print("에러:", str(e))
            에러: Forward request failed: Network error
        """
        try:
            if target_gateway_id:
                # 특정 게이트웨이로 포워딩
                return await self._forward_to_gateway(db, target_gateway_id, method, params, request_headers)

            # 모든 관련 게이트웨이로 포워딩 - 헤더들이 각 게이트웨이로 전달됨
            return await self._forward_to_all(db, method, params, request_headers)

        except Exception as e:
            raise ForwardingError(f"포워딩 요청 실패: {str(e)}")

    async def forward_tool_request(self, db: Session, tool_name: str, arguments: Dict[str, Any], request_headers: Optional[Dict[str, str]] = None) -> ToolResult:
        """Forward a tool invocation request.

        Locates the specified tool in the database, verifies it's federated,
        and forwards the invocation request to the appropriate gateway.
        Handles tool validation and response parsing.

        Args:
            db: Database session for tool and gateway lookups
            tool_name: Name of the tool to invoke
            arguments: Tool arguments as key-value pairs
            request_headers (Optional[Dict[str, str]], optional): Headers from the request to pass through.
                Defaults to None.

        Returns:
            ToolResult object containing the tool execution results

        Raises:
            ForwardingError: If tool not found, not federated, or forwarding fails

        Examples:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock, MagicMock
            >>>
            >>> # Test successful tool forwarding
            >>> service = ForwardingService()
            >>> db = Mock()
            >>> tool = Mock(name="calculator", gateway_id=1, enabled=True)
            >>> db.execute.return_value.scalar_one_or_none.return_value = tool
            >>> # ToolResult expects content to be a list of content objects
            >>> service._forward_to_gateway = AsyncMock(
            ...     return_value={
            ...         "content": [{"type": "text", "text": "Result: 42"}],
            ...         "is_error": False
            ...     }
            ... )
            >>>
            >>> result = asyncio.run(service.forward_tool_request(
            ...     db, "calculator", {"operation": "add", "a": 20, "b": 22}
            ... ))
            >>> result.content[0].text
            'Result: 42'
            >>> result.is_error
            False

            >>> # Test tool not found
            >>> db.execute.return_value.scalar_one_or_none.return_value = None
            >>> try:
            ...     asyncio.run(service.forward_tool_request(db, "unknown_tool", {}))
            ... except ForwardingError as e:
            ...     print(str(e))
            Failed to forward tool request: Tool not found: unknown_tool

            >>> # Test non-federated tool
            >>> tool = Mock(name="local_tool", gateway_id=None, enabled=True)
            >>> db.execute.return_value.scalar_one_or_none.return_value = tool
            >>> try:
            ...     asyncio.run(service.forward_tool_request(db, "local_tool", {}))
            ... except ForwardingError as e:
            ...     print(str(e))
            Failed to forward tool request: Tool local_tool is not federated
        """
        try:
            # Find tool
            tool = db.execute(select(DbTool).where(DbTool.name == tool_name).where(DbTool.enabled)).scalar_one_or_none()

            if not tool:
                raise ForwardingError(f"Tool not found: {tool_name}")

            if not tool.gateway_id:
                raise ForwardingError(f"Tool {tool_name} is not federated")

            # Forward to gateway
            result = await self._forward_to_gateway(db, tool.gateway_id, "tools/invoke", {"name": tool_name, "arguments": arguments}, request_headers)

            # Parse result
            return ToolResult(
                content=result.get("content", []),
                is_error=result.get("is_error", False),
            )

        except Exception as e:
            raise ForwardingError(f"Failed to forward tool request: {str(e)}")

    async def forward_resource_request(self, db: Session, uri: str) -> Tuple[Union[str, bytes], str]:
        """Forward a resource read request.

        Locates the gateway hosting the specified resource URI and forwards
        the read request. Handles both text and binary resource responses
        with appropriate MIME type detection.

        Args:
            db: Database session for gateway lookups
            uri: Resource URI to read (e.g., "file://data.csv", "https://api/resource")

        Returns:
            Tuple of (content, mime_type) where content is str for text
            or bytes for binary data

        Raises:
            ForwardingError: If no gateway found for resource or forwarding fails

        Examples:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock
            >>>
            >>> # Test text resource
            >>> service = ForwardingService()
            >>> db = Mock()
            >>> gateway = Mock(id=1, name="gateway1")
            >>> service._find_resource_gateway = AsyncMock(return_value=gateway)
            >>> service._forward_to_gateway = AsyncMock(
            ...     return_value={"text": "Hello, World!", "mime_type": "text/plain"}
            ... )
            >>>
            >>> content, mime_type = asyncio.run(
            ...     service.forward_resource_request(db, "file://hello.txt")
            ... )
            >>> content
            'Hello, World!'
            >>> mime_type
            'text/plain'

            >>> # Test binary resource
            >>> service._forward_to_gateway = AsyncMock(
            ...     return_value={"blob": b"\\x89PNG...", "mime_type": "image/png"}
            ... )
            >>> content, mime_type = asyncio.run(
            ...     service.forward_resource_request(db, "file://image.png")
            ... )
            >>> isinstance(content, bytes)
            True
            >>> mime_type
            'image/png'

            >>> # Test resource not found
            >>> service._find_resource_gateway = AsyncMock(return_value=None)
            >>> try:
            ...     asyncio.run(service.forward_resource_request(db, "unknown://resource"))
            ... except ForwardingError as e:
            ...     print(str(e))
            Failed to forward resource request: No gateway found for resource: unknown://resource
        """
        try:
            # Find gateway for resource
            gateway = await self._find_resource_gateway(db, uri)
            if not gateway:
                raise ForwardingError(f"No gateway found for resource: {uri}")

            # Forward request
            result = await self._forward_to_gateway(db, gateway.id, "resources/read", {"uri": uri})

            # Parse result
            if "text" in result:
                return result["text"], result.get("mime_type", "text/plain")
            if "blob" in result:
                return result["blob"], result.get("mime_type", "application/octet-stream")

            raise ForwardingError("Invalid resource response format")

        except Exception as e:
            raise ForwardingError(f"Failed to forward resource request: {str(e)}")

    async def _forward_to_gateway(
        self,
        db: Session,
        gateway_id: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Forward request to a specific gateway.

        Sends JSON-RPC formatted requests to the specified gateway with
        authentication, retry logic, and rate limiting. Updates gateway
        last_seen timestamp on successful communication.

        Args:
            db: Database session for gateway record updates
            gateway_id: ID of the gateway to forward to
            method: RPC method name
            params: Optional method parameters
            request_headers (Optional[Dict[str, str]], optional): Headers from the request to pass through.
                Defaults to None.

        Returns:
            The 'result' field from the gateway's JSON-RPC response

        Raises:
            ForwardingError: If gateway not found, rate limited, or request fails
            httpx.TimeoutException: If unable to connect after all retries

        Examples:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock, MagicMock
            >>> from datetime import datetime, timezone
            >>>
            >>> # Test successful forwarding
            >>> service = ForwardingService()
            >>> db = Mock()
            >>> gateway = Mock(id="gw1", name="Gateway 1", url="http://gateway1.com", enabled=True)
            >>> db.get.return_value = gateway
            >>> service._check_rate_limit = Mock(return_value=True)
            >>> service._get_auth_headers = Mock(return_value={"Authorization": "Basic test"})
            >>>
            >>> # Mock HTTP response
            >>> response = Mock()
            >>> response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"tools": ["tool1", "tool2"]}}
            >>> response.raise_for_status = Mock()
            >>> service._http_client.post = AsyncMock(return_value=response)
            >>>
            >>> result = asyncio.run(service._forward_to_gateway(db, "gw1", "tools/list"))
            >>> result
            {'tools': ['tool1', 'tool2']}
            >>> gateway.last_seen is not None
            True

            >>> # Test gateway not found
            >>> db.get.return_value = None
            >>> try:
            ...     asyncio.run(service._forward_to_gateway(db, "invalid", "test"))
            ... except ForwardingError as e:
            ...     print(str(e))
            Gateway not found: invalid

            >>> # Test rate limiting
            >>> db.get.return_value = gateway
            >>> service._check_rate_limit = Mock(return_value=False)
            >>> try:
            ...     asyncio.run(service._forward_to_gateway(db, "gw1", "test"))
            ... except ForwardingError as e:
            ...     print(str(e))
            Rate limit exceeded
        """
        # Get gateway
        gateway = db.get(DbGateway, gateway_id)
        if not gateway or not gateway.enabled:
            raise ForwardingError(f"Gateway not found: {gateway_id}")

        # Check rate limits
        if not self._check_rate_limit(gateway.url):
            raise ForwardingError("Rate limit exceeded")

        try:
            # Build request
            request = {"jsonrpc": "2.0", "id": 1, "method": method}
            if params:
                request["params"] = params

            # Send request with retries using the persistent client directly
            for attempt in range(settings.max_tool_retries):
                try:
                    # Merge auth headers with passthrough headers
                    headers = self._get_auth_headers()
                    if request_headers:
                        headers = get_passthrough_headers(request_headers, headers, db, gateway)

                    response = await self._http_client.post(
                        f"{gateway.url}/rpc",
                        json=request,
                        headers=headers,
                    )
                    response.raise_for_status()
                    result = response.json()

                    # Update last seen
                    gateway.last_seen = datetime.now(timezone.utc)

                    # Handle response
                    if "error" in result:
                        raise ForwardingError(f"Gateway error: {result['error'].get('message')}")
                    return result.get("result")

                except httpx.TimeoutException:
                    if attempt == settings.max_tool_retries - 1:
                        raise
                    await asyncio.sleep(1 * (attempt + 1))

        except Exception as e:
            raise ForwardingError(f"Failed to forward to {gateway.name}: {str(e)}")

    async def _forward_to_all(self, db: Session, method: str, params: Optional[Dict[str, Any]] = None, request_headers: Optional[Dict[str, str]] = None) -> List[Any]:
        """Forward request to all active gateways.

        Broadcasts the same request to all enabled gateways in parallel,
        collecting successful responses while tracking individual failures.
        Continues forwarding even if some gateways fail.

        Args:
            db: Database session for gateway queries
            method: RPC method name to invoke on all gateways
            params: Optional method parameters
            request_headers (Optional[Dict[str, str]], optional): Headers from the request to pass through.
                Defaults to None.

        Returns:
            List of successful responses from active gateways

        Raises:
            ForwardingError: Only if ALL gateways fail (partial success is allowed)

        Examples:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock, MagicMock
            >>>
            >>> # Test broadcasting to multiple gateways
            >>> service = ForwardingService()
            >>> db = Mock()
            >>> gw1 = Mock(id=1, name="Gateway 1", enabled=True)
            >>> gw2 = Mock(id=2, name="Gateway 2", enabled=True)
            >>> gw3 = Mock(id=3, name="Gateway 3", enabled=True)
            >>>
            >>> # Mock database query
            >>> mock_result = Mock()
            >>> mock_result.scalars.return_value.all.return_value = [gw1, gw2, gw3]
            >>> db.execute.return_value = mock_result
            >>>
            >>> # Mock forwarding with mixed results
            >>> async def mock_forward(db, gw_id, method, params=None, request_headers=None):
            ...     if gw_id == 1:
            ...         return {"gateway": "gw1", "status": "ok"}
            ...     elif gw_id == 2:
            ...         raise Exception("Gateway 2 is down")
            ...     else:
            ...         return {"gateway": "gw3", "status": "ok"}
            >>>
            >>> service._forward_to_gateway = mock_forward
            >>> results = asyncio.run(service._forward_to_all(db, "health/check"))
            >>> len(results)
            2
            >>> results[0]["gateway"]
            'gw1'
            >>> results[1]["gateway"]
            'gw3'

            >>> # Test all gateways failing
            >>> async def mock_all_fail(db, gw_id, method, params=None, request_headers=None):
            ...     raise Exception(f"Gateway {gw_id} failed")
            >>>
            >>> service._forward_to_gateway = mock_all_fail
            >>> try:
            ...     asyncio.run(service._forward_to_all(db, "test"))
            ... except ForwardingError as e:
            ...     print("All failed:", "Gateway 1 failed" in str(e))
            All failed: True
        """
        # Get active gateways
        gateways = db.execute(select(DbGateway).where(DbGateway.enabled)).scalars().all()

        # Forward to each gateway
        results = []
        errors = []

        for gateway in gateways:
            try:
                result = await self._forward_to_gateway(db, gateway.id, method, params, request_headers)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        if not results and errors:
            raise ForwardingError(f"All forwards failed: {'; '.join(errors)}")

        return results

    async def _find_resource_gateway(self, db: Session, uri: str) -> Optional[DbGateway]:
        """Find gateway hosting a resource.

        Queries all active gateways for their resource lists to locate
        which gateway hosts the specified resource URI. Uses sequential
        checking with error tolerance for unreachable gateways.

        Args:
            db: Database session for gateway queries
            uri: Resource URI to locate (e.g., "file://data.csv")

        Returns:
            Gateway record hosting the resource, or None if not found

        Examples:
            >>> import asyncio
            >>> from unittest.mock import Mock, AsyncMock, MagicMock
            >>>
            >>> # Test finding resource
            >>> service = ForwardingService()
            >>> db = Mock()
            >>> # Properly configure mock gateway objects
            >>> gw1 = Mock(id=1, enabled=True)
            >>> gw1.name = "Gateway 1"
            >>> gw2 = Mock(id=2, enabled=True)
            >>> gw2.name = "Gateway 2"
            >>>
            >>> # Mock database query
            >>> mock_result = Mock()
            >>> mock_result.scalars.return_value.all.return_value = [gw1, gw2]
            >>> db.execute.return_value = mock_result
            >>>
            >>> # Mock gateway responses
            >>> async def mock_forward(db, gw_id, method, params=None):
            ...     if gw_id == 1:
            ...         return [{"uri": "file://doc1.txt"}, {"uri": "file://doc2.txt"}]
            ...     else:
            ...         return [{"uri": "file://data.csv"}, {"uri": "file://config.json"}]
            >>>
            >>> service._forward_to_gateway = mock_forward
            >>> gateway = asyncio.run(service._find_resource_gateway(db, "file://data.csv"))
            >>> gateway.name
            'Gateway 2'

            >>> # Test resource not found
            >>> gateway = asyncio.run(service._find_resource_gateway(db, "file://missing.txt"))
            >>> gateway is None
            True

            >>> # Test with gateway errors
            >>> async def mock_with_error(db, gw_id, method, params=None):
            ...     if gw_id == 1:
            ...         raise Exception("Gateway unavailable")
            ...     else:
            ...         return [{"uri": "file://found.txt"}]
            >>>
            >>> service._forward_to_gateway = mock_with_error
            >>> gateway = asyncio.run(service._find_resource_gateway(db, "file://found.txt"))
            >>> gateway.name
            'Gateway 2'
        """
        # Get active gateways
        gateways = db.execute(select(DbGateway).where(DbGateway.enabled)).scalars().all()

        # Check each gateway
        for gateway in gateways:
            try:
                resources = await self._forward_to_gateway(db, gateway.id, "resources/list")
                for resource in resources:
                    if resource.get("uri") == uri:
                        return gateway
            except Exception as e:
                logger.error(f"Failed to check gateway {gateway.name} for resource {uri}: {str(e)}")
                continue

        return None

    def _check_rate_limit(self, gateway_url: str) -> bool:
        """Check if gateway request is within rate limits.

        Implements a sliding window rate limiter that tracks requests
        per gateway URL over the last 60 seconds. Automatically cleans
        expired entries from the request history.

        Args:
            gateway_url: Gateway URL to check rate limit for

        Returns:
            True if request is allowed, False if rate limit exceeded

        Examples:
            >>> from datetime import datetime, timezone, timedelta
            >>> from unittest.mock import patch
            >>>
            >>> # Test within rate limit
            >>> service = ForwardingService()
            >>> service._request_history = {}
            >>>
            >>> # First request always allowed
            >>> service._check_rate_limit("http://gateway1.com")
            True
            >>> len(service._request_history["http://gateway1.com"])
            1

            >>> # Multiple requests within limit
            >>> for _ in range(3):
            ...     allowed = service._check_rate_limit("http://gateway1.com")
            >>> allowed
            True
            >>> len(service._request_history["http://gateway1.com"])
            4

            >>> # Test rate limit exceeded
            >>> # Assuming settings.tool_rate_limit = 10
            >>> service._request_history["http://gateway2.com"] = [
            ...     datetime.now(timezone.utc) - timedelta(seconds=i)
            ...     for i in range(10)
            ... ]
            >>> with patch('mcpgateway.config.settings.tool_rate_limit', 10):
            ...     service._check_rate_limit("http://gateway2.com")
            False

            >>> # Test old entries cleanup (older than 60 seconds)
            >>> old_time = datetime.now(timezone.utc) - timedelta(seconds=61)
            >>> recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)
            >>> service._request_history["http://gateway3.com"] = [old_time, old_time, recent_time]
            >>> service._check_rate_limit("http://gateway3.com")
            True
            >>> # Old entries removed, only recent + new one remain
            >>> len(service._request_history["http://gateway3.com"])
            2
        """
        now = datetime.now(timezone.utc)

        # Clean old history
        self._request_history[gateway_url] = [t for t in self._request_history.get(gateway_url, []) if (now - t).total_seconds() < 60]

        # Check limit
        if len(self._request_history[gateway_url]) >= settings.tool_rate_limit:
            return False

        # Record request
        self._request_history[gateway_url].append(now)
        return True

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers for gateway authentication.

        Constructs authentication headers using configured credentials.
        Includes both Basic auth and API key headers for compatibility
        with different gateway authentication schemes.

        Returns:
            Dictionary containing Authorization and X-API-Key headers

        Examples:
            >>> from unittest.mock import patch
            >>>
            >>> service = ForwardingService()
            >>>
            >>> # Test header generation
            >>> with patch('mcpgateway.config.settings.basic_auth_user', 'testuser'):
            ...     with patch('mcpgateway.config.settings.basic_auth_password', 'testpass'):
            ...         headers = service._get_auth_headers()
            >>>
            >>> headers["Authorization"]
            'Basic testuser:testpass'
            >>> headers["X-API-Key"]
            'testuser:testpass'
            >>> len(headers)
            2

            >>> # Test with different credentials
            >>> with patch('mcpgateway.config.settings.basic_auth_user', 'admin'):
            ...     with patch('mcpgateway.config.settings.basic_auth_password', 'secret123'):
            ...         headers = service._get_auth_headers()
            >>> headers["X-API-Key"]
            'admin:secret123'
        """
        api_key = f"{settings.basic_auth_user}:{settings.basic_auth_password}"
        return {"Authorization": f"Basic {api_key}", "X-API-Key": api_key}
