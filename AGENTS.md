# Repository Guidelines - MCP Gateway Agents

## Project Structure

### Top-level

- `mcpgateway/`: FastAPI 기반 MCP Gateway 애플리케이션 패키지(엔트리 `main.py`)
- `agent_runtimes/langchain_agent/`: LangChain 에이전트 런타임(오픈AI 호환 Chat API + A2A JSON-RPC)
- `mcp-servers/`: 샘플 MCP 서버 구현(`go/fast-time-server`, `python/mcp_eval_server`)
- `plugins/`: 내장 플러그인과 플러그인 설정(`plugins/config.yaml` 포함)
- `plugin_templates/`: 플러그인 스캐폴드 템플릿(Jinja)
- `docs/`: MkDocs 기반 문서 사이트 소스(`docs/docs/` 하위에 아키텍처/가이드 등)
- `deployment/`: 배포 자산(Ansible, Kubernetes 매니페스트, Terraform)
- `charts/`: Helm 차트(`charts/mcp-stack`)
- `tests/`: 테스트 스위트(유닛/통합/E2E/보안/퍼지/플레이라이트 등)
- 개발/운영 보조: `Makefile`, `pyproject.toml`, `Containerfile*`, `docker-compose*.yml`, `run.sh`, `run-gunicorn.sh`, `uv.lock`, `tox.ini`, `pyrightconfig.json`
- 예시 구성: `examples/` (예: `reverse-proxy-config.yaml`)

### mcpgateway/ (FastAPI 애플리케이션)

- 애플리케이션 엔트리포인트: `main.py`
    - 수명주기 관리(lifespan), 미들웨어(CORS, 보안 헤더, Docs 보호, MCP 경로 리라이트), 라우터 등록
    - 서비스 초기화(툴/리소스/프롬프트/서버/게이트웨이/태그/A2A/완성 등) 및 종료
    - SSE/WS/STDIO/Streamable HTTP 등 프로토콜 지원 지점 연결
- 설정/부트스트랩
    - `config.py`: Pydantic Settings, 환경변수 검증 및 JSONPath 응답 변환 도우미
    - `bootstrap_db.py`, `alembic/`: 초기 스키마 생성과 마이그레이션(버전은 `alembic/versions/`)
    - `db.py`: SQLAlchemy 엔진/세션, 모델 선언과 유틸
- 라우터
    - `routers/`: `well_known.py`, `reverse_proxy.py`, `oauth_router.py` 등 공개 엔드포인트/헬퍼
    - Admin UI: `admin.py`(라우터) + `templates/admin.html`, `static/admin.{css,js}`
    - 관리 API(패스스루 헤더): 전역/게이트웨이 헤더 패스스루 설정 지원
        - 전역: `GET/PUT /admin/config/passthrough-headers`
        - 게이트웨이별: `Gateways.passthrough_headers` 필드로 제어(관리/CRUD API를 통해 설정)
    - OAuth 라우터: 게이트웨이 OAuth 2.0 플로우 지원
        - `GET /oauth/authorize/{gateway_id}` → 공급자 인가로 이동
        - `GET /oauth/callback` → 콜백 처리 및 토큰 저장
        - `GET /oauth/status/{gateway_id}` → 연결 상태 조회
        - `POST /oauth/fetch-tools/{gateway_id}` → OAuth 후 도구 동기화
- 전송 계층(Transports)
    - `transports/`: `sse_transport.py`, `websocket_transport.py`, `stdio_transport.py`, `streamablehttp_transport.py`
- 서비스 계층(도메인 로직)
    - `services/`: `tool_service.py`, `resource_service.py`, `prompt_service.py`, `server_service.py`, `gateway_service.py`, `completion_service.py`, `a2a_service.py`, `export_service.py`, `import_service.py`, `tag_service.py`, `logging_service.py` 등
- 플러그인 프레임워크
    - `plugins/framework/`: 플러그인 수명주기/검증/훅 정의, `PluginManager`
- 캐시/세션
    - `cache/`: `resource_cache.py`(LRU+TTL), `session_registry.py`(세션/메시지 관리)
- 미들웨어/보안/검증
    - `middleware/security_headers.py`: CSP, X-Frame-Options 등 보안 헤더 삽입
    - 문서 보호 미들웨어, 경로 리라이트는 `main.py` 내 정의
    - `validation/`: JSON-RPC 검증 및 오류 타입
- 스키마/모델/유틸
    - `schemas.py`: Pydantic DTO 집합, API 스키마
    - `models.py`: 프로토콜/리소스/루트 등 공용 모델·열거형
    - `utils/`: 인증(JWT/Basic), 재시도 HTTP 클라이언트, 헤더 패스스루, Redis/DB 준비 체크, 오류 포매터 등
- 기타
    - `observability.py`: OpenTelemetry 초기화(옵션)
    - `version.py`: 버전 라우터/헬퍼

### agent_runtimes/langchain_agent/

- **목적**: Gateway의 Tool 카탈로그를 동적으로 수집·제한하면서 OpenAI 호환 API 제공
    - OpenAI 호환 `/v1/chat/completions` 엔드포인트 (스트리밍 지원)
    - A2A (Agent-to-Agent) JSON-RPC 엔드포인트
    - 다중 LLM 프로바이더 지원 (OpenAI, Azure, Anthropic, Bedrock, Ollama)
    - MCP Gateway와의 실시간 통합

- **핵심 파일 구조**:
    - `app.py`: FastAPI 애플리케이션 (헬스체크, OpenAI 호환 API, A2A 엔드포인트)
    - `agent_langchain.py`: LangChain 기반 에이전트 코어 로직
        - 다중 LLM 프로바이더 지원 (`create_llm()`)
        - MCP 도구를 LangChain 도구로 변환 (`MCPTool`)
        - AgentExecutor를 통한 도구 실행 오케스트레이션
    - `mcp_client.py`: MCP Gateway 클라이언트
        - 도구 디스커버리 및 메타데이터 수집
        - 다중 실행 표면 지원 (JSON-RPC, REST, 직접 호출)
        - 스키마 검증 및 에러 처리
    - `config.py`: Pydantic 설정 모델
    - `models.py`: OpenAI 호환 API 모델들
    - `start_agent.py`: 애플리케이션 시작점
    - `requirements.txt`, `Makefile`: 의존성과 빌드 설정

### plugins/ (런타임 플러그인 및 설정)

- 설정: `plugins/config.yaml`
- 내장 필터 예시: `pii_filter/`, `deny_filter/`, `regex_filter/`, `resource_filter/`
- 외부/네이티브 플러그인 템플릿: `plugin_templates/{external, native}`

### A2A (Agent-to-Agent) 시스템

- **핵심 서비스**: `mcpgateway/services/a2a_service.py`
    - A2A 에이전트 등록/관리/삭제
    - 에이전트 간 통신 및 상호작용
    - 메트릭 수집 및 모니터링
    - 비동기 이벤트 스트림 관리

- **데이터베이스 모델**: `mcpgateway/db.py`
    - `A2AAgent`: 에이전트 메타데이터 저장
    - `A2AAgentMetric`: 상호작용 메트릭 기록
    - `server_a2a_association`: 서버-에이전트 매핑

- **API 엔드포인트**: `mcpgateway/main.py`
    - `/a2a`: 에이전트 관리 API
    - `/{agent_name}/invoke`: 에이전트 호출
    - 메트릭 및 헬스체크 엔드포인트

- **특징**:
    - 표준화된 Agent-to-Agent 프로토콜 지원
    - 다중 프로토콜 버전 지원 (`1.0`, `2025-03-26` 등)
    - OAuth 및 API 키 인증
    - 실시간 헬스체크 및 모니터링

### mcp-servers/ (샘플 MCP 서버)

- `go/fast-time-server`: Go 기반 시간 서버(컨테이너/stdio로 테스트 가능)
- `python/mcp_eval_server`: Python 예제(리소스/툴/프롬프트 데모 포함)

### 배포 & 오케스트레이션

- `deployment/k8s/`: K8s 매니페스트(게이트웨이/Redis/Postgres/Ingress 등)
- `deployment/ansible/`: IBM Cloud 등 대상 인프라 구성 롤북
- `deployment/terraform/`: 클라우드 리소스 프로비저닝 샘플
- `charts/mcp-stack`: Helm 차트(프로파일별 배포값은 `values.yaml`)

### 문서 사이트(MkDocs)

- `docs/`: `mkdocs.yml` + `docs/docs/` 하위에
    - `architecture/`, `development/`, `using/`, `manage/`, `testing/` 등 상세 가이드

### 테스트 스위트

- `tests/unit`, `tests/integration`, `tests/e2e`, `tests/playwright`, `tests/security`, `tests/fuzz`, `tests/migration`
- 공용 픽스처: `tests/conftest.py`, 문서-예제 동기화 가드: `test_readme.py`

### 개발·운영 유틸

- 컨테이너/컴포즈: `Containerfile`, `Containerfile.lite`, `docker-compose*.yml`
- 실행 스크립트: `run.sh`(uvicorn 헬퍼), `run-gunicorn.sh`
- 품질/도구 설정: `pyproject.toml`(의존성·스크립트·툴링), `tox.ini`, `pyrightconfig.json`
- 기타: `async_testing/`(프로파일링/벤치마크), `os_deps.sh`, `smoketest.py`, `mutmut_config.py`

참고: CLI 엔트리포인트는 `pyproject.toml`의 `[project.scripts]`에 정의됨

- `mcpgateway = mcpgateway.cli:main`
- `mcpplugins = mcpgateway.plugins.tools.cli:main`

## Build, Test, and Development Commands

- Pre-commit: `make autoflake isort black pre-commit`
- Setup: `make venv`, `make install-dev`.
- Run: `make dev` (hot reload on :8000), `make serve` (gunicorn), or `mcpgateway --host 0.0.0.0 --port 4444`.
- Quality: `make lint`, `make lint-web`, `make check-manifest`.
- Tests: `make test`, `make doctest`, `make htmlcov` (HTML to `docs/docs/coverage/index.html`).
- Final check: `make doctest test htmlcov smoketest lint-web flake8 bandit interrogate pylint verify`

## Makefile Quick Reference

- `make dev`: Run fast-reload dev server on `:8000`.
- `make serve`: Run production Gunicorn server on `:4444`.
- `make certs`: Generate self-signed TLS certs in `./certs/`.
- `make serve-ssl`: Run Gunicorn behind HTTPS on `:4444` (uses `./certs`).
- `make lint`: Run full lint suite; `make install-web-linters` once before `make lint-web`.
- `make test`: Run unit tests; `make coverage` writes HTML to `docs/docs/coverage/`.
- `make doctest`: Run doctests across `mcpgateway/` modules.
- `make check-env`: Verify `.env` keys match `.env.example`.
- `make clean`: Remove caches, build artefacts, venv, coverage, docs, certs.

MCP helpers

- JWT token: `python -m mcpgateway.utils.create_jwt_token --username admin --exp 10080 --secret KEY`.
- Expose stdio server: `python -m mcpgateway.translate --stdio "uvx mcp-server-git" --port 9000`.

## Coding Style & Naming Conventions

- Python >= 3.11. Type hints required; strict `mypy` settings.
- Formatters/linters: Black (line length 200), isort (profile=black), Ruff (F,E,W,B,ASYNC), Pylint as configured in `pyproject.toml` and dotfiles.
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_CASE` for constants.
- Group imports per isort sections (stdlib, third-party, first-party `mcpgateway`, local).

## Testing Guidelines

- Pytest with async; discovery configured in `pyproject.toml`.
- Layout: unit (`tests/unit`), integration (`tests/integration`), e2e (`tests/e2e`), UI (`tests/playwright`).
- Naming: files `test_*.py`, classes `Test*`, functions `test_*`; marks: `slow`, `ui`, `api`, `smoke`, `e2e`.
- Commands: `make test`, `pytest -k "name"`, `pytest -m "not slow"`. Use `make coverage` for reports.
- Keep tests deterministic, isolated, and fast by default.

## Commit & Pull Request Guidelines

- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`). Link issues (e.g., `Closes #123`).
- Sign every commit with DCO: `git commit -s`.
- Do not mention Claude or Claude Code in PRs/diffs. Do not include effort estimates or "phases".
- Include tests and docs for behavior changes; attach screenshots for UI changes when relevant.
- Require green lint and tests locally before opening a PR.

## 에이전트 아키텍처 개요

### LangChain 에이전트 아키텍처

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OpenAI API    │    │   LangChain     │    │   MCP Gateway   │
│   Compatible    │◄──►│   Agent Runtime │◄──►│   Tool Catalog  │
│   Client        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ChatGPT/Claude │    │ AgentExecutor + │    │   Tool Service  │
│  Web UI, CLI    │    │  Function Tools │    │  Resource Service│
│  IDE Plugins    │    │                 │    │  Prompt Service  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**주요 컴포넌트**:

- **MCP 클라이언트**: Gateway의 `/tools` 엔드포인트에서 도구 카탈로그 수집
- **도구 어댑터**: MCP 도구를 LangChain BaseTool로 변환
- **LLM 팩토리**: 다중 프로바이더 지원 (OpenAI, Azure, Anthropic, Bedrock, Ollama)
- **AgentExecutor**: LangChain의 함수 호출 에이전트 실행

### A2A (Agent-to-Agent) 아키텍처

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   External AI   │    │   A2A Service   │    │   MCP Gateway   │
│   Agent/Service │◄──►│   (JSON-RPC)   │◄──►│   Tool Registry │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Standardized   │    │ Async Event     │    │  Metrics &      │
│  Protocol       │    │ Streams         │    │  Monitoring     │
│  (v1.0/2025)    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**주요 특징**:

- **표준화된 프로토콜**: Agent-to-Agent 통신 표준
- **비동기 이벤트**: 실시간 상호작용 지원
- **메트릭 수집**: 응답 시간, 성공률, 에러 추적
- **다중 인증**: API 키, OAuth, Bearer 토큰

### 통합 에이전트 아키텍처

```text
┌─────────────────────────────────────────────────────────────┐
│                    MCP Gateway Ecosystem                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │ LangChain   │ │   A2A       │ │ Federation  │ │ Plugins │ │
│  │ Agent       │ │ Agents      │ │ Gateways    │ │ System  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              MCP Gateway Core Services                  │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │ Tools │ Resources │ Prompts │ Servers │ Gateways │ Tags │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│              Transport Layer (SSE/WebSocket/HTTP)           │
└─────────────────────────────────────────────────────────────┘
```

## Architecture Overview

- Core: FastAPI + Pydantic with SQLAlchemy. Architectural decisions live under `docs/docs/architecture/adr/`.
- Data: SQLite by default; PostgreSQL via extras. Migrations managed with Alembic in `mcpgateway/alembic/`.
- Caching & Federation: Optional Redis, mDNS/Zeroconf discovery, peer registration, health checks and failover.
- Virtual Servers: Compose tools, prompts, and resources across multiple MCP servers; control tool visibility per server.
- Transports: SSE, WebSocket, stdio wrapper, and streamable HTTP endpoints.

## 에이전트 개발 및 사용 가이드

### LangChain 에이전트 시작하기

#### 1. 환경 설정

```bash
cd agent_runtimes/langchain_agent
cp .env.example .env
# .env 파일에 다음 설정 추가:
# MCP_GATEWAY_URL=http://localhost:4444
# MCPGATEWAY_BEARER_TOKEN=your-jwt-token
# OPENAI_API_KEY=your-openai-key
```

#### 2. 실행

```bash
# 개발 모드
make dev

# 프로덕션 모드
make serve
```

#### 3. API 사용

```bash
# OpenAI 호환 채팅 API
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "tools": "auto"
  }'

# A2A 에이전트 호출
curl -X POST http://localhost:8000/a2a/agent-name/invoke \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"query": "test"}}'
```

### A2A 에이전트 등록 및 관리

#### 1. 에이전트 등록

```bash
curl -X POST http://localhost:4444/a2a \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "name": "my-ai-agent",
    "endpoint_url": "https://api.example.com/agent",
    "agent_type": "custom",
    "protocol_version": "1.0"
  }'
```

#### 2. 에이전트 목록 조회

```bash
curl http://localhost:4444/a2a \
  -H "Authorization: Bearer your-token"
```

#### 3. 에이전트 호출

```bash
curl -X POST http://localhost:4444/a2a/my-ai-agent/invoke \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "parameters": {"task": "analyze_data"},
    "interaction_type": "query"
  }'
```

### 지원되는 LLM 프로바이더

| 프로바이더 | 설정 변수 | 설명 |
|-----------|----------|------|
| OpenAI | `OPENAI_API_KEY` | 표준 OpenAI API |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | Azure OpenAI 서비스 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 모델 |
| AWS Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Amazon Bedrock |
| Ollama | `OLLAMA_BASE_URL` | 로컬 Ollama 서버 |

### 에이전트 메트릭 및 모니터링

#### 성능 메트릭 조회

```bash
# LangChain 에이전트 메트릭
curl http://localhost:8000/metrics \
  -H "Authorization: Bearer your-token"

# A2A 에이전트 메트릭
curl http://localhost:4444/a2a/my-agent/metrics \
  -H "Authorization: Bearer your-token"
```

## Security & Configuration Tips

- Copy `.env.example` → `.env`; verify with `make check-env`. Never commit secrets.
- Auth: set `JWT_SECRET_KEY`; export `MCPGATEWAY_BEARER_TOKEN` using the token utility for API calls.
- Wrapper: set `MCP_SERVER_URL` and `MCP_AUTH` when using `mcpgateway.wrapper`.
- TLS: `make certs` → `make serve-ssl`. Prefer environment variables for config; see `README.md`.

## 문서 탐색

- **mcpgateway**: [mcpgateway/AGENTS.md](mcpgateway/AGENTS.md)
  - **cache**: [mcpgateway/cache/AGENTS.md](mcpgateway/cache/AGENTS.md)
  - **federation**: [mcpgateway/federation/AGENTS.md](mcpgateway/federation/AGENTS.md)
  - **handlers**: [mcpgateway/handlers/AGENTS.md](mcpgateway/handlers/AGENTS.md)
  - **middleware**: [mcpgateway/middleware/AGENTS.md](mcpgateway/middleware/AGENTS.md)
  - **plugins**: [mcpgateway/plugins/AGENTS.md](mcpgateway/plugins/AGENTS.md)
    - **framework**: [mcpgateway/plugins/framework/AGENTS.md](mcpgateway/plugins/framework/AGENTS.md)
  - **routers**: [mcpgateway/routers/AGENTS.md](mcpgateway/routers/AGENTS.md)
  - **services**: [mcpgateway/services/AGENTS.md](mcpgateway/services/AGENTS.md)
  - **transports**: [mcpgateway/transports/AGENTS.md](mcpgateway/transports/AGENTS.md)
  - **utils**: [mcpgateway/utils/AGENTS.md](mcpgateway/utils/AGENTS.md)
  - **validation**: [mcpgateway/validation/AGENTS.md](mcpgateway/validation/AGENTS.md)
  - **alembic**: [mcpgateway/alembic/AGENTS.md](mcpgateway/alembic/AGENTS.md)
- **agent_runtimes**: [agent_runtimes/AGENTS.md](agent_runtimes/AGENTS.md)
  - **langchain_agent**: [agent_runtimes/langchain_agent/AGENTS.md](agent_runtimes/langchain_agent/AGENTS.md)
- **mcp-servers**: [mcp-servers/AGENTS.md](mcp-servers/AGENTS.md)
- **plugins**: [plugins/AGENTS.md](plugins/AGENTS.md)
- **plugin_templates**: [plugin_templates/AGENTS.md](plugin_templates/AGENTS.md)
- **docs**: [docs/AGENTS.md](docs/AGENTS.md)
- **deployment**: [deployment/AGENTS.md](deployment/AGENTS.md)
- **charts**: [charts/AGENTS.md](charts/AGENTS.md)
- **tests**: [tests/AGENTS.md](tests/AGENTS.md)
- **async_testing**: [async_testing/AGENTS.md](async_testing/AGENTS.md)
- **examples**: [examples/AGENTS.md](examples/AGENTS.md)
