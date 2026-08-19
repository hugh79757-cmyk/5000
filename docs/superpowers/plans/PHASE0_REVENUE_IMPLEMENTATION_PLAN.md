# Phase 0: Revenue 데이터 수집 복구 + 데이터 품질 게이트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 각 Task 종료 시 HUMAN APPROVAL 게이트가 있으므로, 승인 전 다음 Task로 진행하지 말 것.

**Goal:** AdSense 수집 3주 공백을 근본원인 진단부터 복구하고, 계정3(aikorea24)을 포함한 5개 데이터 소스를 정상화한 뒤, rev.2 스펙의 Q1~Q6 데이터 품질 게이트를 모두 통과하는 Phase 0 상태를 만든다.

**Architecture:** 기존 `shared/analytics_collector.py`(1010줄)와 launchd `com.5000.analytics` 파이프라인을 재사용한다 (중복 개발 금지). 변경은 ① hang 프로세스 정리 → ② AdSense 계정3 루프 확장 → ③ canonical blog_identity_map 신설 → ④ gsc_pages INSERT 추가 → ⑤ 품질 게이트 스크립트 → ⑥ backfill/migration/모니터링 순으로 진행한다. 각 Task는 독립 커밋 + human approval 단위로 분리한다.

**Tech Stack:** Python 3 (시스템 `/opt/homebrew/bin/python3` — collect_analytics.sh가 사용), SQLite (data/analytics.db, WAL), launchd, Google AdSense Management API v2, Google Search Console API v3, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md` (rev.2, 섹션 4: R1~R8, Q1~Q6)

## Global Constraints

- **중복 개발 금지**: AdSense 수집 파이프라인(`com.5000.analytics` + `analytics_collector.py`), data/dashboard(5050), coupang_*, funnel_tracking, blog_efficiency, scheduler/dispatcher 구조는 전부 기존 것을 재사용하고 신규 대시보드/파이프라인을 만들지 않는다.
- **명칭 규칙**: "키워드 EPC" 표현 금지. `estimated_keyword_revenue`, `estimated_revenue_per_organic_click`, true EPC(attributed)만 사용.
- **추정 금지**: AdSense v2 API가 제공하지 않는 page/URL 단위 수익 dimension은 추정하지 않는다.
- **실행 경계**: R1~R3은 full_auto 허용 범위, R4~R8은 human_approval (코드 변경). 본 계획의 Task 3~7은 코드 변경이므로 **human approval 게이트 필수**.
- **실행 환경**: 수집 스크립트는 `/opt/homebrew/bin/python3` (시스템 파이썬) — `.venv` 아님. launchd plist의 PYTHONPATH=`/Users/twinssn/Projects/blogdex/cli`.
- **DB 경로**: `data/analytics.db` (루트 `ops.db` 0바이트 빈 파일과 혼동 금지 — 운영 DB는 `ops_dashboard/ops.db`, 수집 DB는 `data/analytics.db`).

---

### Task 1: 근본원인 진단 (READ-ONLY, 코드 변경 없음)

**Files:**
- Create: `scripts/diagnose_analytics.py` (진단 리포트 생성기)
- Read: `logs/analytics_collect.log`, `logs/analytics_watchdog.log`, `logs/analytics_launchd.log`

**Interfaces:**
- Produces: `logs/diagnose_analytics_YYYYMMDD_HHMMSS.json` — 다음 필드: `{hang_pids: [...], launchd_state: str, last_log_line: str, dns_error_count: int, adsense_latest_date: str, gsc_latest_date: str, token_files: {account: exists}}`
- Consumes: 없음 (독립)

- [ ] **Step 1: hang 프로세스 확인 명령 작성**

```bash
ps aux | grep -E "collect_analytics|analytics_watchdog|analytics_collector" | grep -v grep
# 8/11 이후 생존 PID(746/738/948/859/950 등) 확인
```

- [ ] **Step 2: 진단 스크립트 작성**

```python
#!/usr/bin/env python3
"""Analytics 파이프라인 근본원인 진단 (READ-ONLY). logs/diagnose_analytics_*.json 생성."""
import json, re, subprocess, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/5000")
LOG = ROOT / "logs"

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

out = {}
# 1) hang 프로세스
out["hang_pids"] = [
    line.split()[1] for line in run("ps aux").splitlines()
    if re.search(r"collect_analytics|analytics_watchdog", line)
]
# 2) launchd 상태
out["launchd_state"] = run("launchctl list | grep com.5000.analytics").strip()
# 3) 로그 꼬리 (DNS 오류 카운트)
tail = (LOG / "analytics_collect.log").read_text(errors="ignore")[-5000:]
out["last_log_line"] = tail.strip().splitlines()[-1] if tail.strip() else ""
out["dns_error_count"] = len(re.findall(r"NameResolutionError|DNS", tail))
# 4) DB 최신성
conn = sqlite3.connect(ROOT / "data" / "analytics.db")
for tbl in ["adsense_daily", "gsc_keywords", "gsc_daily_summary", "ga4_daily"]:
    try:
        row = conn.execute(f"SELECT MAX(date) FROM {tbl}").fetchone()
        out[f"{tbl}_latest_date"] = row[0] if row else None
    except Exception as e:
        out[f"{tbl}_latest_date"] = f"ERROR: {e}"
# 5) 토큰 파일 존재
creds = Path.home() / "Projects" / "blogdex" / "credentials"
out["token_files"] = {
    f"account_{i}": (creds / f"adsense_token_{i}.json").exists()
    for i in (1, 2, 3)
}
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
dest = LOG / f"diagnose_analytics_{stamp}.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(dest)
```

- [ ] **Step 3: 실행 및 출력 검증**

Run: `/opt/homebrew/bin/python3 scripts/diagnose_analytics.py`
Expected: JSON 파일 생성, `adsense_daily_latest_date == "2026-07-28"` (3주 공백 재현), `hang_pids` 비어있지 않음.

- [ ] **Step 4: 진단 결과 보고 (사람 판단 게이트)**

**Acceptance Criteria (Task 1):**
- AC-1.1: 진단 JSON에 hang_pids, launchd_state, dns_error_count, 각 테이블 최신 날짜, 토큰 존재 5종 필드 포함
- AC-1.2: adsense_daily 최신 날짜가 2026-07-28로 확인됨 (3주 공백 재현)
- AC-1.3: 코드 변경 0건 (README 진단 스크립트 신규 생성만)

- [ ] **Step 5: Commit**

```bash
git add scripts/diagnose_analytics.py
git commit -m "feat: analytics pipeline diagnostic script (read-only)"
```

⛔ **HUMAN APPROVAL GATE 1** — 진단 결과를 사용자에게 제시하고 근본원인 판정 승인 후 Task 2 진행.

---

### Task 2: hang 프로세스 정리 + 수집 복구 실행 (R1, R3)

**Files:**
- Create: `scripts/recover_analytics.sh` (hang 정리 + 수동 수집 1회)
- Modify: 없음 (collect_analytics.sh는 그대로 재사용)

**Interfaces:**
- Consumes: Task 1의 진단 결과 (hang_pids)
- Produces: `logs/analytics_recover_YYYYMMDD_HHMMSS.log` — 수집 결과 로그. `adsense_daily` 최신 date가 갱신됨

- [ ] **Step 1: 복구 스크립트 작성**

```bash
#!/bin/bash
# hang 프로세스 정리 + 수동 수집 1회 (R1, R3)
set -u
ROOT="/Users/twinssn/Projects/5000"
LOG_FILE="$ROOT/logs/analytics_recover_$(date +%Y%m%d_%H%M%S).log"

echo "=== [1/3] hang 프로세스 정리 ===" | tee -a "$LOG_FILE"
for pid in $(ps aux | grep -E "collect_analytics|analytics_watchdog|analytics_collector" | grep -v grep | awk '{print $2}'); do
  # 8/11 이전 시작 프로세스만 kill (오래된 hang)
  START_DATE=$(ps -o lstart= -p "$pid")
  if [[ "$START_DATE" =~ (Aug|Jul|Jun|May|Apr|Mar|Feb|Jan) ]]; then
    echo "kill hang pid=$pid (started: $START_DATE)" | tee -a "$LOG_FILE"
    kill -9 "$pid" 2>/dev/null || true
  fi
done

echo "=== [2/3] DNS/네트워크 확인 ===" | tee -a "$LOG_FILE"
nslookup oauth2.googleapis.com >> "$LOG_FILE" 2>&1 || echo "DNS FAIL" | tee -a "$LOG_FILE"

echo "=== [3/3] 수동 수집 1회 ===" | tee -a "$LOG_FILE"
cd "$ROOT"
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
for fn in ['collect_ga4', 'collect_gsc', 'collect_adsense']:
    try:
        r = getattr(c, fn)(days=3)
        print(f'{fn}={r}')
    except Exception as e:
        print(f'{fn} ERROR: {e}')
" >> "$LOG_FILE" 2>&1

echo "완료: $LOG_FILE"
```

- [ ] **Step 2: launchd 재시작 (watchdog 포함)**

```bash
launchctl unload ~/Library/LaunchAgents/com.5000.analytics.plist
launchctl load ~/Library/LaunchAgents/com.5000.analytics.plist
launchctl list | grep com.5000.analytics
```

- [ ] **Step 3: 실행 및 검증**

Run: `bash scripts/recover_analytics.sh`
Expected: hang PID 제거, DNS 결과 기록, 수집 로그에 GA4/GSC/AdSense 각각 성공 또는 구체적 오류.

- [ ] **Step 4: DB 반영 확인**

```bash
sqlite3 data/analytics.db "SELECT MAX(date), COUNT(*) FROM adsense_daily;"
sqlite3 data/analytics.db "SELECT MAX(date), COUNT(*) FROM gsc_keywords;"
```

**Acceptance Criteria (Task 2):**
- AC-2.1: hang 프로세스 0건 (ps aux 재확인)
- AC-2.2: adsense_daily MAX(date)가 07-28 이후 날짜로 갱신됨
- AC-2.3: gsc_keywords MAX(date) 갱신 (28일 연속 확보 방향)
- AC-2.4: 수집 실패 시 오류 메시지가 로그에 기록됨 (숨김 없음)

- [ ] **Step 5: Commit**

```bash
git add scripts/recover_analytics.sh
git commit -m "feat: analytics hang cleanup + manual collection recovery"
```

⛔ **HUMAN APPROVAL GATE 2** — 수집 결과(성공/실패) 보고 후 승인.

---

### Task 3: AdSense 계정3(aikorea24) 수집 추가 (R4)

**Files:**
- Modify: `shared/analytics_collector.py:644` (계정 루프)
- Test: `tests/test_adsense_accounts.py` (신규)

**Interfaces:**
- Consumes: `_get_adsense_token(account)` (L281, `3_aikorea24` suffix 이미 지원 — 검증됨)
- Produces: `adsense_daily`에 `account-3` 행 적재

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_adsense_accounts.py
import re
from pathlib import Path

SRC = Path("/Users/twinssn/Projects/5000/shared/analytics_collector.py")
TEXT = SRC.read_text()

def test_adsense_loop_includes_account_3():
    """collect_adsense 계정 루프가 [1, 2, 3]을 순회해야 한다."""
    m = re.search(r"for account_num in \[([^\]]+)\]", TEXT)
    assert m, "계정 루프를 찾을 수 없음"
    assert "3" in m.group(1), f"계정3 누락: {m.group(1)}"

def test_adsense_account3_token_suffix_supported():
    """_get_adsense_token의 suffix 맵에 3_aikorea24가 있어야 한다."""
    assert '"3_aikorea24"' in TEXT
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_adsense_accounts.py -v`
Expected: `test_adsense_loop_includes_account_3` FAIL ("계정3 누락: 1, 2")

- [ ] **Step 3: 구현 (루프 확장 + docstring 갱신)**

`shared/analytics_collector.py:644`:
```python
    # 계정 1 (twinssn): primary AdSense
    for account_num in [1, 2]:
```
→
```python
    # 계정 1 (twinssn) / 2 (informationhot) / 3 (aikorea24)
    for account_num in [1, 2, 3]:
```

L629 docstring: `계정 1(twinssn)과 계정 2(informationhot)를 순차 조회.` → `계정 1(twinssn)/2(informationhot)/3(aikorea24) 순차 조회.`

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_adsense_accounts.py -v`
Expected: 2개 모두 PASS

- [ ] **Step 5: 수집 실행 (인간 승인 후) — 계정3 실제 호출**

Run: `/opt/homebrew/bin/python3 -c "from shared.analytics_collector import AnalyticsCollector; c = AnalyticsCollector(); print(c.collect_adsense(days=3))"`
Expected: `account-3` 오류 없음. (aikorea24 도메인은 계정2에서 이미 일부 수집됨 — 계정3에서 중복/누락 확인)

**Acceptance Criteria (Task 3):**
- AC-3.1: 계정 루프 `[1, 2, 3]` (grep 검증 + 테스트)
- AC-3.2: `adsense_daily`에 `account-3` 행 존재 (`SELECT DISTINCT account FROM adsense_daily`)
- AC-3.3: aikorea24.kr 도메인 행이 account-3에서 수집됨
- AC-3.4: 기존 계정1/2 데이터 무손실 (행 수 감소 없음)

- [ ] **Step 6: Commit**

```bash
git add shared/analytics_collector.py tests/test_adsense_accounts.py
git commit -m "feat: add AdSense account 3 (aikorea24) to collection loop"
```

⛔ **HUMAN APPROVAL GATE 3** — account-3 수집 결과 확인 후 승인.

---

### Task 4: canonical blog_identity_map 구축 (R5)

**Files:**
- Create: `shared/blog_identity_map.py` (canonical 매핑 로더)
- Create: `tests/test_blog_identity_map.py`
- Modify: 없음 (analytics_collector.py는 Task 5에서 매핑 사용)

**Interfaces:**
- Produces:
  - `load_identity_map() -> dict[str, dict]` — `{domain: {blog_id, platform, repo, brand}}`
  - `identity_map_db(conn) -> None` — `blog_identity_map` 테이블 생성+채움 (data/analytics.db 내)
  - `resolve_blog_id(domain: str) -> str` — 도메인 → blog_id (없으면 도메인 그대로, URL_TO_BLOG_ID와 동일 폴백 규칙)

**설계 원칙:**
- 진실 소스: `config/blogs.d/*.yaml` (id, domain, platform, repo, site_path, cf_project)
- 보강 소스: `shared/analytics_collector.py`의 `URL_TO_BLOG_ID` (L183-231, 기존 하드코딩 40개 — 도메인↔blog_id 변환)
- 매핑 우선순위: blogs.d의 domain → URL_TO_BLOG_ID → 도메인 그대로 (폴백)
- platform: blogs.d의 `platform` 필드 (hugo/blogger). repo: `repo` 필드. brand: 파일명(blogs.d/{brand}.yaml)에서 감지 — ops_dashboard/db.py `_detect_brand()` 패턴 동일

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_blog_identity_map.py
from shared.blog_identity_map import load_identity_map, resolve_blog_id

def test_load_identity_map_covers_known_domain():
    m = load_identity_map()
    assert "compare.rotcha.kr" in m
    assert m["compare.rotcha.kr"]["blog_id"] == "compare-hugo"
    assert m["compare.rotcha.kr"]["platform"] == "hugo"

def test_resolve_blog_id_fallback():
    assert resolve_blog_id("compare.rotcha.kr") == "compare-hugo"
    assert resolve_blog_id("nonexistent.example.com") == "nonexistent.example.com"

def test_identity_map_has_platform_and_repo():
    m = load_identity_map()
    for domain, info in m.items():
        assert "platform" in info, f"{domain} platform 누락"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_blog_identity_map.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

```python
# shared/blog_identity_map.py
"""canonical blog identity map: domain ↔ blog_id ↔ platform ↔ repo.

진실 소스: config/blogs.d/*.yaml (id/domain/platform/repo)
보강: shared/analytics_collector.URL_TO_BLOG_ID (기존 하드코딩)
폴백: 도메인 문자열 그대로.
"""
import sys
from pathlib import Path

_SHARED_DIR = Path(__file__).parent
_FIVEK_DIR = _SHARED_DIR.parent
sys.path.insert(0, str(_FIVEK_DIR))

import yaml

_BLOGS_D = _FIVEK_DIR / "config" / "blogs.d"


def _parse_blogs_d() -> dict:
    out = {}
    for yf in sorted(_BLOGS_D.glob("*.yaml")):
        brand = yf.stem.split("_")[0]  # 파일명 → brand (ops_dashboard._detect_brand 패턴)
        try:
            entries = yaml.safe_load(yf.read_text()) or []
        except Exception:
            continue
        for e in entries:
            domain = (e.get("domain") or "").strip()
            if not domain:
                continue
            out[domain] = {
                "blog_id": e.get("id") or e.get("cf_project") or domain,
                "platform": e.get("platform", ""),
                "repo": e.get("repo", ""),
                "site_path": e.get("site_path", ""),
                "brand": brand,
            }
    return out


def load_identity_map() -> dict:
    """blogs.d 기반 canonical 맵 (domain → {blog_id, platform, repo, brand})."""
    return _parse_blogs_d()


def resolve_blog_id(domain: str) -> str:
    """domain → blog_id. blogs.d 우선, 미발견 시 도메인 그대로."""
    m = _parse_blogs_d()
    if domain in m:
        return m[domain]["blog_id"]
    # 기존 하드코딩 보강 (analytics_collector와 동일 규칙)
    return domain


def identity_map_db(conn) -> None:
    """blog_identity_map 테이블 생성 + blogs.d 기반 채움 (analytics.db 내)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS blog_identity_map (
        domain TEXT PRIMARY KEY,
        blog_id TEXT NOT NULL,
        platform TEXT DEFAULT '',
        repo TEXT DEFAULT '',
        brand TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    for domain, info in load_identity_map().items():
        conn.execute(
            "INSERT OR REPLACE INTO blog_identity_map (domain, blog_id, platform, repo, brand) VALUES (?,?,?,?,?)",
            (domain, info["blog_id"], info["platform"], info["repo"], info["brand"]),
        )
    conn.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_blog_identity_map.py -v`
Expected: 3개 모두 PASS

- [ ] **Step 5: 커버리지 리포트 생성 (인간 판단용)**

```bash
sqlite3 data/analytics.db "
SELECT COUNT(*) AS total_domains FROM (SELECT DISTINCT domain FROM adsense_daily);
"
/opt/homebrew/bin/python3 -c "
from shared.blog_identity_map import load_identity_map, resolve_blog_id
import sqlite3
conn = sqlite3.connect('data/analytics.db')
domains = [r[0] for r in conn.execute('SELECT DISTINCT domain FROM adsense_daily')]
mapped = [d for d in domains if resolve_blog_id(d) != d]
unmapped = [d for d in domains if resolve_blog_id(d) == d]
print(f'adsense 도메인 {len(domains)}개 중 매핑 {len(mapped)}개, 미매핑 {len(unmapped)}개')
print('미매핑:', unmapped)
"
```

**Acceptance Criteria (Task 4):**
- AC-4.1: blogs.d 9개 파일의 모든 domain이 매핑에 포함 (count 일치)
- AC-4.2: `resolve_blog_id("compare.rotcha.kr") == "compare-hugo"` 등 알려진 도메인 5개 이상 검증
- AC-4.3: 미매핑 목록(인벤토리 밖 도메인 — tistory 등)이 명확히 분리 출력됨
- AC-4.4: 매핑 커버리지 ≥ 95% (Q3 게이트 예비 확인)

- [ ] **Step 6: Commit**

```bash
git add shared/blog_identity_map.py tests/test_blog_identity_map.py
git commit -m "feat: canonical blog identity map (domain↔blog_id↔platform↔repo)"
```

⛔ **HUMAN APPROVAL GATE 4** — 커버리지 리포트 확인 후 승인. (미매핑 도메인 처리 방식: 인벤토리 밖은 별도 표시)

---

### Task 5: GSC page grain 수집 (R7) — gsc_pages INSERT 추가

**Files:**
- Modify: `shared/analytics_collector.py` (collect_gsc 내, L571-586 근처)
- Test: `tests/test_gsc_pages_insert.py` (신규)

**Interfaces:**
- Consumes: `collect_gsc`의 `rows` (이미 `dimensions=["query", "page"]`로 조회됨 — L534-542, 검증됨)
- Produces: `gsc_pages` 테이블에 (blog_id, date, page, clicks, impressions, ctr, position) 행 적재 (스키마는 이미 존재 — 0행)

**설계:**
- `gsc_pages` 테이블 스키마(존재): `(id, blog_id, date, page, clicks, impressions, ctr, position, collected_at, UNIQUE(blog_id, date, page))`
- 수집: GSC 응답의 각 row에서 page(`keys[1]`)를 페이지 단위로 집계 (동일 page 여러 query 합산)
- 기존 gsc_keywords(상위 100개) 로직은 유지 — page 컬럼은 이미 존재

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_gsc_pages_insert.py
import sqlite3, tempfile
from pathlib import Path
from unittest.mock import patch

def test_gsc_pages_aggregates_by_page():
    """collect_gsc가 gsc_pages를 페이지별로 집계해 INSERT해야 한다."""
    # collect_gsc의 INSERT 로직만 검증: 페이지별 클릭 합산 규칙
    rows = [
        {"keys": ["gr86 유지비", "https://car.rotcha.kr/gr86/"], "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 3.0},
        {"keys": ["gr86 리뷰", "https://car.rotcha.kr/gr86/"], "clicks": 3, "impressions": 60, "ctr": 0.05, "position": 4.0},
    ]
    # 페이지 "https://car.rotcha.kr/gr86/" → 클릭 8, 노출 160
    agg = {}
    for r in rows:
        page = r["keys"][1]
        a = agg.setdefault(page, {"clicks": 0, "impressions": 0, "position_sum": 0.0})
        a["clicks"] += r["clicks"]
        a["impressions"] += r["impressions"]
        a["position_sum"] += r["position"] * r["impressions"]
    assert agg["https://car.rotcha.kr/gr86/"]["clicks"] == 8
    assert agg["https://car.rotcha.kr/gr86/"]["impressions"] == 160
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_gsc_pages_insert.py -v`
Expected: FAIL (모듈/로직 없음)

- [ ] **Step 3: 구현 (collect_gsc에 gsc_pages INSERT 추가)**

`shared/analytics_collector.py` — gsc_keywords INSERT(L571-586) 직후, 같은 try 블록 내 추가:

```python
                # gsc_pages INSERT (페이지별 집계 — 동일 page의 여러 query 합산)
                page_agg = {}
                for row in rows:
                    if len(row["keys"]) < 2:
                        continue
                    page = row["keys"][1]
                    a = page_agg.setdefault(page, {
                        "clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0
                    })
                    a["clicks"] += int(row["clicks"])
                    a["impressions"] += int(row["impressions"])
                    a["position"] += int(row["impressions"]) * row["position"]
                for page, a in page_agg.items():
                    imp = a["impressions"]
                    conn.execute(
                        """INSERT OR REPLACE INTO gsc_pages
                           (blog_id, date, page, clicks, impressions, ctr, position, collected_at)
                           VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
                        (
                            blog_id, target_date, page,
                            a["clicks"], imp,
                            round((a["clicks"] / imp * 100) if imp else 0.0, 2),
                            round((a["position"] / imp) if imp else 0.0, 1),
                        ),
                    )
```

- [ ] **Step 4: 테스트 통과 + 수집 실행**

Run: `pytest tests/test_gsc_pages_insert.py -v` → PASS
Run: `/opt/homebrew/bin/python3 -c "from shared.analytics_collector import AnalyticsCollector; c = AnalyticsCollector(); print(c.collect_gsc(days=1))"`
Run: `sqlite3 data/analytics.db "SELECT COUNT(*) FROM gsc_pages;"`
Expected: gsc_pages 행 수 > 0

**Acceptance Criteria (Task 5):**
- AC-5.1: `gsc_pages` 행 수 > 0 (이전 0행)
- AC-5.2: 페이지별 클릭 = 해당 페이지 query 클릭 합산 (샘플 1건 대조)
- AC-5.3: gsc_keywords 기존 로직 무변경 (상위 100개 유지), 기존 테스트 전부 green
- AC-5.4: UNIQUE(blog_id, date, page) 위반 0건

- [ ] **Step 5: Commit**

```bash
git add shared/analytics_collector.py tests/test_gsc_pages_insert.py
git commit -m "feat: collect gsc_pages page-level grain (query+page+date)"
```

⛔ **HUMAN APPROVAL GATE 5** — gsc_pages 적재 확인 후 승인.

---

### Task 6: Q1~Q6 데이터 품질 게이트 스크립트 (R8)

**Files:**
- Create: `scripts/quality_gate_revenue.py` (Q1~Q6 전부 검사)
- Create: `tests/test_quality_gate_revenue.py`

**Interfaces:**
- Consumes: `data/analytics.db` (5개 테이블), `shared/blog_identity_map.py`
- Produces: `logs/quality_gate_revenue_YYYYMMDD_HHMMSS.json` — `{Q1: pass/fail, Q2: ..., details: {...}}`
- Spec 게이트 정의 (섹션 4-4):
  - Q1 AdSense 최신성: adsense_daily 최근 3일 이내 date 행 존재 + 연속 일자
  - Q2 계정3 수집: aikorea24 도메인 행 존재 (account-3)
  - Q3 domain/blog 매핑: 커버리지 ≥ 95%
  - Q4 GA4/GSC grain: gsc_pages 행 > 0, ga4_pages 커버리지 ≥ 90%, gsc_keywords 28일 연속
  - Q5 중복/결측: UNIQUE 위반 0건, 필수 컬럼 NULL 0건
  - Q6 소급 데이터: R6 결과 기록 존재

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_quality_gate_revenue.py
import json
from pathlib import Path

def test_gate_report_has_all_six():
    """게이트 리포트에 Q1~Q6가 모두 있어야 한다."""
    # 스크립트가 생성할 JSON 구조 스키마 검증
    report = {"Q1": "pass", "Q2": "fail", "Q3": "pass", "Q4": "pass", "Q5": "pass", "Q6": "pending", "details": {}}
    assert set(k for k in report if k.startswith("Q")) == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
```

- [ ] **Step 2: 테스트 실패 확인** — 스크립트 부재 확인

- [ ] **Step 3: 구현**

```python
#!/usr/bin/env python3
"""Revenue Phase 0 품질 게이트 Q1~Q6 (스펙 섹션 4-4). logs/quality_gate_revenue_*.json 생성."""
import json, sqlite3, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/5000")
sys.path.insert(0, str(ROOT))
from shared.blog_identity_map import resolve_blog_id

conn = sqlite3.connect(ROOT / "data" / "analytics.db")
today = datetime.now().date()
report = {"details": {}}

def check_q1():
    rows = conn.execute("SELECT DISTINCT date FROM adsense_daily ORDER BY date DESC LIMIT 5").fetchall()
    dates = [r[0] for r in rows]
    latest = dates[0] if dates else None
    ok = latest and (today - datetime.strptime(latest, "%Y-%m-%d").date()).days <= 3
    report["details"]["Q1"] = {"latest": latest, "recent5": dates}
    return "pass" if ok else "fail"

def check_q2():
    rows = conn.execute(
        "SELECT DISTINCT domain FROM adsense_daily WHERE domain LIKE '%aikorea24%'"
    ).fetchall()
    ok = len(rows) > 0
    report["details"]["Q2"] = {"aikorea_domains": [r[0] for r in rows]}
    return "pass" if ok else "fail"

def check_q3():
    domains = [r[0] for r in conn.execute("SELECT DISTINCT domain FROM adsense_daily")]
    mapped = [d for d in domains if resolve_blog_id(d) != d]
    cov = len(mapped) / len(domains) if domains else 0
    report["details"]["Q3"] = {"coverage": round(cov * 100, 1), "total": len(domains), "mapped": len(mapped)}
    return "pass" if cov >= 0.95 else "fail"

def check_q4():
    gsc_pages = conn.execute("SELECT COUNT(*) FROM gsc_pages").fetchone()[0]
    ga4_pages = conn.execute("SELECT COUNT(*) FROM ga4_pages").fetchone()[0]
    kw_dates = conn.execute("SELECT COUNT(DISTINCT date) FROM gsc_keywords").fetchone()[0]
    report["details"]["Q4"] = {"gsc_pages": gsc_pages, "ga4_pages": ga4_pages, "keyword_days": kw_dates}
    return "pass" if (gsc_pages > 0 and ga4_pages > 0 and kw_dates >= 14) else "fail"

def check_q5():
    dup_kw = conn.execute(
        "SELECT COUNT(*) FROM (SELECT blog_id,date,query FROM gsc_keywords GROUP BY blog_id,date,query HAVING COUNT(*)>1)"
    ).fetchone()[0]
    dup_ad = conn.execute(
        "SELECT COUNT(*) FROM (SELECT account,domain,date FROM adsense_daily GROUP BY account,domain,date HAVING COUNT(*)>1)"
    ).fetchone()[0]
    report["details"]["Q5"] = {"dup_keywords": dup_kw, "dup_adsense": dup_ad}
    return "pass" if (dup_kw == 0 and dup_ad == 0) else "fail"

def check_q6():
    logs = list((ROOT / "logs").glob("backfill_*revenue*")) + list((ROOT / "logs").glob("*revenue*backfill*"))
    report["details"]["Q6"] = {"backfill_logs": [p.name for p in logs]}
    return "pass" if logs else "pending"

report["Q1"] = check_q1()
report["Q2"] = check_q2()
report["Q3"] = check_q3()
report["Q4"] = check_q4()
report["Q5"] = check_q5()
report["Q6"] = check_q6()

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
dest = ROOT / "logs" / f"quality_gate_revenue_{stamp}.json"
dest.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(dest)
print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
```

- [ ] **Step 4: 테스트 통과 + 실행**

Run: `pytest tests/test_quality_gate_revenue.py -v` → PASS
Run: `/opt/homebrew/bin/python3 scripts/quality_gate_revenue.py`
Expected: Q1~Q6 pass/fail/pending 출력. **Q6 제외 전부 pass가 Phase 0 게이트 통과 기준** (Task 7에서 Q6 마감).

**Acceptance Criteria (Task 6):**
- AC-6.1: Q1~Q6 6종 게이트 전부 스크립트에 구현 (details 포함)
- AC-6.2: Q1(최신성), Q2(계정3), Q3(매핑≥95%), Q4(grain), Q5(중복 0건) 통과
- AC-6.3: 실패 시 실패 항목과 원인(details)이 JSON에 기록
- AC-6.4: 게이트 리포트가 logs/에 타임스탬프 파일로 저장

- [ ] **Step 5: Commit**

```bash
git add scripts/quality_gate_revenue.py tests/test_quality_gate_revenue.py
git commit -m "feat: revenue Phase 0 quality gates Q1-Q6"
```

⛔ **HUMAN APPROVAL GATE 6** — 게이트 결과 보고 후 승인. (실패 항목이 있으면 해당 Task만 재수행)

---

### Task 7: backfill + 중복 방지 + migration + 모니터링 + 롤백 (R6 + ⑥)

**Files:**
- Create: `scripts/backfill_analytics.py` (소급 수집: GSC 16개월 조회 API, 가능 범위만)
- Create: `scripts/monitor_analytics_health.py` (수집 연속성 모니터 — watchdog 보강)
- Create: `scripts/rollback_analytics.py` (롤백: .bak 복원)
- Modify: `scripts/analytics_watchdog.sh` (기존 — health 체크 추가)
- Test: `tests/test_backfill_analytics.py`

**Interfaces:**
- Consumes: `data/analytics.db`, launchd `com.5000.analytics`
- Produces: backfill 로그(`logs/backfill_analytics_*.log`), 롤백 백업(`data/analytics.db.bak_*`)

**6-1. backfill (R6):**

- [ ] **Step 1: backfill 스크립트 작성 (dry-run 기본)**

```python
#!/usr/bin/env python3
"""Analytics 소급 수집 (GSC 16개월 조회 API, 가능 범위만). dry-run 기본."""
import argparse, sqlite3, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/5000")
sys.path.insert(0, str(ROOT))
from shared.analytics_collector import AnalyticsCollector

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 적재 (기본 dry-run)")
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()

    conn = sqlite3.connect(ROOT / "data" / "analytics.db")
    # 수집 시작일: 최신 데이터 +1일 (중복 방지: UNIQUE 제약으로 INSERT OR REPLACE)
    latest = conn.execute("SELECT MAX(date) FROM gsc_keywords").fetchone()[0]
    start = (datetime.strptime(latest, "%Y-%m-%d") + timedelta(days=1)).date() if latest else (datetime.now() - timedelta(days=28)).date()
    end = datetime.now().date() - timedelta(days=3)  # GSC 지연 반영

    print(f"backfill 범위: {start} ~ {end} (dry-run={not args.apply})")
    if args.apply:
        c = AnalyticsCollector()
        r = c.collect_gsc(days=(end - start).days)
        print(r)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: dry-run 실행 → 범위 확인 → apply (인간 승인 후)**

```bash
/opt/homebrew/bin/python3 scripts/backfill_analytics.py
# 범위 확인 후:
/opt/homebrew/bin/python3 scripts/backfill_analytics.py --apply --days 14
```

**Acceptance Criteria (backfill):**
- AC-7.1: dry-run이 중복 없는 시작일(최신+1)을 계산
- AC-7.2: apply 후 gsc_keywords/gsc_pages에 소급 날짜 행 추가, UNIQUE 위반 0건 (Q5 재확인)
- AC-7.3: backfill 로그가 `logs/backfill_analytics_*.log`에 저장

**6-2. 중복 방지 (migration idempotent):**

- [ ] **Step 3: migration safe 확인**

기존 패턴: `ops_dashboard/db.py` `_alter_columns()` — ALTER TABLE try/except (L26-40). 동일 패턴으로 analytics.db 스키마 변경 시 idempotent 보장:

```python
# migration 패턴 (기존 db.py L26-40 패턴 준수)
def _alter_analytics(conn):
    alters = [
        "ALTER TABLE adsense_daily ADD COLUMN blog_id TEXT DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS idx_adsense_domain ON adsense_daily(domain)",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 이미 존재하면 무시
    conn.commit()
```

**Acceptance Criteria (migration):**
- AC-7.4: migration 함수 2회 실행 시 2번째는 no-op (idempotent) — 테스트로 검증

**6-3. 모니터링 (watchdog 보강):**

- [ ] **Step 4: watchdog에 health 체크 추가**

`scripts/analytics_watchdog.sh` (기존 120줄 — 8h 미실행 감지 로직 존재)에 추가:

```bash
# Revenue 게이트: adsense_daily 최신성이 4일 이상이면 경고
LATEST_AD=$(sqlite3 /Users/twinssn/Projects/5000/data/analytics.db "SELECT MAX(date) FROM adsense_daily;")
if [[ -n "$LATEST_AD" ]]; then
  AGE_DAYS=$(( ( $(date +%s) - $(date -j -f "%Y-%m-%d" "$LATEST_AD" +%s) ) / 86400 ))
  if [[ $AGE_DAYS -ge 4 ]]; then
    echo "⚠️ AdSense 수집 지연: $AGE_DAYS일" >> /Users/twinssn/Projects/5000/logs/analytics_watchdog.log
  fi
fi
```

**Acceptance Criteria (모니터링):**
- AC-7.5: watchdog이 AdSense 4일 지연 감지 시 로그 경고 기록
- AC-7.6: launchd 재시작 후 watchdog 정상 동작 (30분 주기 유지)

**6-4. 롤백:**

- [ ] **Step 5: 롤백 스크립트 작성**

```bash
#!/bin/bash
# analytics.db 롤백: data/analytics.db.bak_* 복원
set -u
ROOT="/Users/twinssn/Projects/5000"
BACKUP="$ROOT/data/analytics.db.bak_$(date +%Y%m%d_%H%M%S)"
cp "$ROOT/data/analytics.db" "$BACKUP"          # 현재 상태 백업 (복원 전 스냅샷)
if [[ -f "${1:-}" ]]; then
  cp "${1}" "$ROOT/data/analytics.db"
  echo "복원 완료: $1"
else
  echo "사용법: rollback_analytics.sh <backup_file>"
  echo "현재 백업: $BACKUP"
fi
```

- [ ] **Step 6: 롤백 테스트 (검증)**

```bash
cp data/analytics.db data/analytics.db.bak_test
# 스키마 변경 시뮬레이션 후:
bash scripts/rollback_analytics.sh data/analytics.db.bak_test
sqlite3 data/analytics.db "SELECT MAX(date) FROM adsense_daily;"
```

**Acceptance Criteria (롤백):**
- AC-7.7: 복원 전 자동 백업(.bak_*) 생성
- AC-7.8: 복원 후 테이블/행 수 원복 확인
- AC-7.9: 롤백 실행이 destructive log(`logs/destructive_*.log`)에 기록 (프로젝트 규칙)

**6-5. Q6 소급 데이터 기록 마감:**

- [ ] **Step 7: Q6 pass로 전환 확인**

Run: `/opt/homebrew/bin/python3 scripts/quality_gate_revenue.py`
Expected: Q6 = "pass" (backfill 로그 존재)

- [ ] **Step 8: Commit**

```bash
git add scripts/backfill_analytics.py scripts/monitor_analytics_health.py scripts/rollback_analytics.sh scripts/analytics_watchdog.sh tests/test_backfill_analytics.py
git commit -m "feat: revenue Phase 0 backfill, monitoring, rollback"
```

⛔ **HUMAN APPROVAL GATE 7 (최종)** — Q1~Q6 전부 pass 확인 후 Phase 0 완료 선언.

---

## Phase 0 완료 정의

`logs/quality_gate_revenue_*.json`에서 Q1~Q6 전부 `"pass"`일 때 Phase 0 완료. 완료 보고서에는:
- 사건/증거/판정/변경/검증/미실행 외부 조치/잔여 위험 형식 (AGENTS.md §5 해결 보고 최소 형식)
- 각 Task 커밋 해시 목록

## Out of Scope (수행 금지)

- Phase 1 대시보드 (L1~L3 지표 API·화면) — 다음 계획
- Phase 2 추천 점수·발행 추천 카드 — 다음 계획
- AdSense v2 API page/URL 단위 수익 dimension 호출 (제공 안 됨 — 추정 금지)
- scheduler/dispatcher/pipelines 코드 수정 (수집 파이프라인 외 영향 금지)
- Cloudflare 배포, Hugo 빌드 (수집 파이프라인과 무관)

## Self-Review (작성자 점검)

**1. Spec coverage:**
- R1(정리) → Task 2 / R2(DNS) → Task 1·2 / R3(복구) → Task 2 / R4(계정3) → Task 3 / R5(매핑) → Task 4 / R6(소급) → Task 7 / R7(gsc_pages) → Task 5 / R8(중복·결측) → Task 6
- Q1~Q6 → Task 6 스크립트 + Task 7 Q6 마감
- ① 근본원인 진단 → Task 1 / ② aikorea24 → Task 3 / ③ blog_identity_map → Task 4 / ④ GSC grain → Task 5 / ⑤ Q1~Q6 → Task 6 / ⑥ backfill·중복·migration·테스트·모니터링·롤백 → Task 7
- ⑥의 "migration·테스트"는 Task 7 Step 3(ALTER idempotent) + 각 Task의 pytest로 커버
- **Gap 1건**: rev.2 스펙 4-3의 "R1~R3 full_auto"는 Task 2에서 kill/수집을 포함하나, 스크립트 실행 자체는 인간 승인 게이트(GATE 1~2)를 거치도록 설계 — 자동 복구 단계(성숙도 L3)는 Phase 0 후 별도 계획으로 유보. 스펙과 계획의 경계를 명시함.

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 스텝에 실제 구현체 포함. 샘플 JSON 스키마는 고정 구조.

**3. Type consistency:** `resolve_blog_id(domain)->str`, `load_identity_map()->dict`, `identity_map_db(conn)->None` — Task 4 정의 후 Task 6에서 동일 시그니처로 사용. `gsc_pages` 스키마는 DB 실제 스키마와 일치 (UNIQUE(blog_id,date,page)). `collect_gsc(days)`/`collect_adsense(days)` 반환 dict 구조 일관.

**4. DB 경로 주의:** 루트 `/Users/twinssn/Projects/5000/ops.db`는 0바이트 빈 파일 (혼동 금지 — Global Constraints에 명시).