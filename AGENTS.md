# Repository Guidelines

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
- 목적: Gateway의 Tool 카탈로그를 동적으로 수집·제한하면서
  - OpenAI 호환 `/v1/chat/completions` 제공(스트리밍 포함)
  - A2A(JSON-RPC) 엔드포인트 제공
- 핵심 파일
  - `app.py`: FastAPI 앱(헬스/레디니스, OpenAI 호환 API, A2A)
  - `agent_langchain.py`: LangChain 기반 에이전트, 툴 통합·실행
  - `mcp_client.py`: Gateway 연동, 툴 디스커버리/스키마 파싱
  - `config.py`, `models.py`, `start_agent.py`, `requirements.txt`, `Makefile`

### plugins/ (런타임 플러그인 및 설정)
- 설정: `plugins/config.yaml`
- 내장 필터 예시: `pii_filter/`, `deny_filter/`, `regex_filter/`, `resource_filter/`
- 외부/네이티브 플러그인 템플릿: `plugin_templates/{external, native}`

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

## Architecture Overview
- Core: FastAPI + Pydantic with SQLAlchemy. Architectural decisions live under `docs/docs/architecture/adr/`.
- Data: SQLite by default; PostgreSQL via extras. Migrations managed with Alembic in `mcpgateway/alembic/`.
- Caching & Federation: Optional Redis, mDNS/Zeroconf discovery, peer registration, health checks and failover.
- Virtual Servers: Compose tools, prompts, and resources across multiple MCP servers; control tool visibility per server.
- Transports: SSE, WebSocket, stdio wrapper, and streamable HTTP endpoints.

## Security & Configuration Tips
- Copy `.env.example` → `.env`; verify with `make check-env`. Never commit secrets.
- Auth: set `JWT_SECRET_KEY`; export `MCPGATEWAY_BEARER_TOKEN` using the token utility for API calls.
- Wrapper: set `MCP_SERVER_URL` and `MCP_AUTH` when using `mcpgateway.wrapper`.
- TLS: `make certs` → `make serve-ssl`. Prefer environment variables for config; see `README.md`.
