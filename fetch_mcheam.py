import requests
import os
import re
from html.parser import HTMLParser

BASE_URL   = "https://mcheam.com/wp-json/wp/v2/posts"
OUTPUT_DIR = "mcheam_posts"
PER_PAGE   = 100

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

def fetch_posts(page):
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "_fields": "id,date,title,content,link"
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
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

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    page  = 1
    total = 0

    print(f"📥 수집 시작 → 저장 폴더: {OUTPUT_DIR}")
    print("─" * 50)

    while True:
        print(f"🔄 {page}페이지 요청 중...", end=" ")
        posts = fetch_posts(page)

        if not posts:
            print("완료!")
            break

        for post in posts:
            filepath = save_post(post, OUTPUT_DIR)
            print(f"  ✅ [{post['id']}] {post['title']['rendered']}")
            total += 1

        page += 1

    print("─" * 50)
    print(f"🎉 총 {total}개 포스트 저장 완료! → ./{OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
