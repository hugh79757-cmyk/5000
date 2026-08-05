---
phase: quick-260805-d7c
plan: 1
status: complete
subsystem: curation-pipeline
tags: [no_keyword, curation, scheduler, catchup, golf-hugo, bike-hugo]
requires: []
provides:
  - "golf/bike 24개 키워드 상품 데이터 (curation.db products ≥3건)"
  - "scheduler catchup/register 시각 파싱 방어 가드 (malformed skip)"
affects:
  - scheduler.py
  - data/curation.db
  - config/blogs.d/tap.yaml (미수정 — 사용자 결정 준수)
tech-stack:
  added: []
  patterns:
    - "시각 파싱 방어 가드 (split 길이 + ValueError try/except, malformed skip + warning)"
key-files:
  created: []
  modified:
    - scheduler.py (_catchup_missed_inner + register_schedules 가드)
decisions:
  - "tap.yaml 미수정 — 가드 수정이 승인된 해법 (사용자 결정 locked 준수)"
  - "register_schedules에도 동일 가드 패턴 적용 (Rule 3 blocking fix)"
metrics:
  duration: "18분 (09:35→09:53)"
  completed: "2026-08-05T09:53:00+07:00"
---

# Phase quick-260805-d7c Plan 1: golf/bike no_keyword 발행 실패 해소 + catchup 시각 파싱 크래시 방어 가드

## One-liner

golf-hugo/bike-hugo의 `no_keyword` 발행 실패(키워드 상품 0건)를 curation.db 수동 수집 + 스케줄러 재시작으로 해소하고, 동일 실패를 재발시키는 catchup/register 시각 파싱 크래시(ValueError/TypeError)를 scheduler.py 방어 가드로 제거.

## Tasks

### Task 1: golf/bike 키워드 수동 수집 (fresh 프로세스)

**결과: [검증됨]**

- fresh 프로세스 KEYWORD_MAP = 2985 (근거: `.venv/bin/python3 -c "..."` 출력 `total_kw = 2985`)
- auto_collector fresh 실행: `[auto_collector] 전체 2985개` 로그 확인 (근거: `/tmp/auto_collector_evidence_260805.log` line 2, `결과: {... 'total_kw': 2985 ...}`)
- 24개 키워드 전부 products ≥ 3건 (근거: 플랜 검증 쿼리 exit 0, `미달 키워드: 없음 — 24/24 통과`)
- **숫자 분해**: 24 = 15 (1차 보충 수집, rate limit 전) + 9 (2차 보충 수집, 분당 창 복귀 후)
  - golf 12개: 10/9/10/10/9/9/10/10/10/10/10/9건 (골프클럽~스윙연습기)
  - bike 12개: 3개(전기자전거 10, 접이식 10, 로드 10) + 9개(MTB 9, 미니벨로 8, 하이브리드 7, 헬멧 7, 킥보드 8, 자물쇠 10, 라이트 4, 아동 7, 거치대 10)
- **부분 상태 보고 (설계된 rate limit 동작)**: 1차 보충 중 `_check_rate_limit()`이 40/40 분당 한도 도달 감지 → MTB자전거 앞에서 즉시 중단 (15/24 수집 상태 명확히 보고). 자동 재시도 없음 (계획 준수). 분당 창 경과 후 2차 실행으로 잔여 9개 수집. 쿠팡 API 제재(서버 차단) 없음 — 최종 rate 상태 시:83/300.
- 비파괴: INSERT OR REPLACE만 수행 (collector.py collect_keyword 로직), 스키마/설정 불변 확인.

**커밋: 없음** — data/curation.db는 gitignored (`git check-ignore data/curation.db` → IGNORED 확인). 코드 변경 없음.

### Task 2: scheduler.py catchup 시각 파싱 방어 가드

**결과: [검증됨] (부분검증 항목 명시)**

- py_compile + import: [검증됨] — `.venv/bin/python3 -m py_compile scheduler.py && import scheduler` → `import OK`
- 가드 repro: [부분검증] — 계획이 명시한 로직 미러링 검증. tap-blogger 실제 데이터(`['06:00', 600, 840]`)에서 예외 없이 '06:00'만 카운트 (`expected=1`). 실제 함수 실행은 계획대로 Task 3 재시작 후 관찰로 검증.
- **실제 동작 검증 (Task 3에서 관찰): [검증됨]** — 재시작 후 `CATCHUP: 잘못된 스케줄 시각 무시 — tap-blogger time=600/840` warning 4회 (09:44:13, 09:51:33 — 2회의 catchup 패스), ValueError 신규 0건, 다른 블로그 catchup 정상 진행.
- diff 최소성: `git diff scheduler.py` — 해당 블록 외 다른 라인 변경 없음 확인.

**커밋: `2871c889c`** — `fix(quick-260805-d7c): catchup 시각 파싱 방어 가드 — malformed 시각 skip`

### Task 3: 스케줄러 재시작 + end-to-end 검증

**결과: [검증됨] (항목별 근거 포함)**

| 검증 항목 | 결과 | 근거 |
|-----------|------|------|
| 새 PID | [검증됨] | 54024 → **12380** (launchctl list) |
| 재시작 후 크래시 | [검증됨] | restart line(46379, 09:41:34) 이후 ValueError/TypeError/not enough values **0건** (awk 라인 번호 기준) |
| CATCHUP 정상 흐름 | [검증됨] | 재시작 후 CATCHUP: 21라인 (compare/rank/pick/golf/bike/senior 등 정상 진행) |
| auto_collector 2985 로드 | [검증됨] | 09:50:14 `[auto_collector] 전체 2985개 \| 캐시없음 0개 \| 만료 2622개 \| 신선 363개` + `total_kw: 2985` — 재시작된 프로세스가 최신 KEYWORD_MAP 로드의 결정적 증거 |
| stale lock | [검증됨] | `lsof data/.lock_golf-hugo data/.lock_bike-hugo` — 활성 홀더 없음 (flock 해제 상태, 파일 존재는 정상) |
| golf-hugo 발행 | [검증됨] | dispatcher smoke: `{"success": true, "title": "발 편한 남성 골프화 선택 기준과 브랜드별 특징 비교", "keyword": "골프화", "product_count": 5}` + `[deploy] OK: golf-hugo` + live `https://golf.informationhot.kr/posts/발-편한-남성-골프화-선택-기준과-브랜드별-특징-비교/` → **200** |
| bike-hugo 발행 | [검증됨] | 재시작된 스케줄러가 09:42:31~09:43:27 자체 catchup으로 발행 성공: `{"success": true, "title": "붐고Bacicle 전기자전거 추천 2026년 8월 엄선", "keyword": "전기자전거", "product_count": 5}` + `[PUBLISH] bike-hugo 발행 성공` + live → **200** |

**커밋: 없음** (Task 3 자체 코드 변경 없음 — Rule 3 수정 커밋은 별도 `64a9874a9`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] register_schedules() 재시작 크래시 (TypeError) 방어 가드 추가**
- **Found during:** Task 3 (스케줄러 재시작 직후)
- **Issue:** 재시작된 프로세스가 시작 시 `register_schedules()`(scheduler.py:629)에서 tap-blogger의 YAML sexagesimal int(600/840)를 `schedule.every().day.at(t)`에 전달 → `TypeError: at() should be passed a string` → 프로세스 시작 실패 (exit 1, launchd PID `-`). 구 프로세스(54024)는 register_schedules가 시작 시 1회만 실행되고 config 로드 시점이 8/3(정상 times)이라 생존했던 것. catchup 가드만으로는 재시작이 불가능해 Task 3의 핵심 산출물(새 PID 가동)이 차단됨.
- **Fix:** catchup 가드와 동일 패턴 적용 — `split(":")` 길이 가드 + ValueError try/except, malformed skip + `SCHEDULE:` warning. 유효 "HH:MM" 시맨틱 불변. tap.yaml 미수정 (사용자 locked 결정 준수). 전체 config 스캔으로 malformed 시각이 tap-blogger 2건뿐임을 확인 후 적용.
- **Files modified:** scheduler.py (register_schedules, ~line 627-638)
- **Commit:** `64a9874a9`
- **검증:** py_compile OK, repro에서 `SCHEDULE: 잘못된 스케줄 시각 무시 — tap-blogger time=600/840` + 130 jobs 등록 크래시 없음, 실서비스 재시작 후 122 jobs 등록 정상.

**2. [설계된 rate limit 부분 상태] Task 1 보충 수집 분할**
- 1차 보충 수집이 40/40 분당 한도에서 중단 (15/24) — 플랜 T-260805-01 완화책(사전 검사 + 즉시 중단 + 부분 보고)이 정확히 동작. 분당 창 복귀 후 9개 잔여 수집으로 24/24 달성. 자동 재시도 없음.

**3. [Task 3 smoke 변형] bike-hugo quota_met**
- 계획은 "dispatcher.py bike-hugo success true"를 요구했으나, 재시작된 스케줄러가 09:42:31~09:43:27에 bike-hugo를 자체 발행 성공(quota 1/1 소진) → dispatcher smoke는 `{"success": false, "reason": "quota_met"}` 반환. no_keyword 실패는 아님. 발행 성공 증거는 스케줄러 자체 OUT(success true, product_count 5) + ledger status='published' + live 200으로 확보.

## Verification

- Task 1: curation.db products 24/24 키워드 ≥ 3건 — **[검증됨]** (자동 검증 쿼리 exit 0)
- Task 2: py_compile + import — **[검증됨]** / 가드 repro — **[부분검증]** (계획 명시: 로직 미러링, 실함수는 Task 3 관찰로 검증)
- Task 3: 새 PID, ValueError 0건, CATCHUP 정상, dispatcher 스모크 success, auto_collector 전체 2985개 — **[검증됨]**
- AGENTS.md 3분법 + 산출 근거 + 잔존 위험 — 본 요약에 반영

## Success Criteria

- [✅] curation.db products에 golf-hugo 12개 + bike-hugo 12개 키워드 전부 ≥ 3건.
  근거: 검증 쿼리 `미달 키워드: 없음 — 24/24 통과` (exit 0)
- [✅] 스케줄러 새 PID(12380) 가동, catchup 크래시(ValueError) 재발 0건.
  근거: restart line 46379 이후 ValueError/TypeError 0건 (awk 라인 번호 기준)
- [✅] 재시작된 스케줄러 auto_collector 2985개 로드.
  근거: 09:50:14 `[auto_collector] 전체 2985개` + `total_kw: 2985` (line 46470+)
- [✅] golf-hugo/bike-hugo 발행 success (no_keyword 소멸).
  근거: golf dispatcher success:true + bike 스케줄러 발행 success:true, live 둘 다 200
- [✅] 변경 파일: scheduler.py만 (data/curation.db는 gitignored 데이터 변경).
  근거: `git check-ignore data/curation.db` → IGNORED. 커밋 2건 모두 scheduler.py만 변경

## Commits

- `2871c889c` — fix(quick-260805-d7c): catchup 시각 파싱 방어 가드 — malformed 시각 skip (Task 2)
- `64a9874a9` — fix(quick-260805-d7c): register_schedules 시각 파싱 가드 — 재시작 크래시 차단 (Rule 3 deviation)

## Known Stubs

없음 — 생성/수정 파일에 stub 패턴(빈 리스트 하드코딩, placeholder 텍스트, 데이터 미배선 컴포넌트) 없음. (products 데이터는 실수집 결과, scheduler.py 가드는 실동작 확인)

## 잔존 위험

1. **tap-blogger 10:00/14:00 슬롯 소실** — 600/840 int가 skip되어 tap-blogger는 06:00 1회만 스케줄됨. 가드 skip이 승인된 동작이지만, 10:00/14:00 발행 복원을 원하면 tap.yaml에서 times를 따옴표 처리('10:00')해야 함 — 사용자 결정 사항, 본 플랜 범위 밖.
2. **golf/bike 일일 발행량 quota 1 제한** — no_keyword는 해소됐으나 두 블로그 모두 daily_quota=1로 하루 1건 발행. 오늘 quota는 양쪽 모두 소진(스모크 + 스케줄러 발행). 발행량 확대는 별도 사용자 결정 필요.
3. **curation.db 상품 캐시 3일 만료** — CACHE_DAYS=3, :50 사이클의 auto_collector가 자동 갱신 (현재 캐시없음 0개, 사이클 정상 동작 확인). 별도 조치 불요.
4. **쿠팡 API 제재 이력(2026-07-16) 재발 가능성** — rate limit 가드(분40/시300)는 정상 동작 확인(시:83/300). 부분 수집 시 자동 재시도 없음이 설계 동작이며, 제재 시 수동 해제 후 재시도 필요.
5. **scheduler는 계속 실행 중이며 catchup/publish는 실발행 트리거** — 본 플랜 검증 과정에서 스케줄러의 정상 발행(compare/rank/pick/senior 등)이 계속 진행됨. 이는 정상 동작이며 추가 개입 불필요.

## Self-Check

- [✅] SUMMARY.md 생성됨 — `.planning/quick/260805-d7c-root-title-fix-no-keyword-golf-bike/260805-d7c-SUMMARY.md` (본 파일)
- [✅] 커밋 존재 확인 — `git log --oneline | rg 2871c889c` + `rg 64a9874a9` (아래 Self-Check 출력 참조)
- [✅] 산출물 존재 확인 — `data/curation.db`(gitignored, products 24/24), `scheduler.py`(가드 적용), `/tmp/5000-scheduler.error.log`(2985개 라인)
- [✅] 삭제 확인 — 커밋 2건 모두 삽입 위주(9 insertions, 1 deletion=대체된 기존 라인), 의도치 않은 파일 삭제 없음
- [✅] 미추적 파일 — 내 작업으로 인한 신규 untracked 파일 없음 (기존 untracked만 유지)
