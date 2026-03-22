import os, re, glob

fixed = 0

# === 1. 단일 .md 파일: 날짜 포함 alias 추가 ===
for f in glob.glob("content/posts/????-??-??-*.md"):
    fname = os.path.basename(f).replace(".md", "")
    # 파일명에서 날짜 부분 추출
    match = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)", fname)
    if not match:
        continue
    date_part, slug_part = match.groups()
    old_url = f"/posts/{fname}/"
    
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    
    # 이미 aliases가 있으면 스킵
    if "aliases:" in content:
        continue
    
    # frontmatter 끝(두번째 ---) 앞에 aliases 삽입
    parts = content.split("---", 2)
    if len(parts) < 3:
        continue
    
    parts[1] = parts[1].rstrip() + f'\naliases:\n  - "{old_url}"\n'
    new_content = "---".join(parts)
    
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    fixed += 1

# === 2. 폴더형 index.md: 특수문자 제거된 slug에 이전 URL alias 추가 ===
# 패턴: 접수일시험일합격발표 → (접수일·시험일·합격발표)
# 패턴: 합격률NNN → 합격률-NN.N%
# 패턴: 따는-법-일정부터 → 따는-법-–-일정부터
# 패턴: 기능사날염 → 기능사(날염)

alias_map = {
    # 접수일시험일합격발표 패턴
    "접수일시험일합격발표": "(접수일·시험일·합격발표)",
}

for f in glob.glob("content/posts/*/index.md"):
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    
    if "aliases:" in content:
        continue
    
    slug_match = re.search(r'^slug:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    if not slug_match:
        continue
    
    slug = slug_match.group(1)
    old_slug = slug
    needs_alias = False
    
    # 접수일시험일합격발표 → (접수일·시험일·합격발표)
    if "접수일시험일합격발표" in slug:
        old_slug = slug.replace("접수일시험일합격발표", "(접수일·시험일·합격발표)")
        needs_alias = True
    
    # 합격률 뒤에 숫자 (806 → 80.6%…)
    m = re.search(r"합격률-(\d+)-", slug)
    if m:
        num = m.group(1)
        if len(num) == 3:
            formatted = f"{num[0]}{num[1]}.{num[2]}%…"
        elif len(num) == 4:
            formatted = f"{num[0:2]}{num[2]}.{num[3]}%…"
        else:
            formatted = num
        old_slug = slug.replace(f"합격률-{num}-", f"합격률-{formatted}-")
        needs_alias = True
    
    # 따는-법-일정부터 → 따는-법-–-일정부터
    if "따는-법-일정부터" in slug:
        old_slug = slug.replace("따는-법-일정부터", "따는-법-–-일정부터")
        needs_alias = True
    
    # 기능사날염 → 기능사(날염)
    if "기능사날염" in slug:
        old_slug = slug.replace("기능사날염", "기능사(날염)")
        needs_alias = True
    
    # 합격률시험일정준비기간 → 합격률·시험일정·준비기간
    if "합격률시험일정준비기간" in slug:
        old_slug = old_slug.replace("합격률시험일정준비기간", "합격률·시험일정·준비기간")
        needs_alias = True
    
    # 어떨까-2026 → 어떨까?-2026
    if "어떨까-2026" in old_slug and "?" not in old_slug:
        old_slug = old_slug.replace("어떨까-2026", "어떨까?-2026")
        needs_alias = True
    
    if not needs_alias:
        continue
    
    old_url = f"/posts/{old_slug}/"
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        continue
    
    parts[1] = parts[1].rstrip() + f'\naliases:\n  - "{old_url}"\n'
    new_content = "---".join(parts)
    
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    fixed += 1

print(f"총 {fixed}개 파일 수정 완료")
