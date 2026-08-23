#!/usr/bin/env python3
"""mechanical_check.py — 블로그 로컬 content/posts 전수 기계적 구조 검사 (읽기 전용).

사용법: python3 mechanical_check.py <blog_id1> <blog_id2> ... [--out DIR]
- 각 블로그의 site_path를 registry에서 조회, content/posts/{slug}/index.md 스캔
- ETAP 블로그는 /Users/twinssn/Projects/ETAP/{blog_id}/content/posts
- Blogger 4개(tvshow/ud/senior/tap-blogger)는 로컬 경로 없음 → SKIP 기록
- 출력: {out}/mech_{blog_id}.jsonl — 포스트당 1행, 평가 스키마 필드 포함
"""
import sys, os, json, re, hashlib, glob

AUDIT_DIR = "/tmp/5000-content-audit"
REGISTRY = os.path.join(AUDIT_DIR, "blog_registry_raw.json")

def load_registry():
    if not os.path.exists(REGISTRY):
        return {}
    raw = json.load(open(REGISTRY))
    blogs = raw if isinstance(raw, list) else raw.get("blogs", raw.get("items", []))
    return {b.get("id"): b for b in blogs if isinstance(b, dict) and b.get("id")}

def find_post_files(site_path):
    """content/posts/{slug}/index.md 목록. 없으면 content/posts/{slug}.md 폴백."""
    posts_dir = os.path.join(site_path, "content", "posts")
    files = []
    if os.path.isdir(posts_dir):
        files = sorted(glob.glob(os.path.join(posts_dir, "*", "index.md")))
        files += sorted(glob.glob(os.path.join(posts_dir, "*.md")))
    return files

def parse_frontmatter(text):
    """--- ... --- 헤더 파싱 (간단 yaml). 실패 시 {}."""
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    body = text[m.end():]
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().strip('"\'')
            v = v.strip().strip('"\'')
            # 리스트/딕셔너리는 문자열로만 보존
            if v.startswith("[") or v.startswith("{"):
                v = v.strip()
            fm[k] = v
    return fm, body

def mech_check(post_file, blog_id, frozen_slugs):
    with open(post_file, encoding="utf-8", errors="replace") as f:
        text = f.read()
    fm, body = parse_frontmatter(text)
    slug = fm.get("slug") or os.path.basename(os.path.dirname(post_file))
    title = fm.get("title", "").strip()
    date = fm.get("date", "")
    desc = fm.get("description", "").strip()

    # 본문 통계
    body_noshort = re.sub(r"{{<[^>]+>}}", "", body)  # shortcode 제거
    body_text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body_noshort)  # 이미지 제거
    body_text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", body_text)       # 링크 제거
    body_text = re.sub(r"^[#>\-\s*`|]+", "", body_text, flags=re.M)
    body_text = re.sub(r"\s+", " ", body_text).strip()

    h2_count = len(re.findall(r"^##\s", body_noshort, re.M))
    h3_count = len(re.findall(r"^###\s", body_noshort, re.M))
    img_count = len(re.findall(r"!\[[^\]]*\]\([^)]*\)", body_noshort))
    internal_links = len(re.findall(r"\[[^\]]*\]\((/[^)]*)\)", body_noshort))
    external_links = len(re.findall(r"\[[^\]]*\]\((https?://[^)]*)\)", body_noshort))

    # 템플릿/미치환 마커
    shortcode_markers = len(re.findall(r"\{\{<.*?>\}\}", body))
    raw_template_markers = len(re.findall(r"\{\{|\{%", body))
    todo_markers = len(re.findall(r"TODO|PLACEHOLDER|Lorem ipsum|example\.com", body, re.I))

    # hash (본문 전체 md5, 중복 탐지용)
    body_md5 = hashlib.md5(body_noshort.encode()).hexdigest()
    # prefix 유사도용 (본문 첫 500자 정규화)
    prefix = body_text[:500].replace(" ", "")[:200]

    # 지표 판정 (스키마 기반)
    title_len = len(title)
    body_len = len(body_text)
    is_frozen = slug in frozen_slugs

    return {
        "blog": blog_id,
        "slug": slug,
        "title": title[:120],
        "title_len": title_len,
        "title_flag": "LONG_TITLE" if title_len > 60 else ("SHORT_TITLE" if title_len < 10 else "OK"),
        "body_len": body_len,
        "body_flag": "TOO_SHORT" if body_len < 500 else ("SHORT" if body_len < 1500 else "OK"),
        "h2_count": h2_count,
        "h2_flag": "NO_H2" if h2_count == 0 else "OK",
        "h3_count": h3_count,
        "img_count": img_count,
        "internal_links": internal_links,
        "external_links": external_links,
        "shortcode_markers": shortcode_markers,
        "raw_template_markers": raw_template_markers,
        "todo_markers": todo_markers,
        "template_flag": "TEMPLATE_LEAK" if (raw_template_markers or todo_markers) else "OK",
        "has_date": bool(date),
        "has_desc": len(desc) > 20,
        "body_md5": body_md5,
        "body_prefix": prefix,
        "frozen": is_frozen,
        "file": post_file,
    }

def main():
    argv_rest = list(sys.argv[1:])
    if "--out" in argv_rest:
        idx = argv_rest.index("--out")
        if idx + 1 < len(argv_rest):
            out_dir = argv_rest[idx + 1]
            argv_rest = argv_rest[:idx] + argv_rest[idx + 2:]
        else:
            out_dir = AUDIT_DIR
            argv_rest = argv_rest[:idx]
    else:
        out_dir = AUDIT_DIR
    args = argv_rest
    out_dir = AUDIT_DIR
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        out_dir = sys.argv[idx + 1]
        # --out 다음에 오는 값(출력 디렉터리)이 blog_id로 섞이지 않도록 제거
        out_val = sys.argv[idx + 1]
        args = [a for a in args if a != out_val]
    os.makedirs(out_dir, exist_ok=True)

    registry = load_registry()
    # Interior 실험 FROZEN 슬러그 (부록 A — interior-hugo 기준)
    frozen_slugs = set()
    frozen_path = os.path.join(AUDIT_DIR, "frozen_interior_slugs.json")
    if os.path.exists(frozen_path):
        frozen_slugs = set(json.load(open(frozen_path)))

    total_posts, total_blogs = 0, 0
    for blog_id in args:
        info = registry.get(blog_id)
        if not info:
            with open(os.path.join(out_dir, f"mech_{blog_id}.jsonl"), "w") as f:
                f.write(json.dumps({"blog": blog_id, "status": "NOT_IN_REGISTRY"}) + "\n")
            continue
        site_path = info.get("site_path", "")
        if not site_path or not os.path.isdir(site_path):
            with open(os.path.join(out_dir, f"mech_{blog_id}.jsonl"), "w") as f:
                f.write(json.dumps({"blog": blog_id, "status": "NO_LOCAL_PATH",
                                    "platform": info.get("platform", "")}) + "\n")
            continue
        files = find_post_files(site_path)
        n = 0
        with open(os.path.join(out_dir, f"mech_{blog_id}.jsonl"), "w", encoding="utf-8") as f:
            for pf in files:
                try:
                    row = mech_check(pf, blog_id, frozen_slugs)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
                except Exception as e:
                    f.write(json.dumps({"blog": blog_id, "file": pf,
                                        "status": "CHECK_FAILED", "error": str(e)[:100]}) + "\n")
        total_blogs += 1
        total_posts += n
        print(f"{blog_id}: {n} posts checked ({len(files)} files)")

    print(f"TOTAL: {total_blogs} blogs, {total_posts} posts")

if __name__ == "__main__":
    main()
