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


class BranchDbMissingError(FileNotFoundError):
    """Raised when allow_create=False and the branch DB file is absent.

    Prevents the STRUCT-11-class failure: silent empty-DB creation ->
    first query hits 'no such table' and crashes the pipeline.
    """

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

# connect_branch_db 전용 매핑 — _BRANCH_DB를 보강하고 stock name-collision 해소.
# `stock` → stap_content.db (기존 get_db_path 시맨틱 보존).
# `stock_metrics` → data/stock.db (5000 전용 지표 DB, 별도 파일 — F1 collision 해소).
# _BRANCH_DB와 중복 키(stock)가 있으나 get_db_path는 _BRANCH_DB을 그대로 사용하므로 기존 호출부 영향 없음.
_BRANCH_DB_FILE: dict[str, str] = {
    "car": "car.db",
    "rap": "rap.db",
    "senior": "senior.db",
    "curation": "curation.db",
    "stock": "stap_content.db",           # ARTICLES_DB view (preserve existing get_db_path)
    "stock_metrics": "stock.db",          # 5000/data/stock.db (separate file!)
    "course": "course.db",
    "gap": "gap.db",
    "festival": "festival.db",
    "travel-en": "travel-en.db",
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


def connect_branch_db(branch: str, allow_create: bool = False) -> sqlite3.Connection:
    """분기 전용 SQLite DB에 연결한다.

    allow_create=False (기본): 파일이 없으면 BranchDbMissingError를 던진다.
        절대 무음 생성하지 않는다. 모든 READ 경로에 사용할 것.
    allow_create=True: CREATE TABLE IF NOT EXISTS를 동반하는 bootstrap 경로에서만.
        존재하거나 새 파일이면 연결한다.
    """
    if branch not in _BRANCH_DB_FILE:
        raise BranchDbMissingError(
            f"connect_branch_db('{branch}'): 등록된 전용 DB가 없습니다 (무음 생성 거부). "
            f"지원 분기: {', '.join(sorted(_BRANCH_DB_FILE))}"
        )
    path = os.path.join(_DATA, _BRANCH_DB_FILE[branch])
    if not allow_create and not os.path.exists(path):
        raise BranchDbMissingError(
            f"Branch DB 누락 (무음 생성 거부): {path}. "
            f"백업에서 복원(BRANCH_DB_RUNBOOK.md)하거나 분기 collector를 실행하세요."
        )
    return sqlite3.connect(path)


__all__ = [
    "get_db_path",
    "get_connection",
    "connect_branch_db",
    "BranchDbMissingError",
    "db_paths",
    "PUBLISH_LEDGER_DB",
    "ARTICLES_DB",
]

PUBLISH_LEDGER_DB = db_paths.PUBLISH_LEDGER_DB
ARTICLES_DB = db_paths.ARTICLES_DB
