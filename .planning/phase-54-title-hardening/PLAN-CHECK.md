# Plan Check: Phase 54 — Curation Title Generation Hardening

**Checked:** 2026-08-01 (리넘버: 49 → 54, `.planning/phase-54-title-hardening/`로 이동 완료)
**Plans verified:** PLAN.md (단일 플랜, Task 1-5)

---

## Overall Verdict: **PASS** (with 3 minor warnings)

계획은 구조적으로 건전하고 목표-완전(goal-complete)하며 실행 준비가 되어 있다.
모든 file:line 참조가 실제 코드와 일치(아래 검증표). 블로커 없음.
3건의 경고는 라인 오프셋 표기, mock 시나리오 명시, 실행 전 baseline 확인 항목.

---

## 코드 사실 검증표 (PLAN.md의 file:line 참조 vs 실제 코드)

| PLAN.md 참조 | 실제 코드 | 결과 |
|---|---|---|
| writer.py:15 `generate as ai_generate` import | `from shared.ai_writer import generate as ai_generate` | ✅ 일치 |
| writer.py:255 `_build_system_prompt` | `def _build_system_prompt(keyword, blog_id=None, style_hint="", recent_titles=None) -> str:` | ✅ 일치 |
| writer.py:256 연도 삽입 유지 필수 | `year = datetime.now().year` (프롬프트 f-string에서 `{year}년` 사용) | ✅ 일치 — Task 2의 "256 유지" 전제 정확 |
| writer.py:286-287 제목 규칙 1 | `1. [연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]` | ✅ 일치 — MAJOR-1(연도-접두 거부 금지) 근거 정확 |
| writer.py:449 `generate_curation_article` | `def generate_curation_article(keyword, products, blog_id=None):` | ✅ 일치 |
| writer.py:509-524 본문 글자수 재시도 루프 | `for attempt in range(2)` + `if len(body) >= 1800: break` | ✅ 일치 |
| writer.py:510 본문 생성 호출 | `ai_generate(system_prompt, user_prompt, temperature=0.85, max_tokens=6000)` (tier 미지정 → default) | ✅ 일치 — Task 5의 tier 분기 mock 전제 성립 |
| writer.py:526-528 800자 return None | `if not body or len(body) < 800: ... return None` | ✅ 일치 — "변경하지 않는다" 명시 정확 |
| writer.py:530-537 H1 추출 | `if line.startswith("# "): title = line.lstrip("# ").strip()` | ✅ 일치 (1라인 오프셋 — W1 참조) |
| writer.py:538-539 하드코딩 fallback | `if not title: title = f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` | ✅ 일치 — SC-1 대상 정확 |
| writer.py:552-560 description 인라인 | `desc_lines` 루프 + `" ".join(desc_lines)[:160]` | ✅ 일치 — "기존 160자 → 150자" 근거 정확 |
| writer.py:297 "TOP 5" 예시 (공백) | `예: "... 1만원대 합격 TOP 5"` | ✅ — SC-1 grep(`추천 TOP5` 띄어쓰기 없음) 오염 없음. Task 1 금지 예시는 `추천 TOP N` 표기로 설계됨 |
| ai_writer.py:71 `generate` 시그니처 | `def generate(system_prompt, user_prompt, tier="default", temperature=None, max_tokens=None):` | ✅ 일치 — 기본 tier=`"default"`, Task 5 kwargs 분기(`tier=="economy"`) 성립 |
| ai_writer.py:154-160 dict 반환 | `return {"content": content, "model": ..., "provider": ..., "tier": ..., "tokens_used": ...}` | ✅ 일치 — Task 2 MINOR-4 정규화(`result.get("content", "")`) 근거 정확 |
| ai_writer.py:172-173 전 tier 실패 raise | `msg = f"모든 LLM tier 실패: {last_error}"` / `raise RuntimeError(msg)` | ✅ 일치 — Task 2 try/except 전제 정확 |
| pipeline.py:427 TITLE_BLOCKED dict | `TITLE_BLOCKED = {"laptop-hugo": [...], ...}` | ✅ 일치 |
| pipeline.py:653 LEDGER_DB | `LEDGER_DB = PROJECT_DIR / "data" / "content.db"` | ✅ 일치 |
| pipeline.py:655 `_record_failure` 시그니처 | `def _record_failure(blog_id: str, stage: str, error_msg: str, keyword: str = "") -> None:` | ✅ 일치 |
| pipeline.py:889 본경로 호출 | `article = generate_curation_article(keyword, products, blog_id=blog_id)` | ✅ 일치 |
| pipeline.py:890-892 None 체크 | `if not article: _record_failure(blog_id, "write_error", ...) return {...}` | ✅ 일치 — 게이트 삽입 위치("890-892 뒤") 정확 |
| pipeline.py:895 언어 검증 | `_lang_err = assert_korean_or_reject(...)` | ✅ 일치 — 게이트가 "언어 검증 895 이전" 전제 정확 |
| pipeline.py:901 sanitize_title | `title = sanitize_title(article["title"])` | ✅ 일치 |
| pipeline.py:912-917 TITLE_BLOCKED 검사 | `for bw in title_blocked: if bw.lower() in title.lower() ...` | ✅ 일치 |
| pipeline.py:965-968 fallback 키워드 루프 | `article = generate_curation_article(keyword, products, blog_id=blog_id)` + `if not article: continue` | ✅ 일치 — Task 4 게이트 2번째 적용 지점 정확 |
| tests/curation/conftest.py fixture | `sample_products`(:8), `temp_db`(:21), `temp_db_with_data`(:74) | ✅ 일치 |
| 검증 루프 [5] `id > 1980` 기준 | `data/curation.db` publish_log `MAX(id)=1987` | ✅ 유효 (실행 시점 재확인 필요) |

---

## Goal-Backward Traceability Matrix

| Phase Goal / SC (from PLAN.md) | Task(s) | Verification Step |
|---|---|---|
| **Goal**: 신규 발행 제목 템플릿 패턴 0건 (fail-closed) | T2 (fallback 제거+재생성), T4 (게이트) | [1]~[5] 전부 |
| **SC-1**: writer.py fallback grep 0건 | T2 (538-539 삭제) | [1] `grep -n "추천 TOP5"` |
| **SC-2**: 제목 `(2026년)` 미종결 | T2 (재생성 루프), T1 (H1 1차 방어) | [2] mock 검증 |
| **SC-3**: description CoT 미포함 | T3 (`_extract_description`) | [2] mock 검증 |
| **SC-4**: 회귀 테스트 — 신규 title 템플릿 패턴 0건 | T4 (게이트), T5 (테스트) | [3] pytest |
| **SC-5**: 기존 스위트 green | T5 (기존 테스트 수정 없음) | [4] pytest + W3(baseline) |

| CONTEXT 확정 설계 결정 | Task(s) | 반영 |
|---|---|---|
| 재생성 루프 (economy/0.5/200, 2회, 10-60자 + CoT/템플릿 거부) | T2 | ✅ PLAN:57-62 |
| 템플릿 패턴 3종 + `^\d{4}년` 제외 (MAJOR-1 교정) | T2, T4 | ✅ PLAN:55-56, 102 |
| 실패 처리: 발행 중단 + `_record_failure("title_regenerate_failed")` | T2, T4 | ✅ PLAN:65, 104 |
| 프롬프트 additive (H1 첫 줄 / CoT 금지 / `TOP N` 표기) | T1 | ✅ PLAN:33-37 |
| description `_extract_description` 헬퍼 (CoT 스킵 → 의미 문단 → 150자) | T3 | ✅ PLAN:82-89 |
| 게이트 thin wrapper (기존 TITLE_BLOCKED 위, dict 하위 호환) | T4 | ✅ PLAN:103-110 |
| 회귀 테스트 필수 + `_title_gate` 단위 시임 (MAJOR-2) | T5 | ✅ PLAN:127-132 |
| 계약 1 (dict 하위 호환), 계약 3 (hard fallback 금지) | T2, T4 | ✅ 마커 키 추가만 / 완전 제거+차단 |
| 계약 4 (스코프 제한: Hugo 템플릿/키워드 풀 별도) | — | ✅ 위험표에 명시 (T2 body 미삽입, T5 스코프) |
| 계약 5 (검증 스크립트 정확성: `generate_curation_article`, `sqlite3 data/curation.db`) | — | ✅ 검증 루프 [2]/[5] 일치 |

---

## Dimension-by-Dimension Analysis

### Dimension 1: Requirement Coverage — ✅ PASS
SC-1~SC-5 각각 최소 1개 태스크 매핑. 계약 1~5 전부 반영. 누락 요구사항 없음.

### Dimension 2: Task Completeness — ✅ PASS
Task 1-5 각각 파일/라인/설명/의존성/Acceptance Check/예상 소요 명시. Task 2에 mock 기반 검증 시나리오 상세 포함.

### Dimension 3: Dependency Correctness — ✅ PASS
- T1 → T2 → T3 (동일 파일 writer.py 순차 편집) ✓
- T2 → T4 (마커 dict 계약 소비) ✓
- T1~T4 → T5 (회귀 테스트) ✓
- 사이클 없음. 병렬 불가 명시 (단일 파일 체인) ✓

### Dimension 4: Key Links Planned — ✅ PASS
데이터 흐름 추적 정확:
- `writer._build_system_prompt`(:255) → `writer.generate_curation_article`(:449, H1 추출 :531-537 → 재생성 :57-62) → `pipeline.py`(:889 본경로, :965 fallback) → 게이트 → `_record_failure`(:655, LEDGER_DB :653)
- `ai_writer.generate`(:71) → dict 반환(:154-160) → `RuntimeError`(:173) 정규화 경로 일치

### Dimension 5: Scope Sanity — ✅ PASS
5 tasks / 3 파일 수정 (writer.py, pipeline.py) + 1 신규 테스트 파일. 본문 재생성 제목 삽입 금지(T2), 본문 CoT scrub은 위험표에만 기록(MINOR-7) — 스코프 명시적.

### Dimension 6: Verification Derivation — ✅ PASS
SC-1/SC-2/SC-3은 독립 검증 명령(mock 포함) 존재, SC-4는 pytest, SC-5는 기존 스위트. 검증 루프 [5]는 실 DB 조건(`id > 1980`) 명시. 실행 후 기록 데이터 미수정 원칙 명시.

### Dimension 7: Context Compliance — ✅ PASS
CONTEXT.md 7개 확정 결정 전부 Task에 구현. 계약 1/3/4/5 준수. 스코프 축소 언어 없음.

### Dimension 7b: Scope Reduction Detection — ✅ PASS
"v1/future/stub/placeholder" 축소 표현 없음. 전 태스크 약속 이행 구조.

### Dimension 7c: Architectural Tier Compliance — ✅ PASS
- `writer.py` / `pipeline.py` → Pipeline 코드 계층 ✓
- `tests/curation/` → 테스트 계층 ✓
- `_record_failure`/LEDGER_DB → 기존 인프라 재사용 ✓

### Dimension 8: Nyquist Compliance — ⏭️ SKIPPED
`.planning/config.json`에서 이전 phase와 동일하게 비활성 추정 (이전 phase PLAN-CHECK에서 SKIPPED 처리됨).

### Dimension 9: Cross-Plan Data Contracts — ✅ PASS
`title_generation_failed` 마커 키는 writer → pipeline 단방향 계약. 기존 반환 키(title/body_md/keyword/product_count/description) 모두 유지 — 기존 호출부(pipeline.py:889/965, 기타 import처) 파손 없음.

### Dimension 10: AGENTS.md Compliance — ✅ PASS
- **Additive만**: Task 1 기존 프롬프트 내용 불변, Task 2 마커 키 추가만, Task 3 150자(기존 160자의 부분집합)
- **기존 테스트 수정 금지**: Task 5 명시 ("기존 테스트 파일 수정하지 않는다")
- **기존 동작 보존**: TITLE_BLOCKED/sanitize_title/_record_failure 시그니처 불변
- **실 HTTP 경로 mock 지양**: MAJOR-2 반영 (`_title_gate` 단위 시임, `_run_inner` 경유 금지, `_record_failure` 패치로 content.db 쓰기 차단)

### Dimension 11: Research Resolution — ✅ PASS
CONTEXT.md 결정 2에 plan-checker MAJOR-1 교정 반영 표기. RESEARCH.md 4.5 `get_keyword_metadata`는 옵션 스코프로 미결정 — PLAN 미반영 (아래 W2 참조).

### Dimension 12: Pattern Compliance — ⏭️ SKIPPED
본 phase에 PATTERNS.md 없음 (이전 phase와 동일).

---

## Warnings

### Warning 1: H1 추출 라인 오프셋 표기 (PLAN.md:49)

**Severity:** WARNING (문서 표기)
**Description:** Task 2의 "H1 추출(530-537)"은 실제 코드에서 `title = ""` 초기화가 531, H1 매칭 루프가 532-537. PLAN은 530부터로 1라인 오프셋. Task 4 Acceptance가 TITLE_BLOCKED 루프를 "912-917"로 지칭하는 것도 실제와 일치(916에서 `_record_failure` 호출, 917에서 return) — 이건 정확.
**Fix:** 실행 시 라인번호가 아닌 패턴(`if line.startswith("# ")`)으로 로케이트.
**Execution risk:** 없음. grep/패턴 기반 Acceptance라 라인 오프셋 무해.

### Warning 2: `get_keyword_metadata` 미결정 항목 (RESEARCH.md 4.5)

**Severity:** WARNING (스코프 경계)
**Description:** RESEARCH.md 4.5는 retry 프롬프트에 키워드 메타데이터를 조건부 삽입하는 옵션을 제안했으나 CONTEXT.md/PLAN.md에 반영되지 않음. "옵션/스코프 판단 필요" 상태로 남아 있음.
**Fix:** 실행 전 명시적 결정 필요 — (a) 스코프 포함(재생성 프롬프트에 `get_keyword_metadata(keyword)` → None이면 생략) 또는 (b) 명시적으로 스코프 제외 선언.
**Execution risk:** 낮음. 미포함 시에도 fail-closed 차단체계(SC-1~5)는 성립. 포함 시 Task 2 `_regenerate_title`에 작은 추가.

### Warning 3: SC-5 baseline 미실행 상태

**Severity:** WARNING (실행 프로세스)
**Description:** SC-5 "기존 스위트 green"은 수정 전 baseline을 요구하지만 PLAN에 명시적 baseline 실행 단계가 없음.
**Fix:** Task 1 시작 전 `python -m pytest tests/curation -q` baseline 기록 (AGENTS.md 코드 수정 원칙 필수 단계).
**Execution risk:** 낮음. 실행 시 첫 단계로 수행하면 해소.

---

## Summary

| Dimension | Status |
|-----------|--------|
| 1. Requirement Coverage | ✅ PASS |
| 2. Task Completeness | ✅ PASS |
| 3. Dependency Correctness | ✅ PASS |
| 4. Key Links Planned | ✅ PASS |
| 5. Scope Sanity | ✅ PASS |
| 6. Verification Derivation | ✅ PASS |
| 7. Context Compliance | ✅ PASS |
| 7b. Scope Reduction Detection | ✅ PASS |
| 7c. Architectural Tier Compliance | ✅ PASS |
| 8. Nyquist Compliance | ⏭️ SKIPPED |
| 9. Cross-Plan Data Contracts | ✅ PASS |
| 10. AGENTS.md Compliance | ✅ PASS |
| 11. Research Resolution | ✅ PASS |
| 12. Pattern Compliance | ⏭️ SKIPPED |

**Overall: PASS** — 0 블로커, 3 경고. 실행 준비 완료.

PLAN.md의 모든 file:line 참조는 실제 코드와 정확히 일치(코드 사실 검증표 26건 전부 ✅). 리넘버(49→54) 후에도 계약·설계 결정·plan-checker 교정(MAJOR-1 연도-접두 제외, MAJOR-2 단위 시임, MINOR-4 dict 정규화, MINOR-5 kwargs 분기 mock, MINOR-6 grep 오염 방지, MINOR-7 본문 CoT, MINOR-8 전용 프롬프트)이 전부 유지됨. 실행 전 W2(스코프 결정)와 W3(baseline 기록)만 처리하면 된다.
