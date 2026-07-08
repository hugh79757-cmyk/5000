# Phase 14 Context: Cross-Project Content Quality Dashboard

**Date:** 2026-07-08
**Scope:** Unified Dashboard Wave 2(UI) + Wave 3(Integration/Ops) 완성

---

## 1. Locked Decisions

- **Architecture:** Flask + Chart.js (Jinja2 SSR, SPA 아님) — Wave 1에서 확정
- **Phase 번호:** 14 (Phase 13 Hugo Markdown Audit 다음)
- **데이터 소스:** content.db (5000) + analytics.db (GA4/GSC/AdSense/Bing) + SAP/publish_log.db + aikorea24 D1 + money-aikorea24 MD/sitemap
- **블로그 범위:** 5000 38개 + SAP 10개 + aikorea24 1개 + money-aikorea24 1개 = **50개 사이트**
- **배포:** 5000 프로젝트 내 `data/dashboard/` Flask 서버 (기존 인프라 독립)
- **자동화:** launchd (6시간 analytics 수집 + 30분 watchdog + 대시보드 서버 상시 실행)

---

## 2. Requirements

### R1 — Dashboard UI 완료 (Wave 2)
- 5개 페이지(Overview, Revenue, Traffic, Search, Health) 모두 Chart.js 차트 정상 렌더링
- 공통 차트 헬퍼 함수로 중복 제거, 일관된 다크 테마(Bootstrap 5 + Chart.js)
- 30초 자동 새로고침 (Health 페이지), 수동 새로고침 버튼 (차트 페이지)

### R2 — 외부 사이트 통합 (Wave 3)
- SAP 10개 블로그 발행 이력 `/api/posts`에 통합 표시
- aikorea24 + money-aikorea24 발행 현황 통합 표시
- GSC/GA4 속성 ID 전체 사이트 등록 (None 제거)

### R3 — 운영 자동화 및 텔레그램 알림 (Wave 4)
- Flask 서버 launchd 등록 (부팅 시 자동 실행, 크래시 시 재시작)
- 사이트 다운 감지 시 텔레그램 알림 (cooldown 30분)
- 로그 로테이션 (10MB, backup 5)

### R4 — 콘텐츠 품질 파이프라인 설계 (Phase 15 연결)
- Phase 13 Hugo 마크다운 수정 후 콘텐츠 품질 지표 수집 파이프라인 설계
- 대시보드에 "Content Quality" 섹션 추가 예정

---

## 3. Out of Scope (Deferred)

- 실시간 WebSocket 업데이트 — Phase 16+
- A/B 테스트 대시보드 — Phase 16+
- 사용자 인증/로그인 — 로컬 전용, 필요시 Phase 16+
- 알림 규칙 엔진 (조건부 알림) — Phase 16+
- Blogger API 직접 연동 — blogdex 경유
- WordPress 사이트 (kuta, ud-blogger) — blogdex에서 관리

---

## 4. Data Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Flask Dashboard (5000/data/dashboard/)        │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ Overview │  │ Revenue  │  │ Traffic  │  │ Site Health   │   │
│  │   Page   │  │   Page   │  │   Page   │  │    Page       │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘   │
│       └──────────────┴────────────┴────────────────┘            │
│                            │                                     │
│                    ┌───────┴────────┐                            │
│                    │  Chart.js      │                            │
│                    │  visualization │                            │
│                    └───────┬────────┘                            │
│                            │ Flask routes (JSON API)             │
└────────────────────────────┼────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────────┐
          ▼                  ▼                      ▼
    ┌────────────┐   ┌──────────────┐   ┌──────────────────────┐
    │ content.db │   │ analytics.db │   │ SAP/publish_log.db  │
    │ (5000 hub) │   │ (5000 hub)   │   │ (직접 연결)          │
    └────────────┘   └──────────────┘   └──────────────────────┘
                             │
                     ┌───────┴────────┐
                     ▼                ▼
               ┌──────────┐   ┌────────────────┐
               │ blogdex  │   │ aikorea24 D1   │
               │ D1 (참고)│   │ (Workers API)  │
               └──────────┘   └────────────────┘
```

---

## 5. Key Technical Decisions

1. **Chart 헬퍼 함수 추출** — `dashboard.js`에 `createLineChart()`, `createBarChart()`, `createDualLineChart()`, `destroyChart()` 공통 팩토리 함수 추가하여 5개 페이지 중복 코드 제거
2. **SAP/aikorea24 캐시 DB 분리** — `data/dashboard/data/` 하위에 별도 SQLite 파일로 캐시, 메인 DB 오염 방지
3. **Telegram 알림 Cooldown** — `alert_cooldown.json`로 30분 간격 관리, `notify_down.py`에서 헬스 체크 연동
4. **Launchd venv 경로 고정** — `/Users/twinssn/Projects/5000/venv/bin/python` 절대 경로 사용

---

## 6. Success Criteria

1. ✅ 5개 대시보드 페이지 차트 정상 렌더링 (JS 에러 0개)
2. ✅ 50개 사이트 발행/수익/트래픽/검색/헬스 단일 뷰에서 확인
3. ✅ SAP + aikorea24 + money-aikorea24 데이터 API 통합
4. ✅ Flask 서버 launchd 자동 실행, 크래시 복구
5. ✅ 사이트 다운 시 30분 쿨다운으로 텔레그램 알림
6. ✅ 로그 로테이션 정상 동작