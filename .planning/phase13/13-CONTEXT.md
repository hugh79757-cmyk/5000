# Phase 13 — 통합 대시보드 (Flask + Chart.js): CONTEXT

**Date:** 2026-07-07
**Scope:** 단일 대시보드에서 5000(Hub) + SAP(Sports) + aikorea24 + money-aikorea24 모든 자동블로그 통합 모니터링

---

## 1. Locked Decisions

- **아키텍처**: Flask + Chart.js (Jinja2 SSR, SPA 아님)
- **Phase 번호**: 5000 Phase 13 (Phase 11 AdSense / Phase 12 Content Enrichment 이후)
- **데이터 소스**: content.db (5000), analytics.db (5000), SAP/publish_log.db, blogdex D1 (참고), aikorea24 D1, money-aikorea24 MD
- **블로그 범위**: 5000 37개 (CUAP/TAP/STAP/RAP/SEAP/CAP/LAP/ETAP/GAP 포함) + SAP 10개 + aikorea24 1개 + money-aikorea24 1개 = **49개 사이트**
- **blogdex 활용 범위**: GA4/GSC/AdSense/Bing 수집 패턴만 참고 (daily_sync.py, perf.py, adsense.py, gsc.py). 자체 대시보드는 사용하지 않음.
- **배포**: 5000 프로젝트 내 `data/dashboard/` 디렉토리에 Flask 서버 (기존 Hugo/Dispatcher 인프라와 독립)

## 2. Requirements

### R1 — 사이트 헬스 체크 (필수)
- 49개 사이트 모두 HTTP 200 응답 확인
- 텔레그램 알림 (사이트 다운 시)
- 히스토리 트래킹 (SQLite)

### R2 — 발행 현황 (필수)
- 일간/주간/월간 블로그별 발행 수
- 5000 content.db + SAP publish_log.db + aikorea24 + money-aikorea24 통합
- 시계열 차트 (Chart.js)

### R3 — 광고 수익 (필수)
- analytics.db adsense_daily 연동
- 일간/주간/월간 수익 추이 (line chart)
- 블로그별/도메인별 수익 순위 (bar chart)
- RPM/CTR 추이

### R4 — 트래픽 분석 (필수)
- analytics.db ga4_daily 연동
- 세션/사용자/페이지뷰 추이
- 이탈률, 참여율
- 블로그별 트래픽 순위

### R5 — 검색 엔진 성과 (필수)
- GSC 클릭/노출/CTR/평균순위
- Bing 클릭/노출
- 블로그별 검색 트래픽 순위

### R6 — SAP 통합 (필수)
- SAP 10개 블로그 발행 이력 수집
- SAP 발행 현황을 메인 대시보드에 통합 표시
- SAP 사이트 헬스 체크 포함

### R7 — aikorea24 + money-aikorea24 통합 (필수)
- 발행 현황 수집 파이프라인
- 메인 대시보드에 통합 표시
- 사이트 헬스 체크 포함

### R8 — GA4 데이터 수집 재개 (우선)
- analytics.db GA4 수집 중단 원인 파악 및 재개
- SAP/aikorea24/money-aikorea24 GA4 속성 추가
- blogdex daily_sync.py 패턴 참고

### R9 — 대시보드 UI/UX (우선)
- Flask + Chart.js 반응형 레이아웃
- 모바일 대응 (Bootstrap 5 또는 Tailwind)
- 다크모드
- 자동 새로고침 (30초)

### R10 — 배포 및 운영 (우선)
- Flask 서버 launchd 등록 (5000 스케줄러와 독립)
- 로그: dashboard.log
- 장애 시 텔레그램 알림

## 3. Out of Scope (Deferred)

- 실시간 업데이트 (WebSocket) — Phase 14+
- A/B 테스트 대시보드 — Phase 14+
- Blogger API 직접 연동 — blogdex 경유
- Wordpress 사이트 (kuta, ud-blogger) — blogdex에서 관리
- 알림 규칙 엔진 (조건부 알림) — Phase 14+
- 사용자 인증/로그인 — 로컬 전용, 필요시 Phase 14+

## 4. 데이터 수집 아키텍처

```
                   ┌──────────────────────────┐
                   │  analytics_collector.py   │
                   │  (매일 cron, blogdex 참고) │
                   └────────┬─────────────────┘
                            │ GA4 API / GSC API / AdSense API / Bing API
                            ▼
                   ┌──────────────────────────┐
                   │  analytics.db             │
                   │  (ga4_daily, adsense_daily, │
                   │   gsc_daily_summary,       │
                   │   bing_daily_summary)      │
                   └────────┬─────────────────┘
                            │
                    ┌───────┴────────┐
                    │                │
                    ▼                ▼
           ┌────────────┐   ┌──────────────────┐
           │ content.db │   │ SAP/publish_log  │
           │ (5000 hub) │   │ (직접 수집)       │
           └────────────┘   └──────────────────┘
                    │                │
                    └───────┬────────┘
                            │ Flask app.py
                            ▼
                   ┌──────────────────────────┐
                   │  Flask Dashboard          │
                   │  localhost:5050           │
                   │  Jinja2 + Chart.js        │
                   └──────────────────────────┘
```

## 5. Effort Breakdown (예상)

| 영역 | 항목 | 난이도 | 위험 | Wave |
|------|------|--------|------|------|
| R8 | GA4 수집 재개 + SAP/aikorea24 추가 | Medium | 🟡 | Wave 1 |
| R2 | content.db 기반 발행 현황 API | Small | 🟢 | Wave 1 |
| R3 | adsense_daily 연동 차트 | Small | 🟢 | Wave 1 |
| R4 | ga4_daily 연동 차트 | Small | 🟢 | Wave 1 |
| R5 | GSC + Bing 연동 차트 | Small | 🟢 | Wave 1 |
| R1 | 사이트 헬스 체크 (ping) | Small | 🟢 | Wave 1 |
| R9 | Flask Jinja2 템플릿 (UI) | Medium | 🟢 | Wave 2 |
| R6 | SAP publish_log 수집 통합 | Medium | 🟡 | Wave 2 |
| R7 | aikorea24 + money-aikorea24 수집 | Medium | 🟡 | Wave 3 |
| R10 | launchd 등록 + 텔레그램 연동 | Small | 🟢 | Wave 3 |

## 6. Wave Plan

```
Wave 1 —핵심 데이터 API + 수집 재개 (병렬 가능):
  GA4 수집 재개 (analytics_collector.py)
  content.db 기반 발행 현황 API (/api/posts)
  adsense_daily 기반 수익 API (/api/revenue)
  ga4_daily 기반 트래픽 API (/api/traffic)
  gsc+bing 기반 검색 API (/api/search)
  사이트 헬스 체크 API (/api/health)

Wave 2 — 대시보드 UI 완성:
  Flask Jinja2 템플릿 (Chart.js 차트 6종)
  반응형 레이아웃 (Bootstrap 5)
  SAP publish_log.db 통합
  사이트 헬스 페이지
  자동 새로고침 (30초)

Wave 3 — 외부 사이트 통합 + 운영:
  aikorea24 D1 연동
  money-aikorea24 MD/파일 수집
  launchd 등록
  텔레그램 알림 (사이트 다운)
  dashboard.log
```

## 7. Success Criteria

1. 5000 대시보드 `localhost:5050` 접속 가능
2. 37개+10개+2개 = 49개 사이트 헬스 체크 ✅/❌ 표시
3. 일간/주간/월간 발행 수 차트 정상 표시
4. 애드센스 수익 추이 차트 정상 표시
5. GA4 트래픽 (세션/사용자) 차트 정상 표시
6. GSC/Bing 검색 실적 차트 정상 표시
7. SAP 10개 블로그 발행 이력 통합 표시
8. aikorea24 + money-aikorea24 발행 현황 표시
9. GA4 수집 재개 (analytics.db ga4_daily에 신규 데이터)
10. Flask 서버 launchd 자동 실행
