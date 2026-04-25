"""ETAP 이미지 수집 - Pexels (primary) + Unsplash (fallback) + 관련성 필터 + 중복 방지"""
import os, logging, sqlite3, requests, re

logger = logging.getLogger(__name__)

R2_BASE = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")


def _get_db():
    return sqlite3.connect(DB_PATH)


def _init_used_images_table():
    db = _get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS used_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_url TEXT UNIQUE,
        photographer TEXT,
        source TEXT,
        slug TEXT,
        usage_type TEXT,
        used_at TEXT DEFAULT (datetime('now'))
    )""")
    db.commit()
    db.close()


def _is_image_used(image_url):
    db = _get_db()
    row = db.execute("SELECT 1 FROM used_images WHERE image_url = ?", (image_url,)).fetchone()
    db.close()
    return row is not None


def _mark_image_used(image_url, photographer, source, slug, usage_type):
    db = _get_db()
    try:
        db.execute(
            "INSERT OR IGNORE INTO used_images (image_url, photographer, source, slug, usage_type) VALUES (?, ?, ?, ?, ?)",
            (image_url, photographer, source, slug, usage_type)
        )
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


_init_used_images_table()


def _is_relevant(photo, city, country):
    """Pexels alt 텍스트 또는 URL에 도시명/국가명이 포함되어 있는지 확인"""
    alt = (photo.get("alt") or "").lower()
    url = (photo.get("url") or "").lower()
    text = alt + " " + url

    # 도시명과 국가명으로 키워드 생성
    keywords = []
    if city:
        # "New York" -> ["new york", "new", "york"]
        city_lower = city.lower()
        keywords.append(city_lower)
        # 단어가 2개 이상이면 개별 단어도 확인 (단, 3글자 이상만)
        for w in city_lower.split():
            if len(w) >= 4:
                keywords.append(w)
    if country:
        country_lower = country.lower()
        keywords.append(country_lower)
        for w in country_lower.split():
            if len(w) >= 4:
                keywords.append(w)

    # 키워드 중 하나라도 매칭되면 관련 있음
    for kw in keywords:
        if kw in text:
            return True
    return False


def _search_pexels(query, per_page=15, city="", country=""):
    """Pexels 검색 + 관련성 필터링. per_page를 넉넉히 요청해서 필터 후에도 결과 확보."""
    key = os.getenv("PEXELS_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get("https://api.pexels.com/v1/search", params={
            "query": query, "per_page": per_page, "orientation": "landscape", "size": "large"
        }, headers={"Authorization": key}, timeout=10)
        if r.status_code != 200:
            logger.warning("[Pexels] %s: %s", r.status_code, query)
            return []
        results = []
        for p in r.json().get("photos", []):
            photo_data = {
                "url": p["src"]["landscape"],
                "thumb": p["src"]["medium"],
                "credit": "Photo by [%s](%s) on [Pexels](https://www.pexels.com)" % (p["photographer"], p["photographer_url"]),
                "photographer": p["photographer"],
                "download_location": None,
                "source": "pexels",
                "alt": p.get("alt", ""),
            }
            # 관련성 필터: city/country가 주어졌으면 alt에 포함된 것만
            if city or country:
                if _is_relevant(photo_data, city, country):
                    results.append(photo_data)
                else:
                    logger.debug("[Pexels] 관련성 없음, 스킵: %s", (p.get("alt", ""))[:60])
            else:
                results.append(photo_data)
        return results
    except Exception as e:
        logger.warning("[Pexels] error: %s", e)
        return []


def _search_unsplash(query, per_page=15, city="", country=""):
    key = os.getenv("UNSPLASH_ACCESS_KEY", "")
    if not key:
        return []
    try:
        r = requests.get("https://api.unsplash.com/search/photos", params={
            "query": query, "per_page": per_page, "orientation": "landscape"
        }, headers={"Authorization": "Client-ID %s" % key}, timeout=10)
        if r.status_code != 200:
            logger.warning("[Unsplash] %s: %s", r.status_code, query)
            return []
        results = []
        for p in r.json().get("results", []):
            photo_data = {
                "url": p["urls"]["regular"],
                "thumb": p["urls"]["thumb"],
                "credit": "Photo by [%s](%s) on [Unsplash](https://unsplash.com)" % (p["user"]["name"], p["user"]["links"]["html"]),
                "photographer": p["user"]["name"],
                "download_location": p["links"]["download_location"],
                "source": "unsplash",
                "alt": p.get("alt_description") or p.get("description") or "",
            }
            if city or country:
                if _is_relevant(photo_data, city, country):
                    results.append(photo_data)
            else:
                results.append(photo_data)
        return results
    except Exception as e:
        logger.warning("[Unsplash] error: %s", e)
        return []


def _search_with_fallback(query, per_page=15, city="", country=""):
    results = _search_pexels(query, per_page, city, country)
    if results:
        return results
    return _search_unsplash(query, per_page, city, country)


def _upload_to_r2(r2_key, image_url, force=False):
    from shared.r2_uploader import file_exists, upload_bytes
    if not force and file_exists(r2_key):
        return "%s/%s" % (R2_BASE, r2_key)
    img_data = requests.get(image_url, timeout=15).content
    upload_bytes(img_data, r2_key, content_type="image/jpeg")
    r2_url = "%s/%s" % (R2_BASE, r2_key)
    logger.info("R2 upload: %s", r2_url)
    return r2_url


def _trigger_unsplash_download(photo):
    if photo.get("source") == "unsplash" and photo.get("download_location"):
        try:
            key = os.getenv("UNSPLASH_ACCESS_KEY", "")
            requests.get(photo["download_location"], headers={"Authorization": "Client-ID %s" % key}, timeout=5)
        except Exception:
            pass


def fetch_city_image(city, country, slug, force=False):
    """커버 이미지 검색. 도시+국가명 관련성 필터 적용."""
    # 여러 쿼리 패턴 시도 (구체적 → 일반적)
    queries = [
        "%s %s city" % (city, country) if country else "%s city" % city,
        "%s skyline" % city,
        "%s travel" % city,
    ]

    for query in queries:
        results = _search_with_fallback(query, per_page=15, city=city, country=country)
        if not results:
            continue
        for photo in results:
            if not force and _is_image_used(photo["url"]):
                continue
            r2_key = "etap/%s/cover.jpg" % slug
            try:
                r2_url = _upload_to_r2(r2_key, photo["url"], force=force)
                _trigger_unsplash_download(photo)
                _mark_image_used(photo["url"], photo["photographer"], photo["source"], slug, "cover")
                logger.info("[ETAP] cover: %s (%s)", r2_url, photo["photographer"])
                return {"url": r2_url, "credit": photo["credit"]}
            except Exception as e:
                logger.error("[Image] cover upload error: %s", e)
                continue

    # 관련성 필터로 모두 탈락한 경우, 필터 없이 재시도 (이미지 없는 것보다는 나음)
    logger.warning("[Image] No relevant cover for %s, trying without filter", slug)
    fallback_query = "%s travel" % city
    results = _search_with_fallback(fallback_query, per_page=5, city="", country="")
    for photo in results:
        if _is_image_used(photo["url"]):
            continue
        r2_key = "etap/%s/cover.jpg" % slug
        try:
            r2_url = _upload_to_r2(r2_key, photo["url"], force=force)
            _trigger_unsplash_download(photo)
            _mark_image_used(photo["url"], photo["photographer"], photo["source"], slug, "cover")
            return {"url": r2_url, "credit": photo["credit"]}
        except Exception:
            continue

    logger.warning("[Image] No cover image at all for %s", slug)
    return None


def fetch_body_images(city, country, slug, count=3, force=False):
    """본문 이미지. 관련성 필터 적용, 다양한 쿼리."""
    queries = [
        "%s %s skyline cityscape" % (city, country) if country else "%s skyline" % city,
        "%s %s street food market" % (city, country) if country else "%s food" % city,
        "%s %s famous landmark" % (city, country) if country else "%s landmark" % city,
        "%s %s nature scenery" % (city, country) if country else "%s scenery" % city,
        "%s %s culture people" % (city, country) if country else "%s culture" % city,
    ]
    collected = []

    for q in queries:
        if len(collected) >= count:
            break
        results = _search_with_fallback(q, per_page=15, city=city, country=country)
        for photo in results:
            if len(collected) >= count:
                break
            if not force and _is_image_used(photo["url"]):
                continue
            r2_key = "etap/%s/body_%d.jpg" % (slug, len(collected) + 1)
            try:
                r2_url = _upload_to_r2(r2_key, photo["url"], force=force)
                _trigger_unsplash_download(photo)
                _mark_image_used(photo["url"], photo["photographer"], photo["source"], slug, "body")
                collected.append({"url": r2_url, "credit": photo["credit"]})
            except Exception as e:
                logger.warning("[Image] body upload error: %s", e)
                continue

    logger.info("[Image] %s body images: %d", slug, len(collected))
    return collected
