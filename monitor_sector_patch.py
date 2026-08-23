#!/usr/bin/env python3
"""monitor_sector.py 패치 후보 — canonical URL 기반 permalink 검증.

이 파일은 운영 monitor를 변경하지 않는다. 검증용으로만 사용.
원인: Cloudflare Pages는 한글 경로를 raw UTF-8로 서빙하되,
      percent-encoded 경로(%EC%84%B9...)는 404를 반환할 수 있음.
해결: Hugo가 생성한 canonical URL을 추출하여 검증.

사용법:
  python3 monitor_sector_patch.py          # 최신 기사 canonical URL 확인
  python3 monitor_sector_patch.py --all    # 최근 5건 확인
"""
import sqlite3
import os
import re
import subprocess
from urllib.parse import unquote

FIVEK = "/Users/twinssn/Projects/5000"
STAP = "/Users/twinssn/Projects/STAP"
STAP_DB = os.path.join(STAP, "data", "stap_content.db")
HUGO_PUBLIC = os.path.join(STAP, "sector-hugo", "public")


def get_articles(n=5):
    """최근 기사 n건 조회."""
    conn = sqlite3.connect(STAP_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, slug FROM articles "
        "WHERE blog_id='sector-hugo' ORDER BY id DESC LIMIT ?",
        (n,)
    ).fetchall()
    conn.close()
    return rows


def extract_canonical_from_html(html_path):
    """Hugo 생성 HTML에서 canonical URL 추출.

    Hugo Blowfish 테마 형식: <link rel=canonical href=https://.../>
    따옴표 없는 href= 속성 지원. 경로 내 '/'와 태그 종료 '/>'를 구분.
    """
    if not os.path.exists(html_path):
        return None
    with open(html_path) as f:
        html = f.read()
    # 따옴표 있는 경우: rel="canonical" href="https://..."
    m = re.search(r'rel="canonical"\s+href="(https://[^"]+)"', html)
    if m:
        return m.group(1)
    # 따옴표 없는 경우: rel=canonical href=https://.../>  또는  rel=canonical href=https://...>
    # [^>]+? 로 non-greedy 매칭 후 /> 또는 > 종료
    m = re.search(r'rel=canonical\s+href=(https://[^>]+?)(?:\s*/?>)', html)
    if m:
        return m.group(1)
    return None


def check_http(url, timeout=10):
    """curl HEAD 요청으로 HTTP 상태 확인."""
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=timeout
        )
        return int(result.stdout.strip()) if result.stdout.strip() else 0
    except Exception:
        return 0


def build_url_variants(slug):
    """slug로부터 URL 변형 3종 생성."""
    base = "https://sector.techpawz.com/posts"
    return {
        "raw": f"{base}/{slug}/",
        "lowercase_pct": f"{base}/{_percent_encode(slug, lower=True)}/",
        "uppercase_pct": f"{base}/{_percent_encode(slug, lower=False)}/",
    }


def _percent_encode(text, lower=True):
    """정확히 한 번 UTF-8 percent-encoding."""
    result = []
    for byte in text.encode("utf-8"):
        if 0x21 <= byte <= 0x7E and byte not in (0x25, 0x23, 0x5B, 0x5D):
            result.append(chr(byte))
        else:
            hex_str = f"{byte:02X}" if not lower else f"{byte:02x}"
            result.append(f"%{hex_str}")
    return "".join(result)


def verify_article(article):
    """단일 기사에 대해 canonical URL + 3종 변형 검증."""
    slug = article["slug"]
    article_id = article["id"]

    # Hugo public에서 canonical URL 추출
    canonical_url = None
    for candidate in [
        os.path.join(HUGO_PUBLIC, "posts", slug, "index.html"),
        os.path.join(HUGO_PUBLIC, "posts", unquote(slug), "index.html"),
    ]:
        canonical_url = extract_canonical_from_html(candidate)
        if canonical_url:
            break

    # URL 변형별 HTTP 확인
    variants = build_url_variants(slug)
    results = {}
    for name, url in variants.items():
        results[name] = check_http(url)

    # canonical URL도 확인
    canonical_status = 0
    if canonical_url:
        canonical_status = check_http(canonical_url)

    return {
        "article_id": article_id,
        "title": article["title"][:40],
        "slug": slug,
        "canonical_url": canonical_url,
        "canonical_status": canonical_status,
        "raw_status": results["raw"],
        "lowercase_pct_status": results["lowercase_pct"],
        "uppercase_pct_status": results["uppercase_pct"],
    }


def main():
    import sys
    n = 5 if "--all" in sys.argv else 1
    articles = get_articles(n)

    for article in articles:
        r = verify_article(article)
        print(f"\n=== id={r['article_id']}: {r['title']} ===")
        print(f"  slug: {r['slug']}")
        print(f"  canonical: {r['canonical_url'] or 'NOT FOUND'}")
        print(f"  canonical HTTP: {r['canonical_status']}")
        print(f"  raw slug HTTP: {r['raw_status']}")
        print(f"  lowercase %%xx HTTP: {r['lowercase_pct_status']}")
        print(f"  uppercase %%XX HTTP: {r['uppercase_pct_status']}")

        # 판정
        if r["canonical_status"] == 200:
            print(f"  → canonical URL 정상 (단일 기준)")
        elif r["raw_status"] == 200:
            print(f"  → raw slug 정상, canonical 미확인")
        else:
            print(f"  → ⚠️ 확인 필요")


if __name__ == "__main__":
    main()
