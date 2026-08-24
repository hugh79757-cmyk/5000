# 규칙 등록 런북 (Rule Registration Runbook)

> Phase 64-06 · 5단계 등록 절차 · WARNING observe → reverse-validate → promote
> 참조: `.planning/phases/PHASE-64-rule-system-evolution/64-SELF-IMPROVEMENT.md §c`, `64-RULE-CATEGORIES.md`, `.planning/OPERATIONS-CHARTER.md` §6-2

---

## 개요

신규 규칙(S01~V03 등 C/S/L/P/V 후보 15종)은 배포차단(CRITICAL/MAJOR)으로 바로 승격하지 않는다.
반드시 `WARNING observe 7일 → 역검증(전건탐지 100% + 오탐 0건) → 사람 승인 promote → 문서화` 5단계를 거친다.
이 문서는 각 단계의 체크리스트와 산출물(artifact) 경로를 고정한다.

**원칙:** 기존 C01~C09 동작 불변, 신규 규칙은 WARNING observe부터 (charter 원칙 6) — 배포차단 금지.

---

## 단계 1: 발견 (discover)

문제 증상 발견 → 미탐(false_negative)으로 기록 → 후보 rule_id 배정.

**입력:** 문제 증상, 영향 범위, 심각도 추정, 발견 경위

**체크리스트:**
- [ ] 문제 정의서 1페이지 작성: "무엇이 문제인가 / 몇 건 / 어느 블로그 / 얼마나 심각한가"
- [ ] `logs/rule_feedback.jsonl`에 미탐 기록 append (type=false_negative, rule_id=후보, blog_id, slug, severity, gate_decision=passed, reason, detected_by=agent|human, status=open)
  - 예: `python -c "from shared.rule_feedback import record_feedback; record_feedback('false_negative', rule_id='V01', blog_id='health-hugo', slug='저혈압-...', severity='CRITICAL', gate_decision='passed', reason='라이브 og:title 불일치', detected_by='human')"`
- [ ] 후보 rule_id 배정 — 카테고리 코드 + 다음 번호 (예: V01, S01) — `64-RULE-CATEGORIES.md` §1 매핑에서 중복 확인
- [ ] 카테고리 분류: C(콘텐츠 무결성)/S(구조/SEO)/L(링크 건전성)/P(발행 정합)/V(라이브-파일 일치)

**산출물:**
- `logs/rule_feedback.jsonl` — fn-YYYYMMDD-NNN 1줄 (positive signal)
- 문제 정의서 (선택: `.planning/phases/PHASE-64-rule-system-evolution/candidates/{RULE_ID}.md`)

---

## 단계 2: 임시 관찰규칙 등록 (observe, WARNING, 7일)

실제 데이터에서 문제 빈도와 오탐 여부를 확인. 배포차단 금지 — 경고+로그만.

**수행:**
- [ ] `ops_dashboard/db.py` `SEED_STANDARD_RULES`에 후보 추가 (severity=WARNING, enabled=1)
  ```python
  {"rule_id": "V01", "target": "live+file", "severity": "WARNING",
   "description": "라이브 title/og:title 불일치 (관찰대상 — 배포차단 아님)"}
  ```
  - 위치: `ops_dashboard/db.py:552` `SEED_STANDARD_RULES` 리스트 — `C09` 다음에 append, INSERT OR IGNORE 패턴 유지
  - idempotency: 재실행 시 `INSERT OR IGNORE`로 중복 없음 보장
- [ ] `ops_dashboard/checks/content_integrity.py`에 체크 함수 등록 (또는 기존 체크 확장) — severity=WARNING이므로 `check_results`에 fail 기록만, `dispatcher.py:preflight_check`에서 blocked=False (severity lookup으로 CRITICAL만 차단)
- [ ] 필요 시 `shared/leak_tracker.py` 등 훅에 WARNING 로깅만 추가 (배포차단 로직 추가 금지)
- [ ] 7일간 데이터 축적 — `logs/rule_feedback.jsonl` + `check_results` where rule_id=후보 + `logs/leak-origin.jsonl` (해당 시)
- [ ] 관찰기간 기본값: **7일** (주간 사이클 커버 최소 기간) — 고위험·빈발은 3일 단축 가능(사람 승인), 저위험·희소는 14일 연장 가능

**체크리스트:**
- [ ] SEED에 WARNING으로 INSERT 확인: `grep -n "V01" ops_dashboard/db.py`
- [ ] `seed_standard_rules` 재시드 후 `sqlite3 ops_dashboard/ops.db "SELECT rule_id,severity FROM standard_rules WHERE rule_id='V01'"` → WARNING
- [ ] dashboard `/feedback` 및 `/api/feedback`에서 관찰 위반이 warn(노랑)으로만 표시, 배포차단 없음 확인
- [ ] 관찰기간 7일 경과 또는 N건 이상 데이터 확보 (권장: 긍정 5건+ / 부정 10건+ 축적)

**산출물:**
- `ops_dashboard/db.py` — SEED_STANDARD_RULES 1줄 추가 (WARNING)
- `ops_dashboard/ops.db` standard_rules 1 row (WARNING)
- `logs/rule_feedback.jsonl` / `check_results` 관찰 데이터

---

## 단계 3: 역검증 (reverse-validate, 전건탐지 100% + 오탐 0건)

목적: 이 규칙이 진짜 문제를 놓치지 않고(미탐 0) 모든 문제를 잡으며(전건탐지 100%), 정상글을 오탐하지 않는지(오탐 0건) 확인.

**수행:**
- [ ] 검증 데이터 구성 (최소 기준):
  - **긍정 샘플(위반 샘플):** 문제가 있는 콘텐츠 — 최소 5건 이상 → `scripts/c01_c08_validation_data/{rule_id}_positive/` 디렉터리 또는 json manifest
  - **부정 샘플(정상 샘플):** 정상 콘텐츠 — 최소 10건 이상 → `scripts/c01_c08_validation_data/{rule_id}_negative/`
  - 참고: 기존 C01~C08 검증 데이터 `scripts/c01_c08_validation_data/` (contamination.json, dead_links.json, normal_samples.json 등)가 형태 레퍼런스
- [ ] 역검증 실행:
  ```bash
  python scripts/rule_reverse_validate.py \
    --rule-id V01 \
    --positive-dir scripts/c01_c08_validation_data/v01_positive \
    --negative-dir scripts/c01_c08_validation_data/v01_negative
  ```
  - 일반화 스크립트 `scripts/rule_reverse_validate.py`는 `scripts/c01_c08_reverse_validation.py` 패턴 일반화 — `argparse --rule-id --positive-dir --negative-dir`, gate `전건탐지 100% + 오탐 0건` → exit 0 else 1 + report table
  - C01 데모 (정상 동작 확인):
    ```bash
    # 데모용 C01 샘플(자가 생성) — 긍정=곡선따옴표 포함, 부정=정상
    python scripts/rule_reverse_validate.py --rule-id C01 \
      --positive-dir scripts/c01_c08_validation_data/c01_demo_positive \
      --negative-dir scripts/c01_c08_validation_data/c01_demo_negative
    ```
- [ ] 판정 기준:
  - **전건탐지 100%:** 긍정 샘플 전부 탐지(detected == total_positive)
  - **오탐 0건:** 부정 샘플 전부 통과(false_positives == 0)
  - 둘 다 충족 → 단계 4로 진행. 하나라도 실패 → 규칙 조건/패턴/threshold 조정 후 재검증

**체크리스트:**
- [ ] `python scripts/rule_reverse_validate.py --help | grep -q "rule-id"` — CLI 파라미터 존재 확인
- [ ] 긍정 샘플 5건 이상, 부정 샘플 10건 이상 파일/데이터 존재 확인
- [ ] 실행 결과 exit 0 + report table에 `detection 5/5 (100%)` 및 `false_positive 0/10` 표시 확인 — 아니면 조건 조정 후 재검증
- [ ] 실패 시 처리: 오탐 발생 → 규칙 민감도 하향 / 미탐 발생 → 패턴 강화 → 재검증 반복
- [ ] 반복적 실패(3회 이상) → 규칙 자체 재설계 또는 폐기 검토

**산출물:**
- `scripts/rule_reverse_validate.py` 출력 (stdout report table) — 예: `| rule | positive | detected | rate | negative | false_positive | gate |`
- 검증 데이터 디렉터리 + 검증 결과 아카이브 (선택: `scripts/c01_c08_validation_data/{rule_id}/validation_result.json`)

---

## 단계 4: 정식 승격 (promote, human gate)

관찰(WARNING) → 배포차단(CRITICAL/MAJOR) 승격. 사람 승인 필수 (charter §6-2).

**수행:**
- [ ] 역검증 통과 확인 (단계 3 exit 0 리포트 첨부)
- [ ] 사람 승인 요청 — 포함 정보: 변경할 rule_id, from→to severity, 변경 사유(피드백 요약 링크), 역검증 결과, 예상 영향(차단될 정상글 범위 추정)
- [ ] 승격 실행 (human gate — --approve 없으면 실패):
  ```bash
  python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL --approve
  # 또는 특정 severity로: --from WARNING --to MAJOR --approve
  # dry-run/검증용 dummy: --file /tmp/dummy_db.py --approve
  ```
  - 스크립트는 `ops_dashboard/db.py:SEED_STANDARD_RULES`의 해당 rule_id entry severity를 in-place regex replace — `--approve` 없이 실행 시 exit 1 + "human approval required per charter §6-2" 출력 후 변경 없음
  - file edit은 `INSERT OR IGNORE` seed와 호환되도록 텍스트 치환만 수행 (DB migration 없음)
- [ ] 후속 반영 (수동):
  - `ops_dashboard/checks/content_integrity.py` 체크 severity 업데이트 (해당 시)
  - `dispatcher.py:preflight_check` severity lookup이 CRITICAL이면 blocked=True로 동작 (코드 수정 불필요 — 이미 severity-aware, but 확인)
  - `shared/publishers/hugo_writer.py` 훅 추가 (해당 시)
  - 필요 시 기존 발행분 소급 검사 배치

**체크리스트:**
- [ ] `python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL` (--approve 없이) → exit 1, stderr/stdout에 `approval` 포함 확인 (human gate 동작 검증)
- [ ] `python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL --approve` → exit 0, `ops_dashboard/db.py` 내 `"rule_id": "V01"` entry의 `"severity": "CRITICAL"` 로 변경 확인 (`grep -A2 '"V01"' ops_dashboard/db.py`)
- [ ] 승격 후 `sqlite3 ops_dashboard/ops.db "DELETE FROM standard_rules WHERE rule_id='V01'"` 후 재시드 시 CRITICAL로 재삽입되는지 확인 (seed idempotency)
- [ ] 후속 체크리스트 출력 확인: `post-promote checklist: 1) dashboard check severity 확인 2) preflight severity lookup 확인 3) git diff + tag backup`

**산출물:**
- `ops_dashboard/db.py` — SEED_STANDARD_RULES 해당 rule severity 변경 (WARNING→CRITICAL/MAJOR)
- promote stdout — post-promote checklist (dashboard/preflight/git tag)

---

## 단계 5: 문서화 (document)

승격 완료를 문서와 검증 데이터로 고정.

**수행:**
- [ ] 규칙 정의서 업데이트: `.planning/phases/PHASE-64-rule-system-evolution/64-RULE-CATEGORIES.md` §5 미구현 목록에서 해당 후보를 구현 완료로 이동 또는 별도 `docs/RULE_REGISTRY.md`에 추가 — "왜 필요한지 1줄" 필수 포함 (어떤 사고/발견에서 나왔는지, 예: "Phase 63 저혈압 글 og:title 불일치 재발 방지")
- [ ] 운영헌장 반영 확인: `.planning/OPERATIONS-CHARTER.md` 해당 카테고리(C/S/L/P/V) 배경 사고에 신규 규칙 사례 추가 필요 여부 판단
- [ ] 역검증 데이터 아카이브: `scripts/c01_c08_validation_data/{rule_id}/`에 긍정/부정 샘플 + 검증 결과 보관 (재현 가능성 보장)
- [ ] 피드백 상태 갱신: `logs/rule_feedback.jsonl`의 관련 fn entry를 `status=resolved`로 갱신 또는 신규 `resolved` 기록 (선택)
- [ ] 게이트 동작 최종 확인: `dispatcher.py` preflight가 CRITICAL 승격 규칙에 대해 blocked=True로 차단하는지 1건 수동 테스트

**체크리스트:**
- [ ] `64-RULE-CATEGORIES.md` 또는 `docs/RULE_REGISTRY.md`에 rule_id, target, severity, description, 배경 1줄 기록 확인
- [ ] `scripts/c01_c08_validation_data/{rule_id}/` 검증 데이터 존재 확인
- [ ] `logs/rule_feedback.jsonl` 해당 규칙 관련 fn/fp entry resolved 또는 문서 링크 확인
- [ ] `git diff ops_dashboard/db.py` — severity 변경 1줄만 포함, 다른 동작 변경 없음 확인

**산출물:**
- `.planning/phases/PHASE-64-rule-system-evolution/64-RULE-CATEGORIES.md` 업데이트 (또는 `docs/RULE_REGISTRY.md`)
- `scripts/c01_c08_validation_data/{rule_id}/` 검증 데이터
- (선택) `.planning/OPERATIONS-CHARTER.md` 갱신

---

## 긴급 예외 (긴급 예외 — live clear-cut critical, 역검증 통과 시 관찰 생략 가능)

**조건:** 다음을 모두 충족하는 경우에만 관찰기간(단계 2, 7일)을 생략하고 단계 3→4로 즉시 진행 가능

1. 라이브에서 확인된 명백(clear-cut) critical 문제 — 예: 라이브 og:title이 파일 title과 완전히 다른 값으로 노출, 고객/검색엔진에 즉시 피해
2. 역검증(단계 3)이 전건탐지 100% + 오탐 0건을 통과 — 검증 데이터 5건+/10건+ 확보 및 `rule_reverse_validate.py` exit 0
3. 사람 승인(`--approve`) 획득 — charter §6-2 human gate 준수

**효과:** 관찰기간 7일을 거치지 않고 `discover → reverse-validate → promote` 단축 경로 허용. 단, 역검증은 생략 불가.

**기록 의무:** 긴급 예외 적용 시 반드시 아래를 `logs/rule_feedback.jsonl`에 기록:
- 사유: "긴급 예외 적용 — live clear-cut critical, 역검증 100%+0 통과로 관찰 생략"
- 역검증 결과 요약 (긍정/부정 건수, gate pass)
- 승인자/시각

**적용 예시:** "라이브에서 V01(title 불일치)이 재발견됐고, 검증 데이터 10건에서 전건탐지 100% 확인, 오탐 0건" → 관찰기간 없이 승격 검토 가능. 이 경우에도 `scripts/rule_promote.py --approve` human gate는 필수.

**오남용 방지:** 긴급 예외는 예외적 경로이며, 남용 시 관찰 데이터 부족으로 오탐 리스크 증가. 반복적 긴급 예외는 운영헌장 위반으로 간주.

---

## 단계 간 이동 조건 요약

| 현재 단계 | → 다음 단계 조건 | → 이전 단계 조건 |
|-----------|-----------------|-----------------|
| 단계 1 (발견) | 문제 정의서 + fn 기록 + 후보 rule_id 배정 완료 | — |
| 단계 2 (관찰) | SEED에 WARNING INSERT + 7일(또는 N건) 데이터 축적 | 문제 정의 부족 시 단계 1로 |
| 단계 3 (역검증) | `rule_reverse_validate.py` exit 0 (전건탐지 100% + 오탐 0) | 관찰 데이터 부족/모호 시 단계 2 연장, 조건 미달 시 패턴 조정 후 단계 3 재검증 |
| 단계 4 (승격) | 역검증 통과 + 사람 승인(`--approve`) + promote 실행 | 조건 조정 후 단계 3으로 재검증 |
| 단계 5 (문서화) | 승격 완료 + 게이트 동작 확인 + 문서/데이터 아카이브 | 문서 누락 시 단계 4 완료 후 보완 |

---

## 전체 아티팩트 경로 체크리스트 (빠른 검증)

```bash
# 단계 1
cat logs/rule_feedback.jsonl | grep -q "false_negative" && echo "fn 기록 OK"

# 단계 2
grep -q "V01" ops_dashboard/db.py && echo "SEED 추가 OK"
sqlite3 ops_dashboard/ops.db "SELECT rule_id,severity FROM standard_rules WHERE rule_id='V01'"

# 단계 3
python scripts/rule_reverse_validate.py --help | grep -q "rule-id" && echo "reverse-validate CLI OK"
python scripts/rule_reverse_validate.py --rule-id C01 \
  --positive-dir scripts/c01_c08_validation_data/c01_demo_positive \
  --negative-dir scripts/c01_c08_validation_data/c01_demo_negative

# 단계 4
python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL; echo "exit=$? (expect 1 without --approve)"
python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL --approve; echo "exit=$? (expect 0)"
grep -A2 '"V01"' ops_dashboard/db.py

# 단계 5
grep -q "V01" .planning/phases/PHASE-64-rule-system-evolution/64-RULE-CATEGORIES.md && echo "문서화 OK"
ls scripts/c01_c08_validation_data/V01/ 2>/dev/null && echo "검증 데이터 OK"
```

---

## 참고

- charter 원칙 6: "신규 규칙은 WARNING observe부터 — 배포차단 금지"
- `SEED_STANDARD_RULES`는 `INSERT OR IGNORE` idempotent — 재시드 시 중복 없음
- `rule_reverse_validate.py` gate는 `전건탐지 100% + 오탐 0건` 엄격 기준 — 하나라도 실패 시 승격 불가
- `rule_promote.py`는 오직 `--approve` 플래그가 있을 때만 파일 수정 — human approval gate (charter §6-2)
- `64-RULE-CATEGORIES.md` §5 미구현 목록: S01~S05(5), L01~L03(3), P01~P04(4), V01~V03(3) = 총 15 후보
