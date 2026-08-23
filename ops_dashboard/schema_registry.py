"""ops_dashboard.schema_registry — 분기별 표준화 스키마를 ops.db에 적재/조회.

SSOT는 schemas/*.yaml (코드). 본 모듈은 그 스냅샷을 DB에 미러링한다.
- init_schema_registry(): 테이블 생성 (멱등)
- sync_all_schemas(): config/blogs.d 전수 파싱 + load_schema + INSERT OR REPLACE
- get_schema / get_all_schemas / get_branch_summary: 조회 유틸

근거 문서: docs/superpowers/specs/2026-08-23-fleet-verification.md
"""
import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ops_dashboard.db import DB_PATH
from ops_dashboard.schema_loader import load_schema

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BLOGS_D_DIR = _PROJECT_ROOT / "config" / "blogs.d"

DDL = """
CREATE TABLE IF NOT EXISTS schema_registry (
  blog_id TEXT PRIMARY KEY,
  branch TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  required_frontmatter TEXT,
  optional_frontmatter TEXT,
  ga4_id TEXT DEFAULT NULL,
  h2_guard_enabled INTEGER DEFAULT 1,
  build_status TEXT DEFAULT 'unknown',
  last_synced_at TEXT NOT NULL,
  raw_schema TEXT NOT NULL
);
"""

# site_path 루트 → 분기 (lowercase). config pipeline 폴백은 그 다음.
_ROOT_BRANCH = [
    ("/Users/twinssn/Projects/ETAP", "etap"),
    ("/Users/twinssn/Projects/TAP", "tap"),
    ("/Users/twinssn/Projects/STAP", "stap"),
    ("/Users/twinssn/Projects/CUAP", "cuap"),
    ("/Users/twinssn/Projects/cap", "cap"),
]
_PIPELINE_BRANCH = {
    "rap": "rap", "senior": "seap", "travel": "tap", "etap": "etap",
    "stock": "stap", "stap": "stap", "curation": "cuap",
}

_GA_RE = re.compile(r"G-[A-Z0-9]{6,}")


def _load_blog_configs() -> dict[str, dict]:
    blogs = {}
    for f in sorted(_BLOGS_D_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for b in data.get("blogs") or []:
            if isinstance(b, dict) and b.get("id"):
                blogs[b["id"]] = b
    return blogs


def _branch_of(cfg: dict) -> str:
    sp = cfg.get("site_path") or ""
    for root, br in _ROOT_BRANCH:
        if sp.startswith(root):
            return br
    return _PIPELINE_BRANCH.get(cfg.get("pipeline") or "", "cap")


def _ga4_id(site_path: str | None) -> str | None:
    """extend-head 직접 주입 > config(ga4_measurement_id/googleAnalytics/services.ID) 순으로 추출.
    placeholder(G-XXXXXXXXXX)는 무시."""
    if not site_path or not Path(site_path).exists():
        return None
    ids: list[str] = []
    for f in sorted(Path(site_path).glob("layouts/**/extend*head*.html")):
        try:
            c = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if c.startswith("{{/* DEPRECATED"):
            continue
        ids += [i for i in _GA_RE.findall(c) if i != "G-XXXXXXXXXX"]
        if ids:
            break
    if ids:
        return ids[0]
    for cf in list(Path(site_path).glob("config/_default/*.toml")) + [Path(site_path) / "hugo.toml"]:
        if not cf.exists():
            continue
        t = cf.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'(?:ga4_measurement_id|googleAnalytics)\s*=\s*"(G-[A-Z0-9]{6,})"', t) \
            or re.search(r'ID\s*=\s*"(G-[A-Z0-9]{6,})"', t)
        if m and m.group(1) != "G-XXXXXXXXXX":
            return m.group(1)
    return None


def _build_status(cfg: dict) -> str:
    # ponytail: 실빌드 재실행 대신 2026-08-23 fleet 검증 결과(활성 Hugo 74/74 exit 0)를
    # 반영한 정적 판정. 빌드 실패가 누적되면 이 자리에서 hugo --destination 격리 검증으로 교체.
    if (cfg.get("platform") or "hugo") == "hugo" and cfg.get("status") == "active" and cfg.get("site_path"):
        return "pass"
    return "unknown"


def _conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path or DB_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init_schema_registry(db_path: str | Path | None = None) -> None:
    con = _conn(db_path)
    try:
        with con:
            con.execute(DDL)
    finally:
        con.close()


def sync_all_schemas(db_path: str | Path | None = None, blogs_d_dir: Path | None = None) -> dict:
    """전체 블로그 스키마 로드 + INSERT OR REPLACE. 멱등."""
    d = blogs_d_dir or _BLOGS_D_DIR
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inserted, failed = 0, []
    con = _conn(db_path)
    try:
        with con:
            con.execute(DDL)
            for bid, cfg in sorted(_load_blog_configs_from(d)):
                branch = _branch_of(cfg)
                try:
                    spec = load_schema(bid)
                except Exception as e:  # noqa: BLE001 — 개별 실패가 전체 sync 중단시키지 않게
                    failed.append((bid, f"{type(e).__name__}: {e}"))
                    continue
                raw = asdict(spec)
                version = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
                optional_fm = [k for k, v in (raw.get("empty_value_policy") or {}).items() if v == "allow"]
                con.execute(
                    "INSERT OR REPLACE INTO schema_registry VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        bid, branch, version,
                        json.dumps(raw.get("required_frontmatter") or [], ensure_ascii=False),
                        json.dumps(optional_fm, ensure_ascii=False),
                        _ga4_id(cfg.get("site_path")),
                        1,
                        _build_status(cfg),
                        now,
                        json.dumps(raw, ensure_ascii=False),
                    ),
                )
                inserted += 1
    finally:
        con.close()
    return {"total": inserted + len(failed), "inserted": inserted, "failed": failed,
            "synced_at": now}


def _load_blog_configs_from(d: Path):
    for f in sorted(d.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for b in data.get("blogs") or []:
            if isinstance(b, dict) and b.get("id"):
                yield b["id"], b


def get_schema(db_path: str | Path | None, blog_id: str) -> dict | None:
    con = _conn(db_path)
    try:
        row = con.execute("SELECT * FROM schema_registry WHERE blog_id=?", (blog_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def get_all_schemas(db_path: str | Path | None = None) -> list[dict]:
    con = _conn(db_path)
    try:
        rows = con.execute("SELECT * FROM schema_registry ORDER BY branch, blog_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _keyword_map_len(blog_id: str) -> int | None:
    """curation 키워드풀 개수. 임포트 불가 환경(테스트 등)에서는 None → kw 검사 생략."""
    try:
        from pipelines.curation.keywords import KEYWORD_MAP
        kws = KEYWORD_MAP.get(blog_id)
        return len(kws) if kws is not None else None
    except Exception:  # noqa: BLE001
        return None


def classify_standardization(db_path: str | Path | None = None) -> dict:
    """내구 신호(schema_registry + blog_lifecycle + KEYWORD_MAP)만으로 표준화 상태 분류.

    주의 사유: ga4:shared(활성 블로그 간 GA4 ID 공유), ga4:missing,
    kw:<N>(curation 키워드풀 30 미만), platform:blogger(GA4/Hugo 표준 미적용 대상).
    일회성 감사 결과(H2 구형글 샘플링 등)는 재현 불가라 제외 — 감사 스냅샷 54/22/9와
    계산값의 차이는 이 때문.
    """
    con = _conn(db_path)
    try:
        rows = [dict(r) for r in con.execute(
            """SELECT r.blog_id, r.branch, r.ga4_id, r.build_status, r.last_synced_at,
                      l.config_status AS status, l.site_path
               FROM schema_registry r
               LEFT JOIN blog_lifecycle l ON l.blog_id = r.blog_id
               ORDER BY r.branch, r.blog_id"""
        ).fetchall()]
    finally:
        con.close()

    # 활성 블로그 간 GA4 ID 공유 탐지
    ga4_count: dict[str, int] = {}
    for r in rows:
        if (r["status"] or "") == "active" and r["ga4_id"]:
            ga4_count[r["ga4_id"]] = ga4_count.get(r["ga4_id"], 0) + 1

    for r in rows:
        reasons = []
        status = (r["status"] or "").lower()
        if status != "active":
            r["state"] = "inactive"
        else:
            if r["ga4_id"] is None:
                reasons.append("ga4:missing")
            elif ga4_count.get(r["ga4_id"], 0) > 1:
                reasons.append("ga4:shared")
            n = _keyword_map_len(r["blog_id"])
            if n is not None and n < 30:
                reasons.append(f"kw:{n}")
            cfg_platform = (_load_blog_configs().get(r["blog_id"]) or {}).get("platform") or "hugo"
            if cfg_platform != "hugo":
                reasons.append("platform:" + cfg_platform)
            r["state"] = "attention" if reasons else "ok"
        r["reasons"] = reasons

    summary = {"total": len(rows),
               "ok": sum(1 for r in rows if r["state"] == "ok"),
               "attention": sum(1 for r in rows if r["state"] == "attention"),
               "inactive": sum(1 for r in rows if r["state"] == "inactive")}
    return {"summary": summary, "blogs": rows}


def get_branch_summary(db_path: str | Path | None = None) -> list[dict]:
    con = _conn(db_path)
    try:
        rows = con.execute(
            """SELECT branch,
                      COUNT(*) AS total,
                      SUM(CASE WHEN ga4_id IS NOT NULL THEN 1 ELSE 0 END) AS with_ga4,
                      SUM(CASE WHEN build_status='pass' THEN 1 ELSE 0 END) AS build_pass,
                      MAX(last_synced_at) AS last_synced_at
               FROM schema_registry GROUP BY branch ORDER BY total DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
