"""ETAP post_processor — 글 본문에 상품 카드, 비교 테이블, 크로스셀 블록 삽입"""

import logging
import re

logger = logging.getLogger(__name__)


def insert_product_cards(content: str, products: list, max_cards: int = 5) -> str:
    """본문 하단(마지막 H2 앞 또는 끝)에 Viator 상품 카드 HTML 삽입.

    Args:
        content: 마크다운 본문
        products: list of dict (name, price, currency, discount, image_url, link, category)
        max_cards: 최대 카드 수
    Returns:
        상품 카드가 삽입된 본문

    """
    if not products:
        return content

    cards = products[:max_cards]
    lines = ['\n\n<div class="etap-product-cards">\n']
    lines.append('<h2 class="etap-card-title">Top Tours &amp; Activities</h2>\n\n')

    for p in cards:
        name = p.get("name", "")
        # "Save XX%! " 접두사 제거
        import re as _re
        name = _re.sub(r"^Save [\d.]+%!\s*", "", name)
        price = p.get("price", "")
        currency = p.get("currency", "USD")
        discount = p.get("discount", "")
        image_url = p.get("image_url", "")
        link = p.get("link", "#")
        category = p.get("category", "")

        discount_badge = ""
        if discount and str(discount) not in ("0", ""):
            try:
                disc_val = abs(float(str(discount).replace("%","").replace("-","")))
                discount_badge = f' <span class="badge">-{round(disc_val)}%</span>'
            except (ValueError, TypeError):
                discount_badge = f' <span class="badge">-{discount}%</span>'

        img_tag = ""
        if image_url:
            img_tag = f"[![{name}]({image_url})]({link})\n\n"

        lines.append(f"{img_tag}**[{name}]({link})**{discount_badge}\n\n")
        if category:
            lines.append(f"_{category}_\n\n")
        if price:
            try:
                pv = float(str(price).replace("$","").replace(",",""))
                ps = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
            except (ValueError, TypeError):
                ps = f"{currency} {price}"
            # Normalize to $integer
            try:
                _pv = float(str(ps).replace("$","").replace(",","").replace("USD","").replace("GBP","").replace("EUR","").strip())
                ps = f"${round(_pv)}"
            except (ValueError, TypeError):
                pass
            lines.append(f"From **{ps}**\n\n")
        lines.append(f"[Book Now]({link})\n\n---\n\n")

    lines.append("</div>\n")
    card_block = "".join(lines)

    # 삽입 위치: 마지막 H2 "Travel Tips" 앞, 없으면 본문 끝
    # 이미 카드 블록이 있으면 중복 삽입 방지
    cards_pos = content.find('<div class="etap-product-cards">')
    if cards_pos > 0:
        return content

    tips_match = re.search(r"^## (?:Travel Tips|Budget Breakdown|Getting Around)", content, re.MULTILINE)
    if tips_match:
        pos = tips_match.start()
        return content[:pos] + card_block + "\n" + content[pos:]
    return content + card_block


def insert_comparison_table(content: str, products: list, max_rows: int = 5) -> str:
    """상품 비교 마크다운 테이블을 본문에 삽입.

    Args:
        content: 마크다운 본문
        products: list of dict (name, price, currency, discount, link)
        max_rows: 최대 행 수
    Returns:
        비교 테이블이 삽입된 본문

    """
    if not products:
        return content

    rows = products[:max_rows]
    table_lines = ["\n\n| Tour | Price | Discount | Book |\n"]
    table_lines.append("|------|-------|----------|------|\n")

    for p in rows:
        name = p.get("name", "")
        price = p.get("price", "")
        currency = p.get("currency", "USD")
        discount = p.get("discount", "")
        link = p.get("link", "#")

        if discount and str(discount) not in ("0", ""):
            try:
                disc_val = abs(float(str(discount).replace("%","").replace("-","")))
                discount_str = f"-{round(disc_val)}%"
            except (ValueError, TypeError):
                discount_str = f"-{discount}%"
        else:
            discount_str = "-"
        try:
            pv = float(str(price).replace("$","").replace(",",""))
            ps = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
        except (ValueError, TypeError):
            ps = f"{currency} {price}"
            try:
                _pv2 = float(str(ps).replace("$","").replace(",","").replace("USD","").replace("GBP","").replace("EUR","").strip())
                ps = f"${round(_pv2)}"
            except (ValueError, TypeError):
                pass
        table_lines.append(f"| [{name}]({link}) | {ps} | {discount_str} | [Book]({link}) |\n")

    table_lines.append("\n")
    table_block = "".join(table_lines)

    # 삽입 위치: "Top Things to Do" H2 뒤, 없으면 두 번째 H2 뒤
    h2_matches = list(re.finditer(r"^## .+", content, re.MULTILINE))
    target = None
    for m in h2_matches:
        if "things to do" in m.group().lower() or "top tours" in m.group().lower():
            target = m
            break
    if not target and len(h2_matches) >= 2:
        target = h2_matches[1]

    if target:
        insert_pos = content.find("\n", target.end())
        if insert_pos == -1:
            insert_pos = target.end()
        return content[:insert_pos] + table_block + content[insert_pos:]
    return content + table_block


def insert_cross_sell_block(content: str, cross_html: str, position: str = "top") -> str:
    """크로스셀 링크 블록을 본문에 삽입.

    Args:
        content: 마크다운 본문
        cross_html: 삽입할 크로스셀 HTML/마크다운 블록
        position: "top" (첫 H2 뒤) 또는 "bottom" (본문 끝)

    Returns:
        크로스셀 블록이 삽입된 본문

    """
    if not cross_html:
        return content

    block = f"\n\n{cross_html}\n\n"

    if position == "top":
        # 첫 번째 H2의 첫 번째 문단 뒤에 삽입
        first_h2 = re.search(r"^## .+", content, re.MULTILINE)
        if first_h2:
            # H2 다음의 빈 줄 이후 첫 문단 끝 찾기
            after_h2 = first_h2.end()
            next_double_newline = content.find("\n\n", after_h2)
            if next_double_newline != -1:
                # 첫 문단 끝 뒤에 삽입
                second_para_end = content.find("\n\n", next_double_newline + 2)
                if second_para_end != -1:
                    return content[:second_para_end] + block + content[second_para_end:]
            return content[:after_h2] + block + content[after_h2:]
        return block + content
    return content + block


# ── AdSense 본문 광고 삽입 ──
ADSENSE_BLOCK = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8772455780561463"
     crossorigin="anonymous"></script>
<!-- ETAP -->
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-8772455780561463"
     data-ad-slot="4276065235"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({});
</script>"""

def insert_adsense(content: str) -> str:
    """첫 번째 단락 하단과 두 번째 H2 아래에 AdSense 광고 블록을 삽입합니다."""
    import re as _re
    if "<!-- ETAP -->" in content:
        return content

    # 광고 위치 1: 첫 번째 빈 줄(단락 구분) 뒤
    first_para = _re.search(r"\n\n", content)
    if first_para:
        pos1 = first_para.end()
        content = content[:pos1] + "\n" + ADSENSE_BLOCK + "\n\n" + content[pos1:]

    # 광고 위치 2: 두 번째 H2 아래
    h2_list = [m.start() for m in _re.finditer(r"^## ", content, _re.MULTILINE)]
    if len(h2_list) >= 2:
        h2_start = h2_list[1]
        h2_end = content.index("\n", h2_start)
        pos2 = h2_end + 1
        content = content[:pos2] + "\n" + ADSENSE_BLOCK + "\n\n" + content[pos2:]

    return content



# === ETAP v2 후처리 함수 ===

def fix_encoding(text: str) -> str:
    """GPT 출력의 인코딩 문제 수정"""
    if not text:
        return text
    import re as _re
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "–").replace("—", "—")
    text = text.replace("…", "...").replace(" ", " ")
    contractions = {
        "youre": "you're", "youll": "you'll", "youve": "you've", "youd": "you'd",
        "theyre": "they're", "theyll": "they'll", "theyve": "they've", "theyd": "they'd",
        "weve": "we've", "wed": "we'd",
        "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't", "werent": "weren't",
        "dont": "don't", "doesnt": "doesn't", "didnt": "didn't",
        "cant": "can't", "couldnt": "couldn't", "wouldnt": "wouldn't",
        "shouldnt": "shouldn't", "wont": "won't",
        "hasnt": "hasn't", "havent": "haven't", "hadnt": "hadn't",
        "thats": "that's", "whats": "what's", "heres": "here's",
        "theres": "there's", "lets": "let's",
        "hes": "he's", "shes": "she's", "whos": "who's",
    }
    for wrong, right in contractions.items():
        text = _re.sub(r"\b" + wrong + r"\b", right, text, flags=_re.IGNORECASE)
    return _re.sub(
        r"\bits (a |an |the |not |also |worth|important|essential|advisable|best|easy|hard|possible|clear|no )",
        r"it's \1", text, flags=_re.IGNORECASE
    )


def clean_tags(tags: list) -> list:
    """태그에서 마크다운/프롬프트 잔재 제거"""
    if not tags:
        return tags
    import re as _re
    bad = [r"^H[1-6]$", r"^##", r"^\*\*", r"^Title:", r"^Slug:", r"^Tags:", r"^Category:"]
    cleaned = []
    for tag in tags:
        tag = str(tag).strip().replace("#", "").replace("*", "").strip()
        if not tag or len(tag) < 2:
            continue
        if any(_re.match(p, tag, _re.IGNORECASE) for p in bad):
            continue
        cleaned.append(tag)
    return cleaned


def clean_prompt_leaks(content: str) -> str:
    """GPT 출력에서 프롬프트 지시문 잔재 제거"""
    if not content:
        return content
    import re as _re
    patterns = [
        r"\[Note:.*?\]",
        r"\[Instructions?:.*?\]",
        r"\(Note to (?:self|AI|assistant):.*?\)",
    ]
    for p in patterns:
        content = _re.sub(p, "", content, flags=_re.IGNORECASE)
    return content.strip()
