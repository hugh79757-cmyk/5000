# docs/TRACKC_GSC_COLLECTION_PLAN.md — GSC 34도메인 gsc_pages 수집 계획 (트랙C Task 5)

**상태:** PLAN (2026-08-22, 대표 승인됨)
**목적:** GSC 페이지 수준 데이터(gsc_pages)를 수집해 색인 상태/노출/클릭 per page를 확인 가능하게 한다.

## 1. 현재 상태

- `shared/analytics_collector.py:collect_gsc()` — 3개 계정(twinssn/informationhot/aikorea24) 순차 조회.
  - 현재 `dimensions: ["query", "page"]`로 조회하지만 **gsc_pages 테이블에 INSERT하지 않음**
    (gsc_daily_summary + gsc_keywords만 기록).
  - `gsc_pages: 0 rows` (analytics.db 실측).
- `GSC_SITES` 목록(analytics_collector.py:132)에 **ETAP 34개 도메인이 미등록**.
  현재 등록: travel(6), stock(6), rap(1), LAP(5), kuta(1), hotissue(1), SAP(10+), AI Korea(미확인).

## 2. 34개 ETAP 도메인 목록 (GSC 등록 대상)

| # | blog_id | domain | ga4_property |
|---|---|---|---|
| 1 | adventure-hugo | adventure.techpawz.com | 531123457 |
| 2 | airlines-hugo | airlines.techpawz.com | 531035921 |
| 3 | airports-hugo | airports.techpawz.com | 531044776 |
| 4 | bus-hugo | bus.techpawz.com | 531065834 |
| 5 | citytours-hugo | citytours.techpawz.com | 533547904 |
| 6 | cruise-hugo | cruise.techpawz.com | 531006370 |
| 7 | culture-hugo | culture.techpawz.com | 531065835 |
| 8 | daytrips-hugo | daytrips.techpawz.com | 531054102 |
| 9 | deals-hugo | deals.techpawz.com | 531065294 |
| 10 | dining-hugo | dining.techpawz.com | 531047182 |
| 11 | escape-hugo | escape.techpawz.com | 533557099 |
| 12 | esim-hugo | esim.techpawz.com | 531068317 |
| 13 | eurail-hugo | eurail.techpawz.com | 531024940 |
| 14 | extreme-hugo | extreme.techpawz.com | 533528727 |
| 15 | ferry-hugo | ferry.techpawz.com | 531123458 |
| 16 | flights-hugo | flights.techpawz.com | 531065272 |
| 17 | foodtour-hugo | foodtour.techpawz.com | 531167909 |
| 18 | ghost-hugo | ghost.techpawz.com | 533502285 |
| 19 | hiking-hugo | hiking.techpawz.com | 533501468 |
| 20 | layover-hugo | layover.techpawz.com | 533564578 |
| 21 | luxury-hugo | luxury.techpawz.com | 533565769 |
| 22 | michelin-hugo | michelin.techpawz.com | 531066288 |
| 23 | multiday-hugo | multiday.techpawz.com | 531139671 |
| 24 | nature-hugo | nature.techpawz.com | 531055811 |
| 25 | nightlife-hugo | nightlife.techpawz.com | 533501469 |
| 26 | nomad-hugo | nomad.techpawz.com | 533489259 |
| 27 | phototour-hugo | phototour.techpawz.com | 531036743 |
| 28 | tour-hugo | tour.techpawz.com | 531055776 |
| 29 | tours-hugo | tours.techpawz.com | 531081222 |
| 30 | trains-hugo | trains.techpawz.com | 531082945 |
| 31 | transfers-hugo | transfers.techpawz.com | 531012256 |
| 32 | visa-hugo | visa.techpawz.com | 531039430 |
| 33 | visafree-hugo | visafree.techpawz.com | 531135786 |
| 34 | walking-hugo | walking.techpawz.com | 531135787 |
| 35 | watersports-hugo | watersports.techpawz.com | 531139672 |
| 36 | watertours-hugo | watertours.techpawz.com | 533560944 |

> 36개 블로그 중 airports(531044776)·nomad(533489259)는 paused — 등록은 하되 수집 우선순위 낮음.
> deals(531065294)는 106일 사망 상태 — 등록 후 색인 상태 확인이 진단에 유용.

## 3. 수집 절차 (GSC API)

### 3.1 도메인 등록 (사람 확인 필요 — API 접근 가능 여부에 따라)

1. Search Console API(`webmasters.v3`)에 34개 사이트 등록 확인:
   ```python
   service = build("webmasters", "v3", credentials=creds)
   sites = service.sites().list().execute()  # 현재 등록된 사이트 확인
   ```
2. 미등록 도메인은 다음 중 하나로 등록:
   - **수동**: Search Console UI에서 각 도메인 추가 + DNS/HTML 태그 인증 (사람 수행)
   - **API**: `service.sites().add(siteUrl=...)` — 도메인 인증(소유권) 필요, 사람 확인 후

### 3.2 gsc_pages 수집 (collect_gsc 확장)

`collect_gsc()`에 페이지 단위 INSERT 추가 필요 (기존 코드 수정 — 트랙C 범위, 승인됨):

```python
# gsc_pages INSERT (collect_gsc 내부, gsc_keywords INSERT 다음)
# dimensions를 ["page"] 단독으로 추가 조회해 페이지별 클릭/노출 확보
page_resp = service.searchanalytics().query(
    siteUrl=site_url,
    body={
        "startDate": target_date,
        "endDate": target_date,
        "dimensions": ["page"],
        "rowLimit": 1000,
    },
).execute()
for row in page_resp.get("rows", []):
    page = row["keys"][0]
    conn.execute(
        """INSERT OR REPLACE INTO gsc_pages
           (blog_id, date, page, clicks, impressions, ctr, position, collected_at)
           VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
        (blog_id, target_date, page,
         int(row["clicks"]), int(row["impressions"]),
         round(row["ctr"] * 100, 2), round(row["position"], 1)),
    )
```

- `dimensions: ["query", "page"]`(기존)와 `["page"]`(신규)를 **2회 쿼리**로 분리 —
  rowLimit 500/1000. gsc_keywords는 기존대로, gsc_pages는 신규 INSERT.
- 수집 주기: 기존 collect_gsc와 동일 스케줄(일 1회). 최소 7일치 누적 후
  색인/노출/클릭 per page 판정 가능.

### 3.3 URL_TO_BLOG_ID 매핑 추가

`shared/analytics_collector.py:184 URL_TO_BLOG_ID`에 34개 도메인 → blog_id 매핑 추가 필요.
(현재 travel/stock/LAP만 있고 ETAP 도메인은 `name`(도메인 문자열)이 그대로 blog_id로
기록되는 문제 — gsc_pages.blog_id가 도메인이 아니라 blog_id가 되도록.)

## 4. 수집 완료 후 확인 가능 항목

| 항목 | 쿼리 |
|---|---|
| 색인 상태 (indexed/not_indexed) | gsc_pages에 page 존재 = 노출 발생 = 색인+노출. 미존재 = 미노출(추정) |
| 노출수 per page | `SELECT page, SUM(impressions) FROM gsc_pages WHERE blog_id=? GROUP BY page ORDER BY 2 DESC` |
| 클릭수 per page | `SELECT page, SUM(clicks) ...` |
| 34도메인 등록 여부 | `service.sites().list()` 결과 vs 위 표 대조 |

## 5. 의존성/승인

- **사람 승인**: Search Console 도메인 등록(DNS 인증), GA4 Admin API 호출 (본 문서는
  계획 — 실제 API 호출은 승인 후).
- **트랙B**: 독립 진행 (트랙B 전체 재개 없음). gsc_pages 스키마는 트랙B spec에서
  이미 정의됨(APPROVED_DEPENDENCY) — 충돌 없음.
