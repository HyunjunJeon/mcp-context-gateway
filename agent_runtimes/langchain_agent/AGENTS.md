# AGENTS: LangChain Agent Runtime

OpenAI 호환 Chat Completions와 A2A(JSON-RPC)를 제공하며 MCP Gateway의 도구 카탈로그를 동적으로 수집/제한하는 런타임입니다.

## 주요 기능

- OpenAI 호환 `/v1/chat/completions` (스트리밍 지원)
- A2A 에이전트 엔드포인트
- 다중 LLM 프로바이더(OpenAI, Azure, Anthropic, Bedrock, Ollama)
- MCP Gateway와 실시간 통합(도구 동기화)

## 핵심 파일

- `app.py`: FastAPI 앱(헬스체크, OpenAI API, A2A)
- `agent_langchain.py`: 에이전트 코어(LLM 팩토리 `create_llm`, `MCPTool`, AgentExecutor)
- `mcp_client.py`: 게이트웨이 클라이언트(도구 디스커버리/스키마 검증)
- `config.py`: 설정 모델
- `models.py`: OpenAI 호환 API 모델
- `start_agent.py`: 실행 엔트리

## 빠른 시작

```bash
cd agent_runtimes/langchain_agent
cp .env.example .env
make dev   # 개발
# 또는
make serve # 프로덕션
```

환경 변수 예시:

```bash
MCP_GATEWAY_URL=http://localhost:4444
MCPGATEWAY_BEARER_TOKEN=your-jwt-token
OPENAI_API_KEY=your-openai-key
```

## 호출 예시

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}],
    "tools": "auto"
  }'
```

## 아키텍처 개요

- MCP 도구 → LangChain BaseTool로 어댑트(`MCPTool`)
- Provider 팩토리로 LLM 선택(`create_llm`)
- AgentExecutor가 도구 호출 오케스트레이션

## 테스트

- `tests/` 내 유닛 테스트: `pytest -q`
- 데모 스크립트: `demo.py`, `test_agent.sh`

## 탐색

- **⬆️ agent_runtimes**: [../AGENTS.md](../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../AGENTS.md](../../AGENTS.md)
