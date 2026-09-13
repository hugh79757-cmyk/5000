"""GH Actions 러너 ↔ R2 상태 round-trip 규약 (Phase 78, MASTER-PLAN I2).

- I2 목록 원장 SSOT: 러너가 발행에 쓰는 상태 파일 전부.
- STAP 외부 원장(../STAP/data/stap_content.db) 제외 — 5000/data/stap_content.db가
  articles 원장 실체(콤보가드 source_exists 실소스, ARTICLES_DB 경유)이므로
  **반드시 포함**. 외부 ../STAP 경로만 제외 (WL-20260911 사본 함정과 정합 —
  5000/data 쪽이 러너 복원용 실체).
- put 직전 WAL TRUNCATE 체크포인트 필수 — live WAL DB는 put↔get 사이
  변경되므로 체크포인트 없이 put하면 원본-객체 불일치 (Task 3 실증:
  1차 대조 4/4 MISMATCH → 스냅샷 절차로 12/12 OK).
- 호출부 연결은 P2 스캐폴딩(publish.yml round-trip 스텝) 확정 시 — 본
  모듈은 규약 코드화만 (PLAN Task 10.2 TBD 합의).
"""

import os
import sqlite3

from shared.paths import FIVEK_ROOT

# I2 round-trip 목록 (상대경로 → 절대경로 해석)
STATE_FILES = [
    "data/content.db",      # 발행 원장 (WAL)
    "data/car.db",          # CAP car (WAL)
    "data/curation.db",     # CUAP (DELETE)
    "data/travel-en.db",    # ETAP (WAL)
    "data/rap.db",          # RAP (WAL)
    "data/stock.db",        # STAP (DELETE)
    "data/senior.db",       # SEAP (DELETE)
    "data/stap_content.db",  # articles 원장 (콤보가드 실소스) — 갭B 수정 2026-09-13
    "data/failure_count.json",
    "data/cooldown.json",
    "data/llm_rotation_state.json",
    "ops_dashboard/ops.db",  # ops 상태 (WAL) — catchup/retry SSOT, 누락 시 무한 catchup
]


def wal_checkpoint(db_path: str) -> tuple:
    """WAL DB put 직전 필수 체크포인트 (TRUNCATE).

    체크포인트 실패 시 put 금지 — 호출부(P2 round-trip 스텝)에서 강제.
    """
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        conn.close()


def snapshot_paths() -> dict:
    """round-trip 대상 절대경로 매핑 반환 (존재 검증 포함).

    반환: {상대경로: 절대경로 or None} — None이면 파일 부재.
    """
    out = {}
    for rel in STATE_FILES:
        p = os.path.join(FIVEK_ROOT, rel)
        out[rel] = p if os.path.exists(p) else None
    return out
