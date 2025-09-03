# MCP Gateway Middleware - 요청 처리 및 보안 미들웨어 가이드

## 개요

`middleware/` 폴더는 FastAPI 애플리케이션의 요청/응답 처리 파이프라인에 개입하여 추가 기능을 제공하는 미들웨어 컴포넌트를 포함합니다. 주로 보안 강화와 요청 처리 최적화를 담당합니다.

## 미들웨어 구조 개요

```
middleware/
├── __init__.py                     # 미들웨어 모듈 초기화
└── security_headers.py             # 보안 헤더 미들웨어
```

## Security Headers 미들웨어 (`security_headers.py`)

**역할**: 모든 HTTP 응답에 보안 헤더를 추가하여 웹 애플리케이션의 보안을 강화
**주요 기능**:
- XSS 공격 방지
- 클릭재킹 공격 방지
- MIME 타입 스니핑 방지
- HTTPS 강제 적용
- 서버 정보 노출 방지

### 구현된 보안 헤더들

#### 1. X-Content-Type-Options
**목적**: MIME 타입 스니핑 공격 방지
```http
X-Content-Type-Options: nosniff
```
- 브라우저가 응답의 MIME 타입을 추측하지 못하게 함
- 설정된 Content-Type 헤더만 신뢰하도록 강제

#### 2. X-Frame-Options
**목적**: 클릭재킹(Clickjacking) 공격 방지
```http
X-Frame-Options: DENY
```
- 다른 사이트의 iframe 내에 페이지가 로드되는 것을 방지
- DENY: 모든 프레이밍 금지
- SAMEORIGIN: 같은 출처만 허용
- ALLOW-FROM uri: 특정 URI만 허용

#### 3. X-XSS-Protection
**목적**: 레거시 XSS 보호 (CSP와 함께 사용)
```http
X-XSS-Protection: 0
```
- 최신 브라우저에서는 CSP(Content Security Policy)를 사용하므로 비활성화
- 구형 브라우저에서는 XSS 필터링을 비활성화

#### 4. X-Download-Options
**목적**: Internet Explorer 다운로드 실행 방지
```http
X-Download-Options: noopen
```
- IE에서 다운로드된 파일의 자동 실행 방지
- 보안 다운로드를 위한 설정

#### 5. Referrer-Policy
**목적**: 리퍼러 정보 전송 제어
```http
Referrer-Policy: strict-origin-when-cross-origin
```
- HTTPS 사이트로의 요청에서만 전체 URL 전송
- 크로스-오리진 요청에서는 오리진 정보만 전송
- 개인정보 보호와 보안의 균형

#### 6. Content-Security-Policy (CSP)
**목적**: XSS 및 코드 인젝션 공격 방지
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' ws: wss: https:; frame-ancestors 'none';
```

**CSP 디렉티브 설명**:
- `default-src 'self'`: 기본적으로 같은 오리진만 허용
- `script-src`: 허용된 스크립트 소스 (CDN 포함)
- `style-src`: 허용된 스타일 소스
- `img-src`: 허용된 이미지 소스
- `font-src`: 허용된 폰트 소스
- `connect-src`: 허용된 연결 소스 (WebSocket 포함)
- `frame-ancestors 'none'`: 모든 프레이밍 금지

#### 7. Strict-Transport-Security (HSTS)
**목적**: HTTPS 연결 강제 적용
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```
- 브라우저가 HTTPS만 사용하도록 강제
- HTTP로의 다운그레이드 공격 방지
- 서브도메인에도 적용

### 민감한 헤더 제거

#### 서버 정보 노출 방지
```python
# 제거되는 헤더들
if "X-Powered-By" in response.headers:
    del response.headers["X-Powered-By"]
if "Server" in response.headers:
    del response.headers["Server"]
```

- `X-Powered-By`: 서버 기술 스택 노출 방지
- `Server`: 서버 버전 정보 노출 방지
- 공격자가 취약점을 악용하는 것을 방지

## 미들웨어 설정 및 구성

### 설정 기반 동적 적용

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 설정에 따라 보안 헤더 적용
        if not settings.security_headers_enabled:
            return response

        # 각 헤더의 개별 설정 확인
        if settings.x_content_type_options_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"

        if settings.x_frame_options:
            response.headers["X-Frame-Options"] = settings.x_frame_options

        # ... 다른 헤더들
```

### 환경별 설정

**개발 환경**:
```python
# settings.py
security_headers_enabled: bool = False  # 개발 시 편의를 위해 비활성화
x_frame_options: str = "SAMEORIGIN"     # 개발 시 iframe 허용
```

**프로덕션 환경**:
```python
# settings.py
security_headers_enabled: bool = True   # 프로덕션에서 필수 활성화
x_frame_options: str = "DENY"          # 프로덕션에서 엄격 적용
hsts_enabled: bool = True              # HTTPS 강제 적용
```

## FastAPI 애플리케이션에 미들웨어 등록

### 미들웨어 등록 순서
```python
from fastapi import FastAPI
from mcpgateway.middleware.security_headers import SecurityHeadersMiddleware

app = FastAPI()

# 보안 미들웨어 등록 (다른 미들웨어들보다 먼저)
app.add_middleware(SecurityHeadersMiddleware)

# CORS 미들웨어 (보안 미들웨어 다음에)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 미들웨어 실행 순서
1. **SecurityHeadersMiddleware**: 요청 처리 전 보안 검증
2. **CORSMiddleware**: 크로스-오리진 요청 처리
3. **AuthenticationMiddleware**: 사용자 인증
4. **LoggingMiddleware**: 요청 로깅
5. **Endpoint Handler**: 실제 비즈니스 로직
6. **Response Processing**: 응답 생성
7. **SecurityHeadersMiddleware**: 응답에 보안 헤더 추가

## 보안 헤더 검증 및 테스트

### 보안 헤더 테스트
```python
import pytest
from fastapi.testclient import TestClient
from mcpgateway.main import app

client = TestClient(app)

def test_security_headers_present():
    """보안 헤더가 올바르게 추가되는지 테스트"""
    response = client.get("/")

    # 필수 보안 헤더 검증
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers

def test_security_headers_disabled_in_dev():
    """개발 환경에서 보안 헤더가 비활성화되는지 테스트"""
    # settings.security_headers_enabled = False로 설정된 상태에서
    response = client.get("/")
    assert "X-Content-Type-Options" not in response.headers
```

### CSP 정책 검증
```python
def test_csp_policy():
    """CSP 정책이 올바르게 구성되는지 테스트"""
    response = client.get("/admin")

    csp = response.headers.get("Content-Security-Policy")
    assert csp is not None

    # 필수 CSP 디렉티브 검증
    assert "default-src 'self'" in csp
    assert "script-src" in csp
    assert "frame-ancestors 'none'" in csp

    # Admin UI를 위한 예외 허용 검증
    assert "https://cdnjs.cloudflare.com" in csp
    assert "https://cdn.tailwindcss.com" in csp
```

## 성능 및 오버헤드 고려사항

### 미들웨어 오버헤드 최소화
```python
# 설정 기반 조건부 실행
if settings.security_headers_enabled:
    # 보안 헤더 추가 로직
    # 설정이 비활성화된 경우 아무런 처리도 하지 않음
```

### 캐시 가능한 헤더들
```python
# 정적 헤더들은 한 번만 계산하여 재사용
_cache = {}

def get_csp_header():
    """CSP 헤더를 캐시하여 성능 최적화"""
    if "csp" not in _cache:
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",
            # ... 다른 디렉티브들
        ]
        _cache["csp"] = "; ".join(csp_directives) + ";"
    return _cache["csp"]
```

## 모니터링 및 로깅

### 보안 이벤트 로깅
```python
async def dispatch(self, request: Request, call_next) -> Response:
    response = await call_next(request)

    # 보안 관련 이벤트 로깅
    if response.status_code >= 400:
        logger.warning(
            "Security event detected",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "user_agent": request.headers.get("User-Agent"),
                "ip": self._get_client_ip(request)
            }
        )

    return response
```

### 메트릭 수집
```python
# 보안 헤더 적용 메트릭
SECURITY_HEADERS_APPLIED = Counter(
    "security_headers_applied_total",
    "Total number of responses with security headers applied"
)

async def dispatch(self, request: Request, call_next) -> Response:
    response = await call_next(request)

    if settings.security_headers_enabled:
        SECURITY_HEADERS_APPLIED.inc()

    return response
```

## 확장 및 커스터마이징

### 사용자 정의 보안 헤더 추가
```python
class CustomSecurityHeadersMiddleware(SecurityHeadersMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await super().dispatch(request, call_next)

        # 추가 보안 헤더
        response.headers["X-Custom-Security"] = "enabled"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"

        return response
```

### 환경별 헤더 설정
```python
def get_security_headers_for_environment():
    """환경에 따른 보안 헤더 설정"""
    if settings.environment == "development":
        return {
            "X-Frame-Options": "SAMEORIGIN",  # 개발 시 iframe 허용
            "Content-Security-Policy": "default-src * 'unsafe-inline'",  # 개발 시 유연한 CSP
        }
    elif settings.environment == "production":
        return {
            "X-Frame-Options": "DENY",  # 프로덕션에서 엄격 적용
            "Strict-Transport-Security": f"max-age={settings.hsts_max_age}; includeSubDomains",
        }
```

## 보안 표준 준수

### OWASP 권장사항 준수
- **X-Frame-Options**: 클릭재킹 방지 (OWASP Top 10 - A05:2021)
- **X-Content-Type-Options**: MIME 스니핑 방지
- **CSP**: XSS 방지 (OWASP Top 10 - A03:2021)
- **HSTS**: 중간자 공격 방지 (OWASP Top 10 - A02:2021)

### CIS 보안 벤치마크
- **5.1**: 서버 헤더 제거
- **5.2**: X-Powered-By 헤더 제거
- **5.3**: 보안 헤더 구현
- **5.4**: CSP 구현

## 결론

middleware/ 폴더의 SecurityHeadersMiddleware는 MCP Gateway의 보안을 강화하는 핵심 컴포넌트입니다:

- **다층적 보안**: XSS, 클릭재킹, MIME 스니핑 등 다양한 공격 방지
- **표준 준수**: OWASP 및 CIS 보안 표준 준수
- **성능 최적화**: 설정 기반 조건부 실행으로 오버헤드 최소화
- **유연성**: 환경별 설정과 확장 가능한 구조
- **모니터링**: 보안 이벤트 로깅과 메트릭 수집

이 미들웨어를 통해 게이트웨이는 프로덕션 환경에서 안전하게 운영될 수 있으며, 다양한 보안 위협으로부터 보호됩니다.
