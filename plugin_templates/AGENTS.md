# AGENTS: 플러그인 스캐폴드 템플릿

새로운 플러그인을 빠르게 생성하기 위한 Jinja 기반 템플릿을 제공합니다. 외부/네이티브 플러그인 모두 동일한 수명주기/검증 훅을 따릅니다.

## 디렉터리

- `external/`: 외부 프로세스/서비스 연동 플러그인 템플릿
- `native/`: 게이트웨이 프로세스 내 실행 플러그인 템플릿

## 사용(프로젝트 루트에서 Copier 권장)

```bash
# 사전준비: pipx/uv로 copier 설치
copier copy plugin_templates/external ./plugins/my-external-plugin
# 또는
copier copy plugin_templates/native ./mcpgateway/plugins/tools/my-native-plugin
```

## 템플릿 가이드

- 변수 프롬프트에 따라 패키지명/진입점/설정 스텁이 생성됩니다.
- 생성 후 `plugins/config.yaml` 또는 게이트웨이 설정에 등록하세요.

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
