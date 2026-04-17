#!/usr/bin/env python3
"""hugo.yaml -> config/_default/ TOML 폴더 방식 전환 (Blowfish 기술문서 준수)"""
import os

CUAP = "/Users/twinssn/Projects/CUAP"

blogs = {
    "baby-hugo": {
        "baseURL": "https://baby.informationhot.kr/",
        "title": "유아용품 추천 가이드",
        "description": "유아용품 추천 및 비교 리뷰",
    },
    "fitness-hugo": {
        "baseURL": "https://fitness.informationhot.kr/",
        "title": "운동용품 추천 가이드",
        "description": "운동용품 추천 및 비교 리뷰",
    },
    "appliance-hugo": {
        "baseURL": "https://appliance.informationhot.kr/",
        "title": "가전제품 추천 가이드",
        "description": "가전제품 추천 및 비교 리뷰",
    },
    "interior-hugo": {
        "baseURL": "https://interior.informationhot.kr/",
        "title": "가구 인테리어 추천 가이드",
        "description": "가구 인테리어 추천 및 비교 리뷰",
    },
    "laptop-hugo": {
        "baseURL": "https://laptop.informationhot.kr/",
        "title": "노트북 추천 가이드",
        "description": "노트북 추천 및 비교 리뷰",
    },
}

HUGO_TOML = """baseURL = "{baseURL}"
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
"""

LANGUAGES_KO_TOML = """languageCode = "ko"
languageName = "한국어"
weight = 1
title = "{title}"

[params]
  displayName = "KO"
  isoCode = "ko"
  dateFormat = "2006년 1월 2일"
  description = "{description}"
"""

MENUS_KO_TOML = """[[main]]
  name = "글목록"
  pageRef = "posts"
  weight = 10

[[main]]
  name = "태그"
  pageRef = "tags"
  weight = 20
"""

PARAMS_TOML = """colorScheme = "ocean"
defaultAppearance = "dark"
autoSwitchAppearance = false
enableSearch = true
mainSections = ["posts"]

[header]
  layout = "basic"
  showTitle = true

[footer]
  showCopyright = true
  showThemeAttribution = false
  showScrollToTop = true

[homepage]
  layout = "background"
  showRecent = true
  showRecentItems = 12

[article]
  showWordCount = false
  showReadingTime = false
  showDate = true
  showAuthor = false
  showBreadcrumbs = true
  showTableOfContents = true
  showRelatedContent = false

[list]
  showSummary = true
  showCards = true
  groupByYear = false
"""

MARKUP_TOML = """[goldmark]
  [goldmark.renderer]
    unsafe = true

[highlight]
  noClasses = false
"""

for blog, info in blogs.items():
    blog_dir = os.path.join(CUAP, blog)
    config_dir = os.path.join(blog_dir, "config", "_default")
    os.makedirs(config_dir, exist_ok=True)

    # hugo.toml
    with open(os.path.join(config_dir, "hugo.toml"), "w") as f:
        f.write(HUGO_TOML.format(**info))

    # languages.ko.toml
    with open(os.path.join(config_dir, "languages.ko.toml"), "w") as f:
        f.write(LANGUAGES_KO_TOML.format(**info))

    # menus.ko.toml
    with open(os.path.join(config_dir, "menus.ko.toml"), "w") as f:
        f.write(MENUS_KO_TOML)

    # params.toml
    with open(os.path.join(config_dir, "params.toml"), "w") as f:
        f.write(PARAMS_TOML)

    # markup.toml
    with open(os.path.join(config_dir, "markup.toml"), "w") as f:
        f.write(MARKUP_TOML)

    # hugo.yaml 삭제
    yaml_path = os.path.join(blog_dir, "hugo.yaml")
    if os.path.exists(yaml_path):
        os.remove(yaml_path)
        print(f"[{blog}] hugo.yaml 삭제")

    print(f"[{blog}] config/_default/ 생성 완료")

print("\n모든 블로그 설정 전환 완료")
