# MCP Gateway Utils - 유틸리티 함수 모음 가이드

## 개요

`utils/` 폴더는 MCP Gateway 전반에서 사용되는 공통 유틸리티 함수들을 제공합니다. 이 모듈들은 인증, 데이터 처리, 네트워크 통신, 보안 등 다양한 기능을 지원하며, 코드 중복을 방지하고 일관된 구현을 보장합니다.

## 유틸리티 모음 구조 개요

```
utils/
├── __init__.py                      # 유틸리티 모듈 초기화
├── create_jwt_token.py              # JWT 토큰 생성 및 검증
├── create_slug.py                   # 슬러그 생성 유틸리티
├── db_isready.py                    # 데이터베이스 연결 확인
├── display_name.py                  # 표시 이름 생성
├── error_formatter.py               # 오류 메시지 포맷팅
├── metadata_capture.py              # 메타데이터 캡처
├── metrics_common.py                # 공통 메트릭 계산
├── oauth_encryption.py              # OAuth 토큰 암호화
├── passthrough_headers.py           # 헤더 패스스루 관리
├── redis_isready.py                 # Redis 연결 확인
├── retry_manager.py                 # 재시도 로직 관리
├── security_cookies.py              # 보안 쿠키 관리
├── services_auth.py                 # 서비스 인증 헬퍼
└── verify_credentials.py            # 자격 증명 검증
```

## 주요 유틸리티 상세 설명

### 1. JWT 토큰 관리 (`create_jwt_token.py`)

**역할**: JWT 토큰의 생성, 검증 및 CLI 인터페이스 제공
**주요 기능**:
- JWT 토큰 생성 및 서명
- 토큰 만료 시간 설정
- CLI 도구로의 활용

**핵심 함수**:
```python
def _create_jwt_token(
    data: Dict[str, Any],
    expires_in_minutes: int = DEFAULT_EXP_MINUTES,
    secret: str = DEFAULT_SECRET,
    algorithm: str = DEFAULT_ALGO,
) -> str:
    """JWT 토큰 생성 (동기)"""

async def create_jwt_token(
    data: Dict[str, Any],
    expires_in_minutes: int = DEFAULT_EXP_MINUTES,
    secret: str = DEFAULT_SECRET,
    algorithm: str = DEFAULT_ALGO,
) -> str:
    """JWT 토큰 생성 (비동기 래퍼)"""
```

**사용 예시**:
```bash
# CLI 사용
python -m mcpgateway.utils.create_jwt_token --username admin --exp 60

# 프로그래밍적 사용
from mcpgateway.utils.create_jwt_token import create_jwt_token

token = await create_jwt_token({"username": "admin", "role": "user"})
```

### 2. 재시도 관리자 (`retry_manager.py`)

**역할**: 네트워크 요청의 자동 재시도 및 복원력 제공
**주요 기능**:
- 지수 백오프 재시도 로직
- HTTP 상태 코드 기반 재시도 결정
- 네트워크 오류 자동 처리

**핵심 클래스**:
```python
class ResilientHttpClient:
    def __init__(
        self,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        # 재시도 설정 초기화

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET 요청 with 자동 재시도"""

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST 요청 with 자동 재시도"""
```

**재시도 정책**:
```python
# 재시도 가능한 상태 코드
RETRYABLE_STATUS_CODES = {429, 503, 502, 504, 408}

# 재시도 가능한 예외
RETRYABLE_EXCEPTIONS = (httpx.NetworkError, httpx.TimeoutException)
```

**사용 예시**:
```python
async with ResilientHttpClient() as client:
    try:
        response = await client.get("https://api.example.com/data")
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # Rate limit hit, client will auto-retry
            raise
```

### 3. 슬러그 생성 (`create_slug.py`)

**역할**: URL 친화적인 슬러그 생성
**주요 기능**:
- 텍스트를 URL 안전한 형태로 변환
- 중복 방지 및 정규화

**핵심 함수**:
```python
def slugify(text: str, separator: str = "-") -> str:
    """텍스트를 URL 안전한 슬러그로 변환"""
    # 소문자 변환, 특수문자 제거, 공백을 구분자로 변경
    # 연속된 구분자 제거 및 앞뒤 구분자 제거
```

**사용 예시**:
```python
from mcpgateway.utils.create_slug import slugify

# "Hello World! 123" -> "hello-world-123"
slug = slugify("Hello World! 123")

# 사용자 정의 구분자
slug = slugify("Test Case", separator="_")  # "test_case"
```

### 4. OAuth 암호화 (`oauth_encryption.py`)

**역할**: OAuth 토큰의 안전한 저장 및 검색
**주요 기능**:
- 토큰 암호화/복호화
- 안전한 저장소 관리
- 키 회전 지원

**핵심 기능**:
```python
class OAuthTokenEncryptor:
    def encrypt_token(self, token: str) -> str:
        """OAuth 토큰 암호화"""

    def decrypt_token(self, encrypted_token: str) -> str:
        """OAuth 토큰 복호화"""
```

### 5. 헤더 패스스루 (`passthrough_headers.py`)

**역할**: HTTP 헤더의 선택적 전달 관리
**주요 기능**:
- 보안 헤더 필터링
- 테넌트 및 사용자 정보 전달
- 헤더 검증 및 정제

**핵심 함수**:
```python
def get_passthrough_headers(request: Request) -> Dict[str, str]:
    """안전하게 전달할 수 있는 헤더만 추출"""

def should_passthrough_header(header_name: str) -> bool:
    """헤더가 패스스루될 수 있는지 검증"""
```

### 6. 데이터베이스 연결 확인 (`db_isready.py`)

**역할**: 데이터베이스 연결 상태 모니터링
**주요 기능**:
- 연결 상태 확인
- 헬스 체크 엔드포인트 지원
- 연결 풀 모니터링

**사용 예시**:
```python
from mcpgateway.utils.db_isready import wait_for_db_ready

# 데이터베이스 연결 대기
await wait_for_db_ready(timeout=30)
```

### 7. Redis 연결 확인 (`redis_isready.py`)

**역할**: Redis 연결 상태 모니터링
**주요 기능**:
- Redis 연결 검증
- 클러스터 지원
- 연결 풀 상태 확인

### 8. 표시 이름 생성 (`display_name.py`)

**역할**: 사용자 친화적인 표시 이름 생성
**주요 기능**:
- 기술적 이름을 읽기 쉬운 형태로 변환
- 다국어 지원
- 캐싱을 통한 성능 최적화

**사용 예시**:
```python
from mcpgateway.utils.display_name import generate_display_name

# "get_user_profile" -> "Get User Profile"
display_name = generate_display_name("get_user_profile")
```

### 9. 메타데이터 캡처 (`metadata_capture.py`)

**역할**: 요청 및 응답 메타데이터 수집
**주요 기능**:
- HTTP 요청 정보 캡처
- 성능 메트릭 수집
- 감사 로그 생성

**캡처되는 정보**:
```python
metadata = {
    "request_id": str(uuid.uuid4()),
    "timestamp": datetime.utcnow(),
    "user_agent": request.headers.get("User-Agent"),
    "ip_address": get_client_ip(request),
    "method": request.method,
    "url": str(request.url),
    "response_time": response_time,
    "status_code": response.status_code
}
```

### 10. 공통 메트릭 계산 (`metrics_common.py`)

**역할**: 애플리케이션 메트릭 계산 유틸리티
**주요 기능**:
- 성능 메트릭 집계
- 통계 계산 (평균, 백분위수 등)
- 메트릭 포맷팅

**주요 함수**:
```python
def build_top_performers(
    metrics_data: List[Dict[str, Any]],
    limit: int = 5
) -> List[TopPerformer]:
    """상위 성능자 목록 생성"""

def calculate_percentiles(data: List[float]) -> Dict[str, float]:
    """백분위수 계산 (P50, P95, P99 등)"""
```

### 11. 서비스 인증 (`services_auth.py`)

**역할**: 서비스 간 인증 처리
**주요 기능**:
- 서비스 간 토큰 생성 및 검증
- API 키 관리
- 인증 헤더 처리

**사용 예시**:
```python
from mcpgateway.utils.services_auth import decode_auth, encode_auth

# 인증 헤더 생성
auth_header = encode_auth("service_name", "api_key")

# 인증 헤더 검증
credentials = decode_auth(auth_header)
```

### 12. 보안 쿠키 (`security_cookies.py`)

**역할**: 안전한 HTTP 쿠키 관리
**주요 기능**:
- 보안 쿠키 설정
- CSRF 토큰 관리
- 세션 쿠키 처리

**보안 설정**:
```python
def create_secure_cookie(
    name: str,
    value: str,
    secure: bool = True,
    http_only: bool = True,
    same_site: str = "strict"
) -> str:
    """보안 쿠키 생성"""
```

### 13. 오류 포맷터 (`error_formatter.py`)

**역할**: 표준화된 오류 메시지 포맷팅
**주요 기능**:
- 오류 메시지 정규화
- 사용자 친화적인 메시지 생성
- 로깅용 상세 정보 포함

**사용 예시**:
```python
from mcpgateway.utils.error_formatter import format_error_response

error_response = format_error_response(
    error=ValueError("Invalid input"),
    status_code=400,
    include_traceback=settings.debug
)
```

### 14. 자격 증명 검증 (`verify_credentials.py`)

**역할**: 사용자 자격 증명 검증
**주요 기능**:
- 비밀번호 해싱 및 검증
- 다중 인증 방식 지원
- 보안 정책 적용

## 유틸리티 사용 패턴

### 1. 데코레이터 패턴
```python
from functools import wraps
from mcpgateway.utils.retry_manager import ResilientHttpClient

def with_retry(max_retries: int = 3):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with ResilientHttpClient(max_retries=max_retries) as client:
                # 클라이언트를 함수에 주입
                kwargs['http_client'] = client
                return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 2. 컨텍스트 매니저 패턴
```python
from contextlib import asynccontextmanager
from mcpgateway.utils.create_jwt_token import create_jwt_token

@asynccontextmanager
async def authenticated_session(username: str):
    """인증된 세션 컨텍스트"""
    token = await create_jwt_token({"username": username})
    try:
        yield {"Authorization": f"Bearer {token}"}
    finally:
        # 세션 정리
        pass
```

### 3. 팩토리 패턴
```python
from mcpgateway.utils import (
    create_jwt_token,
    retry_manager,
    oauth_encryption
)

class UtilsFactory:
    @staticmethod
    def create_jwt_manager(secret: str):
        return create_jwt_token.JWTManager(secret)

    @staticmethod
    def create_http_client(**kwargs):
        return retry_manager.ResilientHttpClient(**kwargs)

    @staticmethod
    def create_oauth_encryptor(key: str):
        return oauth_encryption.OAuthTokenEncryptor(key)
```

## 성능 및 안정성 고려사항

### 캐싱 전략
```python
from functools import lru_cache
import asyncio
from typing import Dict, Any

# 동기 함수 캐싱
@lru_cache(maxsize=1000)
def cached_slugify(text: str) -> str:
    return slugify(text)

# 비동기 함수 캐싱
_cache: Dict[str, Any] = {}

async def cached_display_name(name: str) -> str:
    if name in _cache:
        return _cache[name]

    result = await generate_display_name(name)
    _cache[name] = result

    # 캐시 크기 제한
    if len(_cache) > 1000:
        # LRU 방식으로 오래된 항목 제거
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]

    return result
```

### 메모리 관리
```python
import gc
import psutil
from mcpgateway.utils.metrics_common import calculate_memory_usage

def cleanup_resources():
    """리소스 정리 및 메모리 관리"""
    # 사용하지 않는 객체 정리
    gc.collect()

    # 메모리 사용량 모니터링
    memory_info = calculate_memory_usage()
    if memory_info['usage_percent'] > 80:
        # 메모리 정리 로직
        clear_caches()
        gc.collect()
```

## 테스트 및 검증

### 유닛 테스트 패턴
```python
import pytest
from unittest.mock import Mock, patch
from mcpgateway.utils.retry_manager import ResilientHttpClient

@pytest.mark.asyncio
async def test_resilient_client_retry():
    """재시도 로직 테스트"""
    with patch('httpx.AsyncClient') as mock_client:
        # 429 상태 코드를 반환하는 모의 응답
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '1'}

        mock_client.return_value.request.side_effect = [
            httpx.HTTPStatusError("Too Many Requests", response=mock_response),
            Mock(status_code=200, json=lambda: {"success": True})
        ]

        async with ResilientHttpClient(max_retries=2) as client:
            response = await client.get("https://api.example.com")

            # 재시도가 발생했는지 검증
            assert mock_client.return_value.request.call_count == 2
```

### 통합 테스트 패턴
```python
@pytest.mark.asyncio
async def test_jwt_token_integration():
    """JWT 토큰 생성 및 검증 통합 테스트"""
    from mcpgateway.utils.create_jwt_token import create_jwt_token

    # 토큰 생성
    payload = {"username": "test_user", "role": "admin"}
    token = await create_jwt_token(payload, expires_in_minutes=5)

    # 토큰 검증
    import jwt
    decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert decoded["username"] == "test_user"
    assert decoded["role"] == "admin"
    assert "exp" in decoded  # 만료 시간이 포함되었는지 확인
```

## 결론

utils/ 폴더는 MCP Gateway의 핵심 기능을 지원하는 필수적인 유틸리티 모음입니다:

- **재사용성**: 공통 로직을 모듈화하여 코드 중복 방지
- **안정성**: 검증된 알고리즘과 에러 처리로 신뢰성 보장
- **성능**: 캐싱과 최적화로 시스템 성능 향상
- **유지보수성**: 집중화된 로직으로 변경 영향 최소화
- **확장성**: 새로운 유틸리티의 추가가 용이한 구조

이러한 유틸리티들은 게이트웨이의 모든 컴포넌트에서 일관되게 사용되며, 시스템의 전반적인 품질과 안정성을 높이는 데 기여합니다.
