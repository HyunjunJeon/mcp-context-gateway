# AGENTS: Plugin Framework

게이트웨이 플러그인 시스템의 핵심 프레임워크입니다. 플러그인 수명주기, 로딩/검증, 레지스트리, 외부 MCP 연동을 포괄합니다.

## 구성 요소

- `base.py`: 플러그인 베이스 추상화(수명주기 훅, 검증 인터페이스)
- `constants.py`: 공용 상수/키
- `errors.py`: 프레임워크 전반의 예외 타입
- `manager.py`: 플러그인 로드/초기화/수명주기 오케스트레이션
- `models.py`: 플러그인 메타데이터/설정 모델
- `registry.py`: 플러그인 등록/탐색 레지스트리
- `utils.py`: 공통 유틸리티
- `loader/`: 설정에서 플러그인을 해석/구성품화
  - `config.py`: 플러그인 설정 로더/검증
  - `plugin.py`: 플러그인 인스턴스화 로직
- `external/mcp/`: 외부 MCP 서버와의 연동 도우미
  - `client.py`: 외부 MCP 클라이언트
  - `server/`: 임베디드 MCP 서버 래퍼(runtime, server)

## 수명주기 개요

1) 구성 로드(파일/ENV) → 2) 등록/검증 → 3) 초기화 → 4) 요청/응답 훅 실행 → 5) 종료 정리

## 개발자 가이드

- 새 플러그인은 `base.py`의 계약을 구현합니다.
- 설정 스키마는 `models.py`를 통해 Pydantic으로 정의합니다.
- 외부 프로세스 기반 연동은 `external/` 하위 유틸을 참고하세요.

## 디버깅 팁

- 로드 순서/활성 목록을 로그로 확인하세요.
- 실패 시 `errors.py` 유형으로 분류해 원인 파악을 돕습니다.

## 탐색

- **⬆️ plugins**: [../AGENTS.md](../AGENTS.md)
- **⬆️ mcpgateway**: [../../AGENTS.md](../../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../../AGENTS.md](../../../AGENTS.md)
