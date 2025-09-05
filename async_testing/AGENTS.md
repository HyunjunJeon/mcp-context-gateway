# AGENTS: Async Testing/Profiling 유틸리티

이 디렉터리는 비동기 코드의 성능/정확성 검증을 위한 스크립트 모음입니다. 벤치마크, 프로파일링, 모니터링, 결과 비교를 지원합니다.

## 파일 구성

- `benchmarks.py`: 주요 경로의 성능 벤치마크 실행기
- `profiler.py`: CPU/벽시계 시간 기반 프로파일링 도구
- `monitor_runner.py`: 장시간 워크로드 모니터링/수집
- `async_validator.py`: 비동기 동작의 정합성/레이스 조건 검증
- `profile_compare.py`: 프로파일 결과 비교/회귀 감지
- `config.yaml`: 벤치마크/프로파일러 기본 설정 샘플

## 사용 예시

```bash
# 벤치마크 실행
python -m async_testing.benchmarks --profile simple --iterations 1000

# 프로파일링
python -m async_testing.profiler --target mcpgateway.main:app --duration 60

# 결과 비교(베이스 vs. 후보)
python -m async_testing.profile_compare --base base.prof --candidate head.prof
```

## 권장 워크플로우

1) 기준선 측정 → 2) 변경 적용 → 3) 동일 시나리오 재측정 → 4) `profile_compare.py`로 회귀 여부 판정 → 5) 결과 기록(`docs/docs/testing/performance.md` 등)

## 팁

- 테스트는 격리된 환경(로컬/CI)에서 반복 가능하게 구성하세요.
- 결과 변동성을 줄이기 위해 충분한 워밍업과 반복 횟수를 사용하세요.
