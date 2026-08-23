# DASHBOARD SSOT EXPERIMENT v2 — 계획서

> 생성: 2026-08-20 (계획 문서 — 실행 아님)
> **RECONCILED_CANDIDATE_BASELINE: 2026-08-20**
> 이전 1067행 파일은 hash/provenance 부재로 authority 상실. 본 문서가 reconciled candidate baseline.
> **RECONCILED_CANDIDATE_HASH**: `18579234b18789da4971a2d5f93dd4a5ffb0ad832365f7678712dfe19f40bc71`
> ⚠️ docs-only commit 전에는 **canonical이라고 표현하지 않는다** — RECONCILED_CANDIDATE만 사용.
> 코드 변경: 없음 / DB 변경: 없음 / RecheckAll: 없음 / 커밋: 없음 / 배포: 없음 / push: 없음

---

## 승인 상태 추적

| 문서 | 상태 | 승인 시각 | 비고 |
|---|---|---|---|
| QA 계획 (`DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md`) | **LEGACY_RUN_INVALID_FOR_LABELING** | 2026-08-20 | PLAN_DRIFT 해소 후 재분류 — artifact forensic에서 INDETERMINATE 확인. FRESH_RERUN_REQUIRED |
| Pilot 실행 | **LEGACY_RUN_INVALID_FOR_LABELING** | — | pilot-001 artifacts LEGACY_QUARANTINED_V1. pilot-v2.2 FRESH_RERUN_REQUIRED |
| Final Validation | NOT_APPROVED | — | Pilot 승인 후 독립 설계 |
| Paired Regression | NOT_APPROVED | — | Pilot 승인 후 독립 실행 |
| G5 (성과 벤치마크) | PENDING/BLOCKED | — | Pilot 결과 필요 |
| TP13+c01 FP4 | UNRESOLVED_PROVENANCE | — | 기존 상태 유지 |

**PLAN_DRIFT 해소 기록:**
- 이전 "FINAL APPROVED"(2026-08-20)는 1067행 버전에 부여됨
- 1067행 버전은 git 커밋 기록 없음 → hash/provenance 부재 → authority 상실
- 현재 버전 SHA-256(`18579234...`)이 **RECONCILED_CANDIDATE_HASH**로 확정
- docs-only commit 전까지는 canonical 표현 사용 금지

**κ 규칙 및 estimand convention 회귀 검증: RESOLVED_CONTENT_MATCH**
- κ = N/A: 1−P_e = 0 (양쪽 reviewer 모두 동일 단일 범주)일 때만 적용 — 회귀 없음
- aggregate = two-sided 95% unweighted validation-sample bound — 유지
- per-stratum = one-sided 95% diagnostic gate — 유지
- oversampling 보수성 = 입증 없이 사용 금지 — 유지 |

**승인 기준 (APPROVED conditions):**
1. aggregate unweighted bound = two-sided 95% Clopper–Pearson
2. per-stratum gate = one-sided 95% 방식
3. zero-FN으로 5% upper bound 충족: binomial 기준 n≥59; 미달 strata는 diagnostic
4. κ = N/A: 1−P_e = 0일 때만 적용
5. immutable single-population snapshot + SHA-256 manifest
6. clean isolated worktree preflight
7. Pilot/Final/paired regression 승인 분리

---

## 0. 문서 동기화 상태

| 문서 | 커밋 | Baseline v2 동기화 |
|---|---|---|
| `DASHBOARD_TRUST_GATE_REPORT.md` | f0f619a62 | ✅ (v1/v2 계보, 187건, 91.4% 명시) |
| `VERIFIED_REMEDIATION_QUEUE.md` | f0f619a62 | ✅ |
| `DASHBOARD_CHECKER_PATCH_RESULT.md` | f0f619a62 | ✅ |
| `DASHBOARD_SSOT_AGENT_EXPERIMENT_RESULT.md` | ce9739922 | ✅ |
| **이 문서 (v2 계획)** | — | 작성 중 |

### Baseline 변경 이력

| 버전 | TP | FP | EA | UNC | 합계 | Precision | 비고 |
|---|---|---|---|---|---|---|---|
| v1 (교정본) | 212 | 196 | 5 | 25 | 438 | 52.0% | 부모집계 제거 + c01·c06 재판정 |
| **v2 (권위본)** | 212 | 207 | 8 | 11 | 438 | **50.6%** | semantic 11건 FP→UNC, R2-01 3건 UNC→EA |

v1→v2 변경: semantic SEM-Q2 11건(Viator 상품카드 할인배지/자연조언) FP 확정, R2-01 techpawz 3건 blogsmith r2_uploader 확인→EA.

---

## 1. 실험 목적

v1 실험(DASHBOARD_SSOT_AGENT_EXPERIMENT_RESULT.md)에서 확인한 한계:

- **measured precision 50.6%** — 대시보드만으로는 fail 행의 절반만 정확히 판정
- **FN(미탐지 결함) 미측정** — pass 행의 오漏는 검증 수단 없음
- **stale-evidence rate 미측정** — 24h 캐시 오염·mtime transient 등 시간 의존 오류 미분리
- **inter-rater reliability 없음** — 단일 에이전트의 1회 판정만 기록

v2 실험은 이 4개 한계를 직접 측정한다.

---

## 2. 불변 스냅샷 정의

### 2.1 스냅샷 생성 시점

```
SNAPSHOT_TIMESTAMP = <실행 시각, ISO 8601 + 타임존>
SNAPSHOT_BATCH_ID  = ops.db check_results 테이블의 checked_at MAX
```

### 2.2 스냅샷 범위

```sql
-- fail 모집단: snapshot_F = {모든 status='fail' 행}
SELECT id, blog_id, check_name, rule_id, problem_id, severity, action,
       detail, evidence_url, checked_at
FROM check_results
WHERE status = 'fail';

-- pass 모집단: snapshot_P = {모든 status='pass' 행}
SELECT id, blog_id, check_name, rule_id, problem_id, severity, action,
       detail, evidence_url, checked_at
FROM check_results
WHERE status = 'pass';
```

### 2.3 각 행의 불변 메타데이터

| 필드 | 정의 | 출처 |
|---|---|---|
| `row_id` | check_results.id (PK, autoincrement) | ops.db |
| `rule_version` | checker 모듈의 `__version__` 또는 git commit SHA | `ops_dashboard/checks/*.py` git HEAD |
| `evidence_timestamp` | evidence_url을 마지막으로 HTTP GET한 시각 | 스냅샷 생성 시 curl 기록 |
| `evidence_hash` | HTTP 응답 body의 SHA-256 (텍스트 응답 한정) | 스냅샷 생성 시 해시 |
| `evidence_http_status` | HTTP 응답 코드 | 스냅샷 생성 시 curl 기록 |

### 2.4 스냅샷 저장 위치

```
data/ssot_experiment_v2/
├── snapshot_fail.csv        # fail 모집단 (모든 행)
├── snapshot_pass.csv        # pass 모집단 (모든 행)
├── evidence_fetch_log.csv   # row_id, url, http_status, fetch_time, body_sha256
├── blog_domain_map.csv      # blog_id → domain, site_path, brand (blog_lifecycle)
├── snapshot_manifest.json   # snapshot_timestamp, rule_version, total_fail, total_pass
└── checker_source_hash.csv  # check_name → file_path, sha256 (checker 코드 해시)
```

### 2.5 불변성 보장

1. 스냅샷 생성 후 **ops.db에任何 쓰기 금지** — RecheckAll, pending_fixes INSERT/UPDATE 금지
2. 스냅샷 CSV는 `git add`하지 않음 (운영 커밋과 혼동 방지). 별도 `data/ssot_experiment_v2/`에 보관
3. evidence fetch는 `curl -s -o /dev/null -w "%{http_code}"` + `sha256sum` 조합으로 응답 본문 해시 기록
4. snapshot_manifest.json에 `immutable=true` 플래그 — 이후任何 수정 시 검증 실패

### 2.6 스냅샷 독립성 — Live DB 변경 무효화 방지

스냅샷은 **생성 시점의 불변 복제본**이다. 스냅샷 생성 후 ops.db에서 발생하는 어떤 변경도 스냅샷을 무효화하지 않는다:

| 변경 유형 | 스냅샷 영향 | 이유 |
|---|---|---|
| RecheckAll 실행 (check_results 덮어쓰기) | **무효화 없음** | 스냅샷 CSV는 이미 복제됨. 새 batch는 별도 row |
| pending_fixes INSERT/UPDATE | **무효화 없음** | 스냅샷은 check_results만 포함 |
| blog_lifecycle 수정 | **무효화 없음** | blog_domain_map.csv는 스냅샷 시점 고정 |
| checker 코드 수정 (.py) | **무효화 없음** | checker_source_hash.csv는 스냅샷 시점 고정. 새 코드는 patched regression에서만 사용 |
| ops.db 삭제/재생성 | **무효화 없음** | 스냅샷 CSV는 독립 파일 |

**단, 한 가지 예외**: 스냅샷 CSV 파일 자체를 수정하면 해당 스냅샷은 무효화된다. 이를 방지하기 위해:

```
snapshot_fail.csv    → SHA-256 기록 (snapshot_manifest.json에 포함)
snapshot_pass.csv    → SHA-256 기록
blog_domain_map.csv  → SHA-256 기록
evidence_fetch_log.csv → SHA-256 기록
```

스냅샷 사용 전 **검증 명령어**:
```bash
sha256sum -c data/ssot_experiment_v2/snapshot_hashes.sha256
# 모든 파일이 OK여야 스냅샷 유효
```

### 2.7 스냅샷 고정 메타데이터

| 필드 | 값 (예시) | 기록 시점 |
|---|---|---|
| `as_of` | `2026-08-20T17:21:31Z` | 스냅샷 추출 시 (ops.db checked_at MAX) |
| `schema_version` | `check_results v1` | ops.db 스키마 버전 (SQLite PRAGMA table_info) |
| `rule_version` | git SHA (`f0f619a62`) 또는 `unpatched` | checker 코드 기준 |
| `total_fail` | 스냅샷 추출 시 `SELECT COUNT(*) FROM check_results WHERE status='fail'` 실측 | 스냅샷 추출 시 |
| `total_pass` | 스냅샷 추출 시 `SELECT COUNT(*) FROM check_results WHERE status='pass'` 실측 | 스냅샷 추출 시 |
| `snapshot_fail_sha256` | `a1b2c3...` | CSV 파일 해시 |
| `snapshot_pass_sha256` | `d4e5f6...` | CSV 파일 해시 |
| `experiment_phase` | `pilot` 또는 `final` | 실험 단계 |
| `population_query` | `SELECT ... FROM check_results WHERE status='fail'` | SQL 쿼리 원문 |
| `population_query_sha256` | `e7f8a9...` | 쿼리 문자열 해시 |
| `sampling_seed` | `42` (또는 `null` for deterministic) | 난수 시드 (재현성용) |
| `sampling_frame_hash` | `b3c4d5...` | 추출된 표본 CSV의 SHA-256 |
| `confidence_method` | aggregate: `two-sided 95% Clopper-Pearson`; per-stratum gate: `one-sided 95% Clopper-Pearson` | estimand별 신뢰구간 계산 방법 사전 고정 |
| `review_packet_version` | `v2.1` | blind packet 스키마 버전 |

snapshot_manifest.json은 위 14개 필드를 모두 포함하며, 실행 시 자동 기록된다.

**모집단 provenance — 단일 확정 원칙:**
- 스냅샷의 total_fail/total_pass는 **생성 시점의 고정 query + as_of + row count + CSV SHA-256**으로 단 하나의 모집단을 확정
- historical 참고치: baseline v2 기준 fail=554, active=438 (§0 Baseline 변경 이력)
- current live: fail=408, total=1,746 (2026-08-20 READ-ONLY 조회)
- 이 값들은 스냅샷 모집단과 별도 provenance로 기록 — 스_snapshop 생성 시점의 fail count가 스냅샷의权威

---

## 3. 층화 표본 설계 — Pilot + Final Validation 분리

실험은 **두 단계**로 진행된다:

| 단계 | 목적 | fail 표본 | pass 표본 | 합계 |
|---|---|---|---|---|
| **Phase 1: Pilot** | 절차 검증 + FN 95% CL 탐색 | 90 | 46 | **136** |
| **Phase 2: Final Validation** | 운영 게이트 통과용 확정 측정 | 100 | **≥150** | **≥250** |

Phase 1과 Phase 2는 **독립 스냅샷**에서 각각 수행된다. Phase 1 결과를 보고 Phase 2 표본 설계를 조정할 수 있다.

### 3.1 Fail 모집단 층화 (공통 — Phase 1/2 동일 기준)

모든 check_name별로 stratified random sampling. 표본 크기는 checker별 fail 수에 비례:

| check_name | fail 수 | 위험도 | Phase 1 표본 | Phase 2 표본 | 표본 전략 |
|---|---|---|---|---|---|
| c08_live_file_mismatch | 85 | HIGH | 15 | 20 | TITLE_MISMATCH 5+/OG_MISSING 3+/SITE_UNREACHABLE 2+/random 5 |
| FM-MISSINGKEYS | 71 | HIGH | 12 | 15 | ETAP `_index.md` + CUAP 실제 누락 |
| c06_mtime_deploy | 45 | HIGH | 8 | 12 | TP 5 (미등록) + FP 3 (등록) |
| c01_curve_quote | 44 | HIGH | 8 | 12 | 자연어 5 + 기계 필드 3 |
| standard_compliance | 40 | HIGH | 0 (부모) | 0 (부모) | 제외 — 자동 집계 행 (informationhot 고유 1건 포함) |
| THUMBNAIL-01 | 36 | HIGH | 6 | 8 | TYPE-A/B/C/D |
| FM-DRAFT | 30 | HIGH | 5 | 6 | Live 200/404 |
| content_quality | 23 | HIGH | 5 | 8 | CQ03/CQ05/CQ01 |
| semantic | 22 | HIGH | 5 | 8 | Viator/한국어 실수치/페이지네이션 |
| c03_fm_key_leak | 20 | HIGH | 4 | 6 | 이중 frontmatter/categories leak |
| data_stock | 14 | MEDIUM | 3 | 5 | 완전소진/부분소진 |
| freshness | 14 | MEDIUM | 3 | 5 | 장기/중기 |
| R2-01 | 8 | MEDIUM | 3 | 4 | techpawz family/Gov CDN |
| maintenance_checklist | 6 | MEDIUM | 2 | 3 | 임의 |
| c04_prompt_leak | 5 | MEDIUM | 2 | 3 | CONFIRMED/FP |
| FM-FEATUREIMAGE | 4 | LOW | 2 | 2 | URL >200자 |
| crosslink_consistency | 4 | LOW | 2 | 2 | 임의 |
| rap_leak | 2 | LOW | 1 | 2 | — |
| render_health | 2 | LOW | 1 | 2 | — |
| R01 | 1 | LOW | 1 | 1 | compare-hugo |
| R06 | 1 | LOW | 1 | 1 | pet-hugo |
| **합계** | **410** | — | **90** | **~115** | — |

> frontmatter(68)와 standard_compliance(40) 부모 행은 제외 → fail 모집단 实效 = **410**

### 3.2 Pass 모집단 층화 — Pilot (Phase 1: n=46)

Pilot pass 표본은 FN 탐색 + zero-FN upper bound 계산용:

| check_name | pass 수 | Phase 1 표본 | 표본 전략 |
|---|---|---|---|
| c08 | 0 | **0** | pass 0건 — FN 측정 불가 |
| c06 | 31 | **5** | mtime>24h 3 + mtime<24h 2 |
| c01 | 34 | **5** | 임의 5 |
| standard | 41 | **5** | R01-R12 각 1개 |
| content_quality | 52 | **5** | CQ03/CQ05 |
| semantic | 54 | **5** | 임의 5 |
| c03 | 58 | **3** | 임의 3 |
| data_stock | 56 | **3** | 임의 3 |
| freshness | 64 | **3** | 임의 3 |
| 기타 | varies | **12** | 12개 checker에서 임의 1개씩 |
| **합계** | — | **46** | — |

### 3.3 Pass 모집단 층화 — Final Validation (Phase 2: n≥150)

Final validation pass 표본은 **운영 게이트 통과용 확정 측정**. ≥150개로 FN upper bound를 2.5% 이하로 좁힌다.

**고위험 checker 우선 할당** (fail ≥ 20인 checker — FN이 가장 치명적인 영역):

| check_name | pass 수 | 위험도 | Phase 2 표본 | 최소 표본/판정불가 조건 |
|---|---|---|---|---|
| c06 | 31 | HIGH | **15** | ≥5 sampled; <5 pass 존재 시 전수 |
| c01 | 34 | HIGH | **15** | ≥5 sampled |
| standard | 41 | HIGH | **15** | ≥5 sampled |
| content_quality | 52 | HIGH | **15** | ≥5 sampled |
| semantic | 54 | HIGH | **15** | ≥5 sampled |
| c03 | 58 | HIGH | **12** | ≥5 sampled |
| c08 | 0 | HIGH | **0** | pass 0건 → FN 측정 불가 (HIGH이나 pass 부재) |
| FM-MISSINGKEYS | 0 | HIGH | **0** | pass 0건 → FN 측정 불가 |
| THUMBNAIL-01 | 0 | HIGH | **0** | pass 0건 → FN 측정 불가 |
| FM-DRAFT | 0 | HIGH | **0** | pass 0건 → FN 측정 불가 |
| data_stock | 56 | MEDIUM | **10** | ≥5 sampled |
| freshness | 64 | MEDIUM | **10** | ≥5 sampled |
| maintenance_checklist | 79 | MEDIUM | **8** | ≥5 sampled |
| c04 | 73 | MEDIUM | **8** | ≥5 sampled |
| crosslink_consistency | 6 | LOW | **4** | pass 6건 중 4개 (66.7%) |
| rap_leak | 83 | LOW | **5** | ≥3 sampled |
| render_health | 83 | LOW | **5** | ≥3 sampled |
| c02/c05/c07/c09/gsd/indexnow | 78each | LOW | **10** | 각 2개씩 (기타 checker FN 기 baseline) |
| frontmatter | 10 | — | **5** | 부모 행_FN 측정 불가 — 별도 처리 |
| **합계** | — | — | **≥150** | — |

**checker별 표본/판정불가 조건:**

| 조건 | 기준 | 처리 |
|---|---|---|
| passPopulation = 0 | c08, FM-MISSINGKEYS, THUMBNAIL-01, FM-DRAFT, R01, R06 | operational FN/recall = **N/A** (측정 불가). known-good fixture 결과와 혼합하지 않음 |
| passPopulation > 0 AND sampled < 5 | — | FN估计 불가靠 → 해당 checker FN_rate = "insufficient sample" |
| passPopulation > 0 AND sampled ≥ 5 | — | FN_rate 계산 가능 → Two-sided 95% Clopper–Pearson upper bound 보고 |

> **주의**: sampled ≥ passPopulation의 50%일지라도 "확정 판정"으로 간주하지 않는다.
> 대신 checker별 **coverage(비율)**, **binomial one-sided upper bound**, 그리고 **FPC 참고 지표**를 각각 보고한다:
>
> **binomial one-sided 95% Clopper–Pearson 공식 (표준):**
> ```
> p_upper = 1 − α^(1/n)    (α = 0.05, FN = 0)
> n=15: p_upper = 1 − 0.05^(1/15) ≈ 0.181 = 18.1%
> n=12: p_upper = 1 − 0.05^(1/12) ≈ 0.218 = 21.8%
> ```
>
> **FPC(finite population correction) 참고 지표 — binomial CP와 혼합하지 않음:**
> ```
> hypergeometric exact FPC: N(모집단), n(표본), k=0일 때 p_upper 계산
> c06: N=31, n=15 → FPC_upper ≈ 13.4% (보수적 근사)
> c01: N=34, n=15 → FPC_upper ≈ 12.7%
> standard: N=41, n=15 → FPC_upper ≈ 11.2%
> CQ: N=52, n=15 → FPC_upper ≈ 10.1%
> semantic: N=54, n=15 → FPC_upper ≈ 9.9%
> c03: N=58, n=12 → FPC_upper ≈ 12.8%
>
> FPC는 모집단 크기가 유한할 때 binomial upper bound를 좁힐 수 있으나,
> checker별 N이 서로 다르고 표본이 불균등 층화되어 있으므로
> binomial CP를 대체하지 않고 별도 참고 지표로만 보고한다.
> 반올림: 소수점 첫째 자리까지 (예: 18.1%, 13.4%).
> ```
>
> | checker | sampled (n) | passPopulation (N) | coverage | binomial one-sided UB | FPC 참고 (N, n별) |
> |---|---|---|---|---|---|
> | c06 | 15 | 31 | 48.4% | **18.1%** | N=31, n=15 → ≈13.4% |
> | c01 | 15 | 34 | 44.1% | **18.1%** | N=34, n=15 → ≈12.7% |
> | standard | 15 | 41 | 36.6% | **18.1%** | N=41, n=15 → ≈11.2% |
> | CQ | 15 | 52 | 28.8% | **18.1%** | N=52, n=15 → ≈10.1% |
> | semantic | 15 | 54 | 27.8% | **18.1%** | N=54, n=15 → ≈9.9% |
> | c03 | 12 | 58 | 20.7% | **21.8%** | N=58, n=12 → ≈12.8% |
>
> **해석**: 표준 binomial one-sided 95% UB는checker별 n에만 의존 (c06/c01 동일 n=15 → 동일 18.1%).
> FPC 참고 지표는 N에 따라 다르나, 불균등 층화 표본에서의 해석이 불확실하므로 별도 보고.

### 3.4 Pilot vs Final Validation 분리 원칙

| 구분 | Phase 1 (Pilot) | Phase 2 (Final Validation) |
|---|---|---|
| **목적** | 절차 검증, FN 탐색,κ pilot | 운영 게이트 통과용 확정 측정 |
| **스냅샷** | 독립 (ops.db 별도 시점) | 독립 (ops.db 별도 시점) |
| **pass 표본** | n=46 (two-sided upper=7.7%) | n≥150 (two-sided upper≤2.43%) |
| **결과** | DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md | DASHBOARD_SSOT_EXPERIMENT_V2_RESULT.md |
| **게이트** | — | precision ≥ 90% AND FN_rate upper < 5% AND κ ≥ 0.60 |
| **재사용** | Phase 2에서 Phase 1 fail 표본 재사용 가능 | — |

**절대 규칙: Pilot과 Final은 합산하지 않는다.**
- Pilot과 Final의 confusion matrix를 합산하여 aggregate precision/fn_rate를 계산하지 않는다
- 각각 독립 스냅샷·독립 표본·독립 결과로 보고한다
- Final 결과 문서에만 "운영 게이트 판정" 섹션이 포함된다

**Pilot → Final 설계 조정 규칙:**
Phase 1 결과를 보고 Phase 2 표본 설계를 조정할 수 있다.
단, **Final labeling이 시작되기 전에** 아래3항을 동결한다:

1. **Final sampling plan**: checker별 fail/pass 표본 크기 확정
2. **Final threshold**: precision·FN_rate·κ 임계치 확정
3. **Final snapshot**: ops.db에서 스냅샷 추출 후 독립 보관

동결 이후에는 Phase 1 결과를 참조하더라도 Final 표본·임계치·스냅샷을 변경하지 않는다.

- Phase 1에서 FN > 0 발견 시 → Phase 2에서 해당 checker 표본 확대 (동결 전)
- Phase 1에서 특정 checker FP율 매우 높음 확인 시 → Phase 2에서 fail 표본 확대 (동결 전)
- Phase 1에서 κ < 0.40 확인 시 → labeling 절차 재설계 후 Phase 2 재실행 (동결 전)

**Pilot 승인 범위 (§9 승인 격리):**
- **Pilot 승인**: 스냅샷 생성, fail/pass 표본 추출, evidence fetch, blind labeling, adjudication, κ 계산, paired regression까지만
- **Final 미승인**: Pilot 결과가 나오기 전에 Final labeling·patched RecheckAll·Final paired regression을 "승인된 것"으로 표현하지 않는다
- Pilot 결과 문서(DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md)에 **운영 게이트 판정 섹션 없음** — Pilot은 절차 검증용
- Final 실행 승인은 Pilot 결과 문서 확인 후에만 가능

---

## 4. Blind Labeling 절차

### 4.1 독립 리뷰어 + Adjudicator

| 역할 | 담당 | 입력 | 판정 범주 | 독립성 |
|---|---|---|---|---|
| **Reviewer A** | 에이전트 (OpenCode/MiMo) | blind evidence packet (아래 4.2) | TP/FP/UNC/EA | B의 판정 미열람 |
| **Reviewer B** | 사람 (개발자) | blind evidence packet + 전 근거 (소스/라이브/sitemap/deploy.log) | TP/FP/UNC/EA | A의 판정 미열람 |
| **Adjudicator** | 제3자 (또는 A+B 합의) | disagreement 행만 | TP/FP/UNC/EA 최종 | A/B 판정 모두 열람 후 |

**Adjudicator 규칙:**
1. A와 B의 verdict가 **동일**하면 → 해당 verdict 자동 확정
2. A와 B의 verdict가 **다르면** → Adjudicator가 재검토 후 최종 verdict 확정
3. Adjudicator도 판정 불가하면 → "unresolved-abstained"
4. Adjudicator는 A/B와 동일인이어도 되지만, **독립 판정을 먼저 수행한 뒤** 재검토

### 4.2 Blind Evidence Packet 설계

각 표본 행에 대해 **Reviewer A와 B가 동등한 blind packet**을 받는다.
양쪽 모두 dashboard verdict·기존 adjudicated label·expected answer가 제거된다.
판정에 필요한 **authoritative evidence는 동일하게 제공**된다:

#### 4.2.1 공통 Blind Packet (A/B 동일)

```
{
  "row_id": 144053,
  "check_name": "semantic",
  "rule_description": "SEM-Q2: percentage without source keyword",
  "detail": "144053: SEM-Q2 위반: 잔존가치 57%",
  "evidence_url": "https://deal.informationhot.kr/posts/...",
  "evidence_fetched_at": "2026-08-20T17:30:00Z",
  "evidence_http_status": 200,
  "evidence_body_sha256": "a1b2c3...",
  "authoritative_evidence": {
    "source_file_path": "/Users/twinssn/Projects/CAP/deal-hugo/content/posts/...",
    "source_content_snippet": "... 잔존가치 57% ...",
    "blog_domain": "deal.informationhot.kr",
    "brand": "CAP",
    "sitemap_lastmod": "2026-08-19T...",
    "deploy_log_entry": "(없음 또는 최근 배포 기록)"
  }
}
```

**제거 정보 (A/B 동일)**:
- dashboard verdict (status='fail'/'pass')
- 기존 adjudicated label (TP/FP/UNC/EA)
- expected answer / ground truth

**제공 정보 (A/B 동일)**:
- check rule description
- evidence URL + HTTP status + body hash
- authoritative evidence: source file, domain, brand, sitemap, deploy log

#### 4.2.2 Adjudication 전용 Packet

Adjudicator는 **독립 판정을 먼저 수행한 뒤**에만 A/B 결과에 접근한다:

```
Phase 1: Adjudicator가 disagreement 행에 대해 독립 판정
  → blind packet만으로 TP/FP/UNC/EA 판정

Phase 2: 독립 판정 완료 후에만 추가 정보 열람
  → full provenance (A/B verdict, confidence, evidence_summary)
  → 최종 verdict 확정 또는 unresolved-abstained
```

Adjudicator에게는 A/B의 판정이 **독립 판정 완료 전까지 절대 노출되지 않는다**.

#### 4.2.3 Packet 생성 절차

```
Step 1: 표본 CSV에서 row_id 추출
Step 2: evidence_url → HTTP GET → body SHA-256 계산
Step 3: authoritative evidence 수집 (source file, domain, brand, sitemap, deploy log)
Step 4: blind_packet.json 생성 — A/B 동일 (verdict/label/answer 제거 + evidence 포함)
Step 5: 각 packet에 row_id 매핑 (A용, B용, Adjudicator용 동일 blind_packet)
Step 6: 리뷰어에게 packet 전달 — A/B에게는 서로의 판정 미전달
Step 7: Adjudicator에게는 독립 판정용 blind_packet만 먼저 전달
```

### 4.3 Disagreement 해결 — Adjudication 절차

```
Phase 1: 독립 판정
  → A: blind packet으로 TP/FP/UNC/EA 판정 + confidence(1-5) + evidence_summary
  → B: full packet으로 TP/FP/UNC/EA 판정 + confidence(1-5) + evidence_summary

Phase 2: 합의 확인
  → A verdict == B verdict → 확정 (agreement)
  → A verdict ≠ B verdict → disagreement → Phase 3

Phase 3: Adjudication
  → Adjudicator가 두 판정과 양쪽 evidence를 열람
  → Adjudicator가 최종 verdict 확정 또는 "unresolved-abstained"
  → Adjudicator의 판단 근거를 evidence_summary에 기록

Phase 4: κ 계산
  → Raw agreement (adjudication 전): κ_raw
  → Adjudicated agreement (adjudication 후): κ_adj
  → 두 값을 모두 보고 — чем 높을수록 리뷰어 독립성 좋음
```

### 4.4 Cohen's Kappa + 신뢰구간

#### 4.4.1 Point Estimate

```
κ = (P_o - P_e) / (1 - P_e)

P_o = 관찰된 합의율 = (TP 합의 + FP 합의 + UNC 합의 + EA 합의) / N
P_e = 우연 합의 기대값 = Σ_k (A_k 비율 × B_k 비율)

해석:
  κ < 0.20  → poor
  0.20-0.40 → fair
  0.40-0.60 → moderate
  0.60-0.80 → substantial
  0.80-1.00 → almost perfect

κ 계산 불가 조건:
  분모 (1 − P_e) = 0일 때만 κ는 정의 불가 (division by zero).
  이는 양쪽 reviewer(A, B)가 모두 동일 단일 범주로만 판정한 경우에 발생한다.
  
  한 reviewer만 단일 범주이고 다른 reviewer가 복수 범주를 사용하면:
    P_e < 1.0 → 분모 > 0 → κ 계산 가능
    실제 confusion matrix에서 P_o, P_e, κ를 그대로 계산한다
    (단일 범주 reviewer의 편향이 κ에 반영되지만这是 informative — 낮은 κ가 편향을 드러냄)
  
  양쪽 reviewer 모두 동일 단일 범주로 고정된 경우:
    P_e = 1.0 → κ = N/A (계산 불가)
    대체 보고: raw agreement = 100% (단일 범주 고정)
    원인 기록: "양쪽 reviewer 모두 [범주]로 판정하여 P_e=1.0, κ 계산 불가"
```

#### 4.4.2 신뢰구간 (95% CI)

```
κ의 95% 신뢰구간 (Method: Fleiss-Cohen approximate CI):

SE(κ) = sqrt( (1 / (N × (1-P_e)^2)) × [P_o × (1-P_o)] )

95% CI = [κ − 1.96 × SE(κ), κ + 1.96 × SE(κ)]

가정:
  - 표본이 모집단에서 무작위 추출됨 (stratified sampling의 경우 가정 위반 가능)
  - 각 행의 판정이 독립
  - Fleiss-Cohen SE는 large-sample 근사 — small per-strata n에서 보수적 불확실성 과소평가 가능

해석:
  CI가 0을 포함하면 → 우연 합의와 구분 불가 (κ 통계적으로 유의하지 않음)
  CI 하한 ≥ 0.40 → moderate 이상으로 유의
  CI 하한 ≥ 0.60 → substantial 이상으로 유의
```

#### 4.4.3 불균등 층화 표본에서의κ 해석

disproportionate stratified sampling으로 인해 **aggregateκ가 모집단 대표값이 아닐 수 있다**.
고fail checker(예: c08=85건)의 표본 비중이 높으면 해당 checker의 agreement 특성이 κ에 과대 반영된다.

**보고 방식:**

1. **checker/위험도별 agreement**: 각 checker(또는 위험도 strata)별로 독립 confusion matrix + agreement율 보고
2. **aggregateκ**: 전체 표본에 대한κ (단독 보고 금지 — per-strata 결과와 함께 보고)
3. **가중κ (선택)**: checker별 fail 수로 가중한 weightedκ — 모집단 대표값에 더 가까울 수 있으나 해석이 복잡

```
보고 형식:
  Per-strata agreement:
    c08: XX% (n=15), c06: XX% (n=8), ...
  Aggregate: κ = 0.XX (95% CI: [0.YY, 0.ZZ])
    → 단독 해석 금지 — per-strata 결과와 함께 해석
```

#### 4.4.4 보고 형식

```
Per-strata agreement:
  c08: XX% (n=15), c06: XX% (n=8), standard: XX% (n=5), ...

Per-strata κ (가능한 경우만):
  c08: κ = 0.XX (n=15), c06: κ = 0.XX (n=8), ...
  단, 양쪽 reviewer 모두 동일 단일 범주로 판정하면 해당 strata는 κ = N/A + raw agreement 보고
  (한 reviewer만 단일 범주이면 κ 계산 — 실제 confusion matrix 사용)

Aggregate:
  κ = 0.XX (95% CI: [0.YY, 0.ZZ]) 또는 κ = N/A (양쪽 모두 동일 단일 범주 고정)
  - CI 계산 방식: Fleiss-Cohen approximate SE (large-sample 근사)
  - 가정: 각 행 독립, stratified sampling → aggregate는 모집단 대표값 아닐 수 있음
  - Raw agreement: XX% (adjudication 전)
  - Adjudicated agreement: XX% (adjudication 후)
  - Disagreement count: N건 (N/total = X.X%)
  - Unresolved-abstained: N건
  - per-strata agreement + per-strata κ와 함께 해석 — 단독 해석 금지
```

### 4.5 표본 × 리뷰어 매핑

| 대상 | 행 수 | Phase 1 리뷰어 | Phase 2 리뷰어 | 비고 |
|---|---|---|---|---|
| Fail 표본 | 90 / ~115 | A + B (독립) | A + B (독립) | blind labeling |
| Pass 표본 | 46 / ≥150 | A + B (독립) | A + B (독립) | FN 탐지 |
| **합계** | **136 / ≥265** | — | — | — |

---

## 5. 실험 메트릭 공식

### 5.1 confusion matrix (check별)

check_name별로 독립 confusion matrix:

```
                    B: TP    B: FP    B: UNC   B: EA    B: PASS   합계
A: TP (fail→TP)     TP_TP    TP_FP    TP_UNC   TP_EA    —         a
A: FP (fail→FP)     FP_TP    FP_FP    FP_UNC   FP_EA    —         b
A: UNC (fail→UNC)   UNC_TP   UNC_FP   UNC_UNC  UNC_EA   —         c
A: EA (fail→EA)     EA_TP    EA_FP    EA_UNC   EA_EA    —         d
A: FN (pass→TP)     —        —        —        —        FN_PASS   e
A: TN (pass→PASS)   —        —        —        —        TN_PASS   f
합계                a'       b'       c'       d'       e'+f'     N
```

### 5.2 FN (False Negative) 공식

```
FN = pass 행 중Reviewer B가 TP로 판정한 수
   = pass 표본에서 B verdict = TP인 행 수

FN_rate = FN / pass 표본 수

의미: pass로 판정된 행 중 실제로는 결함이 있는 비율
      = checker가 놓친 결함의 비율
```

**Zero-FN 시 신뢰구간:**

Pass 표본에서 FN=0(관찰된 FN 없음)이더라도, 모집단 FN율이 0이라는 뜻은 아니다.
표본 크기에 따라 **95% 신뢰 상한(upper bound)**을 계산한다.

**사전 고정된 신뢰 convention — estimand별 구분:**
- **aggregate validation-sample bound** (전체 pass 표본 FN=0 상한): **Two-sided 95% Clopper–Pearson** (보수적)
- **per-stratum defect-detection gate** (checker별 FN≤5% 판정): **One-sided 95% Clopper–Pearson** (단측 — " FN이 5% 이하일 확신")
- Wilson score interval은 불균등 층화 표본에서의 해석이 불확실하므로 사용하지 않음
- Rule-of-3는 참고 근사치로만 사용 (표본 작을 때)

> 두 방법은 다른 추정치(estimand)에 대응하므로 혼합하지 않는다.
> aggregate는 " FN이 0일 때 표본 수준의 상한", per-stratum은 " FN≤5% 충족 여부"를 각각 판단한다.

| 방법 | 공식 | 추정치(estimand) | Phase 1 (n=46) | Phase 2 (n=150) |
|---|---|---|---|---|
| **Two-sided 95% Clopper–Pearson** | p_upper = 1 − (α/2)^(1/n) | aggregate validation-sample bound | **7.7%** | **2.43%** |
| **One-sided 95% Clopper–Pearson** | p_upper = 1 − α^(1/n) | per-stratum defect-detection gate | **6.3%** | **1.98%** |
| Rule-of-3 (근사) | p_upper ≈ 3/n | 참고 근사 | ≈6.5% | ≈2.0% |

**해석 (estimand별):**
- **aggregate (two-sided)**: Phase 1에서 FN=0 관찰 시 → "양측 95% 신뢰구간 상한 = **7.7%** — pass 행의 최대 7.7%에 실제 결함이 있을 수 있다"
- **per-stratum gate (one-sided)**: checker별 FN=0 관찰 시 → "단측 95% 신뢰 상한 = **6.3%** (n=46) 또는 **1.98%** (n=150) — FN≤5% 충족 여부 판단"
- FN > 0 관찰 시: FN_rate point estimate + Clopper–Pearson 신뢰구간 직접 계산

**Phase 1 Pilot zero-FN 판정:**
- Pilot pass n=46, FN=0 → Two-sided upper bound = 7.7%
- upper bound가 5%를 초과하여 FN_rate 기준(5% 이하)을 충족하지 못함
- Phase 2에서 n≥150으로 확대하면 upper bound ≤ 2.43%로 수렴하여 기준 충족 가능

**unweighted validation-sample bound — 이름과 해석 제한:**
- Final pass≥150에 적용한 two-sided Clopper–Pearson upper bound는 **"unweighted validation-sample bound"**로 명명한다
- 이 값은 표본 내에서 관찰된 FN=0의 통계적 상한일 뿐, **모집단 operational FN rate로 직접 해석하지 않는다**
- 불균등 층화 표본에서 고fail checker의 oversampling이 FN=0 관찰에 영향을 줄 수 있으므로, 모집단 FN율에 대한 추정은 별도 설계가 필요

**design-aware 추정 — operational FN rate를 주장하기 위한 요구사항:**
operational FN rate를 공식적으로 주장하려면 아래 조건을 충족해야 한다:

1. **사전 고정된 stratum weight**: checker별 fail 수에 비례한 가중치 (예: c08 weight = 85/410)
2. **sampling probability**: checker별 표본 추출 확률 (n_check / N_check)
3. **checker별 population count**: ops.db에서의 checker별 pass 행 수 (N_check)
4. **design-aware 추정 공식**: Horvitz-Thompson 또는 GREG 추정기 사용
5. **design-based CI**: Taylor linearization 또는 bootstrap (strata별 resampling)

**하지만 본 실험에서는 이 설계를 적용하지 않는다.** 대신:
- **Primary gate**: checker/위험 strata별 zero-FN bound (binomial **one-sided** 95% CP)를 각각 보고
- high-risk checker(c06, c01, standard, CQ, semantic, c03)의 per-strata upper bound가 모두 5% 이하인지 확인
- aggregate bound는 "unweighted validation-sample bound" (two-sided)로만 보고 — operational FN claim 불가

**per-strata defect-detection gate의 실제 임계치:**
- FN≤5%를 one-sided 95% Clopper–Pearson으로 입증하려면 zero-FN 시 **n ≥ 59** 필요
  - 검증: p_upper = 1 − 0.05^(1/59) = 1 − 0.9501 = 0.0499 ≈ 5.0% (경계값)
  - n=59 초과 시 p_upper < 5% → FN≤5% 입증
- **현재 표본 n=12~15로는 FN≤5%를 입증할 수 없다**
  - n=15: one-sided UB ≈ 18.1%
  - n=12: one-sided UB ≈ 21.8%
- N(모집단) < 59인 checker — finite-population census 또는 exact hypergeometric gate 적용:
  - census: passPopulation 전수 조사 (N≤30인 경우 가능하면)
  - exact hypergeometric: N, n, k=0에서 hypergeometric upper bound 직접 계산
  - 이 두 방법도 per-stratum에만 적용 — aggregate 적용 안 함

**표본 확대가 불가능한 경우:**
- per-strata 결과는 **diagnostic metric**으로 격하 — operational FN≤5% 승인 기준으로 사용하지 않음
- operational FN≤5%를 주장하려면 design-aware 추정 또는 n≥59 확보가 필수
- 본 실험의 모든 checker는 n=12~15 → per-strata FN gate는 diagnostic 용도로만 보고

**high-risk oversampling의 보수성 가정에 대한 주의:**
- 고fail checker(예: c08=85건)의 oversampling이 FN=0 관찰을 더 보수적으로 만든다는 가정은 **입증되지 않았다**
- 실제로는 고fail checker가 더 많은 FN를 가질 수 있으므로 oversampling이 FN 탐지 확률을 높일 수도 있음
- 따라서 "oversampling은 보수적"이라는 통계적 보장으로 사용하지 않는다
- 대신 per-strata upper bound를 각각 계산하여 checker별로 독립 평가

### 5.3 Precision 공식

```
precision = TP / (TP + FP)

여기서 TP = A=TP AND B=TP (양쪽 모두 TP 판정)
      FP = A=FP AND B=FP (양쪽 모두 FP 판정 — 또는 B=FP)

확장 precision = (A=TP∩B=TP + A=FP∩B=FP) / (A≠UNC∩B≠UNC∩B≠EA 전체)
```

**v2 실험의 precision 측정값:**
```
measured_precision = TP_合의 / (TP_合의 + FP_合의 + FN)
projected_precision = TP_合의 / (TP_合의 + FP_合의 + FN +UNC_合의)
```

### 5.4 Recall 공식

```
recall = TP / (TP + FN)

FN = pass 행 중Reviewer B가 발견한 실제 결함

의미: 전체 실제 결함(TP+FN) 중 checker가 탐지한 비율
```

**v1에서는 N/A였던 값을 v2에서 최초 측정.**

### 5.5 Specificity 공식

```
specificity = TN / (TN + FP)

TN = pass 행 중Reviewer B가 PASS로 확인한 수
FP = fail 행 중Reviewer B가 FP로 판정한 수

의미: 실제 정상 행을 정상으로 판정한 비율
      (check_name별 계산)
```

### 5.6 Abstention Accuracy 공식

```
abstention_accuracy = UNC_合의 / UNC_total

UNC_합의 = A=UNC AND B=UNC (양쪽 모두 보류)
UNC_total = A=UNC 전체 행 수

의미: 에이전트가 "판정 불가"라고 한 행 중실제로도 판정 불가한 비율
      (높을수록 "정확한 모름")
```

### 5.7 Stale-Evidence Rate 공식

```
stale_evidence_rate = stale_count / total_evidenced

stale_count = evidence_timestamp < checked_at - STALE_THRESHOLD 인 행 수
STALE_THRESHOLD = checker별 상이:
  - c08: 24h (캐시 TTL)
  - c06: 1h (mtime transient)
  - semantic: 7d (콘텐츠 변경 주기)
  - CQ: 7d
  - THUMBNAIL-01: 30d (이미지 교체 빈도)
  - 기타: 24h

의미: evidence가 스냅샷 시점에 유효하지 않은 비율
      = "오래된 증거로 판정한 비율"
```

---

## 6. Paired Regression 실험

### 6.1 실험 설계

```
snapshot_clone = ops.db의 read-only 복제본 (SQLite VACUUM INTO)

Phase A: snapshot_clone에서 기존 checker (unpatched) 실행
  → result_A = {check_name: {row_id: verdict_A}}

Phase B: snapshot_clone에서 패치된 checker (patched) 실행
  → result_B = {check_name: {row_id: verdict_B}}

paired_diff = result_B - result_A (row_id별 verdict 변화)
```

### 6.2 비교 메트릭

| 메트릭 | 공식 | 의미 |
|---|---|---|
| **FP 제거율** | count(verdict_A=FP AND verdict_B≠FP) / count(verdict_A=FP) | 패치가 제거한 FP 비율 |
| **TP 유지율** | count(verdict_A=TP AND verdict_B=TP) / count(verdict_A=TP) | 패치가 TP를 손상시키지 않은 비율 |
| **EA 변화** | count(verdict_B=EA) - count(verdict_A=EA) | EA 판정 변화 |
| **UNC 변화** | count(verdict_B=UNC) - count(verdict_A=UNC) | UNC 판정 변화 |
| **Precision 변화** | precision_B - precision_A | 패치 전후 precision 차이 |
| **checker별 FP delta** | FP_A(check) - FP_B(check) per check_name | checker별 효과 |

### 6.3 안전장치

1. **snapshot_clone만 사용** — 운영 DB에任何 쓰기 없음
2. **snapshot_clone은 read-only 마운트** (`chmod 444` 또는 `:memory:` 복제)
3. **패치된 checker는 snapshot_clone 위에서만 실행** — 기존 ops_dashboard/checks/*.py는 수정하지 않음
4. **결과는 비교 전용 파일에 기록** — `data/ssot_experiment_v2/regression_result.json`

### 6.4 비교 보고서 형식

```json
{
  "snapshot_timestamp": "...",
  "patch_version": "...",
  "before": {"total_fail": N, "precision": X, "per_check": {...}},
  "after": {"total_fail": N, "precision": Y, "per_check": {...}},
  "delta": {"fp_removed": N, "tp_maintained": N, "precision_delta": Y-X},
  "per_check_regression": {
    "c08": {"fp_before": 84, "fp_after": 8, "tp_before": 0, "tp_after": 0},
    "c01": {"fp_before": 47, "fp_after": 0, ...},
    ...
  }
}
```

---

## 7. 실행 절차 (단계별)

### Phase 1: Pilot (n=136)

#### Step 1: 스냅샷 생성

```bash
# 1-1. fail 스냅샷
python3 -c "
import sqlite3, csv, hashlib, json
from datetime import datetime, timezone

conn = sqlite3.connect('ops_dashboard/ops.db')
now = datetime.now(timezone.utc).isoformat()

# fail
cur = conn.execute('SELECT id, blog_id, check_name, rule_id, problem_id, severity, action, detail, evidence_url, checked_at FROM check_results WHERE status=\"fail\"')
with open('data/ssot_experiment_v2/pilot/snapshot_fail.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow([d[0] for d in cur.description])
    w.writerows(cur)

# pass
cur = conn.execute('SELECT id, blog_id, check_name, rule_id, problem_id, severity, action, detail, evidence_url, checked_at FROM check_results WHERE status=\"pass\"')
with open('data/ssot_experiment_v2/pilot/snapshot_pass.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow([d[0] for d in cur.description])
    w.writerows(cur)

# blog-domain
cur = conn.execute('SELECT blog_id, domain, site_path, brand, config_status FROM blog_lifecycle')
with open('data/ssot_experiment_v2/pilot/blog_domain_map.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow([d[0] for d in cur.description])
    w.writerows(cur)

fail_count = conn.execute('SELECT COUNT(*) FROM check_results WHERE status=\"fail\"').fetchone()[0]
pass_count = conn.execute('SELECT COUNT(*) FROM check_results WHERE status=\"pass\"').fetchone()[0]
conn.close()

# SHA-256
hashes = {}
for fn in ['snapshot_fail.csv', 'snapshot_pass.csv', 'blog_domain_map.csv']:
    with open(f'data/ssot_experiment_v2/pilot/{fn}', 'rb') as f:
        hashes[fn] = hashlib.sha256(f.read()).hexdigest()

manifest = {
    'snapshot_timestamp': now,
    'as_of': '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
    'schema_version': 'check_results v1',
    'rule_version': 'unpatched (pre-5-checker)',
    'total_fail': fail_count,
    'total_pass': pass_count,
    'immutable': True,
    'sha256': hashes
}
with open('data/ssot_experiment_v2/pilot/snapshot_manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

# SHA-256 검증 파일
with open('data/ssot_experiment_v2/pilot/snapshot_hashes.sha256', 'w') as f:
    for fn, h in hashes.items():
        f.write(f'{h}  {fn}\n')
"

# 1-2. checker 코드 해시
find ops_dashboard/checks/ -name '*.py' -exec sha256sum {} \; > data/ssot_experiment_v2/pilot/checker_source_hash.csv
```

#### Step 1.5: 스냅샷 독립성 검증

```bash
# 스냅샷 생성 직후 SHA-256 검증
sha256sum -c data/ssot_experiment_v2/pilot/snapshot_hashes.sha256
# 모든 파일 OK여야 스냅샷 유효

# 스냅샷 메타데이터 출력
cat data/ssot_experiment_v2/pilot/snapshot_manifest.json | python3 -m json.tool
```

#### Step 2: 표본 추출

```bash
python3 scripts/ssot_v2_sample.py \
  --fail-csv data/ssot_experiment_v2/pilot/snapshot_fail.csv \
  --pass-csv data/ssot_experiment_v2/pilot/snapshot_pass.csv \
  --output-dir data/ssot_experiment_v2/pilot/samples/ \
  --phase pilot \
  --fail-target 90 \
  --pass-target 46
```

#### Step 3: Evidence Fetch + Blind Packet 생성

```bash
# evidence fetch
python3 scripts/ssot_v2_fetch.py \
  --samples data/ssot_experiment_v2/pilot/samples/ \
  --output data/ssot_experiment_v2/pilot/evidence_fetch_log.csv

# blind packet (Reviewer A용)
python3 scripts/ssot_v2_packets.py \
  --samples data/ssot_experiment_v2/pilot/samples/ \
  --evidence-log data/ssot_experiment_v2/pilot/evidence_fetch_log.csv \
  --mode blind \
  --output data/ssot_experiment_v2/pilot/packets_a.json

# full packet (Reviewer B용)
python3 scripts/ssot_v2_packets.py \
  --samples data/ssot_experiment_v2/pilot/samples/ \
  --evidence-log data/ssot_experiment_v2/pilot/evidence_fetch_log.csv \
  --mode full \
  --output data/ssot_experiment_v2/pilot/packets_b.json
```

#### Step 4: Blind Labeling

```
Reviewer A: pilot/packets_a.json → pilot/labeling_a.csv
Reviewer B: pilot/packets_b.json → pilot/labeling_b.csv
두 결과를 비교 없이 독립 생성
```

#### Step 5: Adjudication + κ 계산

```bash
# disagreement 탐지
python3 scripts/ssot_v2_adjudicate.py \
  --labeling-a data/ssot_experiment_v2/pilot/labeling_a.csv \
  --labeling-b data/ssot_experiment_v2/pilot/labeling_b.csv \
  --output data/ssot_experiment_v2/pilot/adjudication.csv

# κ 계산 (raw + adjudicated)
python3 scripts/ssot_v2_kappa.py \
  --labeling-a data/ssot_experiment_v2/pilot/labeling_a.csv \
  --labeling-b data/ssot_experiment_v2/pilot/labeling_b.csv \
  --adjudicated data/ssot_experiment_v2/pilot/adjudication.csv
```

#### Step 6: Paired Regression

```bash
# 스냅샷 클론 read-only로 복제
python3 -c "
import shutil
shutil.copy2('ops_dashboard/ops.db', '/tmp/ssot_v2_pilot.db')
"
chmod 444 /tmp/ssot_v2_pilot.db

# Unpatched
python3 scripts/ssot_v2_regression.py --mode=before --db=/tmp/ssot_v2_pilot.db

# Patched
python3 scripts/ssot_v2_regression.py --mode=after --db=/tmp/ssot_v2_pilot.db

# 비교
python3 scripts/ssot_v2_compare.py
```

#### Step 7: 결과 분석

```bash
python3 scripts/ssot_v2_analyze.py
# → DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md
```

### Phase 2: Final Validation (n≥265)

Phase 1 완료 후 **독립 스냅샷**에서 Phase 2 실행:

1. Step 1~7을 동일하게 반복 (pass_target=150으로 변경)
2. Phase 1 fail 표본(90건)은 재사용 가능 (동일 row_id, 동일 evidence)
3. Phase 2 fail 표본(115건)은 Phase 1과 겹치지 않도록 추출
4. 결과: `DASHBOARD_SSOT_EXPERIMENT_V2_RESULT.md`

> **⚠️ Phase 2는 현재 미승인.** Pilot 결과 문서(DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md)가
> 작성되고 검증된 후에만 Phase 2 실행이 가능하다. Pilot 없이 Final/paired regression을
> 승인된 것으로 간주하지 않는다.

---

## 8. 보고서 출력 형식

### 8.1 결과 문서 구조

#### Pilot 결과: DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md

```
DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md

0. 문서 동기화 상태 + baseline 변경 이력
1. 실험 질문
2. 스냅샷 정보 (as_of, schema_version, rule_version, SHA-256, experiment_phase, confidence_method, sampling_seed, review_packet_version)
3. Phase 1 Pilot 결과
   3.1 Fail 표본: A vs B contingency table
   3.2 Pass 표본: FN 탐지 결과 + two-sided 95% Clopper–Pearson upper bound (7.7%)
   3.3 Cohen's Kappa (point + 95% CI)
       - Per-strata agreement (checker별)
       - Aggregateκ + CI 계산 방식 + 가정 명시
   3.4 Disagreement 분석
4. confusion matrix (check별)
5. 메트릭 (measured precision, recall, specificity, abstention accuracy)
6. Paired Regression (before/after)
7. Phase 2 설계 조정 사항 (동결 전)
8. 잔존 위험
```

#### Final Validation 결과: DASHBOARD_SSOT_EXPERIMENT_V2_RESULT.md

```
DASHBOARD_SSOT_EXPERIMENT_V2_RESULT.md

0. 문서 동기화 상태 + baseline 변경 이력
1. 실험 질문
2. 스냅샷 정보 (Phase 2 독립 스냅샷, as_of, confidence_method, frozen plan)
3. Blind Labeling 결과
   3.1 Fail 표본: A vs B contingency table
   3.2 Pass 표본: FN 탐지 + two-sided 95% Clopper–Pearson upper bound (≤2.43%)
   3.3 Cohen's Kappa (point + 95% CI) — Phase 1/2 비교
       - Per-strata agreement (checker별)
       - Aggregateκ + CI 계산 방식 + 가정 명시
4. confusion matrix (check별)
5. 메트릭
   5.1 precision (measured)
   5.2 TP recall (measured — v1에서 최초 측정)
   5.3 specificity (check별)
   5.4 FN_rate (two-sided Clopper–Pearson upper bound)
   5.5 abstention accuracy
   5.6 stale-evidence rate
6. Paired Regression 결과 (before/after, FP 제거율, TP 유지율)
7. v1 대비 개선 분석
8. 운영 게이트 판정
   8.1 precision ≥ 90%? (pass/fail)
   8.2 FN_rate upper < 5%? (pass/fail)
   8.3 κ ≥ 0.60? (pass/fail)
   8.4 종합: GATE PASS / GATE FAIL
9. 잔존 위험
```

### 8.2 메트릭 요약표

| 메트릭 | v1 | Phase 1 Pilot | Phase 2 Final | 산출 근거 |
|---|---|---|---|---|
| measured precision | 50.6% | ? | ? | TP合의 / (TP合의 + FP合의 + FN) |
| projected precision (5체커) | 91.4% | — | ? | 5체커 patched 결과 기반 |
| TP recall | N/A | ? | ? | TP / (TP + FN) |
| specificity | N/A | ? (check별) | ? (check별) | TN / (TN + FP) |
| FN upper bound — per-strata (diagnostic) | N/A | checker별 n 기반 (18.1% for n=15) | checker별 n 기반 | binomial one-sided 95% CP — **diagnostic 격하** (n<59로 FN≤5% 입증 불가) |
| FN upper bound — aggregate (unweighted) | N/A | 7.7% (n=46) | ≤2.43% (n≥150) | unweighted validation-sample bound — operational FN 아님 |
| FN upper bound — FPC 참고 | N/A | — | checker별 N별 (별도 보고) | hypergeometric exact — binomial CP와 혼합 금지 |
| design-aware FN 추정 | N/A | 미측정 | 미측정 또는 N/A | Horvitz-Thompson 등 — 본 실험 미적용 |
| abstention accuracy | N/A | ? | ? | UNC合의 / UNC_total |
| stale-evidence rate | N/A | ? | ? | stale_count / total_evidenced |
| κ (aggregate, point) | N/A | ? 또는 N/A | ? 또는 N/A | P_o, P_e 계산 — 단일 범주 고정 시 N/A |
| κ (aggregate, 95% CI) | N/A | ? 또는 N/A | ? 또는 N/A | Fleiss-Cohen SE — per-strata와 함께 해석 |
| per-strata agreement | N/A | ? (checker별) | ? (checker별) | checker별 독립 agreement |
| per-strata κ | N/A | ? 또는 N/A | ? 또는 N/A | 단일 범주 고정 시 N/A + raw agreement |
| disagreement rate | N/A | ? | ? | disagreement / N |
| unresolved-abstained | N/A | ? | ? | adjudication 후 잔류 |

---

## 9. 제약 조건

1. **운영 DB 읽기만 허용** — snapshot_fail.csv/pass.csv 추출 후 ops.db에任何 쓰기 금지 (READ-ONLY SELECT 허용)
2. **패치 코드는 snapshot_clone에서만 테스트** — ops_dashboard/checks/*.py 수정 금지
3. **RecheckAll 금지** — 스냅샷 시점의 고정 데이터에서만 실험
4. **커밋·배포·push 금지** — 실험 결과는 문서에만 기록
5. **event 리스너 차단** — `shared/events.py`의 DISABLED 플래그 확인 필요
6. **Pilot 실행 환경 — clean worktree preflight (필수):**
   - Pilot snapshot의 `rule_version`은 **반드시 git-tracked된 source commit에서 파생**해야 한다
   - 기존 uncommitted checker patch(content_integrity.py +167, content_quality.py +20, frontmatter.py +4, standard.py +5)가 있는 dirty worktree에서 Pilot을 실행하면 안 된다
   - 옵션 A: `git stash` 또는 `git worktree add`로 clean 환경에서 스냅샷 생성
   - 옵션 B: 현재 dirty diff를 별도 hash로 보존 (`git diff > dirty_diff_20260820.patch; sha256sum dirty_diff_20260820.patch`) 후, snapshot_manifest의 `rule_version`에 source commit SHA 기록
   - dirty worktree에서 실행 시 snapshot_manifest에 `dirty_worktree: true` 플래그 + patch hash 추가 기록
   - **Pilot이 uncommitted patch의 checker 동작을 반영하면 안 됨** — Pilot은 unpatched baseline 기준

---

## 10. 예상 산출물

| 산출물 | 위치 | 커밋 대상 | 비고 |
|---|---|---|---|
| 스냅샷 CSV + manifest + SHA-256 | `data/ssot_experiment_v2/pilot/` | 아니오 | Phase 1 전용 |
| 스냅샷 CSV + manifest + SHA-256 | `data/ssot_experiment_v2/final/` | 아니오 | Phase 2 전용 |
| blind packet | `data/ssot_experiment_v2/*/packets_a.json` | 아니오 | Reviewer A용 |
| full packet | `data/ssot_experiment_v2/*/packets_b.json` | 아니오 | Reviewer B용 |
| labeling 결과 | `data/ssot_experiment_v2/*/labeling_*.csv` | 아니오 | A/B 독립 |
| adjudication 결과 | `data/ssot_experiment_v2/*/adjudication.csv` | 아니오 | disagreement 해결 |
| regression 결과 | `data/ssot_experiment_v2/*/regression_result.json` | 아니오 | paired diff |
| checker 코드 해시 | `data/ssot_experiment_v2/*/checker_source_hash.csv` | 아니오 | rule_version 고정 |
| **Pilot 결과 문서** | `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PILOT.md` | 네 (실행 후) | Phase 1 결과 |
| **Final 결과 문서** | `docs/DASHBOARD_SSOT_EXPERIMENT_V2_RESULT.md` | 네 (실행 후) | Phase 2 결과 |
| **이 계획 문서** | `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` | 네 (지금) | QA 완료 |

---

## 10A. Pilot execution artifacts — LEGACY_QUARANTINED_V1

> ⚠️ **pilot-001 artifacts are LEGACY_QUARANTINED_V1.** No delete/modify/move/copy/reuse.
> Fresh execution: pilot-v2.2 with new identifiers (§14 in CORRECTED_ALLOCATION.md).
> Forensic closure: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md`

### Stage 1 — DB copy + snapshot: REUSE_REVOKED

| 항목 | 값 |
|---|---|
| source_db | `ops_dashboard/ops.db` (4,247,552 bytes) |
| backup_method | sqlite3.backup API (online) |
| copy_sha256 | `8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac` |
| as_of | `2026-08-20T18:35:48.846796` |
| expected (preflight) | total=1936, fail=412, pass=1333, eligible=1745 |
| actual (snapshot) | total=1936, fail=412, pass=1333, eligible=1745 |
| delta | 0 (모든 카운트 정확히 일치) |
| row_id NULL | 0건 |
| row_id 중복 | 0건 |
| 판정 | **PROVISIONALLY_VALID** — 재조회/재생성 없이 보존 |

### Stage 1 reuse — REUSE_REVOKED (forensic: snapshot_hash unresolvable)

Stage 1의 기존 immutable manifest와 snapshot은 **수정하지 않는다**.
대신 별도 `reconciliation_manifest.json`을 설계하여 plan hash 변경과 재사용 근거를 기록한다.

**reconciliation_manifest.json 스키마:**

```json
{
  "reconciliation_id": "recon-2026-08-20-001",
  "reconciled_at": "2026-08-20THH:MM:SSZ",
  "original_plan_hash": "0c2d6fdb1ab254670b5fd29f56c839ef7a3d0bfe1b9f0b746ab89199977d2c0c",
  "reconciled_plan_hash": "18579234b18789da4971a2d5f93dd4a5ffb0ad832365f7678712dfe19f40bc71",
  "snapshot_hash": "8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac",
  "stage0_manifest_hash": "(Stage0_MANIFEST.json의 SHA-256)",
  "reconciliation_reason": "Plan 문서의 sampling/evidence governance 정정 — Stage 1 DB copy/snapshot/schema/row contents에 영향 없음",
  "stage1_reuse_decision": "REUSE_APPROVED — snapshot 불변, manifest 불변",
  "approved_by": "(사용자 승인 시 기록)",
  "approved_at": "(승인 시각)"
}
```

**저장 위치**: `/tmp/ssot_v2_pilot/reconciliation_manifest.json` (Stage 0 worktree 내)
**커밋 대상**: Plan 문서와 함께 docs-only commit에 포함

### Semantic diff — 두 계획 버전 간 변경 범위

| 변경 영역 | original (0c2d6fdb) | reconciled (18579234) | Stage 1 영향 |
|---|---|---|---|
| **sampling governance** | binomial CP 13.4% (FPC 혼용) | binomial CP 18.1% + FPC 별도 참고 | ❌ 영향 없음 — snapshot은 sampling 이전 단계 |
| **evidence governance** | detail-only 109건 = "evidence available" | detail-only 109건 = checker contract별 재분류 | ❌ 영향 없음 — evidence 분류는 labeling 단계 |
| **κ reporting** | aggregate만 보고 | per-strata + aggregate + N/A rule | ❌ 영향 없음 — labeling 이후 계산 |
| **unweighted naming** | "operational FN bound" 혼용 | "unweighted validation-sample bound" 명명 | ❌ 영향 없음 — 해석 규칙 변경 |
| **oversampling 가정** | 보수적 가정 암묵 | 입증 없이 사용 금지 명시 | ❌ 영향 없음 — 해석 규칙 변경 |
| **design-aware 추정** | 미정의 | 요구사항5개 정의 (미적용) | ❌ 영향 없음 — 추정 미수행 |
| **manifest fields** | 8필드 | 14필드 (experiment_phase 등6 추가) | ❌ 영향 없음 — 기존 manifest 수정 없음 |
| **population query** | 동일 | 동일 | ❌ 영향 없음 |
| **DB copy** | 동일 | 동일 | ❌ 영향 없음 |
| **snapshot schema** | 동일 | 동일 | ❌ 영향 없음 |
| **row contents** | 동일 | 동일 | ❌ 영향 없음 |
| **snapshot hash** | 동일 | 동일 | ❌ 영향 없음 |

**결론**: 변경은 전부 sampling/evidence governance 해석 규칙에 해당하며,
population query·DB copy·snapshot schema·row contents·snapshot hash에는 영향 없음.
Stage 1 재사용: **PROVISIONALLY_VALID → REUSE_APPROVED**.

### Stage 2 — sampling: LEGACY_QUARANTINED_V1

> ⚠️ pilot-001 Stage 2 artifacts are LEGACY_QUARANTINED_V1. See forensic closure.

**Stage 2 재실행 전 동결된 완전한 allocation matrix:**

| check_name | risk_tier | planned_n | available_N | census_n | shortfall_n | reallocated_from | reallocated_to | final_n | notes |
|---|---|---|---|---|---|---|---|---|---|
| c08_live_file_mismatch | HIGH | 15 | 85 | — | 0 | — | — | 15 | 원래 계획 충족 |
| FM-MISSINGKEYS | HIGH | 12 | 71 | — | 0 | — | — | 12 | 원래 계획 충족 |
| **c06_mtime_deploy** | **HIGH** | **8** | **2** | **2** | **6** | — | — | **2** | **STRUCTURAL_SHORTFALL** — census, diagnostic only |
| **c01_curve_quote** | **HIGH** | **8** | **4** | **4** | **4** | — | — | **4** | **STRUCTURAL_SHORTFALL** — census, diagnostic only |
| standard_compliance | HIGH | 8 | 40 | — | 0 | — | — | 8 | 원래 계획 충족 |
| THUMBNAIL-01 | HIGH | 6 | 36 | — | 0 | — | — | 6 | 원래 계획 충족 |
| FM-DRAFT | MEDIUM | 5 | 30 | — | 0 | — | — | 5 | 원래 계획 충족 |
| content_quality | MEDIUM | 5 | 23 | — | 0 | — | — | 5 | 원래 계획 충족 |
| semantic | MEDIUM | 5 | 22 | — | 0 | — | — | 5 | 원래 계획 충족 |
| c03_fm_key_leak | MEDIUM | 4 | 20 | — | 0 | — | — | 4 | 원래 계획 충족 |
| freshness | LOW | 3 | 14 | — | 0 | — | — | 3 | 원래 계획 충족 |
| data_stock | LOW | 3 | 14 | — | 0 | — | — | 3 | 원래 계획 충족 |
| R2-01 | LOW | 3 | 8 | — | 0 | — | — | 3 | 원래 계획 충족 |
| maintenance_checklist | LOW | 2 | 6 | — | 0 | — | — | 2 | 원래 계획 충족 |
| c04_prompt_leak | LOW | 2 | 5 | — | 0 | — | — | 2 | 원래 계획 충족 |
| FM-FEATUREIMAGE | LOW | 2 | 4 | — | 0 | — | — | 2 | 원래 계획 충족 |
| crosslink_consistency | LOW | 2 | 4 | — | 0 | — | — | 2 | 원래 계획 충족 |
| rap_leak | LOW | 1 | 2 | — | 0 | — | — | 1 | 원래 계획 충족 |
| render_health | LOW | 1 | 2 | — | 0 | — | — | 1 | 원래 계획 충족 |
| R01 | LOW | 1 | 1 | — | 0 | — | — | 1 | 원래 계획 충족 |
| R06 | LOW | 1 | 1 | — | 0 | — | — | 1 | 원래 계획 충족 |
| **합계** | — | **90** | — | **6** | **10** | — | — | **87** | fail=87 (부족 3건) |

> c06(2/8)와 c01(4/8)의 부족분10건은 재배분되지 않았다 — 재배분 규칙에 의해 자동 해소되지 않는 STRUCTURAL_SHORTFALL.

**Stage 2 재실행 시 allocation 재배분 규칙 (동결):**

1. **checker 순서**: risk_tier 내에서 planned_n 내림차순 → 동률 시 check_name 알파벳순
2. **동률 처리**: planned_n이 동일하면 available_N이 많은 checker 우선 (표본 확보 용이성)
3. **최대 allocation**: 단일 checker에 최대15표본 (과도한 특정 checker 편중 방지)
4. **재배분 종료 조건**:
   - 잔여 fail pool = 0이면 즉시 종료
   - 모든 checker의 census_n 합이 fail 목표(90)에 도달하면 종료
   - 남은 fail이 재배분 대상 checker의 minimum(≥3) 미만이면 종료
5. **c06/c01**: 전수 선택(census)하지만 **original planned_n을 충족한 것으로 표시하지 않음**
   - actual_n = available_N (census)
   - planned_n 미충족 → STRUCTURAL_SHORTFALL 유지
   - diagnostic only — operational gate에서 제외
6. **재배분 불가 시**: 남은 fail을 고위험 checker의 minimum allocation으로 배분하지 않음 — 대신 총 fail 감소(90→87 등)로 기록

**판정: STRATIFIED_COVERAGE_DEGRADED**
- 전체 fail 87/90 달성했으나 checker별 최소 allocation 미충족(c06 2/8, c01 4/8)
- PASS_WITH_DELTA로 숨기지 않고 투명하게 보고
- Stage 3 산출물은 표본 설계 변경으로 QUARANTINED

### Stage 3 — Evidence fetch + blind packet: LEGACY_QUARANTINED_V1

> ⚠️ pilot-001 Stage 3 artifacts are LEGACY_QUARANTINED_V1. See forensic closure.

| 항목 | 값 |
|---|---|
| 총 패킷 | 133건 (87 fail + 46 pass) |
| blind_packet_version | v3.0 |
| PII 발견 | 0건 |
| redaction | 0건 |
| 판정 | **QUARANTINED_ARTIFACT** — Stage 2 설계 변경으로 labeling 입력 사용 불가 |

**기존 Stage 3 산출물 보존 규칙:**
- 133건 blind packet과 manifest는 **불변 보존** (수정·삭제·재사용 금지)
- 저장 위치: `/tmp/ssot_v2_pilot/blind_packets/` (Stage 0 worktree)
- **새 실행에는 새로운 packet_version 사용** (v4.0+)
- 새 packet은 parent_packet_hash를 기록하여 계보 추적

**detail-only 109건 evidence 재분류 — checker contract별:**

기존 "detail-only evidence = evidence available"로 간주하지 않는다.
대신 각 checker의 contract(무엇을 검증하는지)에 따라 authoritative/auxiliary/insufficient로 재분류한다.

| checker | contract (무엇을 검증) | detail에 포함된 정보 | evidence 분류 | 근거 |
|---|---|---|---|---|
| c08_live_file_mismatch | 실제 파일 vs 커밋 불일치 | 파일 경로, 커밋 SHA, 불일치 설명 | **authoritative** | detail이 직접 증거를 포함 — URL 불필요 |
| c06_mtime_deploy | mtime vs deploy 시점 | 파일 경로, mtime, deploy timestamp | **authoritative** | detail이 직접 증거를 포함 |
| c01_curve_quote | 인용 곡률 검증 | 인용 위치, 곡률 점수, 기준값 | **authoritative** | detail이 직접 증거를 포함 |
| standard_compliance | 표준 컴플라이언스 | 위반 항목, 기준값, 측정값 | **authoritative** | detail이 직접 증거를 포함 |
| THUMBNAIL-01 | 썸네일 깨짐 | 이미지 URL, HTTP 상태, 경로 | **authoritative** | detail이 직접 증거를 포함 |
| FM-DRAFT | 프론트매터 draft 상태 | YAML 키, draft 값, 파일 경로 | **authoritative** | detail이 직접 증거를 포함 |
| content_quality | 콘텐츠 품질 | 품질 점수, 위반 항목 | **auxiliary** | detail이 점수만 제공, 원문 검증 불가 |
| semantic | 의미론적 검증 | 의미 유사도, 기준값 | **auxiliary** | detail이 점수만 제공, 맥락 검증 불가 |
| c03_fm_key_leak | 프론트매터 키 누출 | 노출된 키, 파일 경로 | **authoritative** | detail이 직접 증거를 포함 |
| freshness | 콘텐츠 신선도 | 날짜 차이, 기준값 | **auxiliary** | detail이 점수만 제공 |
| data_stock | 데이터 재고 | 재고 점수, 기준값 | **auxiliary** | detail이 점수만 제공 |
| R2-01 | R2 이미지 검증 | 이미지 URL, HTTP 상태 | **authoritative** | detail이 직접 증거를 포함 |
| maintenance_checklist | 유지보수 체크리스트 | 체크 항목, 상태 | **auxiliary** | detail이 상태만 제공 |
| c04_prompt_leak | 프롬프트 누출 | 노출된 텍스트, 위치 | **authoritative** | detail이 직접 증거를 포함 |
| FM-FEATUREIMAGE | featureimage 검증 | 이미지 URL, 경로, 상태 | **authoritative** | detail이 직접 증거를 포함 |
| crosslink_consistency | 교차 링크 일관성 | 링크 쌍, 깨진 링크 | **authoritative** | detail이 직접 증거를 포함 |
| rap_leak | 부동산 정보 누출 | 노출된 정보, 위치 | **authoritative** | detail이 직접 증거를 포함 |
| render_health | 렌더링 상태 | 렌더링 결과, 에러 | **auxiliary** | detail이 상태만 제공 |
| R01 | 규칙01 위반 | 위반 항목, 위치 | **authoritative** | detail이 직접 증거를 포함 |
| R06 | 규칙06 위반 | 위반 항목, 위치 | **authoritative** | detail이 직접 증거를 포함 |

**evidence 분류 요약 (133건 기준):**

| 분류 | 건수 | 비율 | 처리 |
|---|---|---|---|
| **authoritative** (URL or detail이 직접 증거) | ~95 | ~71% | 리뷰어가 독립 검증 가능 |
| **auxiliary** (detail이 점수/상태만 제공) | ~25 | ~19% | 리뷰어가 점수만 확인, 원문 검증 불가 → UNC/NOT_EVALUATED 후보 |
| **insufficient** (detail도 불충분) | ~13 | ~10% | 리뷰어가 판정 불가 → **UNC/NOT_EVALUATED 후보** |
| **합계** | **133** | **100%** | — |

- **insufficient**: evidence_url 빈 값 + detail이 검증 불가능한 정보만 포함 → UNC/NOT_EVALUATED 판정 예상
- **auxiliary**: detail이 점수를 제공하나 원문 검증 불가 → 리뷰어가 점수만 신뢰하는 판정
- **authoritative**: detail이 직접 증거를 포함 (URL 불필요) — 리뷰어가 독립 검증 가능

---

## 잔존 위험

1. 이 문서는 **실행 계획** — 실제 측정은 수행되지 않았음. 모든 "예정" 수치는 설계 기반.
2. Phase 1 Pilot pass n=46에서 zero-FN 시 FN_upper=7.7% — **operational threshold 5% 미달**. Phase 2에서 n≥150 확대 필요.但如果 Phase 1에서 FN>0 발견 시 Phase 2 표본 설계 재조정 필요.
3. Phase 2 pass ≥150개 확보를 위해 checker별 passPopulation이 충분한지 사전 확인 필요 (c06 pass 31, c01 pass 34 — 한 checker에서 15개 추출 시 48%/44% 비율).
4. 표본 90+~115fail의 대표성은 checker별 fail 분포에 의존 — 소수 checker(R01, R06, rap_leak)는 표본 1~2개로 불충분.
5. Reviewer B(사람)의 참여 가용성 — blind labeling에 수 시간 소요 예상.
6. c08 패치의 `_parse_frontmatter` YAML 전환이 snapshot_clone에서 어떻게 동작하는지는 확인되지 않음 (pyyaml 버전 의존).
7. stale-evidence rate의 STALE_THRESHOLD는 checker별 상이 — 임의 기준값 사용.
8. Adjudicator가 A/B와 동일인이면 독립성 저하 가능 — 가능한 별도 제3자 사용 권장.
9. Clopper-Pexact 95% CI는 보수적 — FN_rate point estimate와의 괴리 가능.
10. **Stage 2 STRATIFIED_COVERAGE_DEGRADED**: c06(2/8)와 c01(4/8)의 구조적 부족으로 해당 checker 결과는 diagnostic only. operational gate에서 제외.
11. **Stage 3 QUARANTINED**: Stage 2 표본 설계 변경으로 기존 133개 blind packet 재사용 불가. Stage 2 재실행 후 Stage 3 재생성 필요.
12. **evidence sufficiency**: 109/133건(82%)이 detail-only evidence — 독립 URL 검증 불가. abstention 비율 상승 예상.

---

## Hash Lineage

| 항목 | SHA-256 | 시점 |
|---|---|---|
| **RECONCILED_CANDIDATE_HASH** (Plan) | `18579234b18789da4971a2d5f93dd4a5ffb0ad832365f7678712dfe19f40bc71` | 2026-08-20 (본 문서 — 정정 후) |
| original_plan_hash (정정 전) | `0c2d6fdb1ab254670b5fd29f56c839ef7a3d0bfe1b9f0b746ab89199977d2c0c` | 2026-08-20 (Stage 0에서 사용) |
| Pilot Packet hash | `7a920603ae696aa8864a26bd34e80fcb2563a84e3bfc05cbd69693c034c64893` | 2026-08-20 |
| reconciliation_manifest hash | `(reconciliation_manifest.json 생성 시 계산)` | — |
| Stage0 manifest hash | `(Stage0_MANIFEST.json SHA-256)` | 2026-08-20 |
| DB copy_sha256 | `8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac` | 2026-08-20 |
| sampling_frame_hash | `1f16e8d225cd3ebb019233c15cf27d4781bca9b7895c326fce37f5d0fe6bea42` | 2026-08-20 |
| sample_hash (Stage 2) | `b69e29f71643654404fb79d92396704fe4801be652ae41578791eb12722fe322` | 2026-08-20 |
| blind_packet_manifest_hash (Stage 3) | `21feb11203306c5a522e137b57d0e4429664f7da7c16fe778e514fbe01617457` | 2026-08-20 |
| 이전 1067행 해시 | **UNKNOWN** (git 커밋 없음, authority 상실) | — |

**canonical commit 후보 (아직 미실행) — path-scoped docs-only:**
```
# 커밋 대상: 3개 문서만 (Plan + Packet + reconciliation)
git add docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md
git add docs/SSOT_V2_PILOT_AUTHORIZATION_PACKET.md
git add docs/SSOT_V2_RECONCILIATION_RECORD.md
git commit -m "SSOT v2: reconciled candidate plan + pilot packet + reconciliation record (docs-only)"
```

**커밋에 포함하지 않는 것:**
- 기존 checker patch (content_integrity.py, content_quality.py, frontmatter.py, standard.py)
- test 파일 (test_checker_patches_20260820.py)
- ops.db 또는 ops_snapshot.db
- /tmp/ssot_v2_pilot/ 내 실행 산출물 (manifest, sample, blind_packets 등)

커밋은 사용자 승인 후에만 실행. 커밋 후에야 Plan 문서의 hash는 canonical로 격상.
