# Phase 5: Post-Stabilization Enhancement — 복구 + 테마 + 모니터링

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 (버그 수정) 완료 후 후속 작업 3가지:
1. 이미 발행된 7/1 손상 글 수동 복구
2. Blowfish 테마 v2.x 업그레이드 (Phase 4에서 `featureimage:`로 되돌린 것을 `cover.image:` 원복)
3. 모니터링 & 관측 시스템 구축 (원래 Phase 2 계획이었으나 버그 수정으로 미뤄짐)

DOTALL regex 에지 케이스 확장은 테마 업그레이드 plan에 포함한다.
</domain>

<decisions>
## Implementation Decisions

### D-01: 7/1 글 수동 복구는 스크립트화
- travel4-hugo에 발행된 2개 손상 글을 찾아 일괄 수정하는 스크립트 작성
- 변경 항목: `cover.image:` → `featureimage:`, CTA HTML 추가, `{{}}` 제거
- 수정 후 Hugo rebuild + wrangler deploy

### D-02: Blowfish 테마 업그레이드는 git submodule 관리
- travel4-hugo의 Blowfish 테마가 git submodule인지 확인
- 업그레이드 후 `featureimage:`를 `cover.image:`로 되돌림 (Phase 4의 임시 fix 원복)
- travel1/2/3-hugo도 동일 테마 사용 시 함께 업그레이드

### D-03: 모니터링은 stdlib-first
- 외부 모니터링 도구 추가 없이 Python stdlib + 기존 인프라 활용
- 발행 글 자동 검증: Hugo build 후 HTML 파싱으로 CTA/썸네일/`{{}}` 감지
- Telegram 리포트: 발행 결과에 품질 메트릭 추가
- 알람 임계값: CTA 누락 = ERROR, `{{}}` 잔재 = WARNING

### D-04: DOTALL regex 에지 케이스 확장
- 현재 패턴: `## (함께|관련|추천) (읽어보기|읽을거리|글|포스트)`
- 누락 가능 패턴: `## 함께 보면 좋은 글`, `## 더 읽어보기`, `## 추천 게시물`
- 패턴 확장: `r"\n+##\s*(함께|관련|추천|더)\s*(읽어보기|읽을거리|글|포스트|게시물)"`

</decisions>

<canonical_refs>
## Canonical References

### Key Files
- `shared/publishers/hugo_writer.py` — `_build_frontmatter_blowfish()` (테마 업그레이드 후 `cover.image:`로 원복)
- `shared/publishers/hugo_writer.py` — `_clean_body()` (DOTALL regex 확장)
- `pipelines/travel/writer.py` — CTA 삽입 로직
- `dispatcher.py` — backoff, 결과 검증

### Prior Phase
- `.planning/phases/04-tap-publishing-stabilization/04-CONTEXT.md` — Phase 4 context
- `shared/publishers/hugo_writer.py` — 현재 `featureimage:` 사용 중

</canonical_refs>

<code_context>
## Existing Code Insights

### Blowfish frontmatter (현재 — Phase 4에서 변경)
```python
# Phase 4: featureimage:로 복원됨
if thumbnail_url:
    fm += 'featureimage: "' + thumbnail_url + '"\n'
```

### _clean_body DOTALL regex (현재)
```python
body_md = re.sub(r"\n+##\s*(함께|관련|추천)\s*(읽어보기|읽을거리|글|포스트).*", "", body_md, flags=re.DOTALL)
```

### travel4-hugo Hugo config 확인 필요
- site_path: /Users/twinssn/Projects/TAP/travel4-hugo
- themes 디렉토리 구조 확인
- Blowfish 버전 확인 (theme.toml)

</code_context>

<specifics>
## Specific Ideas

### Plan 05-01 실행 방법
```bash
# travel4-hugo 사이트 경로
cd /Users/twinssn/Projects/TAP/travel4-hugo

# 7/1 발행 글 찾기
find content/posts -name "index.md" -newer content/posts/경기-양평-.../index.md

# 각 파일 수정:
# 1. cover.image: → featureimage:
# 2. CTA HTML 추가 (cta_html 변수 내용)
# 3. {{}} 라인 제거
# 4. Hugo build + wrangler deploy
```

### 모니터링 체크리스트 예시
- `featureimage:` 또는 `cover.image:` 키 존재 여부
- `<div class="cta-box">` 존재 여부
- `{{` 패턴 미존재
- "지도에서 보기" 미존재
- 전체 글자수 2000자 이상

</specifics>

<deferred>
## Deferred Ideas

- **CI/CD 파이프라인** — GitHub Actions에 Hugo build + 검증 자동화
- **발행 품질 대시보드** — Web UI 필요 (과도한 엔지니어링)
- **크로스 블로그 일관성 검증** — 모든 travel 블로그를 동시에 검사

</deferred>

---

*Phase: 5 — Post-Stabilization Enhancement*
*Context gathered: 2026-07-01*
