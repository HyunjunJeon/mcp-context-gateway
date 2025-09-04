# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/transports/sse_transport.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

SSE 전송 구현체.
MCP를 위한 Server-Sent Events (SSE) 전송을 구현하며,
적절한 세션 관리를 통해 서버에서 클라이언트로의 스트리밍을 제공합니다.
"""

# Standard
import asyncio
from datetime import datetime
import json
from typing import Any, AsyncGenerator, Dict
import uuid

# Third-Party
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

# First-Party
from mcpgateway.config import settings
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.transports.base import Transport

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class SSETransport(Transport):
    """적절한 세션 관리를 통해 Server-Sent Events를 사용하는 전송 구현체.

    이 전송 구현체는 MCP 게이트웨이와 클라이언트 간의 실시간 통신을 위해
    Server-Sent Events (SSE)를 사용합니다. 자동 세션 관리와 keepalive 지원으로
    스트리밍 기능을 제공합니다.

    예시:
        >>> # 기본 URL로 SSE 전송 생성
        >>> transport = SSETransport()
        >>> transport
        <mcpgateway.transports.sse_transport.SSETransport object at ...>

        >>> # 사용자 정의 URL로 SSE 전송 생성
        >>> transport = SSETransport("http://localhost:8080")
        >>> transport._base_url
        'http://localhost:8080'

        >>> # 초기 연결 상태 확인
        >>> import asyncio
        >>> asyncio.run(transport.is_connected())
        False

        >>> # 올바른 Transport 서브클래스인지 확인
        >>> isinstance(transport, Transport)
        True
        >>> issubclass(SSETransport, Transport)
        True

        >>> # 세션 ID 생성 확인
        >>> transport.session_id
        '...'
        >>> len(transport.session_id) > 0
        True

        >>> # 필요한 메소드가 존재하는지 확인
        >>> hasattr(transport, 'connect')
        True
        >>> hasattr(transport, 'disconnect')
        True
        >>> hasattr(transport, 'send_message')
        True
        >>> hasattr(transport, 'receive_message')
        True
        >>> hasattr(transport, 'is_connected')
        True
    """

    def __init__(self, base_url: str = None):
        """SSE 전송을 초기화합니다.

        Args:
            base_url: 클라이언트 메시지 엔드포인트를 위한 기본 URL

        예시:
            >>> # 기본 초기화 테스트
            >>> transport = SSETransport()
            >>> transport._connected
            False
            >>> transport._message_queue is not None
            True
            >>> transport._client_gone is not None
            True
            >>> len(transport._session_id) > 0
            True

            >>> # 사용자 정의 기본 URL 테스트
            >>> transport = SSETransport("https://api.example.com")
            >>> transport._base_url
            'https://api.example.com'

            >>> # 세션 ID 고유성 테스트
            >>> transport1 = SSETransport()
            >>> transport2 = SSETransport()
            >>> transport1.session_id != transport2.session_id
            True
        """
        # 기본 URL 설정 (제공되지 않은 경우 설정에서 가져옴)
        self._base_url = base_url or f"http://{settings.host}:{settings.port}"
        # 연결 상태 초기화
        self._connected = False
        # 메시지 큐 생성 (비동기 통신용)
        self._message_queue = asyncio.Queue()
        # 클라이언트 연결 종료 이벤트
        self._client_gone = asyncio.Event()
        # 고유 세션 ID 생성
        self._session_id = str(uuid.uuid4())

        logger.info(f"SSE 전송 생성: base_url={self._base_url}, session_id={self._session_id}")

    async def connect(self) -> None:
        """SSE 연결을 설정합니다.

        예시:
            >>> # 연결 설정 테스트
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport.connect())
            >>> transport._connected
            True
            >>> asyncio.run(transport.is_connected())
            True
        """
        # 연결 상태를 True로 설정
        self._connected = True
        logger.info(f"SSE 전송 연결됨: {self._session_id}")

    async def disconnect(self) -> None:
        """SSE 연결을 정리합니다.

        예시:
            >>> # 연결 해제 테스트
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport.connect())
            >>> asyncio.run(transport.disconnect())
            >>> transport._connected
            False
            >>> transport._client_gone.is_set()
            True
            >>> asyncio.run(transport.is_connected())
            False

            >>> # 이미 연결 해제된 상태에서 테스트
            >>> transport = SSETransport()
            >>> asyncio.run(transport.disconnect())
            >>> transport._connected
            False
        """
        # 연결된 상태인 경우에만 정리 작업 수행
        if self._connected:
            # 연결 상태 해제
            self._connected = False
            # 클라이언트 연결 종료 이벤트 설정
            self._client_gone.set()
            logger.info(f"SSE 전송 연결 해제됨: {self._session_id}")

    async def send_message(self, message: Dict[str, Any]) -> None:
        """SSE를 통해 메시지를 보냅니다.

        Args:
            message: 보낼 메시지

        Raises:
            RuntimeError: 전송이 연결되지 않은 경우
            Exception: 큐에 메시지를 넣을 수 없는 경우

        예시:
            >>> # Test sending message when connected
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport.connect())
            >>> message = {"jsonrpc": "2.0", "method": "test", "id": 1}
            >>> asyncio.run(transport.send_message(message))
            >>> transport._message_queue.qsize()
            1

            >>> # Test sending message when not connected
            >>> transport = SSETransport()
            >>> try:
            ...     asyncio.run(transport.send_message({"test": "message"}))
            ... except RuntimeError as e:
            ...     print("Expected error:", str(e))
            Expected error: Transport not connected

            >>> # Test message format validation
            >>> transport = SSETransport()
            >>> asyncio.run(transport.connect())
            >>> valid_message = {"jsonrpc": "2.0", "method": "initialize", "params": {}}
            >>> isinstance(valid_message, dict)
            True
            >>> "jsonrpc" in valid_message
            True

            >>> # Test exception handling in queue put
            >>> transport = SSETransport()
            >>> asyncio.run(transport.connect())
            >>> # Create a full queue to trigger exception
            >>> transport._message_queue = asyncio.Queue(maxsize=1)
            >>> asyncio.run(transport._message_queue.put({"dummy": "message"}))
            >>> # Now queue is full, next put should fail
            >>> try:
            ...     asyncio.run(asyncio.wait_for(transport.send_message({"test": "message"}), timeout=0.1))
            ... except asyncio.TimeoutError:
            ...     print("Queue full as expected")
            Queue full as expected
        """
        # 전송이 연결되어 있는지 확인
        if not self._connected:
            raise RuntimeError("전송이 연결되지 않음")

        try:
            # 메시지를 큐에 추가하여 SSE 스트리밍을 위해 준비
            await self._message_queue.put(message)
            logger.debug(f"SSE용 메시지 큐에 추가됨: {self._session_id}, method={message.get('method', '(response)')}")
        except Exception as e:
            logger.error(f"메시지 큐에 추가 실패: {e}")
            raise

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """SSE 전송을 통해 클라이언트로부터 메시지를 수신합니다.

        이 메소드는 SSE 전송을 위한 지속적인 메시지 수신 패턴을 구현합니다.
        SSE가 주로 서버에서 클라이언트로의 통신 채널이므로, 이 메소드는
        초기 initialize 플레이스홀더 메시지를 yield한 후 대기 루프에 진입합니다.
        실제 클라이언트 메시지는 별도의 HTTP POST 엔드포인트를 통해 수신됩니다
        (이 메소드에서는 처리하지 않음).

        다음 중 하나가 발생할 때까지 메소드가 계속 실행됩니다:
        1. 연결이 명시적으로 해제될 때 (client_gone 이벤트가 설정됨)
        2. 외부에서 수신 루프가 취소될 때

        Yields:
            Dict[str, Any]: JSON-RPC 형식의 메시지. 첫 번째로 yield되는 메시지는 항상
                다음과 같은 형식의 initialize 플레이스홀더입니다:
                {"jsonrpc": "2.0", "method": "initialize", "id": 1}

        Raises:
            RuntimeError: 이 메소드가 호출될 때 전송이 연결되지 않은 경우
            asyncio.CancelledError: SSE 수신 루프가 외부에서 취소될 때

        예시:
            >>> # Test receive message when connected
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport.connect())
            >>> async def test_receive():
            ...     async for msg in transport.receive_message():
            ...         return msg
            ...     return None
            >>> result = asyncio.run(test_receive())
            >>> result
            {'jsonrpc': '2.0', 'method': 'initialize', 'id': 1}

            >>> # Test receive message when not connected
            >>> transport = SSETransport()
            >>> try:
            ...     async def test_receive():
            ...         async for msg in transport.receive_message():
            ...             pass
            ...     asyncio.run(test_receive())
            ... except RuntimeError as e:
            ...     print("Expected error:", str(e))
            Expected error: Transport not connected

            >>> # Verify generator behavior
            >>> transport = SSETransport()
            >>> import inspect
            >>> inspect.isasyncgenfunction(transport.receive_message)
            True
        """
        # 전송이 연결되어 있는지 확인
        if not self._connected:
            raise RuntimeError("전송이 연결되지 않음")

        # SSE의 경우 POST를 통해 전달되는 메시지를 기다리는 루프를 설정
        # 대부분의 메시지는 POST 엔드포인트를 통해 오지만, 수신 루프를 유지하기 위해
        # 초기 initialize 플레이스홀더를 yield함
        yield {"jsonrpc": "2.0", "method": "initialize", "id": 1}

        # 취소될 때까지 계속 대기
        try:
            # 클라이언트 연결이 종료되지 않은 동안 계속 대기
            while not self._client_gone.is_set():
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info(f"SSE 수신 루프 취소됨: 세션 {self._session_id}")
            raise
        finally:
            logger.info(f"SSE 수신 루프 종료됨: 세션 {self._session_id}")

    async def is_connected(self) -> bool:
        """전송이 연결되어 있는지 확인합니다.

        Returns:
            연결되어 있다면 True

        예시:
            >>> # 초기 상태 테스트
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport.is_connected())
            False

            >>> # 연결 후 테스트
            >>> transport = SSETransport()
            >>> asyncio.run(transport.connect())
            >>> asyncio.run(transport.is_connected())
            True

            >>> # 연결 해제 후 테스트
            >>> transport = SSETransport()
            >>> asyncio.run(transport.connect())
            >>> asyncio.run(transport.disconnect())
            >>> asyncio.run(transport.is_connected())
            False
        """
        return self._connected

    async def create_sse_response(self, _request: Request) -> EventSourceResponse:
        """스트리밍을 위한 SSE 응답을 생성합니다.

        Args:
            _request: FastAPI 요청 객체

        Returns:
            SSE 응답 객체

        예시:
            >>> # SSE 응답 생성 테스트
            >>> transport = SSETransport("http://localhost:8000")
            >>> # 이 메소드는 FastAPI Request 객체가 필요하며
            >>> # doctest 환경에서 쉽게 테스트할 수 없음
            >>> callable(transport.create_sse_response)
            True
        """
        # 세션 ID를 포함한 메시지 엔드포인트 URL 생성
        endpoint_url = f"{self._base_url}/message?session_id={self._session_id}"

        async def event_generator():
            """SSE 이벤트를 생성합니다.

            Yields:
                SSE 이벤트
            """
            # 먼저 엔드포인트 이벤트를 전송
            yield {
                "event": "endpoint",
                "data": endpoint_url,
                "retry": settings.sse_retry_timeout,
            }

            # 연결 수립을 돕기 위해 즉시 keepalive 전송 (활성화된 경우)
            if settings.sse_keepalive_enabled:
                yield {
                    "event": "keepalive",
                    "data": "{}",
                    "retry": settings.sse_retry_timeout,
                }

            try:
                # 클라이언트 연결이 종료되지 않은 동안 계속 실행
                while not self._client_gone.is_set():
                    try:
                        # keepalive를 위한 타임아웃과 함께 메시지 대기
                        timeout = settings.sse_keepalive_interval if settings.sse_keepalive_enabled else None
                        message = await asyncio.wait_for(
                            self._message_queue.get(),
                            timeout=timeout,  # keepalive를 위한 구성 가능한 타임아웃 (일부 도구는 실행에 더 많은 타임아웃이 필요함)
                        )

                        # datetime 객체를 포함한 메시지를 JSON으로 직렬화
                        data = json.dumps(message, default=lambda obj: (obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, datetime) else TypeError("직렬화할 수 없는 타입")))

                        # logger.info(f"Sending SSE message: {data[:100]}...")
                        logger.debug(f"SSE 메시지 전송: {data}")

                        yield {
                            "event": "message",
                            "data": data,
                            "retry": settings.sse_retry_timeout,
                        }
                    except asyncio.TimeoutError:
                        # 타임아웃 시 keepalive 전송 (활성화된 경우)
                        if settings.sse_keepalive_enabled:
                            yield {
                                "event": "keepalive",
                                "data": "{}",
                                "retry": settings.sse_retry_timeout,
                            }
                    except Exception as e:
                        logger.error(f"SSE 메시지 처리 오류: {e}")
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": str(e)}),
                            "retry": settings.sse_retry_timeout,
                        }
            except asyncio.CancelledError:
                logger.info(f"SSE 이벤트 생성기 취소됨: {self._session_id}")
            except Exception as e:
                logger.error(f"SSE 이벤트 생성기 오류: {e}")
            finally:
                logger.info(f"SSE 이벤트 생성기 완료됨: {self._session_id}")
                # 큐에 있는 메시지 처리를 허용하기 위해 의도적으로 client_gone을 설정하지 않음

        # SSE 응답 생성 및 반환
        return EventSourceResponse(
            event_generator(),
            status_code=200,
            headers={
                "Cache-Control": "no-cache",      # 캐시 방지
                "Connection": "keep-alive",       # 연결 유지
                "Content-Type": "text/event-stream",  # SSE 콘텐츠 타입
                "X-MCP-SSE": "true",             # MCP SSE 식별자
            },
        )

    async def _client_disconnected(self, _request: Request) -> bool:
        """클라이언트 연결이 해제되었는지 확인합니다.

        Args:
            _request: FastAPI Request 객체

        Returns:
            bool: 클라이언트 연결이 해제되었으면 True

        예시:
            >>> # 클라이언트 연결 해제 확인 테스트
            >>> transport = SSETransport()
            >>> import asyncio
            >>> asyncio.run(transport._client_disconnected(None))
            False

            >>> # client_gone 설정 후 테스트
            >>> transport = SSETransport()
            >>> transport._client_gone.set()
            >>> asyncio.run(transport._client_disconnected(None))
            True
        """
        # 내부 client_gone 플래그만 확인
        # 요청의 connection_lost를 확인하지 않음 (신뢰할 수 없고 조기 종료를 유발할 수 있음)
        return self._client_gone.is_set()

    @property
    def session_id(self) -> str:
        """
        이 전송의 세션 ID를 가져옵니다.

        Returns:
            str: 세션 ID

        예시:
            >>> # 세션 ID 프로퍼티 테스트
            >>> transport = SSETransport()
            >>> session_id = transport.session_id
            >>> isinstance(session_id, str)
            True
            >>> len(session_id) > 0
            True
            >>> session_id == transport._session_id
            True

            >>> # 세션 ID 고유성 테스트
            >>> transport1 = SSETransport()
            >>> transport2 = SSETransport()
            >>> transport1.session_id != transport2.session_id
            True
        """
        return self._session_id
