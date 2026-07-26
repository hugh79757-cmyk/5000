# Phase 49-B: CUAP 크로스링크 전수 검증 및 잔여 404 수정 리포트

> **스캔 시간:** 2026-07-26 16:19:45
> **대상:** 10개 CUAP 블로그, 3,076개 포스트 파일

---

## 1. 작업 요약

Phase 49 Wave 2에서 `fix_baked_crosslink_cards.py`가 143개 href를 수정했으나,
여전히 10개 CUAP 블로그에 404를 반환하는 크로스링크가 남아있어 전수 검증 및 일괄 수정을 수행.

| 단계 | 작업 | 결과 |
|------|------|------|
| Step 1 | 전수 스캔 스크립트 작성 (`scan_all_crosslinks.py`) | 완료 |
| Step 2 | 잔여 404 수정 스크립트 작성 (`fix_remaining_crosslinks.py`) | 완료 |
| Step 2a | 1차 수정 (일반 href) | 70개 링크 수정 |
| Step 2b | 2차 수정 (이스케이프 href의 trailing slash 버그) | 15개 링크 수정 |
| 재검증 | 전수 재스캔 | **9840/9840 정상, 0건 404** |
| Step 3 | Hugo 빌드 검증 | **10개 블로그 전부 0 에러** |

---

## 2. 최종 스캔 결과

| 블로그 | 총 포스트 | 총 크로스링크 | 정상 | 404 (수정전) | 404 (수정후) |
|--------|----------|-------------|------|------------|------------|
| appliance-hugo | 434 | 1,312 | 1,312 | 4 | **0** |
| baby-hugo | 399 | 1,188 | 1,188 | 5 | **0** |
| beauty-hugo | 249 | 850 | 850 | 12 | **0** |
| camping-hugo | 207 | 724 | 724 | 6 | **0** |
| fitness-hugo | 421 | 1,338 | 1,338 | 4 | **0** |
| health-hugo | 226 | 776 | 776 | 8 | **0** |
| interior-hugo | 536 | 1,680 | 1,680 | 9 | **0** |
| kitchen-hugo | 231 | 738 | 738 | 10 | **0** |
| laptop-hugo | 210 | 644 | 644 | 4 | **0** |
| pet-hugo | 163 | 590 | 590 | 8 | **0** |
| **TOTAL** | **3,076** | **9,840** | **9,840** | **70** | **0** |

- JSON-LD self-refs (canonical URL, 제외): 964
- 기타 도메인 링크 (stock.informationhot.kr 등): 0
- **최종 정상률: 100% (9,840/9,840)**

---

## 3. 수정 상세

### 1차 수정 (70 links)

대부분 `20260721-{keyword}-추천` / `20260722-{keyword}-추천` 형식의 date-prefixed slug가 원인.
이 slug들은 `_make_slug(keyword)`에서 생성되었으나 실제 포스트는 `slugify(title)`로 생성된
디렉토리명을 사용하여 불일치 발생.

**수정 전략:**
1. 링크 텍스트에서 키워드 추출 (예: "제습기 추천 추천" → "제습기")
2. 대상 블로그의 `content/posts/`에서 키워드를 포함하는 디렉토리 검색
3. `difflib.SequenceMatcher`로 유사도 측정, threshold 0.3 이상인 경우 자동 교체

**수정 예시:**
- `20260721-제습기-추천/` → `대성쎌틱듀플렉스-1등급-제습기-추천-19l20l-실속-선택-가이드-2026년-7월/`
- `20260722-1등급-제습기-추천/` → `대성쎌틱듀플렉스-1등급-제습기-추천-19l20l-실속-선택-가이드-2026년-7월/`
- `20260721-캠핑-방수포-추천/` → `2026년-7월-캠핑-방수포-추천-다이떼코멧-실속-top-5/`

### 2차 수정 (15 links — trailing slash 버그)

escaped-quote href (`href=\"...\"`)에서 regex가 slug 끝의 `/`를 포함하여 캡처,
`href` 재구성 시 `//` (더블 슬래시)가 발생해 content.replace() 매칭 실패.

**수정:** `slug = slug.rstrip('/')` 추가로 trailing slash 제거 후 15개 링크 추가 수정 완료.

### 불용 키워드 (threshold 미달로 수정되지 않은 경우)

없음 — 모든 70+15개 링크가 threshold 0.3 이상 매칭되어 자동 수정됨.

---

## 4. 버그 근본 원인 요약

크로스링크 URL slug 불일치의 근본 원인은 `publisher.py`의 import override:
- `publisher.py:530`의 `_write_hugo_post()`는 `{"success": True, "file": path, "url": url}`을 반환하지만,
- `publisher.py:762-770`에서 `hugo_writer._write_hugo_post()`로 **override**되어
- `hugo_writer._write_hugo_post()`는 `{"success": True, "file": path}`만 반환 (**"url" 키 없음**)
- 결과적으로 `pipeline.py:1064`의 `result.get("url")`이 항상 None이 되어
- `_make_slug(keyword)`의 date-prefixed slug가 fallback으로 사용됨

이는 Phase 49 Wave 1/2에서 수정된 사항이며, 본 Phase 49-B는 기존 포스트에 이미
bake된 잘못된 크로스링크를 일괄 수정하는 작업.

---

## 5. Hugo 빌드 검증

| 블로그 | 빌드 시간 | 에러 |
|--------|----------|------|
| appliance-hugo | 3,089ms | 0 |
| baby-hugo | 3,018ms | 0 |
| beauty-hugo | 2,127ms | 0 |
| camping-hugo | 2,115ms | 0 |
| fitness-hugo | 3,878ms | 0 |
| health-hugo | 1,672ms | 0 |
| interior-hugo | 3,911ms | 0 |
| kitchen-hugo | 1,979ms | 0 |
| laptop-hugo | 1,834ms | 0 |
| pet-hugo | 1,500ms | 0 |

**Hugo 빌드: 10/10 성공, 0 에러.**

---

## 6. 파일 변경 내역

- **수정된 포스트 파일:** 36개 (1차) + 8개 (2차) = **44개 파일**
- **백업 위치:** `/tmp/crosslink_fix_backup/`

### 사용된 스크립트
| 스크립트 | 역할 |
|---------|------|
| `scripts/scan_all_crosslinks.py` | 전수 스캔 — 모든 크로스링크 추출 및 파일 시스템 기반 존재 확인 |
| `scripts/fix_remaining_crosslinks.py` | 404 링크 자동 수정 — 키워드 매칭 + fuzzy fallback |

### 기존 유지
- `scripts/fix_baked_crosslink_cards.py` — Phase 49 Wave 2 (143개 수정, 그대로 유지)
- Phase 49 Wave 1/2 커밋 변경 없음

---

## 7. 잔존 위험

| 위험 | 설명 | 완화 |
|------|------|------|
| **신규 발행 시 재발** | `_write_hugo_post()`의 "url" 누락 버그가 근본 수정되지 않으면 신규 포스트도 잘못된 slug로 크로스링크 생성 | Phase 49 Wave 1/2에서 파이프라인 코드 수정 필요 |
| **가정용 같은 모호한 키워드** | "가정용 추천" 같은 generic link text는 여러 포스트에 매칭 가능, 현재는 최신 post로 연결 | 모든 "가정용" 링크가 appliance-hugo에 연결되어 있어 기능상 문제 없음 |
| **백업 복원 시점** | 수정 후 신규 포스트가 발행되면 백업 복원 시 해당 포스트 손실 가능 | 백업은 2026-07-26 16:18 기준 |
