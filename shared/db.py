"""shared/db.py — 중앙 DB 경로 + 연결 헬퍼 (Phase 61, D-06).

분기별 SQLite DB 경로 해석과 연결을 중앙화한다. 역할은 path/connection 해석에 한정하며
데이터 이동·mutation을 하지 않는다 (data/*.db 불변, D-06). 기존 `shared/db_paths.py`를
replace하지 않고 확장해 사용한다 — 기존 심볼명 보존 (D-08).

travel 분기 주의 (PIPELINE-STANDARD §6.4, Review #3/#4):
  travel 파이프라인은 전용 DB 파일이 없다. `travel-en.db`를 사용하지 않으며,
  `PUBLISH_LEDGER_DB`(data/content.db) + `ARTICLES_DB`(data/stap_content.db) +
  `FESTIVAL_DB`를 사용한다. 따라서 get_db_path('travel')는 매핑하지 않는다
  (stale `db_paths.TRAVEL_DB = data/travel.db` 와의 충돌도 방지).

사용:
    from shared.db import get_db_path, get_connection
    path = get_db_path("rap")
    conn = get_connection(path)
"""

import os
import sqlite3

from shared import db_paths

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_BASE, "data")

# 전용 DB 파일을 가진 분기 → data/<file>.db 매핑.
# `stock`은 stap_content.db(ARTICLES_DB)를 사용.
# travel은 전용 DB가 없어 여기 포함하지 않는다 (get_db_path('travel') → ValueError).
_BRANCH_DB: dict[str, str] = {
    "car": "car.db",
    "rap": "rap.db",
    "senior": "senior.db",
    "curation": "curation.db",
    "stock": "stap_content.db",
}

_TRAVEL_NOTE = (
    "travel 분기는 전용 DB 파일이 없습니다. travel-en.db가 아니라 "
    "PUBLISH_LEDGER_DB(content.db) + ARTICLES_DB(stap_content.db) + FESTIVAL_DB를 사용하므로 "
    "get_db_path('travel')로 매핑하지 않습니다 (PIPELINE-STANDARD §6.4). "
    "전용 DB 파일을 가진 분기: car/rap/senior/curation/stock."
)


def get_db_path(branch: str) -> str:
    """분기별 전용 DB 경로를 반환한다. 미지원 분기는 ValueError를 던진다.

    지원 분기: car, rap, senior, curation, stock. (travel은 전용 DB가 없어 제외)
    """
    if branch in _BRANCH_DB:
        return os.path.join(_DATA, _BRANCH_DB[branch])
    raise ValueError(f"get_db_path('{branch}'): {_TRAVEL_NOTE}")


def get_connection(db_path: str) -> sqlite3.Connection:
    """주어진 DB 경로에 대한 sqlite3.Connection을 반환한다. 읽기/쓰기 모두 가능."""
    return sqlite3.connect(db_path)


__all__ = [
    "get_db_path",
    "get_connection",
    "db_paths",
    "PUBLISH_LEDGER_DB",
    "ARTICLES_DB",
]

PUBLISH_LEDGER_DB = db_paths.PUBLISH_LEDGER_DB
ARTICLES_DB = db_paths.ARTICLES_DB
