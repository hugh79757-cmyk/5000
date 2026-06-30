"""Airalo eSIM feed collector – parses local XML or remote feed."""
import logging
import os
import sqlite3
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

# 로컬 XML 파일 경로 (이메일로 받은 파일)
LOCAL_XML = os.path.join(BASE_DIR, "data", "Airalo-Product-Catalog_GOOGLE (1).xml")

def _get_db():
    return sqlite3.connect(DB_PATH)

def _parse_value(item, tag, ns):
    """XML 네임스페이스 태그에서 텍스트 추출"""
    el = item.find(tag, ns)
    return el.text.strip() if el is not None and el.text else ""

def _parse_price(val):
    """문자열에서 숫자 추출"""
    if not val:
        return None
    try:
        return float(val.replace(",", "").replace("USD", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None

def collect_from_xml(xml_path=None):
    """로컬 XML 파일에서 Airalo eSIM 데이터 수집"""
    path = xml_path or LOCAL_XML
    if not os.path.exists(path):
        logger.error(f"[Airalo] XML 파일 없음: {path}")
        return 0

    tree = ET.parse(path)
    root = tree.getroot()

    # 네임스페이스 감지
    ns = {}
    if root.tag.startswith("{"):
        default_ns = root.tag.split("}")[0] + "}"
        ns["atom"] = default_ns.strip("{}")
    # Google Shopping 네임스페이스
    ns["g"] = "http://base.google.com/ns/1.0"

    db = _get_db()
    count = 0

    # RSS/Atom 형식 모두 시도
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if not items:
        # channel/item 구조
        channel = root.find("channel")
        if channel is not None:
            items = channel.findall("item")

    for item in items:
        try:
            # RSS item 형식
            product_id = _parse_value(item, "g:id", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}id", ns)
            title = _parse_value(item, "g:title", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}title", ns) or _parse_value(item, "title", ns)
            link = _parse_value(item, "g:link", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}link", ns) or _parse_value(item, "link", ns)
            description = _parse_value(item, "g:description", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}description", ns) or _parse_value(item, "description", ns)
            image_link = _parse_value(item, "g:image_link", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}image_link", ns)
            price_str = _parse_value(item, "g:price", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}price", ns)
            sale_price_str = _parse_value(item, "g:sale_price", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}sale_price", ns)
            brand = _parse_value(item, "g:brand", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}brand", ns)
            condition = _parse_value(item, "g:condition", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}condition", ns)
            availability = _parse_value(item, "g:availability", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}availability", ns)
            product_type = _parse_value(item, "g:product_type", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}product_type", ns)
            mpn = _parse_value(item, "g:mpn", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}mpn", ns)
            is_bundle = _parse_value(item, "g:is_bundle", ns) or _parse_value(item, "{http://base.google.com/ns/1.0}is_bundle", ns)

            if not product_id and not title:
                continue

            price = _parse_price(price_str)
            sale_price = _parse_price(sale_price_str)

            db.execute("""
                INSERT OR REPLACE INTO airalo_esim
                (product_id, title, link, description, image_link, price, sale_price,
                 brand, condition, availability, product_type, mpn, is_bundle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, title, link, description, image_link, price, sale_price,
                  brand, condition, availability, product_type, mpn, is_bundle))
            count += 1
        except Exception as e:
            logger.warning(f"[Airalo] item 파싱 오류: {e}")
            continue

    db.commit()
    db.close()
    logger.info(f"[Airalo] XML에서 {count}건 수집 완료")
    return count

def run_full_collection():
    """전체 수집 실행"""
    return collect_from_xml()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    total = run_full_collection()
    print(f"Airalo eSIM: {total}건")
