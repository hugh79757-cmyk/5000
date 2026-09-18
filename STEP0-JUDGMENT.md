# STEP 0 — 크론 라이브 실측 판정 (2026-09-18) — **분할 판정 갱신**

**기준 시각**: 2026-09-18 (KST +07)  
**대상 워크플로**: `publish.yml` (origin/main)  
**스케줄 5슬롯 (UTC ↔ KST)**:
| 슬롯 | Cron (UTC) | KST (+07) | 비고 |
|------|------------|-----------|------|
| 1 | `30 23 * * *` (23:30) | 06:30 (다음날) | tco 슬롯1 |
| 2 | `10 3 * * *` (03:10) | 10:10 | tco 슬롯2 |
| 3 | `35 6 * * *` (06:35) | 13:35 | tco 슬롯3 |
| 4 | `30 10 * * *` (10:30) | 17:30 | tco 슬롯4 |
| 5 | `45 13 * * *` (13:45) | 20:45 | tco 슬롯5 |

---

## 금일(2026-09-17 KST) 발화 실측 — gh run list 기준

| Run ID | 시각 (UTC) | KST (+07) | 매핑 슬롯 | Event | Conclusion | 소요 |
|--------|------------|-----------|-----------|-------|------------|------|
| 35130087799 | 2026-09-16 17:44:51 | 2026-09-17 00:44 | 슬롯1(전일) | schedule | success | 1m55s |
| 35171314367 | 2026-09-17 01:38:07 | 2026-09-17 08:38 | 슬롯2 | schedule | success | 1m55s |
| 35200411685 | 2026-09-17 08:34:38 | 2026-09-17 15:34 | 슬롯3 | schedule | success | 1m46s |
| 35218656043 | 2026-09-17 12:00:01 | 2026-09-17 19:00 | 슬롯4 | schedule | success | 2m04s |
| 35238058711 | 2026-09-17 15:06:33 | 2026-09-17 22:06 | 슬롯5 | schedule | success | 2m48s |

> **관측**: cron 5개 슬롯 **전부 발화 완료** (라이브 확인). 드리프트 ±30분~1.5h 존재하나 스케줄러 동작함.

---

## 슬롯별 결과 상세 (run 로그 분석)

| 슬롯 | Run ID | Reason | Pipeline Status | Consecutive | Problem ID | 비고 |
|------|--------|--------|-----------------|-------------|------------|------|
| 1 (전일) | 35130087799 | `no_topics` | `WAITING_FOR_CANDIDATES` | 0 | P01 | MINOR 로그 전용 |
| 2 | 35171314367 | `no_topics` | `WAITING_FOR_CANDIDATES` | 0 | P01 | MINOR 로그 전용 |
| 3 | 35200411685 | `no_topics` | `WAITING_FOR_CANDIDATES` | 0 | P01 | MINOR 로그 전용 |
| 4 | 35218656043 | `no_topics` | `WAITING_FOR_CANDIDATES` | 0 | P01 | MINOR 로그 전용 |
| 5 | 35238058711 | `no_topics` | `WAITING_FOR_CANDIDATES` | 0 | P01 | MINOR 로그 전용 |

**전체 5/5 슬롯 발화 + success 결론** — 크론 라이브 **확정 (분기 a)**.

---

## 소급 검증 4항목 (Verdict 요구사항)

### ① 슬롯별 4/4 (실제 5/5) 통과
- ✅ 5개 슬롯 모두 `schedule` 이벤트로 발화
- ✅ 모두 `success` 결론 (실패 0건)
- ✅ `no_topics` = P01 MINOR, 발행 실패 아님 (토픽 대기 상태)

### ② Mac [SKIP] 확인
```bash
grep "tco-hugo" logs/scheduler.log | tail -5
# 2026-09-17 23:55:11 [SKIP] tco-hugo owner=runner — runner 소유 (catchup)
```
- ✅ Mac 스케줄러가 tco-hugo를 `[SKIP]` 처리 (runner 소유 인식)
- ✅ `[PUBLISH] tco-hugo` 재출현 없음 → KILL-SWITCH 신호 ② **미발생**

### ③ Quota 양프레임 ≤5
- tco-hugo 발행 0건 (전 슬롯 `no_topics`)
- content.db / car.db / stap_content.db 동일일 INSERT 0건
- ✅ Quota 프레임 모두 0 ≤ 5

### ④ KILL-SWITCH 4신호 0건
| 신호 | 확인 결과 |
|------|-----------|
| ① quota 초과 / 이중 INSERT | ✅ 0건 (발행 0건) |
| ② Mac [PUBLISH] 재출현 | ✅ 0건 (`[SKIP]`만 확인) |
| ③ R2 manifest mismatch | ✅ 0건 (로그에 `manifest mismatch` 없음) |
| ④ Telegram 이중/중복 알림 | ✅ 0건 (P01 MINOR만 로그, Telegram 발송 안 함) |

**전 4신호 미발생** ✅

---

## ⚖️ 분할 판정 (Verdict 반영)

| 게이트 | 판정 | 근거 |
|--------|------|------|
| **메커니즘 게이트** | **PASS** | cron 5발화 `schedule` + tco-hugo 폴백 바인딩 + `publish-lock-car` + Mac [SKIP] 5/5 + KILL-SWITCH 4신호 0건 + quota 0/5 |
| **발행 레그** | **미실증 (보류)** | `no_topics` 5슬롯 = 불계류, 실발행 카운트 0건 |

> **발행 레그 증명은 G1 batch 1 (compare·deal) 첫 자동 슬롯 4/4로 흡수**

---

## R2 Round-trip 실증 (no_topics 5슬롯에서 실행 확인)

| 슬롯 | get_state | put_state | md5 검증 | 비고 |
|------|-----------|-----------|----------|------|
| 1 (전일) | ✅ 12/12 객체 복원+md5 OK | ✅ 12 객체 put + manifest 갱신 | ✅ | run 35130087799 |
| 2 | ✅ 12/12 객체 복원+md5 OK | ✅ 12 객체 put + manifest 갱신 | ✅ | run 35171314367 |
| 3 | ✅ 12/12 객체 복원+md5 OK | ✅ 12 객체 put + manifest 갱신 | ✅ | run 35200411685 |
| 4 | ✅ 12/12 객체 복원+md5 OK | ✅ 12 객체 put + manifest 갱신 | ✅ | run 35218656043 |
| 5 | ✅ 12/12 객체 복원+md5 OK | ✅ 12 객체 put + manifest 갱신 | ✅ | run 35238058711 |

**결과**: **R2 round-trip 레그 cron 하 5회 실증 완료** — 메커니즘 게이트 PASS의 핵심 근거.

---

## 정정 사항 (Verdict 반영)

1. **"첫 cron 23:30 UTC" 문구 → "첫 완료 슬롯 17:44 UTC (전일 슬롯1, run 35130087799)"**  
   → gh run list 실측 원값으로 정정 (지연 실측치로 기록 가치 유지)

2. **태그 일자 상충 해결**: `pre-destructive-20260918-2115` (실제 실행일자 2026-09-18 KST) 확정  
   → 차기 태그 명명 통일: `pre-destructive-YYYYMMDD-HHMM`

3. **오늘(2026-09-18 KST) = 풀사이클 1일차** 확정

---

## 후속 액션 (Verdict STEP 2 연계)

1. **금야 21:15 창** (KST) — 본 문서(갱신분) + B1-PREFLIGHT.md + worklog stage → 커밋 → push → `git show origin/main` 실증 → IndexNow 확인 → 해시·명세 보고
2. 잔여 슬롯(06:30 KST = 23:30 UTC 당일) 실시간 관찰 → quota 양프레임 + KILL-SWITCH 0건 유지 확인
3. 5/5 + 신호 0건 유지 시 **메커니즘 게이트 PASS 확정** (G-C 종결은 발행 레그 실증 후)

---

*근거: `gh run list`, `gh run view --log`, `logs/scheduler.log` 실측*