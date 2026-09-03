#!/usr/bin/env python3
"""
GSC 백필 스크립트 — 날짜 범위 순회하며 collect_gsc와 동일 로직으로 수집.

shared.analytics_collector에서 재사용: _get_oauth_token, GSC_SITES,
URL_TO_BLOG_ID, _db, _is_auth_error. 새 코드는 날짜 루프 + pacing + 서비스 캐시뿐.

용법:
    python3 scripts/backfill_gsc.py                    # 최근 90일
    python3 scripts/backfill_gsc.py --days 7            # 최근 7일
    python3 scripts/backfill_gsc.py --start-date 2026-06-01 --end-date 2026-06-30
    python3 scripts/backfill_gsc.py --dry-run --days 7  # DB 쓰기 없이 미리보기

재실행 안전: INSERT OR REPLACE 기반 — 크래시 후 같은 인자로 재실행하면 이어받기.
GSC 데이터 지연(~2-3일) 때문에 오늘-3일 이후 날짜는 스킵.
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.analytics_collector import (  # noqa: E402
    GSC_SITES,
    URL_TO_BLOG_ID,
    _db,
    _get_oauth_token,
    _is_auth_error,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_gsc")

# GSC API가 아직 데이터를 제공하지 않는 최근 N일 (2-3일 지연)
DATA_LAG_DAYS = 3
KEYWORDS_ROW_LIMIT = 500
PAGES_ROW_LIMIT = 1000


def build_services():
    """계정별 webmasters service를 1회만 빌드해 반환. {account_num: service}."""
    from googleapiclient.discovery import build

    services = {}
    for account_num in [1, 2, 3]:
        try:
            creds = _get_oauth_token("gsc", account=account_num)
            services[account_num] = build("webmasters", "v3", credentials=creds)
            logger.info(f"GSC 계정 {account_num} 서비스 빌드 OK")
        except Exception as e:
            logger.warning(f"GSC 계정 {account_num} 토큰 실패 — 해당 계열 사이트 스킵: {e}")
    return services


def collect_site_date(service, conn, blog_id, site_url, target_date, dry_run):
    """단일 사이트×단일 날짜 수집. collect_gsc와 동일 쿼리/INSERT 패턴.

    Returns:
        (keywords_inserted, pages_inserted, clicks, impressions)
    """
    resp = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": target_date,
            "endDate": target_date,
            "dimensions": ["query", "page"],
            "rowLimit": KEYWORDS_ROW_LIMIT,
        },
    ).execute()

    rows = resp.get("rows", [])
    if len(rows) >= KEYWORDS_ROW_LIMIT:
        logger.warning(
            f"TRUNCATED [{blog_id} {target_date}]: keywords rows=={KEYWORDS_ROW_LIMIT} "
            f"— 이날짜 데이터 500행 초과, 일부 유실됨"
        )
    clicks = sum(r["clicks"] for r in rows)
    impressions = sum(r["impressions"] for r in rows)
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    pos = (
        sum(r["impressions"] * r["position"] for r in rows) / impressions
        if impressions > 0
        else 0
    )

    if not dry_run:
        conn.execute(
            """INSERT OR REPLACE INTO gsc_daily_summary
               (blog_id, date, total_clicks, total_impressions,
                avg_ctr, avg_position, page_count, collected_at)
               VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
            (
                blog_id, target_date,
                int(clicks), int(impressions),
                round(ctr, 2), round(pos, 1),
                len(rows),
            ),
        )

    sorted_rows = sorted(rows, key=lambda r: r["impressions"], reverse=True)[:100]
    if not dry_run:
        for row in sorted_rows:
            kw_query = row["keys"][0]
            kw_page = row["keys"][1] if len(row["keys"]) > 1 else ""
            conn.execute(
                """INSERT OR REPLACE INTO gsc_keywords
                   (blog_id, date, query, page, clicks, impressions,
                    ctr, position, collected_at)
                   VALUES (?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
                (
                    blog_id, target_date, kw_query, kw_page,
                    int(row["clicks"]), int(row["impressions"]),
                    round(row["ctr"] * 100, 2), round(row["position"], 1),
                ),
            )

    pages_inserted = 0
    page_resp = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": target_date,
            "endDate": target_date,
            "dimensions": ["page"],
            "rowLimit": PAGES_ROW_LIMIT,
        },
    ).execute()
    page_rows = page_resp.get("rows", [])
    if len(page_rows) >= PAGES_ROW_LIMIT:
        logger.warning(
            f"TRUNCATED [{blog_id} {target_date}]: pages rows=={PAGES_ROW_LIMIT} "
            f"— 이날짜 페이지 데이터 1000행 초과, 일부 유실됨"
        )
    if not dry_run:
        for prow in page_rows:
            page_url = prow["keys"][0]
            conn.execute(
                """INSERT OR REPLACE INTO gsc_pages
                   (blog_id, date, page, clicks, impressions, ctr, position, collected_at)
                   VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
                (
                    blog_id, target_date, page_url,
                    int(prow["clicks"]), int(prow["impressions"]),
                    round(prow["ctr"] * 100, 2), round(prow["position"], 1),
                ),
            )
    pages_inserted = len(page_rows)

    return len(sorted_rows), pages_inserted, clicks, impressions


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def build_date_list(args, today):
    # GSC 데이터 미제공인 최근 3일(lag) 이후 날짜는 스킵: usable < cutoff
    cutoff = today - timedelta(days=DATA_LAG_DAYS)
    last_usable = cutoff - timedelta(days=1)
    if args.start_date:
        start = parse_date(args.start_date)
    else:
        start = last_usable - timedelta(days=args.days - 1)
    end = parse_date(args.end_date) if args.end_date else last_usable
    dates = []
    d = start
    while d <= end:
        if d < cutoff:  # cutoff 이상은 GSC 데이터 미제공 → 스킵
            dates.append(d)
        d += timedelta(days=1)
    return dates


def main():
    parser = argparse.ArgumentParser(description="GSC 백필 (날짜 범위 순회 수집)")
    parser.add_argument("--days", type=int, default=90,
                        help="백필 일수 (default 90; --start-date 있으면 무시)")
    parser.add_argument("--start-date", help="시작일 YYYY-MM-DD (재개용)")
    parser.add_argument("--end-date", help="종료일 YYYY-MM-DD")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="사이트 간 대기 초 (default 0.5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB 쓰기 없이 수집 대상만 출력")
    args = parser.parse_args()

    today = datetime.now().date()
    dates = build_date_list(args, today)
    if not dates:
        logger.warning("수집 가능한 날짜 없음 (전부 최근 3일 이내이거나 범위 비어있음)")
        return 0

    mode = "DRY-RUN" if args.dry_run else "BACKFILL"
    logger.info(f"=== GSC {mode}: {dates[0]} ~ {dates[-1]} "
                f"({len(dates)}일, {len(GSC_SITES)} 사이트) ===")
    est_min = len(dates) * len(GSC_SITES) * (1.0 + args.sleep) / 60
    logger.info(f"예상 소요: ~{est_min:.0f}분 "
                f"(쿼리~1s + sleep {args.sleep}s × {len(dates)}일 × {len(GSC_SITES)}사이트)")

    services = build_services()
    if not services:
        logger.error("모든 계정 토큰 실패 — 실행 중단")
        return 1
    logger.info(f"활성 계정: {sorted(services.keys())} / 3")

    conn = _db()
    run_start = time.time()
    totals = {"kw": 0, "pg": 0, "clicks": 0}
    dates_done = 0
    last_completed = None
    # (account_num, site_url) → 403 조합은 최초 1회 기록 후 스킵.
    # GSC 403은 안정적(해당 계정에 사이트 없음) — 재조회 불필요, 3배 쿼리 절약.
    auth_denied = set()

    try:
        for i, target in enumerate(dates, 1):
            dstr = target.strftime("%Y-%m-%d")
            d_kw = d_pg = d_clicks = d_sites = 0
            for account_num in sorted(services):
                service = services[account_num]
                for site_url in GSC_SITES:
                    name = site_url.replace("https://", "").rstrip("/")
                    blog_id = URL_TO_BLOG_ID.get(name, name)
                    if (account_num, site_url) in auth_denied:
                        continue
                    try:
                        kw, pg, clicks, impressions = collect_site_date(
                            service, conn, blog_id, site_url, dstr, args.dry_run
                        )
                        d_kw += kw
                        d_pg += pg
                        d_clicks += clicks
                        d_sites += 1
                        totals["clicks"] += clicks
                    except Exception as e:
                        if _is_auth_error(e):
                            logger.error(
                                f"ANALYTICS_AUTH_ERROR: GSC {blog_id} {dstr} "
                                f"status={getattr(e, 'status_code', '?')} — "
                                f"이 계정×사이트 조합은 이후 스킵"
                            )
                            auth_denied.add((account_num, site_url))
                        else:
                            logger.warning(
                                f"{dstr} {blog_id} 실패 (계정{account_num}): {str(e)[:100]}"
                            )
                    if args.sleep > 0:
                        time.sleep(args.sleep)
            if not args.dry_run:
                conn.commit()
            totals["kw"] += d_kw
            totals["pg"] += d_pg
            last_completed = dstr
            dates_done += 1
            logger.info(
                f"date {dstr}: sites={d_sites} keywords={d_kw} pages={d_pg} "
                f"clicks={d_clicks} ({i}/{len(dates)})"
            )
            if i % 10 == 0 and i < len(dates):
                elapsed = time.time() - run_start
                per_date = elapsed / i
                eta = per_date * (len(dates) - i)
                logger.info(
                    f"진행: {i}/{len(dates)}일 경과 {elapsed/60:.1f}분 "
                    f"ETA {eta/60:.0f}분"
                )
    except KeyboardInterrupt:
        logger.warning(
            f"Ctrl-C 중단 — {dates_done}/{len(dates)}일 완료, "
            f"마지막 완료 날짜: {last_completed}. "
            f"재개: --start-date {(datetime.strptime(last_completed, '%Y-%m-%d') + timedelta(days=1)).date() if last_completed else dates[0]}"
        )
        return 130
    finally:
        conn.close()

    elapsed = time.time() - run_start
    logger.info(
        f"완료: {dates_done}일, keywords={totals['kw']} pages={totals['pg']} "
        f"clicks={totals['clicks']}, 소요 {elapsed/60:.1f}분"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
