# Problematic Keywords — Audit Report

## 1. Syntax Errors (Missing Commas)

These cause unintended Python string concatenation, silently merging keywords.

| Blog | Line(s) | Merged String | Lost Keywords |
|------|---------|---------------|---------------|
| laptop-hugo | 9-10 | `"그램파우치마이크"` | 그램파우치, 마이크 |
| interior-hugo | 418-421 | `"과외거실공부동백다이닝"` | 과외, 거실공부, 동백, 다이닝 |
| baby-hugo | 622-623 | `"국민육아템개월장난감"` | 국민육아템, 개월장난감 |
| baby-hugo | 624-625 | `"교구간식통"` | 교구, 간식통 |
| health-hugo | 1017-1018 | `"고려은단건강하게"` | 고려은단, 건강하게 |
| pet-hugo | 1160-1161 | `"논슬립그레이비"` | 논슬립, 그레이비 |
| pet-hugo | 1162-1163 | `"그리니즈노령견"` | 그리니즈, 노령견 |
| beauty-hugo | 1446-1448 | `"나이트기미세럼EGF 세럼 추천닥터지닥터트럽"` | 나이트기미세럼EGF 세럼 추천, 닥터지, 닥터트럽 |
| camping-hugo | 1593-1594 | `"대형모기장레더"` | 대형모기장, 레더 |

**17 keywords silently lost** across 9 concatenation bugs.

---

## 2. Wrong Blog Category

Keywords that clearly belong to a different niche.

### laptop-hugo
| Keyword | Should Be On |
|---------|-------------|
| 기저귀 | baby-hugo |
| 덤벨 | fitness-hugo |
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 가죽소파 | interior-hugo |
| 강아지 | pet-hugo |
| 개모차 | pet-hugo |
| 고양이 | pet-hugo |

### appliance-hugo
| Keyword | Should Be On |
|---------|-------------|
| 기저귀 | baby-hugo |
| 덤벨 | fitness-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 갤럭시탭 | laptop-hugo |
| 데스크탑 | laptop-hugo |
| 가죽소파 | interior-hugo |
| 강아지 | pet-hugo |
| 개모차 | pet-hugo |
| 고양이 | pet-hugo |
| 데님 | fashion (N/A) |

### interior-hugo
| Keyword | Should Be On |
|---------|-------------|
| 기저귀 | baby-hugo |
| 덤벨 | fitness-hugo |
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 갤럭시탭 | laptop-hugo |
| 강아지 | pet-hugo |
| 개모차 | pet-hugo |
| 고양이 | pet-hugo |

### baby-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 갤럭시탭 | laptop-hugo |
| 강아지 | pet-hugo |
| 개모차 | pet-hugo |
| 고양이 | pet-hugo |

### fitness-hugo
| Keyword | Should Be On |
|---------|-------------|
| 기저귀 | baby-hugo |
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 갤럭시탭 | laptop-hugo |
| 강아지 | pet-hugo |
| 개모차 | pet-hugo |
| 고양이 | pet-hugo |
| 그래픽 | laptop-hugo (GPU context) |
| 등산배낭 | camping-hugo |
| 등산화 | camping-hugo |

### health-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 덤벨 | fitness-hugo |
| 레노버 | laptop-hugo |
| 맥북 / 맥북프로 | laptop-hugo |
| 매트 / 매트리스 | interior-hugo |

### pet-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 덤벨 | fitness-hugo |

### kitchen-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 덤벨 | fitness-hugo |
| 레노버 | laptop-hugo |
| 맥북 / 맥북프로 | laptop-hugo |
| 매트 / 매트리스 | interior-hugo |
| 에어프라이어 추천 | appliance-hugo |
| 식기세척기 추천 | appliance-hugo |

### beauty-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 덤벨 | fitness-hugo |
| 레노버 | laptop-hugo |
| 맥북 / 맥북프로 | laptop-hugo |
| 매트 / 매트리스 | interior-hugo |

### camping-hugo
| Keyword | Should Be On |
|---------|-------------|
| 냉장고 | appliance-hugo |
| 공기청정기 | appliance-hugo |
| 노트북 | laptop-hugo |
| 갤럭시북 | laptop-hugo |
| 덤벨 | fitness-hugo |
| 레노버 | laptop-hugo |
| 맥북 / 맥북프로 | laptop-hugo |
| 매트 / 매트리스 | interior-hugo |

---

## 3. Too Generic (Single-Word Noise)

These single generic words appear across multiple blogs (3+) and are unlikely to return niche-appropriate products:

| Keyword | Appears In (# blogs) |
|---------|---------------------|
| 가방 | 10/10 |
| 가벼운 | 10/10 |
| 가성비 | 10/10 |
| 가정용 | 10/10 |
| 가죽 | 10/10 |
| 가죽소파 | 10/10 |
| 각도조절 | 10/10 |
| 강아지 | 9/10 |
| 개모차 | 9/10 |
| 개월 | 10/10 |
| 갤럭시북 | 10/10 |
| 거실 | 10/10 |
| 거치대 | 10/10 |
| 게이밍 | 9/10 |
| 경량 | 9/10 |
| 고성능 | 10/10 |
| 고양이 | 8/10 |
| 고해상도 | 10/10 |
| 공기청정기 | 10/10 |
| 공부 | 10/10 |
| 국내생산 | 8/10 |
| 국산 | 10/10 |
| 그램 | 10/10 |
| 그레이 | 10/10 |
| 기계식 | 6/10 |
| 기내반입 | 6/10 |
| 기능성 | 8/10 |
| 기숙사 | 10/10 |
| 냉장고 | 10/10 |
| 노트북 | 10/10 |
| 높이조절 | 10/10 |
| 다용도 | 10/10 |
| 대용량 | 10/10 |
| 대학생 | 10/10 |
| 대형 | 9/10 |
| 대화면 | 9/10 |
| 덤벨 | 9/10 |
| 데스크 | 9/10 |
| 도어 | 8/10 |
| 두꺼운 | 6/10 |
| 듀얼 | 9/10 |
| 남녀공용 | 6/10 |
| 남여공용 | 5/10 |
| 노이즈 | 6/10 |
| 노이즈캔슬링 | 5/10 |
| 갤럭시탭 | 6/10 |
| 겸용 | 8/10 |
| 대형 | 9/10 |

**Impact**: These keywords waste API quota and pollute results with irrelevant products. When Coupang API searches "가방", it returns all bags — not laptop bags, not appliance bags. The filter pipeline then either passes the wrong products or filters everything out.

---

## 4. Adult/Off-Topic in baby-hugo

| Keyword | Issue |
|---------|-------|
| 골지 | Ribbed fabric — typically adult women's clothing term |
| 긴팔 | Long-sleeve — generic adult clothing |
| 나시 | Sleeveless shirt/tank top — adult clothing term, often reveals adult fashion |
| 게이밍 | Gaming — unrelated to baby |
| 건전지 | Batteries — unrelated, generic |
| 겨드랑이 | Armpit — odd/irrelevant for baby content |

---

## 5. Cross-Blog Duplicates (Keywords 3+ blogs)

Most egregious: the following "generic" keywords appear on ALL 10 blogs without any blog-specific context:
- 가방, 가벼운, 가성비, 가정용, 가죽, 가죽소파, 각도조절, 개월, 갤럭시북, 거실, 거치대, 고성능, 고해상도, 공기청정기, 공부, 국산, 그램, 그레이, 기숙사, 냉장고, 노트북, 높이조절, 다용도, 대용량, 대학생

These are likely copy-paste residue from an initial template. They provide no blog-specific SEO value and degrade result quality.

---

## Summary

| Issue Type | Count | Severity |
|-----------|-------|----------|
| Syntax errors (missing commas) | 9 instances, 17 lost keywords | **Critical** — breaks keywords silently |
| Wrong blog category keywords | ~80+ | **High** — wastes API calls, wrong products |
| Too generic single-word noise | ~50 keywords x 10 blogs | **High** — dilutes search relevance |
| Adult/off-topic in baby-hugo | 5 keywords | **Medium** — inappropriate product categories |
| Cross-blog duplicate (10/10 blogs) | 24 keywords | **High** — copy-paste residue |

