# AGENTS: 테스트 스위트 개요

유닛/통합/E2E/보안/퍼지/플레이라이트 테스트가 포함됩니다. 빠르고 결정적인 테스트를 기본 목표로 구성됩니다.

## 디렉터리 구조

- `unit/`: 단위 테스트(가장 빠름)
- `integration/`: 컴포넌트 상호작용 검증
- `e2e/`: 엔드투엔드 시나리오
- `security/`: 보안 회귀/정책 검증
- `fuzz/`: 퍼지 테스트(입력 강건성)
- `playwright/`: UI/관리 콘솔 시나리오
- `migration/`: DB 마이그레이션 회귀
- 공용 픽스처: `tests/conftest.py`

## 실행 방법

```bash
make test              # 전체
pytest -k "name"       # 선택 실행
pytest -m "not slow"   # 마커 기반
make htmlcov           # HTML 커버리지 리포트
```

## 작성 가이드

- 파일: `test_*.py`, 클래스: `Test*`, 함수: `test_*`
- 마커: `slow`, `ui`, `api`, `smoke`, `e2e`
- 테스트는 격리/결정성 유지, 외부 자원 의존 최소화

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
