import sqlite3
import random
import re
import json
from datetime import datetime, timedelta
from pipelines.car.data_builder import BRAND_URLS

def has_batchim(text):
    if not text:
        return False
    last_char = text.strip()[-1]
    if '가' <= last_char <= '힣':
        code = ord(last_char) - 0xAC00
        return (code % 28) != 0
    return False

def josa_wa(text):
    return "과" if has_batchim(text) else "와"

def josa_eul(text):
    return "을" if has_batchim(text) else "를"

def josa_i(text):
    return "이" if has_batchim(text) else ""

def select_topic(conn, site_id='hotissue', days_window=7, skip_ids=None, post_type=None):
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days_window)).isoformat()
    recent = c.execute('''
        SELECT DISTINCT t.car_id || ':' || COALESCE(t.competitor_car_id,'')
        FROM topics t JOIN publish_log p ON t.id = p.topic_id
        WHERE p.published_at > ? AND p.site = ?
    ''', (cutoff, site_id)).fetchall()
    recent_keys = {r[0] for r in recent}
    if post_type:
        topics = c.execute('''
            SELECT * FROM topics WHERE status = 'pending' AND site_id = ? AND post_type = ? ORDER BY priority DESC
        ''', (site_id, post_type)).fetchall()
    else:
        topics = c.execute('''
            SELECT * FROM topics WHERE status = 'pending' AND site_id = ? ORDER BY priority DESC
        ''', (site_id,)).fetchall()
    skip_set = set(skip_ids) if skip_ids else set()
    for t in topics:
        if t['id'] in skip_set:
            continue
        key = f"{t['car_id']}:{t['competitor_car_id'] or ''}"
        if key not in recent_keys:
            return t
    placeholder = ','.join('?' * len(skip_set)) if skip_set else '-1'
    oldest = c.execute('''
        SELECT t.* FROM topics t
        LEFT JOIN publish_log p ON t.id = p.topic_id
        WHERE t.status = 'pending' AND t.site_id = ?
        AND t.id NOT IN ({}){}
        ORDER BY p.published_at ASC NULLS FIRST
        LIMIT 1
    '''.format(placeholder, " AND t.post_type = ?" if post_type else ""), [site_id] + (list(skip_set) if skip_set else []) + ([post_type] if post_type else [])).fetchone()
    return oldest

def generate_title(data, site_id="hotissue"):
    """title_engine의 사이트별 고CTR 템플릿 엔진으로 위임"""
    from pipelines.car.title_engine import generate_title as _engine_title
    return _engine_title(data, site_id=site_id)

def make_slug(title):
    slug = re.sub(r'[^\w\s가-힣-]', '', title)
    slug = re.sub(r'\s+', '-', slug.strip()).lower()
    if len(slug) > 60:
        slug = slug[:60].rsplit('-', 1)[0]
    return slug

def validate_body(body, data):
    model_name = data.get("model", "")
    if model_name and model_name not in body:
        print(f"  [후처리] 경고: 본문에 '{model_name}' 없음")
    price = data.get("base_price", 0)
    if price > 0:
        price_str = f"{price:,}"
        if price_str not in body:
            print(f"  [후처리] 경고: 본문에 가격 '{price_str}만원' 없음")
    total_cost = data.get("three_year_total_cost", 0)
    if total_cost > 0 and total_cost > price * 2:
        print(f"  [후처리] 경고: 3년 총비용({total_cost}만원)이 차값의 2배 초과")
    fuel_eff = data.get("fuel_efficiency", 0)
    if fuel_eff and fuel_eff > 0:
        eff_str = str(fuel_eff)
        if eff_str not in body:
            print(f"  [후처리] 경고: 본문에 연비 {eff_str} 없음")
    # 공식 사이트 섹션 제거 (프롬프트에서 금지)
    body = re.sub(r'\n*---\n*## 공식 사이트[\s\S]*$', '', body).rstrip()
    body = re.sub(r'\n*## 공식 사이트[\s\S]*$', '', body).rstrip()
    return body
