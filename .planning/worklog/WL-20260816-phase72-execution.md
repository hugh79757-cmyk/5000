# WL-20260816-phase72-execution

> 날짜: 2026-08-16 / 연관: Phase 72 Wave 2c (SC-4, detect-only) / 상태: 완료

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 17:44 | 신규 detect-only check 3종 + indexnow.py 경고 추가 (모두 additive, 자동수정/배포 없음) | edit scripts/indexnow.py, 신규 checks/indexnow.py·semantic.py, 수정 checks/render.py | 0 (신규/추가만) | git stash relevant files | import OK, 3 check 등록, 기존 checks 유지 | 기존 check 함수/register_check 보존, 자동수정 로직 0건 |

## 4단계 프로토콜 이행
1. 사전 카운트: N/A — 신규 코드 추가만 (기존 동작 변경 없음, non-destructive).
2. 되돌림 수단: `git stash` (해당 파일만 보관), 기존 checks/__init__.py 등록 줄 외부 수정 없음.
3. 실행: Wave 2c Tasks 4.1–4.4 구현.
4. 사후 대조: `from ops_dashboard.checks import run_all_checks` import OK; `indexnow`·`semantic` 등록 확인; 샘플 블로그(compare-hugo) 대상 check_indexnow/check_semantic 실행 예외 없음; render `_check_adsense_publisher_id` mismatch/ok fixture 검증 통과.

## 결과 / 보존 대상 확인
- checks/__init__.py 등록: indexnow, semantic 추가 (render는 기존 check_render_health에 로직 편입, 별도 register 불필요).
- indexnow.py: 연속실패 추적 + 403/연속3회 게이팅 경고(send_dashboard_alert) + data/indexnow_last_status.json 기록. 재시도/자동수정 없음.
- semantic.py: SEM-Q1/Q2/Q3 보수적 키워드 휴리스틱, detect-only.
- render.py: AdSense Publisher-ID ↔ 도메인 계열(AGENTS.md §1) 교차검증 추가, 불일치 시 ADSENSE-ID-MISMATCH fail. 자동수정 없음.

## 잔존 위험
- semantic 휴리스틱은 키워드 기반이라 의도된 건강/효능 표현을 오탐할 수 있음(임계값을 금지어 위주로 보수 설정했으나 0 오탐 보장 안 됨) — 사람 리뷰 대상.
- indexnow 상태 파일은 scripts/indexnow.py 실행 시에만 갱신됨. 스케줄러가 indexnow.py를 주기 실행하지 않으면 상태가 stale되어 check가 pass로 분류됨(24h staleness 게이트 적용).
- AdSense 교차검증은 정적 ca-pub 불일치만 포착(헤드리스 렌더 여부는 별도 phase) — 실제 슬롯 미렌더는 잡지 못할 수 있음.

## Wave 2d (SC-6) — 데이터 기반 레지스트리 (17:46 추가)
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 17:46 | config/problems.yaml+rules.yaml 단일소스 + registry_loader 오버레이 배선 | 신규 config/problems.yaml,config/rules.yaml,shared/registry_loader.py,scripts/gen_playbook_index.py / 수정 shared/problem_registry.py(additive fields+import hook),ops_dashboard/registry/__init__.py(RULES.extend),shared/problem_monitor.py(send_problem_alert friendly),ops_dashboard/db.py(get_registry_view friendly) | P01-32+R01-12 (기존 코드 dict 유지=fallback) | cp problem_registry.py,registry/__init__.py → /tmp/*.bak_20260816 | import OK, P33 YAML추가→lookup_problem OK(코드변경0), PLAYBOOK_INDEX 재생성 47 codes | 기존 32 P-code 동작 동일(regression diff 0, PASS); PROBLEM_REGISTRY 코드 dict 보존 |

### 결과
- 단일 소스: config/problems.yaml(P01-32+unknown_failure 33건, friendly 필드 포함) + config/rules.yaml(R01-12+THUMBNAIL-01+R2-01 14건).
- 오버레이: apply_problem_yaml() YAML 우선 덮어쓰기(PROBLEM_REGISTRY), apply_rule_yaml() 신규 id만 append(idempotent). 모두 try/except.
- friendly 렌더: 텔레그램 알림 본문에 summary_human+summary_llm JSON 블록 추가, /api/registry entry에 summary_human/how_to_add/automation_level 노출.
- PLAYBOOK_INDEX.yaml 이제 YAML derived artifact (source_files 2개 YAML).
- 잔존 위험: summary_human/summary_llm 문구는 빌드 스크립트가 name_ko+one_line_action에서 파생 생성(자동) — 운영자가 필요시 YAML에서 수동 다듬기 가능. rules.yaml은 기존 RULES 동작을 대체하지 않음(추가 전용).

## Wave 2a (SC-2) — ETAP 잔여 정비 (17:50 추가, 안전등급만)
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 17:50 | ETAP 36블로그 전수 스캔 → score<70 잔여 추출 → 안전등급(프론트매터)만 소거 | pipelines.etap.quality_scanner.score_post 전수 호출 + FIXERS['fix_draft_true'] 적용(airlines/eurail/trains/visa) | blogs=36, posts=5154, posts_lt70=363, blogs_lt70=34, safe={draft_true:7}, body={word_count:216,h2:299,image:308,disclaimer:239,bad_url:248,data_error:45,banned:33} | cp 4블로그 content → /tmp/etap-wave2a-backup-20260816-174947 (5.9M) | posts_lt70=363→361, safe={} (draft 잔여 0), 모든 edited 파일 frontmatter 유효·draft:true 0건·parse error 0건 | 본문 미편집(키 삭제만), 위험등급/본문이슈 pending 유지 |

### 4단계 프로토콜 이행
1. 사전 카운트: 위 표 사전카운트 — score<70 잔여 363건 중 안전등급은 draft_true 7건뿐, 나머지 356건은 본문 텍스트 이슈(워드수/H2/이미지/disclaimer/미인가URL/데이터오류/banned)로 자동수정 불가(사람 게이트).
2. 되돌림 수단: /tmp/etap-wave2a-backup-20260816-174947 (4블로그 content 사본 5.9M). ETAP는 별도 git repo 아님 → 파일복사 백업.
3. 실행: FIXERS['fix_draft_true'] 를 4블로그에 적용 (draft:true 키 삭제 7건: airlines 1, eurail 1, trains 3, visa 2). featureimage_broken=0, title_missing=0 이므로 fix_featureimage/fix_frontmatter_missing_keys 는 no-op 또는 score 무관(4542건 tags 누락이나 score 영향 0)이라 미적용(오프골·대량변이 회피). R04/R06/R08/R12/R2-01은 _AUTOFIX_SAFE_ACTIONS 제외(위험등급) → 미적용.
4. 사후 대조: 재스캔 posts_lt70 363→361 (2건만 70↑ 도달, 5건은 본문이슈 잔존으로 <70 유지). safe_types={} (안전등급 잔여 0). 34블로그 모두 여전히 score<70 잔존(전부 본문이슈).

### 결과 / 보존 대상 확인
- 안전등급 처리 완료: draft:true 7건 제거, 재발 방지(잔여 0).
- featureimage/title 정화: 대상 0건.
- 361건 score<70 잔여 = 전부 본문 텍스트 이슈 → 사람 게이트(pending_fixes 'proposed' 대상, 자동적용 금지).
- git push / wrangler deploy 미실행(하드룰 준수). 본문 미편집.

### 잔존 위험
- SC-2 (score<70=0) 는 안전등급만으로 달성 불가 — 361건이 본문 텍스트 편집(워드수↑/H2↑/이미지삽입/disclaimer추가/미인가URL제거/데이터오류수정/banned제거) 필요. 본 작업 범위(본문편집 금지) 밖 → 사람 게이트. 근거있는 명시 예외로 분류.
- fix_frontmatter_missing_keys 미적용: 4542건이 tags/description 등 누락이나 quality_scanner는 title만 페널티(title 누락=0) → score 무관. 대량 프론트매터 변이(4542파일)는 오프골이라 의도적 생략. 운영자가 원하면 별도 wave에서 적용 가능.
- tours-hugo 85건, eurail 26건, trains 28건, ferry 18건, bus 19건 등이 잔여 집중 — 사람 정비 우선순위 후보.

## WL-20260816-frontmatter-detect (GAP-close Wave 2b)
- 파일: ops_dashboard/checks/frontmatter.py 생성 (check_frontmatter, @register_check(\"frontmatter\"))
- 등록: ops_dashboard/checks/__init__.py 에 frontmatter import 블록 추가 (indexnow/semantic 방식 미러)
- 라우팅: 실패 시 rule_id(FM-DRAFT/FM-MISSINGKEYS/FM-FEATUREIMAGE)를 check_results 에 dual-write → dispatcher._auto_fix_on_fail 가 rule_id 로 fixer 매핑(_AUTOFIX_RULE_TO_ACTION) 발화
- 검증: run_all_checks import OK, CHECKS[\"frontmatter\"] 등록 확인; airlines-hugo 직접 실행 → dict 반환, 예외 없음 (FM-DRAFT 미발화=정상, FM-MISSINGKEYS 1건 실제 감지)
- 범위: 탐지만. autofix/deploy/dispatcher 미호출, 라이브 콘텐츠 미수정, git/wrangler 미실행
