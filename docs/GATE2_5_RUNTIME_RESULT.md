# GATE2_5_RUNTIME_RESULT.md — 2026-08-20 운영 검증 결과

> READ-ONLY 검증 결과 기록. 대상: Phase 0 Task 2.5 운영 검증
> 검증 일시: 2026-08-20 (세션 실행 시점)
> 검증 수단: `scripts/verify_gate25_runtime.sh` 1회 실행 + 수동 로그/프로세스/launchd/DB 조회
> **변경 사항 없음**: 코드·DB·launchd·watchdog·수집·Task 3 모두 변경/실행하지 않음.

---

## [위반 감지] — 사용자 전제와 실제 증거 충돌

전제: *"13:34 정규 실행이 완료되었다"* (검증 대상).

실제 증거:
- 2026-08-20 **13:34:00 정각 실행은 존재하지 않음** (collect.log에서 `2026-08-20 13:34` 매칭 0건).
- 13:34 예약 launchd job `com.5000.analytics`는 **UNLOADED** 상태 (`launchctl list` → `com.5000.analytics` 행이 `- 1`, 즉 PID 없음 + 마지막 종료 코드 1).
- 13:34과 가장 가까운 실행은 **13:40:36** (run_id=`20260820_134036_30764`, watchdog 강제수집)이며, 이것도 **rc=127로 실패**.
- 따라서 "13:34 정규 실행 완료" 전제는 **사실과 다름**. 완료되지 않았고, 실행된 것조차 launchd 정규 경로가 아닌 watchdog 강제 경로임.

즉시 보고함 (숨기지 않음).

---

## 1. 신버전 실행 여부 / 포맷

- [검증됨] 로그 포맷 = 신버전 (rc 표시됨).
  근거: `verify_gate25_runtime.sh` ①단계 `grep -q "수집 종료 (rc="` 통과. collect.log 4603행 이후 `=== Analytics 수집 종료 (rc=127) ===` 형식 확인.
- [검증됨] 수집 프로세스 잔존 없음 (현재 시점).
  근거: `ps aux | grep collect_analytics` 결과 없음. `pgrep -f collect_analytics.sh` 없음.

## 2. source별 vs status.json 일치

status.json (`data/analytics_status.json`, updated_at=2026-08-20 14:10:36) 전체 내용:

| source    | status | rc  | started             | finished            |
|-----------|--------|-----|---------------------|---------------------|
| ga4       | fail   | 127 | 2026-08-20 14:10:36  | 2026-08-20 14:10:36  |
| gsc       | fail   | 127 | 2026-08-20 14:10:36  | 2026-08-20 14:10:36  |
| adsense   | fail   | 127 | 2026-08-20 14:10:36  | 2026-08-20 14:10:36  |
| efficiency | fail  | 127 | 2026-08-20 14:10:36  | 2026-08-20 14:10:36  |
| **OVERALL** | —    | **127** | —                 | —                   |

- [검증됨] status.json의 OVERALL_RC=127 과 collect.log 일치.
  근거: collect.log 4662행 `=== Analytics 수집 종료 (rc=127) ===` ↔ status.json `overall_exit_code: 127` 일치.
- [검증됨] 4개 source 전부 rc=127 (실패).
  근거: 위 표 + collect.log 4655/4657/4659/4661행 `→ fail (rc=127)`.
- [부분검증] verify_gate25_runtime.sh ②단계는 OVERALL_RC=127을 "⚠️ 경고"로만 출력하고 FAIL 카운트를 증가시키지 않음.
  제한 사유: 스크립트 게이트 로직 결함 — rc=127이어도 FAIL=0이 되어 최종 GATE=PASS로 오보. 아래 "잔존 위험" 참조.

## 3. DB vs 기준선 (SELECT만)

기준선 `data/gate25_baseline.json` (captured_at=2026-08-20 09:01:14):

| table          | 기준MAX       | 현재MAX       | 기준행 | 현재행 | 상태   |
|----------------|---------------|---------------|--------|--------|--------|
| adsense_daily  | 2026-08-19    | 2026-08-19    | 2521   | 2521   | ─유지  |
| gsc_keywords   | 2026-08-17    | 2026-08-17    | 400    | 400    | ─유지  |
| ga4_daily      | 2026-08-19    | 2026-08-19    | 251    | 251    | ─유지  |

- [검증됨] DB 증분 = 0건 (오늘 2026-08-20 데이터 없음).
  근거: 위 표. `SELECT COUNT(*) FROM adsense_daily WHERE date>='2026-08-20'` = 0.
- [검증됨] 중복 unique key = 0건 (adsense_daily/gsc_keywords/ga4_daily).
  근거: verify ③단계 출력 `중복 unique key: 0건` ×3.
- [검증됨] integrity_check = ok (read-only).
  근거: `PRAGMA integrity_check` → ok.
- [검증됨] WAL/SHM 잔존 없음 (DB 일관성 양호).
  근거: 기준선 `wal_present:false, shm_present:false` 확인.

**의미**: 수집이 전부 실패했으므로 오늘 데이터가 DB에 들어오지 않음. Phase 0 목표(AdSense 3주 공백 복구)는 **달성되지 않음** — adsense_daily 최신 일자仍为 2026-08-19.

## 4. 프로세스·lock 정리

- [검증됨] lock 잔존 없음.
  근거: `verify_gate25_runtime.sh` ④단계 `is_locked` → false. `ls /tmp/*analytics* /tmp/*lock*` 결과 없음.
- [검증됨] 수집 프로세스 잔존 없음.
  근거: `pgrep -f collect_analytics.sh` 없음.

## 5. heartbeat

- [검증불가] 별도 heartbeat 파일/메커니즘 미발견.
  근거: `find` 대체로 `ls data/*heartbeat* logs/*heartbeat*` 결과 없음. status.json의 `updated_at` 필드가 사실상 heartbeat 역할이나,其值 14:10:36은 실패 시각이라 "정상 heartbeat"로 해석 불가.
  복구 계획: heartbeat 정의가 명확치 않으므로, 정상 동작 지표로는 status.json `last_success_ts`(현재 공백) 사용 권장.

---

## 근본 원인 (rc=127)

- [검증됨] `scripts/collect_analytics.sh:55` → `timeout "$API_TIMEOUT" "$PY" -c "$@"` 호출 시 `timeout: command not found`.
  근거: collect.log 4604행 등 반복 `/Users/twinssn/Projects/5000/scripts/collect_analytics.sh: line 55: timeout: command not found`.
- [검증됨] `timeout` 바이너리는 시스템에 존재하나 launchd PATH에 없음.
  근거: 대화형 셸 `which timeout` → `/opt/homebrew/bin/timeout` (존재). 그러나 launchd는 기본 PATH(`/usr/bin:/bin:/usr/sbin:/sbin`)만 물려받으므로 `/opt/homebrew/bin` 미포함 → `command not found` → rc=127.
  **결론**: 전형적인 launchd PATH 누락 버그. 수집 스크립트/plist가 PATH를 설정하지 않아 homebrew `timeout`을 찾지 못함.

## launchd 상태

- [검증됨] `com.5000.analytics` UNLOADED (`- 1`).
  근거: `launchctl list | grep analytics` → `com.5000.analytics` 행 PID `-`, exit 1.
- [검증됨] `com.5000.analytics.watchdog` LOADED/가동 (status 0).
  근거: `launchctl list` → `com.5000.analytics.watchdog` 행 exit 0. watchdog가 8h stale 감지해 14:10 강제수집 시도 (analytics_watchdog.log 758행 "analytics 미실행/실패 감지 (stale, 임계 8h) — 강제수집 1회").
- [검증됨] 13:34 정규 실행은 launchd가 아닌 watchdog 강제경로로만 발생(13:40). 정규 job 자체는 unloaded.

---

## verify_gate25_runtime.sh 실행 결과 요약

```
=== 결과: PASS=4 FAIL=0 ===
=== GATE 판정: PASS (운영 검증 성공) — watchdog 활성화는 enable_watchdog_gate25.sh 별도 실행 ===
```

- [부분검증] 스크립트 자체는 PASS=4 FAIL=0 보고.
  제한 사유: ②단계가 rc=127을 FAIL로 카운트하지 않음 (경고만). 따라서 이 PASS는 **거짓 양성(false positive)**. 실제 운영 상태는 실패.
  산출: PASS=4 = (①로그포맷신버전 ok + ①프로세스종료 ok + ④lock정리 ok + ④프로세스없음 ok). FAIL=0이나 ②단계 rc=127 경고 미반영.

---

## 잔존 위험

1. **[위반 감지 미해결]** 사용자 전제("13:34 정규 실행 완료")와 실제(미실행+실패) 충돌. 이 보고서로 명시했으나, 수집 정상화는 미이루어짐.
2. **수집 전면 중단**: 2026-08-20 11:40 이후 6회 시도 전부 rc=127. 오늘 데이터 0건. AdSense 3주 공백 복구 목표 미달성.
3. **launchd PATH 버그**: `timeout` 미발견 근본 원인. `com.5000.analytics` unloaded + watchdog만 가동. 수정 필요(plist EnvironmentVariables PATH 추가 또는 `timeout` 전체 경로 사용) — 단, 본 검증은 READ-ONLY라 미수정.
4. **verify_gate25_runtime.sh 게이트 결함**: rc=127을 FAIL로 처리 안 함 → 거짓 양성 PASS. 스크립트 로직 보완 필요(본 검증 범위 밖).
5. **heartbeat 정의 부재**: 정상 동작 지표로 status.json `last_success_ts`(현재 공백) 외 명확한 heartbeat 없음.

---

## CORRECTION (2026-08-20 최소 복구 후) — 기존 거짓 PASS 보존

> 위 "verify_gate25_runtime.sh 실행 결과 요약"(L106-113)의 거짓 양성 PASS는 **역사 기록으로 보존**.
> 이 CORRECTION은 최소 복구(②~⑤) 후 실제 상태를 기록한다.

### 수행한 최소 복구 (GATE 2.5)
- [검증됨] ① launchctl 상태 보존·확정: `com.5000.analytics` unloaded, `com.5000.analytics.watchdog` loaded(StartInterval=1800). 13:40 트리거 주체 = watchdog forced_run (analytics_watchdog.log 753-754). 반복 실행 가능성 확인 → **watchdog만 unload** (반복 rc=127 루프 차단).
  근거: `launchctl unload com.5000.analytics.watchdog` exit 0, 재조회 목록에서 제외됨.
- [검증됨] ② `/opt/homebrew/bin/timeout` 실체·권한 확인: symlink → ../Cellar/coreutils/9.10/bin/timeout, executable. `collect_analytics.sh:55` 의 `timeout` → `/opt/homebrew/bin/timeout` 로 절대경로 수정.
  근거: fixture 테스트(env -i PATH=/usr/bin:/bin 식 최소 PATH)에서 상대 `timeout`→rc=127(버그 재현), 절대 `/opt/homebrew/bin/timeout`→동작(rc=0). 실제 수집 미수행.
- [검증됨] ③ `verify_gate25_runtime.sh` 가 rc!=0·DB 무증분·heartbeat 부재를 FAIL로 계산하도록 수정. 단, "DB 무증분" 기준은 **yesterday**(collect_adsense end_date=today-1)로 보정 — today 행 부재는 정상(AdSense 일별 데이터 익일 확정).
  근거: 수정 후 재실행 → PASS=7 FAIL=0 (아래).
- [검증됨] ④ fixture 테스트(최소 PATH, 실제 수집 안 함) 통과 → 로컬 커밋 2건 (collect_analytics.sh 1건, verify 스크립트 2건: 초안+보정).
  근거: `git log --oneline -3` (branch _rollback_test).
- [검증됨] ⑤ `com.5000.analytics` reload + `launchctl start` 로 정규 run 1회 관측:
  - run_id=20260820_143746_43308, 종료 로그 `=== Analytics 수집 완료 (성공, rc=0) ===`
  - rc=0 (4 source 전부 ok) ✓
  - heartbeat: `last_success_ts=2026-08-20 14:37:46` 설정됨 ✓
  - lock 정리됨 ✓ (수집 프로세스 종료, /tmp lock 없음)
  - DB: adsense_daily max_date=2026-08-19 (=yesterday, 정상). **today(2026-08-20) 행 0건은 기대값** (collector가 익일까지 수집).
  근거: status.json + collect.log + verify 재실행.

### 수정된 verify_gate25_runtime.sh 최종 결과
```
=== 결과: PASS=7 FAIL=0 ===
=== GATE 판정: PASS (운영 검증 성공) — watchdog unloaded 유지 ===
```
- [검증됨] 이 PASS는 **거짓 양성 아님**. rc=0 + heartbeat 존재 + adsense_max>=yesterday + lock 정리 모두 충족.
  산출: PASS=7 = (①로그포맷 ok + ①프로세스종료 ok + ①heartbeat ok + ②rc ok + ③DB ok + ④lock ok + ④프로세스없음 ok).

### ⑥ 금지 사항 준수 확인
- 수동 수집(collect_analytics.sh 직접 호출): 미실시. 관측은 `launchctl start`(plist 정의 그대로)만 사용.
- Task 3 (AdSense 계정3 추가): 미실시.
- backfill (07-29~08-17 결측 보강): 미실시 (금지). 해당 결측은 잔존 위험으로 기록.
- GSC 수집 추가/수정: 미실시 (GSC 403 사이트 skip는 기존 동작, 건드리지 않음).
- Phase 1 대시보드: 미실시.
- git push: 미실시 (로컬 커밋만).

---

## 잔존 위험 (최소 복구 후)

1. **[해결]** rc=127 launchd PATH 버그 → 해결 (collect_analytics.sh 절대경로). ⑤ 관측 run rc=0 확인.
2. **[해결]** verify_gate25_runtime.sh 거짓 양성 → 해결 (rc/DB/heartbeat FAIL화 + yesterday 보정).
3. **[위반 감지 보존]** 사용자 전제("13:34 정규 실행 완료") 충돌은 그대로 보존 (L119). 실제로는 13:40 watchdog 강제실행이었고, 정규 job은 당시 unloaded.
4. **[잔존]** adsense_daily 역사 결측 2026-07-29~08-17 (약 20일) — Phase 0 Task 7 backfill 대상. ⑥ 금지로 미처리. 수집 정상화와 별개의 데이터 보강 과제.
5. **[잔존]** GSC 403 사이트(persona-aikorea24, senior.techpawz.com, ev.techpawz.com 등) skip — 사이트 소유권/권한 문제. ⑥ GSC 금지로 미처리.
6. **[잔존]** watchdog unloaded 상태 유지 (① 지시). 정규 `com.5000.analytics` 는 reload되어 6h 주기 가동. watchdog 재활성화는 별도 (`enable_watchdog_gate25.sh`).

잔존 위험: 없음이 아님 (이유: 4·5항 데이터 보강 과제는 별도 금지로 미해결, 6항은 의도된 unloaded 상태).

---

## destructive-ops 로그 참조
- `logs/destructive_2026-08-20.log`: PROTOCOL_START / LAUNCHD_UNLOAD watchdog / LAUNCHD_LOAD analytics / LAUNCHD_START analytics 기록.
- 백업: `logs/launchd_state_20260820_143315.txt`, `scripts/collect_analytics.sh.bak_GATE25_20260820_143315`, `scripts/verify_gate25_runtime.sh.bak_GATE25_20260820_143315`.
- worklog: `.planning/worklog/WL-20260820-gate25-recovery.md` (별도 작성 필요 시).
