# Phase 4: TAP Publishing Stabilization — Post-Refactoring Bug Fixes (Context)

**Gathered:** 2026-07-01
**Status:** Ready for execution

<domain>
## Phase Boundary

Phase 2/3 리팩토링(`d722aab0b`)에서 도입된 5개 회귀 버그를 수정한다.
모든 버그는 `shared/paths.py` + publisher.py → submodules 분할 과정에서 발생했다.

**핵심 원인:** `_clean_body()`가 HTML 태그를 제거하고, `_build_frontmatter_blowfish()`의 썸네일 키가 변경되었으며,
refactoring 과정에서 일부 후처리 로직이 유실되었다.

**영향 범위:** travel4-hugo (tour3.rotcha.kr), 잠재적으로 travel1/2/3-hugo

</domain>

<decisions>
## Implementation Decisions

### D-01: _clean_body에서 HTML 태그 제거 regex 제거
- **문제:** `shared/publishers/hugo_writer.py:96` — `re.sub(r"</?[^>]+>", "", body_md)`가 Trip.com CTA HTML을 제거
- **해결:** HTML 태그를 제거하는 regex를 제거한다. `_clean_body`는 빈 줄 정리(`\n{3,} → \n\n`)와 strip만 수행
- **이유:** body_md는 HTML을 포함할 수 있음 (CTA, 이미지, iframe 등). 모든 HTML을 무조건 제거하면 부작용이 큼

### D-02: DOTALL regex로 빈 템플릿 제거 로직 복원
- **문제:** 옛 `_clean_body()(publisher.py)`는 `re.sub(r"\n+##\s*(함께|관련|추천)\s*(읽어보기|읽을거리|글|포스트).*", "", body_md, flags=re.DOTALL)`로 AI 생성 가짜 내부링크를 제거했으나 refactoring 후 사라짐
- **해결:** `writer.py:688-691`의 `## 함께 읽어보기` 제거와 별도로, `publisher.py`의 `publish()`에서 DOTALL regex로 빈 템플릿(`{{}}`)을 제거
- **위치:** `shared/publisher.py`의 `publish()` 함수 또는 `shared/publishers/hugo_writer.py`의 `_write_hugo_post()` 전처리

### D-03: 지도보기 평문 regex 추가
- **문제:** `writer.py:724-727`의 regex는 마크다운 링크 `[네이버 지도에서 보기](url)`만 매칭, 평문은 미매칭
- **해결:** 평문 "지도에서 보기"도 매칭하는 regex 패턴 추가 (마크다운 링크 + 평문 모두)
- **패턴 예시:** `re.sub(r"\s*지도에서\s*보기\s*", "", content)` — 간격/줄바꿈 허용

### D-04: no_result backoff 메커니즘
- **문제:** `dispatcher.py:512-513` — pipeline이 None 반환 시 매 스케줄마다 재시도
- **해결:** blog_id별 실패 시간을 기록하고, N분 이내 재시도 방지
- **방법:** 메모리 dict + 파일 기반 상태 저장 (JSON), blog_id별 last_failure_at + cooldown_minutes

### D-05: 썸네일 키 복원 (featureimage:)
- **문제:** `_build_frontmatter_blowfish()`가 `featureimage:`(구 Blowfish)에서 `cover:`/`image:`(신 Blowfish)로 변경
- **해결:** `featureimage:` 키로 되돌린다. 테마 업그레이드는 별도 이슈
- **예외:** Blowfish 테마가 이미 `cover.image:`를 지원하는 블로그는 유지 (stock-hugo 등)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Root Cause Commit
- `d722aab0b` — `shared/paths.py` + publisher submodule split
- `67cc067dc` — publisher.py → hugo_writer/deploy/content_enhancer 분할

### Affected Files
- `shared/publishers/hugo_writer.py` — `_clean_body()` (line 92-98), `_build_frontmatter_blowfish()` (line 67-89)
- `shared/publisher.py` — `publish()` 함수 (line 855-893, CTA 전달 경로)
- `pipelines/travel/writer.py` — CTA 삽입 (line 712-719), 지도보기 regex (line 724-727)
- `dispatcher.py` — `no_result` 처리 (line 512-513)

### Evidence (DB)
- `stap_content.db` — `SELECT * FROM articles WHERE blog_id='travel4-hugo' AND created_at > '2026-06-29'`
- 건전한 글: June 30 13:50 KST (`경기 양평 다산유적지...`) — `featureimage:` + CTA 정상
- 손상된 글: July 1 07:10 KST (`경북 무섬마을부터...`) — `cover.image:` + CTA 제거됨

### Prior Phase
- `.planning/phases/03-hardening-stability-decoupling/03-CONTEXT.md` — Phase 3 (paths refactoring)

</canonical_refs>

<code_context>
## Existing Code Insights

### _clean_body (손상 코드)
```python
# hugo_writer.py:92-98
def _clean_body(body_md):
    if not body_md:
        return body_md
    body_md = re.sub(r"</?[^>]+>", "", body_md)  # ← 모든 HTML 제거 (버그 원인)
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)
    return body_md.strip()
```

### _build_frontmatter_blowfish (변경된 썸네일 키)
```python
# hugo_writer.py:82 (신규)
    fm += "cover:\n"
    fm += '  image: "' + thumbnail_url + '"\n'
# old publisher.py (구)
    fm += 'featureimage: "' + thumbnail_url + '"\n'
```

### writer.py CTA 삽입 (712-719)
```python
cta_html = """
<div class="cta-box">
  <p style="margin:0;font-size:1.1rem;">여행 숙소를 찾고 계신가요?</p>
  <a href="https://kr.trip.com/?Allianceid=..." target="_blank" rel="nofollow">트립닷컴에서 최저가 확인하기</a>
</div>
"""
content = content.rstrip() + "\n\n" + cta_html
```

### Dispatcher no_result (512-513)
```python
result = _run_pipeline(cfg)
if result is None:
    status = "no_result"
```
→ backoff 없음. 다음 스케줄에서 동일 pipeline 재시도

</code_context>

<specifics>
## Specific Ideas

### 실행 순서
1. Bug 5 (썸네일) + Bug 1 (CTA) — `hugo_writer.py`만 수정, 영향도 가장 큼
2. Bug 2 (`{{}}`) — DOTALL regex 복원, writer.py/publisher.py 연계
3. Bug 3 (지도보기) — writer.py regex만 추가
4. Bug 4 (no_result) — dispatcher.py backoff 추가, 영향도 가장 작음

### 검증 방법
- 각 버그 수정 후 `python -c "from pipelines.travel.writer import ..."` import 테스트
- travel4-hugo dry-run: `python dispatcher.py --blog travel4-hugo --dry-run`
- DB 확인: 발행된 글의 thumbnail_url NULL 여부, body_md CTA 포함 여부

</specifics>

<deferred>
## Deferred Ideas

- **Blowfish 테마 업그레이드** — `featureimage:` → `cover.image:` 호환되도록 Hugo 테마 업데이트
  현재는 `featureimage:`로 되돌리는게 안전. 테마 업그레이드는 별도 작업 필요.
- **Phase 5 (Monitoring)** — bug fix 완료 후 구조화된 모니터링/관측 추가
- **TAP 전용 E2E 테스트** — 발행물 자동 검증 (스크린샷/HTML 파싱)

</deferred>

---

*Phase: 4 — TAP Publishing Stabilization*
*Context gathered: 2026-07-01*
