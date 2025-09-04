# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/transports/base.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

기본 전송 인터페이스.
MCP 전송을 위한 기본 프로토콜을 정의합니다.
"""

# Standard
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict


class Transport(ABC):
    """MCP 전송 구현을 위한 기본 클래스.

    이 추상 기본 클래스는 모든 MCP 전송 구현이 따라야 하는 인터페이스를 정의합니다.
    연결 관리와 메시지 교환을 위한 핵심 메소드를 제공합니다.

    예시:
        >>> # Transport는 추상 클래스이므로 직접 인스턴스화할 수 없음
        >>> try:
        ...     Transport()
        ... except TypeError as e:
        ...     print("추상 클래스는 인스턴스화할 수 없음")
        추상 클래스는 인스턴스화할 수 없음

        >>> # Transport가 추상 기본 클래스인지 확인
        >>> from abc import ABC
        >>> issubclass(Transport, ABC)
        True

        >>> # 추상 메소드가 정의되어 있는지 확인
        >>> hasattr(Transport, 'connect')
        True
        >>> hasattr(Transport, 'disconnect')
        True
        >>> hasattr(Transport, 'send_message')
        True
        >>> hasattr(Transport, 'receive_message')
        True
        >>> hasattr(Transport, 'is_connected')
        True
    """

    @abstractmethod
    async def connect(self) -> None:
        """전송 연결을 초기화합니다.

        이 메소드는 전송을 위한 기본 연결을 설정해야 합니다.
        메시지를 보내거나 받기 전에 반드시 호출되어야 합니다.

        예시:
            >>> # 이는 추상 메소드입니다 - 서브클래스에서 구현이 필요함
            >>> import inspect
            >>> inspect.ismethod(Transport.connect)
            False
            >>> hasattr(Transport, 'connect')
            True
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """전송 연결을 종료합니다.

        이 메소드는 기본 연결과 관련된 모든 리소스를 정리해야 합니다.
        전송이 더 이상 필요하지 않을 때 호출되어야 합니다.

        예시:
            >>> # 이는 추상 메소드입니다 - 서브클래스에서 구현이 필요함
            >>> import inspect
            >>> inspect.ismethod(Transport.disconnect)
            False
            >>> hasattr(Transport, 'disconnect')
            True
        """

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        """전송을 통해 메시지를 보냅니다.

        Args:
            message: 보낼 메시지

        예시:
            >>> # 이는 추상 메소드입니다 - 서브클래스에서 구현이 필요함
            >>> import inspect
            >>> inspect.ismethod(Transport.send_message)
            False
            >>> hasattr(Transport, 'send_message')
            True
        """

    @abstractmethod
    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """전송에서 메시지를 수신합니다.

        Yields:
            수신된 메시지들

        예시:
            >>> # 이는 추상 메소드입니다 - 서브클래스에서 구현이 필요함
            >>> import inspect
            >>> inspect.ismethod(Transport.receive_message)
            False
            >>> hasattr(Transport, 'receive_message')
            True
        """

    @abstractmethod
    async def is_connected(self) -> bool:
        """전송이 연결되어 있는지 확인합니다.

        Returns:
            연결되어 있다면 True

        예시:
            >>> # 이는 추상 메소드입니다 - 서브클래스에서 구현이 필요함
            >>> import inspect
            >>> inspect.ismethod(Transport.is_connected)
            False
            >>> hasattr(Transport, 'is_connected')
            True
        """
