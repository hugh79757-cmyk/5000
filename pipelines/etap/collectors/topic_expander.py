"""
토픽 자동 확장기 — 매일 실행
각 블로그의 토픽 테이블이 MIN_THRESHOLD 미만이면 Viator 데이터에서 자동 보충
"""
import sqlite3, re, logging, os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "travel-en.db"
MIN_THRESHOLD = 30   # 이 이하면 자동 확장
MIN_TOURS = 1        # 도시당 최소 투어 수

# 블로그별 Viator 카테고리 매핑
BLOG_CATEGORIES = {
    "adventure": {
        "cats": ('Adventure Tours', 'Outdoor Activities', 'Zipline', 'Bungee Jumping',
                 'Climbing', 'Canyoning', 'Abseiling'),
        "label": "Adventure Tours"
    },
    "airlines": {
        "cats": ('Airport & Hotel Transfers', 'Airport Lounges'),
        "label": "Airlines Guide"
    },
    "airports": {
        "cats": ('Airport & Hotel Transfers', 'Airport Lounges'),
        "label": "Airport Guide"
    },
    "bus": {
        "cats": ('Bus Tours', 'Hop-On Hop-Off', 'Trolley Tours'),
        "label": "Bus Tours"
    },
    "citytours": {
        "cats": ('City Tours', 'Sightseeing Tours', 'Cultural Tours', 'Historical Tours'),
        "label": "City Tours"
    },
    "cruise": {
        "cats": ('Cruises', 'Sailing', 'Boat Tours', 'Dinner Cruises',
                 'Speed Boats', 'Yacht Tours'),
        "label": "Cruise Tours"
    },
    "culture": {
        "cats": ('Cultural Tours', 'Historical Tours', 'Archaeology Tours',
                 'Museum Tours', 'Art Tours', 'Religious Tours'),
        "label": "Cultural Tours"
    },
    "daytrips": {
        "cats": ('Day Trips', 'Full-day Tours', 'Half-day Tours', 'Excursions'),
        "label": "Day Trips"
    },
    "deals": {
        "cats": ('Skip the Line', 'Attraction Tickets', 'City Cards', 'Discount Passes'),
        "label": "Deals"
    },
    "dining": {
        "cats": ('Dining Experiences', 'Dinner Cruises', 'Dinner Shows',
                 'Supper Clubs', 'Lunch Tours'),
        "label": "Dining"
    },
    "escape": {
        "cats": ('Escape Games', 'Scavenger Hunts', 'Treasure Hunts',
                 'Mystery Games', 'Interactive Tours'),
        "label": "Escape Games"
    },
    "eurail": {
        "cats": ('Rail Tours', 'Train Tours', 'Scenic Railroads'),
        "label": "Rail Tours"
    },
    "extreme": {
        "cats": ('Extreme Sports', 'Skydiving', 'Bungee Jumping', 'Paragliding',
                 'Hang Gliding', 'Zipline', 'Jet Skiing'),
        "label": "Extreme Sports"
    },
    "ferry": {
        "cats": ('Ferry', 'Boat Tours', 'Water Taxis', 'Speedboat Tours'),
        "label": "Ferry Tours"
    },
    "foodtour": {
        "cats": ('Street Food Tours', 'Cooking Classes', 'Dining Experiences',
                 'Coffee & Tea Tours', 'Wine Tastings', 'Pub Tours', 'High Tea',
                 'Sake Tasting', 'Beer & Brewery Tours', 'Food Tours',
                 'Market Tours', 'Chocolate Tours'),
        "label": "Food Tours"
    },
    "ghost": {
        "cats": ('Ghost Tours', 'Haunted Tours', 'Dark Tourism',
                 'Mystery Tours', 'Paranormal Tours'),
        "label": "Ghost Tours"
    },
    "hiking": {
        "cats": ('Hiking', 'Trekking', 'Nature Walks', 'Mountain Tours',
                 'Trail Running', 'Walking Tours'),
        "label": "Hiking Tours"
    },
    "layover": {
        "cats": ('Layover Tours', 'Airport Tours', 'Short Tours',
                 'Half-day Tours', 'City Tours'),
        "label": "Layover Tours"
    },
    "luxury": {
        "cats": ('Luxury Tours', 'Private Tours', 'VIP Tours',
                 'Helicopter Tours', 'Yacht Tours', 'Limousine Tours'),
        "label": "Luxury Tours"
    },
    "michelin": {
        "cats": ('Dining Experiences', 'Food Tours', 'Gourmet Tours'),
        "label": "Michelin Dining"
    },
    "multiday": {
        "cats": ('Multi-day Tours', 'Package Tours', 'Guided Tours',
                 'Road Trips', 'Overland Tours'),
        "label": "Multi-day Tours"
    },
    "nature": {
        "cats": ('Nature Tours', 'Wildlife Tours', 'Eco Tours', 'National Parks',
                 'Bird Watching', 'Garden Tours', 'Safari'),
        "label": "Nature Tours"
    },
    "nightlife": {
        "cats": ('Nightlife', 'Bar Tours', 'Pub Crawls', 'Club Tours',
                 'Night Tours', 'Evening Tours'),
        "label": "Nightlife Tours"
    },
    "nomad": {
        "cats": ('City Tours', 'Cultural Tours', 'Walking Tours',
                 'Sightseeing Tours', 'Day Trips'),
        "label": "Digital Nomad Guide"
    },
    "phototour": {
        "cats": ('Photography Tours', 'Instagram Tours', 'Photo Walks',
                 'Sunrise Tours', 'Sunset Tours'),
        "label": "Photo Tours"
    },
    "tours": {
        "cats": ('City Tours', 'Sightseeing Tours', 'Guided Tours',
                 'Private Tours', 'Group Tours'),
        "label": "Tours"
    },
    "trains": {
        "cats": ('Rail Tours', 'Train Tours', 'Scenic Railroads'),
        "label": "Train Tours"
    },
    "transfers": {
        "cats": ('Airport & Hotel Transfers', 'Port Transfers', 'Private Transfers'),
        "label": "Transfers"
    },
    "visa": {
        "cats": ('City Tours', 'Sightseeing Tours'),
        "label": "Visa Guide"
    },
    "visafree": {
        "cats": ('City Tours', 'Sightseeing Tours'),
        "label": "Visa Free Guide"
    },
    "walking": {
        "cats": ('Walking Tours', 'Self-guided Tours', 'Audio Guides',
                 'City Walking Tours', 'Historical Walking Tours',
                 'Architecture Tours', 'Neighborhood Tours'),
        "label": "Walking Tours"
    },
    "watersports": {
        "cats": ('Water Tours', 'Sailing', 'Snorkeling', 'Scuba Diving',
                 'Surfing', 'Kayaking', 'Stand Up Paddleboarding',
                 'Jet Skiing', 'Parasailing', 'Rafting', 'Canoeing', 'Fishing'),
        "label": "Water Sports"
    },
    "watertours": {
        "cats": ('Water Tours', 'Sailing', 'Snorkeling', 'Boat Tours',
                 'Kayaking', 'Canoeing', 'River Cruises'),
        "label": "Water Tours"
    },
}


def _make_slug(prefix, city):
    s = city.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s]+', '-', s)
    return f"{s}-{prefix}"


def _get_remaining(conn, tbl, cols):
    if 'exhausted' in cols:
        return conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE exhausted=0").fetchone()[0]
    elif 'status' in cols:
        return conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE status='pending'").fetchone()[0]
    elif 'consumed' in cols:
        return conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE consumed=0").fetchone()[0]
    return conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]


def expand_topics():
    """모든 토픽 테이블 점검 후 부족분 자동 보충"""
    conn = sqlite3.connect(str(DB_PATH))
    total_added = 0
    results = []

    for blog, cfg in BLOG_CATEGORIES.items():
        tbl = f"{blog}_topics"
        cats = cfg["cats"]
        label = cfg["label"]

        # 테이블 존재 확인
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,)
        ).fetchone()[0]
        if not exists:
            continue

        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        remaining = _get_remaining(conn, tbl, cols)

        if remaining >= MIN_THRESHOLD:
            continue

        # 기존 도시 + 슬러그
        existing_cities = set(r[0] for r in conn.execute(f"SELECT DISTINCT city FROM {tbl}").fetchall())
        existing_slugs = set()
        if 'slug' in cols:
            existing_slugs = set(r[0] for r in conn.execute(f"SELECT DISTINCT slug FROM {tbl}").fetchall())

        # Viator에서 후보 도시 조회
        ph = ','.join('?' * len(cats))
        rows = conn.execute(f"""
            SELECT city, country, COUNT(*) as cnt
            FROM viator_tours
            WHERE category IN ({ph})
            AND deep_link IS NOT NULL AND deep_link != ''
            GROUP BY city, country
            HAVING cnt >= {MIN_TOURS}
        """, cats).fetchall()

        added = 0
        for city, country, tour_count in rows:
            if city in existing_cities:
                continue

            title = f"Best {label} in {city}"
            slug = _make_slug(blog.replace("_", "-"), city)
            if slug in existing_slugs:
                slug = f"{slug}-{(country or 'x').lower().replace(' ', '-')}"
            if slug in existing_slugs:
                continue

            try:
                if 'tour_count' in cols and 'exhausted' in cols:
                    conn.execute(f"""
                        INSERT INTO {tbl} (city, country, tour_count, title, slug, priority, exhausted)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (city, country or '', tour_count, title, slug, tour_count))
                elif 'exhausted' in cols and 'title' in cols:
                    conn.execute(f"""
                        INSERT INTO {tbl} (city, country, title, slug, exhausted)
                        VALUES (?, ?, ?, ?, 0)
                    """, (city, country or '', title, slug))
                elif 'consumed' in cols and 'title' in cols:
                    conn.execute(f"""
                        INSERT INTO {tbl} (city, country, title, slug, consumed)
                        VALUES (?, ?, ?, ?, 0)
                    """, (city, country or '', title, slug))
                elif 'title' in cols:
                    conn.execute(f"""
                        INSERT INTO {tbl} (city, country, title, slug)
                        VALUES (?, ?, ?, ?)
                    """, (city, country or '', title, slug))
                else:
                    conn.execute(f"INSERT INTO {tbl} (city, country) VALUES (?, ?)",
                                 (city, country or ''))
                existing_slugs.add(slug)
                added += 1
            except sqlite3.IntegrityError:
                continue
            except Exception as e:
                logger.warning(f"{tbl} {city} 삽입 실패: {e}")
                continue

        if added > 0:
            conn.commit()
            new_remaining = _get_remaining(conn, tbl, cols)
            results.append(f"{tbl}: +{added}개 → 남음 {new_remaining}개")
            total_added += added
            logger.info(f"토픽 확장: {tbl} +{added}개 (남음: {new_remaining})")
        else:
            results.append(f"{tbl}: 남음 {remaining}개 (Viator 후보 소진)")

    conn.close()

    if total_added > 0:
        logger.info(f"토픽 확장 완료: 총 {total_added}개 추가")
    else:
        logger.info("토픽 확장: 보충 필요 없음")

    return {"added": total_added, "details": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = expand_topics()
    print(f"\n총 {result['added']}개 토픽 추가")
    for d in result["details"]:
        print(f"  {d}")
