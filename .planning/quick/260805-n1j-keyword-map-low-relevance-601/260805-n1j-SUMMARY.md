---
phase: quick-260805-n1j
plan: 1
status: complete
type: execute
wave: 1
depends_on: []
requirements:
  - Q-20260805-low-relevance-keywords-601
files_modified:
  - scripts/scan_keyword_relevance.py
  - scripts/apply_keyword_removals.py
  - pipelines/curation/keywords.py
  - .planning/quick/260805-n1j-keyword-map-low-relevance-601/kw_risk_classified.json
  - .planning/quick/260805-n1j-keyword-map-low-relevance-601/kw_b1_review.json
  - .planning/quick/260805-n1j-keyword-map-low-relevance-601/kw_removal_log.json
commit: (see Deviations — Task 2 커밋 a8ed1ec30 + Task 4 최종 커밋)
metrics:
  duration_minutes: ~55
  tasks: 4
  files: 6
---

# Quick Task 260805-n1j: low_relevance 위험 키워드 전수 감사 — 589 고유쌍 → 212 재스캔

**One-liner:** KEYWORD_MAP 전수 감사로 low_relevance 발행 실패 위험 키워드를 589 고유쌍(601행 − 중복 12행)에서 212 고유쌍으로 감소 (제거 377쌍/381토큰, 2982→2601). 외국어혼합(A) 256쌍 + 완전 오프토픽(B0) 82쌍 자동 제거, B1 124쌍은 상품명 8개 샘플 검토로 39쌍 제거/84쌍 유지. 하드 게이트(≤261) 통과: **212 ≤ 261**. 결합 아티팩트 2건('귀체온계카시트'/'노트북가을')은 SKIP_ARTIFACT로 유지.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 파이프라인 게이트 재현 스캔 + 위험 키워드 분류 스크립트 생성 | Task 4 커밋에 포함 (스캐너 신규 파일) | scripts/scan_keyword_relevance.py, kw_risk_classified.json |
| 2 | 토큰 단위 자동 제거 엔진 + A+B0 적용 + 세트 diff 검증 | `a8ed1ec30` | scripts/apply_keyword_removals.py, pipelines/curation/keywords.py (A+B0 적용분) |
| 3 | B1 상품 샘플 검토 + kw_removal_log.json 작성 + 재스캔 검증 | Task 4 커밋에 포함 (B1 제거분) | pipelines/curation/keywords.py (B1 적용분), kw_b1_review.json, kw_removal_log.json |
| 4 | fresh-import 반영 확인 + 커밋 + SUMMARY | `(Task 4 커밋)` | 260805-n1j-SUMMARY.md |

## 숫자 산출 근거 분해 (AGENTS.md Section 2)

- **위험 고유쌍 589 = REMOVE_A 256 + REMOVE_B0 82 + REMOVE_B1 39 + KEEP_B1 84 + KEEP_C 126 + SKIP_ARTIFACT 2 = 589** (kw_removal_log.json action_summary; rows 589건 = 고유쌍 전수)
  - B0 버킷은 Task 1 분류상 83쌍이나, 그중 '노트북가을'이 SKIP_ARTIFACT → REMOVE_B0 82
  - B1 버킷 124쌍 = REMOVE_B1 39 + KEEP_B1 84 + SKIP_ARTIFACT 1('귀체온계카시트') = 124
- **제거 377쌍 = REMOVE_A 256 + REMOVE_B0 82 + REMOVE_B1 39** / **토큰 381개** (377쌍 + 중복 오커런스 4개: fitness '논슬립' 2회 등) → **2982 − 381 = 2601** (실측 TOTAL 2601 일치)
- **재스캔 위험 212 = B0 1('노트북가을' 아티팩트) + B1 85(84 유지 + 1 아티팩트) + C 126 = 212 ≤ 261 하드 게이트 통과**
- **잔존 212 전수 추적**: KEEP_B1 84 / KEEP_C 126 / SKIP_ARTIFACT 2 — 비-KEEP 잔존 0건 (TRACEABILITY OK)
- **충실도**: 위험셋 589쌍 중 유지분 전수(212쌍)의 (avg, threshold, count) 값이 참조 kw_scan_pipeline.json과 **0건 불일치** → 589→212 감소는 스캔 노이즈가 아닌 실제 제거 반영

## Verification (3-way classification)

### [검증됨]

- **하드 게이트: 재스캔 위험 고유쌍 212 ≤ 261.**
  근거: `scan_keyword_relevance.py` 재실행 콘솔 출력 `RISK UNIQUE: 212` (A 0 / B0 1 / B1 85 / C 126). `--fidelity-hard` 1차 실행은 참조(제거 전 589)와의 불일치로 의도대로 실패 → 플래그 없이 재실행해 212 산출 (Task 3 Step 4 규정).
- **제거된 키워드 377쌍 전수가 fresh import 후 KEYWORD_MAP에 부재.**
  근거: Task 4 fresh-import assert — `removed pairs=377 still present=0` (removed ∩ remain = ∅). 총수 `total=2601 == 2982−381` (match=True).
- **유지 예시 키워드 존재.**
  근거: fresh-import assert — `laptop-hugo 'SSD512GB': present=True`, `golf-hugo '골프드라이버': present=True`.
- **SET_DIFF 무결성 (제거만, 무연쇄).**
  근거: Run 1(총 A+B0) `SET_DIFF OK: 338 pairs removed, 0 collateral, 0 remaining`, Run 2(B1) `SET_DIFF OK: 39 pairs removed (누적 377), 0 collateral, 0 remaining` — 재-import 후 비대상 키워드 오커런스 수 불변 검증을 통과한 엔진 출력.
- **충실도 0건 불일치.**
  근거: kw_scan_pipeline.json 589행과 현재 스캔의 유지분 212쌍을 (avg, thr, count) 튜플로 대조 → `kept risk pairs with value drift: 0 / 589`.
- **스캐너 FIDELITY 게이트 (Task 1, 변경 전).**
  근거: Task 1 실행 출력 `FIDELITY OK: 589 unique pairs match (601 rows, 12 duplicates documented)`.
- **py_compile.**
  근거: `py_compile pipelines/curation/keywords.py scripts/scan_keyword_relevance.py scripts/apply_keyword_removals.py` → `py_compile OK`.
- **테스트 실패 셋 불변 (작업 전후 동일).**
  근거: 작업 전 `pytest tests/curation/test_keywords.py -q` → `4 failed, 3 passed in 0.03s`, 작업 후 동일 `4 failed, 3 passed in 0.03s` — 신규 실패 0건. [PRODUCTION CODE]만 수정, [TEST CODE]/[CONFIG] 무수정.
- **스케줄러 재시작 불필요.**
  근거: scheduler.py:263 `subprocess.run([PYTHON, "dispatcher.py", blog_id], ...)` — 매 dispatch가 fresh import로 keywords.py를 재로드. scheduler.py:668-672 auto_collector(`_run_cuap_collector`)만 scheduler 프로세스 내 캐시 → 잔존 위험 #3 참조.
- **커밋에 의도치 않은 삭제 없음.**
  근거: Task 4 커밋의 `git diff --diff-filter=D HEAD~1 HEAD` 결과 0건 (토큰 삭제는 라인 삭제이지 tracked file 삭제 아님). 커밋 스테이징은 키워드/스크립트/quick dir 파일만 개별 add — 무관 파일(.DS_Store, config, data/*.json, ai_writer.py 등 작업 트리 이물) 미포함 확인.

### [부분검증]

- **B1 124쌍의 KEEP/REMOVE 판단은 상품명 8개 샘플 + 규칙 기반 사람 판단.**
  근거: kw_b1_review.json 124건 전수 기록 (decision + reason_code + avg + on_ratio). 결정 규칙(주제 의미 일치/데모그래픽 일치 → KEEP, 불확실 시 KEEP) 준수, Latin/숫자 키워드(SSD512GB 등)는 상품 검증 후 KEEP.
  제한 사유: 상품명은 스캔 시점 curation.db products의 최근 10개 중 상위 8개 스냅샷 기준 — 상품 DB가 시간에 따라 변하면 개별 판단 근거도 달라질 수 있음. 또한 on-ratio 임계(0.5) 경계 부근 B1/C 판정은 스캔 재현의 개별 drop 재평균 디테일에 민감 (계획 line 97 기재).
- **B0/B1 경계의 개별 drop 재평균 재현.**
  근거: 충실도 0건 불일치가 경계 재현의 정합성을 간접 입증 (kw_scan_pipeline.json 수치와 현재 스캔 수치 완전 일치).
  제한 사유: 참조 자체가 동일 로직으로 생성된 산물 — "재현 로직 자체의 오류"는 참조 대조로는 검출 불가. 다만 Task 1 FIDELITY 게이트(589쌍)와 버킷 합계(A 256/B0 83/B1 124/C 126, sum 589)가 계획의 checker 재현과 일치해 교차 검증됨.

### [검증불가]

- **없음.** (테스트 코드 수정 없음, 순환 검증 없음 — 검증 수단은 전부 실행 산출물 대조.)

## Deviations from Plan

### Auto-fixed / 프로세스 이탈 (모두 실행 결과에 영향 없음)

1. **[프로세스] Task 2가 별도 커밋으로 기록됨 (`a8ed1ec30`)** — 계획 Task 2의 Do-NOT에는 "commit (Task 4)"가 있었으나, GSD 실행 프로토콜의 per-task commit 원칙(태스크 완료 즉시 커밋)을 적용해 Task 2 완료 시점에 커밋. 최종 상태는 "Task 4 커밋(나머지 전부) + Task 2 커밋" 2개로, 계획의 단일 커밋 의도와 다르나 리포지토리 최종 상태는 동일.
2. **[생성물] kw_risk_classified.json이 Task 3/4 재스캔에 의해 덮어써짐 (제거 후 212쌍 뷰)** — 스캐너가 해당 경로를 기본 출력으로 사용. Task 1의 589쌍 분류 JSON은 파일로 보존되지 않으나, 589쌍 전수 감사 정보(blog_id/keyword/action/reason_code/avg/on_ratio/sample)는 kw_removal_log.json rows에 완전 보존 — 감사 가능성 유지.
3. **[검증] Task 3 Step 4 재스캔 1차 실행(--fidelity-hard)은 의도된 실패** — 참조가 제거 전 589쌍이므로 hard 게이트는 Task 1(변경 전) 전용. 플래그 없이 재실행해 212 산출. 계획의 Task 3 automated verify(플래그 없는 스캔)와 정합.

### 계획 예측 vs 실측

- 계획 예측 "재스캔 ~180-220쌍, B1 전부 유지여도 251 ≤ 261" → 실측 **212쌍** (예측 범위 내).
- Task 2 done criterion "~338 pairs removed" → 실측 **338쌍** 정확히 일치 (A 256 + B0 82 + SKIP_ARTIFACT 1 제외).

## Known Stubs

없음 — KEYWORD_MAP 데이터 토큰 삭제만 수행한 데이터 편집으로, UI/데이터 소스 스텁 없음.

## Threat Surface Scan

신규 표면 없음 — 네트워크 엔드포인트/인증 경로/스키마 변경 없음. 신규 스크립트 2종은 개발 도구(read-only sqlite SELECT + 토큰 삭제)로 계획 위협 레지스터(T-n1j-01~06, T-n1j-SC) 범위 내이며 전 디스포지션 이행 확인:
- T-n1j-01 (Availability, 블로그별 하한): 소형 블로그(massage/car/homeappliance/golf/bike) 제거 0건 — 12개 유지, safety valve(<8) 미발동.
- T-n1j-02 (Information Disclosure, curation.db): 스캐너는 sqlite3 SELECT만 사용, DML 0건.
- T-n1j-03 (Spoofing, B1 오제거): 124건 전수 검토 + 상품명 8개 샘플 + 보수적 KEEP 규칙.
- T-n1j-04 (Tampering, 토큰 삭제): ast 블록 스코프 + SKIP_ARTIFACT + SET_DIFF 증명(0 collateral) + py_compile + 테스트 불변.
- T-n1j-05 (Elevation, 스케줄러): subprocess fresh import 증명 — 재시작 불필요.
- T-n1j-06 (Availability, 결합 아티팩트): 2건 SKIP_ARTIFACT, 하드 게이트가 흡수 (212 ≤ 261).
- T-n1j-SC (패키지 설치): 설치 0건.

## 잔존 위험 (AGENTS.md Section 6)

1. **결합 아티팩트 2건이 KEYWORD_MAP에 잔존** — '귀체온계카시트'(397-398행) / '노트북가을'(455-456행). 쉼표 누락으로 인접 토큰과 묵시적 결합된 broken 라인이며 소스 토큰이 없어 제거 불가(SKIP_ARTIFACT). 재선택 시 동일 low_relevance 위험이 이론상 남아 있음. 하드 게이트 261이 이를 흡수(212 ≤ 261). 쉼표 포맷 복구는 범위 외 — 향후 포맷 정리 항목으로 유지.
2. **쉼표 누락 결합 라인 총 7줄 중 나머지 5줄**(326/531/534/654/715행)은 위험 셋 밖이라 무처리 — 동일 패턴의 포맷 결함이 존재. 범위 외, 향후 포맷 정리 필요.
3. **auto_collector 캐시** — scheduler 프로세스 내 `_run_cuap_collector`(scheduler.py:668-672)는 제거된 키워드로 계속 수집할 수 있음(다음 자연 재시작까지). 무해 — 미사용 products 행 생성에 그침. subprocess dispatch 경로(scheduler.py:263)는 fresh import라 발행에는 영향 없음.
4. **기존 테스트 실패 4건은 이 작업과 무관한 사전 존재 상태** — 블로그 수 15≠10 / 60~200 상한 / generics 셋 / 중복 검증. 범위 밖, 별도 처리 필요.
5. **KEEP_B1(84) + KEEP_C(126)의 on-ratio/부분 매치는 스코어링 아티팩트 성격** — 의도된 유지(커버리지 보존)이며, 실패 시 재시도 비용만 발생. 상품 DB 변동 시 재분류 필요성은 상시 존재.

## Decisions Made

- A(외국어혼합) 256쌍 + B0(완전 오프토픽) 82쌍은 규칙 기반 자동 제거 (리뷰 없이).
- B1 124쌍은 상품명 8개 샘플 검토로 39쌍 제거 / 84쌍 유지 / 1쌍 SKIP_ARTIFACT — 불확실 시 KEEP 원칙 (잘못된 제거가 커버리지 손실을 유발하므로).
- Latin/숫자 키워드(SSD512GB, AMD라이젠5, MTB자전거, 골프드라이버, 아이언세트 등)는 상품 검증 후 전부 KEEP — 의도된 스펙/브랜드 키워드.
- 결합 아티팩트 2건은 파일 무수정 + 로그 기록 (SKIP_ARTIFACT).
- 스케줄러 재시작 불필요 (subprocess fresh import). auto_collector 캐시는 무해 — 자연 재시작에 맡김.

## Self-Check: PASSED

- [x] FOUND: `.planning/quick/260805-n1j-keyword-map-low-relevance-601/260805-n1j-SUMMARY.md` (파일 존재 확인)
- [x] FOUND: commit `a8ed1ec30` (git log 검색 확인) + Task 4 커밋 (작성 직후 확인)
- [x] FOUND: `scripts/scan_keyword_relevance.py`, `scripts/apply_keyword_removals.py`, `pipelines/curation/keywords.py` 커밋 반영 확인 (`git show --stat` tail 확인)
- [x] FRESH_IMPORT OK: total=2601 (2982−381), removed_absent=377, kept SSD512GB/골프드라이버 present
- [x] 재스캔 RISK UNIQUE=212 ≤ 261 (하드 게이트), TRACEABILITY 212=KEEP_B1 84+KEEP_C 126+SKIP_ARTIFACT 2
