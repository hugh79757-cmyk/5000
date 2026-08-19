# Phase 0 — Gate 1 근본원인 진단 결과 (READ-ONLY)

- 진단 일시: 2026-08-20 (Task 1, 코드/DB/launchd 변경 없음)
- 진단 스크립트: `scripts/diagnose_analytics.py` + `tests/test_diagnose_analytics.py` (pytest 4건 PASS, READ-ONLY 보장)
- 진단 리포트: `logs/diagnose_analytics_*.json`

## 1. 근본원인 (Root Cause)

**1차 원인: 2026-08-11 08:30 이후 hang된 프로세스가 launchd의 재실행을 차단**

- `com.5000.analytics` (PID 746) — `collect_analytics.sh` 실행 중, 8/11 08:30 시작, **실행 시간 8-16:51:32 (약 9일)**, CPU 누적 0:00.01초, 상태 `S`(sleep)
- 자식 프로세스 PID 859 (`collect_ga4` python) — 8/11 08:30:25 시작, CPU 0:00.67, 상태 `S`
- `com.5000.analytics.watchdog` (PID 738) — 8/11 08:30 시작, 자식 PID 948/950 (`collect_ga4`) 동일하게 hang
- launchd는 작업이 **running** 상태이므로 `StartInterval`(21600초) 주기가 도래해도 새 실행을 spawn하지 않음 → 8/11 이후 모든 수집 중단

**2차 원인: 초기 블로킹 트리거**

- 8/11 시점 GSC/GA4/AdSense 수집 중 하나가 네트워크(DNS/타임아웃) 블로킹으로 멈춤 → `collect_analytics.sh`의 `|| echo` fallback은 **프로세스 블로킹 시에는 동작하지 않음** (하위 python이 반환되지 않음)
- watchdog(738)도 자체 hang → "8h 미실행 감지 → 강제 실행" 로직이 실행되지 못함

**현재 네트워크 상태: 정상 복구됨** (아래 6항목)

- `oauth2.googleapis.com` → 142.251.10.95 (해석 OK)
- `adsense.googleapis.com` → 172.217.118.4 (해석 OK)
- `searchconsole.googleapis.com` → 172.217.115.4 (해석 OK)
- 3개 endpoint 모두 HTTP 404 (인증 없는 요청에 대한 정상 응답 = TLS 도달성 정상)
- **판정**: 이전 감사(m0131)의 "DNS 해석 실패 (NameResolutionError)"는 **일시적 네트워크 환경 문제**였으며 현재는 해소됨

## 2. 신뢰도 (Confidence)

| 항목 | 신뢰도 | 근거 |
|------|--------|------|
| hang 프로세스 존재 | **높음** | ps 출력에서 5개 PID 모두 8/11 시작·sleep·CPU ~0 확인 |
| launchd 재실행 차단 | **높음** | launchctl list에서 state=running, runs=1, pid=746 |
| DNS/네트워크 현재 정상 | **높음** | dig 해석 + curl 404 응답 3/3 |
| 과거 DNS가 근본원인 | **중간** | 8/11 로그 꼬리의 NameResolutionError는 당시 상황, 현재는 복구 — 과거 트리거일 뿐 |
| 계정3 누락 원인 | **높음** | `collect_adsense` 루프 `[1,2]` 확인 (계획 Task 3), GSC는 이미 `[1,2,3]` |
| OAuth 만료 | **중간** | AdSense 전용 `adsense_token_*.json` expiry 만료(7/7, 5/19×2)이나 refresh_token 존재 → 자동 갱신 가능. 범용 `token_*.json`은 8/19 갱신됨 |

## 3. Task 2 안전성 (복구 실행 시)

계획 Task 2 (`recover_analytics.sh`)는 **kill -9 → 수동 수집 1회** 방식:

- **안전점**:
  - hang 프로세스(746/738 등)는 8/11부터 무응답이므로 kill로 인한 데이터 손실 없음 (DB 쓰기 중인 프로세스 아님 — analytics.db mtime 7/29 이후 변경 없음)
  - AdSense/GSC/GA4 API는 GET/읽기 전용 → 기존 데이터 덮어쓰기 위험 없음 (UNIQUE 제약으로 INSERT OR REPLACE)
  - DNS 정상이므로 수집 1회 실행 시 성공 가능성 높음
- **위험점**:
  - kill 후 launchd가 즉시 재실행하지 않을 수 있음 (StartInterval 대기) → `launchctl unload/load`로 강제 재시작 필요 (계획 Task 2 Step 2에 포함)
  - 수집 시 OAuth refresh 시도 → `adsense_token_*.json` 자동 갱신 (값 변경 없이 메타데이터만)
- **권장**: kill 전 `analytics.db` 스냅샷 백업 (계획 Task 7 rollback 스크립트 활용)

## 4. 필요 승인 (Approvals Required)

| 승인 항목 | 내용 | 게이트 |
|-----------|------|--------|
| GATE 1 (본 진단) | 진단 결과 승인 → Task 2 진행 | ✅ 요청 중 |
| GATE 2 | hang 프로세스 kill + 수동 수집 실행 | Task 2 종료 시 |
| GATE 3 | 계정3 루프 확장 `[1,2,3]` | Task 3 종료 시 |
| GATE 4 | blog_identity_map 구축 | Task 4 종료 시 |
| GATE 5 | gsc_pages INSERT 추가 | Task 5 종료 시 |
| GATE 6 | Q1~Q6 품질 게이트 | Task 6 종료 시 |
| GATE 7 | backfill/모니터링/롤백 + Q6 마감 | Task 7 종료 시 |

## 5. 롤백 조건 (Rollback Conditions)

- **수동 수집 실패 시**: kill한 프로세스 재생성 불필요 (launchd가 관리). 수집 오류는 `logs/analytics_collect.log`에 기록되며 데이터 손상 없음.
- **DB 오염 시**: `scripts/rollback_analytics.py`로 `analytics.db.bak_*` 복원 (Task 7 구현, 사전 스냅샷).
- **OAuth 갱신 실패 시**: `adsense_token_*.json`이 만료되어 refresh 불가하면 수집은 해당 계정만 건너뜀 (다른 계정 영향 없음) — 수동 재인증 필요 (인간 개입).
- **금지 사항 (본 Gate 1에서 수행 안 함)**: process kill, lock 삭제, 수동 수집, API 호출, 토큰 갱신, Task 2~7, 배포, git push — **전부 미수행**.

## 6. 데이터 현황 (조회 결과)

| 테이블 | 행 수 | MIN(date) | MAX(date) | 비고 |
|--------|-------|-----------|-----------|------|
| adsense_daily | 2393 | 2026-03-19 | **2026-07-28** | account-1/2는 7월까지, aikorea24/informationhot/twinssn은 4월까지 |
| gsc_keywords | 373 | 2026-07-05 | 2026-07-26 | 14일분 (얇음) |
| gsc_pages | **0** | — | — | 테이블 존재하나 수집 안 됨 (Task 5 대상) |
| gsc_daily_summary | 1191 | 2026-03-17 | 2026-07-26 | |
| ga4_daily | 230 | 2026-04-03 | 2026-07-28 | |
| ga4_pages | 1519 | 2026-04-03 | **2026-04-17** | 4월에만 (이후 미수집) |

- analytics.db 파일 mtime: 2026-07-29 00:58:25 (3.6MB)
- AdSense 계정별: account-1(615행, 07-02~07-28), account-2(461행, 07-02~07-28), aikorea24(90행, 03-19~04-17), informationhot(389행, 03-19~04-17), twinssn(838행, 03-19~04-17)
  - 주의: 계정 네이밍이 과거(twinssn/informationhot/aikorea24, 3-4월) → 최근(account-1/account-2, 7월)로 변경됨. 계정3(aikorea24)은 4월 이후 수집 중단.

## 7. 수행 금지 확인

- [x] process kill: 미수행
- [x] lock 파일 삭제: 미수행 (token_*.json.lock 3건 존재하나 삭제 안 함)
- [x] 수동 수집 실행: 미수행
- [x] API 호출/토큰 갱신: 미수행 (메타데이터 조회만)
- [x] Task 2~7 실행: 미수행
- [x] 배포/push: 미수행

---

## 잔존 위험

1. **DNS 일시성**: 현재 정상이나 네트워크 환경이 다시 불안정해지면 수집이 재차 hang 가능 — Task 7 모니터링 강화로 조기 감지 필요.
2. **계정3 네이밍 혼재**: adsense_daily.account에 과거/최근 네이밍이 섞여 있어, Task 3 루프 확장 후 데이터 정합성(Q5) 재검증 필요.
3. **ga4_pages 4월 정지**: 수집 주기가 바뀐 것인지 별도 파이프라인인지 불명 — Task 5와 별개로 조사 필요 (Phase 0 범위 외일 수 있음).
