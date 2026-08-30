# SESSION_SNAPSHOT_2026-08-27.md

> 세션 종료 시점 상태 정리 (2026-08-27). 다음 세션 시작 시 이 파일을 읽고 이어갈 것.

## Git 상태 (5000 repo, main 브랜치)

- **HEAD**: `828e712e8 fix: auto-add twitter_card frontmatter for car pipeline (W5 R17)`
- 브랜치: main (활성), `car-rotation-relief` (main에 병합됨 85f6c7c38, 미삭제 — 삭제 가능)
- 기타 로컬 브랜치: feat/phase62-m5-qb, feat/phase69-incident-taxonomy, feat/phase69-m4-dashboard-ssot, feat/phase71-car-recovery, feat/pr-cap-1-pipeline-result-contract, feat/pr2-root-cause-retry-control, fix/concurrent-publish-event-id, fix/p01-runtime-normalization, feat/candidate-availability-state 등 (미병합, 본 세션 무관)
- **car-trim-refresh 브랜치/커밋(890d3f4b)은 허위 판명** — 존재하지 않음. backward-scan은 기존 `refresh_trims`(:52-122)가 담당.
- stash(5000 repo): stash@{0} Track C clean (2026-08-21), stash@{1} etap-phase61, stash@{2} WIP 광고가이드, stash@{3} WIP related_cards — 본 세션 무관, 보존.
- **stock-hugo stash 주의**: `/Users/twinssn/Projects/stap/stock-hugo` nested repo의 `stash@{0}` = QUARANTINE (adsense 6677→8772 스왑 + Congo→Blowfish 마이그레이션 diff 포함). **drop 금지** (다른 변경 다수 섞임, 사용자 지시). 워킹트리는 6677 정상, 라이브 광고 정상.

## 이번 라운드 완료 항목 (2026-08-26 ~ 27)

| 항목 | 결과 | 커밋/근거 |
|---|---|---|
| AdSense 도메인↔ID 전수감사 | 0건 위반 | baseURL vs ID 스캔 (rotcha/techpawz→8772, informationhot→6677, aikorea24→5938) |
| STAP 5블로그 adsense 잘못 교체 후 복원 | techpawz.com=8772 정상 복귀 | 9563e24 등 |
| car 콤보 가드 영구→90일 기간화 | 완료 | 02e79abf8 |
| select_topic 미사용 콤보 우선 | 완료 | 095a67b09 |
| select_topic 콤보 판정 content.db 정합화 | 완료 (발행 성공의 핵심) | 42a121e54 |
| R17 twitter_card 자동화 (car 3개 FM 빌더) | 완료 | 828e712e8 |
| compare-hugo 발행 재개 | article 12176, 라이브 200 | GLS vs RSQ8 |
| deal-hugo 발행 재개 | article 12177, 12178, 라이브 200 | X3, 7시리즈 |
| pick-hugo 발행 지속 | 48h 3건 (7d 7건) | persona_pick |

## 진행 중 / 미해결

| 항목 | 상태 | 비고 |
|---|---|---|
| ev/guide/hotissue/tco/rank 5개 블로그 발행 0건 | **미진단** | 48h/7d 모두 0. pick/compare/deal만 발행. 원인: 사용 가능 콤보 소진 추정 (단종+영구가드 해제 후에도) — 다음 세션 우선순위 1 |
| ledger_sync content.db 미반영 갭 | **미점검** | car 발행이 content.db articles에 안 쌓임 → 콤보 가드는 content.db 기준, car.db 기준(247건)과 불일치. 우선순위 2 |
| STAP/ETAP R17 twitter_card fail 6건 | **미확장** | finance/airlines/etf/dividend/sector/ipo-hugo (checked_at 08-26T20:23~33). 자동화가 car 3개 FM 빌더만 커버. 우선순위 3 |
| CAP 데이터 소스 근본 확장 | **미시행** | scan_new_cars +30 윈도우(→+200 제안), 신차 출시 의존. 우선순위 4 |

## 잔존 위험

1. S01 유니크 fail=65 (checked_at 08-27T04:30~33) — 거의 전 블로그 1건씩. 임계값 0.5941 기준 재검토 필요.
2. P01 open=272 (기존 357 대비 -85 자동 close), P16=4. 신규 vs stale 구분 필요.
3. dispatcher 내장 빌드 레이스 — 가끔 신규 포스트 라이브 404 (수동 hugo build + deploy_site로 해소).
4. S02 유사도 fail=43 — 콤보 재사용으로 상승 가능, 추이 모니터링 필요.
5. cooldown.json — daily_ev-hugo 등 과거 항목 존재 (자동 만료 예정).

## 다음 세션 우선순위 (사용자 지시 기반)

1. **ev/guide/hotissue/tco/rank 5개 블로그 0건 원인 진단** (조사+보고만, 코드변경 금지)
2. **ledger_sync 점검** — car.db→content.db 동기화 갭 원인
3. **R17 확장** — STAP/ETAP FM 빌더에 twitter_card 자동화 적용
4. **CAP 데이터 소스 근본 확장** — scan window +200, brand 인덱스 크롤 등 (설계수준, 승인 필요)

## 48h 모니터링 판정 요약 (2026-08-27 04:30 기준)

- 8블로그 48h 발행: compare=1, deal=2, pick=3, 나머지 5개=0 (목표 각 2건 미달)
- 콤보 90일 재발행: 0건 ✅
- source_id 30일 재발행: content.db 기준 0건 ✅ / car.db 기준 247건 ⚠️ (DB 불일치)
- R17: car 8개 0건 ✅ / STAP·ETAP 6개 fail ⚠️
- trim 갱신 활용: 판정 불가 (updated_at 일괄 재기록, price_history 테이블로 재판정 가능)
