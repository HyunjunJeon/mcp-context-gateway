# AGENTS: 문서 사이트(MkDocs)

이 디렉터리는 MkDocs 기반 프로젝트 문서의 소스입니다. 아키텍처, 개발, 운영, 테스트 가이드를 포함합니다.

## 구조

- `mkdocs.yml`: 사이트 설정
- `docs/`: 실제 문서 소스
  - `architecture/`, `development/`, `deployment/`, `using/`, `testing/`, `manage/` 등
  - `images/`, `media/`: 자산 파일
  - `index.md`: 랜딩 페이지

## 로컬 미리보기

```bash
cd docs
make serve  # 또는: mkdocs serve
```

## 빌드/배포

```bash
cd docs
make build   # 또는: mkdocs build
```

- 커버리지 HTML은 `docs/docs/coverage/` 하위에 생성됩니다(`make htmlcov`).

## 기여 가이드

- 문서는 기능 변경과 함께 업데이트합니다.
- 긴 코드 블록은 축약/접기, 실제 예시는 테스트(`tests/test_readme.py`)로 검증합니다.

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
