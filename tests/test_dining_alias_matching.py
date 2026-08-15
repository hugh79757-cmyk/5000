"""dining_writer.fetch_restaurants 별칭 정규화 회귀 테스트.

핵심 게이트(오매칭 방지):
  - 정상 city 정확일치 → 매칭 pass
  - 별칭(city) → canonical 해석 시 **country 일치가 하드 게이트**로 유지됨
  - 타국가로의 오매칭(예: 이탈리아 토픽 'TP' → Taipei/Taiwan) → fail(빈 결과)
  - 국가 표기 차이(USA/US/United States, UK/United Kingdom, Türkiye/Turkey)
    브리징
  - 별칭 부재(소스없어 불가) → 빈 결과 유지

로직 테스트는 결정적 in-memory DB, 스모크 1건은 실 DB(read-only)를 사용한다.
"""
import sqlite3

import pytest

from pipelines.etap.dining_writer import fetch_restaurants


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE michelin_restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, address TEXT, location TEXT, price TEXT,
            cuisine TEXT, longitude REAL, latitude REAL, phone TEXT,
            url TEXT, website TEXT, award TEXT, green_star INTEGER,
            facilities TEXT, description TEXT, city TEXT, country TEXT
        );
        CREATE TABLE city_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT, alias TEXT, country TEXT, region TEXT
        );
    """)
    return conn


@pytest.fixture
def db():
    conn = _make_db()
    yield conn
    conn.close()


def _seed_michelin(conn, rows):
    for r in rows:
        conn.execute(
            """INSERT INTO michelin_restaurants
               (name, city, country, award) VALUES (?,?,?,?)""",
            (r["name"], r["city"], r["country"], r.get("award", "1 Star")),
        )


def _seed_alias(conn, rows):
    for r in rows:
        conn.execute(
            "INSERT INTO city_aliases (canonical_name, alias, country, region) VALUES (?,?,?,?)",
            (r["canonical"], r["alias"], r["country"], r.get("region", "")),
        )


class TestExactMatch:
    """정상 city 정확일치 → 매칭 pass."""

    def test_exact_city_returns_rows(self, db):
        _seed_michelin(db, [{"name": "Trattoria X", "city": "Milan", "country": "Italy"}])
        rows = fetch_restaurants("Milan", "Italy", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Milan"

    def test_exact_city_no_country_still_works(self, db):
        """country 미지정 시에도 정확일치는 동작 (하위호환)."""
        _seed_michelin(db, [{"name": "Bistrot", "city": "Paris", "country": "France"}])
        rows = fetch_restaurants("Paris", conn=db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Paris"


class TestAliasMatch:
    """별칭(city) → canonical 해석 + country 하드 게이트."""

    def test_alias_resolves_within_country(self, db):
        _seed_alias(db, [{"canonical": "Milan", "alias": "MI", "country": "Italy"}])
        _seed_michelin(db, [{"name": "Sorelle", "city": "Milan", "country": "Italy"}])
        rows = fetch_restaurants("MI", "Italy", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Milan"

    def test_country_mismatch_rejected(self, db):
        """이탈리아 토픽 'TP'의 별칭은 Taipei/Taiwan → country 게이트로 거부."""
        _seed_alias(db, [{"canonical": "Taipei", "alias": "TP", "country": "Taiwan"}])
        _seed_michelin(db, [{"name": "Din Tai Fung", "city": "Taipei", "country": "Taiwan"}])
        rows = fetch_restaurants("TP", "Italy", db)
        assert rows == []

    def test_same_code_wrong_country_still_rejected(self, db):
        """같은 별칭 코드라도 country가 다르면 매칭 안 됨."""
        _seed_alias(db, [{"canonical": "Milan", "alias": "MI", "country": "Italy"}])
        _seed_michelin(db, [{"name": "Sorelle", "city": "Milan", "country": "Italy"}])
        rows = fetch_restaurants("MI", "France", db)
        assert rows == []


class TestCodeFallback:
    """CITY_ALIAS_FALLBACK 코드 레벨 폴백 (DB city_aliases 부재 시)."""

    def test_fallback_resolves_same_country(self, db):
        """DB 별칭이 없어도 코드 폴백으로 동국가 canonical 해소."""
        _seed_michelin(db, [{"name": "Vincents", "city": "Riga", "country": "Latvia"}])
        rows = fetch_restaurants("Rīga", "Latvia", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Riga"

    def test_fallback_case_insensitive(self, db):
        _seed_michelin(db, [{"name": "L'Enclume", "city": "Liverpool", "country": "United Kingdom"}])
        rows = fetch_restaurants("merseyside", "United Kingdom", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Liverpool"

    def test_fallback_wrong_country_rejected(self, db):
        """코드 폴백도 country 하드 게이트 유지 — 타국가 오매칭 거부."""
        _seed_alias(db, [{"canonical": "Riga", "alias": "Rīga", "country": "Estonia"}])
        _seed_michelin(db, [{"name": "X", "city": "Riga", "country": "Latvia"}])
        rows = fetch_restaurants("Rīga", "France", db)
        assert rows == []

    def test_fallback_country_with_data_only(self, db):
        """폴백 대상이 아닌 도시는 빈 결과 유지 (임의 매칭 없음)."""
        rows = fetch_restaurants("NonRecoverableCity", "Latvia", db)
        assert rows == []


class TestCountryNormalization:
    """국가 표기 차이 브리징 (USA/US/United States 등)."""

    def test_alias_us_bridges_to_usa(self, db):
        # city_aliases.country='US' 이지만 topic.country='United States',
        # michelin.country='USA' — 셋 다 동일 국가로 정규화되어 해소.
        _seed_alias(db, [{"canonical": "New York", "alias": "NYC", "country": "US"}])
        _seed_michelin(db, [{"name": "Per Se", "city": "New York", "country": "USA"}])
        rows = fetch_restaurants("NYC", "United States", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "New York"

    def test_turkey_normalization(self, db):
        _seed_alias(db, [{"canonical": "Istanbul", "alias": "IST", "country": "Turkey"}])
        _seed_michelin(db, [{"name": "Mikla", "city": "Istanbul", "country": "Turkey"}])
        rows = fetch_restaurants("IST", "Türkiye", db)
        assert len(rows) == 1
        assert rows[0]["city"] == "Istanbul"


class TestNoAlias:
    """별칭 부재(소스없어 불가) → 빈 결과 유지."""

    def test_no_alias_returns_empty(self, db):
        rows = fetch_restaurants("NonExistentCity", "Portugal", db)
        assert rows == []

    def test_country_without_data_no_false_hit(self, db):
        """country만 있고 city·별칭이 없으면 빈 결과 (임의 매칭 없음)."""
        _seed_michelin(db, [{"name": "Rest", "city": "Lisbon", "country": "Portugal"}])
        rows = fetch_restaurants("Lamego", "Portugal", db)
        assert rows == []


class TestRealDbSmoke:
    """실 DB(read-only) 스모크 — 정확일치/별칭해소/타국가거부."""

    def test_real_exact_and_alias_and_reject(self):
        from pipelines.etap.dining_writer import _get_db

        conn = _get_db()
        try:
            # 정확일치 pass
            assert len(fetch_restaurants("Milan", "Italy", conn)) >= 3
            # 별칭 해소 pass (MI → Milan, 동일 이탈리아)
            mi = fetch_restaurants("MI", "Italy", conn)
            assert len(mi) >= 3
            assert mi[0]["city"] == "Milan"
            # 타국가 오매칭 fail (TP → Taipei/Taiwan 이탈리아 토픽 제외)
            assert fetch_restaurants("TP", "Italy", conn) == []
            # country 미지정 별칭 → 보수적 (빈 결과)
            assert fetch_restaurants("MI", conn=conn) == []
        finally:
            conn.close()