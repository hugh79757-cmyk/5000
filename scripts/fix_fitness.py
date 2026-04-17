#!/usr/bin/env python3
"""fitness-hugo: featureimage 제거 + 깨진 front matter 복구"""
import re, glob, os

CUAP = "/Users/twinssn/Projects/CUAP"

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return False

    end = content.find("---", 3)
    if end == -1:
        return False

    fm = content[3:end]
    body = content[end+3:]
    original_fm = fm

    # featureimage 줄 제거 (여러 줄에 걸칠 수 있음)
    fm = re.sub(r'featureimage: ".*?"\n', '', fm, flags=re.DOTALL)
    fm = re.sub(r"featureimage: '.*?'\n", '', fm, flags=re.DOTALL)

    # 깨진 slug 복구: slug 줄 뒤에 바로 featureimage가 왔던 경우
    # slug: '저소음-실내자전거-추천\n 이런 식으로 잘려있음
    # title에서 slug 재생성
    title_match = re.search(r'title: "(.+?)"', fm)
    slug_match = re.search(r"slug: '(.*?)('|$)", fm, re.DOTALL)

    if slug_match and not slug_match.group(1).endswith("'"):
        # slug이 깨짐 — title에서 재생성
        if title_match:
            title = title_match.group(1)
            # 디렉토리 이름에서 slug 추출
            dir_name = os.path.basename(os.path.dirname(filepath))
            fm = re.sub(r"slug: '.*", f"slug: '{dir_name}'", fm)

    # 깨진 줄 정리: ---운동기구... 같은 잔해 제거
    fm = re.sub(r"\n---[^\n]+\n", "\n", fm)

    if fm != original_fm:
        content = "---" + fm + "---" + body
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False

# fitness-hugo 전체 처리
pattern = os.path.join(CUAP, "fitness-hugo", "content", "**", "index.md")
files = glob.glob(pattern, recursive=True)
fixed = 0
for f in files:
    if fix_file(f):
        fixed += 1
print(f"[fitness-hugo] fixed: {fixed}/{len(files)}")

# 다른 블로그도 featureimage 잔존 확인 및 제거
for blog in ["baby-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]:
    pattern = os.path.join(CUAP, blog, "content", "**", "index.md")
    files = glob.glob(pattern, recursive=True)
    fixed2 = 0
    for f in files:
        if fix_file(f):
            fixed2 += 1
    if fixed2 > 0:
        print(f"[{blog}] fixed: {fixed2}/{len(files)}")
