# MCP Gateway

FastAPI 기반의 MCP 게이트웨이/프록시로, REST와 MCP, A2A 에이전트를 단일 엔드포인트로 통합합니다. 툴/리소스/프롬프트 카탈로그, 가상 서버, 연합(Federation), 재시도/레이트리밋, 관측성(OpenTelemetry), 선택적 Admin UI, 그리고 다중 전송(SSE/stdio/Streamable HTTP/HTTP)을 지원합니다. OAuth 및 헤더 패스스루(전역/게이트웨이별) 설정이 가능하며, A2A(Agent-to-Agent) 표준을 통해 외부 에이전트와 상호작용할 수 있습니다.

---

<!-- vscode-markdown-toc -->
## Table of Contents

* 1. [Table of Contents](#table-of-contents)
* 2. [🚀 Overview & Goals](#-overview--goals)
* 3. [Quick Start - PyPI](#quick-start---pypi)
    * 3.1. [1 - Install & run (copy-paste friendly)](#1---install--run-copy-paste-friendly)
* 4. [Quick Start - Containers](#quick-start---containers)
    * 4.1. [🐳 Docker](#-docker)
        * 4.1.1. [1 - Minimum viable run](#1---minimum-viable-run)
        * 4.1.2. [2 - Persist the SQLite database](#2---persist-the-sqlite-database)
        * 4.1.3. [3 - Local tool discovery (host network)](#3---local-tool-discovery-host-network)
    * 4.2. [🦭 Podman (rootless-friendly)](#-podman-rootless-friendly)
        * 4.2.1. [1 - Basic run](#1---basic-run)
        * 4.2.2. [2 - Persist SQLite](#2---persist-sqlite)
        * 4.2.3. [3 - Host networking (rootless)](#3---host-networking-rootless)
* 5. [Testing `mcpgateway.wrapper` by hand](#testing-mcpgatewaywrapper-by-hand)
    * 5.1. [🧩 Running from an MCP Client (`mcpgateway.wrapper`)](#-running-from-an-mcp-client-mcpgatewaywrapper)
        * 5.1.1. [1 - Install `uv` (`uvx` is an alias it provides)](#1---install-uv-uvx-is-an-alias-it-provides)
        * 5.1.2. [2 - Create an on-the-spot venv & run the wrapper](#2---create-an-on-the-spot-venv--run-the-wrapper)
        * 5.1.3. [Claude Desktop JSON (runs through **uvx**)](#claude-desktop-json-runs-through-uvx)
    * 5.2. [🚀 Using with Claude Desktop (or any GUI MCP client)](#-using-with-claude-desktop-or-any-gui-mcp-client)
* 6. [Quick Start (manual install)](#quick-start-manual-install)
    * 6.1. [Prerequisites](#prerequisites)
    * 6.2. [One-liner (dev)](#one-liner-dev)
    * 6.3. [Containerized (self-signed TLS)](#containerized-self-signed-tls)
    * 6.4. [Smoke-test the API](#smoke-test-the-api)
* 7. [Installation](#installation)
    * 7.1. [Via Make](#via-make)
    * 7.2. [UV (alternative)](#uv-alternative)
    * 7.3. [pip (alternative)](#pip-alternative)
    * 7.4. [Optional (PostgreSQL adapter)](#optional-postgresql-adapter)
        * 7.4.1. [Quick Postgres container](#quick-postgres-container)
* 8. [Configuration (`.env` or env vars)](#configuration-env-or-env-vars)
    * 9.1. [Basic](#basic)
    * 9.2. [Authentication](#authentication)
    * 9.3. [UI Features](#ui-features)
    * 9.4. [Security](#security)
    * 9.5. [Logging](#logging)
    * 9.6. [Transport](#transport)
    * 9.7. [Federation](#federation)
    * 9.8. [Resources](#resources)
    * 9.9. [Tools](#tools)
    * 9.10. [Prompts](#prompts)
    * 9.11. [Health Checks](#health-checks)
    * 9.12. [Database](#database)
    * 9.13. [Cache Backend](#cache-backend)
    * 9.14. [Development](#development)
* 9. [Running](#running)
    * 10.1. [Makefile](#makefile)
    * 10.2. [Script helper](#script-helper)
    * 10.3. [Manual (Uvicorn)](#manual-uvicorn)
* 10. [Authentication examples](#authentication-examples)
* 11. [☁️ AWS / Azure / OpenShift](#️-aws--azure--openshift)
* 12. [API Endpoints](#api-endpoints)
* 13. [Testing](#testing)
* 14. [Project Structure](#project-structure)
* 15. [API Documentation](#api-documentation)
* 16. [Makefile targets](#makefile-targets)
* 17. [🔍 Troubleshooting](#-troubleshooting)
    * 17.1. [Diagnose the listener](#diagnose-the-listener)
    * 17.2. [Why localhost fails on Windows](#why-localhost-fails-on-windows)
        * 17.2.1. [Fix (Podman rootless)](#fix-podman-rootless)
        * 17.2.2. [Fix (Docker Desktop > 4.19)](#fix-docker-desktop--419)

<!-- vscode-markdown-toc-config
    numbering=true
    autoSave=true
    /vscode-markdown-toc-config -->
<!-- /vscode-markdown-toc -->

## 🚀 개요 & 목표

**MCP Gateway**는 [Model Context Protocol](https://modelcontextprotocol.io) (MCP) 서버와 REST API 앞단에 위치하여, AI 클라이언트를 위한 단일 통합 엔드포인트를 제공하는 게이트웨이/레지스트리/프록시입니다.

**⚠️ 주의**: 현재 릴리스(0.6.0)는 알파/얼리 베타 수준입니다. 프로덕션 용도로 사용하지 말고, 로컬 개발/테스트/실험 목적에 한해 사용하세요. 기능과 API, 동작은 예고 없이 변경될 수 있습니다. 프로덕션 배포 전에는 보안 검토와 추가 방어 체계를 반드시 갖추십시오. 대규모/멀티테넌트 운영에 필요한 항목 중 일부는 계속 [로드맵](https://ibm.github.io/mcp-context-forge/architecture/roadmap/)에 따라 발전 중입니다.

지원 기능:

* 다중 MCP/REST 서비스 연합(Federation)
* **A2A(Agent-to-Agent) 통합**: 외부 AI 에이전트(OpenAI, Anthropic, 커스텀) 연동
* 레거시 API의 MCP 가상화(툴/서버로 노출)
* 전송: HTTP/JSON-RPC/SSE(Keepalive)/stdio/Streamable HTTP
* 실시간 관리 UI(Admin), 구성/로그 모니터링
* 인증/재시도/레이트 리미팅 내장
* **OpenTelemetry 관측성**: Phoenix/Jaeger/Zipkin 등 OTLP 백엔드 연동
* 배포: Docker/PyPI, Redis 기반 캐시 및 멀티 클러스터 연합
* 헤더 패스스루(전역/게이트웨이별) 및 게이트웨이 OAuth 2.0
* Streamable HTTP 경로 리라이트(`/servers/<id>/mcp` → `/mcp`), 상태 비저장/상태 저장 세션
* JSONPath(`apijsonpath`) 기반 결과 가공(툴/리소스 목록/조회)
* 툴/리소스/프롬프트/서버 및 A2A 에이전트 메트릭(리셋 엔드포인트 포함)

![MCP Gateway Architecture](https://ibm.github.io/mcp-context-forge/images/mcpgateway.svg)

---

<details>
<summary><strong>🔌 프로토콜 유연성을 갖춘 게이트웨이 레이어</strong></summary>

* MCP 서버 또는 REST API 앞단에 배치
* MCP 프로토콜 버전 선택 가능(예: `2025-03-26`)
* 다양한 백엔드를 단일 인터페이스로 통합 노출

</details>

<details>
<summary><strong>🌐 피어 게이트웨이 연합(MCP 레지스트리)</strong></summary>

* 피어 게이트웨이 자동 검색(mDNS) 또는 수동 등록
* 헬스 체크 및 원격 레지스트리 병합
* Redis 기반 동기화와 장애 조치 지원

</details>

<details>
<summary><strong>🧩 REST/gRPC 서비스의 가상화</strong></summary>

* 비-MCP 서비스를 가상 MCP 서버로 래핑
* 최소 구성으로 툴/프롬프트/리소스 등록

</details>

<details>
<summary><strong>🔁 REST→MCP 툴 어댑터</strong></summary>

* REST API를 MCP 툴로 변환:

    * JSON 스키마 자동 추출
    * 헤더/토큰/커스텀 인증 지원
    * 재시도/타임아웃/레이트 리미트 정책

</details>

<details>
<summary><strong>🧠 통합 레지스트리</strong></summary>

* **Prompts**: Jinja2 템플릿, 멀티모달, 롤백/버저닝
* **Resources**: URI 기반 접근, MIME 판별, 캐싱, SSE 업데이트
* **Tools**: 네이티브/어댑티드, 입력 검증/동시성 제어

</details>

<details>
<summary><strong>📈 Admin UI, 관측성 & 개발 경험</strong></summary>

* HTMX + Alpine.js 기반 Admin UI
* 필터/검색/내보내기 가능한 실시간 로그 뷰어
* 인증: Basic/JWT/커스텀
* 구조화 로그, 헬스 엔드포인트, 메트릭
* 400+ 테스트, Makefile 타깃, 라이브 리로드, 프리커밋 훅

</details>

<details>
<summary><strong>🔍 OpenTelemetry 관측성</strong></summary>

* **벤더 중립 트레이싱**(OTLP 지원)
* **여러 백엔드**: Phoenix/Jaeger/Zipkin/Tempo/DataDog/New Relic
* **분산 트레이싱**: 연합 게이트웨이·서비스 간 연계
* **자동 계측**: 툴/프롬프트/리소스/게이트웨이 동작
* **LLM 메트릭**: 토큰/비용/모델 성능
* **비활성 시 오버헤드 제로**, 환경변수 기반 쉬운 설정

Quick start with Phoenix (LLM observability):

```bash
# Start Phoenix
docker run -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest

# Configure gateway
export OTEL_ENABLE_OBSERVABILITY=true
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Run gateway - traces automatically sent to Phoenix
mcpgateway
```

See [Observability Documentation](https://ibm.github.io/mcp-context-forge/manage/observability/) for detailed setup with other backends.

</details>

---

## 빠른 시작 - PyPI

MCP Gateway는 [PyPI](https://pypi.org/project/mcp-contextforge-gateway/)에 `mcp-contextforge-gateway` 패키지로 배포됩니다.

---

**요약 실행** ([uv](https://docs.astral.sh/uv/) 사용):

```bash
BASIC_AUTH_PASSWORD=pass \
MCPGATEWAY_UI_ENABLED=true \
MCPGATEWAY_ADMIN_API_ENABLED=true \
uvx --from mcp-contextforge-gateway mcpgateway --host 0.0.0.0 --port 4444
```

<details>
<summary><strong>📋 사전 준비물</strong></summary>

* **Python ≥ 3.10** (3.11 권장)
* **curl + jq** - 마지막 스모크 테스트 단계에서 사용

</details>

### 1 - 설치 & 실행(복붙용)

```bash
# 1️⃣  격리 환경 + PyPI 설치
mkdir mcpgateway && cd mcpgateway
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install mcp-contextforge-gateway

# 2️⃣  커스텀 자격/시크릿 키로 전체 인터페이스 바인딩
# Admin API 엔드포인트 활성화(기본 비활성)
export MCPGATEWAY_UI_ENABLED=true
export MCPGATEWAY_ADMIN_API_ENABLED=true

BASIC_AUTH_PASSWORD=pass JWT_SECRET_KEY=my-test-key \
  mcpgateway --host 0.0.0.0 --port 4444 &   # admin/pass

# 3️⃣  Bearer 토큰 생성 & API 스모크 테스트
export MCPGATEWAY_BEARER_TOKEN=$(python3 -m mcpgateway.utils.create_jwt_token \
    --username admin --exp 10080 --secret my-test-key)

curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://127.0.0.1:4444/version | jq
```

<details>
<summary><strong>Windows (PowerShell) 빠른 시작</strong></summary>

```powershell
# 1️⃣  격리 환경 + PyPI 설치
mkdir mcpgateway ; cd mcpgateway
python3 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install mcp-contextforge-gateway

# 2️⃣  환경변수 설정(세션 한정)
$Env:MCPGATEWAY_UI_ENABLED        = "true"
$Env:MCPGATEWAY_ADMIN_API_ENABLED = "true"
$Env:BASIC_AUTH_PASSWORD          = "changeme"      # admin/changeme
$Env:JWT_SECRET_KEY               = "my-test-key"

# 3️⃣  게이트웨이 실행
mcpgateway.exe --host 0.0.0.0 --port 4444

#   선택: 백그라운드 실행
# Start-Process -FilePath "mcpgateway.exe" -ArgumentList "--host 0.0.0.0 --port 4444"

# 4️⃣  Bearer 토큰 및 스모크 테스트
$Env:MCPGATEWAY_BEARER_TOKEN = python3 -m mcpgateway.utils.create_jwt_token `
    --username admin --exp 10080 --secret my-test-key

curl -s -H "Authorization: Bearer $Env:MCPGATEWAY_BEARER_TOKEN" `
     http://127.0.0.1:4444/version | jq
```

</details>

<details>
<summary><strong>추가 구성</strong></summary>

[.env.example](.env.example)을 `.env`로 복사한 뒤 값을 조정하거나, 환경변수로 설정하세요.

</details>

<details>
<summary><strong>🚀 E2E 데모(로컬 MCP 서버 등록)</strong></summary>

```bash
# 1️⃣  샘플 Go MCP 타임 서버 실행(translate + docker)
python3 -m mcpgateway.translate \
     --stdio "docker run --rm -i -p 8888:8080 ghcr.io/ibm/fast-time-server:latest -transport=stdio" \
     --expose-sse \
     --port 8003

# 또는 공식 mcp-server-git(uvx) 사용:
pip install uv # to install uvx, if not already installed
python3 -m mcpgateway.translate --stdio "uvx mcp-server-git" --expose-sse --port 9000

# 로컬 바이너리 직접 실행(대안)
# cd mcp-servers/go/fast-time-server; make build
# python3 -m mcpgateway.translate --stdio "./dist/fast-time-server -transport=stdio" --expose-sse --port 8002

# NEW: 여러 프로토콜 동시 노출
python3 -m mcpgateway.translate \
     --stdio "uvx mcp-server-git" \
     --expose-sse \
     --expose-streamable-http \
     --port 9000
# 이제 /sse(SSE)와 /mcp(Streamable HTTP)로 모두 접근 가능

# 2️⃣  게이트웨이에 등록
curl -s -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"fast_time","url":"http://localhost:9000/sse"}' \
     http://localhost:4444/gateways

# 3️⃣  툴 카탈로그 확인
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools | jq

# 4️⃣  위 툴들을 묶은 *가상 서버* 생성(3단계에서 확인한 툴 ID 사용)
curl -s -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"time_server","description":"Fast time tools","associatedTools":[<ID_OF_TOOLS>]}' \
     http://localhost:4444/servers | jq

# 예시 curl
curl -s -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN"
     -H "Content-Type: application/json"
     -d '{"name":"time_server","description":"Fast time tools","associatedTools":["6018ca46d32a4ac6b4c054c13a1726a2"]}' \
     http://localhost:4444/servers | jq

# 5️⃣  서버 목록(신규 가상 서버의 UUID 포함)
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/servers | jq

# 6️⃣  클라이언트 SSE 엔드포인트(MCP Inspector CLI 또는 임의의 MCP 클라이언트)
npx -y @modelcontextprotocol/inspector
# Transport Type: SSE, URL: http://localhost:4444/servers/UUID_OF_SERVER_1/sse,  Header Name: "Authorization", Bearer Token
```

</details>

<details>
<summary><strong>🖧 stdio 래퍼 사용(mcpgateway-wrapper)</strong></summary>

```bash
export MCP_AUTH=$MCPGATEWAY_BEARER_TOKEN
export MCP_SERVER_URL=http://localhost:4444/servers/UUID_OF_SERVER_1/mcp
python3 -m mcpgateway.wrapper  # Ctrl-C to exit
```

`uv` 또는 Docker/Podman 내에서도 실행할 수 있습니다(상단 컨테이너 섹션 참고).

MCP Inspector에서 `MCP_AUTH`, `MCP_SERVER_URL` 환경변수를 설정하고, Command는 `python3`, Arguments는 `-m mcpgateway.wrapper`로 지정하세요.

```bash
echo $PWD/.venv/bin/python3 # Using the Python3 full path ensures you have a working venv
export MCP_SERVER_URL='http://localhost:4444/servers/UUID_OF_SERVER_1/mcp'
export MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN}
npx -y @modelcontextprotocol/inspector
```

또는

환경변수 대신 인자로 URL과 인증값을 넘길 수도 있습니다.

```bash
npx -y @modelcontextprotocol/inspector
command as `python`
Arguments as `-m mcpgateway.wrapper --url "http://localhost:4444/servers/UUID_OF_SERVER_1/mcp" --auth "Bearer <your token>"`
```

When using a MCP Client such as Claude with stdio:

```json
{
  "mcpServers": {
    "mcpgateway-wrapper": {
      "command": "python",
      "args": ["-m", "mcpgateway.wrapper"],
      "env": {
        "MCP_AUTH": "your-token-here",
        "MCP_SERVER_URL": "http://localhost:4444/servers/UUID_OF_SERVER_1",
        "MCP_TOOL_CALL_TIMEOUT": "120"
      }
    }
  }
}
```

</details>

---

## 빠른 시작 - 컨테이너

GHCR의 공식 OCI 이미지를 **Docker** 또는 **Podman**으로 실행하세요.

---

### 🐳 Docker

#### 1 - 최소 실행 예시

```bash
docker run -d --name mcpgateway \
  -p 4444:4444 \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e HOST=0.0.0.0 \
  -e JWT_SECRET_KEY=my-test-key \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=changeme \
  -e AUTH_REQUIRED=true \
  -e DATABASE_URL=sqlite:///./mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0

# 로그 보기(Ctrl+C 종료)
docker logs -f mcpgateway

# API 키 생성
docker run --rm -it ghcr.io/ibm/mcp-context-forge:0.6.0 \
  python3 -m mcpgateway.utils.create_jwt_token --username admin --exp 0 --secret my-test-key
```

**[http://localhost:4444/admin](http://localhost:4444/admin)**로 접속(user `admin` / pass `changeme`).

#### 2 - SQLite 데이터베이스 영속화

```bash
mkdir -p $(pwd)/data

touch $(pwd)/data/mcp.db

sudo chown -R :docker $(pwd)/data

chmod 777 $(pwd)/data

docker run -d --name mcpgateway \
  --restart unless-stopped \
  -p 4444:4444 \
  -v $(pwd)/data:/data \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  -e HOST=0.0.0.0 \
  -e JWT_SECRET_KEY=my-test-key \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=changeme \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

호스트의 `./data/mcp.db`에 SQLite 파일이 저장됩니다.

#### 3 - 로컬 툴 디스커버리(host 네트워크)

```bash
mkdir -p $(pwd)/data

touch $(pwd)/data/mcp.db

sudo chown -R :docker $(pwd)/data

chmod 777 $(pwd)/data

docker run -d --name mcpgateway \
  --network=host \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e HOST=0.0.0.0 \
  -e PORT=4444 \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  -v $(pwd)/data:/data \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

`--network=host` 옵션은 컨테이너가 로컬 네트워크로 직접 접근하도록 하여, 호스트에서 실행 중인 MCP 서버를 등록할 수 있게 합니다. 자세한 내용은 [Docker Host network driver 문서](https://docs.docker.com/engine/network/drivers/host/)를 참고하세요.

---

### 🦭 Podman (루트리스 친화)

#### 1 - 기본 실행

```bash
podman run -d --name mcpgateway \
  -p 4444:4444 \
  -e HOST=0.0.0.0 \
  -e DATABASE_URL=sqlite:///./mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

#### 2 - SQLite 영속화

```bash
mkdir -p $(pwd)/data

touch $(pwd)/data/mcp.db

sudo chown -R :docker $(pwd)/data

chmod 777 $(pwd)/data

podman run -d --name mcpgateway \
  --restart=on-failure \
  -p 4444:4444 \
  -v $(pwd)/data:/data \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

#### 3 - Host 네트워킹(루트리스)

```bash
mkdir -p $(pwd)/data

touch $(pwd)/data/mcp.db

sudo chown -R :docker $(pwd)/data

chmod 777 $(pwd)/data

podman run -d --name mcpgateway \
  --network=host \
  -v $(pwd)/data:/data \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

---

<details>
<summary><strong>✏️ Docker/Podman tips</strong></summary>

* **.env files** - Put all the `-e FOO=` lines into a file and replace them with `--env-file .env`. See the provided [.env.example](.env.example) for reference.
* **Pinned tags** - Use an explicit version (e.g. `v0.6.0`) instead of `latest` for reproducible builds.
* **JWT tokens** - Generate one in the running container:

  ```bash
  docker exec mcpgateway python3 -m mcpgateway.utils.create_jwt_token -u admin -e 10080 --secret my-test-key
  ```

* **Upgrades** - Stop, remove, and rerun with the same `-v $(pwd)/data:/data` mount; your DB and config stay intact.

</details>

---

<details>
<summary><strong>🚑 Smoke-test the running container</strong></summary>

```bash
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/health | jq
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/tools | jq
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/version | jq
```

</details>

---

## 실전 가이드 - Docker로 MCP Gateway 운영하기

> 목적: 실제 환경에서 Docker로 게이트웨이를 띄우고, 여러 MCP 서버(stdio/SSE/Streamable HTTP, 다른 게이트웨이)를 등록해 툴 카탈로그로 묶은 뒤, MCP 클라이언트가 연결해 사용할 수 있도록 단계별로 안내합니다.

### ✅ 핵심 요점

- **컨테이너 인자에 MCP 서버 목록을 직접 넘기지 않습니다.**
- 게이트웨이를 먼저 띄운 뒤, **API로 `/gateways`에 MCP 서버를 등록**합니다.
- stdio만 있는 MCP 서버는 `mcpgateway.translate`로 **SSE/Streamable HTTP로 노출**한 다음 등록합니다.

### 0) 사전 준비

- Docker(또는 Podman)
- 포트 정책: 게이트웨이 4444, 각 MCP 서버 포트(예: 9000)
- 컨테이너에서 호스트로 접근이 필요하면 Linux에서 `--network=host` 또는 `--add-host=host.docker.internal:host-gateway` 사용

---

### 1) Gateway 컨테이너 실행(기본)

```bash
docker run -d --name mcpgateway \
  -p 4444:4444 \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e HOST=0.0.0.0 \
  -e JWT_SECRET_KEY=my-test-key \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=changeme \
  -e AUTH_REQUIRED=true \
  -e DATABASE_URL=sqlite:///./mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

- Web UI: `http://localhost:4444/admin` (기본 `admin/changeme`)
- Swagger: `http://localhost:4444/docs`

영속화(권장):

```bash
mkdir -p $(pwd)/data && touch $(pwd)/data/mcp.db && chmod 777 $(pwd)/data
docker run -d --name mcpgateway \
  --restart unless-stopped \
  -p 4444:4444 \
  -v $(pwd)/data:/data \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  -e HOST=0.0.0.0 \
  -e JWT_SECRET_KEY=my-test-key \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=changeme \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

로컬 MCP 서버에 직접 접근이 필요하면(host 네트워크):

```bash
docker run -d --name mcpgateway \
  --network=host \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e HOST=0.0.0.0 \
  -e PORT=4444 \
  -e DATABASE_URL=sqlite:////data/mcp.db \
  -v $(pwd)/data:/data \
  ghcr.io/ibm/mcp-context-forge:0.6.0
```

Docker Compose 예시:

```yaml
version: "3.9"
services:
  gateway:
    image: ghcr.io/ibm/mcp-context-forge:0.6.0
    container_name: mcpgateway
    ports:
      - "4444:4444"
    environment:
      MCPGATEWAY_UI_ENABLED: "true"
      MCPGATEWAY_ADMIN_API_ENABLED: "true"
      HOST: "0.0.0.0"
      JWT_SECRET_KEY: "my-test-key"
      BASIC_AUTH_USER: "admin"
      BASIC_AUTH_PASSWORD: "changeme"
      AUTH_REQUIRED: "true"
      DATABASE_URL: "sqlite:////data/mcp.db"
    volumes:
      - ./data:/data
    # Linux에서 호스트 접근이 필요하면 아래 중 하나 사용
    # network_mode: host
    # extra_hosts:
    #   - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

---

### 2) API 토큰 발급(JWT)

컨테이너 내부에서 발급:

```bash
docker exec mcpgateway python3 -m mcpgateway.utils.create_jwt_token \
  --username admin --exp 10080 --secret my-test-key
```

출력 값을 환경변수로 보관:

```bash
export MCPGATEWAY_BEARER_TOKEN="<위에서 출력된 토큰>"
```

헬스/버전 확인:

```bash
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/health
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/version | jq
```

---

### 3) stdio MCP 서버를 HTTP로 노출(translate)

stdio만 있는 MCP 서버를 **SSE**(필요 시 Streamable HTTP 포함)로 노출합니다.

```bash
# mcp-server-git 예시(uvx 필요)
python3 -m mcpgateway.translate \
  --stdio "uvx mcp-server-git" \
  --expose-sse \
  --port 9000
# → http://localhost:9000/sse 로 접근 가능
```

SSE와 Streamable HTTP 동시 노출:

```bash
python3 -m mcpgateway.translate \
  --stdio "uvx mcp-server-git" \
  --expose-sse \
  --expose-streamable-http \
  --port 9000
# → /sse, /mcp 둘 다 제공
```

컨테이너에서 접근 시:

- host 네트워크로 띄웠다면 그대로 `http://localhost:9000` 사용
- 그렇지 않다면 macOS/Windows: `http://host.docker.internal:9000`, Linux: `--add-host=host.docker.internal:host-gateway` 후 동일 URL 사용

---

### 4) MCP 서버 등록(`/gateways`)

게이트웨이에 등록하면 해당 서버의 툴/리소스/프롬프트가 통합 카탈로그로 병합됩니다.

```bash
# SSE 엔드포인트 등록
curl -s -X POST \
  -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"fast_time","url":"http://localhost:9000/sse"}' \
  http://localhost:4444/gateways

# 두 번째 MCP 서버(예: 9100/sse) 등록
curl -s -X POST \
  -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"tools_2","url":"http://localhost:9100/sse"}' \
  http://localhost:4444/gateways

# 다른 게이트웨이(피어 레지스트리) 등록
curl -s -X POST \
  -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"peer_registry","url":"http://peer-gateway:4444"}' \
  http://localhost:4444/gateways
```

등록 후 툴 확인:

```bash
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  http://localhost:4444/tools | jq
```

---

### 5) 가상 서버 생성(툴 묶음 → 하나의 MCP 서버처럼)

등록된 툴 ID를 확인한 뒤, 원하는 툴들을 하나의 "가상 서버"로 묶습니다.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"time_server",
        "description":"Fast time tools",
        "associatedTools":["<TOOL_ID_1>", "<TOOL_ID_2>"]
      }' \
  http://localhost:4444/servers | jq
```

서버 목록과 UUID 확인:

```bash
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
  http://localhost:4444/servers | jq
```

---

### 6) MCP 클라이언트 연결

- SSE: `http://localhost:4444/servers/<SERVER_UUID>/sse`
  - 헤더: `Authorization: Bearer <토큰>`
- Streamable HTTP: `http://localhost:4444/servers/<SERVER_UUID>/mcp`

MCP Inspector 예시:

```bash
npx -y @modelcontextprotocol/inspector
# Transport Type: SSE
# URL: http://localhost:4444/servers/<SERVER_UUID>/sse
# Header Name: Authorization
# Header Value: Bearer <MCPGATEWAY_BEARER_TOKEN>
```

stdio 전용 클라이언트를 위한 래퍼(`mcpgateway.wrapper`):

```bash
docker run --rm -i \
  -e MCP_AUTH=$MCPGATEWAY_BEARER_TOKEN \
  -e MCP_SERVER_URL=http://host.docker.internal:4444/servers/<SERVER_UUID>/mcp \
  ghcr.io/ibm/mcp-context-forge:0.6.0 \
  python3 -m mcpgateway.wrapper
```

---

### 7) 보안/운영 팁

- 프로덕션: `MCPGATEWAY_UI_ENABLED=false`, `MCPGATEWAY_ADMIN_API_ENABLED=false` 고려(관리면 분리)
- `JWT_SECRET_KEY`는 강력한 랜덤 값 사용, CORS `ALLOWED_ORIGINS` 명시
- 보안 헤더 유지(`SECURITY_HEADERS_ENABLED=true`), 필요 시 `X_FRAME_OPTIONS`/CSP 조정
- 관측성 필요 시 OTEL 환경변수 설정, 컨테이너 재시작: `--restart unless-stopped`
- 데이터는 볼륨(`-v $(pwd)/data:/data`)로 영속화

---

### 8) 트러블슈팅

- 401 Unauthorized: 토큰 생성 시 사용한 `JWT_SECRET_KEY`와 컨테이너 설정이 일치하는지 확인
- 로컬 MCP 서버 미검출: `--network=host` 또는 `host.docker.internal` 접근 경로 사용
- SSE keepalive 경고: 무시 가능, 필요 시 `SSE_KEEPALIVE_ENABLED=false`
- 포트 충돌: `docker ps` / `lsof -i :4444` 확인

---

### 9) 한 번에 따라 하기(최소 세트)

```bash
# 1) Gateway 실행
docker run -d --name mcpgateway -p 4444:4444 \
  -e MCPGATEWAY_UI_ENABLED=true \
  -e MCPGATEWAY_ADMIN_API_ENABLED=true \
  -e HOST=0.0.0.0 \
  -e JWT_SECRET_KEY=my-test-key \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=changeme \
  -e AUTH_REQUIRED=true \
  -e DATABASE_URL=sqlite:///./mcp.db \
  ghcr.io/ibm/mcp-context-forge:0.6.0

# 2) 토큰 발급
export MCPGATEWAY_BEARER_TOKEN=$(docker exec mcpgateway python3 -m mcpgateway.utils.create_jwt_token -u admin --exp 10080 --secret my-test-key)

# 3) stdio MCP 서버를 9000/sse로 노출(호스트에서)
python3 -m mcpgateway.translate --stdio "uvx mcp-server-git" --expose-sse --port 9000

# 4) 서버 등록
curl -s -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"fast_time","url":"http://localhost:9000/sse"}' \
  http://localhost:4444/gateways

# 5) 툴 확인 → 툴 ID 추출
curl -s -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools | jq

# 6) 가상 서버 생성(툴 ID 넣어주세요)
curl -s -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"time_server","description":"Fast time tools","associatedTools":["<TOOL_ID>"]}' \
  http://localhost:4444/servers | jq

# 7) 클라이언트 연결 (SSE)
# URL: http://localhost:4444/servers/<SERVER_UUID>/sse
# Header: Authorization: Bearer <MCPGATEWAY_BEARER_TOKEN>
```

> 여러 MCP 서버를 붙이려면 4번 `POST /gateways`를 서버 수만큼 반복하면 됩니다. 피어 게이트웨이도 같은 방식으로 `url`에 피어의 루트(`http://peer:4444` 등)를 넣어 등록하세요.

---

<details>
<summary><strong>🖧 Running the MCP Gateway stdio wrapper</strong></summary>

The `mcpgateway.wrapper` lets you connect to the gateway over **stdio** while keeping JWT authentication. You should run this from the MCP Client. The example below is just for testing.

```bash
# Set environment variables
export MCPGATEWAY_BEARER_TOKEN=$(python3 -m mcpgateway.utils.create_jwt_token --username admin --exp 10080 --secret my-test-key)
export MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN}
export MCP_SERVER_URL='http://localhost:4444/servers/UUID_OF_SERVER_1/mcp'
export MCP_TOOL_CALL_TIMEOUT=120
export MCP_WRAPPER_LOG_LEVEL=DEBUG  # or OFF to disable logging

docker run --rm -i \
  -e MCP_AUTH=$MCPGATEWAY_BEARER_TOKEN \
  -e MCP_SERVER_URL=http://host.docker.internal:4444/servers/UUID_OF_SERVER_1/mcp \
  -e MCP_TOOL_CALL_TIMEOUT=120 \
  -e MCP_WRAPPER_LOG_LEVEL=DEBUG \
  ghcr.io/ibm/mcp-context-forge:0.6.0 \
  python3 -m mcpgateway.wrapper
```

</details>

---

## `mcpgateway.wrapper` 수동 테스트

Wrapper는 stdin/stdout으로 JSON-RPC를 주고받으므로, 터미널 파이프만으로도 상호작용할 수 있습니다.

```bash
# MCP Gateway Wrapper 시작
export MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN}
export MCP_SERVER_URL=http://localhost:4444/servers/YOUR_SERVER_UUID
python3 -m mcpgateway.wrapper
```

<details>
<summary><strong>프로토콜 초기화</strong></summary>

```json
# 프로토콜 초기화 요청
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"demo","version":"0.0.1"}}}

# 응답 이후 알림 예시
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}

# 프롬프트 가져오기
{"jsonrpc":"2.0","id":4,"method":"prompts/list"}
{"jsonrpc":"2.0","id":5,"method":"prompts/get","params":{"name":"greeting","arguments":{"user":"Bob"}}}

# 리소스 가져오기
{"jsonrpc":"2.0","id":6,"method":"resources/list"}
{"jsonrpc":"2.0","id":7,"method":"resources/read","params":{"uri":"https://example.com/some.txt"}}

# 툴 목록/호출
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_system_time","arguments":{"timezone":"Europe/Dublin"}}}
```

</details>

<details>
<summary><strong>예상 응답 예시</strong></summary>

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"mcpgateway-wrapper","version":"0.6.0"}}}

# When there's no tools
{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}

# After you add some tools and create a virtual server
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"annotations":{"readOnlyHint":false,"destructiveHint":true,"idempotentHint":false,"openWorldHint":true},"description":"Convert time between different timezones","inputSchema":{"properties":{"source_timezone":{"description":"Source IANA timezone name","type":"string"},"target_timezone":{"description":"Target IANA timezone name","type":"string"},"time":{"description":"Time to convert in RFC3339 format or common formats like '2006-01-02 15:04:05'","type":"string"}},"required":["time","source_timezone","target_timezone"],"type":"object"},"name":"convert_time"},{"annotations":{"readOnlyHint":false,"destructiveHint":true,"idempotentHint":false,"openWorldHint":true},"description":"Get current system time in specified timezone","inputSchema":{"properties":{"timezone":{"description":"IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Defaults to UTC","type":"string"}},"type":"object"},"name":"get_system_time"}]}}

# Running the time tool:
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"2025-07-09T00:09:45+01:00"}]}}
```

</details>

### 🧩 MCP 클라이언트에서 실행(`mcpgateway.wrapper`)

The `mcpgateway.wrapper` exposes everything your Gateway knows about over **stdio**, so any MCP client that *can't* (or *shouldn't*) open an authenticated SSE stream still gets full tool-calling power.

> **Remember** to substitute your real Gateway URL (and server ID) for `http://localhost:4444/servers/UUID_OF_SERVER_1/mcp`.
> When inside Docker/Podman, that often becomes `http://host.docker.internal:4444/servers/UUID_OF_SERVER_1/mcp` (macOS/Windows) or the gateway container's hostname (Linux).

---

<details>
<summary><strong>🐳 Docker / Podman</strong></summary>

```bash
docker run -i --rm \
  --network=host \
  -e MCP_SERVER_URL=http://localhost:4444/servers/UUID_OF_SERVER_1/mcp \
  -e MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN} \
  -e MCP_TOOL_CALL_TIMEOUT=120 \
  ghcr.io/ibm/mcp-context-forge:0.6.0 \
  python3 -m mcpgateway.wrapper
```

</details>

---

<details>
<summary><strong>📦 pipx (one-liner install &amp; run)</strong></summary>

```bash
# Install gateway package in its own isolated venv
pipx install --include-deps mcp-contextforge-gateway

# Run the stdio wrapper
MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN} \
MCP_SERVER_URL=http://localhost:4444/servers/UUID_OF_SERVER_1/mcp \
python3 -m mcpgateway.wrapper
# Alternatively with uv
uv run --directory . -m mcpgateway.wrapper
```

**Claude Desktop JSON** (uses the host Python that pipx injected):

```json
{
  "mcpServers": {
    "mcpgateway-wrapper": {
      "command": "python3",
      "args": ["-m", "mcpgateway.wrapper"],
      "env": {
        "MCP_AUTH": "<your-token>",
        "MCP_SERVER_URL": "http://localhost:4444/servers/UUID_OF_SERVER_1/mcp",
        "MCP_TOOL_CALL_TIMEOUT": "120"
      }
    }
  }
}
```

</details>

---

<details>
<summary><strong>⚡ uv / uvx (light-speed venvs)</strong></summary>

#### 1 - Install <code>uv</code>  (<code>uvx</code> is an alias it provides)

```bash
# (a) official one-liner
curl -Ls https://astral.sh/uv/install.sh | sh

# (b) or via pipx
pipx install uv
```

#### 2 - Create an on-the-spot venv & run the wrapper

```bash
# Create venv in ~/.venv/mcpgateway (or current dir if you prefer)
uv venv ~/.venv/mcpgateway
source ~/.venv/mcpgateway/bin/activate

# Install the gateway package using uv
uv pip install mcp-contextforge-gateway

# Launch wrapper
MCP_AUTH=${MCPGATEWAY_BEARER_TOKEN} \
MCP_SERVER_URL=http://localhost:4444/servers/UUID_OF_SERVER_1/mcp \
uv run --directory . -m mcpgateway.wrapper # Use this just for testing, as the Client will run the uv command
```

#### Claude Desktop JSON (runs through **uvx**)

```json
{
  "mcpServers": {
    "mcpgateway-wrapper": {
      "command": "uvx",
      "args": [
        "run",
        "--",
        "python",
        "-m",
        "mcpgateway.wrapper"
      ],
      "env": {
        "MCP_AUTH": "<your-token>",
        "MCP_SERVER_URL": "http://localhost:4444/servers/UUID_OF_SERVER_1/mcp"
    }
  }
}
```

</details>

---

### 🚀 Using with Claude Desktop (or any GUI MCP client)

1. **Edit Config** → `File ▸ Settings ▸ Developer ▸ Edit Config`
2. Paste one of the JSON blocks above (Docker / pipx / uvx).
3. Restart the app so the new stdio server is spawned.
4. Open logs in the same menu to verify `mcpgateway-wrapper` started and listed your tools.

Need help? See:

* **MCP Debugging Guide** - [https://modelcontextprotocol.io/docs/tools/debugging](https://modelcontextprotocol.io/docs/tools/debugging)

---

## Quick Start (manual install)

### Prerequisites

* **Python ≥ 3.10**
* **GNU Make** (optional, but all common workflows are available as Make targets)
* Optional: **Docker / Podman** for containerized runs

### One-liner (dev)

```bash
make venv install serve
```

What it does:

1. Creates / activates a `.venv` in your home folder `~/.venv/mcpgateway`
2. Installs the gateway and necessary dependencies
3. Launches **Gunicorn** (Uvicorn workers) on [http://localhost:4444](http://localhost:4444)

For development, you can use:

```bash
make install-dev # Install development dependencies, ex: linters and test harness
make lint          # optional: run style checks (ruff, mypy, etc.)
```

### Containerized (self-signed TLS)

## Container Runtime Support

This project supports both Docker and Podman. The Makefile automatically detects
which runtime is available and handles image naming differences.

### Auto-detection

```bash
make container-build  # Uses podman if available, otherwise docker

> You can use docker or podman, ex:

```bash
make podman            # build production image
make podman-run-ssl    # run at https://localhost:4444
# or listen on port 4444 on your host directly, adds --network=host to podman
make podman-run-ssl-host
```

### Smoke-test the API

```bash
curl -k -sX GET \
     -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     https://localhost:4444/tools | jq
```

You should receive `[]` until you register a tool.

---

## Installation

### Via Make

```bash
make venv install          # create .venv + install deps
make serve                 # gunicorn on :4444
```

### UV (alternative)

```bash
uv venv && source .venv/bin/activate
uv pip install -e '.[dev]' # IMPORTANT: in zsh, quote to disable glob expansion!
```

### pip (alternative)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Optional (PostgreSQL adapter)

You can configure the gateway with SQLite, PostgreSQL (or any other compatible database) in .env.

When using PostgreSQL, you need to install `psycopg2` driver.

```bash
uv pip install psycopg2-binary   # dev convenience
# or
uv pip install psycopg2          # production build
```

#### Quick Postgres container

```bash
docker run --name mcp-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=mysecretpassword \
  -e POSTGRES_DB=mcp \
  -p 5432:5432 -d postgres
```

A `make compose-up` target is provided along with a [docker-compose.yml](docker-compose.yml) file to make this process simpler.

---

## Configuration (`.env` or env vars)

> ⚠️ If any required `.env` variable is missing or invalid, the gateway will fail fast at startup with a validation error via Pydantic.

You can get started by copying the provided [.env.example](.env.example) to `.env` and making the necessary edits to fit your environment.

<details>
<summary><strong>🔧 Environment Configuration Variables</strong></summary>

### Basic

| Setting         | Description                              | Default                | Options                |
| --------------- | ---------------------------------------- | ---------------------- | ---------------------- |
| `APP_NAME`      | Gateway / OpenAPI title                  | `MCP Gateway`          | string                 |
| `HOST`          | Bind address for the app                 | `127.0.0.1`            | IPv4/IPv6              |
| `PORT`          | Port the server listens on               | `4444`                 | 1-65535                |
| `DATABASE_URL`  | SQLAlchemy connection URL                | `sqlite:///./mcp.db`   | any SQLAlchemy dialect |
| `APP_ROOT_PATH` | Subpath prefix for app (e.g. `/gateway`) | (empty)                | string                 |
| `TEMPLATES_DIR` | Path to Jinja2 templates                 | `mcpgateway/templates` | path                   |
| `STATIC_DIR`    | Path to static files                     | `mcpgateway/static`    | path                   |

> 💡 Use `APP_ROOT_PATH=/foo` if reverse-proxying under a subpath like `https://host.com/foo/`.

### Authentication

| Setting               | Description                                                      | Default       | Options    |
| --------------------- | ---------------------------------------------------------------- | ------------- | ---------- |
| `BASIC_AUTH_USER`     | Username for Admin UI login and HTTP Basic authentication        | `admin`       | string     |
| `BASIC_AUTH_PASSWORD` | Password for Admin UI login and HTTP Basic authentication        | `changeme`    | string     |
| `AUTH_REQUIRED`       | Require authentication for all API routes                        | `true`        | bool       |
| `JWT_SECRET_KEY`      | Secret key used to **sign JWT tokens** for API access            | `my-test-key` | string     |
| `JWT_ALGORITHM`       | Algorithm used to sign the JWTs (`HS256` is default, HMAC-based) | `HS256`       | PyJWT algs |
| `TOKEN_EXPIRY`        | Expiry of generated JWTs in minutes                              | `10080`       | int > 0    |
| `AUTH_ENCRYPTION_SECRET` | Passphrase used to derive AES key for encrypting tool auth headers | `my-test-salt` | string |

> 🔐 `BASIC_AUTH_USER`/`PASSWORD` are used for:
>
> * Logging into the web-based Admin UI
> * Accessing APIs via Basic Auth (`curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN"`)
>
> 🔑 `JWT_SECRET_KEY` is used to:
>
> * Sign JSON Web Tokens (`Authorization: Bearer <token>`)
> * Generate tokens via:
>
>   ```bash
>   export MCPGATEWAY_BEARER_TOKEN=$(python3 -m mcpgateway.utils.create_jwt_token --username admin --exp 0 --secret my-test-key)
>   echo $MCPGATEWAY_BEARER_TOKEN
>   ```
>
> * Tokens allow non-interactive API clients to authenticate securely.
>
> 🧪 Set `AUTH_REQUIRED=false` during development if you want to disable all authentication (e.g. for local testing or open APIs) or clients that don't support SSE authentication.
> In production, you should use the SSE to stdio `mcpgateway-wrapper` for such tools that don't support authenticated SSE, while still ensuring the gateway uses authentication.
>
> 🔐 `AUTH_ENCRYPTION_SECRET` is used to encrypt and decrypt tool authentication credentials (`auth_value`).
> You must set the same value across environments to decode previously stored encrypted auth values.
> Recommended: use a long, random string.

### UI Features

| Setting                        | Description                            | Default | Options |
| ------------------------------ | -------------------------------------- | ------- | ------- |
| `MCPGATEWAY_UI_ENABLED`        | Enable the interactive Admin dashboard | `false` | bool    |
| `MCPGATEWAY_ADMIN_API_ENABLED` | Enable API endpoints for admin ops     | `false` | bool    |
| `MCPGATEWAY_BULK_IMPORT_ENABLED` | Enable bulk import endpoint for tools | `true`  | bool    |

> 🖥️ Set both UI and Admin API to `false` to disable management UI and APIs in production.
> 📥 The bulk import endpoint allows importing up to 200 tools in a single request via `/admin/tools/import`.

### A2A (Agent-to-Agent) Features

| Setting                        | Description                            | Default | Options |
| ------------------------------ | -------------------------------------- | ------- | ------- |
| `MCPGATEWAY_A2A_ENABLED`       | Enable A2A agent features             | `true`  | bool    |
| `MCPGATEWAY_A2A_MAX_AGENTS`    | Maximum number of A2A agents allowed  | `100`   | int     |
| `MCPGATEWAY_A2A_DEFAULT_TIMEOUT` | Default timeout for A2A HTTP requests (seconds) | `30` | int |
| `MCPGATEWAY_A2A_MAX_RETRIES`   | Maximum retry attempts for A2A calls  | `3`     | int     |
| `MCPGATEWAY_A2A_METRICS_ENABLED` | Enable A2A agent metrics collection | `true`  | bool    |

> 🤖 **A2A Integration**: Register external AI agents (OpenAI, Anthropic, custom) and expose them as MCP tools
> 📊 **Metrics**: Track agent performance, success rates, and response times
> 🔒 **Security**: Encrypted credential storage and configurable authentication
> 🎛️ **Admin UI**: Dedicated tab for agent management with test functionality

**A2A Configuration Effects:**

* `MCPGATEWAY_A2A_ENABLED=false`: Completely disables A2A features (API endpoints return 404, admin tab hidden)
* `MCPGATEWAY_A2A_METRICS_ENABLED=false`: Disables metrics collection while keeping functionality

### Security

| Setting                   | Description                    | Default                                        | Options    |
| ------------------------- | ------------------------------ | ---------------------------------------------- | ---------- |
| `SKIP_SSL_VERIFY`         | Skip upstream TLS verification | `false`                                        | bool       |
| `ENVIRONMENT`             | Deployment environment (affects security defaults) | `development`                              | `development`/`production` |
| `APP_DOMAIN`              | Domain for production CORS origins | `localhost`                                 | string     |
| `ALLOWED_ORIGINS`         | CORS allow-list                | Auto-configured by environment                 | JSON array |
| `CORS_ENABLED`            | Enable CORS                    | `true`                                         | bool       |
| `CORS_ALLOW_CREDENTIALS`  | Allow credentials in CORS      | `true`                                         | bool       |
| `SECURE_COOKIES`          | Force secure cookie flags     | `true`                                         | bool       |
| `COOKIE_SAMESITE`         | Cookie SameSite attribute      | `lax`                                          | `strict`/`lax`/`none` |
| `SECURITY_HEADERS_ENABLED` | Enable security headers middleware | `true`                                     | bool       |
| `X_FRAME_OPTIONS`         | X-Frame-Options header value   | `DENY`                                         | `DENY`/`SAMEORIGIN` |
| `HSTS_ENABLED`            | Enable HSTS header             | `true`                                         | bool       |
| `HSTS_MAX_AGE`            | HSTS max age in seconds        | `31536000`                                     | int        |
| `REMOVE_SERVER_HEADERS`   | Remove server identification   | `true`                                         | bool       |
| `DOCS_ALLOW_BASIC_AUTH`   | Allow Basic Auth for docs (in addition to JWT)         | `false`                                        | bool       |

> **CORS Configuration**: When `ENVIRONMENT=development`, CORS origins are automatically configured for common development ports (3000, 8080, gateway port). In production, origins are constructed from `APP_DOMAIN` (e.g., `https://yourdomain.com`, `https://app.yourdomain.com`). You can override this by explicitly setting `ALLOWED_ORIGINS`.
>
> **Security Headers**: The gateway automatically adds configurable security headers to all responses including CSP, X-Frame-Options, X-Content-Type-Options, X-Download-Options, and HSTS (on HTTPS). All headers can be individually enabled/disabled. Sensitive server headers are removed.
>
> **iframe Embedding**: By default, `X-Frame-Options: DENY` prevents iframe embedding for security. To allow embedding, set `X_FRAME_OPTIONS=SAMEORIGIN` (same domain) or disable with `X_FRAME_OPTIONS=""`. Also update CSP `frame-ancestors` directive if needed.
>
> **Cookie Security**: Authentication cookies are automatically configured with HttpOnly, Secure (in production), and SameSite attributes for CSRF protection.
>
> Note: do not quote the ALLOWED_ORIGINS values, this needs to be valid JSON, such as:
> ALLOWED_ORIGINS=["http://localhost", "http://localhost:4444"]
>
> Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are always protected by authentication.
> By default, they require Bearer token authentication. Setting `DOCS_ALLOW_BASIC_AUTH=true` enables HTTP Basic Authentication as an additional method using the same credentials as `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD`.

### Logging

MCP Gateway provides flexible logging with **stdout/stderr output by default** and **optional file-based logging**. When file logging is enabled, it provides JSON formatting for structured logs and text formatting for console output.

| Setting                 | Description                        | Default           | Options                    |
| ----------------------- | ---------------------------------- | ----------------- | -------------------------- |
| `LOG_LEVEL`             | Minimum log level                  | `INFO`            | `DEBUG`...`CRITICAL`       |
| `LOG_FORMAT`            | Console log format                 | `json`            | `json`, `text`             |
| `LOG_TO_FILE`           | **Enable file logging**            | **`false`**       | **`true`, `false`**        |
| `LOG_FILE`              | Log filename (when enabled)        | `null`            | `mcpgateway.log`           |
| `LOG_FOLDER`            | Directory for log files            | `null`            | `logs`, `/var/log/gateway` |
| `LOG_FILEMODE`          | File write mode                    | `a+`              | `a+` (append), `w` (overwrite)|
| `LOG_ROTATION_ENABLED`  | **Enable log file rotation**       | **`false`**       | **`true`, `false`**        |
| `LOG_MAX_SIZE_MB`       | Max file size before rotation (MB) | `1`               | Any positive integer       |
| `LOG_BACKUP_COUNT`      | Number of backup files to keep     | `5`               | Any non-negative integer   |

**Logging Behavior:**

* **Default**: Logs only to **stdout/stderr** with human-readable text format
* **File Logging**: When `LOG_TO_FILE=true`, logs to **both** file (JSON format) and console (text format)
* **Log Rotation**: When `LOG_ROTATION_ENABLED=true`, files rotate at `LOG_MAX_SIZE_MB` with `LOG_BACKUP_COUNT` backup files (e.g., `.log.1`, `.log.2`)
* **Directory Creation**: Log folder is automatically created if it doesn't exist
* **Centralized Service**: All modules use the unified `LoggingService` for consistent formatting

**Example Configurations:**

```bash
# Default: stdout/stderr only (recommended for containers)
LOG_LEVEL=INFO
# No additional config needed - logs to stdout/stderr

# Optional: Enable file logging (no rotation)
LOG_TO_FILE=true
LOG_FOLDER=/var/log/mcpgateway
LOG_FILE=gateway.log
LOG_FILEMODE=a+

# Optional: Enable file logging with rotation
LOG_TO_FILE=true
LOG_ROTATION_ENABLED=true
LOG_MAX_SIZE_MB=10
LOG_BACKUP_COUNT=3
LOG_FOLDER=/var/log/mcpgateway
LOG_FILE=gateway.log
```

**Default Behavior:**

* Logs are written **only to stdout/stderr** in human-readable text format
* File logging is **disabled by default** (no files created)
* Set `LOG_TO_FILE=true` to enable optional file logging with JSON format

### Observability (OpenTelemetry)

MCP Gateway includes **vendor-agnostic OpenTelemetry support** for distributed tracing. Works with Phoenix, Jaeger, Zipkin, Tempo, DataDog, New Relic, and any OTLP-compatible backend.

| Setting                         | Description                                    | Default               | Options                                    |
| ------------------------------- | ---------------------------------------------- | --------------------- | ------------------------------------------ |
| `OTEL_ENABLE_OBSERVABILITY`     | Master switch for observability               | `true`                | `true`, `false`                           |
| `OTEL_SERVICE_NAME`             | Service identifier in traces                   | `mcp-gateway`         | string                                     |
| `OTEL_SERVICE_VERSION`          | Service version in traces                      | `0.6.0`               | string                                     |
| `OTEL_DEPLOYMENT_ENVIRONMENT`   | Environment tag (dev/staging/prod)            | `development`         | string                                     |
| `OTEL_TRACES_EXPORTER`          | Trace exporter backend                         | `otlp`                | `otlp`, `jaeger`, `zipkin`, `console`, `none` |
| `OTEL_RESOURCE_ATTRIBUTES`      | Custom resource attributes                     | (empty)               | `key=value,key2=value2`                   |

**OTLP Configuration** (for Phoenix, Tempo, DataDog, etc.):

| Setting                         | Description                                    | Default               | Options                                    |
| ------------------------------- | ---------------------------------------------- | --------------------- | ------------------------------------------ |
| `OTEL_EXPORTER_OTLP_ENDPOINT`   | OTLP collector endpoint                        | (none)                | `http://localhost:4317`                   |
| `OTEL_EXPORTER_OTLP_PROTOCOL`   | OTLP protocol                                  | `grpc`                | `grpc`, `http/protobuf`                   |
| `OTEL_EXPORTER_OTLP_HEADERS`    | Authentication headers                         | (empty)               | `api-key=secret,x-auth=token`             |
| `OTEL_EXPORTER_OTLP_INSECURE`   | Skip TLS verification                          | `true`                | `true`, `false`                           |

**Alternative Backends** (optional):

| Setting                         | Description                                    | Default               | Options                                    |
| ------------------------------- | ---------------------------------------------- | --------------------- | ------------------------------------------ |
| `OTEL_EXPORTER_JAEGER_ENDPOINT` | Jaeger collector endpoint                      | `http://localhost:14268/api/traces` | URL                             |
| `OTEL_EXPORTER_ZIPKIN_ENDPOINT` | Zipkin collector endpoint                      | `http://localhost:9411/api/v2/spans` | URL                            |

**Performance Tuning**:

| Setting                         | Description                                    | Default               | Options                                    |
| ------------------------------- | ---------------------------------------------- | --------------------- | ------------------------------------------ |
| `OTEL_TRACES_SAMPLER`           | Sampling strategy                              | `parentbased_traceidratio` | `always_on`, `always_off`, `traceidratio` |
| `OTEL_TRACES_SAMPLER_ARG`       | Sample rate (0.0-1.0)                         | `0.1`                 | float (0.1 = 10% sampling)                |
| `OTEL_BSP_MAX_QUEUE_SIZE`       | Max queued spans                              | `2048`                | int > 0                                    |
| `OTEL_BSP_MAX_EXPORT_BATCH_SIZE`| Max batch size for export                     | `512`                 | int > 0                                    |
| `OTEL_BSP_SCHEDULE_DELAY`       | Export interval (ms)                          | `5000`                | int > 0                                    |

**Quick Start with Phoenix**:

```bash
# Start Phoenix for LLM observability
docker run -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest

# Configure gateway
export OTEL_ENABLE_OBSERVABILITY=true
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Run gateway - traces automatically sent to Phoenix
mcpgateway
```

> 🔍 **What Gets Traced**: Tool invocations, prompt rendering, resource fetching, gateway federation, health checks, plugin execution (if enabled)
>
> 🚀 **Zero Overhead**: When `OTEL_ENABLE_OBSERVABILITY=false`, all tracing is disabled with no performance impact
>
> 📊 **View Traces**: Phoenix UI at `http://localhost:6006`, Jaeger at `http://localhost:16686`, or your configured backend

### Transport

| Setting                   | Description                        | Default | Options                         |
| ------------------------- | ---------------------------------- | ------- | ------------------------------- |
| `TRANSPORT_TYPE`          | Enabled transports                 | `all`   | `sse`,`streamablehttp`,`http`,`all` |
| `WEBSOCKET_PING_INTERVAL` | WebSocket ping (secs)              | `30`    | int > 0                         |
| `SSE_RETRY_TIMEOUT`       | SSE retry timeout (ms)             | `5000`  | int > 0                         |
| `SSE_KEEPALIVE_ENABLED`   | Enable SSE keepalive events        | `true`  | bool                            |
| `SSE_KEEPALIVE_INTERVAL`  | SSE keepalive interval (secs)      | `30`    | int > 0                         |
| `USE_STATEFUL_SESSIONS`   | streamable http config             | `false` | bool                            |
| `JSON_RESPONSE_ENABLED`   | json/sse streams (streamable http) | `true`  | bool                            |

> **💡 SSE Keepalive Events**: The gateway sends periodic keepalive events to prevent connection timeouts with proxies and load balancers. Disable with `SSE_KEEPALIVE_ENABLED=false` if your client doesn't handle unknown event types. Common intervals: 30s (default), 60s (AWS ALB), 240s (Azure).

### Federation

| Setting                    | Description            | Default | Options    |
| -------------------------- | ---------------------- | ------- | ---------- |
| `FEDERATION_ENABLED`       | Enable federation      | `true`  | bool       |
| `FEDERATION_DISCOVERY`     | Auto-discover peers    | `false` | bool       |
| `FEDERATION_PEERS`         | Comma-sep peer URLs    | `[]`    | JSON array |
| `FEDERATION_TIMEOUT`       | Gateway timeout (secs) | `30`    | int > 0    |
| `FEDERATION_SYNC_INTERVAL` | Sync interval (secs)   | `300`   | int > 0    |

### Resources

| Setting               | Description           | Default    | Options    |
| --------------------- | --------------------- | ---------- | ---------- |
| `RESOURCE_CACHE_SIZE` | LRU cache size        | `1000`     | int > 0    |
| `RESOURCE_CACHE_TTL`  | Cache TTL (seconds)   | `3600`     | int > 0    |
| `MAX_RESOURCE_SIZE`   | Max resource bytes    | `10485760` | int > 0    |
| `ALLOWED_MIME_TYPES`  | Acceptable MIME types | see code   | JSON array |

### Tools

| Setting                 | Description                    | Default | Options |
| ----------------------- | ------------------------------ | ------- | ------- |
| `TOOL_TIMEOUT`          | Tool invocation timeout (secs) | `60`    | int > 0 |
| `MAX_TOOL_RETRIES`      | Max retry attempts             | `3`     | int ≥ 0 |
| `TOOL_RATE_LIMIT`       | Tool calls per minute          | `100`   | int > 0 |
| `TOOL_CONCURRENT_LIMIT` | Concurrent tool invocations    | `10`    | int > 0 |

### Prompts

| Setting                 | Description                      | Default  | Options |
| ----------------------- | -------------------------------- | -------- | ------- |
| `PROMPT_CACHE_SIZE`     | Cached prompt templates          | `100`    | int > 0 |
| `MAX_PROMPT_SIZE`       | Max prompt template size (bytes) | `102400` | int > 0 |
| `PROMPT_RENDER_TIMEOUT` | Jinja render timeout (secs)      | `10`     | int > 0 |

### Health Checks

| Setting                 | Description                               | Default | Options |
| ----------------------- | ----------------------------------------- | ------- | ------- |
| `HEALTH_CHECK_INTERVAL` | Health poll interval (secs)               | `60`    | int > 0 |
| `HEALTH_CHECK_TIMEOUT`  | Health request timeout (secs)             | `10`    | int > 0 |
| `UNHEALTHY_THRESHOLD`   | Fail-count before peer deactivation,      | `3`     | int > 0 |
|                         | Set to -1 if deactivation is not needed.  |         |         |

### Database

| Setting                 | Description                     | Default | Options |
| ----------------------- | ------------------------------- | ------- | ------- |
| `DB_POOL_SIZE`   .      | SQLAlchemy connection pool size | `200`   | int > 0 |
| `DB_MAX_OVERFLOW`.      | Extra connections beyond pool   | `10`    | int ≥ 0 |
| `DB_POOL_TIMEOUT`.      | Wait for connection (secs)      | `30`    | int > 0 |
| `DB_POOL_RECYCLE`.      | Recycle connections (secs)      | `3600`  | int > 0 |
| `DB_MAX_RETRIES` .      | Max Retry Attempts              | `3`     | int > 0 |
| `DB_RETRY_INTERVAL_MS`  | Retry Interval (ms)             | `2000`  | int > 0 |

### Cache Backend

| Setting                   | Description                | Default  | Options                  |
| ------------------------- | -------------------------- | -------- | ------------------------ |
| `CACHE_TYPE`              | Backend (`memory`/`redis`) | `memory` | `none`, `memory`,`redis` |
| `REDIS_URL`               | Redis connection URL       | (none)   | string or empty          |
| `CACHE_PREFIX`            | Key prefix                 | `mcpgw:` | string                   |
| `REDIS_MAX_RETRIES`       | Max Retry Attempts         | `3`      | int > 0                  |
| `REDIS_RETRY_INTERVAL_MS` | Retry Interval (ms)        | `2000`   | int > 0                  |

> 🧠 `none` disables caching entirely. Use `memory` for dev, `database` for persistence, or `redis` for distributed caching.

### Database Management

MCP Gateway uses Alembic for database migrations. Common commands:

* `make db-current` - Show current database version
* `make db-upgrade` - Apply pending migrations
* `make db-migrate` - Create new migration
* `make db-history` - Show migration history
* `make db-status` - Detailed migration status

#### Troubleshooting

**Common Issues:**

* **"No 'script_location' key found"**: Ensure you're running from the project root directory.

* **"Unknown SSE event: keepalive" warnings**: Some MCP clients don't recognize keepalive events. These warnings are harmless and don't affect functionality. To disable: `SSE_KEEPALIVE_ENABLED=false`

* **Connection timeouts with proxies/load balancers**: If experiencing timeouts, adjust keepalive interval to match your infrastructure: `SSE_KEEPALIVE_INTERVAL=60` (AWS ALB) or `240` (Azure).

### Development

| Setting    | Description            | Default | Options |
| ---------- | ---------------------- | ------- | ------- |
| `DEV_MODE` | Enable dev mode        | `false` | bool    |
| `RELOAD`   | Auto-reload on changes | `false` | bool    |
| `DEBUG`    | Debug logging          | `false` | bool    |

</details>

---

## Running

### Makefile

```bash
 make serve               # Run production Gunicorn server on
 make serve-ssl           # Run Gunicorn behind HTTPS on :4444 (uses ./certs)
```

### Script helper

To run the development (uvicorn) server:

```bash
make dev
# or
./run.sh --reload --log debug --workers 2
```

> `run.sh` is a wrapper around `uvicorn` that loads `.env`, supports reload, and passes arguments to the server.

Key flags:

| Flag             | Purpose          | Example            |
| ---------------- | ---------------- | ------------------ |
| `-e, --env FILE` | load env-file    | `--env prod.env`   |
| `-H, --host`     | bind address     | `--host 127.0.0.1` |
| `-p, --port`     | listen port      | `--port 8080`      |
| `-w, --workers`  | gunicorn workers | `--workers 4`      |
| `-r, --reload`   | auto-reload      | `--reload`         |

### Manual (Uvicorn)

```bash
uvicorn mcpgateway.main:app --host 0.0.0.0 --port 4444 --workers 4
```

---

## Authentication examples

```bash
# Generate a JWT token using JWT_SECRET_KEY and export it as MCPGATEWAY_BEARER_TOKEN
# Note that the module needs to be installed. If running locally use:
export MCPGATEWAY_BEARER_TOKEN=$(JWT_SECRET_KEY=my-test-key python3 -m mcpgateway.utils.create_jwt_token)

# Use the JWT token in an API call
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools
```

---

## ☁️ AWS / Azure / OpenShift

Deployment details can be found in the GitHub Pages.

## ☁️ IBM Cloud Code Engine Deployment

This project supports deployment to [IBM Cloud Code Engine](https://cloud.ibm.com/codeengine) using the **ibmcloud** CLI and the IBM Container Registry.

<details>
<summary><strong>☁️ IBM Cloud Code Engine Deployment</strong></summary>

### 🔧 Prerequisites

* Podman **or** Docker installed locally
* IBM Cloud CLI (use `make ibmcloud-cli-install` to install)
* An [IBM Cloud API key](https://cloud.ibm.com/iam/apikeys) with access to Code Engine & Container Registry
* Code Engine and Container Registry services **enabled** in your IBM Cloud account

---

### 📦 Environment Variables

Create a **`.env`** file (or export the variables in your shell).
The first block is **required**; the second provides **tunable defaults** you can override:

```bash
# ── Required ─────────────────────────────────────────────
IBMCLOUD_REGION=us-south
IBMCLOUD_RESOURCE_GROUP=default
IBMCLOUD_PROJECT=my-codeengine-project
IBMCLOUD_CODE_ENGINE_APP=mcpgateway
IBMCLOUD_IMAGE_NAME=us.icr.io/myspace/mcpgateway:latest
IBMCLOUD_IMG_PROD=mcpgateway/mcpgateway
IBMCLOUD_API_KEY=your_api_key_here   # Optional - omit to use interactive `ibmcloud login --sso`

# ── Optional overrides (sensible defaults provided) ──────
IBMCLOUD_CPU=1                       # vCPUs for the app
IBMCLOUD_MEMORY=4G                   # Memory allocation
IBMCLOUD_REGISTRY_SECRET=my-regcred  # Name of the Container Registry secret
```

> ✅ **Quick check:** `make ibmcloud-check-env`

---

### 🚀 Make Targets

| Target                      | Purpose                                                                   |
| --------------------------- | ------------------------------------------------------------------------- |
| `make ibmcloud-cli-install` | Install IBM Cloud CLI and required plugins                                |
| `make ibmcloud-login`       | Log in to IBM Cloud (API key or SSO)                                      |
| `make ibmcloud-ce-login`    | Select the Code Engine project & region                                   |
| `make ibmcloud-tag`         | Tag the local container image                                             |
| `make ibmcloud-push`        | Push the image to IBM Container Registry                                  |
| `make ibmcloud-deploy`      | **Create or update** the Code Engine application (uses CPU/memory/secret) |
| `make ibmcloud-ce-status`   | Show current deployment status                                            |
| `make ibmcloud-ce-logs`     | Stream logs from the running app                                          |
| `make ibmcloud-ce-rm`       | Delete the Code Engine application                                        |

---

### 📝 Example Workflow

```bash
make ibmcloud-check-env
make ibmcloud-cli-install
make ibmcloud-login
make ibmcloud-ce-login
make ibmcloud-tag
make ibmcloud-push
make ibmcloud-deploy
make ibmcloud-ce-status
make ibmcloud-ce-logs
```

</details>

---

## API Endpoints

You can test the API endpoints through curl, or Swagger UI, and check detailed documentation on ReDoc:

* **Swagger UI** → [http://localhost:4444/docs](http://localhost:4444/docs)
* **ReDoc**    → [http://localhost:4444/redoc](http://localhost:4444/redoc)

Generate an API Bearer token, and test the various API endpoints.

<details>
<summary><strong>🔐 Authentication & Health Checks</strong></summary>

```bash
# Generate a bearer token using the configured secret key (use the same as your .env)
export MCPGATEWAY_BEARER_TOKEN=$(python3 -m mcpgateway.utils.create_jwt_token -u admin --secret my-test-key)
echo ${MCPGATEWAY_BEARER_TOKEN}

# Quickly confirm that authentication works and the gateway is healthy
curl -s -k -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" https://localhost:4444/health
# {"status":"healthy"}

# Quickly confirm the gateway version & DB connectivity
curl -s -k -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" https://localhost:4444/version | jq
```

</details>

---

<details>
<summary><strong>🧱 Protocol APIs (MCP) /protocol</strong></summary>

```bash
# Initialize MCP session
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "protocol_version":"2025-03-26",
           "capabilities":{},
           "client_info":{"name":"MyClient","version":"1.0.0"}
         }' \
     http://localhost:4444/protocol/initialize

# Ping (JSON-RPC style)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
     http://localhost:4444/protocol/ping

# Completion for prompt/resource arguments (not implemented)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "ref":{"type":"ref/prompt","name":"example_prompt"},
           "argument":{"name":"topic","value":"py"}
         }' \
     http://localhost:4444/protocol/completion/complete

# Sampling (streaming) (not implemented)
curl -N -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "messages":[{"role":"user","content":{"type":"text","text":"Hello"}}],
           "maxTokens":16
         }' \
     http://localhost:4444/protocol/sampling/createMessage
```

</details>

---

<details>
<summary><strong>🧠 JSON-RPC Utility /rpc</strong></summary>

```bash
# Generic JSON-RPC calls (tools, gateways, roots, etc.)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"list_tools"}' \
     http://localhost:4444/rpc
```

Handles any method name: `list_tools`, `list_gateways`, `prompts/get`, or invokes a tool if method matches a registered tool name .

</details>

---

<details>
<summary><strong>🔧 Tool Management /tools</strong></summary>

```bash
# Register a new tool
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "name":"clock_tool",
           "url":"http://localhost:9000/rpc",
           "description":"Returns current time",
           "input_schema":{
             "type":"object",
             "properties":{"timezone":{"type":"string"}},
             "required":[]
           }
         }' \
     http://localhost:4444/tools

# List tools
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools

# Get tool by ID
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools/1

# Update tool
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{ "description":"Updated desc" }' \
     http://localhost:4444/tools/1

# Toggle active status
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/tools/1/toggle?activate=false
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/tools/1/toggle?activate=true

# Delete tool
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/tools/1
```

</details>

---

<details>
<summary><strong>🤖 A2A Agent Management /a2a</strong></summary>

```bash
# Register a new A2A agent
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "name":"hello_world_agent",
           "endpoint_url":"http://localhost:9999/",
           "agent_type":"jsonrpc",
           "description":"External AI agent for hello world functionality",
           "auth_type":"api_key",
           "auth_value":"your-api-key",
           "tags":["ai", "hello-world"]
         }' \
     http://localhost:4444/a2a

# List A2A agents
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/a2a

# Get agent by ID
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/a2a/agent-id

# Update agent
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{ "description":"Updated description" }' \
     http://localhost:4444/a2a/agent-id

# Test agent (direct invocation)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "parameters": {
             "method": "message/send",
             "params": {
               "message": {
                 "messageId": "test-123",
                 "role": "user",
                 "parts": [{"type": "text", "text": "Hello!"}]
               }
             }
           },
           "interaction_type": "test"
         }' \
     http://localhost:4444/a2a/agent-name/invoke

# Toggle agent status
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/a2a/agent-id/toggle?activate=false

# Delete agent
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/a2a/agent-id

# Associate agent with virtual server (agents become available as MCP tools)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "name":"AI Assistant Server",
           "description":"Virtual server with AI agents",
           "associated_a2a_agents":["agent-id"]
         }' \
     http://localhost:4444/servers
```

> 🤖 **A2A Integration**: A2A agents are external AI agents that can be registered and exposed as MCP tools
> 🔄 **Protocol Detection**: Gateway automatically detects JSONRPC vs custom A2A protocols
> 📊 **Testing**: Built-in test functionality via Admin UI or `/a2a/{agent_id}/test` endpoint
> 🎛️ **Virtual Servers**: Associate agents with servers to expose them as standard MCP tools

</details>

---

<details>
<summary><strong>🌐 Gateway Management /gateways</strong></summary>

```bash
# Register an MCP server as a new gateway provider
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"peer_gateway","url":"http://peer:4444"}' \
     http://localhost:4444/gateways

# List gateways
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/gateways

# Get gateway by ID
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/gateways/1

# Update gateway
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"description":"New description"}' \
     http://localhost:4444/gateways/1

# Toggle active status
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/gateways/1/toggle?activate=false

# Delete gateway
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/gateways/1
```

</details>

---

<details>
<summary><strong>📁 Resource Management /resources</strong></summary>

```bash
# Register resource
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "uri":"config://app/settings",
           "name":"App Settings",
           "content":"key=value"
         }' \
     http://localhost:4444/resources

# List resources
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/resources

# Read a resource
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/resources/config://app/settings

# Update resource
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"content":"new=value"}' \
     http://localhost:4444/resources/config://app/settings

# Delete resource
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/resources/config://app/settings

# Subscribe to updates (SSE)
curl -N -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/resources/subscribe/config://app/settings
```

</details>

---

<details>
<summary><strong>📝 Prompt Management /prompts</strong></summary>

```bash
# Create prompt template
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "name":"greet",
           "template":"Hello, {{ user }}!",
           "argument_schema":{
             "type":"object",
             "properties":{"user":{"type":"string"}},
             "required":["user"]
           }
         }' \
     http://localhost:4444/prompts

# List prompts
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/prompts

# Get prompt (with args)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"user":"Alice"}' \
     http://localhost:4444/prompts/greet

# Get prompt (no args)
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/prompts/greet

# Update prompt
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"template":"Hi, {{ user }}!"}' \
     http://localhost:4444/prompts/greet

# Toggle active
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/prompts/5/toggle?activate=false

# Delete prompt
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/prompts/greet
```

</details>

---

<details>
<summary><strong>🌲 Root Management /roots</strong></summary>

```bash
# List roots
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/roots

# Add root
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"uri":"/data","name":"Data Root"}' \
     http://localhost:4444/roots

# Remove root
curl -X DELETE -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/roots/%2Fdata

# Subscribe to root changes (SSE)
curl -N -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/roots/changes
```

</details>

---

<details>
<summary><strong>🖥️ Server Management /servers</strong></summary>

```bash
# List servers
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/servers

# Get server
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/servers/UUID_OF_SERVER_1

# Create server
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"db","description":"Database","associatedTools": ["1","2","3"]}' \
     http://localhost:4444/servers

# Update server
curl -X PUT -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"description":"Updated"}' \
     http://localhost:4444/servers/UUID_OF_SERVER_1

# Toggle active
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" \
     http://localhost:4444/servers/UUID_OF_SERVER_1/toggle?activate=false
```

</details>

---

<details>
<summary><strong>📊 Metrics /metrics</strong></summary>

```bash
# Get aggregated metrics
curl -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/metrics

# Reset metrics (all or per-entity)
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/metrics/reset
curl -X POST -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/metrics/reset?entity=tool&id=1
```

</details>

---

<details>
<summary><strong>📡 Events & Health</strong></summary>

```bash
# SSE: all events
curl -N -H "Authorization: Bearer $MCPGATEWAY_BEARER_TOKEN" http://localhost:4444/events

# WebSocket
wscat -c ws://localhost:4444/ws \
      -H "Authorization: Basic $(echo -n admin:changeme|base64)"

# Health check
curl http://localhost:4444/health
```

Full Swagger UI at `/docs`.

</details>

---

<details>
<summary><strong>🛠️ Sample Tool</strong></summary>

```bash
uvicorn sample_tool.clock_tool:app --host 0.0.0.0 --port 9000
```

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"get_time","params":{"timezone":"UTC"}}' \
     http://localhost:9000/rpc
```

</details>

---

## Testing

```bash
make test            # Run unit tests
make lint            # Run lint tools
```

---

## Project Structure

### Agent Docs (AGENTS.md Index)

* [Repository Agents Guide](AGENTS.md)
* [Core Gateway](mcpgateway/AGENTS.md)
* [Services](mcpgateway/services/AGENTS.md)
* [Plugins](mcpgateway/plugins/AGENTS.md)
* [Transports](mcpgateway/transports/AGENTS.md)
* [Routers](mcpgateway/routers/AGENTS.md)
* [Middleware](mcpgateway/middleware/AGENTS.md)
* [Handlers](mcpgateway/handlers/AGENTS.md)
* [Federation](mcpgateway/federation/AGENTS.md)
* [Validation](mcpgateway/validation/AGENTS.md)
* [Utils](mcpgateway/utils/AGENTS.md)
* [Cache](mcpgateway/cache/AGENTS.md)
* [Alembic/Migrations](mcpgateway/alembic/AGENTS.md)

<details>
<summary><strong>📁 Directory and file structure for mcpgateway</strong></summary>

```bash
# ────────── CI / Quality & Meta-files ──────────
├── .bumpversion.cfg                # Automated semantic-version bumps
├── .coveragerc                     # Coverage.py settings
├── .darglint                       # Doc-string linter rules
├── .dockerignore                   # Context exclusions for image builds
├── .editorconfig                   # Consistent IDE / editor behaviour
├── .env                            # Local runtime variables (git-ignored)
├── .env.ce                         # IBM Code Engine runtime env (ignored)
├── .env.ce.example                 # Sample env for IBM Code Engine
├── .env.example                    # Generic sample env file
├── .env.gcr                        # Google Cloud Run runtime env (ignored)
├── .eslintrc.json                  # ESLint rules for JS / TS assets
├── .flake8                         # Flake-8 configuration
├── .gitattributes                  # Git attributes (e.g. EOL normalisation)
├── .github                         # GitHub settings, CI/CD workflows & templates
│   ├── CODEOWNERS                  # Default reviewers
│   └── workflows/                  # Bandit, Docker, CodeQL, Python Package, Container Deployment, etc.
├── .gitignore                      # Git exclusion rules
├── .hadolint.yaml                  # Hadolint rules for Dockerfiles
├── .htmlhintrc                     # HTMLHint rules
├── .markdownlint.json              # Markdown-lint rules
├── .pre-commit-config.yaml         # Pre-commit hooks (ruff, black, mypy, ...)
├── .pycodestyle                    # PEP-8 checker settings
├── .pylintrc                       # Pylint configuration
├── .pyspelling.yml                 # Spell-checker dictionary & filters
├── .ruff.toml                      # Ruff linter / formatter settings
├── .spellcheck-en.txt              # Extra dictionary entries
├── .stylelintrc.json               # Stylelint rules for CSS
├── .travis.yml                     # Legacy Travis CI config (reference)
├── .whitesource                    # WhiteSource security-scanning config
├── .yamllint                       # yamllint ruleset

# ────────── Documentation & Guidance ──────────
├── CHANGELOG.md                    # Version-by-version change log
├── CODE_OF_CONDUCT.md              # Community behaviour guidelines
├── CONTRIBUTING.md                 # How to file issues & send PRs
├── DEVELOPING.md                   # Contributor workflows & style guide
├── LICENSE                         # Apache License 2.0
├── README.md                       # Project overview & quick-start
├── SECURITY.md                     # Security policy & CVE disclosure process
├── TESTING.md                      # Testing strategy, fixtures & guidelines

# ────────── Containerisation & Runtime ──────────
├── Containerfile                   # OCI image build (Docker / Podman)
├── Containerfile.lite              # FROM scratch UBI-Micro production build
├── docker-compose.yml              # Local multi-service stack
├── podman-compose-sonarqube.yaml   # One-liner SonarQube stack
├── run-gunicorn.sh                 # Opinionated Gunicorn startup script
├── run.sh                          # Uvicorn shortcut with arg parsing

# ────────── Build / Packaging / Tooling ──────────
├── MANIFEST.in                     # sdist inclusion rules
├── Makefile                        # Dev & deployment targets
├── package-lock.json               # Deterministic npm lock-file
├── package.json                    # Front-end / docs tooling deps
├── pyproject.toml                  # Poetry / PDM config & lint rules
├── sonar-code.properties           # SonarQube analysis settings
├── uv.lock                         # UV resolver lock-file

# ────────── Kubernetes & Helm Assets ──────────
├── charts                          # Helm chart(s) for K8s / OpenShift
│   ├── mcp-stack                   # Umbrella chart
│   │   ├── Chart.yaml              # Chart metadata
│   │   ├── templates/...             # Manifest templates
│   │   └── values.yaml             # Default values
│   └── README.md                   # Install / upgrade guide
├── k8s                             # Raw (non-Helm) K8s manifests
│   └── *.yaml                      # Deployment, Service, PVC resources

# ────────── Documentation Source ──────────
├── docs                            # MkDocs site source
│   ├── base.yml                    # MkDocs "base" configuration snippet (do not modify)
│   ├── mkdocs.yml                  # Site configuration (requires base.yml)
│   ├── requirements.txt            # Python dependencies for the MkDocs site
│   ├── Makefile                    # Make targets for building/serving the docs
│   └── theme                       # Custom MkDocs theme assets
│       └── logo.png                # Logo for the documentation theme
│   └── docs                        # Markdown documentation
│       ├── architecture/           # ADRs for the project
│       ├── articles/               # Long-form writeups
│       ├── blog/                   # Blog posts
│       ├── deployment/             # Deployment guides (AWS, Azure, etc.)
│       ├── development/            # Development workflows & CI docs
│       ├── images/                 # Diagrams & screenshots
│       ├── index.md                # Top-level docs landing page
│       ├── manage/                 # Management topics (backup, logging, tuning, upgrade)
│       ├── overview/               # Feature overviews & UI documentation
│       ├── security/               # Security guidance & policies
│       ├── testing/                # Testing strategy & fixtures
│       └── using/                  # User-facing usage guides (agents, clients, etc.)
│       ├── media/                  # Social media, press coverage, videos & testimonials
│       │   ├── press/              # Press articles and blog posts
│       │   ├── social/             # Tweets, LinkedIn posts, YouTube embeds
│       │   ├── testimonials/       # Customer quotes & community feedback
│       │   └── kit/                # Media kit & logos for bloggers & press
├── dictionary.dic                  # Custom dictionary for spell-checker (make spellcheck)

# ────────── Application & Libraries ──────────
├── agent_runtimes                  # Configurable agentic frameworks converted to MCP Servers
├── mcpgateway                      # ← main application package
│   ├── __init__.py                 # Package metadata & version constant
│   ├── admin.py                    # FastAPI routers for Admin UI
│   ├── cache
│   │   ├── __init__.py
│   │   ├── resource_cache.py       # LRU+TTL cache implementation
│   │   └── session_registry.py     # Session ↔ cache mapping
│   ├── config.py                   # Pydantic settings loader
│   ├── db.py                       # SQLAlchemy models & engine setup
│   ├── federation
│   │   ├── __init__.py
│   │   ├── discovery.py            # Peer-gateway discovery
│   │   ├── forward.py              # RPC forwarding
│   ├── handlers
│   │   ├── __init__.py
│   │   └── sampling.py             # Streaming sampling handler
│   ├── main.py                     # FastAPI app factory & startup events
│   ├── mcp.db                      # SQLite fixture for tests
│   ├── py.typed                    # PEP 561 marker (ships type hints)
│   ├── schemas.py                  # Shared Pydantic DTOs
│   ├── services
│   │   ├── __init__.py
│   │   ├── completion_service.py   # Prompt / argument completion
│   │   ├── gateway_service.py      # Peer-gateway registry
│   │   ├── logging_service.py      # Central logging helpers
│   │   ├── prompt_service.py       # Prompt CRUD & rendering
│   │   ├── resource_service.py     # Resource registration & retrieval
│   │   ├── root_service.py         # File-system root registry
│   │   ├── server_service.py       # Server registry & monitoring
│   │   └── tool_service.py         # Tool registry & invocation
│   ├── static
│   │   ├── admin.css               # Styles for Admin UI
│   │   └── admin.js                # Behaviour for Admin UI
│   ├── templates
│   │   └── admin.html              # HTMX/Alpine Admin UI template
│   ├── transports
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract transport interface
│   │   ├── sse_transport.py        # Server-Sent Events transport
│   │   ├── stdio_transport.py      # stdio transport for embedding
│   │   └── websocket_transport.py  # WS transport with ping/pong
│   ├── models.py                   # Core enums / type aliases
│   ├── utils
│   │   ├── create_jwt_token.py     # CLI & library for JWT generation
│   │   ├── services_auth.py        # Service-to-service auth dependency
│   │   └── verify_credentials.py   # Basic / JWT auth helpers
│   ├── validation
│   │   ├── __init__.py
│   │   └── jsonrpc.py              # JSON-RPC 2.0 validation
│   └── version.py                  # Library version helper
├── mcpgateway-wrapper              # Stdio client wrapper (PyPI)
│   ├── pyproject.toml
│   ├── README.md
│   └── src/mcpgateway_wrapper/
│       ├── __init__.py
│       └── server.py               # Wrapper entry-point
├── mcp-servers                     # Sample downstream MCP servers
├── mcp.db                          # Default SQLite DB (auto-created)
├── mcpgrid                         # Experimental grid client / PoC
├── os_deps.sh                      # Installs system-level deps for CI

# ────────── Tests & QA Assets ──────────
├── test_readme.py                  # Guard: README stays in sync
├── tests
│   ├── conftest.py                 # Shared fixtures
│   ├── e2e/...                       # End-to-end scenarios
│   ├── hey/...                       # Load-test logs & helper script
│   ├── integration/...               # API-level integration tests
│   └── unit/...                      # Pure unit tests for business logic
```

</details>

---

## API Documentation

* **Swagger UI** → [http://localhost:4444/docs](http://localhost:4444/docs)
* **ReDoc**    → [http://localhost:4444/redoc](http://localhost:4444/redoc)
* **Admin Panel** → [http://localhost:4444/admin](http://localhost:4444/admin)

---

## Makefile targets

This project offer the following Makefile targets. Type `make` in the project root to show all targets.

<details>
<summary><strong>🔧 Available Makefile targets</strong></summary>

```bash
🐍 MCP CONTEXT FORGE  (An enterprise-ready Model Context Protocol Gateway)
🔧 SYSTEM-LEVEL DEPENDENCIES (DEV BUILD ONLY)
os-deps              - Install Graphviz, Pandoc, Trivy, SCC used for dev docs generation and security scan
🌱 VIRTUAL ENVIRONMENT & INSTALLATION
venv                 - Create a fresh virtual environment with uv & friends
activate             - Activate the virtual environment in the current shell
install              - Install project into the venv
install-dev          - Install project (incl. dev deps) into the venv
install-db           - Install project (incl. postgres and redis) into venv
update               - Update all installed deps inside the venv
check-env            - Verify all required env vars in .env are present
▶️ SERVE & TESTING
serve                - Run production Gunicorn server on :4444
certs                - Generate self-signed TLS cert & key in ./certs (won't overwrite)
serve-ssl            - Run Gunicorn behind HTTPS on :4444 (uses ./certs)
dev                  - Run fast-reload dev server (uvicorn)
run                  - Execute helper script ./run.sh
test                 - Run unit tests with pytest
test-curl            - Smoke-test API endpoints with curl script
pytest-examples      - Run README / examples through pytest-examples
clean                - Remove caches, build artefacts, virtualenv, docs, certs, coverage, SBOM, etc.
📊 COVERAGE & METRICS
coverage             - Run tests with coverage, emit md/HTML/XML + badge
pip-licenses         - Produce dependency license inventory (markdown)
scc                  - Quick LoC/complexity snapshot with scc
scc-report           - Generate HTML LoC & per-file metrics with scc
📚 DOCUMENTATION & SBOM
docs                 - Build docs (graphviz + handsdown + images + SBOM)
images               - Generate architecture & dependency diagrams
🔍 LINTING & STATIC ANALYSIS
lint                 - Run the full linting suite (see targets below)
black                - Reformat code with black
autoflake            - Remove unused imports / variables with autoflake
isort                - Organise & sort imports with isort
flake8               - PEP-8 style & logical errors
pylint               - Pylint static analysis
markdownlint         - Lint Markdown files with markdownlint (requires markdownlint-cli)
mypy                 - Static type-checking with mypy
bandit               - Security scan with bandit
pydocstyle           - Docstring style checker
pycodestyle          - Simple PEP-8 checker
pre-commit           - Run all configured pre-commit hooks
ruff                 - Ruff linter + formatter
ty                   - Ty type checker from astral
pyright              - Static type-checking with Pyright
radon                - Code complexity & maintainability metrics
pyroma               - Validate packaging metadata
importchecker        - Detect orphaned imports
spellcheck           - Spell-check the codebase
fawltydeps           - Detect undeclared / unused deps
wily                 - Maintainability report
pyre                 - Static analysis with Facebook Pyre
depend               - List dependencies in ≈requirements format
snakeviz             - Profile & visualise with snakeviz
pstats               - Generate PNG call-graph from cProfile stats
spellcheck-sort      - Sort local spellcheck dictionary
tox                  - Run tox across multi-Python versions
sbom                 - Produce a CycloneDX SBOM and vulnerability scan
pytype               - Flow-sensitive type checker
check-manifest       - Verify sdist/wheel completeness
yamllint            - Lint YAML files (uses .yamllint)
jsonlint            - Validate every *.json file with jq (--exit-status)
tomllint            - Validate *.toml files with tomlcheck
🕸️  WEBPAGE LINTERS & STATIC ANALYSIS (HTML/CSS/JS lint + security scans + formatting)
install-web-linters  - Install HTMLHint, Stylelint, ESLint, Retire.js & Prettier via npm
lint-web             - Run HTMLHint, Stylelint, ESLint, Retire.js and npm audit
format-web           - Format HTML, CSS & JS files with Prettier
osv-install          - Install/upgrade osv-scanner (Go)
osv-scan-source      - Scan source & lockfiles for CVEs
osv-scan-image       - Scan the built container image for CVEs
osv-scan             - Run all osv-scanner checks (source, image, licence)
📡 SONARQUBE ANALYSIS
sonar-deps-podman    - Install podman-compose + supporting tools
sonar-deps-docker    - Install docker-compose + supporting tools
sonar-up-podman      - Launch SonarQube with podman-compose
sonar-up-docker      - Launch SonarQube with docker-compose
sonar-submit-docker  - Run containerized Sonar Scanner CLI with Docker
sonar-submit-podman  - Run containerized Sonar Scanner CLI with Podman
pysonar-scanner      - Run scan with Python wrapper (pysonar-scanner)
sonar-info           - How to create a token & which env vars to export
🛡️ SECURITY & PACKAGE SCANNING
trivy                - Scan container image for CVEs (HIGH/CRIT). Needs podman socket enabled
grype-scan           - Scan container for security audit and vulnerability scanning
dockle               - Lint the built container image via tarball (no daemon/socket needed)
hadolint             - Lint Containerfile/Dockerfile(s) with hadolint
pip-audit            - Audit Python dependencies for published CVEs
📦 DEPENDENCY MANAGEMENT
deps-update          - Run update-deps.py to update all dependencies in pyproject.toml and docs/requirements.txt
containerfile-update - Update base image in Containerfile to latest tag
📦 PACKAGING & PUBLISHING
dist                 - Clean-build wheel *and* sdist into ./dist
wheel                - Build wheel only
sdist                - Build source distribution only
verify               - Build + twine + check-manifest + pyroma (no upload)
publish              - Verify, then upload to PyPI (needs TWINE_* creds)
🦭 PODMAN CONTAINER BUILD & RUN
podman-dev           - Build development container image
podman               - Build container image
podman-prod          - Build production container image (using ubi-micro → scratch). Not supported on macOS.
podman-run           - Run the container on HTTP  (port 4444)
podman-run-shell     - Run the container on HTTP  (port 4444) and start a shell
podman-run-ssl       - Run the container on HTTPS (port 4444, self-signed)
podman-run-ssl-host  - Run the container on HTTPS with --network=host (port 4444, self-signed)
podman-stop          - Stop & remove the container
podman-test          - Quick curl smoke-test against the container
podman-logs          - Follow container logs (⌃C to quit)
podman-stats         - Show container resource stats (if supported)
podman-top           - Show live top-level process info in container
podman-shell         - Open an interactive shell inside the Podman container
🐋 DOCKER BUILD & RUN
docker-dev           - Build development Docker image
docker               - Build production Docker image
docker-prod          - Build production container image (using ubi-micro → scratch). Not supported on macOS.
docker-run           - Run the container on HTTP  (port 4444)
docker-run-ssl       - Run the container on HTTPS (port 4444, self-signed)
docker-stop          - Stop & remove the container
docker-test          - Quick curl smoke-test against the container
docker-logs          - Follow container logs (⌃C to quit)
docker-stats         - Show container resource usage stats (non-streaming)
docker-top           - Show top-level process info in Docker container
docker-shell         - Open an interactive shell inside the Docker container
🛠️ COMPOSE STACK     - Build / start / stop the multi-service stack
compose-up           - Bring the whole stack up (detached)
compose-restart      - Recreate changed containers, pulling / building as needed
compose-build        - Build (or rebuild) images defined in the compose file
compose-pull         - Pull the latest images only
compose-logs         - Tail logs from all services (Ctrl-C to exit)
compose-ps           - Show container status table
compose-shell        - Open an interactive shell in the "gateway" container
compose-stop         - Gracefully stop the stack (keep containers)
compose-down         - Stop & remove containers (keep named volumes)
compose-rm           - Remove *stopped* containers
compose-clean        - ✨ Down **and** delete named volumes (data-loss ⚠)
☁️ IBM CLOUD CODE ENGINE
ibmcloud-check-env          - Verify all required IBM Cloud env vars are set
ibmcloud-cli-install        - Auto-install IBM Cloud CLI + required plugins (OS auto-detected)
ibmcloud-login              - Login to IBM Cloud CLI using IBMCLOUD_API_KEY (--sso)
ibmcloud-ce-login           - Set Code Engine target project and region
ibmcloud-list-containers    - List deployed Code Engine apps
ibmcloud-tag                - Tag container image for IBM Container Registry
ibmcloud-push               - Push image to IBM Container Registry
ibmcloud-deploy             - Deploy (or update) container image in Code Engine
ibmcloud-ce-logs            - Stream logs for the deployed application
ibmcloud-ce-status          - Get deployment status
ibmcloud-ce-rm              - Delete the Code Engine application
🧪 MINIKUBE LOCAL CLUSTER
minikube-install      - Install Minikube (macOS, Linux, or Windows via choco)
helm-install          - Install Helm CLI (macOS, Linux, or Windows)
minikube-start        - Start local Minikube cluster with Ingress + DNS + metrics-server
minikube-stop         - Stop the Minikube cluster
minikube-delete       - Delete the Minikube cluster
minikube-image-load   - Build and load ghcr.io/ibm/mcp-context-forge:latest into Minikube
minikube-k8s-apply    - Apply Kubernetes manifests from deployment/k8s/
minikube-status       - Show status of Minikube and ingress pods
🛠️ HELM CHART TASKS
helm-lint            - Lint the Helm chart (static analysis)
helm-package         - Package the chart into dist/ as mcp-stack-<ver>.tgz
helm-deploy          - Upgrade/Install chart into Minikube (profile mcpgw)
helm-delete          - Uninstall the chart release from Minikube
🏠 LOCAL PYPI SERVER
local-pypi-install   - Install pypiserver for local testing
local-pypi-start     - Start local PyPI server on :8084 (no auth)
local-pypi-start-auth - Start local PyPI server with basic auth (admin/admin)
local-pypi-stop      - Stop local PyPI server
local-pypi-upload    - Upload existing package to local PyPI (no auth)
local-pypi-upload-auth - Upload existing package to local PyPI (with auth)
local-pypi-test      - Install package from local PyPI
local-pypi-clean     - Full cycle: build → upload → install locally
🏠 LOCAL DEVPI SERVER
devpi-install        - Install devpi server and client
devpi-init           - Initialize devpi server (first time only)
devpi-start          - Start devpi server
devpi-stop           - Stop devpi server
devpi-setup-user     - Create user and dev index
devpi-upload         - Upload existing package to devpi
devpi-test           - Install package from devpi
devpi-clean          - Full cycle: build → upload → install locally
devpi-status         - Show devpi server status
devpi-web            - Open devpi web interface
```

</details>

## 🔍 Troubleshooting

<details>
<summary><strong>Port publishing on WSL2 (rootless Podman & Docker Desktop)</strong></summary>

### Diagnose the listener

```bash
# Inside your WSL distro
ss -tlnp | grep 4444        # Use ss
netstat -anp | grep 4444    # or netstat
```

*Seeing `:::4444 LISTEN rootlessport` is normal* - the IPv6 wildcard
socket (`::`) also accepts IPv4 traffic **when**
`net.ipv6.bindv6only = 0` (default on Linux).

### Why localhost fails on Windows

WSL 2's NAT layer rewrites only the *IPv6* side of the dual-stack listener. From Windows, `http://127.0.0.1:4444` (or Docker Desktop's "localhost") therefore times-out.

#### Fix (Podman rootless)

```bash
# Inside the WSL distro
echo "wsl" | sudo tee /etc/containers/podman-machine
systemctl --user restart podman.socket
```

`ss` should now show `0.0.0.0:4444` instead of `:::4444`, and the
service becomes reachable from Windows *and* the LAN.

#### Fix (Docker Desktop > 4.19)

Docker Desktop adds a "WSL integration" switch per-distro.
Turn it **on** for your distro, restart Docker Desktop, then restart the
container:

```bash
docker restart mcpgateway
```

</details>

<details>
<summary><strong>Gateway starts but immediately exits ("Failed to read DATABASE_URL")</strong></summary>

Copy `.env.example` to `.env` first:

```bash
cp .env.example .env
```

Then edit `DATABASE_URL`, `JWT_SECRET_KEY`, `BASIC_AUTH_PASSWORD`, etc.
Missing or empty required vars cause a fast-fail at startup.

</details>
