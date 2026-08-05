#!/usr/bin/env python3
"""
Phase 2: 오염 글 draft 전환 스크립트
- true positive 패턴만 draft 처리 (ko_thinking, test_dummy, prompt_instruction_leak, cjk_line_leak_forbidden)
- forbidden_word_reverse는 별도 판정 (문맥 확인 필요)
- cjk_line_leak는 false positive 다수 (한국어 문화유산 콘텐츠)
"""

import sys
import os
import re
import subprocess
import json

# draft 전환 대상 패턴 (강한 오염 시그니처)
DRAFT_PATTERNS = {"ko_thinking", "test_dummy", "prompt_instruction_leak", "cjk_line_leak", "thinking_tag_remain", "forbidden_grammar_break"}

def add_draft_true(filepath):
    """파일 프론트매터에 draft: true 추가 (라인 편집)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return False, "read error"
    
    # 기존 draft 라인 찾기
    for i, line in enumerate(lines):
        if re.match(r"^draft:\s*(true|false)", line.strip()):
            if "true" in line:
                return False, "already draft"
            lines[i] = "draft: true\n"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True, f"line {i+1}: draft: false -> true"
    
    # frontmatter 끝에 삽입 (--- 라인 앞)
    for i, line in enumerate(lines):
        if line.strip() == "---" and i > 0:
            lines.insert(i, "draft: true\n")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True, f"line {i+1}: inserted draft: true"
    
    return False, "no frontmatter found"


def scan_and_draft(blog_id, site_path):
    """블로그 스캔 + draft 전환"""
    posts_dir = os.path.join(site_path, "content", "posts")
    md_files = glob.glob(os.path.join(posts_dir, "*.md")) + \
               glob.glob(os.path.join(posts_dir, "*/index.md"))
    
    # 스캔 실행
    r = subprocess.run(
        ["python3", "/Users/twinssn/Projects/5000/scripts/scan_multilingual_leak.py", blog_id],
        capture_output=True, text=True
    )
    try:
        scan_data = json.loads(r.stdout)
    except:
        return {"blog": blog_id, "changed": 0, "files": []}
    
    changed_files = []
    for item in scan_data.get("results", []):
        filepath = item["file"]
        findings = item.get("findings", [])
        
        # 강한 오염 패턴이 있는 파일만 draft 전환
        strong_patterns = set(f["pattern"] for f in findings) & DRAFT_PATTERNS
        if not strong_patterns:
            continue
        
        ok, msg = add_draft_true(filepath)
        if ok:
            changed_files.append({
                "file": filepath.split("/")[-1] if filepath.endswith(".md") else filepath.split("/")[-2],
                "patterns": list(strong_patterns),
                "action": msg
            })
    
    return {"blog": blog_id, "changed": len(changed_files), "files": changed_files}


if __name__ == "__main__":
    import glob
    
    SITE_MAP = {
        "compare-hugo": "/Users/twinssn/Projects/cap/compare-hugo",
        "deal-hugo": "/Users/twinssn/Projects/cap/deal-hugo",
        "ev-hugo": "/Users/twinssn/Projects/cap/ev-hugo",
        "guide-hugo": "/Users/twinssn/Projects/cap/guide-hugo",
        "hotissue-hugo": "/Users/twinssn/Projects/cap/hotissue-hugo",
        "tco-hugo": "/Users/twinssn/Projects/cap/tco-hugo",
        "rank-hugo": "/Users/twinssn/Projects/cap/rank-hugo",
        "pick-hugo": "/Users/twinssn/Projects/cap/pick-hugo",
        "travel-hugo": "/Users/twinssn/Projects/TAP/travel-hugo",
        "travel1-hugo": "/Users/twinssn/Projects/TAP/travel1-hugo",
        "travel2-hugo": "/Users/twinssn/Projects/TAP/travel2-hugo",
        "travel3-hugo": "/Users/twinssn/Projects/TAP/travel3-hugo",
        "travel4-hugo": "/Users/twinssn/Projects/TAP/travel4-hugo",
    }
    
    total_changed = 0
    for blog_id, site in SITE_MAP.items():
        result = scan_and_draft(blog_id, site)
        if result["changed"] > 0:
            print(f"### {blog_id}: {result['changed']}건 draft 전환")
            for f in result["files"]:
                print(f"  {f['file'][:55]}: {f['patterns']}")
            total_changed += result["changed"]
        else:
            print(f"### {blog_id}: 0건 (변경 없음)")
    
    print(f"\n## 총 {total_changed}건 draft 전환 완료")
