# MCP Gateway Services Layer - 비즈니스 로직 컴포넌트 가이드

## 개요

`services/` 폴더는 MCP Gateway의 비즈니스 로직 계층을 담당하는 핵심 컴포넌트들로 구성되어 있습니다. 이 계층은 애플리케이션의 도메인 로직을 구현하며, 데이터베이스와의 상호작용, 외부 시스템 통합, 비즈니스 규칙 적용 등을 담당합니다.

## 서비스 아키텍처 개요

```bash
services/
├── __init__.py                     # 서비스 계층 초기화
├── tool_service.py                 # 도구 관리 및 실행 서비스
├── resource_service.py             # 리소스 관리 및 구독 서비스
├── prompt_service.py               # 프롬프트 템플릿 관리 서비스
├── server_service.py               # MCP 서버 카탈로그 관리 서비스
├── gateway_service.py              # 게이트웨이 페데레이션 서비스
├── a2a_service.py                  # Agent-to-Agent 통신 서비스
├── logging_service.py              # 통합 로깅 서비스
├── export_service.py               # 구성 내보내기 서비스
├── import_service.py               # 구성 가져오기 서비스
├── oauth_manager.py                # OAuth 인증 관리자
├── token_storage_service.py        # 토큰 저장소 서비스
├── completion_service.py           # 자동 완성 서비스
├── root_service.py                 # 루트 관리 서비스
├── tag_service.py                  # 태그 관리 서비스
├── log_storage_service.py          # 로그 저장소 서비스
```

## 핵심 서비스 상세 설명

### 1. 도구 관리 서비스 (`tool_service.py`)

**역할**: MCP 도구의 전체 라이프사이클 관리 및 실행
**주요 책임**:

- 도구 등록 및 검증
- 도구 호출 및 스키마 검증
- 도구 페데레이션 (다중 게이트웨이 지원)
- 실행 메트릭 수집 및 모니터링
- 이벤트 알림 및 상태 관리

**핵심 기능**:

- **도구 호출**: MCP 프로토콜을 통한 도구 실행
- **스키마 검증**: 입력 파라미터 유효성 검사
- **페데레이션 지원**: 여러 게이트웨이에 걸친 도구 호출
- **메트릭 수집**: 응답 시간, 성공률, 에러율 추적
- **플러그인 통합**: 실행 전후 후크 포인트 제공

**주요 클래스**:

```python
class ToolService:
    # 도구 관리의 핵심 클래스
    async def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult
    async def register_tool(self, tool_data: ToolCreate) -> ToolRead
    async def federate_tool_request(self, gateway_id: str, tool_name: str) -> ToolResult
```

### 2. 리소스 관리 서비스 (`resource_service.py`)

**역할**: MCP 리소스의 CRUD 및 실시간 구독 관리
**주요 책임**:

- 리소스 등록 및 검색
- 리소스 템플릿 및 URI 처리
- 실시간 구독 및 업데이트 알림
- 콘텐츠 타입 자동 감지
- 활성/비활성 상태 관리

**핵심 기능**:

- **템플릿 기반 리소스**: URI 템플릿을 통한 동적 리소스 생성
- **실시간 구독**: WebSocket/SSE를 통한 리소스 변경 알림
- **콘텐츠 관리**: 텍스트와 바이너리 콘텐츠 지원
- **캐시 최적화**: 자주 접근하는 리소스의 캐시 관리

**주요 클래스**:

```python
class ResourceService:
    # 리소스 관리의 핵심 클래스
    async def read_resource(self, uri: str) -> ResourceContent
    async def subscribe_resource(self, uri: str) -> AsyncGenerator[ResourceUpdate, None]
    async def create_resource_template(self, template: ResourceTemplate) -> ResourceTemplate
```

### 3. 프롬프트 관리 서비스 (`prompt_service.py`)

**역할**: 프롬프트 템플릿의 렌더링 및 관리
**주요 책임**:

- 프롬프트 템플릿 저장 및 검색
- 동적 인자 바인딩 및 렌더링
- 프롬프트 실행 메트릭 수집
- 템플릿 유효성 검사

**핵심 기능**:

- **템플릿 렌더링**: Jinja2 기반 동적 프롬프트 생성
- **인자 검증**: 입력 파라미터의 타입 및 필수성 검사
- **캐시 최적화**: 렌더링된 프롬프트의 캐시 관리
- **메트릭 추적**: 프롬프트 사용 통계 수집

### 4. 서버 카탈로그 서비스 (`server_service.py`)

**역할**: MCP 서버들의 카탈로그 및 연결 관리
**주요 책임**:

- 서버 등록 및 검색
- 서버-엔티티 연관 관계 관리
- 서버 헬스 체크 및 모니터링
- 서버별 접근 제어

**핵심 기능**:

- **다대다 관계 관리**: 서버와 도구/리소스/프롬프트 간의 연관
- **접근 제어**: 서버별 엔티티 가시성 제어
- **헬스 모니터링**: 서버 연결 상태 추적
- **부하 분산**: 여러 서버 간 요청 분배

### 5. 게이트웨이 페데레이션 서비스 (`gateway_service.py`)

**역할**: 다중 게이트웨이 간 통합 및 페데레이션 관리
**주요 책임**:

- 게이트웨이 검색 및 등록
- 크로스-게이트웨이 요청 포워딩
- 기능 집계 및 헬스 모니터링
- 페데레이션 보안 관리

**핵심 기능**:

- **자동 검색**: mDNS/Zeroconf를 통한 게이트웨이 자동 발견
- **요청 라우팅**: 최적의 게이트웨이로 요청 전달
- **기능 집계**: 여러 게이트웨이의 기능 통합 제공
- **헬스 체크**: 게이트웨이 상태 모니터링 및 장애 조치

### 6. Agent-to-Agent 서비스 (`a2a_service.py`)

**역할**: AI 에이전트 간 표준화된 통신 프로토콜 지원
**주요 책임**:

- A2A 에이전트 등록 및 관리
- 표준화된 통신 프로토콜 구현
- 에이전트 간 메시지 라우팅
- 상호작용 메트릭 수집

**핵심 기능**:

- **프로토콜 표준화**: Agent-to-Agent 통신 표준 지원
- **메시지 라우팅**: 에이전트 간 안전한 메시지 전달
- **메트릭 수집**: 상호작용 성능 및 성공률 추적
- **다중 프로토콜**: 다양한 A2A 프로토콜 버전 지원

### 7. 로깅 서비스 (`logging_service.py`)

**역할**: 애플리케이션 전반의 통합 로깅 관리
**주요 책임**:

- 구조화된 JSON 로깅 구현
- 파일과 메모리 이중 출력
- 로그 회전 및 보존 관리
- 관리 UI를 위한 로그 스트리밍

**핵심 기능**:

- **이중 로깅**: 파일 + 메모리 버퍼 동시 기록
- **구조화된 포맷**: JSON 형식의 정형화된 로그
- **실시간 스트리밍**: WebSocket을 통한 실시간 로그 모니터링
- **관리 인터페이스**: 웹 UI를 통한 로그 검색 및 필터링

## 지원 서비스들

### 데이터 관리 서비스

#### 내보내기/가져오기 서비스

- `export_service.py`: 시스템 구성 및 데이터 내보내기
- `import_service.py`: 구성 및 데이터 가져오기 및 병합

#### 토큰 저장소 서비스

- `token_storage_service.py`: OAuth 토큰의 안전한 저장 및 관리
- `oauth_manager.py`: OAuth 2.0 인증 플로우 관리

### 유틸리티 서비스

#### 자동 완성 서비스

- `completion_service.py`: MCP completion 프로토콜 구현

#### 루트 관리 서비스

- `root_service.py`: MCP 루트 디렉토리 및 파일시스템 관리

#### 태그 관리 서비스

- `tag_service.py`: 엔티티 태깅 및 카테고리화

#### 로그 저장소 서비스

- `log_storage_service.py`: 로그 데이터의 영구 저장 및 검색

## 서비스 간 상호작용 패턴

### 1. 비동기 이벤트 기반 통신

```python
# 서비스 간 이벤트 기반 통신 예시
async def notify_tool_change(self, tool_id: str, event_type: str):
    """도구 변경 이벤트를 관련 서비스에 알림"""
    # resource_service에 도구 변경 알림
    await self._resource_service.handle_tool_update(tool_id, event_type)
    # gateway_service에 페데레이션 업데이트 알림
    await self._gateway_service.broadcast_tool_change(tool_id, event_type)
```

### 2. 플러그인 통합 패턴

```python
# 플러그인 후크를 통한 확장성
async def invoke_tool_with_plugins(self, tool_name: str, args: Dict[str, Any]):
    # 실행 전 플러그인 후크
    await self._plugin_manager.tool_pre_invoke(payload, context)

    # 도구 실행
    result = await self._execute_tool(tool_name, args)

    # 실행 후 플러그인 후크
    await self._plugin_manager.tool_post_invoke(payload, context)

    return result
```

### 3. 메트릭 수집 패턴

```python
# 표준화된 메트릭 수집
async def execute_with_metrics(self, operation: str, func: Callable):
    start_time = time.time()
    try:
        result = await func()
        self._record_metric(operation, time.time() - start_time, success=True)
        return result
    except Exception as e:
        self._record_metric(operation, time.time() - start_time, success=False)
        raise
```

## 서비스 초기화 및 종료

### 초기화 순서

```python
# 서비스 초기화 순서 (main.py에서)
async def initialize_services():
    # 1. 로깅 서비스 (가장 먼저)
    await logging_service.initialize()

    # 2. 코어 서비스들
    await tool_service.initialize()
    await resource_service.initialize()
    await prompt_service.initialize()

    # 3. 상호 의존적인 서비스들
    await gateway_service.initialize()
    await a2a_service.initialize()

    # 4. 유틸리티 서비스들
    await completion_service.initialize()
    await export_service.initialize()
```

### 종료 순서

```python
# 서비스 종료 순서 (역순)
async def shutdown_services():
    await a2a_service.shutdown()
    await gateway_service.shutdown()
    await prompt_service.shutdown()
    await resource_service.shutdown()
    await tool_service.shutdown()
    await logging_service.shutdown()
```

## 에러 처리 및 복원력

### 표준 에러 계층

```python
class ServiceError(Exception):
    """모든 서비스 에러의 기본 클래스"""

class ValidationError(ServiceError):
    """입력 검증 실패"""

class NotFoundError(ServiceError):
    """리소스를 찾을 수 없음"""

class ConflictError(ServiceError):
    """리소스 충돌"""

class ExternalServiceError(ServiceError):
    """외부 서비스 통신 실패"""
```

### 재시도 및 회로 차단기 패턴

```python
# 재시도 로직이 내장된 HTTP 클라이언트 사용
self._http_client = ResilientHttpClient(
    client_args={"timeout": settings.federation_timeout},
    max_retries=settings.max_tool_retries
)
```

## 성능 최적화

### 캐시 전략

- **리소스 캐시**: 자주 접근하는 리소스의 메모리 캐시
- **템플릿 캐시**: 렌더링된 프롬프트 템플릿 캐시
- **메타데이터 캐시**: 도구/리소스 메타데이터 캐시

### 동시성 제어

- **세마포어**: 동시 요청 수 제한
- **큐잉**: 과도한 로드 시 요청 큐잉
- **풀 관리**: 데이터베이스 및 HTTP 연결 풀 관리

## 모니터링 및 관측성

### 메트릭 수집

- **실행 메트릭**: 응답 시간, 성공률, 에러율
- **리소스 메트릭**: 메모리 사용량, 연결 수
- **비즈니스 메트릭**: 사용자 활동, API 사용량

### 헬스 체크

```python
async def health_check(self) -> Dict[str, Any]:
    """서비스 헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "metrics": self._collect_metrics(),
        "dependencies": await self._check_dependencies()
    }
```

## 결론

services/ 폴더는 MCP Gateway의 비즈니스 로직을 구현하는 핵심 계층으로, 다음과 같은 특징을 가집니다:

- **모듈화된 설계**: 각 서비스가 독립적인 책임을 가짐
- **확장성**: 플러그인 시스템을 통한 기능 확장
- **복원력**: 재시도 로직과 에러 처리
- **성능**: 캐시와 동시성 제어를 통한 최적화
- **관측성**: 메트릭 수집과 모니터링

이러한 아키텍처는 복잡한 분산 시스템을 구축하고 운영하는 데 필요한 모든 핵심 기능을 제공합니다.

## 탐색

- **⬆️ mcpgateway**: [../AGENTS.md](../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../AGENTS.md](../../AGENTS.md)
