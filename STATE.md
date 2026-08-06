# State File — Resume Status

**Generated:** 2026-08-07 (실체 동기화 세션 — 문서만 갱신한 재작업 아님)
**Session:** Phase 58/60 포함 후속 구간 실체 확정 + STATE/continue-here/SUMMARY 동조

---

## Current Phase Status (Code-Backed)

| Phase | Status | 실제 코드/DB/git 증거 | 
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
| Phase 43 Blog Expansion | ✅ Complete | 4개 블로그 제목 로직 복구 + food fetch str 버그 수정 |
| Phase 49 CUAP Cross-link Bugfix | ✅ Complete | Wave 1: url return + file-based slug fallback + sparse card warning. Wave 2: 14 wrong-slug entities deleted, 143 baked cross-link hrefs fixed across 38 files/10 blogs |
| Phase 58 | ✅ Complete | `.planning/phase-58-publish-problem-telegram-alerting/SUMMARY.md` 존재, PLAN.md+CONTEXT.md 존재, `shared/problem_registry.py`, `shared/problem_detectors.py`, `shared/problem_monitor.py` 존재, 관련 커밋 다수(2026-08-06) |
| Phase 59 | ✅ Complete | `.planning/phase-59-ops-dashboard-and-unification/` 요약 다수 존재, ops_dashboard 인프라(app.py, checks/*, db.py, readiness.py, investigate_publish.py) 존재 |
| Phase 60 | ⚠️ 부분 완료(문서+일부 산출) | `.planning/phase-60-publish-investigation-and-hardening/PLAN.md` 존재, SUMMARY.md 부재, PLAN Part 1~6 있음. 조사 스크립트(investigate_publish.py) 존재, S1 태그(pre-refactor-baseline) 존재, S2/S3 일부 반영(ops.db 스키마·체크·스냅샷), Part 3~6 커밋 존재. **Summary 미완** |
---

---

## 문서 vs 코드 불일치 (고정; 이번 세션에 동기화 대상)

| 문서 | 문제 | 조치 |
|------|------|------|
| ROADMAP.md | "3 phases", Phase 6/7/11/13-15 누락 | ✅ ROADMAP.md 재작성 |
| STATE.md | Phase 11-12 = deferred (틀림) | ✅ 본 문서로 수정 |
| SESSION_STATUS.md | Phase 11 blocker 3개 (이미 해결됨) | 아래 업데이트 |
| REQUIREMENTS.md | 모든 status = Pending (10개 전부) | 아래 업데이트 |
| STATE.md(옛판) | 마지막 Phase 49, 2026-07-26로 표시 | ✅ 이번 세션에 Phase 58/59/60 + CUAP 복원 구간 반영 |
| .continue-here.md(옛판) | Phase 31 마무리 기준, 다음 Phase 32 미플래닝으로 표기 | ✅ 이번 세션에 현재 재개 지점(CUAP 복원 완료 후 P1/P2/P3)으로 갱신 |
| PROGRESS-2026-08-07-session.md | P1 내부 "STRUCT-08/09 resolved / 18→16건"과 문서 전반의 "M01/M07 무력화 후속 큐"가 공존 | ⚠ 상충 있음. 실측 결과로 통일 필요(아래 노트 참조) |
| INDEX.md | 최신 entry 2026-08-05, Phase 58/60·STRUCT 다수 누락 | ✅ 이번 세션 말미에 이번 세션 트라이애지 추가 |
| Phase 60 SUMMARY.md | 부재 | ✅ 이번 세션에 생성 |

---

## Recently Completed (Phase 49 이후 역할 구분)

- Phase 49까지는 이전 STATE.md 유효. 아래는 2026-07-27~08-07 사이 진행된 주요 구간이다.

### Phase 58 — Publish-problem Telegram alerting (완료)
- PLAN.md + SUMMARY.md 존재(`.planning/phase-58-publish-problem-telegram-alerting/`)
- 산출: `shared/problem_registry.py`, `shared/problem_detectors.py`, `shared/problem_monitor.py`
- RELATED COMMIT SEQ: 2026-08-06에 research/PLAN/구현 커밋 다수

### Phase 59 — Ops dashboard & unification (완료)
- `.planning/phase-59-ops-dashboard-and-unification/` 요약 다수 존재
- 산출: `ops_dashboard/` 인프라(app.py, checks/*, db.py, readiness.py, investigate_publish.py, snapshots 등)

### Phase 60 — Publish investigation & hardening (부분 완료, 요약만 미완)
- PLAN.md 존재, SUMMARY.md 부재(작업 3에서 생성)
- S1 태그 `pre-refactor-baseline`(d85095152) 존재
- Part 1 조사 스크립트 `ops_dashboard/investigate_publish.py` 존재 및 1회 실행됨
- S2/S3 일부 반영: ops.db 스키마·checks·스냅샷 계보 존재(post-dashboard-baseline, post-refactor-baseline)
- Part 3~6 관련 커밋 2026-08-06에 존재
- content.db 복구 관련: 요약 파일·워크로그·DB 증거파일 다수 존재(작업 1·2 참조)

---

### CUAP 복원·발행재개·INC-CL (Phase 49 이후 별도 실측 구간)
- CUAP 후보 10+ 블로그: 2026-08-01 이후 전부 발행 시도 중 + 성공도 발생. 중단이 아니라 **실패 동반 정상 가동**. (Part 1 조사 결론과 일치)
- senior 계열 / travel4-hugo: 2026-08-01 이후 success 0. 원인 axis는 서로 다름(senior 계열: publish_error 위주 / travel4-hugo: no_result 위주).
- "INC-CL 74건 재렌더" 표현: 스크립트 `scripts/render_inc_cl_fix.py` 존재하나, content.db 유사제목 stage 총합은 CUAP 후보 기준 30건. 74는 다른 집계·로그 카운터일 가능성 높음(문서 통일 필요).
- pet-hugo M01/M07: maintenance_checklist(ops.db)에 pass/fail 기록 존재. pet-hugo 최근 발행 제목에 `智能玩具` 문자열은 (최신 5건 기준) 등장하지 않음.

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

### 5. STRUCT-08/09 상충 (문서 간)
- PROGRESS-2026-08-07-session.md는 "STRUCT-08/09 resolved / 18→16건"이라 적음
- 반면 같은 세션 산출물 맥락에서 "M01/M07 무력화 후속 큐"가 별도로 남아 있음
- 실체 기준 판단 근거:
  - ops.db known_issues에는 STRUCT-08, STRUCT-09가 **존재하며 둘 다 gsd_status='resolved', resolution_status='resolved'**
  - 따라서 현재 ops.db 기준으로는 STRUCT-08/09 resolved가 사실
  - 다만 PROGRESS 본문 서술("resolved 처리 → open_known_issues 18→16건")과 실제 ops.db open 수(25) 사이의 숫자는 별도 확인 대상(문서의 과거 스냅샷 vs 현재 DB 차이 가능)
  - 결론: "M01/M07 감지 자체가 무력"이라는 서술은 현행 코드·ops.db 실체와 불일치. "무력화 후속 큐"는 오보고 정정/정리 대상으로 보는 쪽이 FACT에 가까움
- 문서 통일 방향: "M01/M07 감지 자체는 콘텐츠DB 직접 연결로 작동 중. 과거 오보고(무력/항상 pass)는 정정. stale fail(정오탐)은 개별 정리 대상"으로 통일

### 6. INDEX.md·continue-here·STATE 시차
- INDEX.md 최신 entry: 2026-08-05. 최신 커밋(2026-08-07)과 시차 있음
- STATE.md/continue-here는 2026-07-22~07-26 시점 기준으로 남아 있었음 → 이번 세션에 최신화

---

## uncommitted changes (작업 중 — 2026-08-07 실체 동기화 시점)

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

## uncommitted changes (작업 중 — 2026-08-07 실체 동기화 시점)

```
 M STATE.md   (실체 동기화 갱신)
 M ops_dashboard/db.py   (SEED_ISSUES 내 STRUCT-08/09 증상 설명 정정 — 로직 변경 아님, diff 6줄)
 M ops_dashboard/investigate_publish_result.json   (Part 1 조사 JSON 재실행 산물)
 M shared/publishers/hugo_writer.py   (실체 확인 후 처리 필요)
?? .planning/PROGRESS-2026-08-07-session.md
?? .planning/QUEUE-next-sessions-2026-08-07.md
?? .planning/stash-QUEUE.md
?? scripts/render_inc_cl_fix.py
?? pipelines/curation/keywords.ts
?? data/content.db.EVIDENCE_polluted_20260806
?? data/content.db.clean_before_recovery_20260806_204047
?? data/content.db.r2_20260806_0500
?? data/ledger_title_fix_backup.jsonl
?? data/stash-archive/
?? ops_dashboard/ops.db-shm
?? ops_dashboard/ops.db-wal
```

- 신규 산출물(.planning/*.md, scripts/render_inc_cl_fix.py, pipelines/curation/keywords.ts)은 작업 4 방침에 따라 커밋 대상.
- DB 증거/백업 파일(content.db.EVIDENCE/clean/r2, ledger_title_fix_backup.jsonl, stash-archive)은 .gitignore 패턴 매칭상 현재는 스테이징될 수 있는 상태이나, 운영 정책상 git 추적 대상으로 보지 않음(위치·의미만 STATE/노트에서 관리).

---

## 추천 Next Action (실체 동기화 후)

### 🟡 즉시
- Phase 60 SUMMARY.md 생성(작업 3): Part 1~6 실제 산출물·결론·잔존 이슈 정리, INDEX.md에 이번 세션 트라이애지 추가
- PROGRESS-2026-08-07-session.md 상충 정리: STRUCT-08/09는 "감지 자체는 작동 중, stale 정오탐 정리 대상"으로 통일

### 🟡 이번 세션 잔여
- P1: M01/M07은 감지 무효가 아니라 콘텐츠DB 직접 연결형. 필요면 stale fail 정오탐 정리 + 크롤 검증 regex 관대화 검토
- P2: R04(GA4 10) / R06(in-article 19, auto) / standard_compliance 실제 값 재확인 준비
- P3: CAP→SEAP→TAP 순서는 유지하되, SEAP/TAP 발행경로(Hugo vs Blogger/WordPress) 확인 선행
- P4: stash 2건, cover 죽은필드·og:image//슬래시 버그, 부모repo 미추적 5블로그 정리

### 🟢 별도 이슈로 분리
- senior 계열·travel4-hugo 8/1 이후 success 0건: CUAP 복원과 무관한 별도 이슈로 등록
  - senior 계열: publish_error 축 (50+50건 규모)
  - travel4-hugo: no_result 축 (29건)
- "INC-CL 74건" 표현: 30건(유사제목 stage)과 불일치. 74의 출처(스크립트 로그 카운터 등) 확인 후 문서 통일

### 🟢 향후
- Phase 12 validate_keyword() 보완
- Phase 10 shortcode toggle 검토
- Phase 15 hook travel/stock 확장
- travel3-hugo 본문 길이 모니터링

---

## 대시보드 현황

| 항목 | 값 |
|------|-----|
| URL | http://localhost:5050 |
| 통합 사이트 | 47개 (38 5000 + 7 SAP + 2 aikorea24) |
| Site Health | 38/38 online |
| launchd | com.5000.dashboard (실행 중) |
| quality-aggregate | com.5000.quality-aggregate (매일 03:00) |
