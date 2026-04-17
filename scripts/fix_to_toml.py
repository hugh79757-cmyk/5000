#!/usr/bin/env python3
"""CUAP hugo.yaml -> hugo.toml (CAP 방식)"""
import os

CUAP = "/Users/twinssn/Projects/CUAP"

blogs = {
    "baby-hugo": ("https://baby.informationhot.kr/", "유아용품 추천 가이드", "유아용품 추천 및 비교 리뷰 블로그"),
    "fitness-hugo": ("https://fitness.informationhot.kr/", "운동용품 추천 가이드", "운동용품 추천 및 비교 리뷰 블로그"),
    "appliance-hugo": ("https://appliance.informationhot.kr/", "가전제품 추천 가이드", "가전제품 추천 및 비교 리뷰 블로그"),
    "interior-hugo": ("https://interior.informationhot.kr/", "가구 인테리어 추천 가이드", "가구 인테리어 추천 및 비교 리뷰 블로그"),
    "laptop-hugo": ("https://laptop.informationhot.kr/", "노트북 추천 가이드", "노트북 추천 및 비교 리뷰 블로그"),
}

TOML_TEMPLATE = '''baseURL = "{url}"
languageCode = "ko"
title = "{title}"
theme = "blowfish"
enableRobotsTXT = true

[pagination]
  pagerSize = 20

[params]
  colorScheme = "ocean"
  defaultAppearance = "dark"
  autoSwitchAppearance = false
  description = "{desc}"
  mainSections = ["posts"]
  enableSearch = true

  [params.homepage]
    layout = "page"
    showRecent = true
    showRecentItems = 12
    cardView = false

  [params.article]
    showWordCount = false
    showReadingTime = false
    showDate = true
    showAuthor = false
    showBreadcrumbs = true
    showTableOfContents = true

  [params.list]
    showWordCount = false
    showSummary = true
    groupByYear = false

  [params.taxonomy]
    showTermCount = true

[taxonomies]
  tag = "tags"
  category = "categories"

[outputs]
  home = ["HTML", "RSS", "JSON"]
  section = ["HTML", "RSS"]

[sitemap]
  changefreq = "daily"
  priority = 0.7
  filename = "sitemap.xml"

[markup]
  [markup.goldmark]
    [markup.goldmark.renderer]
      unsafe = true

[[menus.main]]
  name = "글목록"
  pageRef = "posts"
  weight = 10

[[menus.main]]
  name = "검색"
  pageRef = "search"
  weight = 20
'''

for blog, (url, title, desc) in blogs.items():
    blog_dir = os.path.join(CUAP, blog)

    yaml_path = os.path.join(blog_dir, "hugo.yaml")
    if os.path.exists(yaml_path):
        os.remove(yaml_path)

    toml_path = os.path.join(blog_dir, "hugo.toml")
    with open(toml_path, "w") as f:
        f.write(TOML_TEMPLATE.format(url=url, title=title, desc=desc))

    print(f"[{blog}] done")
