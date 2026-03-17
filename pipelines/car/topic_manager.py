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

def select_topic(conn, site_id='hotissue', days_window=7, skip_ids=None):
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days_window)).isoformat()
    recent = c.execute('''
        SELECT DISTINCT t.car_id || ':' || COALESCE(t.competitor_car_id,'')
        FROM topics t JOIN publish_log p ON t.id = p.topic_id
        WHERE p.published_at > ? AND p.site = ?
    ''', (cutoff, site_id)).fetchall()
    recent_keys = {r[0] for r in recent}
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
        AND t.id NOT IN ({})
        ORDER BY p.published_at ASC NULLS FIRST
        LIMIT 1
    '''.format(placeholder), [site_id] + (list(skip_set) if skip_set else [])).fetchone()
    return oldest

def generate_title(data):
    """본문 H2 첫 번째를 제목으로 사용하되, fallback 템플릿도 준비"""
    model_short = data["model"].replace("현대 ", "").replace("기아 ", "")
    comp_short = data.get("competitor", "").replace("현대 ", "").replace("기아 ", "")
    price = data.get("base_price", 0)
    trim = data.get("trim", "")
    resale = data.get("resale_rate_percent", 0)
    resale_3yr = data.get("resale_3yr", 0)
    dep_3yr = data.get("three_year_depreciation", 0)
    total_3yr = data.get("three_year_total_cost", 0)
    wa = josa_wa(comp_short)
    eul = josa_eul(model_short)

    if comp_short:
        templates = [
            f"{model_short} {trim} {price:,}만원, 지금 사도 될까",
            f"{model_short}{wa} {comp_short} 3년 유지비 {dep_3yr:,}만원 차이 비교",
            f"{model_short} vs {comp_short} 3년 보유하면 누가 더 손해일까",
            f"{price:,}만원 {model_short}, {comp_short}보다 나은 선택일까",
            f"{model_short} {comp_short} 감가 비교 3년 후 얼마나 떨어질까",
        ]
    else:
        templates = [
            f"{model_short} {trim} {price:,}만원, 지금 사도 될까",
            f"{model_short} 3년 타면 실제 비용 {total_3yr:,}만원 나가는 이유",
            f"{price:,}만원 {model_short} 3년 뒤 {resale_3yr:,}만원 감가 분석",
            f"{model_short} {trim} 잔존가치 {resale}% 실구매자 비용 분석",
            f"{model_short}{eul} 지금 사면 3년 후 얼마나 남을까",
        ]
    return random.choice(templates)

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
