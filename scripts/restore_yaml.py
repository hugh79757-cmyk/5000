#!/usr/bin/env python3
"""config/_default/ 제거, hugo.yaml 복원"""
import os, shutil

CUAP = "/Users/twinssn/Projects/CUAP"

blogs = {
    "baby-hugo": ("https://baby.informationhot.kr/", "유아용품 추천 가이드"),
    "fitness-hugo": ("https://fitness.informationhot.kr/", "운동용품 추천 가이드"),
    "appliance-hugo": ("https://appliance.informationhot.kr/", "가전제품 추천 가이드"),
    "interior-hugo": ("https://interior.informationhot.kr/", "가구 인테리어 추천 가이드"),
    "laptop-hugo": ("https://laptop.informationhot.kr/", "노트북 추천 가이드"),
}

YAML_TEMPLATE = """baseURL: "{url}"
languageCode: "ko"
title: "{title}"
theme: "blowfish"
defaultContentLanguage: "ko"
enableRobotsTXT: true
pagination:
  pagerSize: 12
summaryLength: 150

taxonomies:
  tag: "tags"
  category: "categories"

params:
  colorScheme: "ocean"
  defaultAppearance: "dark"
  autoSwitchAppearance: false
  header:
    layout: "basic"
    showTitle: true
  footer:
    showCopyright: true
    showThemeAttribution: false
    showScrollToTop: true
  homepage:
    layout: "profile"
    showRecent: true
    showRecentItems: 12
  article:
    showAuthor: false
    showDate: true
    showReadingTime: false
    showTableOfContents: true
    showBreadcrumbs: true

markup:
  goldmark:
    renderer:
      unsafe: true

deploy:
  branch: main
  commit_dirty: true
  method: wrangler
"""

for blog, (url, title) in blogs.items():
    blog_dir = os.path.join(CUAP, blog)

    # config/_default/ 삭제
    config_dir = os.path.join(blog_dir, "config")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        print(f"[{blog}] config/ 삭제")

    # hugo.yaml 복원
    yaml_path = os.path.join(blog_dir, "hugo.yaml")
    with open(yaml_path, "w") as f:
        f.write(YAML_TEMPLATE.format(url=url, title=title))
    print(f"[{blog}] hugo.yaml 복원")

print("\n복원 완료")
