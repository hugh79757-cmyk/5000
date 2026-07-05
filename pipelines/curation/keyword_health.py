"""키워드 건강 추적 및 격리 — 실패 키워드 자동 격리 + 지수 백오프

키워드가 연속으로 실패하면 자동으로 격리하고, 지수 백오프 방식으로
격리 기간이 증가합니다. 성공 시 격리가 해제됩니다.
"""
import json
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BACKOFF_HOURS = [1, 4, 24, 168, 720]  # 1h, 4h, 1d, 7d, 30d
MAX_QUARANTINE_PERCENT = 0.20  # Never quarantine > 20% of keyword pool


class KeywordHealthStore:
    """키워드 건강 상태 관리 — 실패 추적, 격리, 지수 백오프

    사용법:
        store = KeywordHealthStore("data/curation.db")
        store.ensure_table()
        store.record_failure("laptop-hugo", "게이밍노트북", "irrelevant_products")
        if store.is_quarantined("laptop-hugo", "게이밍노트북"):
            print("키워드 격리 중")
        store.record_success("laptop-hugo", "게이밍노트북")
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        """DB 연결 반환 (row factory 설정)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_table(self):
        """keyword_health 테이블 및 인덱스 생성"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS keyword_health (
                blog_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                consecutive_failures INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_failure_at TEXT,
                last_failure_reason TEXT,
                last_success_at TEXT,
                quarantined_until TEXT,
                failure_history TEXT DEFAULT '[]',
                PRIMARY KEY (blog_id, keyword)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kh_blog_quarantined
            ON keyword_health(blog_id, quarantined_until)
        """)
        conn.commit()
        conn.close()

    def _get_row(self, blog_id: str, keyword: str) -> dict | None:
        """키워드 건강 row 조회 (내부 헬퍼)"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM keyword_health WHERE blog_id=? AND keyword=?",
            (blog_id, keyword),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return dict(row)

    def is_quarantined(self, blog_id: str, keyword: str) -> bool:
        """키워드가 현재 격리 중인지 확인

        quarantined_until > datetime.now() 이면 격리 중으로 간주.
        """
        row = self._get_row(blog_id, keyword)
        if row is None:
            return False
        q_until = row.get("quarantined_until")
        if not q_until:
            return False
        try:
            return datetime.fromisoformat(q_until) > datetime.now()
        except (ValueError, TypeError):
            return False

    def record_failure(self, blog_id: str, keyword: str, reason: str):
        """키워드 실패 기록 — 격리 + 지수 백오프 적용

        Args:
            blog_id: 블로그 ID
            keyword: 실패한 키워드
            reason: 실패 사유 (irrelevant_products, low_relevance, write_error 등)
        """
        now = datetime.now()
        row = self._get_row(blog_id, keyword)

        if row:
            consecutive_failures = row["consecutive_failures"] + 1
            success_count = row["success_count"]
            failure_history = json.loads(row.get("failure_history", "[]"))
        else:
            consecutive_failures = 1
            success_count = 0
            failure_history = []

        # 실패 이력 추가 (최대 10개 유지)
        failure_history.append({
            "timestamp": now.isoformat(),
            "reason": reason,
        })
        failure_history = failure_history[-10:]

        # 지수 백오프 계산
        # consecutive_failures=1 → BACKOFF_HOURS[0] (1h)
        # consecutive_failures=2 → BACKOFF_HOURS[1] (4h)
        # consecutive_failures=5+ → BACKOFF_HOURS[4] (720h = 30d)
        backoff_index = min(consecutive_failures - 1, len(BACKOFF_HOURS) - 1)
        backoff_hours = BACKOFF_HOURS[backoff_index]
        quarantined_until = (now + timedelta(hours=backoff_hours)).isoformat()

        # 격리 상한선 확인 (새로 격리되는 키워드만 체크)
        # 이미 격리 중인 키워드는 갱신만 수행
        already_quarantined = self.is_quarantined(blog_id, keyword)
        if not already_quarantined:
            from pipelines.curation.keywords import get_keywords

            total_keywords = len(get_keywords(blog_id))
            if total_keywords > 0:
                current_quarantined = self._count_quarantined(blog_id)
                if (current_quarantined + 1) / total_keywords > MAX_QUARANTINE_PERCENT:
                    logger.warning(
                        f"[{blog_id}] 격리 상한 도달: {current_quarantined + 1}/{total_keywords} "
                        f"(최대 {MAX_QUARANTINE_PERCENT:.0%}) — '{keyword}' 격리 생략"
                    )
                    quarantined_until = None  # 격리하지 않음

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO keyword_health
                   (blog_id, keyword, consecutive_failures, success_count,
                    last_failure_at, last_failure_reason, quarantined_until, failure_history)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(blog_id, keyword) DO UPDATE SET
                   consecutive_failures = excluded.consecutive_failures,
                   success_count = excluded.success_count,
                   last_failure_at = excluded.last_failure_at,
                   last_failure_reason = excluded.last_failure_reason,
                   quarantined_until = excluded.quarantined_until,
                   failure_history = excluded.failure_history""",
            (
                blog_id,
                keyword,
                consecutive_failures,
                success_count,
                now.isoformat(),
                reason,
                quarantined_until,
                json.dumps(failure_history, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

    def _count_quarantined(self, blog_id: str) -> int:
        """블로그의 현재 격리된 키워드 수"""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM keyword_health WHERE blog_id=? AND quarantined_until > ?",
            (blog_id, now),
        ).fetchone()[0]
        conn.close()
        return count

    def record_success(self, blog_id: str, keyword: str):
        """키워드 성공 기록 — 격리 초기화

        consecutive_failures를 0으로 리셋하고, success_count를 증가시킵니다.
        quarantined_until을 NULL로 설정하여 격리를 해제합니다.
        """
        now = datetime.now()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO keyword_health
                   (blog_id, keyword, consecutive_failures, success_count,
                    last_success_at, quarantined_until)
               VALUES (?, ?, 0, 1, ?, NULL)
               ON CONFLICT(blog_id, keyword) DO UPDATE SET
                   consecutive_failures = 0,
                   success_count = success_count + 1,
                   last_success_at = excluded.last_success_at,
                   quarantined_until = NULL""",
            (blog_id, keyword, now.isoformat()),
        )
        conn.commit()
        conn.close()

    def get_quarantined_keywords(self, blog_id: str = None) -> list[dict]:
        """격리된 키워드 목록 반환

        Args:
            blog_id: 특정 블로그만 조회 (None이면 전체)
        """
        now = datetime.now().isoformat()
        conn = self._get_conn()
        if blog_id:
            rows = conn.execute(
                "SELECT * FROM keyword_health WHERE blog_id=? AND quarantined_until > ? ORDER BY quarantined_until",
                (blog_id, now),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM keyword_health WHERE quarantined_until > ? ORDER BY blog_id, quarantined_until",
                (now,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_health_summary(self, blog_id: str) -> dict:
        """블로그 키워드 건강 요약

        Returns:
            total_keywords: 전체 키워드 수
            quarantined_count: 격리 중인 키워드 수
            healthy_count: 정상 키워드 수
            most_failing_keywords: 실패 횟수 상위 10개 키워드
        """
        from pipelines.curation.keywords import get_keywords

        total = len(get_keywords(blog_id))
        quarantined = self.get_quarantined_keywords(blog_id)
        quarantined_count = len(quarantined)

        conn = self._get_conn()
        most_failing = conn.execute(
            """SELECT blog_id, keyword, consecutive_failures, quarantined_until
               FROM keyword_health
               WHERE blog_id=? AND consecutive_failures > 0
               ORDER BY consecutive_failures DESC LIMIT 10""",
            (blog_id,),
        ).fetchall()
        conn.close()

        return {
            "total_keywords": total,
            "quarantined_count": quarantined_count,
            "healthy_count": total - quarantined_count,
            "most_failing_keywords": [dict(r) for r in most_failing],
        }

    def reset_keyword(self, blog_id: str, keyword: str):
        """키워드 격리 수동 해제"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE keyword_health SET quarantined_until=NULL WHERE blog_id=? AND keyword=?",
            (blog_id, keyword),
        )
        conn.commit()
        conn.close()
