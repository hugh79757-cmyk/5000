# 세션 결과 보고 (2026-08-07) — 대시보드 신뢰성 복원 + 준비도 정리 + 후속 큐

## 개요
- 운영 방식 (A) 정상 발행 재개로 시작.
- P1: 대시보드 신뢰성 복원(M01/M07)
- P2: 준비도 녹색화(표준준수율·stale·known_issue)
- P3: 후속 분기 진입 틀(CAP 본문·SEAP 썸네일·TAP 전수)
- P4: 잔무(stash·5블로그 사이트 파일)

---

## P1 — 대시보드 신뢰성 복원 (완료)

### 1) M01/M07 상태 재확인
- M01/M07은 무력이 아니라 **콘텐츠 DB 직접 연결형으로 이미 작동 중**이었음.
  - `_check_cjk_in_title`: content.db publish_ledger + curation.db publish_log 직접 조회 → CJK 검사
  - `_check_similar_title_safety`: content.db publish_ledger에서 similar_title fail 카운트
- maintenance_checklist(ops.db)에는 이미 fail 기록도 존재:
  - M01 fail: pet-hugo (과거 CJK 제목 智能玩具)
  - M07 fail: pet-hugo 1건, kitchen-hugo 1건, interior-hugo 8건, beauty-hugo 4건

### 2) pet-hugo M01 stale fail 정리
- 원인: content.db + curation.db publish_log 양쪽에 과거 CJK 제목(智能玩具) 행이 남아 있었음.
- 처리: title만 한국어화 정정(智能玩具 → 장난감), 실발행 행 삭제 아님.
  - content.db publish_ledger rowid=49850 정정
  - curation.db publish_log rowid=2121 정정
  - 백업: data/ledger_title_fix_backup.jsonl
- 결과: pet-hugo M01 pass 전환.
- pet-hugo M07 fail(1건)은 similar_title 실제 차단 이력 → 유지.

### 3) STRUCT-08/09 정정
- 내용: “무력/항상 pass” → “콘텐츠 DB 직접 연결형, fail 감지 작동 중”으로 정정.
- known_issue: STRUCT-08/09 resolved 처리 → open_known_issues 18→16건.

### 4) 스케줄러
- 8/6 20:40 이후 중단. 마지막 로그: laptop-hugo quota skip.
- startup 체크(dependency/syntax) 통과 → 코드상 즉시 사망 가능성 낮음.
- 중단 원인 미확인(외부 종료/터미널/절전 가능성). 재개는 안전 장치 확보 후로 보류.
- 현재 launchd job `com.sap.scheduler`는 SAP용이라 5000과 무관.

---

## P2 — 준비도 녹색화 (정리/일부 완료)

### 현재 readiness 지표
- standard_compliance: pass=1 / fail=7 / unknown=1 / deferred_blocks=16 / deferred_count=19 / out_of_scope_blocks=0 / out_of_scope_count=11 / total=25 / ratio=12.5% / green=False
- stale_active_blogs: count=3 (senior-blogger 9일, senior-hugo 8일, travel4-hugo 9일) / green=False / excluded=5
- open_known_issues: count=16 / green=False

### R06 (deferred, STRUCT-16)
- CUAP 15블로그 in-article.html 전부 data-ad-format=auto (sha256 동일, 파일 15개).
- STANDARD(Guideline)는 fluid. 콘솔 슬롯 형식 미확인 → 수정 시 광고 깨질 위험 → deferred 유지.
- Path B(콘솔 슬롯 형식 확인) 후속 등록. 지금 자동→fluid 일괄 변경은 안전하지 않음.

### R04 (out_of_scope, STRUCT-17)
- GA4 10건. Analytics 사안, AdSense 수익과 직접 무관 → 별도 이관.

### stale 3개 (확인/사유 정리)
- senior-blogger: brand=seap, maintenance=awaiting, config=active, site_path 없음, domain=2.techpawz.com
- senior-hugo: brand=seap, maintenance=in_progress, config=active, site_path=/Users/twinssn/Projects/SEAP/senior-hugo
- travel4-hugo: brand=tap, maintenance=awaiting, config=paused, site_path=/Users/twinssn/Projects/TAP/travel4-hugo
- 해소하려면 각 블로그 상태 정비(SEAP/TAP 소관) 필요 → P2에선 확인/사유 정리까지.

### known_issue
- STRUCT-08/09 resolved로 18→16건.
- 나머지 structural 이슈(STRUCT-07/10~18 등)는 이번 P2 범위 밖 → 유지.

### P2 결론
- 표준준수율은 R06 보류로 지금 녹색화 어려움. 대신 deferred 상태 명확화 + Path B 등록.
- stale/known_issue는 녹색화 대상이긴 하나, 실제 해소는 SEAP/TAP 재개/정비가 선행.
- 이번 P2로 얻은 것: 지표 실체와 원인 연결, R06/R04 보류 사유 명확화, STRUCT-08/09 정정.

---

## P3 — 후속 분기 진입 틀 (정리)

### 재사용할 CUAP 절차/스크립트
- 키워드 정화: pipelines/curation/keywords.py, scripts/maintain_keyword_pool.py
- 썸네일: scripts/batch_thumbnails.py (+ shared/thumbnail_generator/generator.py)
- 엔티티/크로스링크: shared/cuap_entity_linker.py, scripts/init_cuap_link_graph.py, register_sample_cuap_entities.py, scan_all_crosslinks.py, fix_cuap_*.py
- CTA/광고: fix_cta_links.py, pipelines/curation/pipeline.py(build_cross_sell_card/build_funnel_header)
- 재렌더: scripts/render_inc_cl_fix.py

### 진입 순서 (CUAP 재사용)
1. 키워드 정화
2. 파일럿 발행 1건
3. 검증(M01/M04/Q1·P14 등)
4. 확대

### 대상별 주의
- CAP 본문: curation 파이프라인 자체 → 위 순서 그대로 적용 가능.
- SEAP 썸네일: batch_thumbnails 절차 적용 가능하나, SEAP 발행 경로/파이프라인 확인 선행.
- TAP 전수: 여행 계열이라 파이프라인이 CUAP와 다름. CUAP식 전수 스캔/정화 절차는 적용 가능하나, 발행 플랫폼(Hugo vs Blogger/WordPress) 차이로 절차 변형 필요.

---

## P4 — 잔무

### stash 2건
- 아카이브: data/stash-archive/stash-0-fd016b3a3.diff, stash-1-c0df11b38.diff
- 분류표/보류/적용금지: .planning/stash-QUEUE.md
- drop: 보류분 포함이라 아직 안 함 (보류분: curation pipeline +151, keywords.py 신규 블로그, travel/writer.py 품질개선 등)
- 적용 금지: stash@{1} dispatcher.py(--config 제거), AGENTS.md(wrangler --config 버그 문서) — 이번 배포 성공과 충돌

### 5 CUAP 블로그 사이트 파일 부모 repo 추적
- 5000 git에서 CUAP 블로그 layouts/ 파일은 추적 안 됨 (CUAP은 cuap/ 독립 git repo).
- 신규 5블로그(massage/car/homeappliance/golf/bike) 사이트 파일도 각 repo에 존재.
- 판단: 지금 당장 5000에 중복 추적하지 않음 (CUAP 독립 repo 구조 + 중복 관리 회피).
- 대신 중앙 표준화 대상(AdSense 템플릿/CTA/거미줄 링크 partial 등)이 있다면 그걸 5000에 두고 배포/복사로 반영하는 구조가 적합. 이번 세션에선 결정만 하고 실행은 안 함.

---

## 다음 세션 진입점
1. P1 재개: 스케줄러 중단 원인 확인 후 scheduler.py 재개(안전 장치 확보 후).
2. P2 Path B: R06 콘솔 슬롯 형식 확인 → auto→fluid 변경 가능 여부 판단.
3. P3: CAP/SEAP/TAP 중 우선 대상 정해 CUAP 절차 재사용 실행.
4. P4 보류분: stash keywords.py 신규 블로그/가독성 개선/ travel writer 품질개선 취사선택.
