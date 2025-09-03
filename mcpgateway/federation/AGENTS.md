# MCP Gateway Federation - 게이트웨이 페데레이션 시스템 가이드

## 개요

`federation/` 폴더는 MCP Gateway의 분산 배포를 지원하는 페데레이션 기능을 포함합니다. 여러 게이트웨이 간의 자동 검색, 연결, 그리고 요청 라우팅을 통해 확장성과 고가용성을 제공합니다.

## 페데레이션 구조 개요

```bash
federation/
├── __init__.py                     # 페데레이션 모듈 초기화
├── discovery.py                    # 피어 게이트웨이 자동 검색
└── forward.py                      # 요청 포워딩 및 라우팅
```

## Discovery Service (`discovery.py`)

**역할**: 네트워크 상의 다른 MCP 게이트웨이를 자동으로 검색하고 연결
**주요 기능**:
- DNS-SD/mDNS 서비스 검색
- 정적 피어 설정
- 피어 정보 교환
- 헬스 체크 및 모니터링

### 지원되는 검색 메커니즘

#### 1. DNS-SD (DNS Service Discovery)
```python
# Zeroconf를 사용한 mDNS 검색
from zeroconf import ServiceInfo, ServiceBrowser

class DNSSDdiscovery:
    """DNS-SD를 통한 서비스 검색"""

    def __init__(self):
        self.zeroconf = AsyncZeroconf()
        self.service_type = "_mcp-gateway._tcp.local."
        self.services = {}

    async def start_discovery(self):
        """서비스 검색 시작"""
        browser = AsyncServiceBrowser(
            self.zeroconf,
            self.service_type,
            handlers=[self._on_service_state_change]
        )

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        """서비스 상태 변경 처리"""
        if state_change == ServiceStateChange.Added:
            # 새 게이트웨이 발견
            self._add_peer_from_dns(name)
        elif state_change == ServiceStateChange.Removed:
            # 게이트웨이 사라짐
            self._remove_peer_from_dns(name)
```

#### 2. 정적 피어 설정
```python
# 수동으로 등록된 피어들
static_peers = [
    "http://gateway1.company.com:4444",
    "http://gateway2.company.com:4444",
    "https://backup-gateway.company.com:4444"
]

async def add_static_peers(self):
    """정적 피어들 등록"""
    for url in static_peers:
        await self.add_peer(url, "static")
```

#### 3. 피어 교환 프로토콜
```python
async def exchange_peers(self, peer_url: str):
    """다른 피어와 피어 목록 교환"""
    try:
        # 피어의 피어 목록 요청
        response = await self._http_client.get(f"{peer_url}/federation/peers")

        # 새 피어들 추가
        for peer_info in response.json():
            if peer_info["url"] not in self._discovered_peers:
                await self.add_peer(peer_info["url"], "exchanged")

    except Exception as e:
        logger.warning(f"Failed to exchange peers with {peer_url}: {e}")
```

### DiscoveredPeer 데이터 구조

```python
@dataclass
class DiscoveredPeer:
    """발견된 피어 게이트웨이 정보"""

    url: str                          # 게이트웨이 URL
    name: str                         # 게이트웨이 이름
    protocol_version: str            # 지원 프로토콜 버전
    capabilities: Optional[Dict]     # 게이트웨이 기능 정보
    discovered_at: datetime          # 발견 시각
    last_seen: datetime              # 마지막 응답 시각
    source: str                      # 발견 출처 (dns, static, manual, exchanged)

    @property
    def is_alive(self) -> bool:
        """게이트웨이가 살아있는지 확인"""
        return (datetime.now(timezone.utc) - self.last_seen) < timedelta(minutes=5)

    @property
    def response_time(self) -> float:
        """평균 응답 시간 (초)"""
        # 최근 응답 시간들의 평균 계산
        return self._calculate_average_response_time()
```

### 헬스 체크 및 모니터링

#### 피어 상태 모니터링

```python
async def monitor_peers(self):
    """모든 피어의 상태 모니터링"""
    while self._running:
        try:
            for peer in self._discovered_peers.values():
                await self._check_peer_health(peer)

            # 30초마다 체크
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Error in peer monitoring: {e}")

async def _check_peer_health(self, peer: DiscoveredPeer):
    """개별 피어 헬스 체크"""
    try:
        start_time = time.time()

        # 헬스 체크 엔드포인트 호출
        response = await self._http_client.get(
            f"{peer.url}/health",
            timeout=5.0
        )

        response_time = time.time() - start_time

        if response.status_code == 200:
            peer.last_seen = datetime.now(timezone.utc)
            peer._record_response_time(response_time)
            peer.status = "healthy"
        else:
            peer.status = "unhealthy"

    except Exception as e:
        peer.status = "unreachable"
        logger.warning(f"Health check failed for {peer.url}: {e}")
```

### 피어 검색 워크플로우

```python
async def discover_peers(self):
    """피어 검색 프로세스 실행"""

    # 1. DNS-SD 검색 시작
    await self._start_dns_discovery()

    # 2. 정적 피어들 추가
    await self._add_static_peers()

    # 3. 기존 피어들과 정보 교환
    await self._exchange_peer_info()

    # 4. 검색된 피어들 검증
    await self._validate_discovered_peers()

async def _validate_discovered_peers(self):
    """발견된 피어들의 유효성 검증"""
    valid_peers = []

    for peer in self._discovered_peers.values():
        if await self._validate_peer(peer):
            valid_peers.append(peer)
        else:
            logger.warning(f"Invalid peer removed: {peer.url}")

    self._discovered_peers = {p.url: p for p in valid_peers}
```

## Forwarding Service (`forward.py`)

**역할**: 검색된 피어 게이트웨이로 요청을 라우팅하고 응답을 처리
**주요 기능**:
- 요청 라우팅 및 로드 밸런싱
- 응답 집계 및 변환
- 에러 처리 및 재시도 로직
- 요청/응답 변환

### ForwardingService 클래스

#### 초기화 및 설정

```python
class ForwardingService:
    """게이트웨이 간 요청 포워딩 서비스"""

    def __init__(self):
        # HTTP 클라이언트 설정
        self._http_client = httpx.AsyncClient(
            timeout=settings.federation_timeout,
            verify=not settings.skip_ssl_verify
        )

        # 요청 추적
        self._active_requests = {}  # 활성 요청 추적
        self._request_history = {}  # 요청 히스토리
        self._gateway_tools = {}    # 게이트웨이별 도구 캐시
```

### 요청 라우팅 로직

#### 최적 게이트웨이 선택

```python
async def select_gateway(self, tool_name: str, db: Session) -> Optional[str]:
    """요청을 처리할 최적 게이트웨이 선택

    Args:
        tool_name: 요청할 도구 이름
        db: 데이터베이스 세션

    Returns:
        선택된 게이트웨이 URL 또는 None
    """
    # 1. 로컬 게이트웨이 우선 확인
    local_gateway = await self._find_local_gateway(tool_name, db)
    if local_gateway:
        return local_gateway

    # 2. 사용 가능한 피어 게이트웨이들 조회
    available_peers = await self._discovery_service.get_available_peers()

    # 3. 각 게이트웨이의 도구 보유 상태 확인
    candidates = []
    for peer in available_peers:
        if await self._peer_has_tool(peer, tool_name):
            candidates.append(peer)

    if not candidates:
        return None

    # 4. 로드 밸런싱 적용
    return await self._select_best_gateway(candidates, tool_name)
```

#### 로드 밸런싱 전략

```python
async def _select_best_gateway(self, candidates: List[str], tool_name: str) -> str:
    """후보 게이트웨이 중 최적 선택"""

    # 라운드-로빈
    if self._load_balancing_strategy == "round_robin":
        return self._round_robin_select(candidates)

    # 최소 응답 시간
    elif self._load_balancing_strategy == "response_time":
        return await self._select_by_response_time(candidates)

    # 랜덤 선택
    elif self._load_balancing_strategy == "random":
        return random.choice(candidates)

    # 가중치 기반 (기본)
    else:
        return await self._weighted_selection(candidates, tool_name)
```

### 요청 포워딩 구현

#### 도구 호출 포워딩

```python
async def forward_tool_call(
    self,
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
    gateway_url: Optional[str] = None
) -> Dict[str, Any]:
    """도구 호출을 적절한 게이트웨이로 포워딩

    Args:
        db: 데이터베이스 세션
        tool_name: 호출할 도구 이름
        arguments: 도구 인자들
        gateway_url: 특정 게이트웨이 지정 (선택적)

    Returns:
        도구 실행 결과

    Raises:
        ForwardingError: 포워딩 실패 시
    """
    try:
        # 게이트웨이 선택
        if not gateway_url:
            gateway_url = await self.select_gateway(tool_name, db)

        if not gateway_url:
            raise ForwardingError(f"No gateway available for tool: {tool_name}")

        # 요청 ID 생성
        request_id = self._generate_request_id()

        # 요청 추적 시작
        self._active_requests[request_id] = {
            "tool_name": tool_name,
            "gateway_url": gateway_url,
            "start_time": time.time()
        }

        # 실제 포워딩 실행
        result = await self._execute_forwarding(
            gateway_url, tool_name, arguments, request_id
        )

        # 요청 추적 완료
        self._complete_request(request_id, result)

        return result

    except Exception as e:
        # 에러 로깅 및 추적
        self._handle_forwarding_error(request_id, e)
        raise ForwardingError(f"Tool forwarding failed: {str(e)}")
```

#### 실제 포워딩 실행

```python
async def _execute_forwarding(
    self,
    gateway_url: str,
    tool_name: str,
    arguments: Dict[str, Any],
    request_id: str
) -> Dict[str, Any]:
    """실제 HTTP 요청 포워딩"""

    # MCP 도구 호출 요청 구성
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": request_id
    }

    # HTTP 요청 실행
    response = await self._http_client.post(
        f"{gateway_url}/jsonrpc",
        json=request_payload,
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-By": settings.gateway_name,
            "X-Request-ID": request_id
        }
    )

    if response.status_code != 200:
        raise ForwardingError(
            f"Gateway returned status {response.status_code}: {response.text}"
        )

    result = response.json()

    # MCP 응답 검증
    if "error" in result:
        raise ForwardingError(f"Tool execution error: {result['error']}")

    return result.get("result", {})
```

### 응답 집계 및 변환

#### 배치 요청 처리

```python
async def forward_batch_request(
    self,
    db: Session,
    requests: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """여러 요청을 배치로 포워딩"""

    # 요청들을 게이트웨이별로 그룹화
    gateway_requests = await self._group_requests_by_gateway(requests, db)

    # 각 게이트웨이로 배치 요청
    responses = []
    for gateway_url, batch in gateway_requests.items():
        try:
            batch_response = await self._execute_batch_forwarding(
                gateway_url, batch
            )
            responses.extend(batch_response)

        except Exception as e:
            # 배치 실패 시 개별 요청으로 폴백
            logger.warning(f"Batch forwarding failed, falling back to individual: {e}")
            individual_responses = await self._forward_individual_requests(
                db, batch
            )
            responses.extend(individual_responses)

    return responses
```

### 에러 처리 및 재시도

#### 재시도 로직

```python
async def _execute_with_retry(
    self,
    gateway_url: str,
    request_payload: Dict,
    max_retries: int = 3
) -> Dict:
    """재시도 로직을 포함한 요청 실행"""

    last_error = None

    for attempt in range(max_retries):
        try:
            response = await self._http_client.post(
                f"{gateway_url}/jsonrpc",
                json=request_payload,
                timeout=self._timeout
            )

            return response.json()

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = e

            if attempt < max_retries - 1:
                # 지수 백오프: 1초, 2초, 4초...
                delay = 2 ** attempt
                logger.info(f"Request failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)

        except Exception as e:
            # 재시도하지 않는 에러
            raise ForwardingError(f"Non-retryable error: {str(e)}")

    # 모든 재시도 실패
    raise ForwardingError(f"All retry attempts failed: {str(last_error)}")
```

#### 게이트웨이 장애 조치

```python
async def _handle_gateway_failure(self, gateway_url: str, error: Exception):
    """게이트웨이 장애 처리"""

    # 장애 카운터 증가
    self._gateway_failures[gateway_url] = self._gateway_failures.get(gateway_url, 0) + 1

    # 일시적 장애로 표시
    await self._discovery_service.mark_gateway_unhealthy(gateway_url)

    # 장애 임계값 초과 시 제거 고려
    if self._gateway_failures[gateway_url] >= self._failure_threshold:
        logger.warning(f"Gateway {gateway_url} exceeded failure threshold, considering removal")
        await self._consider_gateway_removal(gateway_url)

    # 다른 게이트웨이로 요청 재라우팅 시도
    await self._reroute_active_requests(gateway_url)
```

### 캐시 및 최적화

#### 게이트웨이 도구 캐시

```python
async def _cache_gateway_tools(self, gateway_url: str):
    """게이트웨이의 도구 목록 캐시"""

    try:
        # 도구 목록 요청
        response = await self._http_client.post(
            f"{gateway_url}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "cache_tools"
            }
        )

        if response.status_code == 200:
            result = response.json()
            tools = result.get("result", {}).get("tools", [])

            # 캐시 저장
            self._gateway_tools[gateway_url] = {
                "tools": [tool["name"] for tool in tools],
                "cached_at": time.time(),
                "ttl": 300  # 5분 TTL
            }

    except Exception as e:
        logger.error(f"Failed to cache tools for {gateway_url}: {e}")

async def _peer_has_tool(self, gateway_url: str, tool_name: str) -> bool:
    """게이트웨이가 특정 도구를 가지고 있는지 확인"""

    # 캐시 확인
    cache = self._gateway_tools.get(gateway_url)
    if cache and (time.time() - cache["cached_at"]) < cache["ttl"]:
        return tool_name in cache["tools"]

    # 캐시 만료 또는 없음 - 새로 조회
    await self._cache_gateway_tools(gateway_url)

    # 다시 확인
    cache = self._gateway_tools.get(gateway_url, {})
    return tool_name in cache.get("tools", [])
```

### 모니터링 및 메트릭

#### 포워딩 메트릭 수집

```python
class ForwardingMetrics:
    """포워딩 관련 메트릭 수집"""

    def __init__(self):
        self.requests_forwarded = 0
        self.requests_failed = 0
        self.response_times = []
        self.gateway_usage = {}

    def record_forwarding(self, gateway_url: str, response_time: float, success: bool):
        """포워딩 결과 기록"""
        self.requests_forwarded += 1

        if not success:
            self.requests_failed += 1

        self.response_times.append(response_time)
        self.gateway_usage[gateway_url] = self.gateway_usage.get(gateway_url, 0) + 1

        # 오래된 응답 시간 정리 (최근 1000개만 유지)
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]

    def get_stats(self) -> Dict[str, Any]:
        """포워딩 통계 반환"""
        total_requests = self.requests_forwarded
        success_rate = (total_requests - self.requests_failed) / total_requests if total_requests > 0 else 0

        return {
            "total_forwarded": total_requests,
            "success_rate": success_rate,
            "average_response_time": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "gateway_usage": self.gateway_usage,
            "active_requests": len(self._active_requests)
        }
```

## 페데레이션 사용 예시

### 기본 피어 검색

```python
from mcpgateway.federation.discovery import DiscoveryService

# 검색 서비스 초기화
discovery = DiscoveryService()

# 검색 시작
await discovery.start()

# 수동 피어 추가
await discovery.add_peer("http://gateway2.company.com:4444", "manual")

# 검색된 피어 조회
peers = discovery.get_discovered_peers()
for peer in peers:
    print(f"Found peer: {peer.url} (source: {peer.source})")

# 검색 중지
await discovery.stop()
```

### 요청 포워딩

```python
from mcpgateway.federation.forward import ForwardingService

# 포워딩 서비스 초기화
forwarding = ForwardingService()

# 도구 호출 포워딩
try:
    result = await forwarding.forward_tool_call(
        db_session,
        "weather_forecast",
        {"location": "Seoul", "days": 3}
    )
    print(f"Weather forecast: {result}")

except ForwardingError as e:
    print(f"Forwarding failed: {e}")
```

### 고급 라우팅

```python
# 특정 게이트웨이로 강제 라우팅
result = await forwarding.forward_tool_call(
    db_session,
    "special_tool",
    {"param": "value"},
    gateway_url="http://special-gateway.company.com:4444"
)

# 배치 요청 포워딩
batch_requests = [
    {"method": "tools/call", "params": {"name": "tool1", "arguments": {}}},
    {"method": "tools/call", "params": {"name": "tool2", "arguments": {}}},
]

batch_results = await forwarding.forward_batch_request(db_session, batch_requests)
```

## 설정 및 구성

### 페데레이션 설정 예시

```python
# settings.py
# 검색 설정
federation_enabled: bool = True
discovery_methods: List[str] = ["dns_sd", "static", "exchange"]

# 포워딩 설정
federation_timeout: float = 30.0  # 요청 타임아웃 (초)
load_balancing_strategy: str = "weighted"  # 로드 밸런싱 전략
max_retry_attempts: int = 3  # 최대 재시도 횟수

# 피어 설정
static_peers: List[str] = [
    "http://gateway1.company.com:4444",
    "http://gateway2.company.com:4444",
]

# 보안 설정
skip_ssl_verify: bool = False  # SSL 검증 생략 여부
federation_auth_token: str = "your-secret-token"  # 피어 간 인증 토큰
```

## 결론

federation/ 폴더의 컴포넌트들은 MCP Gateway의 분산 배포를 가능하게 하는 핵심 기능입니다:

- **자동 검색**: mDNS와 피어 교환을 통한 게이트웨이 자동 발견
- **지능적 라우팅**: 로드 밸런싱과 장애 조치를 통한 최적 요청 분배
- **강력한 에러 처리**: 재시도 로직과 폴백 메커니즘
- **성능 최적화**: 캐시와 배치 처리를 통한 효율성 향상
- **모니터링**: 포괄적인 메트릭 수집 및 상태 추적

이러한 페데레이션 시스템을 통해 게이트웨이는 단일 장애점 없이 확장 가능하고, 고가용성의 분산 시스템을 구축할 수 있습니다.
