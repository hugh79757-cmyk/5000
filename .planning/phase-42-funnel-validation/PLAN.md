# Phase 42 PLAN — 퍼널(funnel) 설계 검증 (5개 블로그 연결)

> 상태: 📋 Planned | 우선순위: 🔴 HIGH
> 대상: tap.yaml 5개 Hugo 블로그(캠핑/축제/문화유산/맛집/코스)

---

## 사전조건

- Phase 40/41 변경 유지
- 발행/배포 호출 금지, 과거 글 수정 금지
- RESEARCH.md 완료 (`.planning/phase-42-funnel-validation/RESEARCH.md`)

---

## 검증 요약

| 영역 | RESEARCH 결과 | 조치 |
|------|-------------|------|
| "함께 읽어보기" shortcode 렌더링 | Hugo `{{< article >}}` 등록됨, raw 노출 없음 | 검증 완료·수정 불요 |
| nearby-card raw HTML | Goldmark 통과, 정상 렌더링 | 검증 완료·수정 불요 |
| funnel card 생성 | content_store DB에서 최신 글 조회, 정상 | 검증 완료 |
| 퍼널 그래프 | 단방향(4landing → 코스), 역방향/상호 연결 없음 | 기획 이슈 (버그 아님) |
| bridge_to 미설정 | 5개 블로그 전부 bridge_to=[] | 기획 이슈 |

---

## Task 1: "함께 읽어보기" shortcode 검증

### 검증 내용
- dry-run 산출물에서 `{{< article link="">}}` shortcode가 body_md에 정상 포함되는지 확인
- Shortcode 누락 또는 raw 텍스트 노출 여부 확인
- Hugo shortcode 파일 존재 여부 확인

### 검증 방법 (read-only)
```bash
# 1. Blowfish 테마에 article shortcode 존재 확인
ls /Users/twinssn/Projects/TAP/travel-hugo/themes/blowfish/layouts/shortcodes/article.html

# 2. dry-run body_md에서 shortcode 패턴 확인
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
import re
d = fetch_camping()
r = generate_content(d, blog_id='travel-hugo')
body = r.get('body_md','')
shortcodes = re.findall(r'{{<.*?>}}', body)
print(f'Shortcode count: {len(shortcodes)}')
for sc in shortcodes:
    print(f'  {sc[:80]}')
# raw 텍스트 노출 검사
has_raw_link = '[' in body and '](' in body  # markdown link
has_raw_url = re.search(r'https?://[^\s\)]+', body.split('## 함께 읽어보기')[-1]) if '## 함께 읽어보기' in body else False
print(f'Raw markdown links in related section: {bool(has_raw_link and has_raw_url)}')
"
```

### 기대 결과
- Hugo article shortcode 파일 존재 ✅
- body_md에 `{{< article link="">}}` 형식 정상 포함
- raw 마크다운 링크 노출 없음
- **수정 불필요**

---

## Task 2: nearby-card HTML 검증

### 검증 내용
- nearby-card가 raw HTML(`<div class="nearby-card">`)로 body_md에 포함되는지 확인
- 누락 또는 깨진 HTML 구조 없는지 확인
- Hugo Goldmark가 raw HTML 통과 가능한지 확인

### 검증 방법 (read-only)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
import re
d = fetch_camping()
r = generate_content(d, blog_id='travel-hugo')
body = r.get('body_md','')
# nearby-card HTML 검사
nearby_cards = re.findall(r'<div class=\"nearby-card\">.*?</div></div></div>', body, re.DOTALL)
print(f'Nearby card count: {len(nearby_cards)}')
for i, card in enumerate(nearby_cards):
    has_img = 'nearby-card-img' in card
    has_name = 'nearby-card-name' in card
    has_btn = 'nearby-card-btn' in card
    print(f'  Card {i+1}: img={has_img}, name={has_name}, btn={has_btn}, valid={has_name and has_btn}')
# 깨진 HTML 검사
broken_div = body.count('<div') - body.count('</div>')
print(f'Div balance: {broken_div} (0=ok)')
"
```

### 기대 결과
- nearby-card가 정상 HTML 구조로 포함
- **수정 불필요**

---

## Task 3: funnel card 검증

### 검증 내용
- _build_funnel_cards_md()가 publish 시 정상 호출되는지 확인
- depth_next 설정(4개 → travel4-hugo)이 올바른지 확인
- funnel card HTML에 data-funnel-link 속성이 포함되는지 확인
- bridge_to 미설정 현황 확인

### 검증 방법 (read-only)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
import yaml
config = yaml.safe_load(open('/Users/twinssn/projects/5000/config/blogs.d/tap.yaml'))
for blog in config:
    bid = blog.get('id','')
    stage = blog.get('funnel_stage','none')
    depth = blog.get('depth_next',[])
    bridge = blog.get('bridge_to',[])
    print(f'{bid}: stage={stage}, depth={len(depth)} targets, bridge={len(bridge)} targets')
    for d in depth:
        print(f'  depth → {d[\"id\"]} ({d.get(\"topic\",\"\")})')
    for b in bridge:
        print(f'  bridge → {b[\"id\"]} ({b.get(\"topic\",\"\")})')
"
```

### 기대 결과
- depth_next 설정 각 blog_id → travel4-hugo 확인
- bridge_to 전부 미설정 확인 ([])

---

## Task 4: 퍼널 그래프 완전성 분석

### 검증 내용
- 현재 퍼널이 단방향인지 양방향인지 분석
- 독자 흐름(캠핑→코스, 축제→코스, 맛집→코스)이 자연스러운지 평가
- 퍼널 그래프에서 누락된 연결 식별

### 현재 퍼널 그래프
```
travel-hugo (캠핑)        ─┐
travel1-hugo (축제)       ─┤
travel2-hugo (문화유산)    ─┤→ travel4-hugo (코스)
travel3-hugo (맛집)       ─┘
tvshow-blogger / ud-blogger: 퍼널 미설정
```

### 식별된 누락 연결
| 누락 유형 | 예시 | 영향 |
|----------|------|------|
| 역방향 (코스→랜딩) | travel4-hugo → travel-hugo 등 | 코스 글에서 캠핑/맛집 추천 불가 |
| 랜딩 간 상호 연결 | 캠핑→맛집, 축제→캠핑 등 | 크로스셀 기회 손실 |
| Blogger 블로그 연결 | tvshow-blogger → travel3-hugo | 방문자 흐름 단절 |

### 기대 결과
- 단방향 퍼널 확인 (4→코스)
- bridge_to 미설정 확인
- **기획 이슈로 기록, 코드 수정 불필요**

---

## Task 5 (선택): 퍼널 개선 제안 문서화

### 검증 내용 (Task 4 결과에 따라)
- Phase 42 범위 내에서 퍼널 개선이 필요하면 제안
- bridge_to 설정 예시, depth_next 확장 등

### 제안 방향 (현재 판단)
- **travel4-hugo에 bridge_to 추가**: travel-hugo, travel1-hugo, travel2-hugo, travel3-hugo 각각 역방향 링크
- **landing 간 bridge_to 추가**: content overlap 기반 자동 연결 (예: 캠핑장 글에서 근처 맛집 링크)
- **퍼널 카드 위치 조정**: 현재 중간+끝 → 글 하단 통일
- 위 제안은 Phase 43(확장) 또는 별도 Phase로 처리

---

## 실행 순서

```
Task 1 (함께 읽어보기 shortcode) → Task 2 (nearby-card HTML) → Task 3 (funnel card) → Task 4 (퍼널 그래프 분석) → Task 5 (개선 제안, 선택)
```

## 검증 완료 기준

| 조건 | 기준 |
|------|------|
| Shortcode 렌더링 | article shortcode 파일 존재, body_md에 정상 포함 |
| nearby-card HTML | 정상 HTML 구조, 깨짐 없음 |
| funnel card 설정 | depth_next 4개 확인, bridge_to 미설정 확인 |
| 퍼널 그래프 | 단방향 구조 확인, 누락 연결 식별 |
| raw 노출 | shortcode/HTML raw 텍스트 노출 0건 |

## 파일

- RESEARCH.md: `.planning/phase-42-funnel-validation/RESEARCH.md`
- VERIFICATION.md: (execute 후 생성)
- SUMMARY.md: (execute 후 생성)
