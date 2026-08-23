#!/usr/bin/env python3
"""sector-hugo 모니터링 — 정규 실행 결과를 읽기 전용으로 기록.

사용법: python3 monitor_sector.py [--check-last] [--propagate <article_id>]
  --check-last: 가장 최근 1회 실행 결과만 확인
  --propagate <id>: 특정 기사의 PROPAGATING 상태를 재확인 (30/90/180초)

append-only 로그: data/sector_monitor_log.jsonl에 기록된 항목은 절대 삭제하지 않음.
CORRECTION 이벤트로 오분류 수정 이력을 보존함.
"""
import sqlite3
import os
import sys
import json
import time
from datetime import datetime, timedelta

FIVEK = "/Users/twinssn/Projects/5000"
STAP = "/Users/twinssn/Projects/STAP"
CONTENT_DB = os.path.join(FIVEK, "data", "content.db")
STAP_DB = os.path.join(STAP, "data", "stap_content.db")
LOG_FILE = os.path.join(FIVEK, "data", "sector_monitor_log.jsonl")

# PROPAGATING 재확인 간격 (초)
PROPAGATE_INTERVALS = [30, 90, 180]


def get_latest_article():
    """stap_content.db + content.db에서 sector-hugo 최신 기사 확인."""
    # STAP 파이프라인은 stap_content.db에 기록
    for db_path in [STAP_DB, CONTENT_DB]:
        if not os.path.exists(db_path):
            continue
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "articles" in tables:
                row = conn.execute(
                    "SELECT id, title, slug, published_at FROM articles "
                    "WHERE blog_id='sector-hugo' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    conn.close()
                    return dict(row)
        except Exception:
            pass
        conn.close()
    return None


def get_recent_articles(n=5):
    """양쪽 DB에서 sector-hugo 최근 N건."""
    results = []
    for db_path in [STAP_DB, CONTENT_DB]:
        if not os.path.exists(db_path):
            continue
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "articles" in tables:
                rows = conn.execute(
                    "SELECT id, title, slug, published_at FROM articles "
                    "WHERE blog_id='sector-hugo' ORDER BY id DESC LIMIT ?", (n,)
                ).fetchall()
                results.extend([dict(r) for r in rows])
        except Exception:
            pass
        conn.close()
    results.sort(key=lambda x: x.get("id", 0), reverse=True)
    return results[:n]


def check_http(url, retries=1, delay=2):
    """HTTP HEAD 요청으로 상태 확인. retries회 시도, 각각 delay초 대기."""
    import subprocess
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=10
            )
            code = int(result.stdout.strip()) if result.stdout.strip() else 0
            if code == 200 or attempt == retries - 1:
                return code
        except Exception:
            if attempt == retries - 1:
                return 0
        if attempt < retries - 1:
            time.sleep(delay)
    return 0


def get_scheduler_log_recent(blog_id="sector-hugo", lines=20):
    """스케줄러 로그에서 최근 sector-hugo 관련 라인."""
    log_path = "/tmp/5000-scheduler.error.log"
    if not os.path.exists(log_path):
        return []
    result = []
    with open(log_path) as f:
        for line in f:
            if blog_id in line:
                result.append(line.rstrip())
    return result[-lines:]


def check_monitor_log():
    """기존 모니터링 로그에서 성공 회수 확인 (BASELINE/CORRECTION 제외)."""
    if not os.path.exists(LOG_FILE):
        return 0, []
    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                pass
    # BASELINE/CORRECTION 레코드 제외, SUCCESS만 카운트
    successes = sum(1 for e in entries if e.get("reason") == "SUCCESS")
    return successes, entries


def run_check():
    now = datetime.now().isoformat()
    article = get_latest_article()
    recent = get_recent_articles(5)

    entry = {"timestamp": now, "blog_id": "sector-hugo"}

    if not article:
        entry["status"] = "no_article"
        print(f"[{now}] 기사 없음")
        return entry

    entry["article_id"] = article["id"]
    entry["title"] = article["title"]
    entry["slug"] = article["slug"]
    entry["published_at"] = article["published_at"]

    # 개별 게시글 permalink HTTP 확인 — raw slug 직접 사용
    # curl은 UTF-8 raw URL을 직접 처리하므로 quote() 불필요
    # (Cloudflare Pages는 한글 직접 경로로 서빙)
    if article["slug"]:
        url = f"https://sector.techpawz.com/posts/{article['slug']}/"
        entry["url"] = url
        entry["http_status"] = check_http(url, retries=2, delay=3)
    else:
        entry["http_status"] = 0
        entry["url"] = ""

    # 중복 확인 (양쪽 DB)
    dup_count = 0
    for db_path in [STAP_DB, CONTENT_DB]:
        if not os.path.exists(db_path):
            continue
        conn = sqlite3.connect(db_path)
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "articles" in tables:
                dup_count += conn.execute(
                    "SELECT COUNT(*) FROM articles WHERE blog_id='sector-hugo' AND title=?",
                    (article["title"],)
                ).fetchone()[0]
        except Exception:
            pass
        conn.close()
    entry["duplicate_count"] = dup_count

    # 제목 품질
    entry["title_len"] = len(article["title"]) if article["title"] else 0
    entry["title_empty"] = not bool(article["title"])
    entry["title_is_section"] = article["title"] and len(article["title"]) < 5

    # 최근 기사 목록
    entry["recent_titles"] = [r["title"][:50] for r in recent]

    # 스테줄러 로그 — run_id + parser_path 검증
    log_lines = get_scheduler_log_recent(lines=10)
    entry["recent_log"] = log_lines
    entry["has_run_id"] = any("run=" in line for line in log_lines)
    entry["has_parser_path"] = any("parse_response" in line or "sector-diag" in line or "RESULT=" in line for line in log_lines)

    # 판정 — PROPAGATING 상태 지원
    # 배포 직후 최초 404는 PROPAGATING으로 기록하고
    # 30·90·180초 재확인 후에도 404일 때만 FAIL로 판정
    reasons = []
    if entry["http_status"] != 200:
        reasons.append(f"HTTP {entry['http_status']}")
    if entry["title_empty"]:
        reasons.append("title_empty")
    if entry["title_is_section"]:
        reasons.append("title_too_short")
    if dup_count > 1:
        reasons.append(f"duplicate({dup_count})")

    if not reasons:
        entry["reason"] = "SUCCESS"
        entry["fail_reasons"] = []
    elif any("HTTP" in r for r in reasons) and not any(
        r for r in reasons if "HTTP" not in r
    ):
        # HTTP 문제만 있고 제목/중복 문제 없음 → PROPAGATING (전파 지연 가능)
        entry["reason"] = "PROPAGATING"
        entry["fail_reasons"] = reasons
        entry["propagate_intervals"] = PROPAGATE_INTERVALS
    else:
        entry["reason"] = "FAIL"
        entry["fail_reasons"] = reasons

    # 출력
    print(f"[{now}] article_id={article['id']}")
    print(f"  title: {article['title'][:60]}")
    print(f"  slug: {article['slug']}")
    print(f"  HTTP: {entry['http_status']}")
    print(f"  duplicate: {dup_count}")
    print(f"  title_len: {entry['title_len']}")
    print(f"  reason: {entry['reason']}")
    if reasons:
        print(f"  fail_reasons: {reasons}")
    if entry["reason"] == "PROPAGATING":
        print(f"  → 30/90/180초 후 재확인 필요")

    return entry


def check_propagating():
    """PROPAGATING 상태인 기사를 재확인."""
    if not os.path.exists(LOG_FILE):
        return

    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                pass

    # 가장 최근 PROPAGATING 기사 찾기
    propagating = None
    for e in reversed(entries):
        if e.get("reason") == "PROPAGATING":
            propagating = e
            break

    if not propagating:
        print("PROPAGATING 상태 기사 없음")
        return

    article_id = propagating["article_id"]
    slug = propagating["slug"]
    url = propagating.get("url", f"https://sector.techpawz.com/posts/{slug}/")
    ts = datetime.fromisoformat(propagating["timestamp"])
    elapsed = (datetime.now() - ts).total_seconds()

    print(f"PROPAGATING 기사 발견: id={article_id}, 경과 {elapsed:.0f}초")

    # 다음 재확인 간격 결정
    next_interval = None
    for interval in PROPAGATE_INTERVALS:
        if elapsed < interval:
            next_interval = interval
            break

    if next_interval is None:
        # 모든 간격 경과 → 최종 FAIL로 판정
        print(f"  → {PROPAGATE_INTERVALS[-1]}초 경과, 최종 FAIL 판정")
        entry = {
            "timestamp": datetime.now().isoformat(),
            "blog_id": "sector-hugo",
            "article_id": article_id,
            "title": propagating["title"],
            "slug": slug,
            "url": url,
            "http_status": check_http(url, retries=2, delay=3),
            "reason": "FAIL",
            "fail_reasons": propagating["fail_reasons"],
            "note": "PROPAGATING → FAIL (재확인 후에도 404)",
            "original_propagating_ts": propagating["timestamp"],
        }
        append_log(entry)
        print(f"  → FAIL 기록 완료")
    else:
        # 아직 재확인 간격 남음
        remaining = next_interval - elapsed
        print(f"  → 다음 재확인: {next_interval}초 간격 ({remaining:.0f}초 후)")

        # 즉시 1회 재확인
        status = check_http(url, retries=2, delay=3)
        print(f"  → 재확인 HTTP: {status}")
        if status == 200:
            # 성공으로 판정
            entry = {
                "timestamp": datetime.now().isoformat(),
                "blog_id": "sector-hugo",
                "article_id": article_id,
                "title": propagating["title"],
                "slug": slug,
                "url": url,
                "http_status": 200,
                "reason": "SUCCESS",
                "fail_reasons": [],
                "note": "PROPAGATING → SUCCESS (전파 완료)",
                "original_propagating_ts": propagating["timestamp"],
            }
            append_log(entry)
            print(f"  → SUCCESS 기록 완료")
        else:
            print(f"  → 아직 404, {remaining:.0f}초 후 재시도")


def append_log(entry):
    """append-only 로그 기록. 기존 항목은 절대 삭제하지 않음."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def add_correction_event(original_ts, original_reason, new_reason, reason_text):
    """CORRECTION 이벤트를 append-only 로그에 추가."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "blog_id": "sector-hugo",
        "reason": "CORRECTION",
        "original_timestamp": original_ts,
        "original_reason": original_reason,
        "corrected_reason": new_reason,
        "correction_reason": reason_text,
    }
    append_log(entry)
    print(f"CORRECTION 이벤트 추가: {original_reason} → {new_reason}")


def main():
    check_last = "--check-last" in sys.argv
    propagate_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--propagate" and i + 1 < len(sys.argv):
            propagate_id = sys.argv[i + 1]

    # PROPAGATING 재확인 모드
    if propagate_id:
        check_propagating()
        return

    successes, prev_entries = check_monitor_log()
    print(f"=== sector-hugo 모니터링 ===")
    print(f"이전 기록: {len(prev_entries)}건, 성공: {successes}건")
    print()

    # 기존 PROPAGATING 항목 재확인
    for e in prev_entries:
        if e.get("reason") == "PROPAGATING":
            print(f"PROPAGATING 기사 재확인: id={e.get('article_id')}")
            check_propagating()
            print()

    entry = run_check()

    # append-only 로그 저장 (기존 항목 보존)
    append_log(entry)

    # 성공 회수 업데이트 (BASELINE/CORRECTION 제외, SUCCESS만 카운트)
    successes_new, _ = check_monitor_log()
    print(f"\n누적 성공: {successes_new}/3 목표 (baseline/correction 제외)")

    if successes_new >= 3:
        print("\n✅ 3회 성공 달성 — SECTOR_INCIDENT_CLOSURE.md 작성 가능")


if __name__ == "__main__":
    main()
