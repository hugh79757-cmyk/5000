# Rule Registration Runbook — 5단계 신규 규칙 승격 절차

> **목적**: 운영헌장(`.planning/OPERATIONS-CHARTER.md`) §6-2에 따라 신규 규칙(C/S/L/P/V 후보)을 **WARNING 관찰 → 역검증 100%+오탐0 → 승격 → 문서화** 순서로 안전하게 도입한다.
> **원칙**: 배포차단(CRITICAL)은 역검증 통과 전 절대 금지. 모든 단계 아티팩트 경로 명시로 추적 가능.

---

## 개요: 5단계 파이프라인

| 단계 | 명칭 | 핵심 액션 | 진입 조건 | 산출 아티팩트 |
|------|------|-----------|-----------|---------------|
| 1 | **Discover** (발견) | false_negative 피드백/수동 분석으로 후보 식별 | `logs/rule_feedback.jsonl`에 `type=false_negative` 누적 ≥3건 또는 수동 요청 | 후보 규칙 명세서(임시 ID: `CAND-XXX`) |
| 2 | **Observe** (관찰·7일) | WARNING severity로 등록, **배포차단 없음**, 실서비스 관측 | 1단계 후보 확정 + `SEED_STANDARD_RULES`에 WARNING 항목 추가 | `ops_dashboard/db.py` SEED 항목(`severity: "WARNING"`), preflight/dash에 룰 등록 |
| 3 | **Reverse-Validate** (역검증·전건탐지+오탐0) | 양성/음성 검증셋으로 **100% 탐지 + 0% 오탐** 게이트 통과 | 2단계 7일 관찰 완료(또는 긴급 예외) + 검증 데이터 준비 | `scripts/rule_reverse_validate.py --rule-id XXX` 출력: `exit 0` + 리포트 테이블 |
| 4 | **Promote** (승격·인간 게이트) | `--approve` 플래그로 SEED severity 상향(예: WARNING→MAJOR/CRITICAL) | 3단계 `exit 0` 확인 + 사람 승인 | `scripts/rule_promote.py --rule-id XXX --from WARNING --to CRITICAL --approve` 실행 로그 |
| 5 | **Document** (문서화) | 카테고리 매핑·체크리스트·대시보드 반영, 런북 이력 기록 | 4단계 완료 | `64-RULE-CATEGORIES.md` 업데이트, `docs/RULE_REGISTRATION_RUNBOOK.md` 이력 추가 |

---

## 단계별 상세 체크리스트

### 단계 1: Discover (발견) — 후보 식별

**트리거**
- `scripts/rule_feedback_review.py --since 30d` 실행 시 `false_negative` 카운트 ≥ 3건인 rule_id
- 또는 운영자 수동 분석(라이브 장애, C08 크롤 에러 등)으로 새 패턴 발견

**액션**
1. 후보 패턴 명세 작성: 패턴 설명, 탐지 대상(프론트매터/본문/라이브/파일), 로케일(ko/en), 예상 severity
2. 임시 ID 부여: `CAND-001`, `CAND-002`... (나중에 정식 S01/L01/P01/V01 등으로 매핑)
3. 검증 데이터셋 준비 시작: 양성 샘플(위반 케이스) 수집, 음성 샘플(정상 케이스) 수집

**체크리스트**
- [ ] `logs/rule_feedback.jsonl`에서 `false_negative` 패턴 확인
- [ ] 후보 패턴 명세서 작성(`docs/candidates/CAND-XXX-spec.md`)
- [ ] 양성 샘플 ≥ 5개 확보(`scripts/validation_data/CAND-XXX/positive/`)
- [ ] 음성 샘플 ≥ 10개 확보(`scripts/validation_data/CAND-XXX/negative/`)
- [ ] 담당자/요청자 기록

**아티팩트 경로**
- `docs/candidates/CAND-XXX-spec.md` (후보 명세)
- `scripts/validation_data/CAND-XXX/positive/*.md` (양성)
- `scripts/validation_data/CAND-XXX/negative/*.md` (음성)

---

### 단계 2: Observe (관찰·7일) — WARNING 등록·실서비스 관측

**전제**: 1단계 체크리스트 완료

**액션**
1. `ops_dashboard/db.py:SEED_STANDARD_RULES`에 새 규칙 추가:
   ```python
   {"rule_id": "S01", "target": "body", "severity": "WARNING",
    "description": "후보 패턴 설명 — 7일 관찰 중, 배포차단 안 함"}
   ```
2. `seed_standard_rules()` 재실행으로 DB 반영 (`python -c "from ops_dashboard.db import seed_standard_rules; import sqlite3; seed_standard_rules(sqlite3.connect('ops_dashboard/ops.db'))"`)
3. Preflight/대시보드 체크 함수에 규칙 로직 추가 (WARNING이므로 `blocked=False` 경로만)
4. 7일간 실서비스 관측: `logs/c01_c04_preflight.json` / 대시보드 `/blog/<id>`에서 위반 건수·오탐 여부 기록

**체크리스트**
- [ ] `SEED_STANDARD_RULES`에 WARNING 항목 추가 완료
- [ ] `seed_standard_rules()` 실행 → `sqlite3 ops_dashboard/ops.db "SELECT * FROM standard_rules WHERE rule_id='S01'"` 확인
- [ ] Preflight 체크 함수에 로직 추가 (C01~C09 패턴 참조: `dispatcher.py:preflight_check`)
- [ ] 대시보드 체크 함수에 로직 추가 (`ops_dashboard/checks/content_integrity.py` `@register_check` 패턴)
- [ ] 7일 관찰 기간 설정 (시작일 기록)
- [ ] 관찰 기간 중 `blocked=True` 발생 시 즉시 분석 → 오탐이면 단계 3으로 조기 진행, 진짜 위반이면 유지

**아티팩트 경로**
- `ops_dashboard/db.py` (SEED_STANDARD_RULES 수정)
- `ops_dashboard/ops.db` (standard_rules 테이블 반영)
- `dispatcher.py` / `ops_dashboard/checks/content_integrity.py` (체크 로직 추가)
- 관찰 로그: `logs/rule_feedback.jsonl`에 `type=false_positive` 누적 시 기록

**중요**: 이 단계에서 **절대 `blocked=True` 반환 금지**. WARNING severity 규칙은 preflight에서 `blocked=False`로만 기록.

---

### 단계 3: Reverse-Validate (역검증) — 전건탐지 100% + 오탐 0 게이트

**전제**: 2단계 7일 관찰 완료 **또는** 긴급 예외 조항 충족(아래 참조)

**액션**
1. 검증 데이터셋 최종 확인: 양성/음성 디렉토리에 충분한 샘플 존재
2. `scripts/rule_reverse_validate.py` 실행:
   ```bash
   python scripts/rule_reverse_validate.py \
       --rule-id S01 \
       --positive-dir scripts/validation_data/S01/positive \
       --negative-dir scripts/validation_data/S01/negative
   ```
3. 결과 판정:
   - **통과 (exit 0)**: 양성 100% 탐지(`detected/total = 100%`) AND 음성 0% 오탐(`false_positives = 0`)
   - **실패 (exit 1)**: 미탐지 존재 또는 오탐 발생 → 규칙 로직 수정 후 재실행

**체크리스트**
- [ ] 양성 샘플 전건 탐지 확인 (`detected == total`)
- [ ] 음성 샘플 오탐 0건 확인 (`false_positives == 0`)
- [ ] `rule_reverse_validate.py` 출력에 `✅ 결과: 전건 탐지 + 오탐 0` 확인
- [ ] 검증 리포트 JSON 저장 확인(`scripts/validation_data/S01/validation_result.json`)
- [ ] 실패 시: 규칙 로직 수정 → 검증 데이터 보강 → 재실행 (무한 루프 방지: 최대 3회, 이후 사람 개입)

**아티팩트 경로**
- `scripts/rule_reverse_validate.py` 출력 (stdout + exit code)
- `scripts/validation_data/S01/validation_result.json` (상세 결과)
- 콘솔 리포트 테이블 (탐지율/오탐율 요약)

---

### 단계 4: Promote (승격) — 인간 승인 게이트로 severity 상향

**전제**: 3단계 `exit 0` 확인 완료

**액션**
1. `scripts/rule_promote.py` 실행 (반드시 `--approve` 플래그 필요):
   ```bash
   python scripts/rule_promote.py \
       --rule-id S01 \
       --from WARNING \
       --to CRITICAL \
       --approve
   ```
2. 스크립트 동작:
   - `ops_dashboard/db.py:SEED_STANDARD_RULES`에서 해당 `rule_id` 항목의 `severity` 값을 `--to` 값으로 치환 (정규식 기반)
   - `--approve` 없으면 `exit 1` + `"human approval required per charter §6-2"` 출력 후 중단
   - 성공 시: 수정된 SEED 출력 + 사후 체크리스트 출력
3. `seed_standard_rules()` 재실행으로 DB 반영
4. Preflight/대시보드에서 severity lookup 로직이 새 severity 반영 확인

**체크리스트**
- [ ] `--approve` 플래그 포함 실행 확인
- [ ] `ops_dashboard/db.py` SEED_STANDARD_RULES 내 해당 rule_id severity 변경 확인 (`grep -n "S01.*CRITICAL" ops_dashboard/db.py`)
- [ ] `seed_standard_rules()` 재실행 → DB 확인 (`sqlite3 ops_dashboard/ops.db "SELECT severity FROM standard_rules WHERE rule_id='S01'"`)
- [ ] Preflight severity lookup이 새 값 반영 확인 (`python -c "from ops_dashboard.db import SEED_STANDARD_RULES; print([r for r in SEED_STANDARD_RULES if r['rule_id']=='S01'])"`)
- [ ] 대시보드 `/standards` 페이지에서 severity 표시 확인

**아티팩트 경로**
- `ops_dashboard/db.py` (SEED_STANDARD_RULES severity 수정)
- `ops_dashboard/ops.db` (standard_rules 테이블 반영)
- `scripts/rule_promote.py` 실행 로그 (stdout)

**사후 승격 체크리스트 (스크립트 자동 출력)**
```
[ ] Preflight: rule_id 조회 시 새 severity 반환
[ ] Dashboard: /standards 에서 severity 표시 일치
[ ] Telegram alert: CRITICAL 위반 시 알림 포맷 정상
[ ] 배포 게이트: blocked=True 경로 동작 확인 (테스트 블로그 1건)
[ ] 64-RULE-CATEGORIES.md 카테고리 매핑 추가됨
```

---

### 단계 5: Document (문서화) — 영구 기록 반영

**전제**: 4단계 승격 완료

**액션**
1. `64-RULE-CATEGORIES.md` (또는 해당 카테고리 문서)에 정식 rule_id(S01/L01/P01/V01 등) + 카테고리 + severity 기록
2. `docs/RULE_REGISTRATION_RUNBOOK.md` 이력 섹션에 등록 이력 추가
3. 후보 임시 문서(`docs/candidates/CAND-XXX-spec.md`)를 정식 문서로 이동/병합
4. 검증 데이터셋을 `scripts/c01_c08_validation_data/` 스타일로 정규 위치 이동(선택)

**체크리스트**
- [ ] `64-RULE-CATEGORIES.md`에 rule_id, category, severity, description 추가
- [ ] `docs/RULE_REGISTRATION_RUNBOOK.md` 하단 **등록 이력** 테이블에 행 추가
- [ ] 후보 문서 정리(이동/병합)
- [ ] 팀/운영자 공유 (Slack/Telegram 알림)

**아티팩트 경로**
- `64-RULE-CATEGORIES.md` (카테고리 매핑표)
- `docs/RULE_REGISTRATION_RUNBOOK.md` (이력 테이블)
- `docs/rules/S01.md` (정식 규칙 문서, 선택)

---

## 긴급 예외 조항 (Emergency Bypass)

> **운영헌장 §6-2**: "실서비스에서 명백한 크리티컬 장애(C08 라이브 불일치, C09 배포 실패 등)가 발생하고, 역검증 데이터가 즉시 준비되어 **전건탐지 100% + 오탐 0**을 만족하면, 7일 관찰(단계 2)을 생략하고 단계 3→4로 직행할 수 있다. 단, 생략 사유를 런북 이력에 필수 기록."

**적용 조건 (모두 충족해야 함)**
1. 실서비스에서 **명백한 크리티컬 장애** 발생 (배포 실패, 라이브 404 다량, 광고 수익 직결 장애 등)
2. 해당 패턴에 대한 **양성/음성 검증 데이터 즉시 준비 가능** (기존 로그/샘플로 구성 가능)
3. `rule_reverse_validate.py` 실행 결과 **전건탐지 100% + 오탐 0** 달성
4. 승격 사유·생략 사유를 `docs/RULE_REGISTRATION_RUNBOOK.md` 이력에 **상세 기록**

**절차**
1. 긴급 상황 인지 → 담당자 판단 → 위 4조건 확인
2. 단계 1~2 생략, 바로 단계 3 역검증 실행
3. 통과 시 단계 4 승격 실행 (`--approve` 필수)
4. 이력 기록: `"긴급 예외 적용: [장애 내용], 관찰 7일 생략, 역검증 통과일자 [YYYY-MM-DD]"`

**주의**: 이 조항은 **연 2회 초과 사용 금지**. 남용 시 운영헌장 위반으로 간주.

---

## 등록 이력 (자동 갱신 영역)

| 날짜 | Rule ID | 후보→정식 | 카테고리 | Severity(초기→최종) | 관찰기간 | 역검증결과 | 승격승인자 | 비고 |
|------|---------|-----------|----------|---------------------|----------|------------|------------|------|
| 2026-08-24 | (예시) S01 | CAND-001→S01 | S | WARNING→CRITICAL | 7일 | 전건탐지 15/15, 오탐 0/20 | 홍길동 | 최초 등록 |
| 2026-08-24 | (예시) L01 | CAND-005→L01 | L | WARNING→MAJOR | 생략(긴급) | 전건탐지 8/8, 오탐 0/12 | 김철수 | C08 크롤 에러 대응 긴급 예외 |

> **자동 갱신**: 단계 5 완료 시 위 테이블에 행 추가. 포맷 유지 필수.

---

## 관련 스크립트 요약

| 스크립트 | 용도 | 핵심 옵션 |
|----------|------|-----------|
| `scripts/rule_reverse_validate.py` | 범용 역검증 (양성/음성 디렉토리 기반) | `--rule-id`, `--positive-dir`, `--negative-dir`, `--help` |
| `scripts/rule_promote.py` | SEED severity 상향 (인간 게이트) | `--rule-id`, `--from`, `--to`, `--approve` (필수) |
| `scripts/rule_feedback_review.py` | 피드백 분석 → 후보 발굴 | `--since 7d|30d` |
| `ops_dashboard/db.py:seed_standard_rules()` | SEED → DB 동기화 | 수동 호출 또는 dispatcher 시작 시 자동 |

---

## 버전 관리

- v1.0 (2026-08-24): Phase 64 Task 64-06 최초 작성
- 변경 시: 상단 버전/날짜 갱신, 이력 테이블에 변경 사유 기록