"""db_paths.py — 프로젝트 전체 DB 경로 단일 관리

content.db:      publish_ledger (source_id/title 중복 체크용)
stap_content.db: articles (최신 발행 데이터, sigungu 중복 체크용)
"""
import os

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 발행 이력 ledger (publish_ledger 테이블) — content.db
PUBLISH_LEDGER_DB = os.path.join(_BASE, "data", "content.db")

# articles 테이블 (최신 발행 데이터) — stap_content.db
ARTICLES_DB       = os.path.join(_BASE, "data", "stap_content.db")

# 기타
TAP_DB            = os.path.join(_BASE, "data", "tap.db")
FESTIVAL_DB       = os.path.join(_BASE, "data", "festival.db")
TRAVEL_DB         = os.path.join(_BASE, "data", "travel.db")
