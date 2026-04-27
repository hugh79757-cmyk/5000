import requests
import os
import re
from html.parser import HTMLParser

PER_PAGE = 100
MAX_PAGES = 7

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fed = []
        self.skip_tags = {"script", "style"}
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self._skip = True
        if tag in {"p","br","h1","h2","h3","h4","h5","h6","li","div","tr","blockquote"}:
            self.fed.append("\n")
        if tag in {"h1","h2","h3","h4","h5","h6"}:
            self.fed.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self._skip = False
        if tag in {"p","h1","h2","h3","h4","h5","h6","li","div","tr","blockquote"}:
            self.fed.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.fed.append(data)

    def get_text(self):
        return "".join(self.fed)

def html_to_text(html):
    s = HTMLStripper()
    s.feed(html)
    text = s.get_text()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def safe_filename(title, post_id):
    name = re.sub(r'[\\/*?:"<>|]', "", title)
    name = name.strip().replace(" ", "_")[:80]
    return f"{post_id}_{name}.md"

def fetch_posts(base_url, page):
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "_fields": "id,date,title,content,link"
    }
    resp = requests.get(base_url, params=params, timeout=30)
    if resp.status_code == 400:
        return []
    resp.raise_for_status()
    return resp.json()

def save_post(post, folder):
    post_id = post["id"]
    title   = post["title"]["rendered"]
    body    = html_to_text(post["content"]["rendered"])
    date    = post.get("date", "")[:10]
    link    = post.get("link", "")

    md = (
        f"---\n"
        f"id: {post_id}\n"
        f"title: \"{title}\"\n"
        f"date: {date}\n"
        f"source: {link}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n"
    )

    filepath = os.path.join(folder, safe_filename(title, post_id))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    return filepath

def is_wordpress(site_url):
    """워드프레스 REST API 사용 가능 여부 확인"""
    try:
        api_url = site_url.rstrip("/") + "/wp-json/wp/v2/posts"
        resp = requests.get(api_url, params={"per_page": 1}, timeout=10)
        return resp.status_code == 200, api_url
    except Exception as e:
        return False, None

def main():
    print("=" * 50)
    print("  🌐 WordPress 포스트 수집기")
    print("=" * 50)

    # 사이트 URL 입력
    site_url = input("\n📌 워드프레스 사이트 주소를 입력하세요 (예: https://example.com): ").strip()

    if not site_url.startswith("http"):
        site_url = "https://" + site_url

    print(f"\n🔍 {site_url} 확인 중...")
    is_wp, base_url = is_wordpress(site_url)

    if not is_wp:
        print("❌ 워드프레스 REST API에 접근할 수 없습니다.")
        print("   - 워드프레스 사이트가 맞는지 확인해주세요.")
        return

    print(f"✅ 워드프레스 확인 완료!")

    # 저장 폴더명 = 도메인명 자동 추출
    domain = re.sub(r'https?://', '', site_url).rstrip('/').replace('.', '_')
    output_dir = domain + "_posts"

    # 최대 페이지 수 입력
    print(f"\n📄 최대 몇 페이지까지 수집할까요? (기본값: {MAX_PAGES}, 1페이지 = 최대 100개 포스트)")
    page_input = input(f"   페이지 수 입력 (엔터 시 {MAX_PAGES}페이지): ").strip()
    max_pages = int(page_input) if page_input.isdigit() else MAX_PAGES

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n📥 수집 시작 → 저장 폴더: ./{output_dir}/")
    print("─" * 50)

    page  = 1
    total = 0

    while page <= max_pages:
        print(f"🔄 {page}페이지 요청 중...", end=" ")
        posts = fetch_posts(base_url, page)

        if not posts:
            print("완료!")
            break

        for post in posts:
            save_post(post, output_dir)
            print(f"  ✅ [{post['id']}] {post['title']['rendered']}")
            total += 1

        page += 1

    print("─" * 50)
    print(f"🎉 총 {total}개 포스트 저장 완료! → ./{output_dir}/")
    print(f"\n📂 폴더 바로 열기:")
    print(f"   open {output_dir}")

if __name__ == "__main__":
    main()
