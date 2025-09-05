# AGENTS: Agent Runtimes 개요

이 디렉터리는 다양한 에이전트 런타임을 모아두는 상위 컨테이너입니다. 현재는 LangChain 기반 런타임이 제공되며, 추후 다른 프레임워크(LangGraph 등) 런타임을 확장할 수 있습니다.

## 포함 서브런타임

### `langchain_agent/`
- 목적: MCP Gateway의 도구 카탈로그를 동적으로 수집·제한하면서 OpenAI 호환 Chat Completions API와 A2A(JSON-RPC)를 제공하는 에이전트 런타임
- 주요 기능:
  - OpenAI 호환 `/v1/chat/completions` (스트리밍 포함)
  - A2A 에이전트 엔드포인트
  - 다중 LLM 프로바이더(OpenAI, Azure, Anthropic, Bedrock, Ollama)
  - MCP Gateway와 실시간 통합(도구 동기화)
- 핵심 파일:
  - `app.py`: FastAPI 앱(헬스체크, OpenAI 호환 API, A2A 엔드포인트)
  - `agent_langchain.py`: LangChain 에이전트 코어(LLM 팩토리, MCPTool 어댑터, AgentExecutor)
  - `mcp_client.py`: 게이트웨이 클라이언트(도구 디스커버리/스키마 검증)
  - `config.py`: Pydantic 설정 모델과 환경 변수
  - `models.py`: OpenAI 호환 API 모델
  - `start_agent.py`: 애플리케이션 시작점
  - `requirements.txt`, `Makefile`: 의존성과 빌드/실행 헬퍼

## 빠른 시작

1) 환경 변수 설정

```bash
cd agent_runtimes/langchain_agent
cp .env.example .env
# 필수 값 예시
# MCP_GATEWAY_URL=http://localhost:4444
# MCPGATEWAY_BEARER_TOKEN=your-jwt-token
# OPENAI_API_KEY=your-openai-key
```

2) 실행

```bash
# 개발(핫리로드)
make dev

# 프로덕션(Gunicorn)
make serve
```

3) 간단 호출 예시

```bash
# OpenAI 호환 Chat Completions
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "tools": "auto"
  }'
```

## 아키텍처 요약

- MCP 도구 → LangChain BaseTool 변환(`MCPTool`)
- LLM 팩토리(`create_llm`)를 통한 프로바이더 선택
- AgentExecutor로 함수-도구 호출 기반 실행
- 게이트웨이의 도구/리소스/프롬프트를 동적으로 반영

## 테스트/품질

- 유닛/통합 테스트는 `agent_runtimes/langchain_agent/tests/` 참고
- 공통 리포지토리 품질 커맨드: `make lint`, `make test`, `make htmlcov`

## 확장 가이드

- 새 런타임 추가 시 `agent_runtimes/<new_runtime>/`로 디렉터리를 분기하고, 독립적인 `app.py`/`config.py`/`requirements.txt`를 구성하십시오.
- MCP 연동은 공통 패턴(도구 카탈로그 수집→검증→어댑트)을 재사용합니다.

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
- **하위 문서**
  - [langchain_agent/AGENTS.md](langchain_agent/AGENTS.md)
