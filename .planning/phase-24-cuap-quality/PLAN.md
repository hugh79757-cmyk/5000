# Phase 24: CUAP 콘텐츠 품질 고도화 — PLAN

**Objective:** beauty-hugo의 콘텐츠 품질을 강화하여 뷰티 관련성, 제목 전환율, 이미지 중복 방지를 개선한다.

**Mode:** implementation

---

## Wave 1: 키워드 오염 제거 (beauty-hugo)

### Task 1.1: beauty-hugo 키워드 목록 정리

**File:** `pipelines/curation/keywords.py`

**변경:**
- `beauty-hugo` 섹션에서 비뷰티 키워드 제거
- 제거 대상:
  - 가구/인테리어: `"가죽", "가죽소파", "거실", "등받이", "리클라이너", "라운지", "라운지전용"`
  - 전자기기: `"노트북", "갤럭시북", "레노버", "라이젠"`
  - 생활가전: `"공기청정기", "냉장고"`
  - 운동용품: `"덤벨"`
  - 사무용품: `"데스크", "각도조절"`
  - 기타: `"가방", "경량", "고성능", "고해상도", "국산", "그램", "그레이", "기숙사", "기획세트", "다용도", "대용량", "대학생", "대형", "대화면"`

**검증:**
- [ ] `beauty-hugo` 키워드 100% 뷰티 관련
- [ ] `validate_keyword()` 호출 시 비뷰티 키워드 차단 확인

---

### Task 1.2: CATEGORY_FILTERS 강화

**File:** `pipelines/curation/pipeline.py`

**변경:**
- `CATEGORY_FILTERS["beauty-hugo"]`는 이미 존재함 (pipeline.py:360-376)
- 기존 필터를 강화 — `blocked` 리스트 확대

```python
"beauty-hugo": {
    "allowed": [
        "화장품", "스킨케어", "세럼", "앰플", "크림", "로션",
        "클렌저", "클렌징", "토너", "에센스", "수분", "보습",
        "비비크림", "쿠션", "파운데이션", "프라이머",
        "아이크림", "립밤", "립스틱", "틴트", "마스카라", "아이라이너",
        "블러셔", "하이라이터", "컨실러", "파우더",
        "선크림", "자외선", "미백", "주름", "탄력",
        "트러블", "여드름", "모공", "각질", "진정",
        "마스크팩", "시트마스크", "워시오프", "필오프",
        "헤어", "샴푸", "트리트먼트", "헤어에센스",
        "바디", "핸드크림", "바디로션",
        "네일", "매니큐어", "페디큐어",
        "향수", "데오드란트",
        "고데기", "헤어드라이어",  # 뷰티 기기
        "면도기", "제모기",  # 뷰티 기기
    ],
    "blocked": [
        "가구", "인테리어", "소파", "침대", "책상", "의자",
        "가전", "냉장고", "세탁기", "건조기", "청소기",
        "노트북", "컴퓨터", "태블릿", "모니터",
        "도서", "교재", "식품", "의류", "패션",
        "장난감", "완구", "출산/유아", "반려동물",
        "스포츠", "운동", "헬스",
        "공기청정기", "에어컨",  # 가전 차단
        "덤벨", "데스크",  # 운동/사무 차단
    ],
},
```

**검증:**
- [ ] `_filter_irrelevant_products("beauty-hugo", ...)` 호출 시 가구/가전 상품 차단
- [ ] 뷰티 상품만 통과

---

## Wave 2: 타이틀 전환율 최적화

### Task 2.1: 네이버 블로그 타이틀 패턴 분석

**参考:** 네이버에서 "립밤 추천", "세럼 추천" 등으로 검색 시 상위 10개 블로그 제목 패턴

**관찰된 패턴:**
1. "2026년 7월 [제품명] 추천 — [한줄요약]"
2. "[제품A] vs [제품B] — [비교 포인트]"
3. "[제품명] 후기 | [체험담]"
4. "[제품명] 총정리 — [가격/스펙/후기]"

### Task 2.2: writer.py 제목 생성 로직 강화

**File:** `pipelines/curation/writer.py`

**변경:**
- `_build_system_prompt()`의 제목 규칙 강화
- 네이버 상위 블로그 패턴 참조 추가
- 클릭 유도 요소 추가

```python
extra_title_rules = f"""
[이번 발행 제목 스타일 — 네이버 상위 블로그 벤치마크]
제목은 반드시 아래 패턴 중 하나를 따라야 합니다:

1. [연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]
   예: "2026년 7월 립밤 추천 리엔케이·바세린 — 하루 종일 촉촉한 선택"

2. [제품A] vs [제품B] — [비교 포인트]
   예: "헤라 블랙 쿠션 vs 샵한현재 마스터 핏 — 커버력 비교"

3. [제품명] [체험형 후기] — [공감대]
   예: "센카 퍼펙트 휩 3주 사용 후기 — 여드름 피부에게 딱 맞는 폼클렌저"

4. [대상]을 위한 [제품 유형] 총정리 — [가격대/혜택]
   예: "민감성 피부를 위한 클렌저 총정리 — 1만원대 합격 TOP 5"

[제목 필수 요소]
- 제품명 또는 브랜드명 1~2개 포함
- "추천", "후기", "비교", "총정리" 중 1개 포함
- 구체적 수치 또는 혜택 포함 (예: "1만원대", "3주 사용", "TOP 5")
- "가성비" 사용 금지 → "합격점", "실속", "가격 대비" 사용
"""
```

**검증:**
- [ ] 제목이 네이버 상위 블로그 패턴과 유사
- [ ] "가성비" 단어 미포함
- [ ] 제품명/브랜드명 포함

---

## Wave 3: 이미지 중복 방지

### Task 3.1: 이미지 해시 기반 고유 ID 부여

**File:** `pipelines/curation/pipeline.py`

**변경:**
- `_upload_thumbnail()` 함수에 해시 기반 고유 파일명 추가
- 현재: `thumbnails/{blog_id}/{slug}.webp`
- 변경: `thumbnails/{blog_id}/{product_id_hash}_{slug}.webp`

```python
import hashlib

def _upload_thumbnail(image_url, product_id=None):
    """이미지 업로드 — 해시 기반 고유 파일명으로 중복 방지"""
    try:
        resp = _requests.get(image_url, timeout=10)
        if resp.status_code != 200:
            return ""
        
        # product_id가 있으면 해시 기반 고유 파일명 생성
        if product_id:
            id_hash = hashlib.md5(str(product_id).encode()).hexdigest()[:8]
            filename = f"{id_hash}_{slugify(product_id)}.webp"
        else:
            filename = f"{slugify(image_url)}.webp"
        
        # R2 업로드
        # ... (기존 로직 유지)
    except Exception as e:
        logger.error(f"썸네일 업로드 실패: {e}")
        return ""
```

**호출 사이트 수정 (필수):**
- `pipeline.py:835`에서 `product_id` 전달하도록 변경

```python
# 변경 전:
thumbnail_url = _upload_thumbnail(products[0]["product_image"])

# 변경 후:
thumbnail_url = _upload_thumbnail(
    products[0]["product_image"],
    product_id=products[0].get("product_id")
)
```

**검증:**
- [ ] 동일 제품 다른 블로그에서 발행 시 파일명 상이
- [ ] R2에서 중복 파일명 0개

---

## Execution Order

```
Wave 1 (키워드 정리) → Wave 2 (타이틀 최적화) → Wave 3 (이미지 중복 방지) → Verify
```

---

## Post-Execution Verification

1. `python3 -c "from pipelines.curation.keywords import get_keywords; kws = get_keywords('beauty-hugo'); print(f'총 {len(kws)}개 키워드'); [print(k) for k in kws if any(x in k for x in ['가구','가전','노트북','냉장고','덤벨','데스크'])]"` → 0개 출력
2. `python3 -c "from pipelines.curation.pipeline import CATEGORY_FILTERS; f = CATEGORY_FILTERS.get('beauty-hugo'); print('beauty-hugo 필터 존재' if f else 'MISSING')"` → "beauty-hugo 필터 존재"
3. Hugo build 성공
4. 테스트 발행 1건 — 제목 패턴 확인

---

## Risk Mitigation

| 리스크 | 영향도 | 완화 방안 |
|--------|--------|-----------|
| 키워드 정리 후 발행 불가 | 중 | 뷰티 키워드 100개 이상 확보 후 적용 |
| 타이틀 패턴 변경으로 유사 제목 증가 | 하 | `recent_titles` 피드백 로직 유지 |
| 이미지 해시 충돌 | 하 | MD5 8자리 + product_id 조합 |
