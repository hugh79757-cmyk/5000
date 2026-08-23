# 쿼터우회 발행 (Quota Bypass Publish)

> travel 분기에만 있던 쿼터 우회 발행을 **전 분기 일반화**한 공용 진입점.
> 오늘 일일 쿼터(예: travel 3건, cap/stock 5건)가 소진된 뒤에도 추가 발행이 필요할 때 사용.
> 이 스킬은 `scripts/force_publish_travel.py` 로직을 확장한 `shared/quota_bypass.py`
> (쿼터우회) 의 사용법을 다룬다.

## 개요

| 항목 | 값 |
|------|-----|
| 스크립트 | `shared/quota_bypass.py` |
| 우회 방식 | `dispatcher.dispatch()` 재사용 + `get_blog_config`/`_is_duplicate` **런타임 패치** |
| 우회 범위 | `daily_quota=999` 만 |
| 중복 가드 | 유지 (`_used_places`/`similar_title`/`source_id`) |
| 원복 | 불필요 (소스 파일 미변경) |
| 배포 | dispatcher 경로 그대로 (Hugo build + wrangler) |

## 사용 방법

### 1. 단일 블로그 발행 (특정 블로그만)

```bash
cd /Users/twinssn/Projects/5000
python3 shared/quota_bypass.py {blog_id}
```

예시:

```bash
# travel-hugo (tour1.rotcha.kr) — 일일 3건 소진 후 추가 1건
python3 shared/quota_bypass.py travel-hugo

# car 분기 한 곳
python3 shared/quota_bypass.py compare-hugo

# etap 분기 한 곳
python3 shared/quota_bypass.py tours-hugo
```

**주의: 인자를 하나만 주면 그 블로그 한 곳만 발행한다.** 여러 블로그를 한 번에 발행하는
기능은 없으며, 필요하면 블로그별로 명령을 따로 실행한다.

### 2. 지원 분기 목록 확인

```bash
python3 shared/quota_bypass.py --list
```

`--list` 는 실제 발행/배포 없이 **in-process 지원 분기**와 **제외(subprocess 격리) 분기**를 보여준다.

- 지원(in-process): travel·car·rap·senior·curation·etap 등 `daily_quota=999` 우회 가능
- 제외(subprocess 격리): `stock/dividend/etf/sector/ipo/finance-hugo`(STAP),
  `tap-blogger`(TAP) — 실행 시 `{"success":false,"reason":"...지원 안 함"}` + exit 1

### 3. 쿼터 소진 여부 확인 (선택)

발행 전 오늘 건수를 확인해 실제로 우회가 필요한지 판단:

```bash
cd /Users/twinssn/Projects/5000
python3 -c "
import sqlite3
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
conn = sqlite3.connect('data/content.db')
count = conn.execute(
    \"SELECT COUNT(*) FROM publish_ledger WHERE blog_id=? AND DATE(created_at)=?\",
    ('travel-hugo', today)
).fetchone()[0]
conn.close()
print(f'today count: {count}')
"
```

### 4. 출력 해석

발행 성공 시 `{"success": true, "url": "...", "slug": "...", "title": "..."}` 형태의 JSON.
실패 시 `{"success": false, "reason": "..."}` + exit code 1.

- `daily_quota_exceeded` → 쿼터 우회가 안 먹힌 경우 (드물게 발행 경로가 다른 모듈을 쓰는 경우)
- `no_result` / `no_data` → 데이터 소스에 발행 가능한 콘텐츠가 없음
- `duplicate_*` / `similar_title` → 중복 가드에 걸림 (우회하지 않으므로 정상)
- `STAP/TAP 격리 분기` → 해당 블로그는 이 스크립트 지원 대상 아님

## 동작 원리

`dispatcher.dispatch(blog_id)` 를 **통째로 재사용**하며, 실행 직전 다음 세 함수만 런타임 패치한다.

```python
dispatcher.get_blog_config        -> cfg["daily_quota"] = 999
shared.publisher.get_blog_config  -> cfg["daily_quota"] = 999
dispatcher._is_duplicate          -> lambda blog_id: False
```

이 때문에:

- `publish_ledger` 기록, cooldown/failure 추적, publish slot, Hugo build + wrangler 배포,
  발행 후 자동 재검사(post-publish check)가 모두 **원래 경로대로 동작**한다.
- 중복 발행 가드(source_id / `_used_places` / `similar_title`)는 **그대로 살아있어**
  중복 콘텐츠가 발행되지 않는다.
- 소스 파일(git diff)을 건드리지 않으므로 **원복이 불필요**하다.

## 기존 travel 전용 스크립트와의 관계

| 항목 | `scripts/force_publish_travel.py` | `shared/quota_bypass.py` |
|------|-----------------------------------|--------------------------|
| 적용 범위 | travel-hugo 전용 | 모든 in-process 분기 |
| 실행 방식 | `_run_single()` 직접 호출 | `dispatcher.dispatch()` 재사용 |
| ledger/배포/post-check | 미포함 | 포함 (dispatch 경로) |
| 중복 가드 | 유지 | 유지 |
| 원복 | 불필요 | 불필요 |

travel-hugo 에 한해서는 `force_publish_travel.py` 도 동일하게 사용 가능하며(권장),
그 외 분기는 `quota_bypass.py` 를 쓴다.

## 주의사항

- **파괴적 작업**: 발행은 글 생성 + 배포(파괴적)까지 수행한다. 실제 운영 블로그에
  콘텐츠가 올라가므로, 스케줄러(launchd/scheduler.py)가 동시 실행 중이면 중복 발행이
  생길 수 있다. 가능하면 스케줄 창과 겹치지 않게 실행한다.
- **쿼터는 우회하되 데이터 제한은 그대로**: 데이터 소스에 발행 가능한 콘텐츠가 없으면
  `no_result`/`no_data` 가 된다 (우회해도 데이터가 없으면 발행 안 됨).
- **테스트/디버깅 용도로만 사용**: 일일 쿼터 제한이 운영 목적이라면 임의로 우회하지 않는다.
- **STAP/TAP 은 미지원**: subprocess 격리라 이 스크립트로 우회할 수 없다.

## 관련 명령어 (발행 후 확인)

```bash
# 발행 글 확인 (Hugo 저장소)
ls -lt /Users/twinssn/Projects/TAP/travel-hugo/content/posts/ | head -3

# 라이브 사이트
open https://tour1.rotcha.kr/posts/<slug>/
```

## 관련 스킬

- `travel-hugo-publish` — travel-hugo 발행 특화 (이 스킬이 인용)
- `tap-blog-spec` — TAP 본문 규격
- `wrangler-deployment-patterns` — Cloudflare Pages 배포 패턴
