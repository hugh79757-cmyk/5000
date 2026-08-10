#!/usr/bin/env python3
"""
C05: draft:true 발행 감지 포스트의 draft:true 제거
대상: travel4-hugo, travel3-hugo, travel2-hugo, rap5-hugo, rap4-hugo, rap3-hugo,
       rap2-hugo, rap-hugo, pet-hugo, laptop-hugo, kitchen-hugo, interior-hugo,
       fitness-hugo, camping-hugo, health-hugo, beauty-hugo, baby-hugo, appliance-hugo,
       biz-techpawz-hugo
레시피: Appendix C.6 C05
"""

import os
import re
import yaml
from pathlib import Path

TARGET_BLOGS = {
    "travel4-hugo": "/Users/twinssn/Projects/TAP/travel4-hugo",
    "travel3-hugo": "/Users/twinssn/Projects/TAP/travel3-hugo",
    "travel2-hugo": "/Users/twinssn/Projects/TAP/travel2-hugo",
    "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo",
    "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
    "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo",
    "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
    "rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo",
    "pet-hugo": "/Users/twinssn/Projects/CUAP/pet-hugo",
    "laptop-hugo": "/Users/twinssn/Projects/CUAP/laptop-hugo",
    "kitchen-hugo": "/Users/twinssn/Projects/CUAP/kitchen-hugo",
    "interior-hugo": "/Users/twinssn/Projects/CUAP/interior-hugo",
    "fitness-hugo": "/Users/twinssn/Projects/CUAP/fitness-hugo",
    "camping-hugo": "/Users/twinssn/Projects/CUAP/camping-hugo",
    "health-hugo": "/Users/twinssn/Projects/CUAP/health-hugo",
    "beauty-hugo": "/Users/twinssn/Projects/CUAP/beauty-hugo",
    "baby-hugo": "/Users/twinssn/Projects/CUAP/baby-hugo",
    "appliance-hugo": "/Users/twinssn/Projects/CUAP/appliance-hugo",
    "biz-techpawz-hugo": "/Users/twinssn/Projects/biz-techpawz-hugo",
}


def fix_draft_in_post(post_path: str) -> dict:
    """단일 포스트의 draft:true 제거"""
    result = {"path": post_path, "changes": []}

    with open(post_path, "r", encoding="utf-8") as f:
        content = f.read()

    # YAML frontmatter 영역 추출
    if not content.startswith("---"):
        result["error"] = "frontmatter 없음"
        return result

    parts = content.split("---", 2)
    if len(parts) < 3:
        result["error"] = "frontmatter 파싱 실패"
        return result

    fm_block = parts[1]
    body = parts[2]

    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        # YAML 파싱 실패 시 라인 단위로 처리
        lines = fm_block.split("\n")
        new_lines = []
        changed = False
        for line in lines:
            stripped = line.strip().lower()
            if re.match(r'^draft\s*:\s*true\s*$', stripped):
                # draft: true → draft: false
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}draft: false")
                changed = True
                result["changes"].append("draft:true → draft:false")
            else:
                new_lines.append(line)
        if changed:
            new_fm_block = "\n".join(new_lines)
            new_content = f"---{new_fm_block}---{body}"
            with open(post_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            result["written"] = True
        else:
            result["written"] = False
        return result

    if not isinstance(fm, dict):
        result["error"] = "frontmatter가 dict 아님"
        return result

    if fm.get("draft", "").lower() == "true" if isinstance(fm.get("draft"), str) else fm.get("draft") is True:
        fm["draft"] = False
        # YAML 재직렬화 (single-quote 스타일)
        new_fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        new_content = f"---{new_fm_yaml}---{body}"
        with open(post_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        result["changes"].append(f"draft:true → draft:false ({fm.get('title', '제목없음')})")
        result["written"] = True
    else:
        result["written"] = False

    return result


def fix_blog_drafts(blog_id: str, site_dir: str) -> dict:
    """블로그의 모든 포스트에서 draft:true 제거"""
    result = {"blog_id": blog_id, "posts_fixed": 0, "posts_checked": 0, "details": []}
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

        result["posts_checked"] += 1
        r = fix_draft_in_post(index_md)
        if r.get("written"):
            result["posts_fixed"] += 1
            result["details"].append(r["changes"][0] if r["changes"] else "수정됨")
        elif r.get("error"):
            pass  # 무시

    return result


def main():
    print("=== C05 draft:true 제거 ===")
    total_fixed = 0
    total_checked = 0

    for blog_id, site_dir in TARGET_BLOGS.items():
        if not os.path.isdir(site_dir):
            print(f"  SKIP {blog_id}: 디렉토리 없음")
            continue
        r = fix_blog_drafts(blog_id, site_dir)
        if r.get("error"):
            print(f"  {blog_id}: {r['error']}")
            continue
        print(f"  {blog_id}: {r['posts_fixed']}/{r['posts_checked']}건 수정")
        total_fixed += r["posts_fixed"]
        total_checked += r["posts_checked"]

    print(f"\n=== 요약 ===")
    print(f"총 {total_fixed}/{total_checked}건 draft:true 제거 완료")


if __name__ == "__main__":
    main()
