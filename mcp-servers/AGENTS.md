# AGENTS: 샘플 MCP 서버 모음

게이트웨이 통합/데모/테스트를 위한 참고용 MCP 서버 구현이 포함됩니다.

## Go: `go/fast-time-server`

- 역할: 단순 시간 조회 서버(컨테이너/stdio 테스트 가능)
- 사용 아이디어:
  - 로컬 실행: `go run .`
  - 컨테이너 실행: 디렉터리 내 Docker/예시 스크립트 참조

## Python: `python/mcp_eval_server`

- 역할: 리소스/툴/프롬프트 데모가 포함된 예제 서버
- 사용 아이디어:
  - 가상환경 구성 후 의존성 설치
  - `python -m mcp_eval_server` 형태로 실행(서브모듈 엔트리 참고)

## 게이트웨이와 함께 쓰기

- stdio 노출 예시:

```bash
python -m mcpgateway.translate --stdio "<your-mcp-server-command>" --port 9000
```

- 서버를 등록한 뒤 `/tools` 동기화 또는 LangChain 런타임에서 자동 디스커버리로 활용하세요.

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
