# SSOT Experiment v2 — Pilot Authorization Packet (Reconciled Revision)

> **Status**: LEGACY_RUN_INVALID_FOR_LABELING — FRESH_RERUN_REQUIRED
> **Previous**: 461 lines, FINAL REVISION (SUPERSEDED)
> **This revision**: Reconciled with plan hash 18579234... — Stage 1 reuse REVOKED, new allocation policy, Stage 2-3 LEGACY_QUARANTINED_V1
> **QA Plan**: `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` — LEGACY_RUN_INVALID_FOR_LABELING
> **Forensic closure**: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` — LEGACY_QUARANTINED_V1

---

## §0 문서 동기화 상태

| 항목 | 값 | 검증 |
|---|---|---|
| QA Plan 파일 | `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` | ~1300 lines |
| QA Plan 상태 | **LEGACY_RUN_INVALID_FOR_LABELING** — FRESH_RERUN_REQUIRED | |
| QA Plan RECONCILED_CANDIDATE_HASH | `18579234b18789da4971a2d5f93dd4a5ffb0ad832365f7678712dfe19f40bc71` | |
| QA Plan original_plan_hash | `0c2d6fdb1ab254670b5fd29f56c839ef7a3d0bfe1b9f0b746ab89199977d2c0c` | Stage 0에서 사용 |
| Pilot Packet hash (이 문서) | `(SHA-256: 기록 시 계산)` | |
| **상호 hash 관계** | Plan의 RECONCILED_CANDIDATE_HASH가 Packet의 original_plan_hash를 참조; Packet hash가 Plan의 hash lineage에 기록 | |
| HEAD commit | `ce9739922` | git log -1 |
| 기존 dirty worktree | 4 files (+164/-32) + 1 untracked test | git status, git diff --binary |
| ops.db 경로 | `ops_dashboard/ops.db` | NOT `data/ops.db` |
| **Stage 1 재사용** | **REUSE_REVOKED** — snapshot_hash unresolvable, hash chain broken. Forensic: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` | |
| **Stage 2-3 quarantine** | **LEGACY_QUARANTINED_V1** — 7 artifacts preserved, no delete/modify/move/copy/reuse. New execution: pilot-v2.2 with new identifiers | |
| **pilot-v2.2 chain contract** | Designed in `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` §14–§18 | |

---

## §1 Population 정의

### 1.1 total rows vs eligible population

| 항목 | 값 | 근거 |
|---|---|---|
| `database_total_rows` | **1,936** (expected_preflight_count) | `SELECT COUNT(*) FROM check_results` (packet 작성 시 관측) |
| `excluded_other_status` | **191** (expected_preflight_count) | total − eligible = 1936 − 1745 |
| `eligible_population_rows` | **1,745** (expected_preflight_count) | fail + pass = 412 + 1333 |
| `fail` (check_result='fail') | **412** (expected_preflight_count) | `SELECT COUNT(*) FROM check_results WHERE check_result='fail'` |
| `pass` (check_result='pass') | **1,333** (expected_preflight_count) | `SELECT COUNT(*) FROM check_results WHERE check_result='pass'` |

> **중요**: 위 값은 packet 작성 시(2026-08-20) 관측한 **expected_preflight_count**이다.
> 실제 실행 시 고정된 DB copy에서 산출한 값만 **snapshot_actual_count**로 manifest에 확정된다.
> 불일치 시 auto-fail이 아니라 provenance delta를 기록하고 승인된 허용 조건에 따라 중단/속행을 판단한다.

### 1.2 합계 검증 (expected)

```
412 (fail) + 1,333 (pass) = 1,745 (eligible)
1,745 (eligible) + 191 (excluded) = 1,936 (total) ✓
```

### 1.3 excluded_other_status 기준

제외 대상: `check_result`가 `'fail'` 또는 `'pass'`가 아닌 모든 행 (예: `'pending'`, `'skipped'`, `NULL` 등).

### 1.4 불일치 시 처리 (proof provenance delta)

| 시나리오 | 처리 |
|---|---|
| snapshot_actual == expected_preflight | 정상 진행 |
| snapshot_actual ≠ expected_preflight (차이 ≤5%) | provenance delta 기록, 로그 후 승인된 허용 조건에 따라 속행 |
| snapshot_actual ≠ expected_preflight (차이 >5%) | provenance delta 기록, **중단** — 사용자 승인 후 재개 |

---

## §2 Snapshot 정의 — SQLite Online Backup

### 2.1 스냅샷 추출 방법 (단일 고정)

**scheduler는 중단하지 않는다.** 스냅샷 추출 방법은 **SQLite online backup API**로 단일 고정한다.

```
방법: sqlite3 online backup API (sqlite3_backup_init/step/finish)
       또는 동등한 read-only consistent-copy (VACUUM INTO는 별도 선택지 — §2.4 참조)
```

**핵심 원칙:**
- 원본 ops.db를 수정하지 않는 read-only consistent-copy 생성
- copy 생성 후 **모든 SELECT는 고정된 copy에서만** 수행
- copy 생성 전·후에 source DB의 mtime/size가 변하지 않았음을 검증

### 2.2 copy 메타데이터 기록

copy 생성 시 아래 필드를 manifest에 기록:

| 필드 | 설명 |
|---|---|
| `source_db_identity` | `ops_dashboard/ops.db` (경로) |
| `source_db_size_bytes` | copy 생성 전 source DB 크기 (bytes) |
| `source_db_mtime` | copy 생성 전 source DB 최종 수정 시각 (ISO 8601) |
| `copy_started_at` | copy 작업 시작 시각 |
| `copy_completed_at` | copy 작업 완료 시각 |
| `copy_path` | 고정된 copy 파일 경로 (이후 모든 SELECT 대상) |
| `copy_sha256` | copy 완료 후 copy 파일의 SHA-256 해시 |

### 2.3 copy 검증 체크리스트

copy 생성 후, copy에서 쿼리하기 전:

- [ ] `source_db_size_bytes` = copy 직전 source DB 크기와 일치
- [ ] `source_db_mtime` = copy 직전 source DB mtime과 일치
- [ ] copy 파일이 존재하고 0 bytes가 아님
- [ ] copy에서 `SELECT COUNT(*) FROM check_results` > 0

### 2.4 VACUUM INTO 선택 시 별도 검증 (§2.1과 혼용 금지)

VACUUM INTO를 선택하는 경우, 아래 조건을 추가 충족:

| 검증 항목 | 기준 |
|---|---|
| source DB 변경 없음 | VACUUM INTO 전·후 source DB size/mtime 동일 |
| concurrent writer 차단 | VACUUM INTO 중 다른 writer가 ops.db에 쓰지 않음 (file lock 또는 scheduler 일시 중단) |
| partial file 처리 | VACUUM INTO 실패 시 생성된 파일을 삭제하고 재시도 — 불완전한 copy 사용 금지 |
| lock 해제 | VACUUM INTO 완료 후 lock 해제 확인 |

> **금지**: VACUUM INTO와 read transaction을 혼용하여 동일 실험에서 둘 다 사용하는 것.

### 2.5 as_of 산출

`as_of`는 고정된 copy에서 산출:
```sql
-- copy_path에서 (원본 아님)
SELECT MAX(checked_at) FROM check_results;
-- → as_of = 이 값
```

### 2.6 manifest 확장 필드

| 필드 | 값 | 설명 |
|---|---|---|
| `as_of` | `(copy 내 MAX(checked_at))` | 고정 copy에서 산출 |
| `source_db_identity` | `ops_dashboard/ops.db` | §2.2 참조 |
| `source_db_size_bytes` | `(copy 전 source DB 크기)` | §2.2 참조 |
| `source_db_mtime` | `(copy 전 source DB mtime)` | §2.2 참조 |
| `copy_started_at` | `(copy 시작 시각)` | §2.2 참조 |
| `copy_completed_at` | `(copy 완료 시각)` | §2.2 참조 |
| `copy_sha256` | `(copy 파일 SHA-256)` | §2.2 참조 |
| `schema_version` | `check_results v1` | PRAGMA table_info |
| `extractor_source_version` | `ce9739922-unpatched` | §3 참조 |
| `result_producer_version` | `(실행 시 결정)` | §3 참조 |
| `snapshot_fail_count` | `(copy에서 산출)` | snapshot_actual |
| `snapshot_pass_count` | `(copy에서 산출)` | snapshot_actual |
| `snapshot_eligible_count` | `(copy에서 산출)` | snapshot_actual |
| `snapshot_total_count` | `(copy에서 산출)` | snapshot_actual |
| `snapshot_fail_sha256` | `(fail CSV 해시)` | SHA-256 |
| `snapshot_pass_sha256` | `(pass CSV 해시)` | SHA-256 |
| `experiment_phase` | `pilot` | Pilot 실험 단계 |
| `population_query` | `(SQL 원문)` | §4 참조 |
| `population_query_sha256` | `(canonical query 해시)` | §4 참조 |
| `sampling_seed` | `(deterministic seed)` | §5 참조 |
| `sampling_frame_hash` | `(eligible population CSV 해시)` | §5 참조 |
| `confidence_method` | aggregate=two-sided 95% CP / per-stratum=one-sided 95% CP | §6 참조 |
| `review_packet_version` | `v3.0` | 본 packet 버전 |
| `plan_document_hash` | `(QA plan SHA-256)` | 승인된 QA plan의 해시 |

---

## §3 Rule Version — 분리 (④)

| 필드 | 값 | 설명 |
|---|---|---|
| `extractor_source_version` | **`ce9739922-unpatched`** | ce9739922 커밋의 checker 코드 (patch 적용 전). data 추출에 사용 |
| `result_producer_version` | **`(실행 시 결정)`** | checker가 DB 행을 생성할 때 사용한 버전. **입증 불가 시 `UNKNOWN_OR_MIXED`** |

**重要**: `extractor_source_version`은 현재 Pilot에서 data를 추출하는 checker 코드의 버전이다.
그러나 DB의 각 행이 ce9739922 버전의 checker에 의해 생성되었음을 **입증할 수 없다** — 이전 버전의 checker가 생성했을 수 있다.

따라서 `result_producer_version`:
- ce9739922 이전 버전의 checker가 행을 생성했을 수 있으면 → `UNKNOWN_OR_MIXED`
- ce9739922 이후 patched 버전이 행을 생성했을 수 있으면 → `UNKNOWN_OR_MIXED`
- ce9739922-unpatched만 사용되었다고 확신할 수 있는 경우에만 → `ce9739922-unpatched`

> **금지**: `extractor_source_version`을 `result_producer_version`과 동일하게 기록하여
> "ce9739922가 기존 status의 생성 버전이다"라고 주장하는 것.

---

## §4 Population Query (canonical 규칙)

### 4.1 Population query (copy 내)

```sql
-- fail 모집단
SELECT * FROM check_results WHERE check_result='fail';

-- pass 모집단
SELECT * FROM check_results WHERE check_result='pass';
```

### 4.2 canonical query 정규화 규칙

`population_query_sha256`은 아래 규칙으로 정규화한 SQL에서 계산:

1. **인코딩**: UTF-8
2. **줄바꿈**: LF (CRLF → LF 변환)
3. **공백 정규화**: 연속 공백/탭 → 단일 공백, 앞뒤 공백 제거
4. **대소문자**: SQL 키워드는 대문자로 통일 (`SELECT`, `FROM`, `WHERE`)
5. **해시**: 정규화된 문자열의 SHA-256

---

## §5 Sampling (SHA-256 기반 정렬, PRNG 고정 대체)

### 5.1 Sampling seed (non-null deterministic)

```python
import hashlib

# snapshot hash에서 파생
snapshot_hash = sha256(population_query_sha256 + as_of + extractor_source_version)
experiment_id = "SSOT_V2_PILOT_" + as_of

# non-null deterministic seed
sampling_seed = int(hashlib.sha256(
    (snapshot_hash + experiment_id).encode()
).hexdigest()[:8], 16)  # 8 hex digits → integer
```

### 5.2 표본 선택 방법 — SHA-256 기반 정렬 (권장)

PRNG 의존성을 제거하고 재현성을 높이기 위해 **SHA-256(seed || stable_row_id) 기반 정렬**을 사용:

```python
import hashlib

def compute_selection_score(row_id: str, seed: int) -> int:
    """SHA-256(seed || row_id) → 정수. 재현 가능한 deterministic score."""
    h = hashlib.sha256(f"{seed}||{row_id}".encode()).hexdigest()
    return int(h[:16], 16)  # 16 hex digits → 64-bit integer

# 각 행에 score 부여 후 score 오름차순 정렬
# 상위 n개 선택 (stratified: checker별 fail/pass 그룹에서 독립 적용)
```

### 5.3 동률 처리 규칙 (tie-breaking)

동일한 selection score가 나오는 경우 (SHA-256 충돌로 극히 드묾):
1. `stable_row_id` 오름차순으로 정렬하여 우선순위 결정
2. `stable_row_id`도 동일하면 → 해당 행은 **sampling에서 제외** (중복 row_id — §7에서 사전 검증)

### 5.4 PRNG·알고리즘·정렬·중복·배분 고정 (SHA-256 기반 대체 시)

| 항목 | 고정값 |
|---|---|
| Selection method | SHA-256(seed \|\| stable_row_id) 기반 정렬 (§5.2) |
| Tie-breaking | stable_row_id 오름차순 (§5.3) |
| Sampling algorithm | Stratified random sampling (checker별 fail/pass 비율에 비례) |
| 정렬 기준 | selection score 오름차순 (deterministic) |
| 중복 처리 | 무복원 — 동일 row_id 중복 선택 금지 |
| Checker별 allocation | QA plan §3.3 표준표에 따라 checker별 n 고정 |
| Python/runtime version | 실행 시 기록 — PRNG 미사용 시 불필요 |

> **대안**: PRNG를 사용하는 경우 `random.Random(seed)` (Mersenne Twister)를 고정하고
> Python version, random module version을 manifest에 기록한다.
> SHA-256 기반 정렬이 PRNG보다 재현성이 높으므로 권장.

### 5.5 sampling_frame_hash

```
sampling_frame_hash = SHA-256 of eligible population CSV
  = fail CSV + pass CSV (copy에서 추출, filtering 전)
  = SHA-256( fail_rows ++ pass_rows )
```

**표본 추출 전** copy에서 eligible population/frame CSV를 먼저 생성하고 그 해시를 기록.

### 5.6 sample_hash (별도 기록)

```
sample_hash = SHA-256 of final sample CSV
  = stratified sampling 후 실제로 라벨링할 행들의 CSV 해시
```

---

## §6 Confidence Method (분리)

| 메트릭 | 방법 | 명칭 |
|---|---|---|
| **Aggregate FN upper bound** | Two-sided 95% Clopper–Pearson | unweighted validation-sample bound |
| **Per-stratum FN gate** | One-sided 95% Clopper–Pearson | checker별 zero-FN bound |
| **κ CI** | Fleiss-Cohen approximate SE | (보조 메트릭) |

**구분**: aggregate bound는 operational FN rate로 해석하지 않음 (QA plan §5.2 참조).

---

## §7 row_id 검증 (⑤)

### 7.1 사전 검증 (snapshot 전)

row_id가 sampling에 사용되기 전, copy에서 아래 검증을 수행:

```sql
-- 1. not null 검증
SELECT COUNT(*) FROM check_results WHERE row_id IS NULL;
-- → 0이 아니면 중단

-- 2. 유니크 검증
SELECT row_id, COUNT(*) as cnt FROM check_results GROUP BY row_id HAVING cnt > 1;
-- → 결과가 있으면 중단

-- 3. stable 여부 (변경 금지)
-- row_id는 DB 행 생성 시 할당된 고유 식별자로, 이후 변경되지 않음
```

### 7.2 검증 결과

| 검증 | 기대값 | 실제값 (copy에서) | 결과 |
|---|---|---|---|
| NULL row_id | 0 | `(실행 시 기록)` | PASS/FAIL → FAIL 시 중단 |
| 중복 row_id | 0 | `(실행 시 기록)` | PASS/FAIL → FAIL 시 중단 |
| row_id stable | TRUE | `(실행 시 기록)` | PASS |

**중복 또는 결측이 하나라도 있으면 sampling 전에 중단한다.**

---

## §8 Evidence Fetch (post-snapshot observation)

### 8.1 증거 유형

**post-snapshot observation** — 스냅샷 이후 관찰. historical snapshot evidence가 아님.

### 8.2 기록 필드

| 필드 | 설명 |
|---|---|
| `fetched_at` | evidence fetch 시각 (ISO 8601) |
| `http_status` | HTTP 응답 상태 코드 (예: 200, 404, 503) |
| `final_url` | redirect 후 최종 URL |
| `content_hash` | 응답 본문 SHA-256 |
| `freshness_verdict` | STALE/OK/FRESH (checker별 STALE_THRESHOLD 기준) |

### 8.3 제약 조건

| 제약 | 기준 |
|---|---|
| domain allowlist | rotcha.kr, informationhot.kr, aikorea24.kr 계열만 |
| redirect 제한 | 최대 3회 following — 초과 시 abort |
| 응답 크기 제한 | 최대 10MB — 초과 시 truncation + 경고 |
| secret/PII redaction | Blind packet 생성 전 검사 (§8.4 참조) |

### 8.4 PII 검사

- **blind packet 생성 전**에 detail/HTML/JSON에서 secret·email·token·query parameter 검사 수행
- "PII가 없다"고 단정하지 않고 **검사 후 발견 시 redaction** 수행
- 검사 방법: regex 패턴 매칭 (`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`, `sk-[a-zA-Z0-9]{20,}`, `Bearer [a-zA-Z0-9._-]+`, `api_key=`, `token=` 등)
- redaction 기록: `redacted_fields: [list of field names]`

### 8.5 접근권과 보존 경계

| 항목 | 정의 |
|---|---|
| raw evidence 접근권 | Adjudicator만 접근 — Reviewer A/B는 blind packet만 수신 |
| raw evidence 보존 | evidence fetch 후 `raw_evidence/` 디렉터리에 저장, Pilot 종료 후 30일 보존 |
| blind packet 보존 | `blind_packets/` 디렉터리 — labeling 완료 후 보존 |
| PII 포함 여부 | 확정 불가 — "PII가 없다"고 단정하지 않음, 검사 후 redaction으로 대응 |

---

## §9 κ 규칙

### 9.1 N/A 조건

κ=N/A는 **1−P_e=0인 경우**:

```
P_e = Σ_k (A_k 비율 × B_k 비율)

1−P_e = 0 이 되는 경우:
  - 모든 행에서 A와 B가 동일한 단일 범주로만 판정
  - 예: 모든 행을 TP로 판정 → P_e=1.0 → κ = (P_o−1)/0 = 정의 불가
```

**κ=N/A 보고 시**:
- raw agreement = 100% (동일 범주 고정)
- 원인 기록: "1−P_e=0 — Reviewer X가 모든 행을 동일 범주로 판정"
- per-strata와 aggregate 모두에 적용

---

## §10 Pilot 범위

### 10.1 포함 (Pilot scope)

| 단계 | 내용 |
|---|---|
| Step 1 | DB copy + 스냅샷 생성 |
| Step 2 | 표본 추출 (stratified sampling) |
| Step 3 | Evidence fetch + blind packet 생성 |
| Step 4 | A/B labeling (Reviewer A + B 독립) |
| Step 5 | Adjudication + κ 계산 |
| Step 6 | Pilot result (metrics, confusion matrix, per-strata) |

### 10.2 제외 (NOT in Pilot)

| 항목 | 상태 |
|---|---|
| Paired Regression | **NOT_APPROVED** — Final phase에서만 |
| Final Validation | **NOT_APPROVED** — Phase 2에서만 |
| patched RecheckAll | **NOT_APPROVED** — Final phase에서만 |

---

## §11 Stage Gate — Stage별 승인 분리 (⑧)

### 11.1 Stage 정의

실행은 6개 Stage로 분리되며, 각 Stage 완료 시 산출물 해시 검증 후 다음 Stage로 진행:

| Stage | 내용 | 산출물 | Gate 검증 |
|---|---|---|---|
| **Stage 0** | Isolated worktree 생성 + preflight 검증 | worktree path, dirty baseline hash | dirty_diff_binary_hash 기록 확인 |
| **Stage 1** | Consistent DB copy + snapshot | copy_path, copy_sha256, manifest | copy_sha256 검증, snapshot_actual vs expected_preflight |
| **Stage 2** | Sampling | sampling_frame_hash, sample_hash, sample CSV | sampling_frame_hash 검증, row_id 검증 |
| **Stage 3** | Evidence fetch + blind packet | blind_packet_hash, evidence manifest | PII 검사 통과, packet hash 검증 |
| **Stage 4** | Labeling (Reviewer A + B) | A/B labeling 결과, reviewer_id 기록 | reviewer_id 지정 확인 |
| **Stage 5** | Adjudication + result | Pilot result, κ, metrics | 최종 |

### 11.2 Gate 규칙

- 각 Stage의 산출물 해시 검증 실패 → **다음 Stage로 진행하지 않음**
- Stage 4 시작 전: **Reviewer A+B가 실제로 지정되어 있어야 함**
- Stage 5 시작 전: **Adjudicator가 A/B와 다른 사람이어야 함**

### 11.3 Reviewer 지정

| 역할 | 담당 | reviewer_id | 상태 |
|---|---|---|---|
| Reviewer A | 에이전트 | `(PENDING — 지정 시 기록)` | **PENDING** |
| Reviewer B | 사람 (개발자) | `(PENDING — 지정 시 기록)` | **PENDING** |
| Adjudicator | 제3자 | `(PENDING — 지정 시 기록)` | **PENDING** |

- **個人 식별정보는 사용하지 않는다** — reviewer_id로만 지정
- A와 B가 실제 배정되기 전에는 **blind packet 배포·labeling 금지**
- Adjudicator는 A/B와 **다른 사람**이어야 함 (동일인 여부 확인)

---

## §12 실행 조건

| 항목 | 상태 | 확인 |
|---|---|---|
| QA Plan | FINAL APPROVED | §0 참조 |
| worktree | ce9739922 기반 isolated — 원래 dirty tree 미손 | §3 (Stage 0) |
| DB copy | consistent-copy — 원본 미변경 | §2 (Stage 1) |
| row_id 검증 | NULL/중복 없음 — copy에서 검증 | §7 (Stage 1) |
| sampling | SHA-256 기반 정렬 — 재현 가능 | §5 (Stage 2) |
| Reviewer 지정 | PENDING — stage gate 적용 | §11 (Stage 4) |
| **작업 금지** | worktree 생성·DB copy·snapshot·sampling·network fetch·labeling·RecheckAll·commit·push **수행하지 않음** | 사용자 지시 |

---

## 잔존 위험

| 위험 | 상태 | 대응 |
|---|---|---|
| Reviewer A+B 미지정 | **BLOCKED** | Stage 4 전까지 지정 필요 |
| Adjudicator = A 또는 B | **BLOCKED** | Stage 5 전까지 확인 필요 |
| copy 중 concurrent writer | VACUUM INTO/online backup으로 회피 | §2.4 검증 |
| row_id 중복/결측 | copy에서 사전 검증 | §7 — 실패 시 중단 |
| snapshot_actual ≠ expected_preflight | provenance delta 기록 | §1.4 허용 조건 적용 |
| result_producer_version 입증 불가 | UNKNOWN_OR_MIXED 기록 | §3 — эксперимент 결과 해석에 영향 |
| raw evidence에 PII 잔존 | 불가피 | redaction 검사 후盲化 — 단정 금지 |
| plan_document_hash 미계산 | Pilot 시작 전 계산 필요 | Stage 0에서 SHA-256 기록 |
| SHA-256(seed‖row_id) 동률 | 극히 드묾 | §5.3 tie-breaking 규칙 적용 |
