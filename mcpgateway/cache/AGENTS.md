# MCP Gateway Cache - 캐시 및 세션 관리 시스템 가이드

## 개요

`cache/` 폴더는 MCP Gateway의 성능 최적화와 분산 배포를 지원하는 캐시 시스템을 포함합니다. 리소스 캐시와 세션 레지스트리를 통해 효율적인 데이터 관리와 확장성을 제공합니다.

## 캐시 구조 개요

```bash
cache/
├── __init__.py                      # 캐시 모듈 초기화
├── resource_cache.py               # 리소스 콘텐츠 캐시
└── session_registry.py             # 세션 레지스트리 및 분산 상태
```

## Resource Cache (`resource_cache.py`)

**역할**: MCP 리소스 콘텐츠의 메모리 기반 캐시 관리
**주요 기능**:

- TTL 기반 만료
- 최대 크기 제한 및 LRU 제거
- 스레드 안전한 비동기 작업
- 자동 만료 및 메모리 관리

### 캐시 엔트리 구조

```python
@dataclass
class CacheEntry:
    """캐시 엔트리 데이터 클래스"""
    value: Any          # 캐시된 값
    expires_at: float   # 만료 시간 (Unix timestamp)
    last_access: float  # 마지막 접근 시간
```

### ResourceCache 클래스

#### 초기화 및 설정

```python
class ResourceCache:
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """캐시 초기화

        Args:
            max_size: 최대 캐시 엔트리 수 (기본값: 1000)
            ttl: TTL 초 단위 (기본값: 3600초 = 1시간)
        """
```

#### 주요 메소드들

##### 캐시 조회 및 저장

```python
async def get(self, key: str) -> Optional[Any]:
    """키로 캐시된 값 조회"""
    async with self._lock:
        entry = self._cache.get(key)
        if entry and self._is_expired(entry):
            # 만료된 엔트리 제거
            del self._cache[key]
            return None
        if entry:
            entry.last_access = time.time()
            return entry.value
        return None

async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
    """키-값 쌍을 캐시에 저장"""
    async with self._lock:
        # 최대 크기 초과 시 LRU 제거
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()

        expires_at = time.time() + (ttl or self.ttl)
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=expires_at,
            last_access=time.time()
        )
```

##### 캐시 관리

```python
async def delete(self, key: str) -> bool:
    """특정 키의 캐시 엔트리 삭제"""
    async with self._lock:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

async def clear(self) -> None:
    """모든 캐시 엔트리 삭제"""
    async with self._lock:
        self._cache.clear()

async def cleanup_expired(self) -> int:
    """만료된 엔트리들을 정리하고 제거된 개수 반환"""
    async with self._lock:
        expired_keys = [
            key for key, entry in self._cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)
```

##### 캐시 상태 조회

```python
async def size(self) -> int:
    """현재 캐시된 엔트리 개수 반환"""
    async with self._lock:
        return len(self._cache)

async def keys(self) -> list[str]:
    """모든 캐시 키 목록 반환"""
    async with self._lock:
        return list(self._cache.keys())

async def stats(self) -> Dict[str, Any]:
    """캐시 통계 정보 반환"""
    async with self._lock:
        total_entries = len(self._cache)
        expired_count = sum(1 for entry in self._cache.values() if self._is_expired(entry))

        return {
            "total_entries": total_entries,
            "expired_entries": expired_count,
            "max_size": self.max_size,
            "ttl": self.ttl,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0
        }
```

### LRU (Least Recently Used) 제거 정책

```python
def _evict_lru(self) -> None:
    """가장 오래된 접근 엔트리를 제거"""
    if not self._cache:
        return

    # last_access가 가장 오래된 엔트리 찾기
    oldest_key = min(
        self._cache.keys(),
        key=lambda k: self._cache[k].last_access
    )
    del self._cache[oldest_key]
```

### TTL 만료 검사

```python
def _is_expired(self, entry: CacheEntry) -> bool:
    """캐시 엔트리가 만료되었는지 확인"""
    return time.time() > entry.expires_at
```

## Session Registry (`session_registry.py`)

**역할**: SSE 세션 관리 및 분산 배포 지원
**주요 기능**:

- 다중 워커 프로세스 간 세션 공유
- Redis/SQLAlchemy 백엔드 지원
- 세션 메시지 브로드캐스팅
- 자동 세션 정리

### 지원되는 백엔드 유형

#### 1. 메모리 백엔드 (기본값)

```python
# 단일 프로세스 배포용
reg = SessionRegistry(backend='memory')
```

#### 2. Redis 백엔드

```python
# 다중 워커 분산 배포용
reg = SessionRegistry(backend='redis', redis_url='redis://localhost:6379')
```

#### 3. 데이터베이스 백엔드

```python
# 데이터베이스 기반 분산 배포용
reg = SessionRegistry(backend='database')
```

### SessionRegistry 클래스

#### 세션 관리 메소드들

##### 세션 추가 및 조회

```python
async def add_session(self, session_id: str, transport: SSETransport) -> None:
    """새로운 세션 추가"""
    async with self._lock:
        # 백엔드에 세션 존재 기록
        await self._backend.set_session_exists(session_id, True)
        # 로컬 메모리에 트랜스포트 객체 저장
        self._local_sessions[session_id] = transport

async def get_session(self, session_id: str) -> Optional[SSETransport]:
    """세션 ID로 트랜스포트 객체 조회"""
    # 로컬 세션 우선 확인
    transport = self._local_sessions.get(session_id)
    if transport:
        return transport

    # 백엔드에서 세션 존재 확인
    exists = await self._backend.session_exists(session_id)
    if exists:
        # 다른 워커의 세션임을 표시하는 특수 객체 반환
        return RemoteSessionPlaceholder(session_id)

    return None
```

##### 세션 제거

```python
async def remove_session(self, session_id: str) -> None:
    """세션 제거"""
    async with self._lock:
        # 로컬 세션 제거
        self._local_sessions.pop(session_id, None)
        # 백엔드에서 세션 존재 기록 제거
        await self._backend.set_session_exists(session_id, False)
```

##### 메시지 브로드캐스팅

```python
async def broadcast(self, session_id: str, message: Dict[str, Any]) -> None:
    """특정 세션으로 메시지 브로드캐스팅"""
    transport = self._local_sessions.get(session_id)
    if transport:
        try:
            await transport.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")
            # 전송 실패 시 세션 제거
            await self.remove_session(session_id)
```

### 백엔드 추상화

#### SessionBackend 기본 클래스

```python
class SessionBackend:
    """세션 백엔드 기본 클래스"""

    async def session_exists(self, session_id: str) -> bool:
        """세션이 존재하는지 확인"""
        raise NotImplementedError

    async def set_session_exists(self, session_id: str, exists: bool) -> None:
        """세션 존재 상태 설정"""
        raise NotImplementedError

    async def cleanup_expired_sessions(self) -> int:
        """만료된 세션 정리"""
        raise NotImplementedError
```

#### MemoryBackend 구현

```python
class MemoryBackend(SessionBackend):
    """메모리 기반 백엔드"""

    def __init__(self):
        self._sessions: Dict[str, bool] = {}
        self._lock = asyncio.Lock()

    async def session_exists(self, session_id: str) -> bool:
        async with self._lock:
            return self._sessions.get(session_id, False)

    async def set_session_exists(self, session_id: str, exists: bool) -> None:
        async with self._lock:
            if exists:
                self._sessions[session_id] = True
            else:
                self._sessions.pop(session_id, None)
```

#### RedisBackend 구현

```python
class RedisBackend(SessionBackend):
    """Redis 기반 분산 백엔드"""

    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)
        self._session_prefix = "session:"
        self._ttl = 3600  # 1시간 TTL

    async def session_exists(self, session_id: str) -> bool:
        key = f"{self._session_prefix}{session_id}"
        exists = await self.redis.exists(key)
        if exists:
            # 세션 존재 시 TTL 갱신
            await self.redis.expire(key, self._ttl)
        return bool(exists)

    async def set_session_exists(self, session_id: str, exists: bool) -> None:
        key = f"{self._session_prefix}{session_id}"
        if exists:
            await self.redis.setex(key, self._ttl, "1")
        else:
            await self.redis.delete(key)
```

### 세션 메시지 처리

#### 메시지 큐잉 시스템

```python
async def queue_message(self, session_id: str, message: Dict[str, Any]) -> None:
    """세션으로 보낼 메시지를 큐에 추가"""
    async with self._lock:
        if session_id not in self._message_queues:
            self._message_queues[session_id] = asyncio.Queue()

        await self._message_queues[session_id].put(message)

        # 메시지 처리 태스크 시작
        if session_id not in self._processing_tasks:
            self._processing_tasks[session_id] = asyncio.create_task(
                self._process_message_queue(session_id)
            )
```

#### 메시지 처리 워커

```python
async def _process_message_queue(self, session_id: str) -> None:
    """세션의 메시지 큐를 처리하는 워커 태스크"""
    queue = self._message_queues.get(session_id)
    if not queue:
        return

    try:
        while True:
            try:
                # 큐에서 메시지 가져오기 (타임아웃 1초)
                message = await asyncio.wait_for(queue.get(), timeout=1.0)

                # 세션이 여전히 존재하는지 확인
                transport = self._local_sessions.get(session_id)
                if not transport:
                    break

                # 메시지 전송
                await transport.send_message(message)
                queue.task_done()

            except asyncio.TimeoutError:
                # 큐가 비어있으면 워커 종료
                break
            except Exception as e:
                logger.error(f"Error processing message for session {session_id}: {e}")
                break
    finally:
        # 정리 작업
        self._processing_tasks.pop(session_id, None)
        self._message_queues.pop(session_id, None)
```

## 캐시 사용 예시

### 리소스 캐시 활용

```python
from mcpgateway.cache.resource_cache import ResourceCache

# 캐시 초기화
resource_cache = ResourceCache(max_size=1000, ttl=3600)

# 리소스 콘텐츠 캐싱
async def get_resource_content(resource_uri: str) -> str:
    # 캐시에서 먼저 확인
    cached_content = await resource_cache.get(resource_uri)
    if cached_content:
        return cached_content

    # 캐시에 없으면 원본 소스에서 가져오기
    content = await fetch_resource_from_source(resource_uri)

    # 결과를 캐시에 저장
    await resource_cache.set(resource_uri, content)

    return content
```

### 세션 레지스트리 활용

```python
from mcpgateway.cache.session_registry import SessionRegistry

# 분산 세션 레지스트리 초기화
session_registry = SessionRegistry(backend='redis', redis_url='redis://localhost:6379')

# SSE 세션 관리
async def handle_sse_connection(session_id: str, transport: SSETransport):
    # 세션 등록
    await session_registry.add_session(session_id, transport)

    try:
        # 세션 유지 및 메시지 처리
        while await transport.is_connected():
            # 클라이언트로부터 메시지 수신
            message = await transport.receive_message()

            # 메시지 처리
            response = await process_message(message)

            # 응답 전송
            await session_registry.broadcast(session_id, response)

    finally:
        # 세션 정리
        await session_registry.remove_session(session_id)
```

## 성능 최적화 전략

### 캐시 적중률 모니터링

```python
# 캐시 통계 수집
stats = await resource_cache.stats()
hit_rate = stats['hit_rate']

if hit_rate < 0.5:  # 적중률이 50% 미만이면
    # TTL 증가 또는 캐시 크기 확대 고려
    logger.warning(f"Low cache hit rate: {hit_rate:.2%}")
```

### 메모리 사용량 관리

```python
# 주기적인 만료 엔트리 정리
async def cleanup_task():
    while True:
        await asyncio.sleep(300)  # 5분마다
        removed_count = await resource_cache.cleanup_expired()
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired cache entries")
```

### 분산 캐시 전략

```python
# 다중 레벨 캐싱
class MultiLevelCache:
    def __init__(self):
        self.l1_cache = ResourceCache(max_size=100, ttl=300)   # L1: 빠른 메모리 캐시
        self.l2_cache = ResourceCache(max_size=1000, ttl=3600) # L2: 큰 메모리 캐시
        # L3: Redis 캐시 (필요시)

    async def get(self, key: str):
        # L1 캐시 확인
        value = await self.l1_cache.get(key)
        if value is not None:
            return value

        # L2 캐시 확인
        value = await self.l2_cache.get(key)
        if value is not None:
            # L1에 복사 (다음 요청용)
            await self.l1_cache.set(key, value)
            return value

        return None
```

## 모니터링 및 디버깅

### 캐시 메트릭 수집

```python
from prometheus_client import Counter, Gauge, Histogram

CACHE_HITS = Counter('cache_hits_total', 'Total cache hits')
CACHE_MISSES = Counter('cache_misses_total', 'Total cache misses')
CACHE_SIZE = Gauge('cache_size', 'Current cache size')
CACHE_OPERATION_TIME = Histogram('cache_operation_duration', 'Cache operation duration')

async def monitored_get(self, key: str):
    with CACHE_OPERATION_TIME.time():
        value = await self.get(key)
        if value is not None:
            CACHE_HITS.inc()
        else:
            CACHE_MISSES.inc()
        CACHE_SIZE.set(await self.size())
        return value
```

### 세션 상태 모니터링

```python
async def get_session_stats(self) -> Dict[str, Any]:
    """세션 레지스트리 통계"""
    return {
        "local_sessions": len(self._local_sessions),
        "backend_sessions": await self._backend.get_session_count(),
        "processing_tasks": len(self._processing_tasks),
        "message_queues": len(self._message_queues),
    }
```

## 결론

cache/ 폴더의 컴포넌트들은 MCP Gateway의 성능과 확장성을 결정짓는 핵심 요소입니다:

- **ResourceCache**: 빠른 메모리 기반 캐싱으로 I/O 비용 절감
- **SessionRegistry**: 분산 환경에서의 세션 관리로 확장성 보장
- **다중 백엔드 지원**: 환경에 따른 최적의 저장소 선택
- **비동기 처리**: 블로킹 없는 고성능 캐시 작업
- **모니터링**: 캐시 효율성과 상태 추적

이러한 캐시 시스템을 통해 게이트웨이는 고부하 상황에서도 안정적인 성능을 유지하고, 분산 배포 시에도 일관된 사용자 경험을 제공할 수 있습니다.
