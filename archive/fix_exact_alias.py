#!/usr/bin/env python3
import re

filepath = "/Users/twinssn/Desktop/rotcha-hugo/content/posts/2020-07-06-인간본성의-법칙-왜-우리는-금기시-하는-것을-동경할까-그림자-활용법.md"

# 티스토리 원본 URL 경로
alias = "/entry/왜-우리는-금기시-하는-것을-동경할까-그림자-활용법"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if alias in content:
    print("이미 존재함")
else:
    if 'aliases:' in content:
        content = re.sub(r'(aliases:\s*\n)', f'\\1  - "{alias}"\n', content)
    else:
        parts = content.split('---', 2)
        if len(parts) >= 3:
            parts[1] = parts[1].rstrip() + f'\naliases:\n  - "{alias}"\n'
            content = '---'.join(parts)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"추가 완료: {alias}")
