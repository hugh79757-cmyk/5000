"""
quality_scanner.py — 발행 후 사후 품질 스캔 + 일별 로테이션 수동 검토 리포트
매일 스케줄러에서 1회 실행 (예: 23:00)

기능:
  1. 전날 발행된 모든 ETAP 포스트 자동 스캔 → 점수 낮은 글 텔레그램 알림
  2. 36개 블로그 로테이션 (매일 5개씩) → 수동 검토 대상 URL 텔레그램 전송
"""

import os, re, glob, sqlite3, json, logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parents[2]
ETAP_DIR    = PROJECT_DIR.parent / "ETAP"
TRAVEL_DB   = PROJECT_DIR / "data" / "travel-en.db"
SCANNER_DB  = PROJECT_DIR / "data" / "scanner.db"

# 로테이션 상태 저장 DB 초기화
def _init_scanner_db():
    conn = sqlite3.connect(str(SCANNER_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rotation_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date   TEXT,
            blog_ids    TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date   TEXT,
            blog_id     TEXT,
            slug        TEXT,
            score       INTEGER,
            issues      TEXT,
            word_count  INTEGER,
            h2_count    INTEGER,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# 텔레그램
# ============================================================
def _tg(msg: str):
    try:
        from shared.telegram_notifier import send_message
        send_message(msg)
    except Exception as e:
        logger.error(f"[Scanner] TG 전송 실패: {e}")

def _tg_warning(title, detail=""):
    try:
        from shared.telegram_notifier import send_warning
        send_warning(title, detail)
    except Exception as e:
        logger.error(f"[Scanner] TG warning 실패: {e}")


# ============================================================
# 단일 포스트 스캔 → 점수 반환
# ============================================================
BANNED = [
    "plethora", "vibrant", "bustling", "let's dive in", "without further ado",
    "hidden gem", "tapestry", "myriad", "embark on", "rich cultural heritage",
    "culinary delights", "adrenaline junkie", "crystal-clear waters",
    "unforgettable experience", "gastronomic journey", "bucket list",
    "world-class", "must-visit", "a must for", "paradise for",
    "adventure awaits", "look no further", "leave you breathless",
    "feast for the eyes", "in awe of", "of a lifetime",
]

def score_post(filepath: str, blog_id: str) -> dict:
    """Hugo index.md 파일 하나를 채점. 100점 만점."""
    issues = []
    score  = 100

    try:
        raw = open(filepath, encoding="utf-8").read()
    except Exception as e:
        return {"score": 0, "issues": [f"파일 읽기 실패: {e}"], "word_count": 0, "h2_count": 0}

    # 프론트매터 / 본문 분리
    fm_match = re.match(r'^---\n(.*?)\n---\n(.*)', raw, re.DOTALL)
    if not fm_match:
        return {"score": 0, "issues": ["프론트매터 파싱 실패"], "word_count": 0, "h2_count": 0}

    front_matter = fm_match.group(1)
    body         = fm_match.group(2)

    # ── draft 체크 (-30)
    if re.search(r'^draft:\s*true', front_matter, re.MULTILINE):
        issues.append("[CRITICAL] draft: true 상태로 발행됨")
        score -= 30

    # ── 단어 수
    word_count = len(body.split())
    if word_count < 400:
        issues.append(f"[CRITICAL] 단어 수 부족: {word_count}자 (최소 400)")
        score -= 25
    elif word_count < 600:
        issues.append(f"[WARNING] 단어 수 낮음: {word_count}자 (권장 600+)")
        score -= 10

    # ── H2 섹션 수
    h2_count = len(re.findall(r'^## ', body, re.MULTILINE))
    if h2_count < 3:
        issues.append(f"[CRITICAL] H2 섹션 부족: {h2_count}개 (최소 3)")
        score -= 20
    elif h2_count < 4:
        issues.append(f"[WARNING] H2 섹션 적음: {h2_count}개 (권장 4+)")
        score -= 5

    # ── 이미지 삽입 여부
    img_count = len(re.findall(r'!\[', body))
    if img_count == 0:
        issues.append("[WARNING] 이미지 없음")
        score -= 10
    elif img_count < 3:
        issues.append(f"[WARNING] 이미지 부족: {img_count}개 (권장 3+)")
        score -= 5

    # ── $0 / 0만원 데이터 오류
    if re.search(r'\$0\b', body):
        issues.append("[CRITICAL] $0 가격 오류 발견")
        score -= 20
    if re.search(r'\b0만원|\b0%', body):
        issues.append("[CRITICAL] 0만원 또는 0% 데이터 오류 발견")
        score -= 20

    # ── banned phrases
    banned_found = []
    for phrase in BANNED:
        if phrase.lower() in body.lower():
            banned_found.append(phrase)
    if len(banned_found) >= 5:
        issues.append(f"[CRITICAL] banned phrases {len(banned_found)}개: {', '.join(banned_found[:5])}")
        score -= 15
    elif banned_found:
        issues.append(f"[WARNING] banned phrases {len(banned_found)}개: {', '.join(banned_found[:3])}")
        score -= len(banned_found) * 2

    # ── disclaimer 누락
    if 'etap-disclaimer-card' not in body:
        issues.append("[WARNING] disclaimer 누락")
        score -= 5

    # ── 허위 URL (techpawz 외부 링크)
    urls = re.findall(r'https?://[^\s\)\"]+', body)
    bad_urls = [u for u in urls if not any(d in u for d in
                ["techpawz.com", "r2.dev", "googlesyndication.com",
                 "viator.com", "omio.com", "airalo.com", "klook.com",
                 "getyourguide.com", "unsplash.com", "pexels.com"])]
    if bad_urls:
        issues.append(f"[WARNING] 미인가 URL {len(bad_urls)}개: {bad_urls[0][:50]}")
        score -= len(bad_urls) * 3

    # ── title 누락
    if not re.search(r'^title:', front_matter, re.MULTILINE):
        issues.append("[CRITICAL] title 누락")
        score -= 20

    score = max(0, score)
    return {
        "score":      score,
        "issues":     issues,
        "word_count": word_count,
        "h2_count":   h2_count,
    }


# ============================================================
# 전날 발행 포스트 자동 스캔
# ============================================================
def scan_yesterday(blogs: list, target_date: str = None) -> list:
    """target_date(YYYY-MM-DD) 발행 포스트 전체 스캔. 기본값=어제."""
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    low_score_posts = []  # score < 70인 포스트
    total_scanned   = 0
    conn = sqlite3.connect(str(SCANNER_DB))

    for blog in blogs:
        blog_id   = blog.get("id", "")
        site_path = blog.get("site_path", "")
        if not site_path or not os.path.isdir(site_path):
            continue

        posts_dir = os.path.join(site_path, "content", "posts")
        if not os.path.isdir(posts_dir):
            continue

        for md_path in glob.glob(f"{posts_dir}/*/index.md"):
            try:
                raw = open(md_path, encoding="utf-8").read()
            except Exception:
                continue

            # 날짜 필터
            date_match = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', raw, re.MULTILINE)
            if not date_match or date_match.group(1) != target_date:
                continue

            slug   = md_path.split("/")[-2]
            result = score_post(md_path, blog_id)
            total_scanned += 1

            conn.execute(
                "INSERT INTO scan_results (scan_date, blog_id, slug, score, issues, word_count, h2_count) VALUES (?,?,?,?,?,?,?)",
                (target_date, blog_id, slug,
                 result["score"], json.dumps(result["issues"]),
                 result["word_count"], result["h2_count"])
            )

            if result["score"] < 70:
                domain = blog_id.replace("-hugo", "")
                low_score_posts.append({
                    "blog_id":    blog_id,
                    "slug":       slug,
                    "score":      result["score"],
                    "issues":     result["issues"],
                    "word_count": result["word_count"],
                    "h2_count":   result["h2_count"],
                    "url":        f"https://{domain}.techpawz.com/{slug}/",
                })

    conn.commit()
    conn.close()

    logger.info(f"[Scanner] {target_date} 스캔 완료: {total_scanned}건, 저품질 {len(low_score_posts)}건")
    return low_score_posts, total_scanned


# ============================================================
# 로테이션 — 매일 5개 블로그 수동 검토 대상 선정
# ============================================================
def get_rotation_blogs(blogs: list, today: str = None) -> list:
    """오늘 수동 검토할 5개 블로그 반환. 순서는 blog_id 알파벳 기준 순환."""
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(str(SCANNER_DB))

    # 오늘 이미 선정된 게 있으면 재사용
    row = conn.execute(
        "SELECT blog_ids FROM rotation_log WHERE scan_date=?", (today,)
    ).fetchone()

    if row:
        conn.close()
        return json.loads(row[0])

    # 최근 로테이션 이력에서 마지막 인덱스 파악
    last_row = conn.execute(
        "SELECT blog_ids FROM rotation_log ORDER BY id DESC LIMIT 1"
    ).fetchone()

    all_ids = sorted([b["id"] for b in blogs])  # 알파벳 정렬
    n       = len(all_ids)

    if last_row:
        last_batch = json.loads(last_row[0])
        last_id    = last_batch[-1]
        try:
            start_idx = (all_ids.index(last_id) + 1) % n
        except ValueError:
            start_idx = 0
    else:
        start_idx = 0

    # 5개 순환 선정
    selected = []
    for i in range(5):
        selected.append(all_ids[(start_idx + i) % n])

    conn.execute(
        "INSERT INTO rotation_log (scan_date, blog_ids) VALUES (?,?)",
        (today, json.dumps(selected))
    )
    conn.commit()
    conn.close()
    return selected


# ============================================================
# 수동 검토용 샘플 URL 추출 (각 블로그 최신 1건)
# ============================================================
def get_sample_urls(blog_ids: list, blogs: list) -> list:
    """각 블로그의 가장 최근 포스트 URL 반환."""
    blog_map = {b["id"]: b for b in blogs}
    samples  = []

    for blog_id in blog_ids:
        blog      = blog_map.get(blog_id, {})
        site_path = blog.get("site_path", "")
        if not site_path:
            continue

        posts_dir = os.path.join(site_path, "content", "posts")
        files = sorted(
            glob.glob(f"{posts_dir}/*/index.md"),
            key=os.path.getmtime, reverse=True
        )
        if not files:
            continue

        slug   = files[0].split("/")[-2]
        domain = blog_id.replace("-hugo", "")
        result = score_post(files[0], blog_id)

        samples.append({
            "blog_id": blog_id,
            "slug":    slug,
            "url":     f"https://{domain}.techpawz.com/{slug}/",
            "score":   result["score"],
            "issues":  result["issues"],
        })

    return samples


# ============================================================
# 텔레그램 리포트 전송
# ============================================================
def send_report(low_score_posts: list, total_scanned: int,
                rotation_samples: list, target_date: str):
    """스캔 결과 + 로테이션 수동 검토 대상을 텔레그램으로 전송."""

    lines = [f"📊 *ETAP 품질 리포트 — {target_date}*",
             f"스캔: {total_scanned}건 | 저품질(70점↓): {len(low_score_posts)}건",
             ""]

    # ── 저품질 포스트
    if low_score_posts:
        lines.append("🚨 *저품질 포스트 (수정 필요)*")
        for p in sorted(low_score_posts, key=lambda x: x["score"])[:10]:
            top_issue = p["issues"][0] if p["issues"] else "확인 필요"
            lines.append(
                f"• [{p['blog_id']}] {p['score']}점\n"
                f"  {top_issue}\n"
                f"  {p['url']}"
            )
    else:
        lines.append("✅ 저품질 포스트 없음")

    lines.append("")

    # ── 로테이션 수동 검토
    lines.append("🔍 *오늘 수동 검토 블로그 (5개)*")
    for s in rotation_samples:
        score_emoji = "✅" if s["score"] >= 80 else "⚠️" if s["score"] >= 60 else "🚨"
        lines.append(
            f"{score_emoji} [{s['blog_id']}] {s['score']}점\n"
            f"  {s['url']}"
        )

    msg = "\n".join(lines)
    _tg(msg)
    logger.info(f"[Scanner] 텔레그램 리포트 전송 완료")


# ============================================================
# 메인 진입점
# ============================================================
def run_scan(target_date: str = None):
    """스케줄러에서 호출하는 메인 함수."""
    _init_scanner_db()

    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    today = datetime.now().strftime("%Y-%m-%d")

    # blogs 로드
    try:
        import yaml
        etap_yaml = PROJECT_DIR / "config" / "blogs.d" / "etap.yaml"
        blogs = yaml.safe_load(open(etap_yaml))["blogs"]
    except Exception as e:
        logger.error(f"[Scanner] blogs 로드 실패: {e}")
        return

    # ① 자동 스캔
    low_score_posts, total_scanned = scan_yesterday(blogs, target_date)

    # ② 로테이션 블로그 선정
    rotation_blog_ids = get_rotation_blogs(blogs, today)
    rotation_samples  = get_sample_urls(rotation_blog_ids, blogs)

    # ③ 텔레그램 리포트
    send_report(low_score_posts, total_scanned, rotation_samples, target_date)

    return {
        "scanned":         total_scanned,
        "low_score_count": len(low_score_posts),
        "rotation_blogs":  rotation_blog_ids,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_scan()
    print(result)
