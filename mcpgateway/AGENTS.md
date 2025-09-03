# MCP Gateway Core Package - 상세 구조 및 아키텍처 가이드

## 개요

`mcpgateway/` 패키지는 **Model Context Protocol (MCP) Gateway**의 핵심 애플리케이션 패키지입니다. FastAPI 기반의 고성능 게이트웨이로, MCP 서버와 클라이언트 간의 통신을 중계하고 관리하는 역할을 담당합니다.

이 문서는 PROJECT_ROOT의 AGENTS.md와 달리, mcpgateway/ 패키지의 내부 구조와 각 컴포넌트의 역할을 상세히 설명합니다.

```text
mcpgateway/
├── __init__.py              # 패키지 초기화 및 버전 정보
├── main.py                  # FastAPI 애플리케이션 엔트리포인트
├── config.py                # Pydantic 설정 관리
├── db.py                    # SQLAlchemy 모델 및 데이터베이스 연결
├── models.py                # MCP 프로토콜 모델 정의
├── schemas.py               # API 스키마 정의 (Pydantic)
├── admin.py                 # 관리자 UI 및 API 엔드포인트
├── bootstrap_db.py          # 데이터베이스 초기화 스크립트
├── cli.py                   # 명령줄 인터페이스
├── cli_export_import.py     # 내보내기/가져오기 CLI 도구
├── observability.py         # OpenTelemetry 모니터링 설정
├── translate.py             # 프로토콜 변환 유틸리티
├── validators.py            # 입력 검증 유틸리티
├── wrapper.py               # MCP 서버 래핑 유틸리티
├── reverse_proxy.py         # 역방향 프록시 구현
├── alembic/                 # 데이터베이스 마이그레이션
├── cache/                   # 캐시 시스템
├── federation/              # 게이트웨이 페데레이션
├── handlers/                # 요청 핸들러
├── middleware/              # FastAPI 미들웨어
├── plugins/                 # 플러그인 프레임워크
├── routers/                 # API 라우터
├── services/                # 비즈니스 로직 서비스
├── static/                  # 정적 파일 (CSS, JS)
├── templates/               # HTML 템플릿
├── transports/              # 전송 계층 구현
├── utils/                   # 유틸리티 함수들
└── validation/              # 검증 모듈
```

## 패키지 구조 개요

```
mcpgateway/
├── __init__.py              # 패키지 초기화 및 버전 정보
├── main.py                  # FastAPI 애플리케이션 엔트리포인트
├── config.py                # Pydantic 설정 관리
├── db.py                    # SQLAlchemy 모델 및 데이터베이스 연결
├── models.py                # MCP 프로토콜 모델 정의
├── schemas.py               # API 스키마 정의 (Pydantic)
├── admin.py                 # 관리자 UI 및 API 엔드포인트
├── bootstrap_db.py          # 데이터베이스 초기화 스크립트
├── cli.py                   # 명령줄 인터페이스
├── cli_export_import.py     # 내보내기/가져오기 CLI 도구
├── observability.py         # OpenTelemetry 모니터링 설정
├── translate.py             # 프로토콜 변환 유틸리티
├── validators.py            # 입력 검증 유틸리티
├── wrapper.py               # MCP 서버 래핑 유틸리티
├── reverse_proxy.py         # 역방향 프록시 구현
├── alembic/                 # 데이터베이스 마이그레이션
├── cache/                   # 캐시 시스템
├── federation/              # 게이트웨이 페데레이션
├── handlers/                # 요청 핸들러
├── middleware/              # FastAPI 미들웨어
├── plugins/                 # 플러그인 프레임워크
├── routers/                 # API 라우터
├── services/                # 비즈니스 로직 서비스
├── static/                  # 정적 파일 (CSS, JS)
├── templates/               # HTML 템플릿
├── transports/              # 전송 계층 구현
├── utils/                   # 유틸리티 함수들
└── validation/              # 검증 모듈
```

## 핵심 컴포넌트 상세 설명

### 1. 애플리케이션 코어 파일들

#### `main.py` - FastAPI 애플리케이션 엔트리포인트

**역할**: FastAPI 애플리케이션의 메인 엔트리포인트이자 전체 시스템의 중심
**주요 기능**:

- 애플리케이션 수명주기 관리 (startup/shutdown)
- 모든 서비스 초기화 및 조율
- MCP 프로토콜 엔드포인트 제공 (initialize, ping, notify, complete, sample)
- 미들웨어 설정 (CORS, 보안 헤더, 문서 보호)
- 라우터 등록 및 관리
- WebSocket/SSE/HTTP 전송 지원

**핵심 메서드**:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 서비스 초기화 및 종료 관리
```

**주요 클래스**:

#### `config.py` - 설정 관리 시스템

**역할**: Pydantic을 활용한 중앙 집중식 설정 관리
**주요 기능**:

- 환경변수 기반 설정 로딩
- 설정 유효성 검증
- 데이터베이스 연결 설정
- 인증 및 보안 설정
- 캐시 및 세션 설정
- JSONPath 변환 유틸리티 제공

**주요 클래스**:

```python
class Settings(BaseSettings):
    # 전체 애플리케이션 설정 관리
```

**주요 모델들**:

#### `db.py` - 데이터베이스 모델 및 연결

**역할**: SQLAlchemy ORM 모델 정의 및 데이터베이스 연결 관리
**주요 기능**:

- 모든 MCP 엔티티의 데이터베이스 모델 정의
- 관계형 데이터베이스 연결 설정
- 마이그레이션 지원
- UTC 타임스탬프 관리
- 슬러그 생성 및 갱신

**주요 모델들**:

- `Tool`: 도구 정의 및 메트릭
- `Resource`: 리소스 정의 및 구독 관리
- `Prompt`: 프롬프트 템플릿
- `Server`: MCP 서버 카탈로그
- `Gateway`: 페데레이션 게이트웨이
- `A2AAgent`: 에이전트 간 통신용 에이전트

#### `models.py` - MCP 프로토콜 모델

**역할**: MCP 프로토콜의 모든 데이터 모델 정의
**주요 기능**:

- JSON-RPC 2.0 메시지 모델
- MCP 프로토콜 요청/응답 모델
- 리소스, 프롬프트, 도구 모델
- 초기화 및 핸드셰이킹 모델

**주요 모델들**:

```python
class InitializeRequest(BaseModel):  # 클라이언트 초기화 요청
class InitializeResult(BaseModel):   # 서버 초기화 응답
class Tool(BaseModel):              # 도구 정의
class Resource(BaseModel):          # 리소스 정의
```

### 2. 서비스 계층 (`services/`)

서비스 계층은 비즈니스 로직의 핵심으로, 각 MCP 엔티티의 CRUD 작업과 고급 기능을 제공합니다.

#### `tool_service.py` - 도구 관리 서비스

**역할**: MCP 도구의 전체 라이프사이클 관리
**주요 기능**:

- 도구 등록 및 검증
- 도구 호출 및 스키마 검증
- 도구 페데레이션
- 실행 메트릭 수집
- 플러그인 후크 통합

#### `resource_service.py` - 리소스 관리 서비스

**역할**: MCP 리소스의 CRUD 및 구독 관리
**주요 기능**:

- 리소스 템플릿 관리
- 실시간 구독 처리
- 캐시 기반 리소스 제공
- MIME 타입 검증

#### `prompt_service.py` - 프롬프트 관리 서비스

**역할**: 프롬프트 템플릿의 렌더링 및 관리
**주요 기능**:

- 프롬프트 템플릿 렌더링
- 인자 검증
- 캐시 기반 성능 최적화

#### `gateway_service.py` - 게이트웨이 페데레이션 서비스

**역할**: 다중 게이트웨이 간 페데레이션 관리
**주요 기능**:

- 게이트웨이 검색 및 등록
- 헬스 체크 및 모니터링
- OAuth 토큰 관리
- 크로스-게이트웨이 통신

#### `a2a_service.py` - Agent-to-Agent 서비스

**역할**: AI 에이전트 간 표준화된 통신
**주요 기능**:

- A2A 에이전트 등록/관리
- 표준화된 프로토콜 지원
- 메트릭 수집 및 모니터링

#### `logging_service.py` - 통합 로깅 서비스

**역할**: 이중 출력 로깅 시스템 (파일 + 메모리)
**주요 기능**:

- 구조화된 JSON 로깅
- 메모리 버퍼 기반 관리 UI 지원
- 로그 회전 및 보존

### 3. 전송 계층 (`transports/`)

전송 계층은 다양한 프로토콜을 통한 MCP 통신을 지원합니다.

#### `base.py` - 전송 추상 기본 클래스

**역할**: 모든 전송 구현의 공통 인터페이스 정의
**주요 기능**:

- 연결 관리 인터페이스
- 메시지 송수신 추상화
- 연결 상태 모니터링

#### `sse_transport.py` - Server-Sent Events 전송

**역할**: SSE 기반 실시간 양방향 통신
**주요 기능**:

- 이벤트 스트림 관리
- 연결 유지 및 재연결
- 세션 기반 메시징

#### `websocket_transport.py` - WebSocket 전송

**역할**: WebSocket 기반 양방향 통신
**주요 기능**:

- 실시간 메시징
- 연결 상태 모니터링
- 자동 재연결

#### `stdio_transport.py` - 표준 입출력 전송

**역할**: STDIO 기반 프로세스 간 통신
**주요 기능**:

- 자식 프로세스 관리
- 비동기 입출력 처리

#### `streamablehttp_transport.py` - 스트리밍 HTTP 전송

**역할**: HTTP 기반 스트리밍 통신
**주요 기능**:

- HTTP 요청/응답 처리
- 스트리밍 지원

### 4. 플러그인 프레임워크 (`plugins/`)

확장 가능한 플러그인 시스템을 제공합니다.

#### `framework/` - 플러그인 코어 프레임워크

**역할**: 플러그인 수명주기 및 실행 관리
**주요 컴포넌트**:

- `manager.py`: 플러그인 매니저 (실행 조율)
- `base.py`: 플러그인 기본 클래스
- `models.py`: 플러그인 관련 데이터 모델
- `registry.py`: 플러그인 인스턴스 레지스트리

**후크 포인트**:

- `prompt_pre_fetch`: 프롬프트 가져오기 전
- `prompt_post_fetch`: 프롬프트 가져오기 후
- `tool_pre_invoke`: 도구 호출 전
- `tool_post_invoke`: 도구 호출 후
- `resource_pre_fetch`: 리소스 가져오기 전
- `resource_post_fetch`: 리소스 가져오기 후

### 4. 캐시 시스템 (`cache/`)

성능 최적화를 위한 캐시 구현입니다.

#### `resource_cache.py` - 리소스 캐시

**역할**: LRU 기반 리소스 캐싱
**주요 기능**:

- TTL 기반 캐시 만료
- 메모리 사용량 제어
- 백그라운드 정리 작업

#### `session_registry.py` - 세션 레지스트리

**역할**: MCP 세션 및 메시지 관리
**주요 기능**:

- 세션 상태 추적
- 메시지 큐 관리
- Redis/DB 백엔드 지원

### 5. 페데레이션 시스템 (`federation/`)

다중 게이트웨이 간 통합을 지원합니다.

#### `discovery.py` - 게이트웨이 검색

**역할**: mDNS/Zeroconf 기반 게이트웨이 자동 검색
**주요 기능**:

- 로컬 네트워크 게이트웨이 검색
- 헬스 체크 및 상태 모니터링
- 피어 간 메타데이터 교환

#### `forward.py` - 요청 포워딩

**역할**: 크로스-게이트웨이 요청 라우팅
**주요 기능**:

- 요청 라우팅 및 로드 밸런싱
- 에러 처리 및 재시도 로직
- 인증 헤더 전달

### 6. 유틸리티 모듈들 (`utils/`)

공통 유틸리티 함수들을 제공합니다.

#### 주요 유틸리티들

- `create_jwt_token.py`: JWT 토큰 생성
- `retry_manager.py`: 재시도 로직
- `passthrough_headers.py`: 헤더 전달 관리
- `oauth_encryption.py`: OAuth 데이터 암호화
- `metrics_common.py`: 메트릭 계산 유틸리티

### 7. 검증 모듈 (`validation/`)

입력 데이터 검증을 담당합니다.

#### `jsonrpc.py` - JSON-RPC 검증

**역할**: JSON-RPC 메시지 검증
**주요 기능**:

- 메시지 형식 검증
- 스키마 유효성 검사

#### `tags.py` - 태그 검증

**역할**: 태그 기반 필터링 검증
**주요 기능**:

- 태그 형식 검증
- 필터링 로직 지원

## 아키텍처 패턴 및 설계 원칙

### 1. 계층화 아키텍처

```
┌─────────────────┐
│   Routers       │  # API 엔드포인트
├─────────────────┤
│   Services      │  # 비즈니스 로직
├─────────────────┤
│   Repository    │  # 데이터 접근
│   (db.py)       │
├─────────────────┤
│   Transports    │  # 통신 계층
├─────────────────┤
│   Cache         │  # 성능 최적화
└─────────────────┘
```

### 2. 플러그인 기반 확장성

- **후크 기반 아키텍처**: 주요 작업 전후에 플러그인 실행
- **조건부 실행**: 테넌트/사용자/서버 기반 필터링
- **격리된 실행**: 타임아웃 및 에러 격리

### 3. 비동기 설계

- **asyncio 기반**: 모든 I/O 작업 비동기 처리
- **동시성 제어**: 도구 호출 및 리소스 접근 제한
- **백그라운드 작업**: 캐시 정리, 헬스 체크 등

### 4. 보안 우선 접근

- **다중 인증**: JWT, Basic, OAuth 지원
- **입력 검증**: 모든 입력에 대한 엄격한 검증
- **헤더 패스스루**: 보안 헤더 안전한 전달
- **CORS 및 CSP**: 웹 보안 표준 준수

## 개발 및 사용 가이드

### 환경 설정

```bash
# 필수 환경변수
export MCPGATEWAY_BASIC_AUTH_USER=admin
export MCPGATEWAY_BASIC_AUTH_PASSWORD=secure_password
export MCPGATEWAY_JWT_SECRET_KEY=your-secret-key
export DATABASE_URL=sqlite:///./mcp.db

# 선택적 설정
export MCPGATEWAY_LOG_LEVEL=INFO
export MCPGATEWAY_CORS_ENABLED=true
export MCPGATEWAY_PLUGINS_ENABLED=false
```

### 애플리케이션 실행

```bash
# 개발 모드 (핫 리로드)
python -m mcpgateway --reload --host 0.0.0.0 --port 4444

# 프로덕션 모드 (Gunicorn)
gunicorn mcpgateway.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 플러그인 개발

```python
from mcpgateway.plugins.framework import Plugin, PluginConfig
from mcpgateway.plugins.framework.models import ToolPreInvokePayload, GlobalContext

class MyPlugin(Plugin):
    async def tool_pre_invoke(
        self,
        payload: ToolPreInvokePayload,
        context: GlobalContext
    ) -> PluginResult:
        # 플러그인 로직 구현
        pass
```

## 모니터링 및 관측성

### 메트릭 수집

- **도구 실행 메트릭**: 응답 시간, 성공률, 에러율
- **리소스 접근 메트릭**: 캐시 히트율, 접근 빈도
- **시스템 메트릭**: 메모리 사용량, CPU 사용률

### 로깅

- **구조화된 로깅**: JSON 형식 로그
- **이중 출력**: 파일 + 메모리 버퍼
- **로그 회전**: 자동 로그 파일 관리

### 헬스 체크

```bash
# 헬스 체크 엔드포인트
GET /health    # 기본 헬스 체크
GET /ready     # 준비 상태 확인
```

## 결론

`mcpgateway/` 패키지는 현대적인 MCP 게이트웨이 구현의 모범 사례를 보여줍니다:

- **확장성**: 플러그인 기반 아키텍처
- **성능**: 캐시 및 비동기 처리
- **안정성**: 포괄적인 에러 처리 및 검증
- **유지보수성**: 명확한 계층 분리와 모듈화
- **보안**: 다중 인증 및 입력 검증

이 구조는 복잡한 분산 시스템을 구축하고 운영하는 데 필요한 모든 핵심 컴포넌트를 제공합니다.
