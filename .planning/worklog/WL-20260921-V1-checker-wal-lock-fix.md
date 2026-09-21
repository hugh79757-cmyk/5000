# Worklog: WL-20260921-V1-checker-wal-lock-fix

**Date**: 2026-09-21
**Scope**: V-1-1 수리 패치 — checker timeout 5→30s + retry/backoff + row_factory=Row (shared/candidate_availability.py)
**Constraint**: cap.yaml·blogs.d 단일 작성자 규칙 — 이관 세션 창 내 커밋 필요 (현재 uncommitted)

---

## Pre-Count
- 대상 함수: `check_car_availability()` (shared/candidate_availability.py:106)
- 발생 빈도: pick-hugo daily 4회 + catchup 3회 = 7회/일 × 10일 = 70회 checker_error
- 연관 블로그: compare/rank/pick/appliance/baby-hugo (09:18 배치 동시 발생)

## Backup
- git stash@{0} (owner 잔해 3건 포함)
- 원본 파일: shared/candidate_availability.py (HEAD b4fbe15cf)

## Execution (최소 diff)
1. **timeout 증가**: `timeout=5` → `timeout=30` (30초 내 WAL 락 해제 대기)
2. **retry/backoff 추가**: `_connect_car_db_with_retry()` 헬퍼 신설 — 최대 3회, 지수 백오프(0.5s, 1s, 2s) + 지터(0~0.2s)
3. **row_factory=Row 추가**: `persona_pick_eligibility` → `lookup_fuel_efficiency` 호출 체인에서 dict-like row 접근 필요 (기존 버그 노출 후 수정)

## Post-Verification (단위 실측)
```python
# pick-hugo
check_car_availability(pick_hugo_cfg) 
# → {'state': 'healthy', 'available_count': 11, ...}  # checker_error → healthy

# 전체 car 블로그 검증
compare-hugo: healthy count=126
deal-hugo: healthy count=176
ev-hugo: healthy count=84
guide-hugo: healthy count=140
hotissue-hugo: healthy count=127
tco-hugo: healthy count=171
rank-hugo: healthy count=63
pick-hugo: healthy count=11
```

- [x] pick-hugo checker_error → healthy 복귀 확인
- [x] car.db WAL 락 경합 재발 0 (단일 테스트 — 24h 모니터 계획 별도)
- [x] row_factory=Row로 하위 호출 체인(dict access) 정상화

## 24h 모니터 계획 (제안)
- `logs/scheduler.log`에서 `unable to open database file` 발생 빈도 추적
- 메트릭: 일일 발생 건수, 연속 발생 여부, 복구 소요 시간
- 임계값: 24h 무발생 시 패치 검증 완료, 재발 시 max_retries 증가(3→5) 또는 timeout 추가 연장(30→60s) 검토

## 잔여 작업 (V-1 순서)
- [ ] 수리 패치 커밋 (이관 세션 창 내, 단일 작성자 규칙)
- [ ] pick 정상 재확인 (scheduler.log 다음 슬롯 06:55 +07 확인)
- [ ] §16 잔해 정리 (pick owner 재확정 포함)
- [ ] pick 리시딩 (수리된 DB 기반, 스코프 병합)
- [ ] cap.yaml edit (unpause + owner→runner)
- [ ] flip 커밋 → 06:55 +07 슬롯 4/4 관찰

## Logs
- logs/destructive_2026-09-20.log (라인 추가)
- 이 worklog: .planning/worklog/WL-20260921-V1-checker-wal-lock-fix.md