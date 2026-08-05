#!/usr/bin/env python3
"""
CAP/TAP 블로그 오염 전수 스캐너 — 다국어 시그니처 확장판
blog_id 인자를 받아 해당 블로그의 content/posts/*.md를 스캔한다.
출력: JSON (표준 출력)
"""

import sys
import os
import re
import json
import glob

# ── 오염 시그니처 ─────────────────────────────────────────────
PATTERNS = {
    # 1. 한국어 사고과정 (기존 7패턴 유지)
    "ko_thinking": {
        "regex": r"사용자가 제공한 데이터|절대\s+.*\s+말라고 했습니다|초안:|이제\s+.*\s+작성|H2-\d|문장 수:|(?:^|\n)\s*주의:|(?:^|\n)\s*규칙|~해야 합니다\.",
        "lang": "ko", "severity": "high"
    },
    # 2. 영어 사고과정 누수
    "en_thinking": {
        "regex": r"(?:^|\n)\s*(?:The user has provided|Let me re-?[Rr]ead|Wait,|we need to|Let me|I should|Actually,|First,)\b",
        "lang": "en", "severity": "high"
    },
    # 3. 중국어/일본어 누수 — 간체 키워드
    "cjk_leak_keywords": {
        "regex": r"(?:我们|需要|根据|注意|规则|禁止|应当|必须|以上|以下|关于|分析|考虑|但是|所以|因为|如果|虽然|并且|或者|因此|然而|目前|现在|对于|通过|使用|包括|属于|作为|已经)",
        "lang": "zh", "severity": "high"
    },
    # 4. 프롬프트 지시문 노출
    "prompt_instruction_leak": {
        "regex": r"(?:^|\n)\s*(?:bold-list로 정리|테이블 금지|1~2문장으로 소개|H2 없이|최소 \d+문장|~를 명시해야|금지 표현|체크포인트|구조:|도입부 \()",
        "lang": "ko", "severity": "high"
    },
    # 5a. 문법 파괴형 역노출 — 진짜 오염 (draft 전환 대상)
    "forbidden_grammar_break": {
        "regex": r"확인해 보시기 필요합니다|보시기 필요합니다",
        "lang": "ko", "severity": "high"
    },
    # 5b. 스타일 금지어 — 프롬프트가 금지한 표현이 본문에 등장 (스타일 이슈, draft 불필요)
    "forbidden_word_reverse": {
        "regex": r"바랍니다|되시길|있으시|마무리하며|마치며|정리하며|알아보겠습니다|과연|놀랍게도|충격적으로",
        "lang": "ko", "severity": "medium"
    },
    # 6. 테스트/더미 글
    "test_dummy": {
        "regex": r"E2E Test|Test body|Test Title|Test body with image|## Heading \+ More content|이 테스트는|테스트용 포스트",
        "lang": "any", "severity": "low"
    },
    # 7. raw slug 제목 (날짜 패턴 시작)
    "raw_slug_title": {
        "regex": r"^title:\s*(?:20\d{2}-\d{2}-\d{2}-|rss-|ec[0-9a-f]{6}|eba[0-9a-f]|%[0-9a-fA-F])",
        "lang": "any", "severity": "medium", "in_title": True
    },
    # 8. 의미없는 선행문자
    "meaningless_prefix": {
        "regex": r"^[^#]*:\s*(?:ㅇㄴ|ㅁㄴㅇ|ㅇㅁㄴ|ㄹㅋ|ㅋㅋ|ㅎㅎㅎ|!!!\??)",
        "lang": "ko", "severity": "low"
    },
    # 9. 중국어 한자 비중 과다 — 본문에서 간체문장 패턴 (한 라인 내 3자 이상)
    "cjk_line_leak": {
        "regex": r"(?:^[^\n]*[\u4e00-\u9fff]{3,}[^\n]*$)",
        "lang": "zh", "severity": "high"
    },
    # 10. thinking/reasoning 태그 잔재
    "thinking_tag_remain": {
        "regex": r"<think(?:ing)?>|</think(?:ing)?>|<reasoning>|</reasoning>|<chain[- ]of[- ]thought>",
        "lang": "any", "severity": "high"
    },
}


def scan_file(filepath):
    """단일 .md 파일 스캔 — 감지된 오염 목록 반환"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return {"file": filepath, "error": str(e), "findings": []}

    lines = content.split('\n')

    # title 추출
    title = ""
    for line in lines:
        m = re.match(r"^title:\s*(.+)", line)
        if m:
            title = m.group(1).strip().strip('"').strip("'")
            break

    # body 시작 추출 (frontmatter --- 이후 첫 비주석 라인)
    body_start = ""
    in_frontmatter = False
    body_count = 0
    for line in lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter and line.strip() and not line.startswith('#'):
            body_start = line
            break

    findings = []
    for pname, pdef in PATTERNS.items():
        regex = pdef["regex"]
        in_title = pdef.get("in_title", False)
        severity = pdef["severity"]
        lang = pdef["lang"]

        if in_title:
            # 제목에서만 검사
            if re.search(regex, f"title: {title}"):
                findings.append({
                    "pattern": pname,
                    "lang": lang,
                    "severity": severity,
                    "context": title[:100]
                })
        else:
            # 본문 상단(첫 500자)에서 검사 — 전체가 아닌 빠른 스캔용
            if body_start and re.search(regex, body_start[:500]):
                m = re.search(regex, body_start[:500])
                findings.append({
                    "pattern": pname,
                    "lang": lang,
                    "severity": severity,
                    "context": m.group()[:100] if m else body_start[:100]
                })
            # cjk_line_leak: 전체 본문에서 라인별 검사 (빠르게)
            if pname == "cjk_line_leak":
                for line in lines:
                    if re.search(regex, line):
                        findings.append({
                            "pattern": pname,
                            "lang": lang,
                            "severity": severity,
                            "context": line.strip()[:100]
                        })
                        break  # 첫 발견만 기록
            # thinking_tag: 전체 검사
            if pname == "thinking_tag_remain":
                if re.search(regex, content):
                    m = re.search(regex, content)
                    findings.append({
                        "pattern": pname,
                        "lang": lang,
                        "severity": severity,
                        "context": m.group()[:50]
                    })

    return {
        "file": filepath,
        "title": title,
        "findings": findings
    }


def scan_blog(site_path):
    """블로그 전체 스캔"""
    posts_dir = os.path.join(site_path, "content", "posts")
    if not os.path.isdir(posts_dir):
        return {"error": f"posts dir not found: {posts_dir}", "results": []}

    md_files = glob.glob(os.path.join(posts_dir, "*.md")) + \
               glob.glob(os.path.join(posts_dir, "*/index.md"))
    results = []
    for fp in sorted(md_files):
        r = scan_file(fp)
        if r["findings"]:
            results.append(r)
    return {"blog": site_path, "total_posts": len(md_files), "contaminated": len(results), "results": results}


if __name__ == "__main__":
    blog_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not blog_id:
        print(json.dumps({"error": "usage: scanner.py <blog_id>"}))
        sys.exit(1)

    # blog_id → site_path 매핑
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

    site = SITE_MAP.get(blog_id)
    if not site:
        print(json.dumps({"error": f"unknown blog_id: {blog_id}"}))
        sys.exit(1)

    result = scan_blog(site)
    print(json.dumps(result, ensure_ascii=False, indent=2))
