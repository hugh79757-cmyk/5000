# Phase 54 — Curation Title Generation Hardening 실행 계획

> 상태: 계획 수립 (2026-08-01)
> 근거: `RESEARCH.md`(루트코즈 검증 완료, file:line 증거 포함) + `CONTEXT.md`(계약/확정 설계 결정)
> 작업 규칙: **기존 기능 보존, 증분 수정** (AGENTS.md 코드 수정 원칙). 반환 형식 `{"success": bool, "reason": str, ...}` dict 하위 호환 유지 (CONTEXT 계약 1).

---

## Goal (1문장, 측정 가능)

큐레이션 파이프라인에서 하드코딩 fallback 제목(`{keyword} 추천 TOP5 (연도년)`) 생성 경로를 완전히 제거하고, H1 출력 형식 강제 + CoT/프롬프트 누출 차단 + 회귀 테스트로 **신규 발행 제목에서 템플릿 패턴(`추천\s*TOP\s*\d+` 또는 `\(\d{4}년\)$`)이 0건이 되도록** 실패-폐쇄(fail-closed) 차단 체계를 구축한다.

---

## Success Criteria (각각 테스트 가능 — CONTEXT.md 4개 기준 + 1개 보강)

1. **SC-1**: `writer.py:538-539` 하드코딩 fallback이 제거됨 — `grep -n "추천 TOP5" pipelines/curation/writer.py` 결과 0건 (테스트 파일 제외, 파일 특정 grep).
2. **SC-2**: `generate_curation_article(keyword='네덜란드', ...)` 호출 시 제목이 `(2026년)`으로 끝나지 않음 (H1 재생성 경로 검증 포함).
3. **SC-3**: 동일 호출의 `description`에 "우선 사용자 요청" 미포함 (CoT 누출 차단).
4. **SC-4**: 회귀 테스트 통과 — 신규 발행의 publish_log title에 템플릿 패턴(`추천\s*TOP\s*\d+`, `\(\d{4}년\)$`, `BEST\s*\d+` — 게이트 `TITLE_TEMPLATE_PATTERNS`와 동일 3종) 기록 0건.
5. **SC-5**: 기존 테스트 스위트 green 유지 — `python -m pytest tests/curation -q` 전부 통과 (기존 테스트 수정 없이).

---

## Out of Scope (2026-08-01 실행 시 W2 결정 반영)

- **get_keyword_metadata (RESEARCH 4.5)** — deferred to follow-up phase.
  Retry prompt operates without keyword metadata; metadata enrichment
  is a separate capability.

---

## Task Breakdown

> 구분 표기: **[PRODUCTION CODE]** = 검증 대상 코드 수정, **[TEST CODE]** = 검증 수단 추가.

### Task 1 [PRODUCTION CODE] — `_build_system_prompt`에 H1 출력 형식 + CoT 금지 지시 추가
- **파일**: `pipelines/curation/writer.py:255-385` (`_build_system_prompt` 함수)
- **설명** (확정 설계 결정 4):
  - 시스템 프롬프트에 아래 3가지 지시를 추가한다:
    1. "응답의 맨 첫 줄에 반드시 '# ' 마크다운 H1 제목을 작성할 것" — H1 누락 시 재생성 루프가 발동되므로 이를 1차 방어로 차단.
    2. 나열형 템플릿 제목 금지: `"{키워드} 추천 TOP N (연도년)"` 형태 금지 문구.
    3. CoT/검토 텍스트 금지: `"우선 사용자 요청은~"`, `"제목 규칙을 확인해야 한다~"`, `"제목 예시를 만들어보자~"` 형태의 사고 과정/검토 문구 출력 금지.
   - 기존 역할/페르소나/AIDA/제목 규칙 내용(BLOG_EXTRA_RULES 등)은 **변경하지 않는다** — 순수 추가(additive)만.
   - **주의 (MINOR-6)**: 추가되는 금지 문구의 예시는 반드시 `"추천 TOP N (연도년)"` 표기를 사용할 것. 리터럴 `"추천 TOP5"`를 프롬프트 텍스트 안에 쓰면 SC-1 grep(writer.py 한정)이 오염되어 검증 실패로 오판됨.
- **의존성**: 없음 (writer.py 동일 파일 내 Task 2/3보다 먼저 실행하여 diff를 깔끔하게 유지)
- **Acceptance Check**:
  - `grep -n "맨 첫 줄" pipelines/curation/writer.py` → 1건 이상 (H1 지시 존재)
  - `grep -n "우선 사용자 요청\|제목 규칙을 확인\|제목 예시를 만들어" pipelines/curation/writer.py` → 1건 이상 (프롬프트 내 금지 문구 존재)
  - `grep -n "추천 TOP N" pipelines/curation/writer.py` → 금지 예시 표기가 `TOP N` 형태인지 확인 (리터럴 `TOP5` 없음)
  - `python -m pytest tests/curation -q` → 기존 스위트 green (프롬프트 문자열 검증 테스트가 따로 없음을 grep으로 확인 후 진행)
- **예상 소요**: 약 0.5h

---

### Task 2 [PRODUCTION CODE] — 하드코딩 fallback 제거 + 제목 전용 재생성 루프
- **파일**: `pipelines/curation/writer.py:530-539` (H1 추출 + fallback), 신규 헬퍼 추가
- **설명** (확정 설계 결정 1, 2, 3):
  1. **fallback 완전 제거**: `writer.py:538-539`의 `if not title: title = f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` 블록을 삭제한다. 어떤 형태의 템플릿 문자열 fallback도 남기지 않는다.
   2. **`_validate_title(title)` 헬퍼 신규 추가** — 제목 수용 조건 (결정 2, plan-checker MAJOR-1 교정 반영):
      - `10 <= len(title) <= 60`
      - CoT 마커 미포함: `"우선"`, `"사용자 요청"` 부분 문자열 없음
      - 템플릿 패턴 미포함: `re.search(r"추천\s*TOP\s*\d+", title, re.I)` 없음, `re.search(r"\(\d{4}년\)$", title)` 없음, `re.search(r"BEST\s*\d+", title, re.I)` 없음
      - **주의**: `^\d{4}년`(연도-접두)은 거부하지 않는다 — 시스템 프롬프트 제목 규칙 1(writer.py:286-287, `[연도]년 [월]월 [제품명] 추천`)이 연도-접두 제목을 지시하므로, 이를 거부하면 프롬프트 준수 제목이 전부 차단됨. 실제 fallback 시그니처(`{keyword} 추천 TOP5 (2026년)`)는 위 3개 패턴으로 충분히 포착됨.
   3. **`_regenerate_title(keyword, blog_id, max_attempts=2)` 헬퍼 신규 추가**:
      - `ai_generate`(writer.py:15에서 import한 shared/ai_writer.py:71 `generate`의 alias)를 호출: `ai_generate(system_prompt, user_prompt, tier="economy", temperature=0.5, max_tokens=200)`
      - **응답 정규화** (plan-checker MINOR-4 반영): `text = result if isinstance(result, str) else result.get("content", "")` — ai_writer.py:154-160이 dict 반환, 전 tier 실패 시 `RuntimeError` raise (ai_writer.py:172-173)이므로 `try/except`로 감싸 예외도 "무효"로 취급 → 재시도 → 최종 `None` (fail-closed 유지)
      - 응답 첫 줄에서 선행 `"# "` 제거 후 `_validate_title`로 검증
      - 유효 시 해당 제목 반환, 무효 시 최대 2회 재시도 (모두 무효 → `None` 반환)
      - 재생성 전용 프롬프트는 "제목만 한 줄로 출력" 형태로 구성 (본문 작성 프롬프트 재사용 금지 — MINOR-8, max_tokens=200에 본문 규칙 2500~3500자 지시가 섞이면 조각 출력)
  4. **`generate_curation_article` (writer.py:449) 수정**: H1 추출(530-537) 실패 시:
     - `_regenerate_title` 호출 → 성공 시 그 제목 사용
     - **2회 모두 실패 시**: 템플릿 문자열로 대체하지 않고 실패 마커 dict 반환: `{"title": "", "body_md": body, "keyword": keyword, "product_count": min(len(products), 5), "description": <기존 추출 결과>, "title_generation_failed": True}` — pipeline 게이트(Task 4)가 이 마커를 감지해 발행을 차단한다 (결정 3).
     - body가 800자 미달인 기존 `return None` 경로(526-528)는 변경하지 않는다.
     - 본문(body)에는 재생성 제목을 끼워 넣지 않는다 — 제목은 dict로만 전달 (스코프 최소화).
  5. **`datetime` import 정리**: fallback 제거 후 `datetime` 사용처가 남아있지 않으면 import 제거 (grep으로 확인 후 판단, 다른 사용처 있으면 유지).
- **의존성**: Task 1 완료 후 (동일 파일, diff 충돌 방지)
- **Acceptance Check**:
  - `grep -n "추천 TOP5" pipelines/curation/writer.py` → 0건 (fallback 문자열 제거 확인)
  - `grep -n "datetime.now().year" pipelines/curation/writer.py` → **1건 이하** — writer.py:256(프롬프트 연도 삽입용)은 유지 필수, fallback(539) 제거 확인. 0건이 되어도 무방하나 256 유지가 정상
  - mock 기반 함수 검증 (실제 LLM 호출 금지 — `unittest.mock.patch("pipelines.curation.writer.ai_generate", ...)`):
    - 본문 응답에 H1 없음 + 재생성 응답 `"# 네덜란드 산양유 단백질 추천"` → 결과 title = `"네덜란드 산양유 단백질 추천"`, `title_generation_failed` 없음
    - 재생성 응답이 2회 모두 `"# 네덜란드 추천 TOP5 (2026년)"` → 결과 `title == ""`, `title_generation_failed is True`, 템플릿 제목이 결과에 없음
- **예상 소요**: 약 1.5h

---

### Task 3 [PRODUCTION CODE] — `_extract_description(body, title, keyword)` 헬퍼 분리
- **파일**: `pipelines/curation/writer.py:552-560` (인라인 description 추출) → 신규 헬퍼로 대체
- **설명** (확정 설계 결정 5):
  - `_extract_description(body, title, keyword)` 헬퍼 신규 추가, 기존 인라인 로직(552-560)을 호출로 교체:
    1. 본문을 줄 단위 분리, 빈 줄 / `#`, `!`, `[` 시작 줄 스킵 (기존 555번 동작 유지)
    2. **CoT 마커 줄 스킵**: `"우선"` 시작, `"사용자 요청"` 포함, `"제목 규칙"` 시작, `"제목 예시"` 시작 줄은 제외
    3. 첫 의미 문단: 스킵 후 줄들을 누적, 누적 길이 ≥ 20자 되는 지점에서 문단 확정, 문단 시작이 `"우선"`이 아닐 것
    4. **~150자 트렁케이션** (기존 160자 → 결정 5 기준 150자)
    5. 아무 문단도 못 찾으면 최후 fallback: `f"{keyword} 관련 상품 비교와 선택 가이드를 제공합니다."`
  - `title` 파라미터는 시그니처에 포함하되(결정 5), 사용 여부는 구현 판단 — 우선순위는 CoT 스킵 + 의미 문단 추출.
- **의존성**: Task 2 완료 후 (동일 파일)
- **Acceptance Check**:
  - 본문 첫 줄이 `"우선 사용자 요청은 네덜란드 산양유 단백질 추천입니다."` + 의미 문단 → description에 `"우선 사용자 요청"` 미포함, 의미 문단 텍스트 포함
  - 본문이 전부 CoT 스킵 패턴만 존재 → description == `"네덜란드 관련 상품 비교와 선택 가이드를 제공합니다."` (키워드 대입 확인)
  - `python -m pytest tests/curation -q` → 기존 스위트 green
- **예상 소요**: 약 0.5h

---

### Task 4 [PRODUCTION CODE] — pipeline.py 게시 전 제목 게이트 (thin wrapper)
- **파일**: `pipelines/curation/pipeline.py:889-921` (호출부 2곳: 889 본경로, 965 fallback 키워드 루프)
- **설명** (확정 설계 결정 3, 6, 계약 1; plan-checker MAJOR-2/MINOR-5 반영):
  1. 모듈 레벨 템플릿 패턴 추가: `TITLE_TEMPLATE_PATTERNS = [re.compile(r"추천\s*TOP\s*\d+", re.I), re.compile(r"\(\d{4}년\)$"), re.compile(r"BEST\s*\d+", re.I)]` — `_validate_title`(Task 2)과 동일 패턴 (결정 2, 연도-접두 `^\d{4}년` 제외)
  2. **thin wrapper 함수 신규 추가** — `_title_gate(blog_id, keyword, article) -> tuple[str | None, dict | None]`:
     - `article.get("title_generation_failed")` 또는 title이 빈 문자열 → `_record_failure(blog_id, "title_regenerate_failed", f"제목 재생성 실패 (2회 소진): {keyword}", keyword)` 호출 후 `(None, {"success": False, "reason": "title_blocked"})` 반환 (결정 3)
     - title이 `TITLE_TEMPLATE_PATTERNS` 중 하나라도 매치 → `_record_failure(blog_id, "title_blocked", f"템플릿 제목 패턴: {title}", keyword)` 후 `(None, {"success": False, "reason": "title_blocked"})` 반환 (결정 6)
     - 정상 → `(title, None)` 반환
  3. **호출부 2곳 적용**:
     - 본경로(889-917 부근): `article` None 체크 직후(890-892 블록 뒤)에 게이트 호출 → 에러 dict면 즉시 반환 (언어 검증 895 이전에 실행)
     - fallback 키워드 루프(965-968): 게이트 실패 시 `_record_failure`는 wrapper 내부에서 수행되므로 `continue`로 다음 fallback 키워드 진행
  4. **기존 로직 불변**: TITLE_BLOCKED dict 검사(912-917), `sanitize_title`(901), `_record_failure` 시그니처(655)는 수정하지 않는다. 반환은 기존 `{"success": bool, "reason": str}` plain dict 유지 — `PublishResult` namedtuple 도입은 **금지하지 않되**(결정 6), 도입 시 `dict(result._asdict())` 변환을 반환 직전에 적용해 호환성을 지킨다. 단순함을 위해 plain dict 유지를 권장.
- **의존성**: Task 2 (마커 `title_generation_failed` 계약 소비)
- **Acceptance Check** (plan-checker MAJOR-2 교정 — **wrapper 단위 시임** 사용, 실 HTTP 경로 mock 금지):
  - `_title_gate` 단위 검증: `_record_failure`를 `unittest.mock.patch("pipelines.curation.pipeline._record_failure")`로 패치하고
    - article dict에 title=`"네덜란드 추천 TOP5 (2026년)"` 전달 → `(None, {"success": False, "reason": "title_blocked"})` 반환 + `_record_failure` 호출 인자 stage=`"title_blocked"` 확인
    - article dict에 `title_generation_failed=True` 전달 → 동일 반환 + stage=`"title_regenerate_failed"` 확인
    - 정상 title → `(title, None)` 반환, `_record_failure` 미호출 확인
  - **주의**: `_run_inner` 전체 경유 테스트는 금지 — `collect_keyword`(실 쿠팡 HTTP), `enrich_products`(실 네이버 HTTP), `_upload_thumbnail`, `_title_is_duplicate` 등 실 HTTP/파일 경로가 개입되어 hermetic하지 않음. `_record_failure`가 실제 `data/content.db`(LEDGER_DB, pipeline.py:653)에 쓰는 것도 패치로 차단
  - `python -m pytest tests/curation -q` → 기존 스위트 green
- **예상 소요**: 약 1h

---

### Task 5 [TEST CODE] — 회귀 테스트 추가 (필수, Phase 43 실패 교훈 반영)
- **파일**: `tests/curation/test_title_hardening.py` (신규)
- **설명** (확정 설계 결정 7; plan-checker MAJOR-2/MINOR-5 반영):
  - 기존 fixture 재사용: `sample_products`, `temp_db` (tests/curation/conftest.py), `unittest.mock.patch("pipelines.curation.writer.ai_generate", ...)` — 실제 LLM/API 호출 금지.
  - 테스트 목록 (각 테스트는 결정 사항과 1:1 매핑):
    1. `test_h1_missing_triggers_regeneration`: 본문 생성 호출(no H1) + 재생성 호출(`# 네덜란드 산양유 단백질 추천`) mock → title이 재생성 제목이고 `(2026년)` 미포함 (SC-2). **mock 전략 (MINOR-5 교정)**: `side_effect` 시퀀스가 아니라 **kwargs 분기** (`tier=="economy"` → 재생성 응답, 그 외 → 본문 응답) 사용. 시퀀스 방식은 본문 글자수 재시도 루프(writer.py:509-524)가 2회 소모해 재생성 경로가 실행되지 않을 수 있음. **본문 mock 응답 길이는 ≥800자** 필수 (검증 스크립트 예시 ~1200자 충족; 800 미만이면 `return None` 경로로 테스트가 오해 가능 — INFO-4). 재생성 호출 파라미터가 결정 2와 일치하는지(`tier=="economy"`, `temperature==0.5`, `max_tokens==200`)도 assert.
    2. `test_regeneration_failure_returns_marker`: 재생성 2회 모두 `# 네덜란드 추천 TOP5 (2026년)` 반환 mock (kwargs 분기 + side_effect 반복) → `title == ""`, `title_generation_failed is True`, 반환 dict에 템플릿 제목 부재 (결정 3). **추가**: `ai_generate`가 `RuntimeError`를 raise하는 경우도 실패로 처리되어 마커 반환되는지 (MINOR-4).
    3. `test_description_rejects_cot_first_line`: 본문 시작 `"우선 사용자 요청은..."` + 의미 문단 → description에 `"우선 사용자 요청"` 부재, 의미 문단 포함 (SC-3).
    4. `test_title_gate_blocks_template_title`: **`_title_gate` wrapper 단위 테스트** (plan-checker MAJOR-2 교정 — `_run_inner` 경유 금지). `unittest.mock.patch("pipelines.curation.pipeline._record_failure")`로 패치, article dict에 title=`"네덜란드 추천 TOP5 (2026년)"` 전달 → 반환 `(None, {"success": False, "reason": "title_blocked"})`, `_record_failure` 호출 stage=`"title_blocked"` 확인. **publish_log/temp_db 조작 불필요** (게이트는 DB insert 전 차단) (SC-4).
    5. `test_title_gate_blocks_generation_failed`: article dict에 `title_generation_failed=True` → `(None, {"success": False, "reason": "title_blocked"})` + stage=`"title_regenerate_failed"` 확인 (결정 3, SC-4 보강).
  - 기존 테스트 파일(test_pipeline.py 등)은 수정하지 않는다. 필요 시 기존 패턴만 참조.
- **의존성**: Task 1-4 전부 (생산 코드가 구현된 상태에서만 통과 가능)
- **Acceptance Check**:
  - `cd /Users/twinssn/Projects/5000 && python -m pytest tests/curation/test_title_hardening.py -v` → 전부 통과 (5건 이상)
  - `python -m pytest tests/curation -q` → 전체 green (SC-5)
  - 테스트 실패 시 [TEST CODE]와 [PRODUCTION CODE] 수정을 구분해 보고 (AGENTS.md 보고 규칙 5)
- **예상 소요**: 약 1.5h

---

## Dependency Graph

```
Task 1 (writer.py 프롬프트) ─────────────┐
Task 2 (writer.py fallback 제거+재생성) ──┤ (동일 파일 순차 편집)
Task 3 (writer.py description 헬퍼) ─────┘
        │
        ▼
Task 4 (pipeline.py 게이트 — Task 2의 마커 계약 소비)
        │
        ▼
Task 5 (회귀 테스트 — Task 1~4 전부 통과 후에만 green 가능)
```

- **블로킹 관계**: T2 → T4 (마커 dict 계약), T1~T4 → T5 (회귀 테스트)
- **순차 편집 필수**: T1/T2/T3은 `writer.py` 동일 파일이므로 실행 순서 고정 (diff 충돌 방지)
- **병렬 가능 없음**: 전부 단일 파일 체인 — 순차 실행이 최소 비용

---

## Verification Loop (종단 검증 — 실행 순서대로)

```bash
cd /Users/twinssn/Projects/5000

# [1] SC-1: fallback 코드 제거 증명 (writer.py 한정 grep — 테스트 파일의 템플릿 문자열과 혼동 금지)
grep -n "추천 TOP5" pipelines/curation/writer.py || echo "SC-1 PASS: fallback 0건"
#   주의: datetime.now().year는 writer.py:256(프롬프트 연도 삽입용)에 정당하게 잔존하므로 별도 확인
grep -c "datetime.now().year" pipelines/curation/writer.py  # → 1건 (line 256 유지)이 정상, fallback(539) 제거만 확인
# [2] SC-2/SC-3: 함수 단위 검증 — 실제 LLM 호출 금지, 전부 mock (RESEARCH.md §5 교정 버전)
python -c "
from unittest.mock import patch
from pipelines.curation.writer import generate_curation_article

products = [{'product_name': f'테스트상품{i}', 'product_id': str(i), 'product_price': 1000*i,
             'product_image': '', 'product_url': '', 'category_name': '테스트', 'rank': i,
             'is_rocket': False, 'is_free_shipping': False, 'collected_at': '2026-08-01T00:00:00'}
            for i in range(1, 5)]
body = '# 네덜란드 산양유 단백질 추천 가이드\n\n' + ('네덜란드산 산양유 단백질 제품을 비교하는 내용입니다. ' * 40)

def fake_generate(system_prompt, user_prompt, tier='default', temperature=None, max_tokens=None):
    # 본문 생성(default)은 H1 없이 CoT로 시작, 재생성(economy)은 유효 H1 반환
    if tier == 'economy':
        return body
    return '우선 사용자 요청은 네덜란드 산양유 단백질 추천입니다.\n\n' + ('네덜란드산 산양유 단백질 제품을 비교하는 내용입니다. ' * 40)

with patch('pipelines.curation.writer.ai_generate', side_effect=fake_generate):
    r = generate_curation_article(keyword='네덜란드', products=products, blog_id='health-hugo')
    assert r['title'] == '네덜란드 산양유 단백질 추천 가이드', r['title']
    assert not r['title'].endswith('(2026년)'), r['title']
    assert '우선 사용자 요청' not in r['description'], r['description']
    print('[SC-2/SC-3 PASS] title:', r['title'])
    print('[SC-2/SC-3 PASS] desc:', r['description'][:100])
"

# [3] SC-4: 회귀 테스트 실행
python -m pytest tests/curation/test_title_hardening.py -v

# [4] SC-5: 기존 스위트 회귀 확인
python -m pytest tests/curation -q

# [5] 실 DB/로그 산뜰 검증 (파이프라인 실발행 후, 기록적 데이터는 수정하지 않음)
sqlite3 data/curation.db "SELECT title FROM publish_log WHERE id > 1980 AND title LIKE '%추천 TOP%' ORDER BY id DESC LIMIT 5;"
#   → 신규 발행(id > 1980) 기준 0건이면 PASS (1980 이하 기존 행은 Phase 47 스코프)
sqlite3 data/content.db "SELECT stage, COUNT(*) FROM publish_ledger WHERE stage IN ('title_regenerate_failed','title_blocked') GROUP BY stage;"
#   → 차단 경로가 신규 스테이지로 정상 기록되는지 확인```

**검증 성공 기준**: [1]~[4] 전부 PASS + [5] 신규 발행 템플릿 패턴 0건.

---

## Threat Model / Risks (이 계획이 실패할 수 있는 요인)

| 위험 | 영향 | 대응 |
|------|------|------|
| **LLM 비결정성 (default tier temp 0.85)** | 본문 생성 시 H1 누락이 여전히 발생 → 재생성 경로가 자주 발동되어 발행량 감소 | 재생성은 결정된 고정 파라미터(tier=economy, temp 0.5, max_tokens 200) 사용 + 2회 시도. 재생성 실패는 **의도된 fail-closed** — 템플릿 발행보다 발행 누락이 우선 |
| **tier fallback 체인 출력 형식 차이** | shared/ai_writer.py `generate` 내부의 tier fallback(default→fallback1-3→economy)이 재생성 호출의 tier를 덮어쓰거나 다른 형식으로 응답 | `_regenerate_title`은 `"# "` 제거 후 **첫 줄 평문도 수용**하도록 정규화, `_validate_title`가 최종 수용/거부 결정 |
| **`^\d{4}년` / `"우선"` 과차단** | "2026년 캠핑 장비 추천", "우선순위 추천" 같은 정상 제목이 재생성 검증과 게이트에서 거부될 수 있음 | **plan-checker MAJOR-1 교정 반영**: `^\d{4}년`(연도-접두)은 거부 패턴에서 **제외** — 시스템 프롬프트 제목 규칙 1(writer.py:286-287)이 연도-접두를 지시하므로, 거부하면 프롬프트 준수 제목 전부가 차단됨. 연도-괄호-끝(`\(\d{4}년\)$`)만 거부해 실제 fallback 시그니처에 대응. `"우선"` 부분 문자열 거부는 유지하되 "우선순위 추천" 같은 정상 제목 과차단은 의도된 fail-closed로 기록 |
| **본문 CoT 잔존 (MINOR-7)** | 본문 첫 줄 "우선 사용자 요청은..."이 제목만 재생성되고 body_md에는 그대로 남아 게시될 수 있음 | 계약 범위상 본문 scrub은 확정 설계에 없음 — 본 phase는 제목/description 품질까지만. 위험표에 명시적 기록 + 실행 시 선택적 additive로 `_sanitize_body`에 CoT 첫 줄 스킵 추가 가능 (스코프 판단) |
| **기존 테스트/동작 회귀** | writer 반환 shape 변경(마커 dict), description 길이 160→150 변경이 기존 테스트·호출부에 영향 | 마커는 `title_generation_failed` 키 **추가**만(기존 키 유지), description 150자는 기존 160자의 부분집합 — SC-5로 전 스위트 green 강제. 기존 테스트를 고쳐 통과시키는 대신 production 코드가 통과시켜야 함 (AGENTS.md 보고 규칙 5) |
| **grep 검증 오염** | 테스트 파일에 템플릿 문자열(`추천 TOP5 (2026년)`)이 존재 → 리포 전체 grep 시 SC-1 위반으로 오판 | fallback 제거 확인은 `pipelines/curation/writer.py` **파일 한정 grep**만 사용, 테스트 파일 문자열은 의도된 픽스처임을 명시 |
| **기록 데이터 잔존** | 기존 159건(전체 4.7%) 템플릿 제목 게시물이 publish_log/블로그에 남음 | 게이트는 신규 발행만 차단 — 기존 데이터 정리는 Hugo 템플릿 방어(Phase 47) 및 별도 스코프, 본 phase는 `id > 1980` 기준 검증 |
| **mock 불안정** | `generate_curation_article`이 본문 생성 시 ai_generate를 여러 번 호출(글자수 재시도) → 단순 return_value mock으로는 재생성 분기 테스트 불가 | 테스트는 `side_effect` 시퀀스 또는 `tier`/`temperature` kwargs 분기로 mock — Task 5에 명시, 이 파라미터 분기가 곧 재생성 호출 계약 검증 |
| **키워드 풀 문제 미해결** | `"네덜란드"` 국가명 단독 키워드 자체는 잔존 (오탐 상품 가능) | CONTEXT 스코프 제한(결정 8): 키워드 풀 전면 감사는 별도 phase. 본 phase는 제목/description 품질 차단까지만 |

---

## 산출물

- `pipelines/curation/writer.py` 수정 (Task 1-3)
- `pipelines/curation/pipeline.py` 수정 (Task 4)
- `tests/curation/test_title_hardening.py` 신규 (Task 5)
- 커밋 메시지: `feat(curation): harden title generation - remove fallback, add regeneration loop + gate + regression tests`
