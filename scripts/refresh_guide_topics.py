#!/usr/bin/env python3
"""guide-hugo beginner_guide 토픽 재생성
- 트림 유효한 차량만 선별
- 최근 30일 내 발행된 차량은 제외
- skip_no_data 차량도 재시도 (데이터가 보충되었을 수 있음)
- 60개 생성 (12일분, quota=5 기준)
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "car.db"
SITE = "guide"
POST_TYPE = "beginner_guide"
TARGET = 60

def run() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. 유효 트림 있는 차량 전체
    cars = c.execute("""
        SELECT DISTINCT c.car_id, c.model, c.brand, c.segment, c.is_popular
        FROM cars c
        WHERE EXISTS (
            SELECT 1 FROM trims t
            WHERE t.car_id=c.car_id AND t.status='시판' AND t.price>=500
        )
        ORDER BY c.is_popular DESC, RANDOM()
    """).fetchall()

    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    created = 0

    for car in cars:
        if created >= TARGET:
            break

        car_id = car["car_id"]

        # 2. 현재 pending 있으면 skip
        pending = c.execute(
            "SELECT 1 FROM topics WHERE car_id=? AND site_id=? AND post_type=? AND status='pending'",
            (car_id, SITE, POST_TYPE)
        ).fetchone()
        if pending:
            continue

        # 3. 최근 30일 내 published 이력 있으면 skip
        recent = c.execute("""
            SELECT 1 FROM topics t
            JOIN publish_log p ON p.topic_id=t.id
            WHERE t.car_id=? AND t.site_id=? AND t.post_type=?
              AND t.status='published' AND p.published_at > ?
        """, (car_id, SITE, POST_TYPE, cutoff)).fetchone()
        if recent:
            continue

        # 4. 생성
        priority = 7 if car["is_popular"] else 5
        c.execute(
            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,?,?,datetime('now'),?)",
            (car_id, POST_TYPE, priority, "pending", SITE)
        )
        created += 1
        logger.info(f"  [{created}/{TARGET}] {car['brand']} {car['model']} ({car['segment']}) priority={priority}")

    conn.commit()
    conn.close()
    logger.info(f"완료: guide-hugo beginner_guide 토픽 {created}개 생성")

if __name__ == "__main__":
    run()
