# MCP Gateway Routers - API 엔드포인트 관리 가이드

## 개요

`routers/` 폴더는 MCP Gateway의 API 엔드포인트를 정의하고 관리합니다. FastAPI 라우터를 사용하여 RESTful API와 특수 목적의 엔드포인트를 제공하며, 인증, 검증, 로깅 등의 미들웨어와 통합됩니다.

## 라우터 구조 개요

```bash
routers/
├── __init__.py                 # 라우터 모듈 초기화
├── oauth_router.py             # OAuth 2.0 인증 플로우
├── reverse_proxy.py            # 역방향 프록시 및 WebSocket
└── well_known.py               # 표준 웹 리소스 (robots.txt, security.txt 등)
```

## OAuth 라우터 (`oauth_router.py`)

**역할**: OAuth 2.0 인증 플로우 및 토큰 관리를 위한 API 엔드포인트 제공
**주요 기능**:
- OAuth 인증 플로우 시작
- 콜백 처리 및 토큰 교환
- 토큰 상태 조회 및 관리

### 주요 엔드포인트

#### `GET /oauth/authorize/{gateway_id}`
**목적**: OAuth 인증 플로우 시작
**기능**:
- 게이트웨이 OAuth 설정 검증
- 인증 URL 생성 및 리다이렉트
- 상태 파라미터를 통한 CSRF 보호

**요청 예시**:
```http
GET /oauth/authorize/gateway-123
```

**응답**: OAuth 제공자로의 리다이렉트

#### `GET /oauth/callback`
**목적**: OAuth 제공자로부터의 콜백 처리
**기능**:
- 인증 코드 검증 및 토큰 교환
- 토큰 저장 및 세션 관리
- 성공/실패 상태 표시

**쿼리 파라미터**:
- `code`: OAuth 제공자가 제공한 인증 코드
- `state`: CSRF 보호를 위한 상태 토큰

**응답**: HTML 상태 페이지

#### `GET /oauth/status/{gateway_id}`
**목적**: OAuth 인증 상태 조회
**기능**:
- 토큰 유효성 검증
- 만료 시간 확인
- 재인증 필요 여부 판단

#### `POST /oauth/fetch-tools/{gateway_id}`
**목적**: OAuth 인증 후 도구 정보 가져오기
**기능**:
- 저장된 토큰을 사용하여 API 호출
- 도구 메타데이터 동기화
- 캐시 업데이트

## 역방향 프록시 라우터 (`reverse_proxy.py`)

**역할**: 외부 MCP 서버와의 WebSocket 및 HTTP 프록시 연결 관리
**주요 기능**:
- STDIO 프로세스 관리
- WebSocket 터널링
- 세션 관리 및 메시지 라우팅

### 주요 엔드포인트

#### `WebSocket /ws`
**목적**: 양방향 WebSocket 통신 채널
**기능**:
- 실시간 메시지 교환
- 세션 기반 연결 관리
- 자동 재연결 및 오류 처리

**WebSocket 메시지 형식**:
```json
{
  "type": "mcp_message",
  "session_id": "session-123",
  "payload": {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {...}
  }
}
```

#### `GET /sessions`
**목적**: 활성 세션 목록 조회
**기능**:
- 현재 연결된 세션 정보 제공
- 세션 상태 및 메타데이터 표시
- 관리 인터페이스 지원

#### `DELETE /sessions/{session_id}`
**목적**: 특정 세션 종료
**기능**:
- 세션 정리 및 리소스 해제
- 연결된 프로세스 종료
- 세션 상태 업데이트

#### `POST /sessions/{session_id}/request`
**목적**: 세션으로 메시지 전송
**기능**:
- JSON-RPC 메시지 라우팅
- 응답 대기 및 타임아웃 처리
- 오류 처리 및 로깅

#### `GET /sse/{session_id}`
**목적**: Server-Sent Events 스트림
**기능**:
- 서버에서 클라이언트로의 단방향 스트리밍
- 실시간 상태 업데이트
- 연결 유지 및 재연결 지원

## Well-Known 라우터 (`well_known.py`)

**역할**: 표준 웹 리소스 및 보안 정보를 제공하는 엔드포인트
**주요 기능**:
- robots.txt 및 security.txt 제공
- 캐시 제어 및 헤더 관리
- 사용자 정의 well-known 파일 지원

### 주요 엔드포인트

#### `GET /.well-known/{filename}`
**목적**: 표준 웹 리소스 제공
**지원 파일**:
- `robots.txt`: 크롤러 접근 제어
- `security.txt`: 보안 연락처 정보
- 사용자 정의 파일

**캐시 제어**:
```http
Cache-Control: public, max-age=3600
ETag: "version-1"
```

#### `GET /admin/well-known`
**목적**: 관리 인터페이스용 well-known 파일 상태 조회
**기능**:
- 구성된 파일 목록 표시
- 캐시 상태 및 유효성 확인
- 관리용 메타데이터 제공

## 라우터 아키텍처 패턴

### 1. 의존성 주입 패턴
```python
from fastapi import Depends
from sqlalchemy.orm import Session

async def endpoint_handler(
    gateway_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    # 데이터베이스 세션과 사용자 인증 자동 주입
```

### 2. 미들웨어 통합 패턴
```python
from fastapi.middleware.cors import CORSMiddleware
from mcpgateway.middleware.security_headers import SecurityHeadersMiddleware

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 보안 헤더 추가
app.add_middleware(SecurityHeadersMiddleware)
```

### 3. 에러 처리 패턴
```python
from fastapi import HTTPException
from mcpgateway.utils.error_formatter import format_error_response

try:
    result = await process_request(request)
    return result
except ValueError as e:
    raise HTTPException(
        status_code=400,
        detail=format_error_response(e, include_traceback=settings.debug)
    )
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

## 보안 및 인증

### JWT 토큰 인증
```python
from mcpgateway.utils.services_auth import require_auth

@router.get("/protected-endpoint")
async def protected_endpoint(
    current_user: str = Depends(require_auth)
):
    # 인증된 사용자만 접근 가능
    return {"user": current_user}
```

### API 키 인증
```python
from mcpgateway.utils.verify_credentials import verify_api_key

@router.post("/api-endpoint")
async def api_endpoint(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    # API 키 검증 후 처리
    return {"status": "success"}
```

### CORS 및 헤더 관리
```python
@router.options("/{path:path}")
async def options_handler():
    """CORS preflight 요청 처리"""
    return {"Allow": "GET, POST, PUT, DELETE, OPTIONS"}
```

## 응답 형식 및 직렬화

### JSON 응답 표준화
```python
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class StandardResponse(BaseModel):
    success: bool
    data: Any = None
    error: str = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

@router.get("/standard-endpoint")
async def standard_endpoint() -> StandardResponse:
    return StandardResponse(
        success=True,
        data={"result": "success"}
    )
```

### 파일 응답 처리
```python
from fastapi.responses import FileResponse, StreamingResponse

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = get_file_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )
```

## 로깅 및 모니터링

### 요청 로깅
```python
import logging
from mcpgateway.utils.metadata_capture import capture_request_metadata

logger = logging.getLogger(__name__)

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def log_request(request: Request, call_next):
    # 요청 시작 로깅
    metadata = capture_request_metadata(request)
    logger.info(f"Request started: {metadata}")

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # 응답 로깅
    logger.info(f"Request completed: {metadata}, duration={duration:.2f}s, status={response.status_code}")

    return response
```

### 메트릭 수집
```python
from mcpgateway.utils.metrics_common import record_api_metrics

@router.get("/api-endpoint")
async def monitored_endpoint():
    with record_api_metrics("endpoint_name"):
        result = await process_request()
        return result
```

## 라우터 등록 및 구성

### 메인 애플리케이션에 라우터 등록
```python
from fastapi import FastAPI
from mcpgateway.routers import oauth_router, reverse_proxy, well_known

app = FastAPI()

# 라우터 등록
app.include_router(oauth_router.oauth_router)
app.include_router(reverse_proxy.router)
app.include_router(well_known.router)

# 추가 라우터들 (main.py에서)
app.include_router(tool_router, prefix="/tools", tags=["tools"])
app.include_router(resource_router, prefix="/resources", tags=["resources"])
app.include_router(prompt_router, prefix="/prompts", tags=["prompts"])
```

### 라우터 설정 커스터마이징
```python
from fastapi import APIRouter

# 커스텀 라우터 설정
custom_router = APIRouter(
    prefix="/api/v1",
    tags=["api"],
    dependencies=[Depends(get_current_user)],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"}
    }
)
```

## 테스트 및 검증

### 라우터 단위 테스트
```python
import pytest
from fastapi.testclient import TestClient
from mcpgateway.main import app

client = TestClient(app)

def test_oauth_callback():
    response = client.get("/oauth/callback?code=test_code&state=test_state")
    assert response.status_code == 200
    assert "OAuth" in response.text

@pytest.mark.asyncio
async def test_websocket_connection():
    from mcpgateway.transports.websocket_transport import WebSocketTransport

    # WebSocket 연결 테스트
    async with client.websocket_connect("/ws") as websocket:
        await websocket.send_json({"type": "test"})
        response = await websocket.receive_json()
        assert response["type"] == "ack"
```

### 통합 테스트
```python
@pytest.mark.asyncio
async def test_oauth_flow_integration():
    # OAuth 플로우 전체 테스트
    # 1. 인증 시작
    response = client.get("/oauth/authorize/gateway-123")
    assert response.status_code == 302  # Redirect to OAuth provider

    # 2. 콜백 처리 (모의)
    callback_response = client.get("/oauth/callback?code=mock_code&state=gateway-123_mock")
    assert callback_response.status_code == 200

    # 3. 상태 확인
    status_response = client.get("/oauth/status/gateway-123")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["authenticated"] is True
```

## 결론

routers/ 폴더는 MCP Gateway의 API 인터페이스를 정의하며 다음과 같은 특징을 가집니다:

- **RESTful 설계**: 표준 HTTP 메서드와 상태 코드를 따름
- **보안 강화**: 인증, 검증, CORS 지원
- **확장성**: 모듈화된 라우터 구조로 새로운 엔드포인트 추가 용이
- **모니터링**: 요청 로깅과 메트릭 수집으로 운영 가시성 제공
- **테스트 용이성**: FastAPI의 테스트 클라이언트로 손쉬운 테스트 가능

이러한 라우터 구조는 게이트웨이의 모든 기능을 외부에 노출시키며, 안전하고 효율적인 API 통신을 보장합니다.

## 탐색

- **⬆️ mcpgateway**: [../AGENTS.md](../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../AGENTS.md](../../AGENTS.md)
