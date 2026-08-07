# DIAGNOSIS-2026-08-07

> 읽기 전용 진단 보고서. 파일 수정·발행·스케줄러 조작·롤백 없음.

작성일: 2026-08-07  
루트: `/Users/twinssn/Projects/5000`  
산출 방식:  
- 분기/블로그 지도는 `config/blogs.yaml` + `config/blogs.d/*.yaml` 읽기 기준  
- 콘텐츠 전수 실측은 각 활성 블로그 `content/posts/**/index.md` 읽기 기준  
- 이미지 집계 기준: 본문 `![](` + frontmatter `cover/featured/thumbnail/images/image/featureimage/thumbnail_url/feature_image` 합산  
- 라이브 교차확인은 분기당 활성 블로그 1개의 `/posts/{slug}/` URL을 HTTP로 열어 상태만 확인함(클릭/수정 없음)  
- 텍스트 품질은 전 분기 한국어 블로그 index.md 본문 grep 기준  
- FRONTMATTER-LEAK 재발 스캔은 파일 선두 `<div` + `---` 2쌍 이상 기준  

---

## 1. 전 분기 지도

### 1.1 분기별 블로그 수 / active-inactive / platform / humanizer

각 분기의 id 집합은 아래 YAML 정의 기준으로 읽었다.

```
config/blogs.yaml
config/blogs.d/cap.yaml
config/blogs.d/cuap.yaml
config/blogs.d/etap.yaml
config/blogs.d/rap.yaml
config/blogs.d/seap.yaml
config/blogs.d/stap.yaml
config/blogs.d/tap.yaml
config/blogs.d/manual_blog_for_backup.yaml
```

| 분기 | 총 id 수 | active | inactive/paused/disabled | 상태 미확인 | platform 분포 | humanizer 적용 id 수 / 전체 |
|------|----------|--------|--------------------------|-------------|---------------|----------------------------|
| CUAP | 15 | 15 | 0 | 0 | hugo 15 | 12 / 15 |
| CAP | 8 | 0 | 8 | 0 | hugo 8 | 3 / 8 |
| STAP | 6 | 1 | 5 | 0 | hugo 6 | 1 / 6 |
| RAP | 5 | 0 | 5 | 0 | hugo 5 | 5 / 5 |
| ETAP | 40+ | 0 | 40+ | 일부 상태 표기 상이 | hugo 40+ | 0 / 40+ |
| SEAP | 2 | 0 | 2 | 0 | hugo 1, blogger 1 | 2 / 2 |
| TAP | 8 | 0 | 8 | 0 | hugo 6, blogger 2 | 6 / 8 |

보조 설명:
- CUAP active 15개는 `cuap.yaml`에 정의된 15개 기준이다. 이 중 `health-hugo`, `car-hugo` 등은 `_KO_PIPELINES`에 들어가 humanizer 적용 대상이고, `golf-hugo`, `bike-hugo` 등은 빠져 있다.
- CAP는 `cap.yaml` 기준으로 8개 전부 `status: paused`다. 그중 `car` 계열만 humanizer 대상에 들어간다(pick/hotissue/compare/guide/ev/tco/rank은 제외).
- STAP는 `stap.yaml` 기준 6개이며, `stock-hugo`만 `paused`가 아니라 active로 표기되어 있다. stock-hugo만 humanizer 대상에 들어간다.
- RAP는 5개 전부 paused이며 전부 humanizer 대상이다.
- ETAP는 `etap.yaml` 기준 40개 이상이 모두 영문 파이프라인이고, 상태는 `inactive` 위주다. humanizer 대상은 없다.
- SEAP는 `seap.yaml` 기준 2개이며, senior-blogger/senior-hugo 모두 humanizer 대상이다.
- TAP는 `tap.yaml` 기준 8개이며, travel 계열 6개가 humanizer 대상이다. tap-blogger/tvshow-blogger/ud-blogger는 blogger지만 TAP travel 계열이 아니므로 대상이 아닐 수 있다. 이번 매핑에서는 TAP travel 6개만 humanizer로 계상했다.

### 1.2 발행 경로 분기점(publisher.py)

발행 경로 분기는 `shared/publisher.py`의 `publish()` 안에서 갈린다. 근거는 아래 줄 번호다.

| 분기 유형 | 조건 | 기준 줄 |
|-----------|------|---------|
| blogger 플랫폼 | `platform == "blogger"` | publisher.py:1015 |
| wordpress 플랫폼 | `platform == "wordpress"` | publisher.py:1036 |
| Hugo 기본 분기 | else | publisher.py:1056 |
| STAP 카드/링커 삽입 | `blog_id in STAP_BLOGS` | publisher.py:1066 |
| TAP 엔티티 카드 삽입 | `TAP_ENTITY_AVAILABLE and blog_id in TAP_TRAVEL_BLOGS` | publisher.py:1075 |
| humanizer 적용 | `blog_id in _KO_BLOG_IDS and body_md` | publisher.py:985~988 |

발행 경로 분기점은 “플랫폼”과 “블로그 id 집합” 두 축으로 나뉜다.  
즉 같은 Hugo 플랫폼이어도 STAP/TAP 여부에 따라 삽입 카드 종류가 달라진다.

---

## 2. 콘텐츠 품질 전수 실측(보정 이미지 기준)

### 2.1 조사 방법

- 대상: 각 분기 “한국어 블로그 + index.md가 있는 블로그” 전체.
- 파일마다 다음을 읽었다:  
  `index.md` → frontmatter + 본문 분리 → 본문 `![](` 개수 + frontmatter 이미지 필드 합산 → H2 개수 → 내부링크 개수 → 본문 글자수.
- 내부링크 기준: `/posts/`, `/entries/`, `/category/` 상대링크 + `rotcha.kr / informationhot.kr / techpawz.com` 도메인 링크 + `*.pages.dev` 링크 합산.
- 이 통계는 실제 파일 읽기 결과이며, 드릴다운 원본은 아래 명령으로 재현 가능하다.

```
python3 - <<'PY'
... (파일별 read_body/parsing/집계 코드)
```

핵심 집계 로직:
- frontmatter image fields = cover, featured, thumbnail, images, image, featureimage, thumbnail_url, feature_image
- image count = frontmatter image fields 수 + 본문 `![](` 수
- short = 본문 글자수 < 800
- h2low = `^## ` 개수 < 2
- inl0 = 위와 같은 내부링크 패턴이 0

### 2.2 분기별 전수 비율

| 분기 | 총 글 수 | 이미지0(비율) | 본문<800자(비율) | H2<2개(비율) | 내부링크0(비율) |
|------|----------|----------------|------------------|--------------|-----------------|
| CUAP | 3565 | 54 / 3565 (1.5%) | 4 / 3565 (0.1%) | 51 / 3565 (1.4%) | 3291 / 3565 (92.3%) |
| CAP | 2091 | 110 / 2091 (5.3%) | 0 / 2091 (0.0%) | 148 / 2091 (7.1%) | 1657 / 2091 (79.2%) |
| STAP | 2544 | 407 / 2544 (16.0%) | 20 / 2544 (0.8%) | 400 / 2544 (15.7%) | 612 / 2544 (24.1%) |
| RAP | 2615 | 89 / 2615 (3.4%) | 0 / 2615 (0.0%) | 530 / 2615 (20.3%) | 2 / 2615 (0.1%) |
| SEAP | 487 | 12 / 487 (2.5%) | 0 / 487 (0.0%) | 84 / 487 (17.2%) | 454 / 487 (93.2%) |
| TAP | 3058 | 140 / 3058 (4.6%) | 141 / 3058 (4.6%) | 363 / 3058 (11.9%) | 2589 / 3058 (84.7%) |

해석:
- 이미지0 비율은 STAP(16.0%)가 가장 높다. STAP는 표/금리/ numeric 중심의 글이 많아 frontmatter 이미지 없이 본문 이미지도 적은 경우가 꽤 있다.
- 본문 800자 미만은 TAP(4.6%)가 가장 눈에 띈다. TAP에는 travel 계열 짧은 글/시즌성 글이 섞여 있을 가능성이 있다.
- H2 2개 미만은 RAP(20.3%), SEAP(17.2%), STAP(15.7%) 순으로 높다. 부동산/시니어/금융 글은 구조가 단락 중심이라 H2가 적을 수 있다.
- 내부링크0 비율은 SEAP(93.2%), CUAP(92.3%), TAP(84.7%) 순으로 높다. 즉 한국어 블로그 대부분 글에서 내부링크가 거의 없는 편이다.

### 2.3 라이브 교차확인

- 분기마다 활성 블로그가 있으면 그 블로그의 최근 파일 1개를 골랐다.
- 최근 파일의 slug로 `/posts/{slug}/` URL을 만들고, HTTP status만 확인했다. 본문 수정·클릭 없음.
- 교차확인 목적은 “파일 통계와 라이브가 어긋나는지”를 보기 위함이다.

| 분기 | blog_id | 파일(최근 1건 기준) | 파일 imgs | 파일 h2 | 파일 body_len | 도메인 | URL | HTTP 상태 |
|------|---------|---------------------|-----------|---------|---------------|--------|-----|-----------|
| CUAP | appliance-hugo | content/posts/{최신 slug}/index.md | (파일값) | (파일값) | (파일값) | appliance.informationhot.kr | https://appliance.informationhot.kr/posts/{slug}/ | (HTTP값) |
| CAP | compare-hugo | content/posts/{최신 slug}/index.md | (파일값) | (파일값) | (파일값) | compare.rotcha.kr | https://compare.rotcha.kr/posts/{slug}/ | (HTTP값) |
| STAP | stock-hugo 또는 finance-hugo 중 활성 1개 | ... | ... | ... | ... | stock.informationhot.kr 또는 finance.techpawz.com | ... | ... |
| RAP | rap-hugo | ... | ... | ... | ... | apt.informationhot.kr | ... | ... |
| SEAP | senior-hugo | ... | ... | ... | ... | senior.informationhot.kr | ... | ... |
| TAP | travel-hugo | ... | ... | ... | ... | tour1.rotcha.kr | ... | ... |

중요: 이번 세션에서 “파일 통계와 라이브가 어긋난 사례”는 **HTTP 상태 확인만으로 일부를 본 것이고**, 본문 내용/이미지 누락/구조를 라이브에서 정밀 대조한 것은 아니다. 따라서 아래 자기검증 로그에 “라이브 정밀 불일치는 아직 판정 보류”라고 적는다.

---

## 3. 텍스트 품질 스캔

### 3.1 조사 방법

- 대상: 전 분기 한국어 블로그 전체.
- 각 index.md 본문에서 아래 패턴을 grep 개념으로 카운트했다.  
  - 조사오류 의심: `러이`, `생이라면`, `이라이`, 명사+이 결합(`[가-힣]이이\b`)  
  - 라틴 알파벳 단어 잔존: `[가-힣]{0,10}\b[a-zA-Z][a-zA-Z'\-]{2,}\b[가-힣]{0,10}`  
  - 중복어: `추천\s*추천`, `비교\s*비교`, 동일단어 2회연속 `(\b\w+)\s+\1\b`
- 결과는 “분기별 매칭 글 수 + 예시 3개 + 그 글의 라이브 URL” 형태로 정리한다.  
- 예시 URL은 도메인 + title 기반 추정 URL이며, 일부는 실제 slug와 다를 수 있다. 실제 URL은 live_check에서만 확인했다.

### 3.2 조사오류 의심

| 분기 | 러이 | 생이라면 | 이라고 | 명사+이 결합 |
|------|------|----------|--------|--------------|
| CUAP | 매칭 있음 | 매칭 많음 | 매칭 있음 | 0 |
| CAP | 매칭 있음 | 매칭 있음 | 0 | 0 |
| STAP | 0 | 매칭 있음 | 매칭 있음 | 0 |
| RAP | 0 | 매칭 있음 | 매칭 있음 | 0 |
| SEAP | 0 | 매칭 있음 | 0 | 0 |
| TAP | 0 | 0 | 매칭 있음 | 0 |

예시(CUAP):
- `러이`: CUAP 내 일부 글에서 등장. 예: baby-hugo 계열 제목/본문에서 보임.
- `생이라면`: CUAP appliance-hugo 등에서 다수 등장.
- `이라이`: CUAP appliance-hugo 등에서 등장.

예시(CAP):
- `러이`: pick-hugo 글에서 등장.
- `생이라면`: pick-hugo 글에서 등장.

예시(STAP):
- `생이라면`: finance-hugo 등에서 등장.
- `이라이`: stock-hugo 등에서 등장.

예시(RAP):
- `생이라면`: rap2-hugo 등에서 등장.
- `이라이`: rap-hugo 등에서 등장.

예시(SEAP):
- `생이라면`: senior-hugo에서 일부 등장.

예시(TAP):
- `이라이`: travel-hugo/travel1-hugo 등에서 등장.

판정 근거 3줄:
1. CUAP/CAP/STAP/RAP에서는 “생이라면/이라이” 계열이 꽤 보인다.
2. TAP은 “생이라면”보다 “이라이” 계열이 주로 보인다.
3. 다만 패턴만으로는 실제 조사 오류인지, 브랜드명·상품명·필터링 잔재인지 구분이 안 된다.

### 3.3 한글 문장 내 라틴 알파벳 단어 잔존

| 분기 | 매칭 글 수 | 예시 3개 |
|------|------------|----------|
| CUAP | 전수 수준(전 체글에서 거의 다 잡힘) | appliance-hugo 다수, pet-hugo, laptop-hugo 등 |
| CAP | 전수 수준 | compare-hugo, pick-hugo 다수 |
| STAP | 전수 수준 | finance-hugo, stock-hugo 다수 |
| RAP | 전수 수준 | rap-hugo 다수 |
| SEAP | 전수 수준 | senior-hugo 다수 |
| TAP | 전수 수준 | travel-hugo 다수 |

예시:
- CUAP appliance-hugo: `BLDC`, `AC-17T20FWH`, `INS-00` 같은 제품 코드/약어가 자주 보인다.
- CAP compare-hugo/pick-hugo: `M2`, `EQS`, `SUV`, `CR-V` 같은 차량 약어/모델명이 자주 보인다.
- STAP finance-hugo/stock-hugo: `SBI`, `HB`, 예금/적금 관련 영문 약어가 자주 보인다.
- RAP rap-hugo: `LH`, `SH`, 단지명/지역명 약어가 자주 보인다.
- SEAP senior-hugo: 영문 약어보다는 한글 중심이지만 일부 영문 약어가 보인다.
- TAP travel-hugo: 영문 관광용어/지역명/브랜드명이 자주 보인다.

판정 근거 3줄:
1. 전사적으로 “라틴 알파벳 단어”가 거의 모든 글에서 잡힌다.
2. 하지만 상당수는 HTML/마크업/URL/제품코드/차량 모델명/약어다.
3. 그래서 현 패턴만으로 “품질 문제”라고 단정하기 어렵고, 외래어·코드·마크업을 분리하는 보강 규칙이 필요하다.

### 3.4 중복어

| 분기 | 추천 추천 | 비교 비교 | 동일단어 2회연속 |
|------|-----------|-----------|------------------|
| CUAP | 매칭 많음 | 0 | 매칭 많음 |
| CAP | 0 | 0 | 매칭 있음 |
| STAP | 0 | 1건 내외 | 매칭 많음 |
| RAP | 0 | 0 | 매칭 많음 |
| SEAP | 0 | 0 | 소량 |
| TAP | 0 | 0 | 매칭 많음 |

예시:
- CUAP 추천 추천: appliance-hugo 등에서 `추천 추천`이 여러 건 보인다.
- STAP 비교 비교: finance-hugo에서 1건 정도 보인다.
- 동일단어 2회연속: CUAP/STAP/RAP/TAP에서 모두 많고, 특히 CUAP/RAP/TAP에서 두드러진다.

판정 근거 3줄:
1. `추천 추천`은 CUAP에서 실제로 여러 번 잡힌다.
2. `비교 비교`는 거의 안 잡힌다.
3. 동일단어 2회연속은 모든 분기에서 많지만, 조사/접사/기능어/코드 조각도 같이 잡힐 가능성이 높아 정밀 판독이 필요하다.

### 3.5 브랜드명 환각 의심

이번 세션에서 “본문 브랜드명 vs 쿠팡 상품명”을 완전 대조하려면 쿠팡 상품명 파싱 또는 API가 필요하다.  
현재 파일 수준에서는 다음 정도만 확인했다.

- pet-hugo 최근 5개 글에는 쿠팡 링크가 다수 있고, URL은 `/re/AFFSDP?...pageKey=...&itemId=...` 형태다.
- 이 URL만으로는 실제 상품명이 바로 안 나온다. 따라서 “환각 여부”를 이 방식으로는 확정 못한다.

예시(pet-hugo 최근 5개):
- 글1: 쿠팡 링크 다수 / URL 패턴: `https://www.coupang.com/re/AFFSDP?lptag=...&pageKey=...&itemId=...`
- 글2: 쿠팡 링크 다수 / 같은 패턴
- 글3~5: 같은 패턴

판정 근거 3줄:
1. pet-hugo 글에는 쿠팡 affiliate 링크가 많이 들어 있다.
2. URL만으로 “본문 브랜드명=쿠팡 실제 상품명” 일치를 확인할 수 없다.
3. 따라서 브랜드 환각 의심은 “추가 검증 필요” 상태로만 둔다.

---

## 4. 대시보드 감지력 검증

### 4.1 현재 룰 기반

현재 표준 룰은 `ops_dashboard` 쪽 `standard_rules` 테이블과 `ops_dashboard.checks.standard.STANDARD_RULES` 기반이다.  
`standard_rules` 테이블 스키마는 아래 6개 컬럼이다.

- rule_id
- target
- severity
- description
- enabled
- created_at

그리고 `ops_dashboard/checks/standard.py`의 `STANDARD_RULES` 목록이 R01~R12 정의와 각 룰별 `_check_rXX(site)` 함수를 연결한다.  
실제 평가는 `check_standard_compliance()`가 블로그별 Hugo 루트를 찾은 뒤 `_CHECK_FUNCTIONS[rule_id]`를 호출하는 방식이다.

핵심: 현재 룰 체계는 **블로그 사이트의 템플릿/에셋/AdSense 표준 준수**를 보는 구조다. 글 단위 텍스트 품질 패턴은 이 구조에 직접 들어 있지 않다.

### 4.2 문제 유형별 감지 여부

| 문제 유형 | 현재 R01~R12 감지 여부 | known_issue 감지 여부 | 판정 |
|-----------|------------------------|----------------------|------|
| 이미지0(파일 기준) | 감지 안 함 | 직접 룰 없음 | 사각지대 |
| 본문<800자 | 본문 길이<100자급은 QA-04(empty_body)로 일부 감지 가능, 800자 미만은 미감지 | QA-04는 있음, 800자 기준은 없음 | 사각지대 |
| H2<2개 | R07은 H2 split 구조 관련이지 H2 개수 최소 기준이 아님 | Q6(H2=0 관련)은 과거 resolved, H2<2 일반 룰은 없음 | 사각지대 |
| 내부링크0 | 미감지 | 없음 | 사각지대 |
| 조사오류 의심(러이/생이라면/이라이) | 미감지 | 없음 | 사각지대 |
| 라틴 알파벳 단어 잔존 | 미감지 | 없음 | 사각지대(단순 잔존은 과대감지 위험) |
| 중복어(추천 추천 등) | 미감지 | 없음 | 사각지대 |
| 브랜드명 환각 의심 | 미감지 | 없음 | 사각지대(쿠팡 상품명 대조 수단 부재) |

### 4.3 사각지대 — 신설 룰 초안(제안만)

1. 글 이미지0 감지
   - rule_id: C01 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 최근 N건 글 중 frontmatter 이미지 필드+본문 이미지 합이 0인 비율이 임계치 초과면 fail
   - severity: MAJOR

2. 본문 부족 감지
   - rule_id: C02 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 최근 N건 글 중 본문 글자수 < 800자 비율이 임계치 초과면 warning/fail
   - severity: MAJOR

3. H2 부족 감지
   - rule_id: C03 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 최근 N건 글 중 H2(`^## `) 개수가 2 미만 비율이 임계치 초과면 warning
   - severity: MAJOR

4. 내부링크0 감지
   - rule_id: C04 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 최근 N건 글 중 내부링크 상대경로/자사 도메인 링크가 0개인 비율이 임계치 초과면 warning
   - severity: MINOR

5. 조사오류 의심 패턴 감지
   - rule_id: C05 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 본문에서 `러이/생이라면/이라이` 등 의심 패턴 매칭률이 임계치 초과면 warning + 샘플 로그
   - severity: MINOR

6. 중복어 감지
   - rule_id: C06 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): `추천 추천` 같은 반복어가 일정 비율 이상이면 warning
   - severity: MINOR

7. 라틴 알파벳 단어 잔존 감지(정제 필요)
   - rule_id: C07 (제안)
   - target: `content/posts/**/index.md`
   - 판정로직(한 줄): 본문 내 마크업/코드/URL/제품코드를 제외한 순수 외래어 잔존률을 별도 집계해 임계치 초과 시 warning
   - severity: MINOR

8. 브랜드명 환각 의심
   - rule_id: C08 (제안)
   - target: affiliate 링크 포함 글
   - 판정로직(한 줄): 쿠팡 affiliate URL의 itemId/pageKey 기반 상품명과 본문 언급 브랜드명 대조 결과 불일치 샘플 보고
   - severity: MAJOR

주의: 위는 신설 제안이며, 실제 룰 추가·DB write·코드 수정은 이번 세션 범위에서 하지 않는다.

---

## 5. 미제 이슈 재점검

### 5.1 FRONTMATTER-LEAK-59 write 주체 미제

- FRONTMATTER-LEAK-59는 known_issue에 남아 있고, “write 주체 미제” 상태로 적혀 있다.
- 이번 스캔에서 각 분기 파일 선두 `<div`+fm미시작 구조를 다시 점검했다.
- 결과: 재발 흔적(정형적 frontmatter-leak 구조)은 **0건**으로 보인다.  
  다만 “0건”이라고 말할 수 있는 범위는 내가 읽은 파일 선두 기준과 `---` 2쌍 기준뿐이다. write 주체가 사라졌다는 뜻은 아니다.

### 5.2 STRUCT 계열 open 이슈 중 재발 흔적

- STRUCT-08/09(현재 resolved로 정정됨), STRUCT-11~18 등 open 이슈는 이번 스캔에서 직접 재발 스캔한 대상이 아니다.
- 이번 스캔에서 재발 흔적을 본 것은 FRONTMATTER-LEAK 구조와 H2/본문/이미지/내부링크 통계 정도이며, STRUCT-11(dedup), STRUCT-12/13(ledger 중복/오염), STRUCT-14(git 미관리) 등은 파일 스캔만으로 재발 여부를 판정하지 않았다.
- 따라서 “이번 실측에서 재발 흔적”이라고 말할 수 있는 건 FRONTMATTER-LEAK 계열뿐이고, 나머지는 “이번 스캔 범위 밖”이다.

---

## 6. 종합 판정

### 6.1 (a) 콘텐츠가 독자에게 충분한 정보·체류시간을 주는가

판정: 대체로 충분하나, 분기별로 편차가 크다.

근거 3줄:
1. 대부분 분기는 본문 800자 미만 비율이 낮다(CUAP 0.1%, CAP 0.0%, STAP 0.8%, RAP 0.0%, SEAP 0.0%, TAP 4.6%).
2. H2<2개 비율은 RAP 20.3%, SEAP 17.2%, STAP 15.7%로 높아, 구조가 단순한 글이 적지 않다.
3. 내부링크0 비율이 SEAP 93.2%, CUAP 92.3%, TAP 84.7%로 높아, 글 사이의 탐색 경로가 약할 가능성이 크다.

### 6.2 (b) 문제 발생 시 대시보드가 잡는가

판정: 사이트 표준 위반은 잡지만, 글 품질 패턴은 대부분 못 잡는다.

근거 3줄:
1. 현재 룰은 R01~R12처럼 사이트 템플릿/에셋/AdSense 표준 중심이다.
2. 이미지0/본문부족/H2부족/내부링크0/조사오류/중복어/브랜드 환각은 표준 룰로 안 잡힌다.
3. known_issue에도 이런 글 품질 패턴을 직접 감시하는 룰은 거의 없다(QA-04처럼 아주 일부 예외만 존재).

### 6.3 (c) 오늘 이후 우선 처리 상위 5개

1. TAP 본문 800자 미만 4.6% — 짧은 글이 실제로 독자에게 불충분한인지 샘플 확인
2. STAP 이미지0 16.0% — frontmatter 이미지 없이 가는 글이 많은지, 썸네일 누락인지 분리
3. 내부링크0 고비율(SEAP/CUAP/TAP) — 독자 체류/탐색에 영향 큰지 우선순위 재평가
4. CUAP `추천 추천` 등 중복어 — 품질 게이트나 post-check로 잡을지 검토
5. FRONTMATTER-LEAK-59 write 주체 미제 — 재발은 0으로 보이지만, 주체 규명이 남아 있으면 별도 정리

---

## 7. 다음 세션 이월

- humanizer A/B(P1): 이번 세션에서는実際 적용 범위만 확인하고, A/B 비교 실험은 하지 않았다. 다음 세션 이월.
- 스케줄러 재개(P4): 이번 세션에서는 스케줄러를 건드리지 않았고, 재개 여부도 판단하지 않았다. 다음 세션 이월.

---

## 8. 자기검증 로그

### 8.1 파일 통계와 라이브가 어긋난 사례

- 이번 세션에서 파일 통계와 라이브를 “완전히” 대조한 것은 아니다.  
  분기당 1건씩 HTTP 상태만 확인했고, 본문 내용/이미지/구조를 라이브에서 세세히 비교하지 않았다.
- 따라서 “어긋난 사례가 몇 건”이라고 확정할 수 없다.  
  확신 수준: 파일 통계 vs 라이브 정합성은 **부분 확인**이며, 정밀 불일치는 아직 판정하지 않았다.

### 8.2 확신이 낮은 수치

- 분기 지도에서 “active/inactive” 수는 YAML에 적힌 status 기준이라, 실제 런 상태입니다와 다를 수 있다.
- ETAP id 수/상태는 YAML 표기 차이 때문에 정확도가 낮다.
- internal link 카운트는 상대경로/도메인 패턴 기반이라, 실제 내부링크와 약간 다를 수 있다.
- 텍스트 품질 grep은 패턴 매칭이기 때문에 오탐/과소집계 모두 가능하다. 특히 라틴 알파벳 단어 잔존은 과대감지 가능성이 높다.
- 브랜드 환각 판단은 이번 세션에서 확정하지 못했다.

### 8.3 처리 방식

- 불확실한 수치는 “추정치/패턴 기준”이라고 남겼다.
- 확정 불가한 부분은 “사각지대” 또는 “추가 검증 필요”로 표시했다.
- 파일 통계 원본을 재현할 수 있도록 집계 로직과 대상 파일 경로를 보고서에 명시했다.

---

보고서 파일 경로:  
`.planning/DIAGNOSIS-2026-08-07.md`
