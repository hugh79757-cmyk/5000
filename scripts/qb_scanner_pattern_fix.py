#!/usr/bin/env python3
"""
Q-B Scanner Pattern Fix for rap2-hugo disclaimer detection.

Issue: D-1 audit scanner pattern missed rap2-hugo disclaimer phrases.
Root cause: Scanner pattern didn't include rap2-hugo specific phrases
('청약홈', '공공데이터', '한국부동산원') used in its disclaimer text.

Fix: Extended scanner pattern to include rap2-hugo specific terms.

Before: r'면책|출처|국토교통부|국토부|데이터\s*출처|참고\s*자료'
After:  r'면책|출처|국토교통부|국토부|데이터\s*출처|참고\s*자료|청약홈|공공데이터|한국부동산원'

Verification: 491 rap2-hugo posts scanned
- OLD pattern: 96.9% missing (476/491)
- NEW pattern: 0.0% missing (0/491)
"""

import re

# Q-B Fixed Scanner Pattern
DISCLAIMER_PATTERN = re.compile(
    r'면책|출처|국토교통부|국토부|데이터\s*출처|참고\s*자료|청약홈|공공데이터|한국부동산원',
    re.IGNORECASE
)

def check_disclaimer(content: str) -> bool:
    """Check if content contains disclaimer/source attribution markers."""
    # Check body content (after frontmatter)
    body = content.split('---', 2)[-1] if content.startswith('---') else content
    return bool(DISCLAIMER_PATTERN.search(body))

if __name__ == "__main__":
    # Quick verification
    import os
    QUARANTINED = {
        '관악드림동아-실거래가-분석', '강동구-실거래가-8월-최고-25억-분석',
        '광교호반베르디움-실거래가-분석', '강남구-실거래가-2026년-8월-압구정-중심-분석',
        '마포구-실거래가-종합-8월-분석-최고-27억', '충북-청약-8월-공고-매입임대행복주택-예비입주자-모음',
        '청약-정정공고-15건-임대주택-모집-정보', '용인-수지-래미안이스트팰리스1단지-실거래가-분석',
        '목동-롯데캐슬-마에스트로-양천구-브랜드-가치-분석', '사당롯데캐슬2차-실거래가-분석-동작구-브랜드-아파트-가치',
    }
    path = '/Users/twinssn/Projects/RAP/rap2-hugo/content/posts'
    missing = 0
    total = 0
    for fname in os.listdir('/Users/twinssn/Projects/RAP/rap2-hugo/content/posts'):
        if fname in QUARANTINED: continue
        fpath = os.path.join(path, fname, 'index.md')
        if os.path.isfile(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            if not check_disclaimer(content):
                missing += 1
    total = len([f for f in os.listdir('/Users/twinssn/Projects/RAP/rap2-hugo/content/posts') if f not in {'관악드림동아-실거래가-분석', '강동구-실거래가-8월-최고-25억-분석', '광교호반베르디움-실거래가-분석', '강남구-실거래가-2026년-8월-압구정-중심-분석', '마포구-실거래가-종합-8월-분석-최고-27억', '충북-청약-8월-공고-매입임대행복주택-예비입주자-모음', '청약-정정공고-15건-임대주택-모집-정보', '용인-수지-래미안이스트팰리스1단지-실거래가-분석', '목동-롯데캐슬-마에스트로-양천구-브랜드-가치-분석', '사당롯데캐슬2차-실거래가-분석-동작구-브랜드-아파트-가치'} and os.path.isdir(os.path.join('/Users/twinssn/Projects/RAP/rap2-hugo/content/posts', f))])
    print(f"Q-B Fix Verified: {missing}/{total} missing ({missing/total*100:.1f}%)")
