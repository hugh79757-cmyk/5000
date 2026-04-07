# 블로그 등록 가이드

> 새 Hugo 블로그를 Blogdex-Lite 시스템에 등록하는 전체 절차

---

## 1. 등록이 필요한 파일 (2개)

| 파일 | 경로 | 역할 |
|---|---|---|
| sites.yaml | `dashboard/sites.yaml` | 대시보드 표시 + GSC 도메인 매핑 |
| blogs.yaml | `config/blogs.yaml` | 발행 스케줄 + GA4 프로퍼티 + 파이프라인 |

### 등록이 불필요한 모듈

| 모듈 | 이유 |
|---|---|
| GSC | sc-domain 방식으로 루트 도메인(rotcha.kr 등) 하위 서브도메인 자동 수집. sites.yaml에 domain만 등록하면 됨 |
| AdSense | 3개 계정의 모든 도메인을 자동 수집. 등록 불필요 |
| Bing | API 키로 등록된 사이트 자동 탐색. Bing Webmaster에서 사이트 추가만 하면 됨 |
| 효율점수 | gsc_daily_summary + blog_efficiency에서 blog_id 기준 자동 산정 |

---

## 2. 단계별 등록 절차

### STEP 1: sites.yaml에 추가

경로: `/Users/twinssn/Projects/5000/dashboard/sites.yaml`
```yaml
# 파일 끝 sites: 리스트에 추가
- domain: 서브도메인.루트도메인.kr
  blog_id: 블로그id-hugo
  group: 그룹명
```

**규칙:**
- `domain`: 실제 접속 도메인 (예: `camping.rotcha.kr`)
- `blog_id`: Hugo 프로젝트명과 동일하게 (예: `camping-hugo`)
- `group`: 아래 그룹 중 선택

| group 값 | 설명 |
|---|---|
| car | 자동차 |
| travel | 여행(KR) |
| rap | 부동산 |
| senior | 시니어 |
| curation | 큐레이션 |
| sports | 스포츠 |
| main | 메인 |
| stock | 주식 |
| etap | ETAP 여행(EN) |

### STEP 2: config/blogs.yaml에 추가

경로: `/Users/twinssn/Projects/5000/config/blogs.yaml`
```yaml
# blogs: 리스트에 추가
- id: camping-hugo
  name: 캠핑
  domain: camping.rotcha.kr
  cf_project: camping-hugo
  repo: camping-hugo
  platform: hugo
  pipeline: travel          # car / travel / rap / senior / curation / stock / etap
  daily_quota: 5            # 하루 발행 수
  status: active
  post_type:
  - 포스트타입1
  - 포스트타입2
  prompt:
    포스트타입1: 프롬프트경로1.md
    포스트타입2: 프롬프트경로2.md
  schedule:
    times:
    - '07:10'
    - '13:10'
    - '19:10'
```

**필수 필드:**
- `id`: sites.yaml의 blog_id와 동일
- `domain`: sites.yaml의 domain과 동일
- `pipeline`: 어떤 파이프라인으로 발행할지
- `schedule.times`: 발행 시각 (24시간 형식)
- `daily_quota`: 하루 최대 발행 건수

**선택 필드:**
- `ga4_property`: GA4 프로퍼티 ID (숫자). GA4에 등록된 경우만 추가
- `post_type` + `prompt`: 파이프라인별 포스트 유형과 프롬프트 파일 경로

### STEP 3: GA4 프로퍼티 등록 (해당 시)

GA4에 새 블로그를 추가한 경우, `config/blogs.yaml`에 `ga4_property` 필드 추가:
```yaml
- id: camping-hugo
  ga4_property: 123456789    # GA4 Admin > 프로퍼티 ID
  ...
```

GA4 프로퍼티 ID 확인법:
1. Google Analytics → 관리 → 프로퍼티 설정
2. 오른쪽 상단 프로퍼티 ID (숫자만)

### STEP 4: Bing Webmaster 등록 (선택)

1. https://www.bing.com/webmasters 접속
2. 사이트 추가: `https://서브도메인.루트도메인.kr`
3. DNS 인증 (CNAME 레코드)
4. 등록 후 bing_collector.py가 자동 탐색 — 별도 코드 수정 불필요

### STEP 5: Cloudflare Pages 배포 설정

1. Cloudflare Dashboard → Pages → 새 프로젝트
2. GitHub 레포 연결: `camping-hugo`
3. 빌드 설정: Framework `Hugo`, Build command `hugo`, Output `public`
4. 커스텀 도메인: `camping.rotcha.kr`
5. DNS에 CNAME 자동 추가됨

### STEP 6: 검증
```bash
cd /Users/twinssn/Projects/5000
source .venv/bin/activate

# sites.yaml 파싱 확인
python3 -c "
import yaml
with open('dashboard/sites.yaml') as f:
    data = yaml.safe_load(f)
sites = [s for s in data['sites'] if s['blog_id'] == 'camping-hugo']
print('sites.yaml:', 'OK' if sites else 'NOT FOUND')
"

# blogs.yaml 파싱 확인
python3 -c "
import yaml
with open('config/blogs.yaml') as f:
    data = yaml.safe_load(f)
blogs = [b for b in data['blogs'] if b['id'] == 'camping-hugo']
print('blogs.yaml:', 'OK' if blogs else 'NOT FOUND')
"

# GSC 수집 테스트 (새 블로그 포함 확인)
python3 analytics/gsc_collector.py 2>&1 | grep camping

# 대시보드에서 확인
curl -s -u admin:blogdex2026! http://127.0.0.1:5050/ | grep camping
```

---

## 3. 빠른 체크리스트

새 블로그 `XXX-hugo` (도메인: `xxx.rotcha.kr`, 그룹: travel) 등록 시:

- [ ] `dashboard/sites.yaml`에 3줄 추가 (domain, blog_id, group)
- [ ] `config/blogs.yaml`에 블로그 블록 추가 (id, domain, pipeline, schedule, daily_quota)
- [ ] GA4 등록했으면 `ga4_property` 필드 추가
- [ ] Bing Webmaster에 사이트 추가 (선택)
- [ ] Cloudflare Pages 프로젝트 생성 + 커스텀 도메인
- [ ] GitHub 레포 생성 + 초기 Hugo 구조 push
- [ ] 검증 스크립트 실행

---

## 4. 현재 sc-domain 목록 (GSC)

sites.yaml에 등록하면 아래 4개 루트 도메인의 서브도메인으로 자동 매핑됨:

| sc-domain | 루트 도메인 |
|---|---|
| sc-domain:rotcha.kr | rotcha.kr |
| sc-domain:informationhot.kr | informationhot.kr |
| sc-domain:techpawz.com | techpawz.com |
| sc-domain:aikorea24.kr | aikorea24.kr |

**새 루트 도메인을 추가하는 경우** (예: newsite.com):
1. `analytics/gsc_collector.py`의 `SC_DOMAINS` 리스트에 추가:
```python
   SC_DOMAINS = [
       "sc-domain:rotcha.kr",
       "sc-domain:informationhot.kr",
       "sc-domain:techpawz.com",
       "sc-domain:aikorea24.kr",
       "sc-domain:newsite.com",    # 추가
   ]
```
2. Google Search Console에서 `sc-domain:newsite.com` 프로퍼티 등록 + DNS 인증

---

## 5. AdSense 계정 매핑

AdSense는 도메인별 자동 수집이므로 등록 불필요. 단, 새 도메인이 AdSense에 승인되어야 수익 집계됨.

| 계정 | pub ID | 주요 루트 도메인 |
|---|---|---|
| twinssn | ca-pub-8772455780561463 | rotcha.kr, techpawz.com |
| informationhot | ca-pub-6677996696534146 | informationhot.kr |
| aikorea24 | ca-pub-5938862195544185 | aikorea24.kr |

새 도메인의 AdSense 승인 절차:
1. AdSense 대시보드 → 사이트 → 사이트 추가
2. ads.txt 파일을 Hugo 프로젝트 `static/ads.txt`에 배치
3. 심사 통과 후 자동 수집 시작

---

## 6. 크리덴셜 경로

| 용도 | 경로 | 머신 |
|---|---|---|
| GSC/GA4 OAuth | `/Users/twinssn/Projects/5000/data/google_token.pickle` | M1, M4 |
| AdSense (twinssn) | `/Users/twinssn/Projects/blogdex/credentials/adsense_token_1_twinssn.pickle` | M1, M4 |
| AdSense (informationhot) | `/Users/twinssn/Projects/blogdex/credentials/adsense_token_2_informationhot.pickle` | M1, M4 |
| AdSense (aikorea24) | `/Users/twinssn/Projects/blogdex/credentials/adsense_token_3_aikorea24.pickle` | M1, M4 |
| Bing API keys | `.env` 파일 (`BING_WEBMASTER_API_KEY`, `_2`, `_3`) | M1, M4 |
| Blogger API | `/Users/twinssn/Projects/5000/config/blogger_token.json` | M1, M4 |

토큰 만료 시 재발급:
```bash
cd /Users/twinssn/Projects/5000
source .venv/bin/activate
python3 -c "
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES = ['https://www.googleapis.com/auth/adsense.readonly']
flow = InstalledAppFlow.from_client_secrets_file(
    'credentials/ADSENSE_CREDENTIALS_1twinssn.json', SCOPES)
creds = flow.run_local_server(port=0)
with open('credentials/adsense_token_1_twinssn.pickle', 'wb') as f:
    pickle.dump(creds, f)
"
```

---

*최종 업데이트: 2026-04-06*
