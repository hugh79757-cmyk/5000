# WL-20260806-content-db-recovery

> 날짜: 2026-08-06 / 연관: 커밋 219816b57(가드), d0da88bf2(규칙), 최종 마감 커밋
> 상태: **완료 (백필 원복만 보류)** — 커밋 C(표준위반) 마감 2026-08-06

## 세션 스냅샷 (2026-08-06, 커밋 C 마감)

진행: 대시보드 완성 → content.db 복구 완료 → 커밋 B(무력체크/ledger) 완료 →
커밋 C(표준위반) 완료.

커밋 C 마감 내역 (de386628c):
- 준수율 산정 버킷 분리: actionable(R01/R02/R05/R07~R12, 준수율 반영) /
  deferred(R06, STRUCT-16) / out_of_scope(R03 STRUCT-15, R04 STRUCT-17).
  준수율 = pass/(pass+actionable fail 블록), deferred·out_of_scope는 규칙
  건수로 별도 표기. RULES에 `bucket` 키 추가.
- 재정의 신규 준수율: **12.5%** (pass 1/25, actionable fail 7블록,
  deferred R06 19규칙/16블록, out_of_scope 11규칙/0블록, unknown 1).
  stale 3, 미해결 19 → 전체 🔴 확장 금지.
- R01: finance-hugo TOC 비활성 수정 (STAP/finance-hugo, 커밋 f4fe73d).
- R12: 허용 오버라이드 4→18 확장 (cde31b7bc) — travel4-hugo pass 진입.
- R02: 81→0 (N/A 판정 개선, 0c9657d14). R06: 조사만(보류, STRUCT-16).
- STRUCT-14(SEAP/ETAP git 미관리): **중복 아님 확인** — 파일·HEAD·DB 모두
  1건. 이전 read의 2건 표기는 출력 artifact. 시드 정리 불필요.
- 회귀: tests/ops_dashboard 14 passed.

다음 세션 진입점: entity_linker INC-CL-01~04 → 금지어 Q5 → H2 Q6 →
그 후 finance 외 재개 → 리팩토링.
**스케줄러 정지 상태 유지** (재기동은 별도 승인 필요).

## 세션 스냅샷 2 (2026-08-06 야간 — INC-CL-01~04 + Q5 금지어)

진행: entity_linker 무관 크로스링크 필터 → INC-CL 이슈 등록/U11 체크리스트 → Q5 금지어 필터 실작동.

### 커밋 3건 (모두 본 세션)

| 커밋 | 내용 |
|------|------|
| `7e2bd2312` fix(linker): INC-CL-01~04 무관 크로스링크 필터 | `shared/cuap_entity_linker.py::_fallback_blog()`를 CROSS_GRAPH[blog_id]의 primary/secondary/use_cases 합집합으로 제한(+15/−2). `build_funnel_header`/`build_cross_sell_card` 공유 지점 수정. 재렌더 시뮬레이션 10개 블로그 ALL_10_OK |
| `501fde0d2` fix(ops): INC-CL-01~04 등록 + U11 | known_issues 4건 open 등록(ops.db INSERT + `ops_dashboard/db.py` SEED_ISSUES durable). `app.py::_build_unpause_checklist()`에 U11 '베이크된 무관 크로스링크 재렌더 정리'(open INC-CL 있는 블로그만, `LIKE 'INC-CL%'`) — camping/pet 11항목, beauty 10항목 |
| `23edc896a` fix(writer): 금지어 필터 실작동 (Q5) | `pipelines/curation/writer.py`에 `_load_global_forbidden_words()`(quality_checklist.yaml global_forbidden_words 6개 로딩, fail-open), `GLOBAL_FORBIDDEN_WORDS`, `_FORBIDDEN_WORD_REPLACEMENTS`, `_sanitize_body()` 반영(+43) |

### INC-CL 실측 분류 (베이크드 74건/59포스트 — 코드 수정은 신규 생성만 차단)

- camping→baby 15(funnel) / health→camping 12(cross-sell) / laptop→kitchen 32(30 funnel+2 cross-sell) / pet→beauty 15(funnel). inline 기여 0.
- 사용자 결정(옵션 2): 베이크드 정리 보류 — 해당 블로그 발행 정지 중, 재개 시 재렌더로 자연 정리. INC-CL-01~04 open 유지.
- INC-CL 블로그 4곳 gsd_crosscheck = pass (M03 fail이 detection 프록시 충족). 준수율 12.5% 불변.

### Q5 검증 — finance 시범 불가 (실측)

- finance-hugo는 **STAP 소속** (dispatcher.py STAP_PIPELINE_MAP `"finance-hugo": "finance"`, 실제 `/Users/twinssn/Projects/STAP/pipelines/finance` + STAP 자체 shared/ai_writer.py) → curation/writer.py 미경유 → finance 시범 생성으로 Q5 검증 불가.
- 대체 검증: (1) 유닛 — `_sanitize_body()`에 금지어 6개 주입 → 전부 치환/제거 ALL_PASS; (2) 엔드투엔드 dry-run — `generate_curation_article('스킨케어 토너', …, blog_id='beauty-hugo')` 실 LLM 생성(body 3,597자) → 금지어 0건, 발행/배포 없음; (3) 회귀 — tests/ops_dashboard+curation: old writer.py(501fde0d2) vs new(23edc896a) 동일 18 failed/144 passed.

### 발견 — gsd_crosscheck 감지 프록시 취약 (기존, 미수정)

- `crosscheck.py`의 "detected" 판정 = "블로그에 현재 fail 체크가 하나라도 존재" (`get_fail_checks_for_blog` 최신 결과). 전역 이슈(blog_ids='': STRUCT-01/02/08/09/11~13)가 모든 블로그에 적용되어, 일시 fail이 사라지면 crosscheck가 fail로 플립.
- 실측: travel1-hugo crosscheck 06:03 pass → 13:19 pass → 15:11 fail → 15:12 pass → 15:23 fail (본 세션 이전부터 플래핑). tap/travel1~3/tvshow/ud 6곳 추가 fail은 본 커밋과 무관.
- 수정하지 않음 (현 세션 범위 외). readiness fail_total 왜곡 가능 — 별도 판단 필요.

### [위반 감지] stale stash pop 사고 (본 세션, 복구 완료)

- pytest 회귀 기준선 비교 중 클린 트리에 `git stash`(no-op) 후 `git stash pop`이 **이전 세션의 stale stash@{0}**을 적용 → UU/DU 충돌 상태로 작업 트리 오염.
- 복구: 충돌 경로 HEAD 복원 + `git rm -f` DU 런타임 파일(data/cooldown.json, failure_count.json) + writer.py HEAD 확인. 최종 `git status --porcelain` tracked 변경 0건.
- stale stash@{0~3}는 보존 (이전 세션 미커밋 작업 포함). 잔존: 4개 stash 엔트리 — 사용자 판단 필요.

### 다음 진입점

- H2 Q6 (writer.py H2>=1 가드, 옵 TOP5 포맷 H2=0 포스트 실측) → 그 후 finance 외 재개.
- gsd_crosscheck 감지 프록시 개선 여부 사용자 결정 대기.
- **스케줄러 정지 상태 유지.**

## 세션 스냅샷 3 (2026-08-06 심야 — Q5 종료 + Q6 H2 가드 + STRUCT-18 + stash 확인)

### Q6 — fix(writer): H2>=1 가드 (커밋 ed36af514)

- 수정 방식: **재생성 유도 + 최종 명시적 fail 이중 구조**. `_count_h2()` 추가(`^##\s`, H3 제외, 탭 허용). 시도 루프 내 `_sanitize_body()` 직후 H2=0 → warning + body="" + continue(재시도). 루프 종료 후 H2=0 잔존 → `logger.error` + `return None`(침묵 통과 방지).
- 실측: `화장수-추천-top5-2026년`(CUAP beauty-hugo) **H1=0/H2=0** — 옛 TOP5 포맷은 H3(###)만 사용. `유모차-추천-인기-순위-top5`는 H2=1.
- dry-run: 실 LLM `generate_curation_article('화장수 토너', …, beauty-hugo)` → **H2=9, len=4297** — 신규 생성 H2>=1 보장 확인 (발행/배포 없음).
- 유닛: H3-only 3회 → None(fail) / 1차 H2=0→재시도→2차 H2>0 성공(retry) / H2 카운트 정확성.
- 회귀: **18 failed / 144 passed — baseline과 동일 이름·동일 건수** (diff 확인).

### Q5 종료 (커밋 23edc896a, known_issue resolved)

- finance=STAP 파이프라인(별도 shared/ai_writer.py, dispatcher STAP_PIPELINE_MAP) → CUAP writer.py의 Q5 검증 대상 아님 **확정 기록**.
- 검증 완료: beauty-hugo dry-run(3,597자, 금지어 0) + 유닛(주입 6건 전부 치환/제거).
- 공백 노트: **"실발행 검증은 CUAP 재개 후"** — known_issue Q5 notes + db.py SEED에 기록.

### STRUCT-18 등록 (gsd_crosscheck 플래핑 — 코드 미수정, 메모)

- crosscheck detected 프록시 = "블로그에 fail 체크 1개라도 존재" + 전역 이슈(blog_ids='') 전파 → 일시 fail 소멸 시 pass↔fail 플래핑. travel1-hugo 06:03 pass→13:19 pass→15:11 fail→15:12 pass→15:23 fail 실측. tap/travel1~3/tvshow/ud 6곳 일시 +fail(본 세션 커밋과 무관).
- `auto_detectable='no'`로 등록 — auto=yes 시 모든 블로그 crosscheck가 추가 fail되는 것을 방지(메모 성격). 개선 방향(다음 작업 후보): 감지 프록시를 **체크명별 매핑**(auto-detectable 이슈 ↔ 담당 체크명)으로 전환.

### stash 4건 — 읽기 전용 확인 (pop/drop/apply 안 함)

| stash | base | 내용 | HEAD 중복 판정 |
|-------|------|------|----------------|
| @{0} | 8/3 c9800eb61 | rap.yaml force_draft(5곳) + car/rap pipeline + test_alert_thresholds 완화(18-fail 중 2건 fix 시도) + 계획 문서 | rap force_draft만 **중복(커밋됨)**. rap 상태 active/quota5는 HEAD(paused/quota10)와 상이 — 스테일. 테스트 수정은 미커밋 |
| @{1} | 8/3 1cb5a0f4b | cuap.yaml 10곳 active→inactive + curation/pipeline.py 40줄 + writer.py + title_templates + defense_layers 테스트 | 전부 미커밋. 현재 cuap.yaml은 전부 active — CUAP 중지는 config가 아닌 스케줄러 정지로 처리 중 |
| @{2} | 7/30 fd016b3a3 | keywords.py 브랜드 리네이밍("그램"→"LG 그램") + travel 계절 필터→경고만 로그(데이터 소진 방지) + senior/stock/rap fetcher·pipeline + STATE.md | 전부 미커밋 |
| @{3} | 7/26 c0df11b38 | phase-8 flagged 정리(delete_flagged_posts 신규, flagged_posts.yaml 3,286줄, verify_cleanup) + telegram_notifier 전면 개편 + validators.py 214줄 + hugo_writer/dispatcher + AGENTS.md | 전부 미커밋. 일부는 이후 커밋에서 다른 형태로 반영됐을 가능성(reverse-apply 0건이라 정확 역본 아님) |

정리(pop/drop/apply)는 사용자 판단으로 보류.

### 정상화 잔여 재집계 (Q5/Q6 종료 후)

- 준수율 **12.5% 불변** (pass 1/25, actionable fail 7, deferred 19, out_of_scope 11, unknown 1). stale **3**. known_issue **22개 open**(23 − Q5 − Q6 + STRUCT-18, 정상화 대상 교집합 기준). → 확장 BLOCKED 유지.
- 잔여: R01(TOC 비활성 8곳), R03(로더 Publisher ID 3곳), R06/STRUCT-16(광고 형식, 콘솔 확인 대기), STRUCT-12/13(content.db), STRUCT-14(git 미관리), STRUCT-15(이중 관리), STRUCT-18(crosscheck), INC-CL-01~04(베이크드 재렌더), Q1~Q4/QA-01~06(비대상/미해결).
- **스케줄러 정지 상태 유지. finance 외 발행 재개 금지.**

## 배경

`shared/ledger_sync.py` `run_sync()`을 라이브 상태에서 수동 실행. 실제 DB의
`idx_ledger_dedup`이 non-unique(STRUCT-11)라 `INSERT OR IGNORE`가 무력 → 소스
전체 재삽입. `backfill_blank_titles()`이 같은 블로그+날짜 다중 행에 첫 소스
제목을 덮어씀 (오염 의심).

## 파괴적 작업 목록 (전 과정)

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 20:15 | run_sync 재삽입 (사고) | `python -c "run_sync()"` | 42,256행 | 없음 | 57,770행 (+15,514) | source='' 36행 유지 |
| 20:26 | 오염 백업 | `cp` → `bak_20260806_202605` | 57,770 | 본파일 | 해시 동일 | 해당없음 |
| 20:31 | 증거본 보존 | `cp` → `EVIDENCE_polluted_20260806` | 57,770 | 본파일 | 해시 동일 | 해당없음 |
| 20:40 | 클린 백업 (스케줄러 정지 후) | `cp` → `clean_before_recovery_20260806_204047` | 57,771 | 본파일 | 동일 | 해당없음 |
| 20:50 | R2 백업 보존 | `cp` → `r2_20260806_0500` (읽기전용) | 9.2MB | 본파일 | 동일 | 해당없음 |
| 20:52 | **중복 정리 + partial UNIQUE** | 4수치 검증 COMMIT | 삭제 24,061 | 안전망 3벌 | 총 33,710 | **source='' 18,301 유지 ✓** |
| 20:53 | 롤백 1건 | full UNIQUE 시도 실패 | 동일 | 동일 | ROLLBACK 57,771 | source='' 보존 확인 |
| 20:55 | **백필 원복 — 보류 (옵션 C)** | 미실행 | 966행(불안정) | 동일 | 미실행 | 실발행 제목 유실 위험 |
| 23:40 | **롤백 태그 이동** | `git tag -f post-dashboard-baseline f4f23865c` | 구태그 e0fea582…(f13045f31) | 구해시 병기(본 문서) | f4f23865c… | f13045f31 커밋은 히스토리 잔존 |

## 세션 스냅샷 4 (2026-08-06 — 롤백 태그 통일 + stash 정리 + 실정리 R01/R03/재렌더)

### 작업 1 — 롤백 기준 태그 통일 (완료)

- 지시 문서 기준: `f4f23865c`(worklog 세션 스냅샷 — 커밋 C 마감). 구 태그 대상: `f13045f31`(content.db 복구 마감) = e0fea582180e34b2ce4378786e914dfa2dcfa7da.
- 이동 전/후: `e0fea5821…` → `f4f23865c8…` (f13045f31은 f4f23865c의 9커밋 앞 조상 — 안전 이동). HEAD describe: post-dashboard-baseline-6-g3cbee787e.
- 문서 표기 통일: playbook(fleet-ops-audit-playbook.md:133)은 태그 이름 참조뿐(해시 하드코딩 없음) → 정정 불필요. worklog 내 표기는 위 표로 통일.

### 작업 2 — stash 정리 (완료: drop 2건, 보류 2건)

| stash | base | 파일·변경 | 성격 | 처리 |
|-------|------|-----------|------|------|
| @{1} | 8/3 | cuap.yaml 9곳 active→inactive + curation/pipeline 40줄 + writer.py + title_templates + defense_layers 테스트 + tap.yaml + ROADMAP/INDEX + .DS_Store | CUAP 중지를 config로 처리하는 방향 — **재개 전략("스케줄러 정지 유지 + config active 그대로")과 상충** | **drop** (아카이브 stash1-2026-08-03.diff, 17,653B) |
| @{0} | 8/3 | rap.yaml force_draft 5곳 + car/rap pipeline + **test_alert_thresholds 완화(18-fail 2건 fix 시도)** + ROADMAP/CONCERNS/INDEX | force_draft는 이미 커밋됨(중복), rap 상태(active/quota5)는 HEAD(paused/quota10)와 상이 — 통째 살리면 config 오염 위험 | **drop** (아카이브 stash0-2026-08-03.diff, 27,096B). 18-fail 2건(test_alert_thresholds)은 stash 병합 없이 다음 작업에서 별도 재작성 — **메모만, 이번엔 미처리** |
| @{2} | 7/30 | keywords.py 브랜드 리네이밍("그램"→"LG 그램" 등) + travel fetcher 계절 필터→경고만 로그(데이터 소진 방지) + senior/stock/rap fetcher·pipeline + STATE.md + triage | 파이프라인 실질 개선(특히 travel 계절 필터 완화) — 유효 작업 | **보류** (사용자 확인 대기, 아카이브 stash2-2026-07-30.diff) |
| @{3} | 7/26 | phase-8 flagged 정리(delete_flagged_posts 신규, flagged_posts.yaml 3,286줄, verify_cleanup 116줄) + telegram_notifier 전면 개편 + validators.py 214줄 + hugo_writer/dispatcher + AGENTS.md | phase-8 작업의 미커밋 잔여 — validators/notifier 변경이 이후 커밋에 반영됐는지 불확실(회수 가치 있음) | **보류** (사용자 확인 대기, 아카이브 stash3-2026-07-26.diff) |

- drop 대상 diff 전문: `.planning/worklog/archives/stash{0,1}-2026-08-03.diff` (파괴적 로그 + 본 문서 기록).
- 남은 stash: @{0}=7/30(파이프라인), @{1}=7/26(phase-8) — 모두 보류, 사용자 결정 대기.

## 4단계 프로토콜 이행

1. **사전 카운트**: 초기 57,771행 / source!='' 중복 24,061행 / source='' 18,301행(전량 보존 불변식).
   클린 스냅샷 없음 확인 (Time Machine 0건, R2 백업도 6/19부터 중복 보유 → 판정 B).
2. **되돌림 수단**: 안전망 3벌 —
   `clean_before_recovery_20260806_204047`(복구 기준선, 43MB),
   `EVIDENCE_polluted_20260806`(증거본, 43MB),
   `r2_20260806_0500`(R2 8/6 05:00, 읽기전용 9.2MB).
3. **실행**: 스케줄러 PID 31420 + com.5000.scheduler 정지 확인 → lsof 0건 → 실행.
   중복 삭제 → partial UNIQUE(WHERE source != '') 재생성. 트랜잭션 내 4수치
   (삭제 24,061 / 총 33,710 / s!='' 15,409 / s='' 18,301) 정확히 일치 → COMMIT.
4. **사후 대조**: run_sync 재실행 +0 (idempotent), partial UNIQUE 중복 INSERT 차단 실측,
   M09 전수 23/23 pass, 준비도 stale 7개 (변경 없음).

## 코드 수정 (커밋 219816b57)

- `run_sync()`: SELECT-존재확인 후 INSERT (중복 재삽입 차단)
- `run_sync()`에서 `backfill_blank_titles()` 호출 제거 (오염 차단)
- `_ensure_schema()`: 기대 인덱스 정의를 partial UNIQUE(4중 키 + WHERE source != '')로 갱신
- 복구 절차서: `RECOVERY-content-db-20260806.md`

## 결과 / 보존 대상 확인

- **source='' 실발행: 18,301행 전량 보존** (삭제 0건 — 최우선 불변식 달성).
- source!='' 중복 24,061행 삭제 → 15,409행 잔여 (4중 키 기준 고유).
- 백필 원복: **보류** — 원복 대상 1,412→872→966행 불안정, URL 동일 233행(정당 재발행)
  + 판정불가 359행 혼재로 추측 기반 blank 원복은 실발행 제목 유실 위험. STRUCT-13 등록.

## 이슈 상태 (known_issues)

| 이슈 | 상태 | 내용 |
|------|------|------|
| STRUCT-11 | **resolved** | non-unique idx_ledger_dedup → partial UNIQUE 재생성. 1/7부터 누적된 반년 묵은 결함 명시 |
| STRUCT-12 | open | source='' 내부 레거시 중복 2,935그룹/15,177행 (관찰용, 삭제 보류) |
| STRUCT-13 | open | 백필 오염 966행 (재발행 233+다른글 374+판정불가 359, 원복 보류) |

## 잔존 위험

- 백필 오염 966행 title은 그대로 (원복 보류) — 향후 백필 실행 시점 로그 기반 정밀 원복 필요.
- source='' 내부 레거시 중복 15,177행 — 카운트 집계 시 DISTINCT 처리 검토.
- 스케줄러 정지 상태 유지 — 정상화 완료 전 재기동 금지 (별도 승인 필요).
