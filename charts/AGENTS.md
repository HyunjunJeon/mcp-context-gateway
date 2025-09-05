# AGENTS: Helm Charts

이 디렉터리는 Helm 차트를 통해 MCP Gateway 스택을 배포하기 위한 아티팩트를 포함합니다.

## 포함 차트

### `charts/mcp-stack`
- 목적: 게이트웨이, Redis, Postgres, Ingress 등을 하나의 스택으로 배포
- 주요 파일:
  - `Chart.yaml`: 차트 메타데이터
  - `values.yaml`: 기본 값(프로파일별 값은 필요 시 오버라이드)
  - `templates/`: K8s 매니페스트 템플릿 모음
  - `values.schema.json`: 값 스키마 검증
  - `README.md`: 사용 가이드

## 설치/업그레이드

```bash
# 네임스페이스 준비
kubectl create ns mcp || true

# 설치
helm upgrade --install mcp charts/mcp-stack -n mcp \
  -f charts/mcp-stack/values.yaml \
  --set gateway.image.tag=latest

# 값 확인/드라이런
helm template mcp charts/mcp-stack -n mcp --debug --dry-run
```

## 값 커스터마이징 팁

- 민감 정보는 `--set-file` 또는 SealedSecret/ExternalSecrets를 사용하세요.
- Ingress/TLS는 클러스터 환경별로 `values.yaml` 오버레이를 분리하세요.

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
