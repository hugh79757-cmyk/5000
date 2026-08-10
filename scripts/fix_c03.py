#!/usr/bin/env python3
"""
C03: 프론트매터 키 본문 유출 제거
대상: rap5-hugo, rap2-hugo, rap-hugo, interior-hugo, pet-hugo, rap4-hugo
레시피: Appendix C.6 C03
"""

import os
import re

FM_KEYS = [
    "title", "og_image", "featureimage", "date", "slug",
    "categories", "tags", "description", "draft", "image",
    "pubDate", "author"
]

FM_KEY_PATTERN = re.compile(
    r'^\s*(' + '|'.join(re.escape(k) for k in FM_KEYS) + r'):\s*.+$',
    re.MULTILINE
)

TARGET_BLOGS = {
    "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo",
    "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
    "rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo",
    "interior-hugo": "/Users/twinssn/Projects/CUAP/interior-hugo",
    "pet-hugo": "/Users/twinssn/Projects/CUAP/pet-hugo",
    "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
}


def fix_fm_key_leak_in_post(post_path: str) -> dict:
    """단일 포스트에서 frontmatter 키 유출 라인 제거"""
    result = {"path": post_path, "removed_lines": []}

    with open(post_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # frontmatter 영역 찾기 (---로 시작)
    fm_end_idx = None
    for i, line in enumerate(lines):
        if i > 0 and line.strip() == "---":
            fm_end_idx = i
            break

    if fm_end_idx is None:
        result["error"] = "frontmatter 종료 마커 없음"
        return result

    body_lines = lines[fm_end_idx + 1:]
    new_body_lines = []
    for line in body_lines:
        if FM_KEY_PATTERN.match(line):
            result["removed_lines"].append(line.strip()[:80])
        else:
            new_body_lines.append(line)

    if len(new_body_lines) != len(body_lines):
        with open(post_path, "w", encoding="utf-8") as f:
            f.writelines(lines[:fm_end_idx + 1] + new_body_lines)
        result["written"] = True
    else:
        result["written"] = False

    return result


def fix_blog_fm_leak(blog_id: str, site_dir: str) -> dict:
    """블로그의 모든 포스트에서 C03 수정"""
    result = {"blog_id": blog_id, "posts_fixed": 0, "total_removed": 0, "details": []}
    posts_dir = os.path.join(site_dir, "content", "posts")

    if not os.path.isdir(posts_dir):
        result["error"] = "content/posts 없음"
        return result

    for slug_dir in sorted(os.listdir(posts_dir)):
        slug_path = os.path.join(posts_dir, slug_dir)
        if not os.path.isdir(slug_path):
            continue
        index_md = os.path.join(slug_path, "index.md")
        if not os.path.isfile(index_md):
            continue

        r = fix_fm_key_leak_in_post(index_md)
        if r.get("written"):
            result["posts_fixed"] += 1
            result["total_removed"] += len(r["removed_lines"])
            for line in r["removed_lines"]:
                result["details"].append(f"{slug_dir}: {line}")
        elif r.get("error"):
            pass

    return result


def main():
    print("=== C03 frontmatter 키 본문 누수 제거 ===")
    total_fixed = 0
    total_removed = 0

    for blog_id, site_dir in TARGET_BLOGS.items():
        if not os.path.isdir(site_dir):
            print(f"  SKIP {blog_id}: 디렉토리 없음")
            continue
        r = fix_blog_fm_leak(blog_id, site_dir)
        if r.get("error"):
            print(f"  {blog_id}: {r['error']}")
            continue
        print(f"  {blog_id}: {r['posts_fixed']}개 포스트, {r['total_removed']}개 라인 제거")
        for d in r["details"][:3]:
            print(f"    - {d}")
        if len(r["details"]) > 3:
            print(f"    ... 외 {len(r['details']) - 3}건")
        total_fixed += r["posts_fixed"]
        total_removed += r["total_removed"]

    print(f"\n=== 요약 ===")
    print(f"총 {total_fixed}개 포스트, {total_removed}개 라인 제거 완료")


if __name__ == "__main__":
    main()
