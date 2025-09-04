# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/cache/resource_cache.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

리소스 캐시 구현.
MCP Gateway에서 리소스 콘텐츠를 캐싱하기 위한 TTL 만료 기반 메모리 캐시를 구현합니다.
주요 기능:
- TTL 기반 만료
- 최대 크기 제한 및 LRU 제거
- 스레드 안전한 비동기 작업

사용 예시:
    >>> from mcpgateway.cache.resource_cache import ResourceCache
    >>> cache = ResourceCache(max_size=2, ttl=1)
    >>> cache.set('a', 1)
    >>> cache.get('a')
    1
    >>> import time
    >>> time.sleep(1.5)  # 만료를 확인하기 위해 1.5초 대기
    >>> cache.get('a') is None
    True
    >>> cache.set('a', 1)
    >>> cache.set('b', 2)
    >>> cache.set('c', 3)  # LRU 제거 발생
    >>> sorted(cache._cache.keys())
    ['b', 'c']
    >>> cache.delete('b')
    >>> cache.get('b') is None
    True
    >>> cache.clear()
    >>> cache.get('a') is None
    True
"""

# Standard
import asyncio
from dataclasses import dataclass
import time
from typing import Any, Dict, Optional

# First-Party
from mcpgateway.services.logging_service import LoggingService

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


@dataclass
class CacheEntry:
    """만료 시간을 포함한 캐시 엔트리."""

    value: Any          # 캐시에 저장될 실제 값
    expires_at: float   # 캐시 항목의 만료 시간 (Unix timestamp)
    last_access: float  # 마지막으로 접근한 시간 (LRU 정책용)


class ResourceCache:
    """
    TTL 만료 기반 리소스 콘텐츠 캐시.

    속성:
        max_size: 최대 캐시 엔트리 수
        ttl: 생존 시간 (초 단위)
        _cache: 캐시 저장소 (키-값 매핑)
        _lock: 스레드 안전성을 위한 비동기 락

    주요 특징:
        - TTL 기반 자동 만료
        - 최대 크기 제한 및 LRU(Least Recently Used) 제거 정책
        - 비동기 락을 통한 스레드 안전성 보장
        - 백그라운드 정리 태스크로 만료된 항목 자동 제거

    사용 예시:
        >>> from mcpgateway.cache.resource_cache import ResourceCache
        >>> cache = ResourceCache(max_size=2, ttl=1)
        >>> cache.set('a', 1)
        >>> cache.get('a')
        1
        >>> import time
        >>> time.sleep(1.5)  # 만료를 확인하기 위해 1.5초 대기
        >>> cache.get('a') is None
        True
        >>> cache.set('a', 1)
        >>> cache.set('b', 2)
        >>> cache.set('c', 3)  # LRU 제거 발생
        >>> sorted(cache._cache.keys())
        ['b', 'c']
        >>> cache.delete('b')
        >>> cache.get('b') is None
        True
        >>> cache.clear()
        >>> cache.get('a') is None
        True
    """

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """캐시 초기화.

        Args:
            max_size: 최대 캐시 엔트리 수 (기본값: 1000)
            ttl: 캐시 항목의 생존 시간 (초 단위, 기본값: 3600초 = 1시간)
        """
        # 캐시 설정 저장
        self.max_size = max_size
        self.ttl = ttl

        # 캐시 저장소: 키와 CacheEntry 객체의 매핑
        self._cache: Dict[str, CacheEntry] = {}

        # 스레드 안전성을 위한 비동기 락
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """캐시 서비스 초기화."""
        logger.info("리소스 캐시 초기화 중")
        # 백그라운드에서 만료된 항목들을 정리하는 태스크 시작
        asyncio.create_task(self._cleanup_loop())

    async def shutdown(self) -> None:
        """캐시 서비스 종료."""
        logger.info("리소스 캐시 종료 중")
        # 모든 캐시 항목 정리
        self.clear()

    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값을 조회.

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 또는 찾을 수 없거나 만료된 경우 None

        동작 과정:
            1. 캐시에서 키를 찾음
            2. 항목이 존재하면 만료 시간 확인
            3. 만료되지 않았다면 마지막 접근 시간 업데이트 후 값 반환
            4. 만료되었거나 존재하지 않으면 None 반환

        사용 예시:
            >>> from mcpgateway.cache.resource_cache import ResourceCache
            >>> cache = ResourceCache(max_size=2, ttl=1)
            >>> cache.set('a', 1)
            >>> cache.get('a')
            1
            >>> # 만료 테스트를 위해 매우 짧은 TTL 사용
            >>> short_cache = ResourceCache(max_size=2, ttl=0.1)
            >>> short_cache.set('b', 2)
            >>> short_cache.get('b')
            2
            >>> import time
            >>> time.sleep(0.2)  # TTL(0.1초)보다 오래 대기하여 만료 확인
            >>> short_cache.get('b') is None
            True
        """
        # 1. 캐시에 키가 존재하지 않으면 None 반환
        if key not in self._cache:
            return None

        entry = self._cache[key]
        now = time.time()

        # 2. 만료 시간 확인
        if now > entry.expires_at:
            # 만료된 항목은 캐시에서 제거
            del self._cache[key]
            return None

        # 3. LRU 정책을 위한 마지막 접근 시간 업데이트
        entry.last_access = now
        return entry.value

    def set(self, key: str, value: Any) -> None:
        """
        캐시에 값을 저장.

        Args:
            key: 캐시 키
            value: 캐시에 저장할 값

        동작 과정:
            1. 현재 캐시 크기가 최대 크기를 초과하는지 확인
            2. 초과하면 LRU(Least Recently Used) 정책으로 가장 오래된 항목 제거
            3. 새로운 캐시 엔트리 생성 (현재 시간 + TTL)
            4. 캐시에 키-값 쌍 저장

        사용 예시:
            >>> from mcpgateway.cache.resource_cache import ResourceCache
            >>> cache = ResourceCache(max_size=2, ttl=1)
            >>> cache.set('a', 1)
            >>> cache.get('a')
            1
        """
        now = time.time()

        # 1. 캐시 크기 제한 확인
        if len(self._cache) >= self.max_size:
            # LRU(Least Recently Used) 정책으로 가장 오래된 접근 항목 제거
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
            del self._cache[lru_key]

        # 2. 새로운 캐시 엔트리 생성 및 저장
        self._cache[key] = CacheEntry(value=value, expires_at=now + self.ttl, last_access=now)

    def delete(self, key: str) -> None:
        """
        캐시에서 특정 키의 값을 삭제.

        Args:
            key: 삭제할 캐시 키

        동작 과정:
            1. 캐시에서 지정된 키를 찾아서 제거
            2. 키가 존재하지 않아도 에러 없이 처리 (안전한 삭제)

        사용 예시:
            >>> from mcpgateway.cache.resource_cache import ResourceCache
            >>> cache = ResourceCache()
            >>> cache.set('a', 1)
            >>> cache.delete('a')
            >>> cache.get('a') is None
            True
        """
        # 캐시에서 키를 안전하게 제거 (키가 존재하지 않아도 에러 발생하지 않음)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """
        모든 캐시 항목을 삭제.

        동작 과정:
            1. 내부 캐시 딕셔너리를 완전히 비움
            2. 모든 키-값 쌍이 제거되어 메모리 해제

        사용 예시:
            >>> from mcpgateway.cache.resource_cache import ResourceCache
            >>> cache = ResourceCache()
            >>> cache.set('a', 1)
            >>> cache.clear()
            >>> cache.get('a') is None
            True
        """
        # 모든 캐시 항목을 한 번에 제거하여 메모리 해제
        self._cache.clear()

    async def _cleanup_loop(self) -> None:
        """백그라운드 태스크로 만료된 캐시 항목들을 정리."""
        while True:
            try:
                async with self._lock:
                    now = time.time()
                    # 만료된 항목들의 키 목록 생성
                    expired = [key for key, entry in self._cache.items() if now > entry.expires_at]
                    # 만료된 항목들 제거
                    for key in expired:
                        del self._cache[key]

                    if expired:
                        logger.debug(f"만료된 캐시 항목 {len(expired)}개를 정리했습니다")

            except Exception as e:
                logger.error(f"캐시 정리 오류: {e}")

            await asyncio.sleep(60)  # 1분마다 실행
