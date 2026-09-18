#!/usr/bin/env python3
"""기존 ETAP 포스트 Book Now 링크에 affiliate-btn 클래스 부착 (FIX #3b)
대상: 14 블로그, 카드 블록 내 `target="_blank">Book Now</a>` 패턴
변환: target="_blank">Book Now</a> → target="_blank" class="affiliate-btn">Book Now</a>
주의: 이미 class 있는 링크는 스킵 (파일당 1회 확인 후 일괄)
백업: /tmp/etap_h2_backup_20260907000338.tar.gz (같은 content 트리)
"""
import re
import glob
import sys

BLOGS = ['watersports', 'bus', 'multiday', 'tours', 'transfers', 'walking',
         'citytours', 'culture', 'escape', 'ghost', 'layover', 'luxury',
         'nightlife', 'watertours']

DRY = '--apply' not in sys.argv
# 카드 블록 내부의 Book Now만: etap-product-cards div 내부에 있으므로 전체 파일에서
# class 없는 Book Now 링크 = 전부 카드 링크 (본문 프롬프트는 링크 금지라 다른 Book Now 없음)
PATTERN = re.compile(r'<a href="([^"]+)" rel="sponsored noopener" target="_blank">Book Now</a>')

def convert(path):
    with open(path) as f:
        text = f.read()
    matches = PATTERN.findall(text)
    if not matches:
        return 0
    new_text = PATTERN.sub(
        r'<a href="\1" rel="sponsored noopener" target="_blank" class="affiliate-btn">Book Now</a>',
        text)
    if new_text != text and not DRY:
        with open(path, 'w') as f:
            f.write(new_text)
    return len(matches)

grand = 0
for blog in BLOGS:
    total, files = 0, 0
    for p in glob.glob(f'{blog}-hugo/content/posts/*/index.md'):
        c = convert(p)
        if c:
            total += c
            files += 1
    grand += total
    print(f'{blog}: files={files} links={total} [{"APPLIED" if not DRY else "DRY"}]')
print(f'GRAND: {grand} [{"APPLIED" if not DRY else "DRY"}]')
