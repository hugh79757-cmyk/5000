# Travel-Hugo 발행 (Travel-Hugo Publish)

> travel-hugo (tour1.rotcha.kr) 블로그 발행에 특화된 스킬.
> 여행 파이프라인 실행, 쿼터 우회 발행, Hugo 빌드/배포를 다룬다.

## 개요

**travel-hugo**는 5000 프로젝트의 TAP(Travel Auto Publisher) 파이프라인이 생성하는 Hugo 기반 여행 블로그.

- **도메인:** tour1.rotcha.kr
- **사이트 경로:** `/Users/twinssn/Projects/TAP/travel-hugo`
- **저장소:** `/Users/twinssn/Projects/TAP/travel-hugo`
- **플랫폼:** Hugo + Cloudflare Pages
- **파이프라인:** `pipelines/travel/pipeline.py`
- **일일 쿼터:** 3건
- **스케줄:** 07:00, 10:00, 13:00, 16:00, 20:00

## 여행 파이프라인 구조

### 데이터 소스 (BLOG_FETCH_MAP)

| 소스 타입 | 가중치 | fetcher 함수 | 설명 |
|-----------|--------|-------------|------|
| camping | 0.45 | `fetch_camping` | 캠핑장 데이터 (고캠핑 API) |
| korservice | 0.25 | `fetch_korservice` | 관광지/명소 데이터 |
| wellness | 0.15 | `fetch_wellness` | 웰니스/스파 데이터 |
| heritage | 0.15 | `fetch_heritage` | 문화유산 데이터 |

### 발행 흐름

```
fetch_camping/korservice/wellness/heritage()
  → 데이터 필터링 (테마, 시군구, 이미지 유무)
  → 시군구 중복 체크 (최근 3일)
  → 가게명 중복 체크 (used_places)
  → generate_content() — AI 본문 생성
  → validate_post_extended() — 발행 전 검증
  → publish() — Hugo 파일 저장
  → nearby_info 카드 삽입
  → 이미지 등록
```

### 프롬프트 맵

| source_type | prompt_id |
|-------------|-----------|
| camping | tour1_camping |
| korservice | (기본) |
| wellness | (기본) |
| heritage | (기본) |

프롬프트는 `config/prompts/travel.yaml`에서 확인.

## 정상 발행 (쿼터 내)

```bash
cd /Users/twinssn/Projects/5000
python3 dispatcher.py travel-hugo
```

**출력 예시:**
```json
{"success": true, "url": "https://tour1.rotcha.kr/posts/...", "slug": "...", "title": "..."}
```

## 쿼터 우회 발행

오늘 이미 3건 발행되어 쿼터가 소진된 경우, 우회하여 추가 발행 가능.

### 방법 1: 직접 파이프라인 호출 (권장)

`scripts/force_publish_travel.py` 스크립트 사용:

```bash
cd /Users/twinssn/Projects/5000
python3 scripts/force_publish_travel.py
```

이 스크립트는:
- dispatcher의 `_is_duplicate()` 체크 우회
- pipeline 내부 quota 체크 우회 (`blog_cfg["daily_quota"] = 999`)
- `_run_single()` 직접 호출

### 방법 2: 코드 수정으로 5곳 우회

`quota-bypass-publish` 스킬 참조. 5곳 우회를 적용 후 발급:

```bash
cd /Users/twinssn/Projects/5000

# 1. 우회 적용 (5곳)
sed -i '' 's/if current >= quota:/if False and current >= quota:/' pipelines/travel/pipeline.py
sed -i '' 's/if _is_duplicate(blog_id):/if False and _is_duplicate(blog_id):/' dispatcher.py
sed -i '' 's/if today_count >= blog_cfg/if False and today_count >= blog_cfg/' shared/publisher.py
sed -i '' 's/if len(_used_places) >= _dup_threshold:/if False and len(_used_places) >= _dup_threshold:/' pipelines/travel/pipeline.py
python3 -c "import json;d=json.load(open('data/cooldown.json'));d.pop('daily_travel-hugo',None);json.dump(d,open('data/cooldown.json','w'),indent=2)"

# 2. 발행
python3 dispatcher.py travel-hugo

# 3. 원복 (반드시 실행)
sed -i '' 's/if False and current >= quota:/if current >= quota:/' pipelines/travel/pipeline.py
sed -i '' 's/if False and _is_duplicate(blog_id):/if _is_duplicate(blog_id):/' dispatcher.py
sed -i '' 's/if False and today_count >= blog_cfg/if today_count >= blog_cfg/' shared/publisher.py
sed -i '' 's/if False and len(_used_places) >= _dup_threshold:/if len(_used_places) >= _dup_threshold:/' pipelines/travel/pipeline.py
```

### 방법 3: 저장소 직접 확인

발급된 글은 저장소에 저장됨:

```bash
ls -lt /Users/twinssn/Projects/TAP/travel-hugo/content/posts/ | head -5
```

## 발행 후 Hugo 빌드/배포

### 로컬 빌드 테스트

```bash
cd /Users/twinssn/Projects/TAP/travel-hugo
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify
```

### Cloudflare Pages 배포

dispatcher.py가 자동으로 처리함 (dispatcher.py 실행 시 배포까지 수행).

수동 배포가 필요한 경우:

```bash
cd /Users/twinssn/Projects/5000
python3 -c "
import sys
sys.path.insert(0, '.')
from shared.publishers.deploy import deploy_site
deploy_site('/Users/twinssn/Projects/TAP/travel-hugo', 'travel-hugo')
"
```

또는 wrangler 직접 사용:

```bash
cd /Users/twinssn/Projects/TAP/travel-hugo
env -u CLOUDFLARE_API_TOKEN wrangler pages deploy public --project-name=travel-hugo
```

## 현재 발행 건수 확인

```bash
cd /Users/twinssn/Projects/5000
python3 -c "
import sqlite3
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
conn = sqlite3.connect('data/content.db')
count = conn.execute(
    \"SELECT COUNT(*) FROM publish_ledger WHERE blog_id='travel-hugo' AND DATE(created_at)=?\", 
    (today,)
).fetchone()[0]
conn.close()
print(f'today count: {count} / 3')
"
```

## 발행글 확인

### 파일 시스템

```bash
# 최신 발행글
ls -lt /Users/twinssn/Projects/TAP/travel-hugo/content/posts/ | head -3

# 특정 글의 frontmatter 확인
head -15 /Users/twinssn/Projects/TAP/travel-hugo/content/posts/<slug>/index.md
```

### 라이브 사이트

- https://tour1.rotcha.kr/
- https://tour1.rotcha.kr/posts/<slug>/

## 여행 파이프라인 주요 파일

| 파일 | 역할 |
|------|------|
| `pipelines/travel/pipeline.py` | 발행 파이프라인 메인 |
| `pipelines/travel/writer.py` | AI 본문 생성 (prompt + GPT 호출) |
| `pipelines/travel/fetcher.py` | 데이터 수집 (캠핑/관광/맛집/문화유산) |
| `config/prompts/travel.yaml` | 프롬프트 정의 |
| `shared/coupang_travel.py` | 쿠팡 파트너스 상품 카드 |
| `core/content_processor.py` | 본문 후처리 (이미지, nearby 등) |
| `core/nearby_info.py` | 주변 관광지/맛집 정보 |

## 주의사항

- 쿼터 우회 발행 후 **반드시 원복**할 것
- `_used_places` 우회 시 중복 콘텐츠 발행 가능성 있음
- 우회 발행은 테스트/디버깅 목적으로만 사용
- 일일 3건 제한을 반드시 지켜야 하는 경우 우회 금지

## 관련 스킬

- `quota-bypass-publish` — 일반 쿼터 우회 방법 (5곳)
- `tap-blog-spec` — TAP 블로그 본문 규격
- `hugo-blowfish-standardization` — Hugo 블로그 표준화
- `wrangler-deployment-patterns` — Cloudflare Pages 배포 패턴
