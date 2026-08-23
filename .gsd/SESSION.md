# Project 5000 — Golden Standard 통일화 세션 문서
> 이 파일은 세션 간 맥락 전달의 SSOT이다.
> 새 세션 시작 시 이 파일을 먼저 읽어라.

## 1. 현재 상태 (Last Updated: 2026-08-24 17:10 KST)

- **Phase:** Phase Wave 2 — 81 pass 목표 (85 중 Blogger 4 제외) — Wave 2-A 완료, 2-B 부분 완료
- **Status:** Wave 2-A 완료 (michelin R05 top.html 복원 → ETAP 36/36 pass) / Wave 2-B 7건 즉시 해소(compare R01, pet R06+R04, informationhot R07/R08/R12, senior/issue-techpawz R12, camping/interior R19) → 70 pass / 11 fail / 4 unknown. 잔존 11건은 콘텐츠 트랙(R13/R17/THUMBNAIL/R2-01)
- **Blocker:** 11 fail (STAP R13/R17, RAP R13, TAP THUMBNAIL/R2, pet 해결됨) — 콘텐츠 이미지/R2/트위터 파이프라인 보강 필요 / OQ#1 / Wave 3 콘텐츠 QC 대기
- **진입점:** `ops_dashboard/app.py:create_app()` → `python -m ops_dashboard.app` (:5060, Basic Auth)
- **SSOT DB:** `ops_dashboard/ops.db` (17 테이블, 전체 85 재검사, 70 pass/11 fail/4 unknown, ETAP 36 전원 pass)

## 2. 완료된 것 (Done)

| 날짜 | 작업 | 산출물 경로 | 검증 방법 |
|------|------|-------------|-----------|
| 2026-08-15 | Golden Standard yaml 정의 (19개 global) | `config/quality_checklist.yaml:313` (global_standard 19개, r2_exempt_domains 5개) | `grep -c "  - id:" quality_checklist.yaml` = 19 |
| 2026-08-15 | brand_standards 스켈레톤 7분기 채움 | `config/quality_checklist.yaml:435` (cap/cuap/stap/tap/rap/seap/etap) | yaml 실값 확인, 단 tap/rap/seap/etap 4개 AD_INSERT 누락 |
| 2026-08-15 | autofix 6개 구현 및 병합 (Wave 5) | `shared/autofix/r04.py, r06.py, r08.py, r12.py, r2.py, thumbnail.py` + `shared/autofix/__init__.py:91 FIXERS` | `git log a788f0bbc` / `ls shared/autofix/` |
| 2026-08-15 | Phase 71 코드 일부 병합 (Wave 1-5) | `a788f0bbc`, `5d19759df` 등 (dispatcher auto_fix_hook, schema_loader) | `git log --oneline` |
| 2026-08-22~23 | ETAP F1~F13 대표 블로그 수동 15항목 통과 | `docs/superpowers/specs/2026-08-22-golden-standard-status.md` (13/13 ✅) | 문서 내 커밋 hash 421df11b 등 + 라이브 curl |
| 2026-08-23 | 룩북/플레이북/레시피 문서 생성 | `docs/lookbook/ERROR_LOOKBOOK.md` (ERR-001~020, 11169B) / `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md` (P01~P31) / `docs/APPENDIX_C_FIX_RECIPES.md` (R01~R12,C01~C09) | `ls docs/lookbook/` / `grep -c playbook_ref shared/problem_registry.py` = 35 |
| 2026-08-23 | CAP/RAP/SEAP/STAP 분기 표준화 specs | `docs/superpowers/specs/2026-08-23-{cap,rap,seap,stap}-standardization.md` | git log 086fad072 등 |
| 2026-08-23 | 대시보드 SSOT 골격 (17 테이블, 21 checks) | `ops_dashboard/db.py` (check_results, pending_fixes 등) / `ops_dashboard/checks/__init__.py:19 CHECKS` 21개 / `ops_dashboard/registry/rules.py` 30개 | `sqlite3 ops.db .tables` / `grep register_check` |
| 2026-08-23 | 85개 블로그 마스터 목록 확정 | `config/blogs.d/*.yaml` 9개 활성, 85개 엔트리 / `ops.db check_results DISTINCT blog_id` 85 일치 | `grep -c "  - id:" config/blogs.d/*.yaml` 합산 |
| 2026-08-24 | Wave 1: R12 ALLOWED 확장 (affiliate-disclosure.html + _markup/render-link.html) | `ops_dashboard/checks/standard.py:138 ALLOWED_OVERRIDES` | `dbf877522` / `python -c "import ops_dashboard.checks.standard"` OK, ETAP 13 R12 fail 해소 |
| 2026-08-24 | Wave 1: R04 etap 파이프라인 면제 (yaml exempt_pipelines + _load_exempt_pipelines) | `config/quality_checklist.yaml:359 R04 exempt_pipelines` + `ops_dashboard/checks/standard.py:701 _load_exempt_pipelines` + loop N/A 분기 | `8b8ed653a` / `check_standard_compliance(foodtour-hugo)` N/A 전이 확인, ETAP 13 재검사 12/13 pass |
| 2026-08-24 | Wave 2-A: michelin R05 top.html overflow+min-height 복원 | `ETAP/michelin-hugo/layouts/partials/adsense/top.html` (foodtour 복사) | `_check_r05` True + `run_all_checks(michelin-hugo)` pass, ETAP 36/36 완성 (`a852f83` michelin) |
| 2026-08-24 | Wave 2-B: R12 ALLOWED 8개 추가 + R04 legacy params.toml + R19 word boundary | `ops_dashboard/checks/standard.py` ALLOWED 8개(btn/dday 등+informationhot 5) + R04 params.toml 경로 + R19 \\bLLM | `6790a1e66` / 재검사 7개 pass (compare/informationhot/senior/issue-techpawz/camping/interior) |
| 2026-08-24 | Wave 2-B: 템플릿 즉시해소 7건 (R01/R06/R07/R08) | `cap/compare-hugo/hugo.toml` false, `cuap/pet-hugo/in-article.html` fluid, `informationhot single.html` prose+h2 | 재검사 pass, pet R04는 standard.py legacy 경로로 해소 |

## 3. 진행 중인 것 (In Progress)

| 작업 | 담당 | 시작일 | 다음 액션 | 블로커 |
|------|------|--------|-----------|--------|
| Phase 71 계획 미커밋 정리 | 시니어 | 2026-08-14 | `.planning/phase-71-*` git add + STATE.md 생성 | git 미추적 상태, OQ#1/OQ#2 |
| C계열 5개 fixer 구현 (C01/C03/C04/C05/C09) | — | — | `shared/autofix/fix_c0*.py` 생성 + FIXERS 등록 + dispatcher 매핑 | 선언-only 상태 (조사 2 확인) |
| AD_INSERT 4패밀리 보완 (tap/rap/seap/etap) | — | — | yaml brand_standards에 AD_INSERT 블록 추가 또는 OQ#1 보류 명시 고도화 | OQ#1 |
| 문서↔DB 결과 충돌 해소 (F1~F13) — Wave 1 완료 (michelin R05 1건 잔존) | 시니어 | 2026-08-24 | michelin R05 `top.html overflow` 수정 후 재검사 (Wave 1 잔존) | DB 12/13 pass, 1/13 fail (R05) |
| 72개 블로그 golden 이력 구축 | — | — | ETAP 13 외 72개 대상 golden 평가 기록 생성 (문서 또는 DB) | 기준 충돌 선결 필요 |
| CI/CD golden 체크 연동 | — | — | `.github/workflows/*.yml`에 `verify_quality --checklist` step 추가 | 없음 → 수동 호출만 존재 |
| autofix 단위테스트 보강 | — | — | `shared/autofix/*` 실함수 직접 호출 테스트 생성 (현재 mock 배선만) | 6개 모두 NOT FOUND |

## 4. 해야 할 것 (Backlog — 우선순위 순, 시니어 결정 대기)

| # | 작업 | 선행 조건 | 예상 산출물 |
|---|------|-----------|-------------|
| 1 | Phase 71 문서 git 커밋 + STATE.md 생성 (Planned→In Progress) | OQ#1/OQ#2 확인 | `.planning/phase-71-closed-loop-unification/STATE.md` |
| 2 | C01/C03/C04/C05/C09 fixer 구현 및 FIXERS/dispatcher 배선 | 1 | `shared/autofix/fix_c0*.py` 5개, `shared/autofix/__init__.py`, `dispatcher._AUTOFIX_RULE_TO_ACTION` |
| 3 | AD_INSERT 4패밀리 보완 (또는 OQ#1 보류 스펙 확정) | OQ#1 시니어 결정 | `config/quality_checklist.yaml` brand_standards 패치 |
| 4 | 문서↔DB 충돌 해소 — Golden Standard 단일 정의 확정 | 3 | `docs/superpowers/specs/2026-08-22-golden-standard-status.md` 개정 또는 `standard_compliance` 로직 수정 |
| 5 | 72개 블로그 golden 평가 일괄 실행 + 결과 기록 | 4 | `ops.db check_results` 갱신 또는 신규 golden_status 문서 |
| 6 | CI/CD golden 체크 연동 (`dryrun.yml`/`indexnow.yml`) | 5 | `.github/workflows/dryrun.yml` step 추가 |
| 7 | sync_golden_to_gap.py 복원 또는 GAP 미사용 스케줄 공식 비활성화 확인 | — | `scripts/sync_golden_to_gap.py` 또는 `config/` 스케줄 비활성화 문서화 |
| 8 | autofix 실함수 단위테스트 작성 | 2 | `tests/ops_dashboard/test_autofix_*.py` |
| 9 | registry 경로 불일치 해소 (주석 `registry/rules.py` vs 실제 `ops_dashboard/registry/rules.py`) | — | `config/quality_checklist.yaml` 주석 수정 |
| 10 | `.gsd/SESSION.md` prose 참조를 AGENTS.md/CLAUDE.md에 추가 | 본 문서 검토 후 | AGENTS.md L714 / CLAUDE.md L58 패치 |
| 11 | 15항목 체크리스트 본문 삽입 (golden-standard-status.md 하단) | 4 | 해당 문서 하단 리스트 복원 |
| 12 | keyboard fix — `fix_remaining.py` 중복定義 정리 (fix_r04/r06/r08 중복) | 2 | `fix_remaining.py` 제거 또는 `shared/autofix/*`로 통합 |

## 5. 핵심 참조 경로 (이 파일들만 보면 된다)

| 역할 | 경로 | 비고 |
|------|------|------|
| Golden Standard 정의 | `config/quality_checklist.yaml:313` | 19개 global + 7 brand (tap/rap/seap/etap AD_INSERT 누락) |
| Rules Registry | `ops_dashboard/registry/rules.py` | 30개 rule (R01~R12, THUMBNAIL-01, R2-01, C08, FM-*, R13~R23) — 최상위 `registry/` 아님 |
| Autofix 구현 | `shared/autofix/` | 6개 실존(r04,r06,r08,r12,r2,thumbnail) / 5개 미구현(C01,C03,C04,C05,C09) |
| 룩북 | `docs/lookbook/ERROR_LOOKBOOK.md` | ERR-001~020 (SSOT, 2026-08-23) |
| 플레이북 | `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md` | P01~P31 + M01~M11, R01~R12 절차 |
| Fix 레시피 | `docs/APPENDIX_C_FIX_RECIPES.md` | R01~R12, THUMBNAIL-01, R2-01, C01~C09 절차 (82753B, SSOT 이전 선언) |
| 패밀리 통과 현황 | `docs/superpowers/specs/2026-08-22-golden-standard-status.md` | F1~F13 13/13 pass (수동) — 단 DB 대조 시 13/13 fail 충돌 |
| 블로그 마스터 | `config/blogs.d/*.yaml` | 85개 (etap 36, curation 15, car 8, travel 8, stock 6, rap 5, senior 2, none 5) |
| 대시보드 DB | `ops_dashboard/ops.db` | SQLite SSOT, 17 테이블, `check_results` UPSERT |
| 에이전트 지시 | `AGENTS.md` (800줄) + `ops_dashboard/docs/agent-reference/` | 현재 golden 미참조 — SESSION.md 연동 필요 |
| CLAUDE 지시 | `CLAUDE.md` (65줄) | Karpathy 4원칙 — SESSION.md 연동 필요 |
| 체크 엔진 | `ops_dashboard/checks/__init__.py:19` | 21개 @register_check, run_all_checks |
| 스키마 로더 | `ops_dashboard/schema_loader.py` + `shared/standards_loader.py` | quality_checklist → standard_rules 동기화 |
| 디스패처 훅 | `dispatcher.py:924,981,1038,1106,1214` | _trigger_post_publish_checks / _auto_fix_on_fail / execute_pending_fix |

## 6. 의사결정 로그 (Decision Log)

| 날짜 | 결정 | 근거 | 결정자 |
|------|------|------|--------|
| 2026-08-15 | Golden Standard 19개로 확정 (요청 22개 불일치) | yaml 실측 19개, 22 근거 없음 — 사실 기반 채택 | 시니어 (yaml) |
| 2026-08-15 | brand_standards 7분기 스켈레톤, OQ#1 세부 보류 | `funnel_stage/managed_by/ETAP업종분할` 시니어 결정 대기 | 시니어 |
| 2026-08-15 | SAFE autofix만 무인, 파괴등급은 pending_fixes proposed | `dispatcher._AUTOFIX_SAFE_ACTIONS` 화이트리스트 | 시니어 |
| 2026-08-23 | 룩북 SSOT를 ERROR_LOOKBOOK.md(ERR-001~020)로 단일화, APPENDIX_C는 원본 유지 | APPENDIX_C 본문 "SSOT는 이제 lookbook" 선언 | 시니어 |
| 2026-08-23 | ETAP F1~F13 15항목 수동 통과로 골든 확정 | 라이브 curl + 문서 커밋 421df11b 등 | 시니어 |
| 2026-08-24 | Wave 1: Golden 2트랙 중 Track A(R12/R04) 최소 변경으로 ETAP 13 DB pass 전환 (R12 ALLOWED +2, R04 etap 면제 yaml 기반, run_all_checks 재검사 12/13 pass) | 설계안(a) 루프 N/A + r2_exempt_domains 패턴 재사용, brand 기반 면제, DB 권위 | 시니어(대표 결정) + 주니어 구현 |
| — | (추가 결정 시 본 섹션에 append) | — | — |

## 7. 알려진 불일치/부채 (Known Debt)

| # | 내용 | 영향 | 해소 계획 |
|---|------|------|-----------|
| 1 | 항목 수 불일치: 요청 22 vs 실측 19 | 문서 혼선 | SESSION.md 본 문서로 정정, yaml 유지 |
| 2 | 1:1 매핑 불성립: yaml 19 vs registry 30 (공통 14, yaml-only 5, registry-only 16) | 표준 강제 불가 | C계열을 registry로 편입하거나 yaml에서 분리 명시 (Backlog #2) |
| 3 | C계열 5개 fixer 부재 (C01/C03/C04/C05/C09 선언-only) | 해당 불량 자동수정 불가 | Backlog #2 |
| 4 | AD_INSERT 4패밀리 누락 (tap/rap/seap/etap) | 4분기 광고 표준 강제 구멍 | Backlog #3 |
| 5 | 문서↔DB 충돌: F1~F13 문서 pass 13/13 vs DB 13/13 fail → Wave 1 해소 완료 (12/13 pass, 1 fail R05 잔존, 커밋 dbf877522/8b8ed653a) | Golden 정의 불명 → DB 권위 확정, R04/R12 해소로 해소 | Wave 1 완료, michelin R05 잔존은 Backlog #4 잔존 |
| 6 | 72개 블로그 golden 이력 부재 (ETAP 13 외) | 85개 적용 현황 집계 불가 | Backlog #5 |
| 7 | Phase 71 미커밋 (CONTEXT/PLAN/SUMMARY 미추적, STATE 없음) | 진행상태 추적 불가 | Backlog #1 |
| 8 | autofix 단위테스트 부재 (6개 모두 mock 배선만) | 수정 신뢰성 미검증 | Backlog #8 |
| 9 | sync_golden_to_gap.py 완전 부재 (GAP 미사용 방치) | GAP 파이프라인 고장 방치 | Backlog #7 |
| 10 | CI/CD golden 미연동 (Actions 0건) | 자동 검증 없음 | Backlog #6 |
| 11 | registry 경로 불일치 (주석 vs 실제) | 신규 참여자 혼선 | Backlog #9 |
| 12 | 15항목 리스트 본문 부재 (#9~#12 번호 자체 없음) | 재현 불가 | Backlog #11 |
| 13 | fix_remaining.py 중복定義 (fix_r04/r06/r08 중복) | 유지보수 혼선 | Backlog #12 |
| 14 | .gsd/SESSION.md AGENTS/CLAUDE 미연동 | 세션 연속성 수동 | Backlog #10 |
| 15 | OPS DB 코드-문서 상충: 코드는 08-15 병합, 문서는 Planned | Phase 상태 불일치 | Backlog #1에서 STATE 정정 |

---
*이 파일은 git 추적 대상이다. 수정 시 커밋하라. 새 세션은 이 파일을 먼저 읽고, 작업 완료 시 해당 섹션을 업데이트하라.*
