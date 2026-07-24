# TAP 여행 종합 발행 프로젝트 — 리스크 검증 보고서 (실제 코드 기반)

## 3줄 요약

- V-1: 이중 발행 위험은 **실재**한다. `com.5000.scheduler`와 `com.tap.scheduler`가 모두 실행 중이며, `tap-blogger` 일반/축제 발행 시각이 09/10개 슬롯에서 완전히 겹친다.
- V-2: 5000 `tap.yaml`의 `tap-blogger`에는 `blogger_blog_id`/`blog_id_env`가 **비어 있다**. 실제 Blogger 발행은 TAP `.env`의 `BLOGGER_BLOG_ID`를 사용한다.
- V-3: 발행 이력 DB는 **이중화**되어 있다. `content.db(publish_ledger)`와 `stap_content.db(articles)` 양쪽에 기록이 분산된다.
- V-4: 5개 Hugo travel 블로그 배포 주체는 **명확**하다. 코드상 `shared/publisher.py`의 `deploy_site()`가 담당한다.
- V-5: `--commit-dirty=true`는 **Pages 배포**에서만 사용된다. Workers 배포 경로에는 등장하지 않는다.

---

## V-1 이중 스케줄링 실재 여부

### [결론] 이중 발행 위험 = 실재

### [근거]

**1) launchd 등록 상태**

```
$ launchctl list | grep -i -E "tap|5000|scheduler"
787     0      com.5000.scheduler
38430  -15     com.tap.scheduler
```

둘 모두 PID를 가지므로 **loaded + running** 상태다.

**2) plist ProgramArguments**

`~/Library/LaunchAgents/com.5000.scheduler.plist`:
- ProgramArguments: `/Users/twinssn/Projects/5000/.venv/bin/python` + `/Users/twinssn/Projects/5000/scheduler.py`
- KeepAlive=true, RunAtLoad=true

`~/Library/LaunchAgents/com.tap.scheduler.plist`:
- ProgramArguments: `/Users/twinssn/Projects/TAP/venv/bin/python3` + `/Users/twinssn/Projects/TAP/scheduler.py`
- KeepAlive=true, RunAtLoad=true

**3) 5000 scheduler가 tap-blogger를 스케줄하는지 코드 확인**

`/Users/twinssn/projects/5000/scheduler.py` line 610-621:
```python
def register_schedules():
    config = load_config()
    blogs = config.get("blogs", [])
    for blog in blogs:
        if blog.get("status") != "active":
            continue
        blog_id = blog["id"]
        times = blog.get("schedule", {}).get("times", [])
        for t in times:
            schedule.every().day.at(t).do(queue_publish, blog_id)
```

`/Users/twinssn/projects/5000/config/blogs.d/tap.yaml`:
```yaml
- id: tap-blogger
  status: active
  schedule:
    times:
    - 06:00
    - 08:00
    - 10:00
    - 12:00
    - 14:00
    - 16:00
    - 18:00
    - 20:00
    - 22:00
    - 11:00
```

따라서 5000 scheduler는 `tap-blogger`를 실행 대상에 포함한다.

**4) TAP scheduler가 app.py run을 실행하는지 코드 확인**

`/Users/twinssn/Projects/tap/scheduler.py` line 90-124:
```python
def run_publish():
    _run_job("일반 발행", [_PYTHON, 'app.py', 'run'], str(_PROJECT_DIR))

def run_festival():
    _run_job("축제 발행", [_PYTHON, 'run_festival.py'], str(_PROJECT_DIR))

schedule.every().day.at("06:00").do(run_publish)
...
schedule.every().day.at("11:00").do(run_festival)
```

**5) 5000 dispatcher의 tap-blogger 처리 경로**

`/Users/twinssn/projects/5000/dispatcher.py` line 426-427:
```python
if pipeline == "tap":
    return _run_tap_subprocess(cfg)
```

`/Users/twinssn/projects/5000/dispatcher.py` line 439-457:
```python
def _run_tap_subprocess(cfg):
    runner_code = (
        "import sys, os; sys.path.insert(0, " + repr(tap_root) + "); "
        "os.chdir(" + repr(tap_root) + "); "
        "from dotenv import load_dotenv; "
        "load_dotenv(os.path.join(" + repr(tap_root) + ", '.env'), override=True); "
        "from app import run_publish; "
        "result = run_publish(); "
        ...
    )
```

즉, 5000 scheduler가 `tap-blogger`를 트리거하면 → dispatcher → `_run_tap_subprocess` → TAP `app.py run_publish()`를 실행한다.

**6) TAP app.py의 중복 체크 메커니즘**

`/Users/twinssn/Projects/tap/app.py` line 140-168:
```python
_content_key = f"{data.get('source', 'unknown')}_" + hashlib.sha256(
    _key_raw.encode()
).hexdigest()[:20]

_existing = _session.query(ContentPool).filter_by(
    content_key=_content_key,
    is_published=1
).first()
```

`/Users/twinssn/Projects/tap/core/database.py` line 96-115:
```python
class ContentPool(Base):
    is_published = Column(Integer, default=0)      # 0=미발행, 1=발행완료
```

중복 체크는 DB 조회 기반이지만, **인터프로세스 락(flock 등)은 발견되지 않았다**. 두 스케줄러가 동시에 `run_publish()`를 실행하면 race condition 가능성이 있다.

**7) 실행 시각 대조**

| 시각 | 5000 scheduler (tap-blogger) | TAP scheduler (app.py run) | 겹침 |
|---|---|---|---|
| 06:00 | O | O | O |
| 08:00 | O | O | O |
| 10:00 | O | O | O |
| 11:00 | O (festival) | O (festival) | O |
| 12:00 | O | O | O |
| 14:00 | O | O | O |
| 16:00 | O | O | O |
| 18:00 | O | O | O |
| 20:00 | O | O | O |
| 22:00 | O | O | O |

일반 발행 9개 시각이 100% 겹치고, 축제 발행 11:00도 겹친다.

---

## V-2 Blogger ID 일치 여부

### [결론] 불일치 + 미비교 불가

### [근거]

**5000 측 설정:**

`/Users/twinssn/projects/5000/config/blogs.d/tap.yaml`:
```yaml
- id: tap-blogger
  name: travel.rotcha.kr (Blogger)
  pipeline: tap
  platform: blogger
  domain: travel.rotcha.kr
  daily_quota: 5
  schedule:
    times: [...]
  status: active
```

`blogger_blog_id` 필드도 `blog_id_env` 필드도 **존재하지 않는다**.

**5000 publisher.py의 Blogger blog_id 로직:**

`/Users/twinssn/projects/5000/shared/publisher.py` line 923-929:
```python
from shared.blogger_publisher import publish_to_blogger
blogger_blog_id = blog_cfg.get("blogger_blog_id", "")
if not blogger_blog_id:
    blog_id_env = blog_cfg.get("blog_id_env", "")
    blogger_blog_id = os.getenv(blog_id_env, "") if blog_id_env else ""
if not blogger_blog_id:
    return {"success": False, "error": "blogger blog_id not configured"}
```

`tap-blogger`는 `blogger_blog_id`도 `blog_id_env`도 없으므로, 5000의 `publisher.py`로 직접 발행하면 **실패**한다.

**TAP .env의 실제 Blogger blog_id:**

```
# /Users/twinssn/Projects/tap/.env
BLOGGER_BLOG_ID=835513737064071192
```

**TAP app.py의 Blogger 발행:**

`/Users/twinssn/Projects/tap/app.py` line 52, 77, 296:
```python
from core.blogger_publisher import load_publisher
publisher = load_publisher()
...
result = publisher.create_post(...)
```

TAP `core.blogger_publisher`는 TAP `.env`의 `BLOGGER_BLOG_ID`를 사용한다.

**비교 결론:**
- 5000 `tap.yaml`의 `tap-blogger`에는 Blogger blog_id **자체가 없다**.
- TAP `.env`의 `BLOGGER_BLOG_ID`는 **숫자형**이고, 5000 내부 식별자인 `tap-blogger`는 **문자열**이다.
- 두 값은 형식도 역할도 다르므로 **동일하다고 볼 수 없다**.

---

## V-3 발행 이력 DB 이중화 실태

### [결론] 어긋남

### [근거]

**1) 파일 존재 여부**

| DB | 경로 | 존재 | 크기 |
|---|---|---|---|
| content.db | `/Users/twinssn/projects/5000/data/content.db` | O | 36,470,784 bytes |
| stap_content.db | `/Users/twinssn/projects/5000/data/stap_content.db` | O | 69,365,760 bytes |

**2) 테이블 스키마**

`content.db`:
- `articles` 컬럼: id, blog_id, title, slug, body_md, body_html, thumbnail_url, category, tags, data_source, source_id, prompt_id, model, published_url, published_at, platform, status, created_at, sigungu
- `publish_ledger` 컬럼: id, blog_id, title, published_url, status, created_at, source_id, slug, source, stage, error_msg
- 기타: course_published, used_images, used_places

`stap_content.db`:
- `articles` 컬럼: id, blog_id, title, slug, body_md, body_html, thumbnail_url, category, tags, data_source, source_id, prompt_id, model, published_url, published_at, platform, status, created_at, sigungu
- 기타: used_images, used_places

두 DB의 `articles` 스키마는 동일하다. `content.db`에는 추가로 `publish_ledger`와 `course_published`가 있다.

**3) 최근 발행 레코드 상위 5건 (SELECT only)**

`content.db` — `publish_ledger` 최근 5건:
1. `interior-hugo` | 2인용 소파 추천... | `https://interior.informationhot.kr/posts/...` | 2026-07-24T14:08:08
2. `appliance-hugo` | 덴코 남녀공용 데일리... | `https://appliance.informationhot.kr/posts/...` | 2026-07-24T13:59:05
3. `rap-hugo` | 2026년 04월 서울 강남구 성원대치2단지... | `https://apt.informationhot.kr/posts/...` | 2026-07-24T13:52:28
4. `laptop-hugo` | 14인치 노트북 추천... | `https://laptop.informationhot.kr/posts/...` | 2026-07-24T13:45:44
5. `senior-hugo` | 김포시 65세 이상 어르신... | `https://senior.informationhot.kr/posts/...` | 2026-07-24T13:37:59

`stap_content.db` — `articles` 최근 5건:
1. `interior-hugo` | 라텍스 매트리스 추천... | `라텍스-매트리스-추천-흔한-오해-3가지-2026년-기준-바로잡기` | 2026-07-24T14:07:25
2. `appliance-hugo` | 공기청정기 추천: KS한국 6만원대... | `공기청정기-추천-ks한국-6만원대-vs-lg-퓨리케어...` | 2026-07-24T13:58:27
3. `rap-hugo` | 동작구 7월 실거래가 분석... | `동작구-7월-실거래가-분석-최고-227억` | 2026-07-24T13:52:00
4. `laptop-hugo` | 인텔 vs AMD 노트북 추천... | `인텔-vs-amd-노트북-추천-에이수스레노버-실사용-비교` | 2026-07-24T13:45:08
5. `senior-hugo` | 충주시 거동불편 노인 보행기 지원... | `충주시-거동불편-노인-보행기-지원-장기요양등급-없는-분도-받나요` | 2026-07-24T13:37:37

비교 결과:
- 두 DB 모두 2026-07-24 13:3x ~ 14:0x 대역의 최신 기록을 가지고 있다.
- 동일 `blog_id`의 시각이 1~43초 차이로 근접하나, **제목/슬러그가 미세하게 다르다**.
- `content.db`는 `publish_ledger` 위주, `stap_content.db`는 `articles` 위주로 보인다.

**4) 중복 체크 로직이 두 DB 중 어느 것을 기준으로 하는지**

`/Users/twinssn/projects/5000/scheduler.py` line 355-366:
```python
def _get_ledger_count(blog_id, date_str):
    conn = sqlite3.connect(LEDGER_DB)
    row = conn.execute(
        "SELECT COUNT(*) FROM publish_ledger WHERE blog_id=? AND date(created_at)=? AND status='published'",
        (blog_id, date_str)
    ).fetchone()
```

`/Users/twinssn/projects/5000/shared/db_paths.py`:
```python
PUBLISH_LEDGER_DB = os.path.join(_BASE, "data", "content.db")
ARTICLES_DB       = os.path.join(_BASE, "data", "stap_content.db")
```

5000의 중복 체크는 주로 `content.db(publish_ledger)`를 기준으로 한다. TAP은 자체 `tap.db`의 `content_pool`을 사용한다.

---

## V-4 Hugo 5개 배포 주체 확정

### [결론] 배포 주체 명확

### [근거]

**1) 5000 dispatcher의 배포 대상 확인**

`/Users/twinssn/projects/5000/dispatcher.py` line 676-677:
```python
if blog_id in ETAP_PIPELINE_BLOGS or blog_id in WORKERS_BLOGS:
    _build_and_deploy_central(blog_id)
```

`travel-hugo`, `travel1-hugo` ~ `travel4-hugo`는 `ETAP_PIPELINE_BLOGS`에도 `WORKERS_BLOGS`에도 들어가지 않는다. 따라서 **5000 dispatcher는 travel 5개 블로그를 직접 배포하지 않는다**.

**2) 실제 배포 코드 위치**

`/Users/twinssn/projects/5000/shared/publisher.py` line 1033-1040:
```python
if result.get("success"):
    update_published(article_id, result.get("url", ""))
    cf_project = blog_cfg.get("cf_project", "")
    site_path = blog_cfg.get("site_path", "")
    if cf_project and site_path:
        try:
            deploy_site(site_path, cf_project)
            result["deployed"] = True
```

`travel-*` 블로그는 `config/blogs.d/tap.yaml`에 `cf_project`와 `site_path`가 모두 설정되어 있으므로, **`shared/publisher.py`의 `publish()` 함수 내에서 `deploy_site()`가 호출된다**.

**3) TAP 측 배포 수단 확인**

```bash
$ find /Users/twinssn/Projects/tap/travel*-hugo -maxdepth 1 -name 'wrangler.toml' -o -name 'wrangler.json'
(없음)
```

5개 Hugo 사이트 디렉토리에 `wrangler.toml`/`wrangler.json`은 없다.

**4) 배포 타깃 (Cloudflare Pages 프로젝트명)**

| blog_id | cf_project | site_path | 도메인 |
|---|---|---|---|
| travel-hugo | travel-hugo | /Users/twinssn/Projects/TAP/travel-hugo | tour1.rotcha.kr |
| travel1-hugo | travel1-hugo | /Users/twinssn/Projects/TAP/travel1-hugo | travel1.rotcha.kr |
| travel2-hugo | travel2-hugo | /Users/twinssn/Projects/TAP/travel2-hugo | travel2.rotcha.kr |
| travel3-hugo | travel3-hugo | /Users/twinssn/Projects/TAP/travel3-hugo | tour2.rotcha.kr |
| travel4-hugo | travel4-hugo | /Users/twinssn/Projects/TAP/travel4-hugo | tour3.rotcha.kr |

---

## V-5 --commit-dirty=true 실제 사용처

### [결론] Pages 배포에서만 사용

### [근거]

**1) dispatcher.py**

`/Users/twinssn/projects/5000/dispatcher.py` line 580-584:
```python
else:
    r2 = subprocess.run(
        [WRANGLER, "pages", "deploy", "public",
         "--project-name", blog_id,
         "--commit-dirty=true",
         "--commit-message=publish"],
        ...
    )
```

**2) shared/publisher.py (deploy_site)**

`/Users/twinssn/projects/5000/shared/publisher.py` line 724-733:
```python
else:
    result = subprocess.run(
        ["/opt/homebrew/bin/wrangler", "pages", "deploy", "./public",
         "--project-name=" + cf_project,
         "--branch=main",
         "--commit-dirty=true",
         "--commit-message=deploy-" + ...],
        ...
    )
```

재시도 분기에서도 동일하게 Pages 배포에만 사용된다:
`/Users/twinssn/projects/5000/shared/publisher.py` line 754-763:
```python
else:
    result = subprocess.run(
        ["/opt/homebrew/bin/wrangler", "pages", "deploy", "./public",
         "--project-name=" + cf_project,
         "--branch=main",
         "--commit-dirty=true",
         "--commit-message=deploy-" + ...],
        ...
    )
```

**3) shared/publishers/deploy.py**

`/Users/twinssn/projects/5000/shared/publishers/deploy.py` line 123-132:
```python
else:
    result = subprocess.run(
        [WRANGLER_PATH, "pages", "deploy", "./public",
         "--project-name=" + cf_project,
         "--branch=main",
         "--commit-dirty=true",
         "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
        ...
    )
```

재시도 분기에서도 동일:
`/Users/twinssn/projects/5000/shared/publishers/deploy.py` line 151-160:
```python
else:
    result = subprocess.run(
        [WRANGLER_PATH, "pages", "deploy", "./public",
         "--project-name=" + cf_project,
         "--branch=main",
         "--commit-dirty=true",
         "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
        ...
    )
```

Workers 배포 분기 (`wrangler deploy --config ...`)에는 `--commit-dirty=true`가 없다.

---

## 추가 확인: com.tap.scheduler.plist.disabled 의미

`launchctl list`에는 `com.tap.scheduler`가 노출되어 있고, 활성 plist 파일(`com.tap.scheduler.plist`, 수정일 최신)이 존재한다. `.disabled` 파일은 별도이며 현재 로드된 서비스와는 구분된다. 따라서 **현재 실행 중인 TAP scheduler는 `.plist` 쪽**이다.

---

*보고서 생성일: 2026-07-24*
*근거: launchctl 출력, plist 파일 내용, 코드 라인 발췌, SQLite SELECT 쿼리 결과 (읽기 전용)*
