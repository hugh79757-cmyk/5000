# RESEARCH.md — Phase 54: Curation Title Generation Hardening

> 상태: 리서치 완료 (2026-08-01, 이전 세션의 코드 검증 + DB/로그 증거 기반)
> 작성 기준: 코드 직접 판독 + SQLite 쿼리 + 로그 grep — 전부 [검증됨]

---

## 1. 문제 정의

### 1.1 증상

"네덜란드 추천 TOP5 (2026년)" — health-hugo에 발행된 제목. 검색 의도 오류(국가명이 추천 대상으로 오독) + 템플릿 스팸 패턴 + description에 프롬프트 누출.

### 1.2 루트코즈 체인 (전체 경로 확인됨)

```
1. _build_system_prompt(writer.py:255)에 H1 출력 형식 지시 없음
   → 2. deepseek-v4-flash (temp 0.85)가 CoT로 시작, "# 제목" 누락
       → 3. writer.py:530-537 H1 추출 실패 (title = "")
           → 4. writer.py:538-539 하드코딩 fallback 발동
               → 5. "네덜란드 추천 TOP5 (2026년)" 발행
                   → 6. writer.py:552-560 description = CoT 첫 문장 누출
```

### 1.3 핵심 증거

| 증거 | 위치 | 상태 |
|------|------|------|
| fallback 하드코딩 `f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` | writer.py:538-539 | [검증됨] 직접 판독 |
| 발행 제목 = fallback 결과와 정확 일치 | publish_log id=1980 (2026-08-01T09:31:52) | [검증됨] sqlite3 |
| H1 없음 + CoT 누출 (본문 = LLM 원본 응답) | CUAP/health-hugo/content/posts/네덜란드-추천-top5-2026년/index.md | [검증됨] 직접 판독 |
| description = "우선 사용자 요청은..." (CoT 첫 문장) | 위 파일 frontmatter description | [검증됨] |
| 원본 키워드 = "네덜란드" (health-hugo 풀) | keywords.py:598 | [검증됨] |
| LLM = deepseek-v4-flash, temp 0.85 | config/models.yaml default tier | [검증됨] |
| 재발 시점 로그 | scheduler.log:218459 `[OUT] {"success": true, "title": "네덜란드 추천 TOP5 (2026년)"}` | [검증됨] |
| 회귀 테스트 부재 | grep "test.*title" — 게시 전 제목 품질 검사 0건 | [부분검증] |

## 2. 원인 요인 상세

### 2.1 근본: 프롬프트에 출력 형식 미지정 (CRITICAL)

- `_build_system_prompt`(writer.py:255-385): 역할/페르소나(BLOG_EXTRA_RULES:37)/AIDA 퍼널/제목 규칙 4패턴/길이 25~55자/브랜드 포함/가성비 금지 — 상세하나 **"맨 첫 줄에 # 제목" 지시 없음**
- `_build_user_prompt`(writer.py:390-449): 상품 4개 JSON + AIDA 순서 — 출력 형식 미지정
- 결과: H1 추출(writer.py:530-537)이 LLM의 "자발적" H1에 의존 → 불안정

### 2.2 fallback 하드코딩 (CRITICAL)

- writer.py:538-539: H1 없으면 무조건 `{keyword} 추천 TOP5 ({year}년)`
- "추천 TOP 5" 패턴 게시물: 전체 3,364건 중 159건(4.7%), 최근 30일 844건 중 111건(13%) — 하루 평균 3.7건 신규 발생 중
- 상품 수(4개)와 "TOP5" 불일치

### 2.3 CoT/프롬프트 누출 (HIGH)

- `_sanitize_body`(writer.py:196)에 누출 필터 없음 (금지어 치환만)
- description 추출(writer.py:552-560): 본문 첫 2문장 무검증 → CoT 첫 문장("우선 사용자 요청은...")이 그대로 meta description
- 발행물 본문에 프롬프트 텍스트 + 모델 사고 과정 통째로 게시됨

### 2.4 발행 전 제목 게이트 부재 (HIGH)

- pipeline.py:906 `sanitize_title(article["title"])` — 길이/특수문자 정규화만
- pipeline.py:912-921 TITLE_BLOCKED — health-hugo는 목록 미등록 → 우회
- **큐레이션 파이프라인에 `validate_post` 호출 0건** (grep 확인) — travel:326/senior:255/car:297/rap:1088은 호출
- publisher.py:827-846 발행 후 `validate_post_html`은 텔레그램 알림만, 차단/롤백 없음

### 2.5 키워드 풀 문제 (MEDIUM)

- keywords.py:598 `"네덜란드"` 국가명 단독 키워드 (산양유 단백질 원산지 유래)
- "뉴질랜드", "개월분" 등 유사 단편 키워드 인접 존재
- 쿠팡 API가 원산지 기반 상품(네덜란드산 산양유, 국기, 치즈 등 오탐 포함) 반환

## 3. 기존 시도 실패 원인 (Phase 43)

- Phase 43(2026-07-24) "Title Generation Fix": max_tokens 제거 + temp 0.85 + timeout 300s — **프롬프트/fallback 로직 자체는 미수정**
- 회귀 테스트 부재 → 2026-08-01 재발 (publish_log id=1980)
- 교훈: 같은 버그가 재발하지 않으려면 **회귀 테스트를 phase 범위에 포함**해야 함

## 4. 수정 방향 (검증된 설계)

### 4.1 writer.py:538-539 — fallback 제거 + 제목 전용 재생성

- H1 누락 시 `ai_generate`(shared/ai_writer.py:71, `generate`를 writer.py:15에서 alias)로 제목 재생성
- 재생성 조건: 첫 줄 # 제거 + 길이 10~60자 + CoT 패턴 거부("우선", "사용자 요청") + **템플릿 패턴 거부**(`추천\s*TOP\s*\d+`, `BEST\s*\d+`, `\(\d{4}년\)$` — 연도-괄호-끝)
- **참고 (2026-08-01 plan-checker MAJOR-1 교정 적용)**: `^\d{4}년`(연도-접두)은 거부하지 않음 — 시스템 프롬프트 제목 규칙 1(writer.py:286-287)이 `[연도]년 [월]월 [제품명] 추천` 형태를 지시하므로 거부하면 프롬프트 준수 제목이 전부 차단됨. 실제 fallback 시그니처는 `추천\s*TOP\s*\d+`와 `\(\d{4}년\)$`로 포착됨. (이하 상세는 CONTEXT.md 확정 설계 결정 2 참조)
- max 2회 retry, 실패 시 발행 중단(TITLE_BLOCKED 상태 반환) — hard fallback 금지
- 재생성 호출에 `tier="economy"` 지정 (models.yaml economy tier = deepseek-paid)

### 4.2 writer.py:255 — 시스템 프롬프트에 H1 형식 + CoT 금지

- "응답의 맨 첫 줄에 반드시 # 마크다운 H1 제목" 지시
- "{키워드} 추천 TOP N (연도년)" 형태 나열형 제목 금지
- "우선 사용자 요청은~", "제목 규칙을 확인해야 한다~", "제목 예시를 만들어보자~" 등 CoT/검토 텍스트 출력 금지

### 4.3 writer.py:552-560 — `_extract_description()` 분리

- CoT 마커 제거 후 첫 의미 문단 추출 (20자 이상, '우선' 시작 제외)
- 150자 내외 트렁케이션
- 최후 fallback: `{keyword} 관련 상품 비교와 선택 가이드를 제공합니다.`

### 4.4 pipeline.py — 게시 전 제목 게이트 (thin wrapper)

- 기존 `TITLE_BLOCKED` dict + `{"success": False, "reason": ...}` 반환 패턴 위에 wrapper 추가
- `PublishResult` namedtuple 반환하되 `dict(result._asdict())`로 하위 호환 — 호출부 최소 변경
- 차단 시 `_record_failure(blog_id, "template_title", ...)` + `{"success": False, "reason": "title_blocked"}` 반환

### 4.5 keywords.py — `get_keyword_metadata()` (옵션, 스코프 판단 필요)

- `KEYWORD_COMPANION = {"네덜란드": "산양유 단백질", "뉴질랜드": "프로바이오틱스"}` 매핑
- `get_keyword_metadata(keyword) -> dict | None` — 없으면 None, retry 프롬프트에만 메타데이터 섹션 삽입
- **이 항목은 Phase 54의 필수 스코프가 아님** — fallback 제거만으로 템플릿 재발은 차단됨. 키워드 풀 감사는 별도 phase 권장
- > **Phase 54에서 미적용** (2026-08-01 실행 시 W2 결정): `get_keyword_metadata`는 follow-up phase로 이연. Retry prompt는 keyword metadata 없이 동작하며, metadata enrichment는 별도 capability로 취급.

## 5. 검증 방법 (수정된 스크립트 — 원 제안안의 오류 교정)

```bash
# 함수명 교정: generate_post → generate_curation_article (writer.py:449)
python -c "
from pipelines.curation.writer import generate_curation_article
result = generate_curation_article(keyword='네덜란드', products=SAMPLE_PRODUCTS, blog_id='health-hugo')
print('title:', result['title'])
print('desc:', result['description'][:100])
assert not result['title'].endswith('(2026년)')
assert '우선 사용자 요청' not in result['description']
"

# DB 확인: psql → sqlite3 (data/curation.db)
sqlite3 data/curation.db "SELECT title FROM publish_log WHERE keyword='네덜란드' ORDER BY id DESC LIMIT 3;"

# 로그 확인
grep "\[title\]" logs/scheduler.log | tail
```

## 6. 참조 파일

- `/Users/twinssn/Projects/5000/pipelines/curation/writer.py` (:37 BLOG_EXTRA_RULES, :196 _sanitize_body, :255 _build_system_prompt, :390 _build_user_prompt, :449 generate_curation_article, :530-539 H1 추출+fallback, :552-560 description)
- `/Users/twinssn/Projects/5000/pipelines/curation/pipeline.py` (:906 sanitize_title, :912-921 TITLE_BLOCKED, :444 _filter_irrelevant_products)
- `/Users/twinssn/Projects/5000/pipelines/curation/keywords.py` (:598)
- `/Users/twinssn/Projects/5000/shared/ai_writer.py` (:71 generate — `generate(system_prompt, user_prompt, tier="default", temperature=None, max_tokens=None)`)
- `/Users/twinssn/Projects/5000/shared/validators.py` (:291 validate_post — curation 미사용)
- `/Users/twinssn/Projects/5000/config/models.yaml` (default/fallback1-3/economy)
- `/Users/twinssn/Projects/5000/data/curation.db` (publish_log, products)
- `/Users/twinssn/Projects/CUAP/health-hugo/content/posts/네덜란드-추천-top5-2026년/index.md` (증거 게시물)
