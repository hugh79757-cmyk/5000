# WL-20260815-pet-pilot-freshness

> 날짜: 2026-08-15 / 커밋: 5000 cbdb8d4, 90f6b66, 5a5e8c8 / CUAP b88ab81 / 상태: 완료 (작업1~5 전부)
> 태그: `pre-pet-pilot-20260815` (5000 repo)

## 작업 개요
pet-hugo (pet.informationhot.kr) 활성화 pilot. freshness 실데이터 재계산 결함 수정 +
표준 config 정합 + 활성화. 라이브 배포는 [정상발행] 게이트 후 조건부 진행.

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 15:03 | pet-hugo 활성화 | cuap.yaml status paused→active + ops.db maintenance_status in_progress→none + sync_blog_lifecycle | 1행 UPDATE (pet-hugo) | ops.db.bak_pet_pilot_20260815 | pet-hugo=active/none | 다른 14개 CUAP 유지 확인 |
| 15:13 | pet-hugo 라이브 배포 | 스케줄러가 활성화 감지→dispatcher 발행 2건(published)→_build_and_deploy_central wrangler deploy (WORKERS) | activation 완료 상태 | ops.db.bak_pet_pilot_20260815 | Version e0f404f4, live HTTP200 | 14개 CUAP 유지 |

## 4단계 프로토콜 이행 (DB 활성화)
1. 사전 카운트: pet-hugo blog_lifecycle 1행 UPDATE. 다른 CUAP 블로그 미변경.
2. 되돌림 수단: ops.db.bak_pet_pilot_20260815 + tag pre-pet-pilot-20260815.
3. 실행: cuap.yaml paused→active → update_maintenance_status('pet-hugo','none') → sync_blog_lifecycle (85 rows).
4. 사후 대조: pet-hugo config_status=active, maintenance_status=none, resume_ready=0. beauty/interior/kitchen/senior/travel4는 유지.

## 수행된 변경
### 5000 repo
- `ops_dashboard/checks/freshness.py`: days_since_last_publish(YAML sync 스냅샷) 대신
  publish_ledger MAX(created_at)을 호출 시점 기준 재계산. naive→KST(+09:00) 보정. (commit cbdb8d4)
- `tests/ops_dashboard/test_freshness_live.py`: 회귀 테스트 5건 추가 — 5 passed. (commit cbdb8d4)
- `config/blogs.d/cuap.yaml`: pet-hugo만 paused→active. (commit 90f6b66)
- 테스트 전체: 27 failed / 459 passed / 1 skipped. **신규 실패 0** (27은 기존 pre-existing).

### CUAP repo (pet-hugo)
- `layouts/partials/adsense/top.html`: data-ad-slot leaderboardSlot→topSlot
  (params.toml은 topSlot=2195212287 정의, leaderboardSlot 미정의→빈 슬롯 버그 수정). (commit b88ab81)
- `layouts/_default/single.html`: 헤더 내 in-article 제거, lead 후 광고 제거, dead TOC 블록 제거 —
  표준(ADSENSE-GUIDE) 헤더는 top 광고 1개만, 본문 H2 분할 인젝션 유지. (commit b88ab81)

## 검증
- freshness 회귀 테스트: 5 passed (pytest tests/ops_dashboard/test_freshness_live.py -q)
- standard compliance: pet-hugo 15/15 pass
- 로컬 Hugo 빌드: 881 pages, 0 errors
- 빌드 산출물 확인: top ad data-ad-slot=2195212287 렌더, 헤더에 in-article 없음, in-article fluid 렌더

## 라이브 배포 결과 (작업5)
- 스케줄러가 활성화를 감지해 15:12 dispatcher 트리거 → publish_ledger 2건 published
  (15:08 "고양이 실속 용품", 15:13 "헤어볼/고양이풀") — **[정상발행] 게이트 충족**
- `_build_and_deploy_central` wrangler deploy (WORKERS) 실행 → Version e0f404f4,
  deploy.log "Deployed pet-hugo", live HTTP 200
- live 확인: 신규 글 본문 렌더 + data-ad-slot=2195212287 (3개, 이전 nil→수정 반영)
- 재검사 트리거(POST /api/run-checks?blog_id=pet-hugo):
  - standard_compliance: pass (All 15 rules passed) — **FAIL→PASS**
  - freshness: pass (Last publish 0d ago, live) — **FAIL→PASS** (이번 수정의 핵심 검증)
  - fail 2건: c01_curve_quote(생성 콘텐츠 곡선따옴표 — 기존 파이프라인 특성, 범위 외),
    c06_mtime_deploy(INFO 등급 "최근 수정", 레시피 C.6 참고용)

## 잔존 위험
- c01_curve_quote 8건: 생성 콘텐츠의 곡선 따옴표(' ') — 이번 작업 범위 외(콘텐츠 생성 특성).
- E2E/통합 테스트는 라이브 배포 후에도 지속 관찰 필요 (freshness fail-flag가 실데이터
  기준 정상 동작함을 이후 주기에서도 확인).