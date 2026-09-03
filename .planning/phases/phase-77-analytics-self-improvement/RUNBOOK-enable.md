# Phase 77: 반영 모드 활성화 Runbook

**Date:** 2026-09-03
**Status:** Final
**대상:** curation 파이프라인 성과 신호 boost (`PERF_SIGNALS` env 게이트)

## 현재 상태

- 추출기: `shared/performance_signals.py` — 6h 주기 launchd 수집 말미에 자동 실행 (commit d97e9b868)
- 학습 상태: `data/keyword_performance.json` — 7 blogs / 23 patterns (2026-09-03 기준, 원시 데이터에서 재생성 가능)
- boost: `pipelines/curation/pipeline.py` `_apply_perf_signal_boost` — **기본 OFF** (commit 0d730ce7e)
- 게이트 조건 4종 전부 통과 시에만 발동: env 설정 + JSON 유효 + blog 신호 존재 + 후보 매칭. 任 실패 시 기존 동작 passthrough

## 관찰 기간 체크 (활성화 전 필수)

전환 기준 3종 (2026-09-03 + 14일 ≈ 09-17 이후 판정):

| # | 기준 | 확인 방법 |
|---|---|---|
| 1 | 추출기 6h 주기 연속 성공 ≥14회 | `grep "perf-signals" logs/analytics_collect.log \| tail -20` — `ok` 연속 확인 |
| 2 | JSON 패턴 수 안정 | 직전 3회 실행 결과 동일 (수집 로그의 `blogs=N patterns=N` 라인 대조) |
| 3 | 테스트 green 유지 | `OPS_TEST_MODE=1 pytest tests/test_performance_signals.py tests/curation -q` — 9+129 passed, 19 failed(pre-existing) 동일 |

## 활성화 절차

1. 위 체크 3종 통과 확인
2. scheduler.py 실행 환경에 env 주입 — launchd plist(`com.5000.scheduler.plist`) `EnvironmentVariables`에 `PERF_SIGNALS=1` 추가, `launchctl unload && load`
3. 1회 수동 검증: `PERF_SIGNALS=1 python3 dispatcher.py deal-hugo` — 로그에 boost 발동 라인 확인
4. 1~2일 관찰: 발행된 글의 키워드가 유지비 계열 등 신호 매칭 쪽으로 편향되는지 대시보드/publish_log 확인

## 되돌림

- **즉시 무력화:** launchd plist에서 `PERF_SIGNALS` 제거 (또는 `=0`) + reload. 재배포·코드 변경 불필요. boost 블록이 passthrough로 전환.
- **완전 제거:** revert 커밋 0d730ce7e
- **학습 상태 리셋:** `rm data/keyword_performance.json` → 다음 6h 주기 재생성 (원시 analytics.db 보존, 손실 없음)

## 확장 로드맵 (별도 phase)

- travel fetcher 가중 선택 — curation 검증 후
- 슬로우/킬 키워드 자동 강등 (클릭 0 지속 키워드) — 관찰 데이터 축적 후
- GA4 수집 재개 → 체류시간/참여 신호 — 데이터 인프라 별개 이슈
