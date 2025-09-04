# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/cache/session_registry.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

선택적 분산 상태를 지원하는 세션 레지스트리.
Redis 또는 SQLAlchemy를 선택적 백엔드로 사용하여 분산 배포에서 공유 상태를 지원하는 SSE 세션 레지스트리를 제공합니다.

SessionRegistry 클래스는 여러 워커 프로세스에서 서버 전송 이벤트(SSE) 세션을 관리하여
MCP 게이트웨이 배포의 수평 확장을 가능하게 합니다. 세 가지 백엔드 모드를 지원합니다:

- **memory**: 단일 프로세스 배포용 메모리 기반 저장소 (기본값)
- **redis**: 다중 워커 배포용 Redis 지원 공유 저장소
- **database**: 다중 워커 배포용 SQLAlchemy 지원 공유 저장소

분산 모드(redis/database)에서는 세션 존재가 공유 백엔드에서 추적되는 반면,
전송 객체는 각 워커 프로세스에 로컬로 유지됩니다. 이를 통해 워커들은 다른 워커의 세션에 대해
알고 메시지를 적절하게 라우팅할 수 있습니다.

사용 예시:
    메모리 백엔드 기본 사용법:

    >>> from mcpgateway.cache.session_registry import SessionRegistry
    >>> class DummyTransport:
    ...     async def disconnect(self):
    ...         pass
    ...     async def is_connected(self):
    ...         return True
    >>> import asyncio
    >>> reg = SessionRegistry(backend='memory')
    >>> transport = DummyTransport()
    >>> asyncio.run(reg.add_session('sid123', transport))
    >>> found = asyncio.run(reg.get_session('sid123'))
    >>> isinstance(found, DummyTransport)
    True
    >>> asyncio.run(reg.remove_session('sid123'))
    >>> asyncio.run(reg.get_session('sid123')) is None
    True

    메시지 브로드캐스팅:

    >>> reg = SessionRegistry(backend='memory')
    >>> asyncio.run(reg.broadcast('sid123', {'method': 'ping', 'id': 1}))
    >>> reg._session_message is not None
    True
"""

# Standard
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

# Third-Party
from fastapi import HTTPException, status

# First-Party
from mcpgateway import __version__
from mcpgateway.config import settings
from mcpgateway.db import get_db, SessionMessageRecord, SessionRecord
from mcpgateway.models import Implementation, InitializeResult, ServerCapabilities
from mcpgateway.services import PromptService, ResourceService, ToolService
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.transports import SSETransport
from mcpgateway.utils.retry_manager import ResilientHttpClient
from mcpgateway.validation.jsonrpc import JSONRPCError

# Initialize logging service first
logging_service: LoggingService = LoggingService()
logger = logging_service.get_logger(__name__)

tool_service: ToolService = ToolService()
resource_service: ResourceService = ResourceService()
prompt_service: PromptService = PromptService()

try:
    # Third-Party
    from redis.asyncio import Redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    # Third-Party
    from sqlalchemy import func

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


class SessionBackend:
    """세션 레지스트리 백엔드 구성의 기본 클래스.

    이 클래스는 세션 저장을 위한 다양한 백엔드 타입의 초기화 및 구성을 처리합니다.
    Redis 또는 데이터베이스 백엔드에 필요한 연결을 설정하고 백엔드 요구사항을 검증합니다.

    속성:
        _backend: 백엔드 타입 ('memory', 'redis', 'database', 또는 'none')
        _session_ttl: 세션의 생존 시간 (초 단위)
        _message_ttl: 메시지의 생존 시간 (초 단위)
        _redis: Redis 연결 인스턴스 (redis 백엔드 전용)
        _pubsub: Redis pubsub 인스턴스 (redis 백엔드 전용)
        _session_message: 임시 메시지 저장소 (memory 백엔드 전용)

    사용 예시:
        >>> backend = SessionBackend(backend='memory')
        >>> backend._backend
        'memory'
        >>> backend._session_ttl
        3600

        >>> try:
        ...     backend = SessionBackend(backend='redis')
        ... except ValueError as e:
        ...     str(e)
        'Redis backend requires redis_url'
    """

    def __init__(
        self,
        backend: str = "memory",
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        session_ttl: int = 3600,  # 1 hour
        message_ttl: int = 600,  # 10 min
    ):
        """세션 백엔드 구성을 초기화.

        Args:
            backend: 백엔드 타입. 'memory', 'redis', 'database', 'none' 중 하나여야 함.
                - 'memory': 메모리 기반 저장소, 단일 프로세스 배포에 적합
                - 'redis': Redis 지원 저장소, 다중 워커 배포용
                - 'database': SQLAlchemy 지원 저장소, 다중 워커 배포용
                - 'none': 세션 추적 없음 (더미 레지스트리)
            redis_url: Redis 연결 URL. backend='redis'일 때 필수.
                형식: 'redis://[:password]@host:port/db'
            database_url: 데이터베이스 연결 URL. backend='database'일 때 필수.
                데이터베이스 타입에 따라 형식 결정 (예: 'postgresql://user:pass@host/db')
            session_ttl: 세션 생존 시간 (초 단위). 이 시간 동안 비활성 상태인 세션은
                자동으로 정리됩니다. 기본값: 3600 (1시간).
            message_ttl: 메시지 생존 시간 (초 단위). 배달되지 않은 메시지는
                이 시간 후 제거됩니다. 기본값: 600 (10분).

        Raises:
            ValueError: 백엔드가 유효하지 않거나, 필수 URL이 누락되었거나,
                필수 패키지가 설치되지 않은 경우.

        사용 예시:
            >>> # 메모리 백엔드 (기본값)
            >>> backend = SessionBackend()
            >>> backend._backend
            'memory'

            >>> # Redis 백엔드는 URL이 필요함
            >>> try:
            ...     backend = SessionBackend(backend='redis')
            ... except ValueError as e:
            ...     'redis_url' in str(e)
            True

            >>> # 유효하지 않은 백엔드
            >>> try:
            ...     backend = SessionBackend(backend='invalid')
            ... except ValueError as e:
            ...     'Invalid backend' in str(e)
            True
        """

        self._backend = backend.lower()
        self._session_ttl = session_ttl
        self._message_ttl = message_ttl

        # Set up backend-specific components
        if self._backend == "memory":
            # Nothing special needed for memory backend
            self._session_message = None

        elif self._backend == "none":
            # No session tracking - this is just a dummy registry
            logger.info("Session registry initialized with 'none' backend - session tracking disabled")

        elif self._backend == "redis":
            if not REDIS_AVAILABLE:
                raise ValueError("Redis backend requested but redis package not installed")
            if not redis_url:
                raise ValueError("Redis backend requires redis_url")

            self._redis = Redis.from_url(redis_url)
            self._pubsub = self._redis.pubsub()

        elif self._backend == "database":
            if not SQLALCHEMY_AVAILABLE:
                raise ValueError("Database backend requested but SQLAlchemy not installed")
            if not database_url:
                raise ValueError("Database backend requires database_url")
        else:
            raise ValueError(f"Invalid backend: {backend}")


class SessionRegistry(SessionBackend):
    """선택적 분산 상태를 지원하는 SSE 세션 레지스트리.

    이 클래스는 서버 전송 이벤트(SSE) 세션을 관리하며, 세션 추가, 제거, 조회 메소드를 제공합니다.
    다양한 배포 시나리오를 위한 여러 백엔드 타입을 지원합니다:

    - **단일 프로세스 배포**: 'memory' 백엔드 사용 (기본값)
    - **다중 워커 배포**: 'redis' 또는 'database' 백엔드 사용
    - **테스트/개발**: 'none' 백엔드로 세션 추적 비활성화

    레지스트리는 전송 객체의 로컬 캐시를 유지하면서 워커 간 세션 존재를
    추적하기 위해 공유 백엔드를 사용합니다. 이를 통해 전송 객체를 프로세스 로컬로 유지하면서
    수평 확장을 가능하게 합니다.

    속성:
        _sessions: 세션 ID를 전송 객체에 매핑하는 로컬 딕셔너리
        _lock: _sessions에 대한 스레드 안전한 접근을 위한 asyncio 락
        _cleanup_task: 만료된 세션 정리용 백그라운드 태스크

    사용 예시:
        >>> import asyncio
        >>> from mcpgateway.cache.session_registry import SessionRegistry
        >>>
        >>> class MockTransport:
        ...     async def disconnect(self):
        ...         print("연결 해제됨")
        ...     async def is_connected(self):
        ...         return True
        ...     async def send_message(self, msg):
        ...         print(f"전송됨: {msg}")
        >>>
        >>> # 레지스트리 생성 및 세션 추가
        >>> reg = SessionRegistry(backend='memory')
        >>> transport = MockTransport()
        >>> asyncio.run(reg.add_session('test123', transport))
        >>>
        >>> # 세션 조회
        >>> found = asyncio.run(reg.get_session('test123'))
        >>> found is transport
        True
        >>>
        >>> # 세션 제거
        >>> asyncio.run(reg.remove_session('test123'))
        연결 해제됨
        >>> asyncio.run(reg.get_session('test123')) is None
        True
    """

    def __init__(
        self,
        backend: str = "memory",
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        session_ttl: int = 3600,  # 1 hour
        message_ttl: int = 600,  # 10 min
    ):
        """지정된 백엔드로 세션 레지스트리를 초기화.

        Args:
            backend: 백엔드 타입. 'memory', 'redis', 'database', 'none' 중 하나여야 함.
            redis_url: Redis 연결 URL. backend='redis'일 때 필수.
            database_url: 데이터베이스 연결 URL. backend='database'일 때 필수.
            session_ttl: 세션 생존 시간 (초 단위). 기본값: 3600.
            message_ttl: 메시지 생존 시간 (초 단위). 기본값: 600.

        사용 예시:
            >>> # 기본 메모리 백엔드
            >>> reg = SessionRegistry()
            >>> reg._backend
            'memory'
            >>> isinstance(reg._sessions, dict)
            True

            >>> # 사용자 정의 TTL을 가진 Redis 백엔드
            >>> try:
            ...     reg = SessionRegistry(
            ...         backend='redis',
            ...         redis_url='redis://localhost:6379',
            ...         session_ttl=7200
            ...     )
            ... except ValueError:
            ...     pass  # Redis가 사용 불가능할 수 있음
        """
        # 부모 클래스 초기화 (백엔드 설정)
        super().__init__(backend=backend, redis_url=redis_url, database_url=database_url, session_ttl=session_ttl, message_ttl=message_ttl)

        # 로컬 전송 객체 캐시: 세션 ID를 전송 객체에 매핑
        self._sessions: Dict[str, Any] = {}

        # 스레드 안전성을 위한 비동기 락
        self._lock = asyncio.Lock()

        # 백그라운드 정리 태스크 참조
        self._cleanup_task = None

    async def initialize(self) -> None:
        """비동기 설정으로 레지스트리를 초기화.

        이 메소드는 __init__에서 수행할 수 없는 비동기 초기화 작업을 수행합니다.
        백그라운드 정리 태스크를 시작하고 분산 백엔드의 pubsub 구독을 설정합니다.

        레지스트리 인스턴스 생성 후 애플리케이션 시작 시 호출하세요.

        사용 예시:
            >>> import asyncio
            >>> reg = SessionRegistry(backend='memory')
            >>> asyncio.run(reg.initialize())
            >>> reg._cleanup_task is not None
            True
            >>>
            >>> # 정리
            >>> asyncio.run(reg.shutdown())
        """
        logger.info(f"백엔드 {self._backend}로 세션 레지스트리 초기화 중")

        if self._backend == "database":
            # 데이터베이스 정리 태스크 시작
            self._cleanup_task = asyncio.create_task(self._db_cleanup_task())
            logger.info("데이터베이스 정리 태스크 시작됨")

        elif self._backend == "redis":
            # Redis pubsub 채널 구독으로 세션 이벤트 수신
            await self._pubsub.subscribe("mcp_session_events")

        elif self._backend == "none":
            # none 백엔드는 초기화할 것이 없음
            pass

        # 메모리 백엔드는 세션 정리 필요
        elif self._backend == "memory":
            self._cleanup_task = asyncio.create_task(self._memory_cleanup_task())
            logger.info("메모리 정리 태스크 시작됨")

    async def shutdown(self) -> None:
        """레지스트리를 종료하고 리소스를 정리.

        이 메소드는 백그라운드 태스크를 취소하고 외부 서비스 연결을 닫습니다.
        깔끔한 종료를 위해 애플리케이션 종료 시 호출하세요.

        사용 예시:
            >>> import asyncio
            >>> reg = SessionRegistry()
            >>> asyncio.run(reg.initialize())
            >>> task_was_created = reg._cleanup_task is not None
            >>> asyncio.run(reg.shutdown())
            >>> # 종료 후, 정리 태스크는 취소되거나 완료되어야 함
            >>> task_was_created and (reg._cleanup_task.cancelled() or reg._cleanup_task.done())
            True
        """
        logger.info("세션 레지스트리 종료 중")

        # 정리 태스크 취소
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Redis 연결 종료
        if self._backend == "redis":
            try:
                await self._pubsub.aclose()
                await self._redis.aclose()
            except Exception as e:
                logger.error(f"Redis 연결 종료 오류: {e}")
                # 오류 예시:
                # >>> import logging
                # >>> logger = logging.getLogger(__name__)
                # >>> logger.error(f"Redis 연결 종료 오류: 연결 끊어짐")  # doctest: +SKIP

    async def add_session(self, session_id: str, transport: SSETransport) -> None:
        """레지스트리에 세션을 추가.

        로컬 캐시와 분산 백엔드(설정된 경우)에 세션을 저장합니다.
        분산 백엔드의 경우 다른 워커들에게 새 세션에 대해 알립니다.

        Args:
            session_id: 고유 세션 식별자. 충돌을 피하기 위해 UUID 또는 유사한
                고유 문자열이어야 합니다.
            transport: 이 세션의 SSE 전송 객체. SSETransport 인터페이스를
                구현해야 합니다.

        사용 예시:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> class MockTransport:
            ...     async def disconnect(self):
            ...         print(f"전송 연결 해제됨")
            ...     async def is_connected(self):
            ...         return True
            >>>
            >>> reg = SessionRegistry()
            >>> transport = MockTransport()
            >>> asyncio.run(reg.add_session('test-456', transport))
            >>>
            >>> # 로컬 캐시에서 찾음
            >>> found = asyncio.run(reg.get_session('test-456'))
            >>> found is transport
            True
            >>>
            >>> # 세션 제거
            >>> asyncio.run(reg.remove_session('test-456'))
            전송 연결 해제됨
        """
        # none 백엔드는 건너뜀
        if self._backend == "none":
            return

        # 스레드 안전하게 로컬 세션 캐시에 저장
        async with self._lock:
            self._sessions[session_id] = transport

        if self._backend == "redis":
            # Redis에 세션 마커 저장
            try:
                await self._redis.setex(f"mcp:session:{session_id}", self._session_ttl, "1")
                # 다른 워커들에게 알리기 위해 이벤트 발행
                await self._redis.publish("mcp_session_events", json.dumps({"type": "add", "session_id": session_id, "timestamp": time.time()}))
            except Exception as e:
                logger.error(f"Redis 세션 추가 오류 {session_id}: {e}")

        elif self._backend == "database":
            # 데이터베이스에 세션 저장
            try:

                def _db_add() -> None:
                    """Store session record in the database.

                    Creates a new SessionRecord entry in the database for tracking
                    distributed session state. Uses a fresh database connection from
                    the connection pool.

                    This inner function is designed to be run in a thread executor
                    to avoid blocking the async event loop during database I/O.

                    Raises:
                        Exception: Any database error is re-raised after rollback.
                            Common errors include duplicate session_id (unique constraint)
                            or database connection issues.

                    Examples:
                        >>> # This function is called internally by add_session()
                        >>> # When executed, it creates a database record:
                        >>> # SessionRecord(session_id='abc123', created_at=now())
                    """
                    db_session = next(get_db())
                    try:
                        session_record = SessionRecord(session_id=session_id)
                        db_session.add(session_record)
                        db_session.commit()
                    except Exception as ex:
                        db_session.rollback()
                        raise ex
                    finally:
                        db_session.close()

                await asyncio.to_thread(_db_add)
            except Exception as e:
                logger.error(f"Database error adding session {session_id}: {e}")

        logger.info(f"Added session: {session_id}")

    async def get_session(self, session_id: str) -> Any:
        """ID로 세션 전송 객체를 조회.

        먼저 로컬 캐시에서 전송 객체를 확인합니다. 로컬에서 찾을 수 없지만
        분산 백엔드를 사용하는 경우 다른 워커에 세션이 존재하는지 확인합니다.

        Args:
            session_id: 조회할 세션 식별자.

        Returns:
            로컬에서 찾은 경우 SSETransport 객체, 찾을 수 없거나 다른 워커에
            존재하는 경우 None.

        사용 예시:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> class MockTransport:
            ...     pass
            >>>
            >>> reg = SessionRegistry()
            >>> transport = MockTransport()
            >>> asyncio.run(reg.add_session('test-456', transport))
            >>>
            >>> # 로컬 캐시에서 찾음
            >>> found = asyncio.run(reg.get_session('test-456'))
            >>> found is transport
            True
            >>>
            >>> # 찾을 수 없음
            >>> asyncio.run(reg.get_session('nonexistent')) is None
            True
        """
        # none 백엔드는 건너뜀
        if self._backend == "none":
            return None

        # 먼저 로컬 캐시 확인
        async with self._lock:
            transport = self._sessions.get(session_id)
            if transport:
                logger.info(f"세션 {session_id}이 로컬 캐시에 존재함")
                return transport

        # 로컬 캐시에 없으면 공유 백엔드에서 존재 여부 확인
        if self._backend == "redis":
            try:
                exists = await self._redis.exists(f"mcp:session:{session_id}")
                session_exists = bool(exists)
                if session_exists:
                    logger.info(f"세션 {session_id}이 Redis에 존재하지만 로컬 캐시에는 없음")
                return None  # 로컬에 전송 객체가 없음
            except Exception as e:
                logger.error(f"Redis error checking session {session_id}: {e}")
                return None

        elif self._backend == "database":
            try:

                def _db_check() -> bool:
                    """Check if a session exists in the database.

                    Queries the SessionRecord table to determine if a session with
                    the given session_id exists. This is used when the session is not
                    found in the local cache to check if it exists on another worker.

                    This inner function is designed to be run in a thread executor
                    to avoid blocking the async event loop during database queries.

                    Returns:
                        bool: True if the session exists in the database, False otherwise.

                    Examples:
                        >>> # This function is called internally by get_session()
                        >>> # Returns True if SessionRecord with session_id exists
                        >>> # Returns False if no matching record found
                    """
                    db_session = next(get_db())
                    try:
                        record = db_session.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
                        return record is not None
                    finally:
                        db_session.close()

                exists = await asyncio.to_thread(_db_check)
                if exists:
                    logger.info(f"Session {session_id} exists in database but not in local cache")
                return None
            except Exception as e:
                logger.error(f"Database error checking session {session_id}: {e}")
                return None

        return None

    async def remove_session(self, session_id: str) -> None:
        """Remove a session from the registry.

        Removes the session from both local cache and distributed backend.
        If a transport is found locally, it will be disconnected before removal.
        For distributed backends, notifies other workers about the removal.

        Args:
            session_id: Session identifier to remove.

        Examples:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> class MockTransport:
            ...     async def disconnect(self):
            ...         print(f"Transport disconnected")
            ...     async def is_connected(self):
            ...         return True
            >>>
            >>> reg = SessionRegistry()
            >>> transport = MockTransport()
            >>> asyncio.run(reg.add_session('remove-test', transport))
            >>> asyncio.run(reg.remove_session('remove-test'))
            Transport disconnected
            >>>
            >>> # Session no longer exists
            >>> asyncio.run(reg.get_session('remove-test')) is None
            True
        """
        # Skip for none backend
        if self._backend == "none":
            return

        # Clean up local transport
        transport = None
        async with self._lock:
            if session_id in self._sessions:
                transport = self._sessions.pop(session_id)

        # Disconnect transport if found
        if transport:
            try:
                await transport.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting transport for session {session_id}: {e}")

        # Remove from shared backend
        if self._backend == "redis":
            try:
                await self._redis.delete(f"mcp:session:{session_id}")
                # Notify other workers
                await self._redis.publish("mcp_session_events", json.dumps({"type": "remove", "session_id": session_id, "timestamp": time.time()}))
            except Exception as e:
                logger.error(f"Redis error removing session {session_id}: {e}")

        elif self._backend == "database":
            try:

                def _db_remove() -> None:
                    """Delete session record from the database.

                    Removes the SessionRecord entry with the specified session_id
                    from the database. This is called when a session is being
                    terminated or has expired.

                    This inner function is designed to be run in a thread executor
                    to avoid blocking the async event loop during database operations.

                    Raises:
                        Exception: Any database error is re-raised after rollback.
                            This includes connection errors or constraint violations.

                    Examples:
                        >>> # This function is called internally by remove_session()
                        >>> # Deletes the SessionRecord where session_id matches
                        >>> # No error if session_id doesn't exist (idempotent)
                    """
                    db_session = next(get_db())
                    try:
                        db_session.query(SessionRecord).filter(SessionRecord.session_id == session_id).delete()
                        db_session.commit()
                    except Exception as ex:
                        db_session.rollback()
                        raise ex
                    finally:
                        db_session.close()

                await asyncio.to_thread(_db_remove)
            except Exception as e:
                logger.error(f"Database error removing session {session_id}: {e}")

        logger.info(f"Removed session: {session_id}")

    async def broadcast(self, session_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to a session.

        Sends a message to the specified session. The behavior depends on the backend:

        - **memory**: Stores message temporarily for local delivery
        - **redis**: Publishes message to Redis channel for the session
        - **database**: Stores message in database for polling by worker with session
        - **none**: No operation

        This method is used for inter-process communication in distributed deployments.

        Args:
            session_id: Target session identifier.
            message: Message to broadcast. Can be a dict, list, or any JSON-serializable object.

        Examples:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> reg = SessionRegistry(backend='memory')
            >>> message = {'method': 'tools/list', 'id': 1}
            >>> asyncio.run(reg.broadcast('session-789', message))
            >>>
            >>> # Message stored for memory backend
            >>> reg._session_message is not None
            True
            >>> reg._session_message['session_id']
            'session-789'
            >>> json.loads(reg._session_message['message']) == message
            True
        """
        # Skip for none backend only
        if self._backend == "none":
            return

        if self._backend == "memory":
            if isinstance(message, (dict, list)):
                msg_json = json.dumps(message)
            else:
                msg_json = json.dumps(str(message))

            self._session_message: Dict[str, Any] = {"session_id": session_id, "message": msg_json}

        elif self._backend == "redis":
            try:
                if isinstance(message, (dict, list)):
                    msg_json = json.dumps(message)
                else:
                    msg_json = json.dumps(str(message))

                await self._redis.publish(session_id, json.dumps({"type": "message", "message": msg_json, "timestamp": time.time()}))
            except Exception as e:
                logger.error(f"Redis error during broadcast: {e}")
        elif self._backend == "database":
            try:
                if isinstance(message, (dict, list)):
                    msg_json = json.dumps(message)
                else:
                    msg_json = json.dumps(str(message))

                def _db_add() -> None:
                    """Store message in the database for inter-process communication.

                    Creates a new SessionMessageRecord entry containing the session_id
                    and serialized message. This enables message passing between
                    different worker processes through the shared database.

                    This inner function is designed to be run in a thread executor
                    to avoid blocking the async event loop during database writes.

                    Raises:
                        Exception: Any database error is re-raised after rollback.
                            Common errors include database connection issues or
                            constraints violations.

                    Examples:
                        >>> # This function is called internally by broadcast()
                        >>> # Creates a record like:
                        >>> # SessionMessageRecord(
                        >>> #     session_id='abc123',
                        >>> #     message='{"method": "ping", "id": 1}',
                        >>> #     created_at=now()
                        >>> # )
                    """
                    db_session = next(get_db())
                    try:
                        message_record = SessionMessageRecord(session_id=session_id, message=msg_json)
                        db_session.add(message_record)
                        db_session.commit()
                    except Exception as ex:
                        db_session.rollback()
                        raise ex
                    finally:
                        db_session.close()

                await asyncio.to_thread(_db_add)
            except Exception as e:
                logger.error(f"Database error during broadcast: {e}")

    def get_session_sync(self, session_id: str) -> Any:
        """Get session synchronously from local cache only.

        This is a non-blocking method that only checks the local cache,
        not the distributed backend. Use this when you need quick access
        and know the session should be local.

        Args:
            session_id: Session identifier to look up.

        Returns:
            SSETransport object if found in local cache, None otherwise.

        Examples:
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>> import asyncio
            >>>
            >>> class MockTransport:
            ...     pass
            >>>
            >>> reg = SessionRegistry()
            >>> transport = MockTransport()
            >>> asyncio.run(reg.add_session('sync-test', transport))
            >>>
            >>> # Synchronous lookup
            >>> found = reg.get_session_sync('sync-test')
            >>> found is transport
            True
            >>>
            >>> # Not found
            >>> reg.get_session_sync('nonexistent') is None
            True
        """
        # Skip for none backend
        if self._backend == "none":
            return None

        return self._sessions.get(session_id)

    async def respond(
        self,
        server_id: Optional[str],
        user: Dict[str, Any],
        session_id: str,
        base_url: str,
    ) -> None:
        """Process and respond to broadcast messages for a session.

        This method listens for messages directed to the specified session and
        generates appropriate responses. The listening mechanism depends on the backend:

        - **memory**: Checks the temporary message storage
        - **redis**: Subscribes to Redis pubsub channel
        - **database**: Polls database for new messages

        When a message is received and the transport exists locally, it processes
        the message and sends the response through the transport.

        Args:
            server_id: Optional server identifier for scoped operations.
            user: User information including authentication token.
            session_id: Session identifier to respond for.
            base_url: Base URL for API calls (used for RPC endpoints).

        Examples:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> # This method is typically called internally by the SSE handler
            >>> reg = SessionRegistry()
            >>> user = {'token': 'test-token'}
            >>> # asyncio.run(reg.respond(None, user, 'session-id', 'http://localhost'))
        """

        if self._backend == "none":
            pass

        elif self._backend == "memory":
            # if self._session_message:
            transport = self.get_session_sync(session_id)
            if transport:
                message = json.loads(str(self._session_message.get("message")))
                await self.generate_response(message=message, transport=transport, server_id=server_id, user=user, base_url=base_url)

        elif self._backend == "redis":
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(session_id)

            try:
                async for msg in pubsub.listen():
                    if msg["type"] != "message":
                        continue
                    data = json.loads(msg["data"])
                    message = data.get("message", {})
                    if isinstance(message, str):
                        message = json.loads(message)
                    transport = self.get_session_sync(session_id)
                    if transport:
                        await self.generate_response(message=message, transport=transport, server_id=server_id, user=user, base_url=base_url)
            except asyncio.CancelledError:
                logger.info(f"PubSub listener for session {session_id} cancelled")
            finally:
                await pubsub.unsubscribe(session_id)
                await pubsub.close()
                logger.info(f"Cleaned up pubsub for session {session_id}")

        elif self._backend == "database":

            def _db_read_session(session_id: str) -> SessionRecord:
                """Check if session still exists in the database.

                Queries the SessionRecord table to verify that the session
                is still active. Used in the message polling loop to determine
                when to stop checking for messages.

                This inner function is designed to be run in a thread executor
                to avoid blocking the async event loop during database reads.

                Args:
                    session_id: The session identifier to look up.

                Returns:
                    SessionRecord: The session record if found, None otherwise.

                Raises:
                    Exception: Any database error is re-raised after rollback.

                Examples:
                    >>> # This function is called internally by message_check_loop()
                    >>> # Returns SessionRecord object if session exists
                    >>> # Returns None if session has been removed
                """
                db_session = next(get_db())
                try:
                    # Delete sessions that haven't been accessed for TTL seconds
                    result = db_session.query(SessionRecord).filter_by(session_id=session_id).first()
                    return result
                except Exception as ex:
                    db_session.rollback()
                    raise ex
                finally:
                    db_session.close()

            def _db_read(session_id: str) -> SessionMessageRecord:
                """Read pending message for a session from the database.

                Retrieves the first (oldest) unprocessed message for the given
                session_id from the SessionMessageRecord table. Messages are
                processed in FIFO order.

                This inner function is designed to be run in a thread executor
                to avoid blocking the async event loop during database queries.

                Args:
                    session_id: The session identifier to read messages for.

                Returns:
                    SessionMessageRecord: The oldest message record if found, None otherwise.

                Raises:
                    Exception: Any database error is re-raised after rollback.

                Examples:
                    >>> # This function is called internally by message_check_loop()
                    >>> # Returns SessionMessageRecord with message data
                    >>> # Returns None if no pending messages
                """
                db_session = next(get_db())
                try:
                    # Delete sessions that haven't been accessed for TTL seconds
                    result = db_session.query(SessionMessageRecord).filter_by(session_id=session_id).first()
                    return result
                except Exception as ex:
                    db_session.rollback()
                    raise ex
                finally:
                    db_session.close()

            def _db_remove(session_id: str, message: str) -> None:
                """Remove processed message from the database.

                Deletes a specific message record after it has been successfully
                processed and sent to the transport. This prevents duplicate
                message delivery.

                This inner function is designed to be run in a thread executor
                to avoid blocking the async event loop during database deletes.

                Args:
                    session_id: The session identifier the message belongs to.
                    message: The exact message content to remove (must match exactly).

                Raises:
                    Exception: Any database error is re-raised after rollback.

                Examples:
                    >>> # This function is called internally after message processing
                    >>> # Deletes the specific SessionMessageRecord entry
                    >>> # Log: "Removed message from mcp_messages table"
                """
                db_session = next(get_db())
                try:
                    db_session.query(SessionMessageRecord).filter(SessionMessageRecord.session_id == session_id).filter(SessionMessageRecord.message == message).delete()
                    db_session.commit()
                    logger.info("Removed message from mcp_messages table")
                except Exception as ex:
                    db_session.rollback()
                    raise ex
                finally:
                    db_session.close()

            async def message_check_loop(session_id: str) -> None:
                """Poll database for messages and deliver to local transport.

                Continuously checks the database for new messages directed to
                the specified session_id. When messages are found and the
                transport exists locally, delivers the message and removes it
                from the database. Exits when the session no longer exists.

                This coroutine runs as a background task for each active session
                using database backend, enabling message delivery across worker
                processes.

                Args:
                    session_id: The session identifier to monitor for messages.

                Examples:
                    >>> # This function is called as a task by respond()
                    >>> # asyncio.create_task(message_check_loop('abc123'))
                    >>> # Polls every 0.1 seconds until session is removed
                    >>> # Delivers messages to transport and cleans up database
                """
                while True:
                    record = await asyncio.to_thread(_db_read, session_id)

                    if record:
                        message = json.loads(record.message)
                        transport = self.get_session_sync(session_id)
                        if transport:
                            logger.info("Ready to respond")
                            await self.generate_response(message=message, transport=transport, server_id=server_id, user=user, base_url=base_url)

                            await asyncio.to_thread(_db_remove, session_id, record.message)

                    session_exists = await asyncio.to_thread(_db_read_session, session_id)
                    if not session_exists:
                        break

                    await asyncio.sleep(0.1)

            asyncio.create_task(message_check_loop(session_id))

    async def _refresh_redis_sessions(self) -> None:
        """Refresh TTLs for Redis sessions and clean up disconnected sessions.

        This internal method is used by the Redis backend to maintain session state.
        It checks all local sessions, refreshes TTLs for connected sessions, and
        removes disconnected ones.
        """
        try:
            # Check all local sessions
            local_transports = {}
            async with self._lock:
                local_transports = self._sessions.copy()

            for session_id, transport in local_transports.items():
                try:
                    if await transport.is_connected():
                        # Refresh TTL in Redis
                        await self._redis.expire(f"mcp:session:{session_id}", self._session_ttl)
                    else:
                        # Remove disconnected session
                        await self.remove_session(session_id)
                except Exception as e:
                    logger.error(f"Error refreshing session {session_id}: {e}")

        except Exception as e:
            logger.error(f"Error in Redis session refresh: {e}")

    async def _db_cleanup_task(self) -> None:
        """Background task to clean up expired database sessions.

        Runs periodically (every 5 minutes) to remove expired sessions from the
        database and refresh timestamps for active sessions. This prevents the
        database from accumulating stale session records.

        The task also verifies that local sessions still exist in the database
        and removes them locally if they've been deleted elsewhere.
        """
        logger.info("Starting database cleanup task")
        while True:
            try:
                # Clean up expired sessions every 5 minutes
                def _db_cleanup() -> int:
                    """Remove expired sessions from the database.

                    Deletes all SessionRecord entries that haven't been accessed
                    within the session TTL period. Uses database-specific date
                    arithmetic to calculate expiry time.

                    This inner function is designed to be run in a thread executor
                    to avoid blocking the async event loop during bulk deletes.

                    Returns:
                        int: Number of expired session records deleted.

                    Raises:
                        Exception: Any database error is re-raised after rollback.

                    Examples:
                        >>> # This function is called periodically by _db_cleanup_task()
                        >>> # Deletes sessions older than session_ttl seconds
                        >>> # Returns count of deleted records for logging
                        >>> # Log: "Cleaned up 5 expired database sessions"
                    """
                    db_session = next(get_db())
                    try:
                        # Delete sessions that haven't been accessed for TTL seconds
                        expiry_time = func.now() - func.make_interval(seconds=self._session_ttl)  # pylint: disable=not-callable
                        result = db_session.query(SessionRecord).filter(SessionRecord.last_accessed < expiry_time).delete()
                        db_session.commit()
                        return result
                    except Exception as ex:
                        db_session.rollback()
                        raise ex
                    finally:
                        db_session.close()

                deleted = await asyncio.to_thread(_db_cleanup)
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired database sessions")

                # Check local sessions against database
                local_transports = {}
                async with self._lock:
                    local_transports = self._sessions.copy()

                for session_id, transport in local_transports.items():
                    try:
                        if not await transport.is_connected():
                            await self.remove_session(session_id)
                            continue

                        # Refresh session in database
                        def _refresh_session(session_id: str = session_id) -> bool:
                            """Update session's last accessed timestamp in the database.

                            Refreshes the last_accessed field for an active session to
                            prevent it from being cleaned up as expired. This is called
                            periodically for all local sessions with active transports.

                            This inner function is designed to be run in a thread executor
                            to avoid blocking the async event loop during database updates.

                            Args:
                                session_id: The session identifier to refresh (default from closure).

                            Returns:
                                bool: True if the session was found and updated, False if not found.

                            Raises:
                                Exception: Any database error is re-raised after rollback.

                            Examples:
                                >>> # This function is called for each active local session
                                >>> # Updates SessionRecord.last_accessed to current time
                                >>> # Returns True if session exists and was refreshed
                                >>> # Returns False if session no longer exists in database
                            """
                            db_session = next(get_db())
                            try:
                                session = db_session.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()

                                if session:
                                    # Update last_accessed
                                    session.last_accessed = func.now()  # pylint: disable=not-callable
                                    db_session.commit()
                                    return True
                                return False
                            except Exception as ex:
                                db_session.rollback()
                                raise ex
                            finally:
                                db_session.close()

                        session_exists = await asyncio.to_thread(_refresh_session)
                        if not session_exists:
                            # Session no longer in database, remove locally
                            await self.remove_session(session_id)

                    except Exception as e:
                        logger.error(f"Error checking session {session_id}: {e}")

                await asyncio.sleep(300)  # Run every 5 minutes

            except asyncio.CancelledError:
                logger.info("Database cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in database cleanup task: {e}")
                await asyncio.sleep(600)  # Sleep longer on error

    async def _memory_cleanup_task(self) -> None:
        """Background task to clean up disconnected sessions in memory backend.

        Runs periodically (every minute) to check all local sessions and remove
        those that are no longer connected. This prevents memory leaks from
        accumulating disconnected transport objects.
        """
        logger.info("Starting memory cleanup task")
        while True:
            try:
                # Check all local sessions
                local_transports = {}
                async with self._lock:
                    local_transports = self._sessions.copy()

                for session_id, transport in local_transports.items():
                    try:
                        if not await transport.is_connected():
                            await self.remove_session(session_id)
                    except Exception as e:
                        logger.error(f"Error checking session {session_id}: {e}")
                        await self.remove_session(session_id)

                await asyncio.sleep(60)  # Run every minute

            except asyncio.CancelledError:
                logger.info("Memory cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in memory cleanup task: {e}")
                await asyncio.sleep(300)  # Sleep longer on error

    # Handle initialize logic
    async def handle_initialize_logic(self, body: Dict[str, Any]) -> InitializeResult:
        """Process MCP protocol initialization request.

        Validates the protocol version and returns server capabilities and information.
        This method implements the MCP (Model Context Protocol) initialization handshake.

        Args:
            body: Request body containing protocol_version and optional client_info.
                Expected keys: 'protocol_version' or 'protocolVersion'.

        Returns:
            InitializeResult containing protocol version, server capabilities, and server info.

        Raises:
            HTTPException: If protocol_version is missing (400 Bad Request with MCP error code -32002).

        Examples:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> reg = SessionRegistry()
            >>> body = {'protocol_version': '2025-03-26'}
            >>> result = asyncio.run(reg.handle_initialize_logic(body))
            >>> result.protocol_version
            '2025-03-26'
            >>> result.server_info.name
            'MCP_Gateway'
            >>>
            >>> # Missing protocol version
            >>> try:
            ...     asyncio.run(reg.handle_initialize_logic({}))
            ... except HTTPException as e:
            ...     e.status_code
            400
        """
        protocol_version = body.get("protocol_version") or body.get("protocolVersion")
        # body.get("capabilities", {})
        # body.get("client_info") or body.get("clientInfo", {})

        if not protocol_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing protocol version",
                headers={"MCP-Error-Code": "-32002"},
            )

        if protocol_version != settings.protocol_version:
            logger.warning(f"Using non default protocol version: {protocol_version}")

        return InitializeResult(
            protocolVersion=settings.protocol_version,
            capabilities=ServerCapabilities(
                prompts={"listChanged": True},
                resources={"subscribe": True, "listChanged": True},
                tools={"listChanged": True},
                logging={},
                # roots={"listChanged": True}
            ),
            serverInfo=Implementation(name=settings.app_name, version=__version__),
            instructions=("MCP Gateway providing federated tools, resources and prompts. Use /admin interface for configuration."),
        )

    async def generate_response(self, message: Dict[str, Any], transport: SSETransport, server_id: Optional[str], user: Dict[str, Any], base_url: str) -> None:
        """Generate and send response for incoming MCP protocol message.

        Processes MCP protocol messages and generates appropriate responses based on
        the method. Supports various MCP methods including initialization, tool/resource/prompt
        listing, tool invocation, and ping.

        Args:
            message: Incoming MCP message as JSON. Must contain 'method' and 'id' fields.
            transport: SSE transport to send responses through.
            server_id: Optional server ID for scoped operations.
            user: User information containing authentication token.
            base_url: Base URL for constructing RPC endpoints.

        Examples:
            >>> import asyncio
            >>> from mcpgateway.cache.session_registry import SessionRegistry
            >>>
            >>> class MockTransport:
            ...     async def send_message(self, msg):
            ...         print(f"Response: {msg['method'] if 'method' in msg else msg.get('result', {})}")
            >>>
            >>> reg = SessionRegistry()
            >>> transport = MockTransport()
            >>> message = {"method": "ping", "id": 1}
            >>> user = {"token": "test-token"}
            >>> # asyncio.run(reg.generate_response(message, transport, None, user, "http://localhost"))
            >>> # Response: {}
        """
        result = {}

        if "method" in message and "id" in message:
            try:
                method = message["method"]
                params = message.get("params", {})
                params["server_id"] = server_id
                req_id = message["id"]

                rpc_input = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": req_id,
                }
                headers = {"Authorization": f"Bearer {user['token']}", "Content-Type": "application/json"}
                rpc_url = base_url + "/rpc"
                async with ResilientHttpClient(client_args={"timeout": settings.federation_timeout, "verify": not settings.skip_ssl_verify}) as client:
                    rpc_response = await client.post(
                        url=rpc_url,
                        json=rpc_input,
                        headers=headers,
                    )
                    result = rpc_response.json()
                    result = result.get("result", {})

                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
            except JSONRPCError as e:
                result = e.to_dict()
                response = {"jsonrpc": "2.0", "error": result["error"], "id": req_id}
            except Exception as e:
                result = {"code": -32000, "message": "Internal error", "data": str(e)}
                response = {"jsonrpc": "2.0", "error": result, "id": req_id}

            logging.debug(f"Sending sse message:{response}")
            await transport.send_message(response)

            if message["method"] == "initialize":
                await transport.send_message(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    }
                )
                notifications = [
                    "tools/list_changed",
                    "resources/list_changed",
                    "prompts/list_changed",
                ]
                for notification in notifications:
                    await transport.send_message(
                        {
                            "jsonrpc": "2.0",
                            "method": f"notifications/{notification}",
                            "params": {},
                        }
                    )
