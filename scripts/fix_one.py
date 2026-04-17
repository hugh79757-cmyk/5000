#!/usr/bin/env python3
import os

f = "/Users/twinssn/Projects/CUAP/fitness-hugo/content/posts/저소음-실내자전거-추천---운동기구와-kc인증-미니-실내-자전거/index.md"
with open(f, "r", encoding="utf-8") as fh:
    content = fh.read()

# 전체 front matter를 재구성
end = content.find("---", 3)
body = content[end+3:]

new_fm = """---
title: "저소음 실내자전거 추천 - 운동기구와 [KC인증] 미니 실내 자전거"
slug: '저소음-실내자전거-추천---운동기구와-kc인증-미니-실내-자전거'
date: '2026-04-16T11:09:46+09:00'
draft: false
description: "실내 자전거를 선택할 때 가장 고민되는 점은 소음과 공간 활용입니다. 특히 아파트와 같은 밀집된 주거 공간에서는 소음이 큰 문제로 작용할 수 있습니다. 저소음 기능이 있는 자전거를 찾는다면, 어떤 제품이 나에게 가장 적합할지 고민이 많으실 겁니다.  저소음 실내 자전거 추천 제품을 통해"
tags: ['저소음 실내자전거 추천']
categories: ['추천']
---"""

# body에서 기존 front matter 잔해 이후 실제 본문 시작점 찾기
# description 뒤의 실제 본문
body_lines = body.strip().split("\n")
real_body_start = 0
for i, line in enumerate(body_lines):
    if line.strip() and not line.startswith("tags:") and not line.startswith("categories:") and not line.startswith("---") and not line.startswith("draft:") and not line.startswith("description:") and not line.startswith("date:") and not line.startswith("slug:") and not line.startswith("featureimage:"):
        real_body_start = i
        break

# 본문에서 첫 이미지 찾기
import re
img_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', body)
if img_match:
    img_url = img_match.group(1)
    new_fm = new_fm.replace("\n---", f'\nfeatureimage: "{img_url}"\n---')

with open(f, "w", encoding="utf-8") as fh:
    fh.write(new_fm + "\n" + body.strip() + "\n")

print("fixed")
