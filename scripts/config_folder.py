#!/usr/bin/env python3
"""hugo.toml -> config/_default/ 폴더 방식 전환 (기술문서 준수)"""
import os, shutil

CUAP = "/Users/twinssn/Projects/CUAP"

blogs = {
    "baby-hugo": ("https://baby.informationhot.kr/", "유아용품 추천 가이드", "유아용품 추천 및 비교 리뷰 블로그"),
    "fitness-hugo": ("https://fitness.informationhot.kr/", "운동용품 추천 가이드", "운동용품 추천 및 비교 리뷰 블로그"),
    "appliance-hugo": ("https://appliance.informationhot.kr/", "가전제품 추천 가이드", "가전제품 추천 및 비교 리뷰 블로그"),
    "interior-hugo": ("https://interior.informationhot.kr/", "가구 인테리어 추천 가이드", "가구 인테리어 추천 및 비교 리뷰 블로그"),
    "laptop-hugo": ("https://laptop.informationhot.kr/", "노트북 추천 가이드", "노트북 추천 및 비교 리뷰 블로그"),
}

HUGO_TOML = '''baseURL = "{url}"
languageCode = "ko"
title = "{title}"
theme = "blowfish"
defaultContentLanguage = "ko"
enableRobotsTXT = true

[pagination]
  pagerSize = 20

[outputs]
  home = ["HTML", "RSS", "JSON"]

[taxonomies]
  tag = "tags"
  category = "categories"
'''

LANGUAGES_KO_TOML = '''languageCode = "ko"
languageName = "한국어"
weight = 1
title = "{title}"

[params]
  displayName = "KO"
  isoCode = "ko"
  dateFormat = "2006년 1월 2일"
  description = "{desc}"
'''

MENUS_KO_TOML = '''[[main]]
  name = "글목록"
  pageRef = "posts"
  weight = 10

[[main]]
  name = "검색"
  pageRef = "search"
  weight = 20
'''

PARAMS_TOML = '''colorScheme = "ocean"
defaultAppearance = "dark"
autoSwitchAppearance = false
enableSearch = true
mainSections = ["posts"]
hotlinkFeatureImage = true

[header]
  layout = "basic"
  showTitle = true

[footer]
  showCopyright = true
  showThemeAttribution = false
  showScrollToTop = true

[homepage]
  layout = "page"
  showRecent = true
  showRecentItems = 12

[article]
  showWordCount = false
  showReadingTime = false
  showDate = true
  showAuthor = false
  showBreadcrumbs = true
  showTableOfContents = true
  showSummary = true
  showRelatedContent = false

[list]
  showSummary = true
  groupByYear = false

[taxonomy]
  showTermCount = true
'''

MARKUP_TOML = '''[goldmark]
  [goldmark.renderer]
    unsafe = true

[highlight]
  noClasses = false
'''

for blog, (url, title, desc) in blogs.items():
    blog_dir = os.path.join(CUAP, blog)
    config_dir = os.path.join(blog_dir, "config", "_default")

    # 기존 hugo.toml 삭제
    for f in ["hugo.toml", "hugo.yaml"]:
        p = os.path.join(blog_dir, f)
        if os.path.exists(p):
            os.remove(p)

    # config/_default/ 생성
    os.makedirs(config_dir, exist_ok=True)

    with open(os.path.join(config_dir, "hugo.toml"), "w") as f:
        f.write(HUGO_TOML.format(url=url, title=title))

    with open(os.path.join(config_dir, "languages.ko.toml"), "w") as f:
        f.write(LANGUAGES_KO_TOML.format(title=title, desc=desc))

    with open(os.path.join(config_dir, "menus.ko.toml"), "w") as f:
        f.write(MENUS_KO_TOML)

    with open(os.path.join(config_dir, "params.toml"), "w") as f:
        f.write(PARAMS_TOML)

    with open(os.path.join(config_dir, "markup.toml"), "w") as f:
        f.write(MARKUP_TOML)

    # content/posts/_index.md 확인/생성
    posts_index = os.path.join(blog_dir, "content", "posts", "_index.md")
    if not os.path.exists(posts_index):
        os.makedirs(os.path.dirname(posts_index), exist_ok=True)
        with open(posts_index, "w") as f:
            f.write("---\ntitle: \"글목록\"\n---\n")

    print(f"[{blog}] done")

print("\n완료")
