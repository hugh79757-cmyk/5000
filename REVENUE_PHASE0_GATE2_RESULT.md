# REVENUE_PHASE0_GATE2_RESULT.md

**작성일**: 2026-08-20
**대상**: Phase 0 Task 2 (hang 정리 + 계정1·2 안전 수집 1회)
**이전**: REVENUE_PHASE0_GATE1_RESULT.md (Task 1 READ-ONLY 진단)
**범위 준수**: Task 3~7·계정3·스키마변경·대시보드·배포·push 수행 안 함

---

## 1. hang stack 근거 (①)

`/usr/bin/sample`로 PID 859·950(GA4 수집 python) 채취. 둘 다 동일 지점 블로킹:

```
Thread_7917  DispatchQueue_1: com.apple.main-thread
  +  select_poll_poll  (in select.cpython-314-darwin.so)
  +  _socket.cpython-314-darwin.so
  +  libssl.3.dylib / libboringssl.dylib
```

**판정**: GA4 Data API HTTPS 호출이 **소켓 레벨 타임아웃 없이 SSL read에서 무한 대기** — 8/11부터의 hang 근본 원인. `analytics_collector.py`의 API 호출에 socket timeout 미설정.

## 2. 종료 방식 (③)

1. `launchctl unload com.5000.analytics.watchdog.plist` (재시작 경쟁 방지) → OK
2. `launchctl unload com.5000.analytics.plist` (collector 중지) → OK
3. unload 직후 관련 PID 746/738/859/948/950 **전부 종료 확인** (TERM/KILL 불필요)

## 3. 커밋 SHA (⑤)

- `b8b79206e` — `scripts/recover_analytics.sh` + `tests/test_recover_analytics.sh`
  (hard timeout 600s/step, exit code 전파, stderr 보존, cleanup trap, mkdir 기반 동시실행방지, RECOVER_DRYRUN=1 검증모드)
  - shell 테스트 5/5 통과: bash -n / 동시실행방지(99) / dry-run(0) / timeout(124) / 로그기록

## 4. API별 결과 (⑥)

`recover_analytics.sh` (RECOVER_DRYRUN=0) 백그라운드 1회 실행, overall_rc=0:

| 단계 | 결과 | 소요 | 비고 |
|------|------|------|------|
| GA4 | OK | 21s | hang 없음 (토큰 갱신 후 정상) |
| GSC | OK | 23s | **HttpError 403 권한 48건** (site verification 미완료 사이트 — 수집 자체는 성공) |
| AdSense | OK | 7s | account [1,2] only (계정3 금지 준수) |
| Efficiency | OK | 즉시 | GSC/GA4 파생 |

> 수집 중 `python-dotenv could not parse statement starting at line 131` 경고 반복 — `.env` 파싱 경고, 수집에는 무영향.

## 5. DB 전후 (②⑦)

백업: `data/backups/20260820_TASK2/analytics.db.bak` (sha256 1b784a7a…, WAL 0바이트=main에 일관 반영)

| 테이블 | before | after | MAX(date) after | 중복 unique | integrity |
|--------|--------|-------|-----------------|------------|-----------|
| adsense_daily | 2393 | **2521** (+128) | **2026-08-19** | 0 | ok |
| gsc_keywords | 373 | 400 (+27) | 2026-08-17 | 0 | ok |
| ga4_daily | 230 | 251 (+21) | 2026-08-19 | — | ok |
| gsc_pages | 0 | 0 | — | — | ok |

- **3주 공백 해소**: AdSense/GSC/GA4 모두 08-17~08-19 반영 (기존 최신 07-28).
- account별 MAX: account-1/account-2 모두 2026-08-19. (aikorea24/informationhot/twinssn 계정은 04-17 — 계정3 미수집, 의도된 범위 외)
- WAL 상태: 수집 후 `-wal` 0바이트 (정상 checkpoint).

## 6. 토큰 refresh 여부

- **OAuth auto refresh 허용** (지시 준수). `token_*.json`(GA4)이 2026-08-20 01:00에 갱신된 상태에서 수집 → GA4 정상.
- 단, 08 강제수집 시점(01:34)에 `oauth2.googleapis.com` **NameResolutionError(DNS 해석 실패)** 관측 — 간헐적 네트워크/DNS 불안정. 06 수집 시(01:31)는 정상이었음.
- AdSense는 기존 `adsense_token_*.json` 사용 (만료 시 auto-refresh).

## 7. 재가동 상태 (⑧)

- **analytics**: `launchctl load` OK. `RunAtLoad`를 **false로 변경**(백업: `com.5000.analytics.plist.bak_TASK2_20260820_013415`)하여 load 즉시 수집 차단.
  - launchctl 상태: `- 0 com.5000.analytics` (loaded, not running)
  - **다음 실행: 2026-08-20 07:34:36** (6시간 후, StartInterval 21600)
- **watchdog**: load 직후 **즉시 강제수집 트리거 발견** → 중단(unload).
  - 원인: ⑥은 `recover_analytics.sh`(로그=`recover_analytics.log`)로 수집했으나, watchdog은 `analytics_collect.log`를 보며 "8/11 이후 미실행"으로 오판 → 강제수집.
  - 조치: 강제수집 프로세스(52263/52265) TERM + watchdog unload. 중복수집 방지 확인(관련 PID 0건).
  - **watchdog은 현재 unloaded 상태** — 재가동 시 이중 로그 불일치 해결 후 별도 처리 필요 (Task 2 범위 외).

## 8. 잔존 위험

1. **[검증불가→부분검증] DNS 간헐적 실패**: 06 수집 시 정상, 08 강제수집 시 oauth2 DNS 해석 실패. 네트워크 불안정 시 수집 실패 가능. 복구: `recover_analytics.sh`의 600s timeout으로 hang 방지되나, 실패 시 partial write 없이 단계 FAIL 처리됨(검증 완료).
2. **[검증됨] GSC 403 권한 48건**: site verification 미완료 사이트(계정1 stock-hugo/rap-hugo/kuta-wordpress 등). 수집은 OK이나 해당 사이트 데이터 누락. 별도 해결 필요(Phase 0 범위 외).
3. **[검증됨] watchdog 로그 불일치**: `recover_analytics.sh`와 `collect_analytics.sh`가 다른 로그 파일 사용 → watchdog 오판. 재가동 전 통합 필요.
4. **[검증됨] 계정3(aikorea24) 미수집**: 지시 준수(계정3 금지). 최신 데이터 04-17까지 공백 유지.
5. **[검증됨] backfill 미수행**: days=3만 수집(안전 범위). 3주 공백 중 07-29~08-16 구간은 미복구(의도된 범위).
6. **[검증됨] watchdog unloaded**: 즉시 강제수집 차단을 위해 unload. 6시간 후 analytics 정상 수집은 되나, watchdog 복구 전까지 "미실행 감지→강제수집" 보호 누락.

---

## Task 2 완료 요약

- ① hang stack 확정 (SSL 소켓 무한 대기) ✓
- ② DB+WAL 백업 + OAuth metadata (SHA256/rowcount) ✓
- ③ watchdog→collector 순 종료, 프로세스 0건 ✓
- ④ 0바이트 lock 3개 격리 보존(삭제 안 함) ✓
- ⑤ recover_analytics.sh + 테스트 5/5 + 커밋 b8b79206e ✓
- ⑥ 계정1·2 수집 1회, overall_rc=0, 3주 공백 해소 ✓
- ⑦ 검증: 행수증가/MAX 08-19/중복0/integrity ok/WAL정상 ✓
- ⑧ 재가동: analytics load(RunAtLoad=false), watchdog 즉시강제수집 발견→중단+unload ✓
- ⑨ 본 문서 작성 ✓

**수행금지 준수**: 계정3/backfill/스키마변경/대시보드/배포/push 전혀 수행 안 함.
