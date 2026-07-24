# State File — Resume Status

**Generated:** 2026-07-24 10:00 KST (verification + completion docs)
**Session:** Phase 30/31 AdSense standardization verification + commit

---

## Current Phase Status (Code-Backed)

| Phase | Status | 실제 코드 증거 | 
|-------|--------|---------------|
| Phase 1-10 | ✅ Complete | git history + 코드 존재 |
| Phase 6+7 | ✅ Complete (merged) | `def74aeef` |
| Phase 11 AdSense | ✅ Complete | 10개 CUAP 블로그 전부 adsense partials + IntersectionObserver |
| Phase 12 Body Rescan | 🔴 Partial | `--scan-body` OK, **`validate_keyword()` 누락** → silent failure |
| Phase 13 Dashboard | ✅ Complete | http://localhost:5050, 6종 API, 5개 UI 페이지 |
| Phase 14 Cross-Project | ✅ Complete | SAP 7 + aikorea24 2 = 47개 통합, launchd |
| Phase 15 Quality Pipe | ✅ Complete | quality_recorder, hugo_builder, API+UI, daily_aggregate |
| Phase 22-C Funnel Cards | ✅ Complete | `.planning/phase-22-c` SUMMARY + CSS deploy |
| Phase 25 CUAP Spider Entity | ✅ Complete | 거미줄 엔티티 시스템, cross-blog linking + funnel + cross-sell |
| Phase 26 CUAP Auto Ads | ✅ Complete | `.continue-here.md` handoff 기록 |
| Phase 28 Worker 404 Fix | ✅ Complete | 6개 Worker 블로그 src/index.js canonical 통일 |
| Phase 29 CUAP Content Fix | ✅ Complete | keywords 정리 + cuap_entities URL 정리 + beauty-hugo 재배포 |
| Phase 30 CUAP AdSense Std | ✅ Complete | informationhot.kr 17개 블로그 표준화, live 광고 확인 |
| Phase 31 rotcha AdSense Std | ✅ Complete | rotcha.kr 6개 Blowfish 블로그 표준화, live 광고 확인 |
| Phase 10-1 Publishing Failure Hardening | ✅ Complete | kitchen-hugo 가정용 차단 + adaptive threshold + deploy retry |

---

## 문서 vs 코드 불일치 (FIXED)

| 문서 | 문제 | 조치 |
|------|------|------|
| ROADMAP.md | "3 phases", Phase 6/7/11/13-15 누락 | ✅ ROADMAP.md 재작성 |
| STATE.md | Phase 11-12 = deferred (틀림) | ✅ 본 문서로 수정 |
| SESSION_STATUS.md | Phase 11 blocker 3개 (이미 해결됨) | 아래 업데이트 |
| REQUIREMENTS.md | 모든 status = Pending (10개 전부) | 아래 업데이트 |

---

## Known Gaps (Code vs Plan)

### 1. Phase 12: `validate_keyword()` 누락
- `keyword_expander.py:273`에서 `from pipelines.curation.keywords import validate_keyword` 호출
- `keywords.py`에 함수 없음 → `ImportError` catch로 silent failure
- **Fix:** 3분 작업, `keywords.py`에 함수 추가만 하면 됨

### 2. Phase 12: `--scan-body` 결과 활용 안 됨
- `detect_problematic_posts.py --scan-body`는 구현됐지만 실제로 실행된 기록 없음
- Body scan 결과로 자동 삭제/필터링 로직 없음

### 3. Phase 10 Blowfish shortcode
- hugo_writer.py에 shortcode 변환 함수 구현됨
- **Toggle disabled** (commit 메시지: "disabled by toggle")
- 활성화하려면 toggle만 켜면 됨

### 4. Phase 15 pipeline hook
- curation pipeline에서만 record_quality 호출
- travel/stock pipeline은 미연결

---

## uncommitted changes (작업 중)

```
M data/dashboard/scripts/sync_sap_to_dashboard.py  (SAP sync fix)
M dispatcher.py                                     (STAP auto-collect + IPO cooldown)
M pipelines/curation/keywords.py                    (keyword cleanup)
M pipelines/curation/pipeline.py                    (CTA fallback)
M scripts/master_backup.py                          (import os fix)
M shared/post_validator.py                          (empty_template regex fix)
M shared/publisher.py                               (og:image inject)
M shared/publishers/hugo_writer.py                  (empty_template regex fix)
```

(7 files modified, 1 pending from today's session)

---

## 추천 Next Action

### 🔴 IMMEDIATE (3분)
- Phase 12: `keywords.py`에 `validate_keyword()` 함수 추가

### 🟡 이번 세션
- Phase 16 계획 수립 (Production Hardening — Phase 1-15에서 발견된 사소한 미비점 정리)

### 🟢 다음 세션
- Phase 10 toggle 활성화 검토 (shortcode가 이미 구현돼 있음)
- Phase 15 pipeline hook을 travel/stock까지 확장

---

## 대시보드 현황

| 항목 | 값 |
|------|-----|
| URL | http://localhost:5050 |
| 통합 사이트 | 47개 (38 5000 + 7 SAP + 2 aikorea24) |
| Site Health | 38/38 online |
| launchd | com.5000.dashboard (실행 중) |
| quality-aggregate | com.5000.quality-aggregate (매일 03:00) |
