#!/usr/bin/env python3
"""ETAP 14 블로그 라이브 강등 H2 복원 (FIX #3)
<strong>X</strong> 단독 라인 (앞뒤 빈 줄, blockquote 아님) → ## X
변환 후 파일 수정 여부 리포트. 백업: /tmp/etap_h2_backup_20260907000338.tar.gz
"""
import re
import glob
import sys

BLOGS = ['watersports', 'bus', 'multiday', 'tours', 'transfers', 'walking',
         'citytours', 'culture', 'escape', 'ghost', 'layover', 'luxury',
         'nightlife', 'watertours']

DRY = '--apply' not in sys.argv

def convert(path):
    with open(path) as f:
        text = f.read()
    lines = text.split('\n')
    changed = 0
    for i, line in enumerate(lines):
        s = line.strip()
        m = re.fullmatch(r'<strong>([^<]+)</strong>', s)
        if not m:
            continue
        prev_blank = i == 0 or lines[i-1].strip() == ''
        next_blank = i + 1 >= len(lines) or lines[i+1].strip() == ''
        if prev_blank and next_blank and not s.startswith('>'):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f'{indent}## {m.group(1)}'
            changed += 1
    if changed and not DRY:
        with open(path, 'w') as f:
            f.write('\n'.join(lines))
    return changed

grand = 0
for blog in BLOGS:
    total, files = 0, 0
    for p in glob.glob(f'{blog}-hugo/content/posts/*/index.md'):
        c = convert(p)
        if c:
            total += c
            files += 1
    grand += total
    mode = 'APPLIED' if not DRY else 'DRY-RUN'
    print(f'{blog}: files={files} converted={total} [{mode}]')
print(f'GRAND: {grand} {"[APPLIED]" if not DRY else "[DRY-RUN]"}')
