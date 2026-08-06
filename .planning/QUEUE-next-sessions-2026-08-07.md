# P1/P2/P3 진행 기록 (2026-08-07)

## P1 — 대시보드 신뢰성 복원
- M01/M07은 무력이 아니라 콘텐츠 DB 직접 연결형으로 이미 작동 중이었음.
  - `_check_cjk_in_title`: content.db publish_ledger + curation.db publish_log 직접 조회 → CJK 검사
  - `_check_similar_title_safety`: content.db publish_ledger에서 similar_title fail 카운트
- pet-hugo M01 stale fail 정리:
  - content.db publish_ledger(rowid=49850) title 정정: 智能玩具 → 장난감
  - curation.db publish_log(rowid=2121) title 정정: 동일
  - 백업: data/ledger_title_fix_backup.jsonl
  - 결과: M01 pass 전환
- pet-hugo M07 fail(1건)은 similar_title 실제 차단 이력 → 유지 (건드리면 안 됨)
- interior(9)/beauty(4)/kitchen(2) M07 fail도 실제 차단 이력 → 유지
- STRUCT-08/09 설명 정정: “무력/항상 pass” → “콘텐츠 DB 직접 연결형, fail 감지 작동 중”
- STRUCT-08/09 known_issue resolved 처리 (18→16건)
- 스케줄러: 8/6 20:40 이후 중단, startup 체크 통과, 원인 미확인(외부 종료 가능성). 재개는 안전 장치 확보 후로 보류.

## P2 — 준비도 녹색화 (녹색 가능 지표 우선)
- 현재 readiness:
  - standard_compliance: pass=1 / fail=7 / unknown=1 / deferred_blocks=16 / deferred_count=19 / out_of_scope_blocks=0 / out_of_scope_count=11 / total=25 / ratio=12.5% / green=False
  - stale_active_blogs: count=3 (senior-blogger 9일, senior-hugo 8일, travel4-hugo 9일) / green=False
  - open_known_issues: count=16 / green=False
- R06(19건, STRUCT-16): CUAP 15블로그 in-article.html 전부 data-ad-format=auto (sha256 동일). STANDARD는 fluid. 콘솔 슬롯 형식 미확인 → 수정 시 광고 깨질 위험 → deferred 유지. Path B(콘솔 확인) 후속 등록.
- R04(GA4 10건, STRUCT-17): Analytics 사안, AdSense 수익과 직접 무관 → 별도 이관.
- stale 3개 상태:
  - senior-blogger: brand=seap, maintenance=awaiting, config=active, site_path 없음, domain=2.techpawz.com
  - senior-hugo: brand=seap, maintenance=in_progress, config=active, site_path=/Users/twinssn/Projects/SEAP/senior-hugo
  - travel4-hugo: brand=tap, maintenance=awaiting, config=paused, site_path=/Users/twinssn/Projects/TAP/travel4-hugo
  - 해소하려면 각 블로그 상태 정비(SEAP/TAP 소관) 필요 → P2에선 확인/사유 정리까지.
- known_issue: STRUCT-08/09 resolved로 18→16건.

## P3 — 후속 분기 (CAP 본문 · SEAP 썸네일 · TAP 전수)
- 재사용할 CUAP 절차/스크립트:
  - 키워드 정화: pipelines/curation/keywords.py, scripts/maintain_keyword_pool.py
  - 썸네일: scripts/batch_thumbnails.py (+ shared/thumbnail_generator/generator.py)
  - 엔티티/크로스링크: shared/cuap_entity_linker.py, scripts/init_cuap_link_graph.py, register_sample_cuap_entities.py, scan_all_crosslinks.py, fix_cuap_*.py
  - CTA/광고: fix_cta_links.py, pipelines/curation/pipeline.py(build_cross_sell_card/build_funnel_header)
  - 재렌더: scripts/render_inc_cl_fix.py
- 진입 순서(CUAP 재사용): 키워드 정화 → 파일럿 발행 1건 → 검증(M01/M04/Q1·P14 등) → 확대
- 주의: SEAP/TAP은 파이프라인/발행 경로(Hugo vs Blogger/WordPress)가 CUAP와 다를 수 있으므로, 절차 적용 전에 발행 경로와 콘텐츠 형식을 먼저 확인.

## 미확정/대기
- 스케줄러 재개: 원인 확인 후 안전 장치 확보 후. (startup 체크는 통과)
- R06 Path B: AdSense 콘솔 슬롯 형식 확인 후 auto→fluid 변경 가능 여부 판단.
- R04: GA4 별도 이관.
