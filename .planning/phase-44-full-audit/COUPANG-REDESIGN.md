# Coupang Affiliate Redesign — 설계 수정안

**작성일**: 2026-07-25  
**배경**: 현재 `_post_process`에서 H2 과다 발생, 브랜드 키워드 강제 삽입 무의미, 함께 읽어보기 중복 문제 해결

---

## 1. 핵심 설계 변경사항

| 항목 | 기존 | 변경 |
|------|------|------|
| **쿠팡 제휴 섹션 제목** | `## 여행 준비에 도움되는 추천 용품` (H2) | `<p class="coupang-section-title">여행 준비에 도움되는 추천 용품</p>` (p + CSS) |
| **함께 읽어보기** | `_post_process`에서 H2로 강제 삽입 | **완전 제거** — 블로우피쉬 테마 `relatedPosts` 옵션으로 자동 처리 |
| **브랜드 키워드 강제** | 프롬프트/치환으로 억지 삽입 | **삭제** — 검증 불가, 수익 직결 아님 |
| **상품 진열** | 랜덤 키워드 → 1개씩 검색 → 가격순 1개 선택 | **쿠팡 API 1회 호출로 3개 상품 확보** (카테고리별 분배) |
| **중복 방지** | 단순 productId 체크 | **세션 레벨 + 블로그 레벨 중복 방지** (productId + 상품명 유사도) |

---

## 2. 새로운 아키텍처

### 2.1 데이터 플로우

```
generate_content()
    │
    ├─► AI 본문 생성 (H2 4개, H3 3개, 2500자+)
    │
    ├─► _validate_and_retry() → 품질 게이트
    │
    ├─► _post_process()
    │       ├─ 문체 통일, 금지어 치환, 이동시간 제거
    │       ├─ ✅ H2 과다 방지 (최대 4개 강제 컷)
    │       ├─ ✅ 쿠팡 섹션: p.tag + class="coupang-section" (H2 아님)
    │       └─ ❌ 함께 읽어보기 삽입 로직 완전 삭제
    │
    └─► CoupangAffiliate.get_product_cards(blog_id, count=3)
            │
            ├─ 키워드 3개 선정 (블로그별 카테고리 분배)
            ├─ 배치 검색 API 1회 호출 (또는 병렬 3회)
            ├─ 필터링: 관련도 + 가격 + 중복 제거
            ├─ 결과: 상품 3개 (카테고리별 1개씩 보장 시도)
            └─ HTML 반환: <div class="coupang-products">...</div>
```

### 2.2 CoupangAffiliate 클래스 리팩토링

```python
# shared/coupang_travel.py — 핵심 변경

class CoupangAffiliate:
    def __init__(self):
        self._session_cache = {}  # productId → {name, price, link, image, category}
        self._blog_used = {}      # blog_id → set(productId)
    
    def get_product_cards(self, blog_id: str, count: int = 3) -> str:
        """
        블로그당 3개 상품 카드 반환 (HTML 문자열)
        - 카테고리 분배: 텐트/의자/랜턴 등 골고루
        - 중복 방지: 세션 캐시 + 블로그별 사용 이력
        - 반환: <div class="coupang-product-grid">...</div>
        """
    
    def _search_batch(self, keywords: list) -> list:
        """여러 키워드 병렬/순차 검색 → 통합 결과 반환"""
    
    def _deduplicate(self, products: list, blog_id: str) -> list:
        """productId + 상품명 유사도(Levenshtein > 0.8) 중복 제거"""
    
    def _distribute_by_category(self, products: list, count: int) -> list:
        """카테고리별 1개씩 우선 배정, 부족하면 나머지 채움"""
```

### 2.3 HTML 출력 구조 (기존 H2 리스트 → CSS Grid)

```html
<!-- 기존: H2 + ul list -->
## 여행 준비에 도움되는 추천 용품
- [상품명](링크) — 12,340원
- [상품명](링크) — 56,780원

<!-- 변경: p.title + div.grid -->
<p class="coupang-section-title">여행 준비에 도움되는 추천 용품</p>
<div class="coupang-product-grid">
  <article class="coupang-product-card">
    <a href="..." target="_blank" rel="nofollow">
      <img src="..." alt="상품명" loading="lazy">
      <span class="coupang-product-name">상품명</span>
      <span class="coupang-product-price">12,340원</span>
    </a>
  </article>
  <article class="coupang-product-card">...</article>
  <article class="coupang-product-card">...</article>
</div>
<p class="coupang-disclaimer">이 포스팅은 쿠팡 파트너스 활동의 일환으로...</p>
```

### 2.4 필요 CSS (테마 또는 인라인)

```css
/* 블로우피쉬 테마 custom.css 또는 인라인 주입 */
.coupang-section-title {
  font-size: 1.125rem;    /* H3~H4 크기 */
  font-weight: 600;
  margin: 2rem 0 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--primary-color);
}
.coupang-product-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin: 1rem 0 2rem;
}
@media (max-width: 768px) {
  .coupang-product-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .coupang-product-grid { grid-template-columns: 1fr; }
}
.coupang-product-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--card-bg);
  transition: transform 0.2s, box-shadow 0.2s;
}
.coupang-product-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.coupang-product-card img {
  width: 100%;
  height: 160px;
  object-fit: cover;
}
.coupang-product-name {
  display: block;
  padding: 0.75rem;
  font-size: 0.875rem;
  line-height: 1.4;
}
.coupang-product-price {
  display: block;
  padding: 0 0.75rem 0.75rem;
  font-weight: 700;
  color: var(--primary-color);
}
.coupang-disclaimer {
  font-size: 0.75rem;
  color: var(--muted-color);
  text-align: center;
  margin-top: 1rem;
}
```

---

## 3. 구현 계획 (PLAN)

### 3.1 Phase 44-01: CoupangAffiliate 리팩토링
- [ ] `get_product_cards(blog_id, count=3)` 메서드 신규 작성
- [ ] 배치 검색 + 중복 제거 + 카테고리 분배 로직
- [ ] HTML 템플릿 분리 (jinja2 또는 f-string 템플릿)
- [ ] 세션 캐시(`_session_cache`) + 블로그 사용 이력(`_blog_used`) 구현

### 3.2 Phase 44-02: _post_process 정리
- [ ] H2 과다 방지: `len(_h2_positions) > 4` → 4개 컷 (기존 5개 → 4개)
- [ ] 쿠팡 섹션: H2 → `<p class="coupang-section-title">` 변경
- [ ] 함께 읽어보기 삽입 로직 **완전 삭제** (블로우피쉬 `relatedPosts` 옵션 의존)
- [ ] 브랜드 키워드 강제 치환(`_REPLACE_MAP`에서 "콜맨" 등) **삭제**

### 3.3 Phase 44-03: writer.py 연동
- [ ] `_enrich_with_nearby` → `_enrich_with_coupang`로 통합/대체
- [ ] `generate_content()`에서 `coupang.get_product_cards(blog_id, 3)` 호출
- [ ] 반환된 HTML을 본문 마지막에 append

### 3.4 Phase 44-04: 검증 및 테스트
- [ ] dry-run 3회/블로그 실행 → H2=4개, 쿠팡 섹션 p태그, 중복 상품 0개 확인
- [ ] CSS 렌더링 확인 (모바일/데스크탑 그리드)
- [ ] API Rate Limit 준수 확인 (분당 50회 내)

---

## 4. 중복 방지 상세 로직

```python
def _deduplicate(self, products: list, blog_id: str) -> list:
    unique = []
    seen_ids = set()
    seen_names = []  # 상품명 유사도 체크용
    
    for p in products:
        pid = p.get("productId")
        name = p.get("productName", "")
        
        # 1) productId 중복
        if pid in seen_ids or pid in self._blog_used.get(blog_id, set()):
            continue
        
        # 2) 상품명 유사도 (Levenshtein ratio > 0.8)
        is_dup = False
        for existing_name in seen_names:
            if self._similarity(name, existing_name) > 0.8:
                is_dup = True
                break
        if is_dup:
            continue
        
        seen_ids.add(pid)
        seen_names.append(name)
        unique.append(p)
    
    # 블로그별 사용 이력 업데이트
    self._blog_used.setdefault(blog_id, set()).update(seen_ids)
    return unique

def _similarity(self, a: str, b: str) -> float:
    """간단한 유사도: 공통 토큰 비율 (또는 difflib.SequenceMatcher)"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()
```

---

## 5. 블로그별 키워드 카테고리 재설계 (브랜드 제거)

```python
# 여행 블로그: 용도별 분배로 3개 카테고리에서 1개씩
TRAVEL_KEYWORD_MAP = {
    "travel-hugo": {
        "shelter": ["캠핑 텐트", "타프", "그늘막"],           # 1순위
        "comfort": ["캠핑 의자", "캠핑 테이블", "캠핑 매트"],  # 2순위
        "utility": ["캠핑 랜턴", "캠핑 화로대", "캠핑 코펠"],  # 3순위
    },
    "travel1-hugo": {
        "outdoor": ["여행용 돗자리", "접이식 의자", "휴대용 선풍기"],
        "tech": ["여행용 보조배터리", "셀카봉 삼각대", "방수팩"],
        "comfort": ["목베개", "여행용 물병", "여행용 파우치"],
    },
    "travel2-hugo": {
        "gear": ["등산 배낭", "트레킹 폴", "등산화"],
        "tech": ["액션캠", "보조배터리", "방수 케이스"],
        "comfort": ["압축 수건", "등산 양말", "자외선 차단 모자"],
    },
    "travel3-hugo": {
        "container": ["보온 도시락", "스텐 텀블러", "식기 세트"],
        "cooking": ["휴대용 버너", "코펠 세트", "그릴 팬"],
        "storage": ["쿨러백", "음식 보관 용기", "진공 포장기"],
    },
    "travel4-hugo": {
        "luggage": ["기내용 캐리어", "여행용 백팩", "압축 파우치"],
        "tech": ["차량용 충전기", "보조배터리", "멀티 어댑터"],
        "comfort": ["목베개", "안대", "압축 양말"],
    },
}
```

---

## 6. 잔여 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| 쿠팡 API Rate Limit (분당 50회) | 배치 검색 1회 + 캐시 1시간 → 실질 0회 추가 호출 |
| 상품 이미지 로드 실패 | `loading="lazy"` + `onerror="this.style.display='none'"` |
| 블로우피쉬 테마 relatedPosts 미작동 | 테마 설정 확인 후 폴백: 우리 코드에서 조건부 삽입 (feature flag) |
| CSS 미적용 (Hugo 파이프라인) | 인라인 `<style>` 주입 또는 `assets/css/custom.css` 생성 |

---

## 7. 다음 단계

1. **이 설계안 승인** → Phase 44 PLAN.md 업데이트
2. **shared/coupang_travel.py** 리팩토링 실행
3. **pipelines/travel/writer.py** `_post_process` + 연동 수정
4. **테스트 실행** → dry-run 3회/블로그 검증
5. **완료 보고**

---

**승인 여부 회신 주시면 즉시 구현 착수하겠습니다.**