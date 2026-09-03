# Phase 77: Analytics 기반 셀프 개선 루프 — VERIFICATION

**Date:** 2026-09-03
**Mode:** READ-ONLY 검증 (코드 무변경, 본 보고서가 유일한 write)
**Source:** PLAN.md §1 Goal-backward 5기준 + additive 제약

---

## 기준별 판정

### 기준 1 — 수요 패턴 ≥3건 산출: **PASS** [검증됨]

**명령:** `python3 shared/performance_signals.py`

**출력:**

```
[perf-signals] blogs=7 patterns=23
  deal-hugo: ['gr86 유지비']
  guide-hugo: ['bmw m4 유지비', 'm4 유지비']
  hotissue-hugo: ['마이바흐 유지비']
  rotcha.kr: ['예비군 슬리퍼', '스타일런 2026', '동원예비군 슬리퍼']
  travel3-hugo: ['대전 드라이브 코스', '대전 드라이브 하기 좋은 곳', '대전 근교 드라이브 코스']
[perf-signals] wrote data/keyword_performance.json
```

**JSON 실측 패턴 검사 (grep 결과):**

| 패턴 계열 | 건수 | 실제 쿼리 |
|---|---|---|
| 유지비 | 4 | gr86 유지비 / bmw m4 유지비 / m4 유지비 / 마이바흐 유지비 |
| 드라이브 | 4 | 대전 드라이브 코스 / 대전 드라이브 하기 좋은 곳 / 대전 근교 드라이브 코스 |
| 예비군 | 3 | 예비군 슬리퍼 / 동원예비군 슬리퍼 / 동원 예비군 슬리퍼 |

총 23패턴 (7 blogs). 계열 3종 이상 실측 존재 확인. 원자적 쓰기(tmp + os.replace) `shared/performance_signals.py:57-60` 확인. analytics.db 읽기 전용(SELECT만, 스키마 무변경).

### 기준 2 — PERF_SIGNALS=1 매칭 후보 우선 선택: **PASS** [검증됨]

**명령:** `OPS_TEST_MODE=1 python3 -m pytest tests/test_performance_signals.py -q`

**출력:** `9 passed in 0.71s`

9 = 3(순수 `_boost_by_signals`: 매칭 선두 이동/무매칭 불변/stable sort) + 5(게이트 passthrough: env 미설정/명시적 0/파일 부재/손상 JSON/해당 blog 신호 없음) + 1(env=1 + 신호 존재 → boost 발동 재현).

**콜사이트 (dead code 아님):** `pipelines/curation/pipeline.py:225` — `candidates = _apply_perf_signal_boost(candidates, blog_id)` 가 `_select_keyword`(def, pipeline.py:178) 내부, 최종 선택 직전(`candidates = cat_filtered or available` 직후)에 호출됨. grep 확인: `_apply_perf_signal_boost` 정의 pipeline.py:161, 호출 pipeline.py:225.

### 기준 3 — 기본 OFF passthrough: **PASS** [검증됨]

**게이트 첫 줄** (`pipelines/curation/pipeline.py:163`):

```python
if not candidates or os.environ.get("PERF_SIGNALS", "") in ("", "0"):
    return candidates
```

`PERF_SIGNALS` 미설정 → `""` → 즉시 반환. 이하 4가지 전부 passthrough (테스트로 재현): env 미설정, `0`, JSON 파일 부재(FileNotFoundError → try/except), 손상 JSON(`{corrupt garbage!!` → json.loads 실패 → except → 원본 반환). 테스트 5종 (`test_env_off_order_unchanged` / `test_env_explicit_zero_order_unchanged` / `test_missing_json_order_unchanged` / `test_corrupt_json_passthrough_no_exception` / `test_no_signals_for_blog_order_unchanged`) 전부 passed.

### 기준 4 — 기존 테스트 회귀 0건: **PASS** [검증됨]

**명령:** `OPS_TEST_MODE=1 python3 -m pytest tests/curation tests/test_performance_signals.py -q`

**출력:** `19 failed, 138 passed in 16.79s`

**산출 근거:** 138 = 129(기존 passed) + 9(신규 test_performance_signals.py). 19 failed는 baseline(2026-09-03 W2 선행 기록, `.continue-here.md:72` "19 failed / 129 passed pre-existing")과 동일 목록:

| 실패 파일 | 건수 |
|---|---|
| test_title_hardening.py | 4 |
| test_title_regression.py | 1 |
| test_keywords.py | 4 |
| test_defense_layers_independent.py | 4 |
| test_alert_thresholds.py | 2 |
| test_cot_threshold_validation.py | 1 |
| test_filters_allblogs.py | 1 |
| test_pipeline.py | 1 |
| test_problem_monitor_integration.py | 1 |
| **합계** | **19** |

신규 실패 0건, 기존 실패 목록 동일 (19=19, 파일별 분해 일치).

### 기준 5 — collect_analytics.sh 훅: **PASS** [검증됨]

- **문법:** `bash -n scripts/collect_analytics.sh` → SYNTAX OK (exit 0)
- **훅 라인** (`scripts/collect_analytics.sh:98-101`): `"$PY" shared/performance_signals.py >> "$LOG_FILE" 2>&1 && echo ok || echo "⚠️ perf-signals extraction failed (non-fatal)"` — `||` 폴백으로 비치명. 훅 성패가 `OVERALL_RC`에 영향 없음 (`exit "$OVERALL_RC"`는 훅과 무선).
- **실제 6h launchd 실행 증거** (`logs/analytics_collect.log`, 2026-09-03 08:08:15 실행분):

```
[2026-09-03 08:08:15] === Analytics 수집 완료 (성공, rc=0) ===
[perf-signals] blogs=7 patterns=23
[perf-signals] wrote /Users/twinssn/Projects/5000/data/keyword_performance.json
[2026-09-03 08:08:15] perf-signals → ok
```

기존 수집(gsc/adsense/efficiency ok) 완료 **후** 추출기 정상 동작. pending-observation 아님 — 실제 launchd 사이클 1회 실행 증거 존재. 단 **연속 성공 ≥14회**는 관찰 기간(≈09-17) 확정 사항으로, RUNBOOK 활성화 기준이므로 pending-observation으로 아래 명시.

---

## Additive 제약 확인

### 커밋 범위: **PASS** [검증됨]

`git show d97e9b868 --stat` (W1): `.gitignore +1` / `scripts/collect_analytics.sh +5` / `shared/performance_signals.py +83` — 전부 의도 파일.

`git show 0d730ce7e --stat` (W2): `pipelines/curation/pipeline.py +25` / `tests/test_performance_signals.py +100` — 전부 의도 파일.

의도 외 파일 변경 없음 (두 커밋 모두 insertion-only, 삭제 라인 0).

### 삽입 전용 (기존 로직 무변경): **PASS** [검증됨]

`git show 0d730ce7e -- pipelines/curation/pipeline.py` diff 확인:

- 신규 삽입: `import json` 1줄, 함수 2개(`_boost_by_signals`, `_apply_perf_signal_boost`), 호출 1줄 — 전부 `+` 라인
- `_select_keyword(blog_id)` 시그니처 무변경 (인자 1개 동일)
- 필터 순서 무변경: 30일 TTL 제외 → 격리 제외 → low_relevance 14일 제외 → 카테고리 14일 억제 → `cat_filtered or available` → (신규) boost → 상품 3개 탐색. boost 호출은 기존 필터 체인 **후단에 추가만**
- 기존 라인 수정/삭제 0건 — 기본 OFF 시 `_apply_perf_signal_boost`가 원본 리스트 그대로 반환하므로 실행 경로도 무변경

### 부수 확인

- `.gitignore:101` — `data/keyword_performance.json` 등록 확인 (W1 커밋)
- RUNBOOK-enable.md (W3, commit 74f2dc45a) — 전환 기준 3종 / 활성화 절차 / 되돌림 3요소 포함 확인

---

## 종합 판정

**PHASE 77 GOAL 달성: PASS (5/5 기준 + additive 제약 충족)**

수요 패턴 추출(관찰) → env 게이트 반영 구조가 계획대로 additive non-destructive로 구현됨. 기본 OFF로 실배포 동작 변화 0. 회귀 0건.

---

## 잔존 위험 (필수)

1. **신호 규모 작음** — 23패턴/7blogs, 클릭 있는 쿼리 ~20개 (CONTEXT.md 공지 제약). curation 계열 blog 중 신호 보유는 deal-hugo/guide-hugo/hotissue-hugo 3개뿐 → boost 실효 범위 협소. 스타일런/예비군(rotcha.kr)·드라이브(travel3-hugo)는 curation 파이프라인 밖이라 W2 개입 대상 아님.
2. **6h 주기 장기 안정성 미확정** — 커밋 후 실제 launchd 실행 1회(09-03 08:08)만 관측. RUNBOOK 활성화 기준(연속 성공 ≥14회, 패턴 수 3회 동일) 충족 여부는 ≈09-17 판정. **pending-observation.**
3. **PERF_SIGNALS=1 프로덕션 미실행** — env 켠 상태의 dispatcher 실배포 검증(런북 절차 3단계)은 활성화 시점 과제. 테스트 재현으로만 확인됨 (by design — 관찰 기간 설계).
4. **RUNBOOK-enable.md:12 오탈자** — "任 실패" 중국어 혼입 (cosmetic, 기능 무영향).
5. **토큰 매칭 단순성** — 공백 분리 완전 일치만. 'gr86'↔'그랜드랜지'류 이형 표기는 미매칭 (설계상 의도 — 과적합 방지, 슬로우 키워드 강등은 Wave 3 out-of-scope).

## 비고 (정직성 명시)

- 본 검증은 코드 무변경 read-only로 수행됨. 유일한 write = 본 VERIFICATION.md.
- 추출기 재실행으로 `data/keyword_performance.json` 재생성됨 (재생산 가능 구조 — 원시 analytics.db 보존, 롤백 불필요).
