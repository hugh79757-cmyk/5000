# WL-20260815-pet-pilot-freshness

> 날짜: 2026-08-15 / 커밋: 5000 cbdb8d4, 90f6b66 / CUAP b88ab81 / 상태: 작업1~4 완료, 작업5(라이브 배포) 보류 대기
> 태그: `pre-pet-pilot-20260815` (5000 repo)

## 작업 개요
pet-hugo (pet.informationhot.kr) 활성화 pilot. freshness 실데이터 재계산 결함 수정 +
표준 config 정합 + 활성화. 라이브 배포는 [정상발행] 게이트 후 조건부 진행.

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 15:03 | pet-hugo 활성화 | cuap.yaml status paused→active + ops.db maintenance_status in_progress→none + sync_blog_lifecycle | 1행 UPDATE (pet-hugo) | ops.db.bak_pet_pilot_20260815 | pet-hugo=active/none | 다른 14개 CUAP 유지 확인 |

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

## 잔존 위험
- 작업5(라이브 배포) 미실행 — dispatcher는 generate+publish+deploy를 한번에 수행해
  "첫 발행 주기"와 "live 배포"를 분리하지 못함. [정상발행] 게이트 확인이 필요.
- pet-hugo freshness fail-flag가 활성 상태에서 실데이터 재계산으로 정상 동작하는지 라이브 검증 대기.
- E2E/통합 테스트는 작업5 라이브 배포 후 확인 예정.