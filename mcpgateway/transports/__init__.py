# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/transports/__init__.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP 전송 패키지.
MCP 프로토콜을 위한 전송 구현체를 제공합니다:
- stdio: 표준 입출력을 통한 통신
- SSE: 서버에서 클라이언트로의 스트리밍을 위한 Server-Sent Events
- WebSocket: 전이중 통신

사용 예시:
    >>> # 사용 가능한 모든 전송 클래스를 임포트
    >>> from mcpgateway.transports import Transport, StdioTransport, SSETransport, WebSocketTransport
    >>>
    >>> # 모든 클래스가 올바르게 임포트되었는지 확인
    >>> Transport.__name__
    'Transport'
    >>> StdioTransport.__name__
    'StdioTransport'
    >>> SSETransport.__name__
    'SSETransport'
    >>> WebSocketTransport.__name__
    'WebSocketTransport'

    >>> # 모든 전송이 기본 Transport를 상속받는지 확인
    >>> from mcpgateway.transports.base import Transport
    >>> issubclass(StdioTransport, Transport)
    True
    >>> issubclass(SSETransport, Transport)
    True
    >>> issubclass(WebSocketTransport, Transport)
    True

    >>> # __all__이 예상된 모든 클래스를 내보내는지 확인
    >>> from mcpgateway.transports import __all__
    >>> sorted(__all__)
    ['SSETransport', 'StdioTransport', 'Transport', 'WebSocketTransport']

    >>> # 전송 클래스를 인스턴스화할 수 있는지 테스트
    >>> stdio = StdioTransport()
    >>> isinstance(stdio, Transport)
    True
    >>> sse = SSETransport("http://localhost:8000")
    >>> isinstance(sse, Transport)
    True
    >>> ws = WebSocketTransport("ws://localhost:8000")
    >>> isinstance(ws, Transport)
    True
"""

from mcpgateway.transports.base import Transport
from mcpgateway.transports.sse_transport import SSETransport
from mcpgateway.transports.stdio_transport import StdioTransport
from mcpgateway.transports.websocket_transport import WebSocketTransport

__all__ = ["Transport", "StdioTransport", "SSETransport", "WebSocketTransport"]
