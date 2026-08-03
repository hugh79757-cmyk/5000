# Phase AI Marketing Skills — 콘텐츠 품질 게이트 우선 개선 (SEO Ops 후순위)

> 이 플랜은 2026-07-30 조사 결과를 기반으로 재구성됨

## 핵심 결론 (조사 기반 근거)

| 지표 | 수치 | 근거 파일 |
|------|------|-----------|
| 전체 발행 글 | 3,781건 (5000/content.db) / 2,849건/30일 (stap_content.db) | content.db, stap_content.db |
| GSC 누적 노출 (4개월) | 22,608회 | analytics.db gsc_daily_summary |
| GSC 누적 클릭 (4개월) | 151회 | analytics.db gsc_daily_summary |
| 블로그별 색인 추정 페이지 | 0~264페이지 (rotcha.kr 최대) | gsc_daily_summary.page_count |
| 품질 통과율 (relevance) | **100%** (avg 0.92, min 0.80) | curation.db publish_log |
| 현재 품질 게이트 threshold | 0.55~0.75 (블로그별) | relevance_scorer.py |
| RAP/TRAVEL 제목 템플릿 고정율 | **90~95%** (지역/단지명만 치환) | stap_content.db 샘플 |
| 본문 구조 고정율 | **100%** (첫 문장·마지막 단락 패턴 동일) | stap_content.db 샘플 |

**근거 기반 결정 사항**

| 판단 | 근거 |
|------|------|
| **Wave 1: 발행 로직 결함 수정 (우선)** | 표 번호 불일치, "총 N건" 문구 오류, 가점제 설명 무단 삽입 등 구체적 결함이 확인되어 품질 게이트 강화 전 필수 |
| **Wave 2: 콘텐츠 중복 방지 게이트** | relevance_scorer.py 통과율 100% = 게이트가 아무것도 걸러내지 못함. 같은 공고 ID 반복 재탕 사례도 확인되어 근본 원인 대응 필요 |
| **Wave 3: ROI 개선 (측정 인프라만 정비)** | 콘텐츠 결함 수정 전 GSC 노출 늘리기 작업은 비효율. robots.txt/sitemap 정합성 점검과 GSC 매핑 정상화만 최소 실행 |
| **SEO Ops 뒤로 미룸** | 색인율 저조의 주원인이 구조적 콘텐츠 반복성으로 판단되어, 기술적 SEO보다 콘텐츠 수정이 선행되어야 함 |
| **A/B 실험 실행 명시적 보류** | 월간 페이지뷰 30~70 수준으로 표본 부족. 인프라만 준비 |
| **콘텐츠 템플릿 다양화 별도 웨이브 미포함** | 이 phase에서는 발행 로직 결함 수정과 중복 게이트까지만 scope. 템플릷 다양화는 별도 phase로 분리 |

---

## Phase 구조: 4개 Wave (단계적 롤아웃 원칙)

**원칙:** 각 Wave는 **단일 블로그 1개에 먼저 적용 → 결과 검토 → 나머지로 확산**. 전체 블로그 동시 적용 금지.

---

## Wave 1: 발행 로직 결함 수정 (최우선)

**Exit Criteria:** 샘플 10건 재발행 시 표 번호/문구 불일치 0건, 카테고리 무관 푸터 0건

### Task 1-1: 표 번호 연속성 검증 추가

**File:** `shared/post_validator.py`

**기존 동작:** 표를 생성하는 코드에서 필터링된 행을 제외한 최종 행 순서대로 번호를 부여하지 않고, 원본 데이터 인덱스를 그대로 사용 → 1, 3, 4, 5처럼 건너뜀

**수정 계획:**
- `post_validator.py` (또는 writer.py 표 생성 함수)에 후처리 단계 추가
- 정규식 `^\d+\.\s` 로 표 행 번호를 스캔 → 연속성 검사 (`1,2,3...` 아닌 경우 WARNING 반환)
- 필터링된 표의 경우 행 번호를 1부터 재부여하는 함수 추가
- `table_number_contiguous` 필드를 article_quality에 기록

**산출물:**
- 수정 전 샘플 (현재): `rap-hugo` 최근 5건 중 표 번호 불연속 사례 캡처
- 수정 후 샘플: 동일 데이터로 재생성 시 번호 1부터 연속 적용 확인

### Task 1-2: "총 N건" 문구와 실제 표 행수 일치 검증

**File:** `shared/post_validator.py`

**기존 동작:** 본문 서두 "총 N건의 공고가 확인되는데" 에서 N이 하드코딩 또는 필터링 전 원본 개수 사용 → 실제 표 행수와 불일치

**수정 계획:**
- 본문 내 정규식 `총\s*(\d+)건` 추출 → 실제 표 행수(`<tr>` 개수 또는 markdown `|` 행 수)와 비교
- 불일치 시 WARNING 반환 + `count_mismatch_bug` 플래그 설정
- 게이트 통과 조건: 불일치 차이가 1 이내 허용, 그 이상은 발행 보류

**산출물:**
- 수정 전: "총 15건" 문구 + 실제 표 12행 (예시)
- 수정 후: 동일 데이터에서 자동 보정 또는 검증 실패로 발행 차단

### Task 1-3: 공고 유형별 가점제 설명 조건 분기

**File:** `pipelines/rap/writer.py` (또는 본문 섹션 조립 파일)

**기존 동작:** "청약 자격 요건" 섹션에 무주택기간/부양가족수/청약통장 가입기간 점수(만점 84점) 설명이 **모든 공고 유형**에 삽입

**수정 계획:**
- 공고 유형 판별: 데이터의 `category` 또는 `house_type` 필드 확인
- 추첨 위주 유형(`매입임대`, `든든전세주택`, `행복주택` 등) → 가점제 설명 블록 **건너뛰기**
- 대체 문구: "이 유형은 가점제가 아닌 추첨 방식으로 운영되며, 소득·자산 기준 충족 여부가 관건입니다"
- 가점제 적용 유형(`분양주택`, `국민임대` 등) → 기존 가점제 설명 유지

**산출물:**
- 수정 전: 매입임대 공고에 가점제 설명 삽입 (스크린샷/샘플)
- 수정 후: 매입임대 공고에 추첨 설명으로 대체

### Task 1-4: 쿠팡 파트너스 푸터 조건부 삽입

**File:** `shared/publisher.py` 또는 `shared/publishers/hugo_writer.py`

**기존 동작:** "이 포스팅은 쿠팡 파트너스 활동의 일환으로..." 문구가 모든 글에 무조건 삽입

**수정 계획:**
- 본문에 쿠팡 어필리에이트 링크(`coupang.com` 또는 `track.coupang.com` 도메인)가 포함된 경우만 푸터 삽입
- 카테고리 기반 화이트리스트/블랙리스트 추가:
  - `blacklist_categories = ["청약", "부동산시세", "세금", "브랜드분석"]` → 쿠팡 푸터 생략
  - `whitelist_categories` 존재 시 해당 카테고리만 푸터 삽입
- config에 `config/category_rules.yaml` 신설로 운영 변경 가능하게

**산출물:**
- 영향 받는 블로그 목록: `rap-hugo~rap5`, `hotissue-hugo` 등 쿠팡과 무관한 카테고리
- 수정 전: 청약 정보 글 하단에 쿠팡 푸터 노출
- 수정 후: 쿠팡 링크 없으면 푸터 미노출

---

## Wave 2: 콘텐츠 중복 방지 게이트 (핵심)

**Exit Criteria:** rap-hugo 1개 블로그에 게이트 적용 + 최근 7일 dry-run에서 duplicate_hold 비율 10% 이상 확인

### Task 2-1: duplicate_gate.py 신설

**File:** `shared/duplicate_gate.py` (new)

**기능:**
1. 입력: `blog_id`, `source_data_ids` (list of 공고 ID)
2. 같은 `blog_id`에서 최근 7일간 발행된 글들의 `source_data_ids` 조회
   - `stap_content.db.articles` 에 `source_ids` 컬럼이 없으면 **마이그레이션 먼저**
3. Jaccard 유사도 또는 교집합/신규 건수 비율 계산
4. threshold 이상(기본 60%, 블로그별 config 조정 가능) → `duplicate_hold` 상태 반환 + 기존 겹치는 글의 `article_id` 로그 기록

**DB 마이그레이션:**
```sql
ALTER TABLE articles ADD COLUMN source_ids TEXT DEFAULT '[]';
-- 또는 별도 테이블 article_sources (article_id, source_id) 생성
```

**산출물:**
- `shared/duplicate_gate.py` 모듈
- 마이그레이션 스크립트 `scripts/migrate_add_source_ids.py`

### Task 2-2: RAP 파이프라인에 게이트 hook 연결

**File:** `pipelines/rap/pipeline.py`

**수정 계획:**
- 글 생성 직후, 발행 전에 `duplicate_gate.check(blog_id, source_data_ids)` 호출
- `duplicate_hold` 반환 시:
  - 발행 건너뜀
  - 로그: `"겹치는 공고 ID 비율 N%로 발행 보류 (기존 article_id: {id})"`
  - 기존 글을 업데이트하는 후속 플로우로 연결 가능하도록 `existing_article_id` 반환

**산출물:**
- 수정 전 `pipeline.py` 흐름도
- 수정 후 흐름도 + dry-run 로그 10건 샘플

### Task 2-3: rap-hugo 1개 블로그에 우선 적용 + dry-run 검증

**대상:** `rap-hugo` (RAP 5개 중 가장 발행량 많음, 446건/전체)

**dry-run 시나리오:**
- 최근 7일치 `rap-hugo` 발행 로그(약 30~40건)를 replay
- 각 건에 대해 `duplicate_gate` 평가
- 결과:
  - `ok`: 발행 허용 (예상 60~70%)
  - `duplicate_hold`: 발행 보류 (예상 20~30%)
  - `error`: 게이트 평가 실패 (예상 5% 미만)

**산출물:**
- dry-run 결과 표: 실행일, 총 시도건, ok 건수, duplicate_hold 건수, overlap source IDs, error 건수

### Task 2-4: relevance_scorer.py 통과율 100% 원인 분석 + 임계값 재설정

**File:** `shared/relevance_scorer.py`

**조사 결과:**
- 현재 `default threshold = 0.75`, 일부 블로그 `0.55`
- OFFTOPIC_THRESHOLD = 0.20 (주간 off-topic 비율 20% 초과 시 경고)
- 실제 curation.db publish_log 30일 평균: avg_relevance 0.92, min 0.80 → **모두 threshold보다 높게 나옴**

**원인 분석:**
- threshold가 지나치게 낮거나 (0.55는 사실상 거의 모든 글 통과)
- OR 스코어링 로직 자체가 관대하게 설계됨
- 가드 역할을 하는 다른 게이트(유사도 체크, 필터링 로직)가 실질적으로는 작동 안 함

**재설정 계획:**
1. 먼저 최근 30일 relevance_score 분포를 스코어링 (현재 임계값 아래로 떨어진 글 비율 계산)
2. 만약 현재 threshold 아래 비율이 5% 미만이면 threshold를 **현재 유지하되**, 스코어링 알고리즘 자체를 재검토
3. 만약 5% 이상이면 threshold를 블로그별로 상향 조정 (0.65 → 0.75, 0.75 → 0.85 방식)
4. 변경 후 dry-run으로 새 threshold 하에서 통과율 80~85% 목표

**산출물:**
- 현재 relevance_score 히스토그램 (bins: 0.0~0.5, 0.5~0.6, 0.6~0.7, 0.7~0.8, 0.8~0.9, 0.9~1.0)
- 제안 임계값 + 예상 통과율
- 실제 변경은 Wave 2 검증 후 승인받아 적용

---

## Wave 3: 기술적 SEO 위생 관리 (최소 범위)

**Exit Criteria:** robots.txt/sitemap.xml 정합성 확인 완료, GSC 사이트 매핑 누락 보완

### Task 3-1: robots.txt / sitemap.xml 정합성 점검

**확인 항목:**
1. Hugo 빌드 출력(`public/robots.txt`, `public/sitemap.xml`)이 실제로 생성되는지
2. `robots.txt`에 `Disallow:` 규칙이 없는지 (필요시 `/api/`, `/posts/` 등은 허용)
3. `sitemap.xml`에 발행 글이 실제로 포함되는지 (URL 목록 수 vs stap_content.db published 수 대조)
4. `hugo.toml` 또는 `config/_default/hugo.toml` 에 `sitemap` 설정 존재 여부

**산출물:**
- 스크린샷 또는 `curl` 결과: robots.txt 내용, sitemap.xml URL 개수
- 이상 없으면 PASS, 이상 있으면 수정 제안서 (이 단계에서는 코드 수정 안함, 보고만)

### Task 3-2: analytics_collector.py GSC 사이트 매핑 보완

**File:** `shared/analytics_collector.py`

**현황:** `GSC_SITES`에 매핑된 사이트 수 제한 → 일부 블로그가 누락되어 데이터 수집 안 됨

**수정 계획 (이 단계에서는 매핑 추가만):**
1. `config/blogs.d/*.yaml` 의 `gsc_site` 또는 `domain` 필드를 스캔
2. `analytics_collector.py` `URL_TO_BLOG_ID` 및 `GA4_PROPERTIES` 에 누락된 매핑 추가
3. 누락된 블로그 목록 산출: `gsc_daily_summary`에 0 레코드인 blog_id 목록

**제외:** IndexNow 재제출, 키워드 리서치/경쟁사 갭 분석 등 "적극적 노출 확대" 작업은 이 웨이브에서 제외 → 별도 Wave로 이관

---

## Wave 4: Growth Engine A/B 인프라 준비 (실험 실행 명시적 보류)

**Exit Criteria:** A/B 정책 문서 작성, 인프라 코드 비활성화 상태로 main 반영

### Task 4-1: A/B 테스트 정책 문서 작성

**File:** `docs/ab_testing_policy.md` (new)

**반드시 포함할 정량 기준:**
```
실험 실행 가능 조건:
- 블로그당 월간 조회수 >= 1,000 (현재 트래픽의 약 15배)
- 최근 7일간 GSC 노출 >= 500
- 위 조건을 만족하는 블로그가 3개 이상일 때만 real experiment 허용
현재 상태 (2026-07-30 기준): 모든 블로그가 조건 미달 → 실험 보류
```

### Task 4-2: shared/ab_testing/ 인프라 코드 (비활성화 상태)

**Directory:** `shared/ab_testing/`

**Files:**
- `experiment.py`: variant_id, blog_id, start_date, end_date, variant_key 저장
- `assignment.py`: `blog_id + visitor_ip_hash → variant` 할당 (sticky)
- `metrics.py`: `analytics.db.ga4_daily` 에서 blog_id + 날짜별 page_views/sessions 집계

**상태:** `__init__.py`만 생성하고, 실제 호출 코드는 주석 처리 또는 feature flag로 비활성화

### Task 4-3: GA4 실험 측정항목 준비 (비활성화)

**File:** `shared/analytics_collector.py`

**계획:**
- `ga4_daily` 스키마에 `experiment_id`, `variant_id` 컬럼 추가 (미래 사용)
- `gtag` 스니펫에 experiment_id 전파 위치 주석으로 표시
- 실제 데이터 수집은 비활성화

---

## 전체 실행 로드맵 (실행 순서)

```
Wave 1 (즉시, 리스크 낮음)
  ├─ Task 1-1: 표 번호 연속성 검증
  ├─ Task 1-2: "총 N건" 문구 불일치 검증
  ├─ Task 1-3: 가점제 설명 조건 분기
  └─ Task 1-4: 쿠팡 푸터 조건부 삽입
      ↓ [단일 블로그 샘플 10건 검증]
      ↓ [결과 검토 → 문제 없으면 전체 블로그에 확산]

Wave 2 (Wave 1 완료 후)
  ├─ Task 2-1: duplicate_gate.py + 마이그레이션
  ├─ Task 2-2: RAP pipeline hook 연결
  ├─ Task 2-3: rap-hugo 1개 블로그 dry-run
  └─ Task 2-4: relevance threshold 원인 분석 + 재설정
      ↓ [dry-run 결과 보고 → 승인 후 나머지 블로그 확산]

Wave 3 (Wave 2 완료 후, 최소 범위)
  ├─ Task 3-1: robots.txt / sitemap.xml 정합성 점검
  └─ Task 3-2: GSC 사이트 매핑 누족 보완

Wave 4 (Wave 3 완료 후, 인프라만)
  ├─ Task 4-1: A/B 정책 문서
  ├─ Task 4-2: ab_testing 모듈 (비활성)
  └─ Task 4-3: GA4 측정항목 준비 (비활성)
```

---

## 단계적 롤아웃 원칙 (명시)

각 Task는 다음 순서를 따름:
1. **단일 블로그 1개에만 먼저 적용** (예: rap-hugo, travel2-hugo)
2. **dry-run 또는 샘플 10건 재발행** 으로 수정 효과 확인
3. **결과 보고** → 문제 없으면 동일 카테고리 블로그로 확산
4. **전체 블로그 동시 적용 금지** — 결함이 발견될 경우 영향 범위를 최소화

---

## 검증 명령어 모음

### Wave 1 검증
```bash
# 표 번호 검증
python3 -c "
from shared.post_validator import validate_post_html
html = open('public/posts/sample/index.html').read()
v = validate_post_html(html, 'rap-hugo')
print('table_issues:', [i for i in v['issues'] if 'table' in i['check']])
"

# 총 N건 검증
python3 -c "
from shared.post_validator import validate_post_html
v = validate_post_html(body_html, 'rap-hugo')
mismatch = [i for i in v['issues'] if 'count_mismatch' in i['check']]
print('mismatch:', mismatch)
"
```

### Wave 2 검증
```bash
# duplicate_gate dry-run
python3 -c "
from shared.duplicate_gate import check
result = check('rap-hugo', ['announcement_12345', 'announcement_67890'])
print(result)
"

# relevance threshold 분포
sqlite3 data/curation.db "
SELECT 
  CASE 
    WHEN avg_relevance_score < 0.5 THEN '0.0~0.5'
    WHEN < 0.6 THEN '0.5~0.6'
    WHEN < 0.7 THEN '0.6~0.7'
    WHEN < 0.8 THEN '0.7~0.8'
    WHEN < 0.9 THEN '0.8~0.9'
    ELSE '0.9~1.0'
  END as score_bin, COUNT(*) as cnt
FROM publish_log
WHERE published_at >= date('now', '-30 days')
GROUP BY score_bin
ORDER BY score_bin;
"
```

### Wave 3 검증
```bash
# robots.txt / sitemap.xml 확인
curl -s https://rap-hugo.rotcha.kr/robots.txt | head -20
curl -s https://rap-hugo.rotcha.kr/sitemap.xml | grep '<url>' | wc -l

# GSC 매핑 누락 확인
python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
print('Mapped blogs:', len(c.GSC_SITES))
"
```

### Wave 4 검증
```bash
python3 -c "
from shared.ab_testing.experiment import create_experiment
e = create_experiment('rap-hugo', 'title_test', ['A','B'], [0.5,0.5])
print('experiment_id:', e['id'])
"
```

---

## 리스크 & 대응

| 리스크 | 발생 확률 | 영향 | 대응 |
|--------|----------|------|------|
| Wave 1 수정으로 기존 발행된 글의 표가 깨짐 | Medium | Medium | 수정은 신규 글부터 적용, 기존 글은 별도 마이그레이션 스크립트로 선택적 적용 |
| relevance threshold 상향으로 발행량 급감 | Medium | High | 2단계 상향 (0.75 → 0.80), 1주일 모니터링 후 조정 |
| duplicate_gate false positive (우려) | Medium | Medium | threshold 60%로 시작, 실제 데이터 보면서 50~70% 사이 튜닝 |
| GSC 데이터 부족으로 SEO 효과 측정 불가 | High | Medium | Wave 3에서는 "정합성 점검"만 목표, 효과 측정은 Wave 4에서 |

---

## 이전 버전 대비 변경 요약

| 항목 | 이전 PLAN | 변경 후 PLAN |
|------|----------|--------------|
| **Wave 1 순서** | SEO Ops 우선 → Quality Gate | **발행 로직 결함 수정** 우선 (품질 게이트 강화 전 필수) |
| **Wave 2** | "템플릿 다양화 별도" 부록 처리 | **공식 Wave 승격**: duplicate_gate + relevance threshold 재설정 |
| **Wave 3** | IndexNow, 키워드 리서치 포함 | **최소 범위로 축소**: robots.txt/sitemap 정합성 + GSC 매핑만 |
| **Wave 4** | A/B 인프라 + GA4 준비 | 동일 (실험 실행 명시적 보류 유지) |
| **SEO Ops** | Wave 1에 포함 | **Wave 3으로 후순위** (콘텐츠 개선 선행) |
| **템플릿 다양화** | 별도 phase로 분리 권장 | 이 phase에서 제외, duplicate_gate로 대체 |
| **근거 추가** | 일반적 서술 | 각 결정에 "조사 기반 근거" 명시 (GSC 22,608 노출, 151 클릭 등) |
| **단계적 롤아웃** | 미명시 | **명시적 추가**: 단일 블로그 → 검증 → 확산 원칙 |

---

## Next Up

```text
───────────────────────────────────────────────────────────────
## ▶ Next Up

**Wave 1: 발행 로직 결함 수정** — post_validator.py 확장 + 조건 분기 추가

`/clear` then:

`Wave 1-1: 표 번호 연속성 검증 추가부터 시작해 주세요.`
───────────────────────────────────────────────────────────────
```

---

## Anti-Patterns 방지
- SEO 도구(IndexNow, 키워드 리서치)를 콘텐츠 결함 수정 전에 실행하지 않음
- 전체 블로그 동시 적용 대신 단일 블로그 → 검증 → 확산
- A/B 실험은 인프라만 구축, 실제 실행은 정량 기준(월 PV 1,000) 달성 시까지 보류
- threshold 상향은 2단계로 점진적 적용, 발행량 급감 방지
