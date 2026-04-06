import pickle, sqlite3, sys
from datetime import datetime, timedelta
from googleapiclient.discovery import build

DB_PATH = '/Users/twinssn/Projects/5000/data/analytics.db'

ACCOUNTS = [
    {
        "name": "twinssn",
        "token_path": "/Users/twinssn/Projects/blogdex/credentials/adsense_token_1_twinssn.pickle",
    },
    {
        "name": "informationhot",
        "token_path": "/Users/twinssn/Projects/blogdex/credentials/adsense_token_2_informationhot.pickle",
    },
    {
        "name": "aikorea24",
        "token_path": "/Users/twinssn/Projects/blogdex/credentials/adsense_token_3_aikorea24.pickle",
    },
]

def init_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adsense_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT,
            domain TEXT,
            date TEXT,
            page_views INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            estimated_earnings REAL DEFAULT 0,
            rpm REAL DEFAULT 0,
            ctr REAL DEFAULT 0,
            collected_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_adsense_date ON adsense_daily(date)")
    conn.commit()

def collect(days=7):
    conn = sqlite3.connect(DB_PATH)
    init_table(conn)

    end = datetime.now()
    start = end - timedelta(days=days)

    collected_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for acct in ACCOUNTS:
        try:
            with open(acct["token_path"], "rb") as f:
                creds = pickle.load(f)
            service = build("adsense", "v2", credentials=creds)
            acct_id = service.accounts().list().execute()["accounts"][0]["name"]

            # 날짜별 도메인별 수집
            for i in range(days):
                day = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                try:
                    resp = service.accounts().reports().generate(
                        account=acct_id,
                        dateRange="CUSTOM",
                        startDate_year=int(day[:4]),
                        startDate_month=int(day[5:7]),
                        startDate_day=int(day[8:10]),
                        endDate_year=int(day[:4]),
                        endDate_month=int(day[5:7]),
                        endDate_day=int(day[8:10]),
                        dimensions=["DOMAIN_NAME"],
                        metrics=["PAGE_VIEWS", "CLICKS", "AD_REQUESTS_CTR", "ESTIMATED_EARNINGS", "PAGE_VIEWS_RPM"],
                        orderBy=["-ESTIMATED_EARNINGS"],
                    ).execute()

                    rows = resp.get("rows", [])
                    for row in rows:
                        cells = row["cells"]
                        domain = cells[0]["value"]
                        pv = int(cells[1]["value"])
                        clicks = int(cells[2]["value"])
                        ctr = float(cells[3]["value"])
                        earnings = float(cells[4]["value"])
                        rpm = float(cells[5]["value"])

                        # 중복 제거
                        conn.execute("DELETE FROM adsense_daily WHERE account=? AND domain=? AND date=?",
                                     (acct["name"], domain, day))
                        conn.execute("""
                            INSERT INTO adsense_daily
                            (account, domain, date, page_views, clicks, estimated_earnings, rpm, ctr, collected_at)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (acct["name"], domain, day, pv, clicks, earnings, rpm, ctr, collected_at))

                    conn.commit()
                    print(f"[OK] {acct['name']} {day}: {len(rows)}개 도메인")
                except Exception as e:
                    print(f"[ERR] {acct['name']} {day}: {e}")

        except Exception as e:
            print(f"[ERR] {acct['name']} 인증 실패: {e}")

    # 결과 확인
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(estimated_earnings) FROM adsense_daily WHERE date > date('now','-7 days')")
    r = cur.fetchone()
    print(f"\n수집 완료: {r[0]}행, 7일 수익 합계: ${r[1]:.2f}" if r[1] else "\n수집 완료")
    conn.close()

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    collect(days)
