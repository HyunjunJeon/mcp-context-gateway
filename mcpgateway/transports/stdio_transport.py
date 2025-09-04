# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/transports/stdio_transport.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

stdio 전송 구현체.
MCP Gateway를 위한 표준 입출력(stdio) 전송을 구현하며,
stdin/stdout 스트림을 통한 통신을 가능하게 합니다. 이 전송은
명령줄 도구, 서브프로세스 통신, 프로세스가 표준 I/O 채널을 통해
통신해야 하는 시나리오에서 특히 유용합니다.

StdioTransport 클래스는 적절한 JSON 인코딩/디코딩과 스트림 관리를 통해
비동기 메시지 처리를 제공합니다. MCP 클라이언트와 서버 간의 양방향 통신을 위한
MCP 전송 프로토콜을 따릅니다.

주요 기능:
- asyncio를 통한 비동기 스트림 처리
- JSON 메시지 인코딩/디코딩
- 라인 기반 메시지 프로토콜
- 적절한 연결 상태 관리
- 오류 처리 및 로깅
- 깔끔한 리소스 정리

참고:
    이 전송은 sys.stdin과 sys.stdout에 대한 접근이 필요합니다.
    테스트 환경이나 이러한 스트림을 사용할 수 없는 경우,
    연결 시도 중에 RuntimeError가 발생합니다.
"""

# Standard
import asyncio
import json
import sys
from typing import Any, AsyncGenerator, Dict, Optional

# First-Party
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.transports.base import Transport

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class StdioTransport(Transport):
    """stdio 스트림을 사용하는 전송 구현체.

    이 전송 구현체는 통신을 위해 표준 입출력 스트림을 사용합니다.
    stdin/stdout을 통해 통신하는 명령줄 도구와 프로세스에서
    일반적으로 사용됩니다.

    예시:
        >>> # 새로운 stdio 전송 인스턴스 생성
        >>> transport = StdioTransport()
        >>> transport
        <mcpgateway.transports.stdio_transport.StdioTransport object at ...>

        >>> # 초기 연결 상태 확인
        >>> import asyncio
        >>> asyncio.run(transport.is_connected())
        False

        >>> # 올바른 Transport 서브클래스인지 확인
        >>> isinstance(transport, Transport)
        True
        >>> issubclass(StdioTransport, Transport)
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

    def __init__(self):
        """stdio 전송을 초기화합니다.

        예시:
            >>> # 전송 인스턴스 생성
            >>> transport = StdioTransport()
            >>> transport._stdin_reader is None
            True
            >>> transport._stdout_writer is None
            True
            >>> transport._connected
            False
        """
        # stdin 리더 초기화 (연결 시 설정됨)
        self._stdin_reader: Optional[asyncio.StreamReader] = None
        # stdout 라이터 초기화 (연결 시 설정됨)
        self._stdout_writer: Optional[asyncio.StreamWriter] = None
        # 연결 상태 초기화
        self._connected = False

    async def connect(self) -> None:
        """stdio 스트림을 설정합니다.

        예시:
            >>> # 참고: 이 메소드는 실제 stdio 스트림이 필요하며
            >>> # doctest 환경에서 쉽게 테스트할 수 없음
            >>> transport = StdioTransport()
            >>> # connect 메소드가 존재하고 호출 가능함
            >>> callable(transport.connect)
            True
        """
        # 현재 실행 중인 이벤트 루프 가져오기
        loop = asyncio.get_running_loop()

        # stdin 리더 설정
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        self._stdin_reader = reader

        # stdout 라이터 설정
        transport, protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
        self._stdout_writer = asyncio.StreamWriter(transport, protocol, reader, loop)

        # 연결 상태를 True로 설정
        self._connected = True
        logger.info("stdio 전송 연결됨")

    async def disconnect(self) -> None:
        """stdio 스트림을 정리합니다.

        예시:
            >>> # 참고: 이 메소드는 실제 stdio 스트림이 필요하며
            >>> # doctest 환경에서 쉽게 테스트할 수 없음
            >>> transport = StdioTransport()
            >>> # disconnect 메소드가 존재하고 호출 가능함
            >>> callable(transport.disconnect)
            True
        """
        # stdout 라이터가 존재하면 정리
        if self._stdout_writer:
            self._stdout_writer.close()
            await self._stdout_writer.wait_closed()
        # 연결 상태 해제
        self._connected = False
        logger.info("stdio 전송 연결 해제됨")

    async def send_message(self, message: Dict[str, Any]) -> None:
        """stdout을 통해 메시지를 보냅니다.

        Args:
            message: 보낼 메시지

        Raises:
            RuntimeError: 전송이 연결되지 않은 경우
            Exception: stdio 라이터에 쓸 수 없는 경우

        예시:
            >>> # Test with unconnected transport
            >>> transport = StdioTransport()
            >>> import asyncio
            >>> try:
            ...     asyncio.run(transport.send_message({"test": "message"}))
            ... except RuntimeError as e:
            ...     print("Expected error:", str(e))
            Expected error: Transport not connected

            >>> # Verify message format validation
            >>> transport = StdioTransport()
            >>> # Valid message format
            >>> valid_message = {"jsonrpc": "2.0", "method": "test", "id": 1}
            >>> isinstance(valid_message, dict)
            True
            >>> "jsonrpc" in valid_message
            True
        """
        # stdout 라이터가 없는지 확인 (연결되지 않은 상태)
        if not self._stdout_writer:
            raise RuntimeError("전송이 연결되지 않음")

        try:
            # 메시지를 JSON으로 직렬화
            data = json.dumps(message)
            # 개행문자를 추가하여 라인 기반 프로토콜 준수
            self._stdout_writer.write(f"{data}\n".encode())
            # 버퍼를 플러시하여 메시지가 즉시 전송되도록 함
            await self._stdout_writer.drain()
        except Exception as e:
            logger.error(f"메시지 전송 실패: {e}")
            raise

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """stdin에서 메시지를 수신합니다.

        Yields:
            수신된 메시지들

        Raises:
            RuntimeError: 전송이 연결되지 않은 경우

        예시:
            >>> # Test with unconnected transport
            >>> transport = StdioTransport()
            >>> import asyncio
            >>> try:
            ...     async def test_receive():
            ...         async for msg in transport.receive_message():
            ...             pass
            ...     asyncio.run(test_receive())
            ... except RuntimeError as e:
            ...     print("Expected error:", str(e))
            Expected error: Transport not connected

            >>> # Verify generator behavior
            >>> transport = StdioTransport()
            >>> # The method returns an async generator
            >>> import inspect
            >>> inspect.isasyncgenfunction(transport.receive_message)
            True
        """
        # stdin 리더가 없는지 확인 (연결되지 않은 상태)
        if not self._stdin_reader:
            raise RuntimeError("전송이 연결되지 않음")

        # 지속적으로 메시지를 읽어들이는 루프
        while True:
            try:
                # stdin에서 한 라인을 읽음
                line = await self._stdin_reader.readline()
                # 빈 라인인 경우 (EOF) 루프 종료
                if not line:
                    break

                # JSON 메시지 파싱
                message = json.loads(line.decode().strip())
                yield message

            except asyncio.CancelledError:
                # 비동기 작업 취소 시 루프 종료
                break
            except Exception as e:
                logger.error(f"메시지 수신 실패: {e}")
                # 오류가 발생해도 계속 다음 메시지 처리
                continue

    async def is_connected(self) -> bool:
        """전송이 연결되어 있는지 확인합니다.

        Returns:
            연결되어 있다면 True

        예시:
            >>> # Test initial state
            >>> transport = StdioTransport()
            >>> import asyncio
            >>> asyncio.run(transport.is_connected())
            False

            >>> # Test after manual connection state change
            >>> transport = StdioTransport()
            >>> transport._connected = True
            >>> asyncio.run(transport.is_connected())
            True

            >>> # Test after manual disconnection
            >>> transport = StdioTransport()
            >>> transport._connected = True
            >>> transport._connected = False
            >>> asyncio.run(transport.is_connected())
            False
        """
        return self._connected
