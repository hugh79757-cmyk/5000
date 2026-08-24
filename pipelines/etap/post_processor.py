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

        lines.append(f'{img_tag}<a href="{link}" rel="sponsored noopener" target="_blank">**{name}**</a>{discount_badge}\n\n')
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
        lines.append(f'<a href="{link}" rel="sponsored noopener" target="_blank">Book Now</a>\n\n---\n\n')

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
        table_lines.append(f'| <a href="{link}" rel="sponsored noopener" target="_blank">{name}</a> | {ps} | {discount_str} | <a href="{link}" rel="sponsored noopener" target="_blank">Book</a> |\n')

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
# 인라인 삽입 폐기: ADSENSE-GUIDE.md §5-1 / §8-4(auto) / §8-10(하드코딩 ID) / §10-2(비표준
# 슬롯 4276065235) 단일 표준 위반. 본문 광고는 테마 single.html의 H2 분할 파셜(adsense/*)
# 로만 주입되므로 인라인 블록은 제거. insert_adsense는 호환성 보존용 no-op.
def insert_adsense(content: str) -> str:
    """AdSense 본문 광고는 파셜(adsense/*) 단일 표준으로 위임. 인라인 삽입 폐기."""
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


# ============================================================
# PHASE 70 WAVE 1: EDITORIAL SYNTHESIS STEP
# ============================================================

def editorial_synthesis_step(content: str, source_data: dict) -> tuple[str, int]:
    """Phase 70 Wave 1: 템플릿 마커 치환 + 데이터 포인트 주입 (S03/S04 게이트 연동).
    
    GPT가 생성한 초안에서 {{...}} 형태의 템플릿 마커를 실제 데이터로 치환하고,
    검증 가능한 데이터 포인트를 본문에 명시적으로 주입한다.
    
    Args:
        content: GPT 생성 초안 (마크다운)
        source_data: 원본 소스 데이터 (prices, dates, names, metrics 등)
    
    Returns:
        (synthesized_content, injected_count): 치환된 본문과 주입된 데이터 포인트 수
    """
    if not content or not source_data:
        return content, 0
    
    injected_count = 0
    
    # 1. 템플릿 마커 치환 ({{key}} -> value)
    # 일반적인 마커 패턴들
    marker_patterns = {
        r"\{\{city\}\}": ["city", "origin_city", "destination_city", "dest_city"],
        r"\{\{origin\}\}": ["origin", "origin_code", "origin_city"],
        r"\{\{destination\}\}": ["destination", "dest_city", "destination_city"],
        r"\{\{price\}\}": ["price", "min_price", "max_price", "cost", "fare"],
        r"\{\{date\}\}": ["date", "departure_date", "return_date", "start_date"],
        r"\{\{airline\}\}": ["airline", "operator", "carrier", "seller"],
        r"\{\{tour_name\}\}": ["tour_name", "product_name", "name", "title"],
        r"\{\{discount\}\}": ["discount", "discount_percent", "savings"],
        r"\{\{rating\}\}": ["rating", "stars", "score"],
        r"\{\{duration\}\}": ["duration", "min_duration", "max_duration"],
        r"\{\{stops\}\}": ["stops", "min_stops", "layovers"],
    }
    
    for pattern, keys in marker_patterns.items():
        matches = list(re.finditer(pattern, content))
        if not matches:
            continue
        
        # source_data에서 첫 번째 매칭되는 값 찾기
        replacement = None
        for key in keys:
            # source_data 직접 검색
            if key in source_data and source_data[key]:
                val = source_data[key]
                if isinstance(val, (list, tuple)) and val:
                    # 리스트인 경우 첫 번째 유효한 항목 사용
                    for item in val:
                        if isinstance(item, dict):
                            for k in keys:
                                if k in item and item[k]:
                                    replacement = str(item[k])
                                    break
                        elif item:
                            replacement = str(item)
                            break
                        if replacement:
                            break
                elif isinstance(val, dict):
                    for k in keys:
                        if k in val and val[k]:
                            replacement = str(val[k])
                            break
                else:
                    replacement = str(val)
                break
            
            # 중첩 구조 검색 (예: flight_prices[0].price)
            for data_key, data_val in source_data.items():
                if isinstance(data_val, (list, tuple)):
                    for item in data_val:
                        if isinstance(item, dict) and key in item and item[key]:
                            replacement = str(item[key])
                            break
                    if replacement:
                        break
        
        if replacement:
            # 모든 매치 치환
            content = re.sub(pattern, replacement, content)
            injected_count += len(matches)
            logger.debug(f"[editorial] Replaced {len(matches)}x {{...}} with '{replacement}'")
    
    # 2. 데이터 포인트 명시적 주입 (S03 게이트 지원)
    # 본문에 없는 중요 데이터 포인트를 H2 섹션 끝에 주입
    
    # 가격 데이터 주입
    price_data = []
    for data_key, data_val in source_data.items():
        if isinstance(data_val, (list, tuple)):
            for item in data_val:
                if isinstance(item, dict):
                    for price_key in ["price", "min_price", "max_price", "cost", "fare"]:
                        if price_key in item and item[price_key] is not None:
                            try:
                                price_data.append(float(str(item[price_key]).replace("$", "").replace(",", "")))
                            except (ValueError, TypeError):
                                pass
    
    if price_data:
        min_price = min(price_data)
        max_price = max(price_data)
        # "Price Range:" 또는 "From $" 패턴이 없으면 주입
        if "price range" not in content.lower() and "from $" not in content.lower():
            # 첫 번째 H2 뒤에 가격 범위 문단 추가
            first_h2 = re.search(r"^## .+", content, re.MULTILINE)
            if first_h2:
                insert_pos = content.find("\n\n", first_h2.end())
                if insert_pos == -1:
                    insert_pos = first_h2.end()
                price_text = f"\n\nPrice range for this route: ${int(min_price):,}–${int(max_price):,}.\n"
                content = content[:insert_pos] + price_text + content[insert_pos:]
                injected_count += 1
    
    # 날짜 데이터 주입
    date_data = []
    for data_key, data_val in source_data.items():
        if isinstance(data_val, (list, tuple)):
            for item in data_val:
                if isinstance(item, dict):
                    for date_key in ["date", "departure_date", "return_date", "start_date", "end_date"]:
                        if date_key in item and item[date_key]:
                            date_data.append(str(item[date_key]))
    
    if date_data:
        # 첫 번째 유효한 날짜 사용
        first_date = date_data[0]
        if "depart" not in content.lower() and "travel date" not in content.lower():
            first_h2 = re.search(r"^## .+", content, re.MULTILINE)
            if first_h2:
                insert_pos = content.find("\n\n", first_h2.end())
                if insert_pos == -1:
                    insert_pos = first_h2.end()
                date_text = f"\n\nTravel dates available from {first_date}.\n"
                content = content[:insert_pos] + date_text + content[insert_pos:]
                injected_count += 1
    
    # 항공사/운영사 데이터 주입
    airline_data = set()
    for data_key, data_val in source_data.items():
        if isinstance(data_val, (list, tuple)):
            for item in data_val:
                if isinstance(item, dict):
                    for airline_key in ["airline", "operator", "carrier", "seller", "provider"]:
                        if airline_key in item and item[airline_key]:
                            airline_data.add(str(item[airline_key]))
    
    if airline_data:
        airlines = ", ".join(sorted(airline_data)[:5])  # 최대 5개
        if "airline" not in content.lower() and "operated by" not in content.lower():
            first_h2 = re.search(r"^## .+", content, re.MULTILINE)
            if first_h2:
                insert_pos = content.find("\n\n", first_h2.end())
                if insert_pos == -1:
                    insert_pos = first_h2.end()
                airline_text = f"\n\nOperated by: {airlines}.\n"
                content = content[:insert_pos] + airline_text + content[insert_pos:]
                injected_count += 1
    
    return content, injected_count


def count_verifiable_data_points(content: str, source_data: dict) -> int:
    """S03 게이트 지원: 본문 내 검증 가능한 데이터 포인트 수 계산.
    
    editorial_synthesis_step으로 주입된 포인트 포함하여 계산.
    quality_guard.unique_data_points_gate와 로직 공유.
    """
    if not source_data:
        return 0
    
    # quality_guard의 unique_data_points_gate 로직 재사용
    try:
        from pipelines.etap.quality_guard import unique_data_points_gate
        _, count, _ = unique_data_points_gate(content, source_data, threshold=0)
        return count
    except ImportError:
        pass
    
    # 폴백: 간단한 카운트
    count = 0
    content_lower = content.lower()

    # 가격
    for data_key, data_val in source_data.items():
        if isinstance(data_val, (list, tuple)):
            for item in data_val:
                if isinstance(item, dict):
                    for price_key in ["price", "min_price", "max_price"]:
                        if price_key in item and item[price_key]:
                            val = str(item[price_key]).replace("$", "").replace(",", "")
                            if val in content:
                                count += 1

    return count


# ============================================================
# PHASE 70 WAVE 2: EDITORIAL SYNTHESIS LAYER (canonical)
# ============================================================
# Canonical synthesis lives in editorial_synthesis.py with the plan signature
# (content, unique_data, topic) -> str. Imported here (aliased to avoid
# shadowing the Wave 1 editorial_synthesis_step above, which tests depend on).
from pipelines.etap.editorial_synthesis import editorial_synthesis_step as _editorial_synthesis_assemble
from pipelines.etap.data_adapters import get_unique_data_points, ADAPTER_REGISTRY


def apply_editorial_synthesis(content: str, topic: dict = None, topic_type: str = None, topic_id=None) -> str:
    """Phase 70 Wave 2: resolve data points for a topic, synthesize an editorial
    paragraph, and append it to the end of the content.

    Wrapped in try/except: on any failure it logs a warning and returns the
    untouched content (graceful degradation). Returns content unchanged when the
    synthesized paragraph is empty.
    """
    try:
        ttype = topic_type or (topic or {}).get("topic_type") or (topic or {}).get("type")
        if not ttype or ttype not in ADAPTER_REGISTRY:
            return content
        unique_data = get_unique_data_points(ttype, topic_id)
        paragraph = _editorial_synthesis_assemble(content, unique_data, topic or {})
        if not paragraph:
            return content
        return content.rstrip() + "\n\n" + paragraph + "\n"
    except Exception as exc:
        logger.warning("[editorial] synthesis skipped: %s", exc)
        return content
