"""ops_dashboard.checks.maintenance — 블로그 정비 체크리스트 실행

Phase 60 Part 2: 블로그 정비·재개 프레임워크
- M01~M10 표준 정비 항목 자동 검사
- 정비 대상 블로그의 체크리스트 진행 상황 추적
- 모든 항목 pass → resume_ready = True
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

# 정비 대상 블로그 (lifecycle_status = maintenance 대상)
# dispatcher reason이 similar_title로 반복 차단된 블로그们


def _check_cjk_in_title(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M01: 제목 CJK 없음 — 최근 발행 제목에 한자/일본어/중국어 누수 없음"""
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')

    # 발행 로그에서 최근 제목 조회
    tables_and_cols = [
        ("publish_log", "title", "published_at"),
        ("publish_ledger", "title", "created_at"),
    ]

    for table, col, date_col in tables_and_cols:
        try:
            rows = conn.execute(f"""
                SELECT {col} FROM {table}
                WHERE blog_id = ? AND {col} IS NOT NULL AND {col} != ''
                ORDER BY {date_col} DESC LIMIT 20
            """, (blog_id,)).fetchall()
        except sqlite3.OperationalError:
            continue

        contaminated = []
        for (title,) in rows:
            if title and cjk_pattern.search(title):
                contaminated.append(title[:50])

        if contaminated:
            return {
                "status": "fail",
                "detail": f"M01: CJK 포함 제목 {len(contaminated)}건 — " + "; ".join(contaminated[:3]),
            }

    return {"status": "pass", "detail": "M01: 최근 제목 20건 중 CJK 포함 없음"}


def _check_cjk_in_body_and_slug(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M11: 본문·슬러그 CJK 없음 — 포스트 본문과 URL 슬러그에 CJK 누수 없음 (확장)"""
    # CJK 문자 패턴 (한자, 히라가나, 가타카나)
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
    # 퍼센트 인코딩된 CJK 패턴 (%E4%B8%AD%... 등 - 3바이트 UTF-8 시퀀스)
    percent_cjk_pattern = re.compile(r'(?:%[Ee][0-9a-fA-F]{2}){3,}')

    blog_row = conn.execute(
        "SELECT site_path FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()

    if not blog_row or not blog_row["site_path"]:
        return {"status": "unknown", "detail": "M11: site_path 없음 — 수동 확인 필요"}

    site_path = Path(blog_row["site_path"])
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.is_dir():
        return {"status": "unknown", "detail": f"M11: {posts_dir} 디렉토리 없음"}

    # 최근 20개 포스트의 본문과 슬러그 검사
    body_contaminated = []
    slug_contaminated = []
    checked = 0

    for post_dir in sorted(posts_dir.iterdir(), reverse=True)[:20]:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue

        try:
            content = idx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        checked += 1

        # 1. 슬러그(디렉토리명) CJK 검사 - 원문 + 퍼센트인코딩 모두
        slug = post_dir.name
        if cjk_pattern.search(slug) or percent_cjk_pattern.search(slug):
            slug_contaminated.append(slug[:60])

        # 2. 본문 CJK 검사 (frontmatter 이후 내용)
        # frontmatter 끝(--- 또는 +++) 이후부터 본문 시작
        # 패턴: ---\n...\n--- 또는 +++\n...\n+++
        parts = re.split(r'^\s*(?:---|\+\+\+)\s*$', content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            body_text = parts[2]  # 두 번째 구분자 이후
        elif len(parts) == 2:
            body_text = parts[1]  # 하나의 구분자만 있는 경우
        else:
            body_text = content  # frontmatter 없으면 전체를 본문으로 간주

        # 코드 블록, HTML 태그 제거 후 검사
        cleaned_body = re.sub(r'```.*?```', '', body_text, flags=re.DOTALL)
        cleaned_body = re.sub(r'<[^>]+>', '', cleaned_body)

        if cjk_pattern.search(cleaned_body):
            # 컨텍스트 포함해서 저장
            # CJK 문자 주변 50자 추출
            for m in cjk_pattern.finditer(cleaned_body):
                start = max(0, m.start() - 30)
                end = min(len(cleaned_body), m.end() + 30)
                context = cleaned_body[start:end].replace('\n', ' ')
                body_contaminated.append(f"{post_dir.name}: ...{context}...")
                break  # 포스트당 1건만 기록

    if slug_contaminated:
        return {
            "status": "fail",
            "detail": f"M11: 슬러그 CJK {len(slug_contaminated)}건 — " + "; ".join(slug_contaminated[:3]),
        }

    if body_contaminated:
        return {
            "status": "fail",
            "detail": f"M11: 본문 CJK {len(body_contaminated)}건 — " + "; ".join(body_contaminated[:3]),
        }

    return {"status": "pass", "detail": f"M11: 최근 {checked}개 포스트 본문·슬러그 CJK 없음"}


def _check_image_repetition(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M02: 이미지 정상 — 동일 이미지 반복 사용 없음"""
    # recent_titles에서 featureimage 수집 (Hugo 사이트)
    blog_row = conn.execute(
        "SELECT site_path FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()

    if not blog_row or not blog_row["site_path"]:
        return {"status": "unknown", "detail": "M02: site_path 없음 — 수동 확인 필요"}

    site_path = Path(blog_row["site_path"])
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.is_dir():
        return {"status": "unknown", "detail": f"M02: {posts_dir} 디렉토리 없음"}

    # 최근 20개 포스트의 featureimage 수집
    featureimages = []
    for post_dir in sorted(posts_dir.iterdir(), reverse=True)[:20]:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        try:
            content = idx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # featureimage 추출
        match = re.search(r'featureimage:\s*["\']?([^\s"\']+)', content)
        if match:
            featureimages.append((post_dir.name, match.group(1)))

    if len(featureimages) < 3:
        return {"status": "unknown", "detail": f"M02: 포스트 {len(featureimages)}건 — 분석 불가"}

    # 동일 URL 반복 검사
    urls = [url for _, url in featureimages]
    url_counts = {}
    for u in urls:
        url_counts[u] = url_counts.get(u, 0) + 1

    repeated = {u: c for u, c in url_counts.items() if c >= 3}
    if repeated:
        top = max(repeated, key=repeated.get)
        return {
            "status": "fail",
            "detail": f"M02: 동일 이미지 {repeated[top]}회 반복 — {top[:60]}",
        }

    return {"status": "pass", "detail": f"M02: {len(featureimages)}개 포스트 이미지 고유성 양호"}


from ops_dashboard.checks import crosslink as crosslink_check


def _check_crosslink_relevance(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M03: 크로스링크 주제 일관 — 내부 링크가 블로그 주제와 무관하지 않음 (M03/audit Q5)"""
    return crosslink_check.check_crosslink_consistency(conn, blog_id)


def _check_content_quality(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M04: 본문 품질 게이트 — Q1~Q4 이슈 없음"""
    # known_issues에서 이 블로그 관련 Q 이슈 확인
    q_issues = conn.execute("""
        SELECT issue_id, symptom FROM known_issues
        WHERE blog_ids LIKE ? AND issue_id LIKE 'Q%' AND gsd_status = 'open'
    """, (f"%{blog_id}%",)).fetchall()

    if q_issues:
        items = [f"{r['issue_id']}: {r['symptom'][:40]}" for r in q_issues]
        return {
            "status": "fail",
            "detail": f"M04: {len(q_issues)}개 미해결 품질 이슈 — " + "; ".join(items[:3]),
        }

    return {"status": "pass", "detail": "M04: 미해결 Q 이슈 없음"}


def _check_standard_compliance(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M05: 표준 (광고/테마) 준수 — R01~R12 모두 통과"""
    # 최근 check_results에서 standard_compliance 결과 확인
    latest = conn.execute("""
        SELECT status, detail FROM check_results
        WHERE blog_id = ? AND check_name = 'standard_compliance'
        ORDER BY checked_at DESC LIMIT 1
    """, (blog_id,)).fetchone()

    if not latest:
        return {"status": "unknown", "detail": "M05: standard_compliance 미실행 — 먼저 run-checks 실행 필요"}

    if latest["status"] == "pass":
        return {"status": "pass", "detail": f"M05: {latest['detail']}"}

    return {"status": "fail", "detail": f"M05: {latest['detail']}"}


def _check_keyword_availability(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M06: 키워드 잔량 충분 — KEYWORD_MAP 정의 − published_products 사용 = 미발행 잔량"""
    project_root = Path(__file__).parent.parent.parent
    MIN_REMAINING = 24  # 잔량 기준

    # 1차: keywords 테이블이 있는 pipeline DB (rap, senior 등)
    for db_name in ["rap.db", "content.db", "senior.db"]:
        db_path = project_root / "data" / db_name
        if not db_path.exists():
            continue
        try:
            c = sqlite3.connect(str(db_path))
            tables = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "keywords" in tables:
                count = c.execute("""
                    SELECT COUNT(*) FROM keywords
                    WHERE blog_id = ? AND active = 1
                """, (blog_id,)).fetchone()[0]
                c.close()
                if count < MIN_REMAINING:
                    return {
                        "status": "fail",
                        "detail": f"M06: active 키워드 {count}개 (기준 {MIN_REMAINING}개 미달)",
                    }
                return {
                    "status": "pass",
                    "detail": f"M06: active 키워드 {count}개",
                }
            c.close()
        except (sqlite3.OperationalError, Exception):
            try:
                c.close()
            except Exception:
                pass
            continue

    # 2차: KEYWORD_MAP(Python) − published_products(DB) = 미발행 잔량
    # curation 블로그의 표준 계산 경로
    try:
        import importlib.util
        kw_path = project_root / "pipelines" / "curation" / "keywords.py"
        if not kw_path.exists():
            return {"status": "unknown", "detail": "M06: keywords.py 파일 없음"}

        spec = importlib.util.spec_from_file_location("keywords", str(kw_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        kw_map = getattr(mod, "KEYWORD_MAP", {})

        defined = set(kw_map.get(blog_id, []))
        if not defined:
            return {
                "status": "unknown",
                "detail": f"M06: KEYWORD_MAP에 {blog_id} 키워드 없음",
            }

        # published_products에서 이미 사용한 키워드
        used = set()
        curation_db = project_root / "data" / "curation.db"
        if curation_db.exists():
            c = sqlite3.connect(str(curation_db))
            rows = c.execute("""
                SELECT DISTINCT keyword FROM published_products
                WHERE blog_id = ?
            """, (blog_id,)).fetchall()
            used = {r[0] for r in rows}
            c.close()

        remaining = defined - used
        remaining_count = len(remaining)

        if remaining_count < MIN_REMAINING:
            return {
                "status": "fail",
                "detail": f"M06: 잔량 {remaining_count}개 < 기준 {MIN_REMAINING}개 "
                          f"(정의 {len(defined)}개 − 사용 {len(used)}개)",
            }

        return {
            "status": "pass",
            "detail": f"M06: 잔량 {remaining_count}개 (정의 {len(defined)}개 − 사용 {len(used)}개)",
        }
    except Exception as e:
        return {"status": "unknown", "detail": f"M06: 계산 오류 — {e}"}


def _check_similar_title_safety(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M07: P03 유사제목 안전 — 최근 유사 제목 차단 이력 없음"""
    # publish_ledger에서 failed + similar_title 확인
    try:
        recent_fails = conn.execute("""
            SELECT COUNT(*) FROM publish_ledger
            WHERE blog_id = ? AND status = 'failed' AND stage = 'similar_title'
              AND created_at > datetime('now', '-7 days')
        """, (blog_id,)).fetchone()[0]

        if recent_fails > 0:
            return {
                "status": "fail",
                "detail": f"M07: 최근 7일 내 similar_title 차단 {recent_fails}건",
            }
    except sqlite3.OperationalError:
        pass

    return {"status": "pass", "detail": "M07: 최근 7일 내 similar_title 차단 없음"}


def _check_cot_leak(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M08: CoT/프롬프트 누수 없음"""
    # known_issues에서 cot_leak 관련 확인
    cot = conn.execute("""
        SELECT issue_id FROM known_issues
        WHERE blog_ids LIKE ? AND issue_id IN ('P08', 'P07') AND gsd_status = 'open'
    """, (f"%{blog_id}%",)).fetchall()

    if cot:
        return {"status": "fail", "detail": f"M08: CoT/CJK 누수 이슈 미해결"}

    return {"status": "pass", "detail": "M08: CoT/프롬프트 누수 이슈 없음"}


def _check_publish_log_integrity(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M09: publish_log 기록 정상 — 발행 성공 시 기록 남음"""
    project_root = Path(__file__).parent.parent.parent

    # publish_ledger는 content.db에 있음
    content_db = project_root / "data" / "content.db"
    curation_db = project_root / "data" / "curation.db"

    try:
        # content.db에서 publish_ledger 발행 건수 확인
        c_conn = sqlite3.connect(str(content_db))
        c_conn.row_factory = sqlite3.Row
        successes = c_conn.execute("""
            SELECT COUNT(*) FROM publish_ledger
            WHERE blog_id = ? AND status = 'published'
              AND created_at > datetime('now', '-7 days')
        """, (blog_id,)).fetchone()[0]
        c_conn.close()

        # curation.db에서 publish_log 발행 건수 확인
        cu_conn = sqlite3.connect(str(curation_db))
        cu_conn.row_factory = sqlite3.Row
        log_count = cu_conn.execute("""
            SELECT COUNT(*) FROM publish_log
            WHERE blog_id = ? AND published_at > datetime('now', '-7 days')
        """, (blog_id,)).fetchone()[0]
        cu_conn.close()

        if successes > 0 and log_count == 0:
            return {
                "status": "fail",
                "detail": f"M09: ledger에 발행 {successes}건이나 publish_log 0건 — 기록 누락",
            }

        return {
            "status": "pass",
            "detail": f"M09: ledger 발행 {successes}건, publish_log {log_count}건",
        }
    except (sqlite3.OperationalError, OSError) as e:
        return {"status": "unknown", "detail": f"M09: DB 접근 불가 — {e}"}


def _check_domain_health(conn: sqlite3.Connection, blog_id: str) -> dict:
    """M10: 도메인 가용성 — HTTP HEAD 200"""
    blog = conn.execute(
        "SELECT domain, config_status FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog or not blog["domain"]:
        return {"status": "unknown", "detail": "M10: 도메인 없음"}

    if blog["config_status"] in ("inactive", "disabled"):
        return {"status": "pass", "detail": f"M10: 비활성 블로그 — 스킵"}

    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(f"https://{blog['domain']}", method="HEAD")
        req.add_header("User-Agent", "OpsDashboard/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 400:
                return {"status": "pass", "detail": f"M10: HTTP {resp.status} 정상"}
            return {"status": "fail", "detail": f"M10: HTTP {resp.status}"}
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {"status": "fail", "detail": f"M10: 연결 실패 — {e}"}


# ---------------------------------------------------------------------------
# 정비 체크 실행기
# ---------------------------------------------------------------------------

MAINTENANCE_CHECKS = {
    "M01": _check_cjk_in_title,
    "M02": _check_image_repetition,
    "M03": _check_crosslink_relevance,
    "M04": _check_content_quality,
    "M05": _check_standard_compliance,
    "M06": _check_keyword_availability,
    "M07": _check_similar_title_safety,
    "M08": _check_cot_leak,
    "M09": _check_publish_log_integrity,
    "M10": _check_domain_health,
    "M11": _check_cjk_in_body_and_slug,
}


@register_check("maintenance_checklist")
def check_maintenance_checklist(conn, blog_id: str) -> dict:
    """정비 체크리스트 전체 실행.

    정비 대상 블로그(maintenance_status != 'none')에 대해서만 실행.
    """
    blog = conn.execute(
        "SELECT maintenance_status FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()

    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found"}

    if blog["maintenance_status"] == "none":
        return {
            "status": "pass",
            "detail": "정비 대상 아님 — maintenance_checklist 스킵",
        }

    # 체크리스트 초기화 (없으면)
    from ops_dashboard.db import init_maintenance_checklist
    init_maintenance_checklist(conn, blog_id)

    results = {}
    pass_count = 0
    fail_count = 0

    for check_id, check_fn in MAINTENANCE_CHECKS.items():
        try:
            result = check_fn(conn, blog_id)
            status = result.get("status", "unknown")
            detail = result.get("detail", "")

            # DB에 기록
            from ops_dashboard.db import set_check_item_status
            set_check_item_status(conn, blog_id, check_id, status, detail)

            results[check_id] = {"status": status, "detail": detail}
            if status == "pass":
                pass_count += 1
            elif status == "fail":
                fail_count += 1
        except Exception as e:
            logger.error("Maintenance check %s failed for %s: %s", check_id, blog_id, e)
            results[check_id] = {"status": "unknown", "detail": f"Error: {e}"}

    total = len(MAINTENANCE_CHECKS)
    all_pass = pass_count == total
    any_fail = fail_count > 0

    # resume_ready 업데이트
    from ops_dashboard.db import update_maintenance_status
    if all_pass:
        update_maintenance_status(conn, blog_id, "ready")
    elif any_fail:
        # ready가 아니면 in_progress 유지
        pass

    detail = f"{pass_count}/{total} 통과, {fail_count}개 실패"
    if all_pass:
        detail = f"전체 {total}항목 통과 — 재개 준비 완료"

    return {
        "status": "pass" if all_pass else "fail",
        "detail": f"M-체크리스트: {detail}",
    }
