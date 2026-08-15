# WL-20260815-cuap-replicate-prep

## 대상
- pet-hugo 안정성 관찰(작업1) + 표준 확정 문서화(작업2) + CUAP 14개 복제 판정(작업3)

## 게이트 (선행)
- git tag `pre-cuap-replicate-prep-20260815` (5000 repo)
- ops.db 백업 `ops_dashboard/ops.db.bak_cuap_rep_prep_20260815`
- 제약 준수: pet 외 활성화 없음, 파이프라인 로직 변경 없음, STAP 실행 없음, 기존 테스트 수정 없음

## 작업1 — pet-hugo 안정성 관찰 (read-only)
### 실데이터 기준 freshness 판독 (finish: pass)
- `check_freshness(pet-hugo, live)` → `pass: Last publish 0d ago (threshold: 1d for cuap) [live, cached=0]`
- 즉 실발행까지의 경과를 실데이터로 재계산해 정확 표시(캐시 스테일 아님)
- `standard_compliance` → `pass (All 15 rules passed)` — 재검사 트리거 후 FAIL→PASS 유지
- 오늘 발행 3건 (15:08/15:13/15:19), daily_quota 5 — 관찰 중 추가 주기 예상
- 신규 P02/P14 알림: `publish_error_events` pet-hugo 행 **0건** (발생 없음)
- 광고 slot 렌더: live 최신 포스트(냉감패드) `data-ad-slot=2195212287` 3개 +
  `ca-pub-6677996696534146` 6회 — slot 3개 지속 렌더
- 자동 재-pause 가드 조건 검증(코드 변경 없이 로직 경로 확인):
  - 경로: pipeline no_result/no_content/fetch_error → dispatcher `_increment_failure_count`
    → `>= _ESCALATION_THRESHOLD(3)` → `_set_daily_cooldown` (dispatcher:1384-1387)
    `daily_{blog_id}` = next-day 00:00 → `_is_on_daily_cooldown` 게이트(dispatcher:1261)
    이 날짜까지 발행 중단.
  - pet-hugo: `cooldown.json`에 pet-hugo/`daily_pet-hugo` **없음**, `failure_count.json`
    pet-hugo **없음** → 가드 미트리거(정상 발행 중). 조건부 트리거 경로는 확인됨.

## 작업2 — 표준 확정 문서화 (additive, commit 6c37f3701)
- **ADSENSE-GUIDE.md** §⑥ `[대표 확정]` 블록 3건 추가:
  1. topSlot 키명 단일화 — leaderboardSlot 폐기 (R02 기준, nil 바인딩→0슬롯 방지)
  2. single.html 헤더 = `top.html` 단일 광고 + dead TOC 제거 (in-article은 본문 H2 분할만)
  3. freshness 판정 = 실데이터(publish_ledger MAX(created_at)) 실시간 재계산 기준, 캐시 미신뢰
  - §7 체크리스트 "헤더 2슬롯"→"헤더 top.html 단일 광고", freshness 실데이터 항목 추가
  - §8 금기 #11(비표준 키명)·#12(헤더 2번째 in-article·dead TOC 잔존) 추가
  - 잔존 `leaderboardSlot` 언급은 금기 문구로 유지(단일화 지침)
- **Blowfish-Hugo-테마-업그레이드-표준-지침서.md**:
  - §8 금기 #11(#11 `leaderboardSlot` 등 비표준 키명)·#12(헤더 in-article·dead TOC) 추가
  - §10 버전 이력 v1.4 (2026-08-15) 추가
- 모두 additive: 기존 표준 서술 보존, `[대표 확정]` 마커 표기, diff = 2 files, +103/-2

## 작업3 — CUAP 14개 복제 판정 (read-only)
### 광고 config 감사 (parallel-worker, 14개 전수)
- **13개 비-pet 사이트 모두 동일 편차**: params.toml + top.html이 `leaderboardSlot` 사용
  (pet 규격은 `topSlot`), single.html 헤더에 `top.html`+`in-article.html` 2개 광고
  (pet은 top 전용) — 즉 전부 **config 수정 필요** (pet-hugo 파일럿 이전과 동일 상태)
- `in-article.html`(fluid+in-article), wrapper div, push-outside, publisher 6677,
  mobile-sticky 부재: 14개 모두 pet 규격 일치
- dead `leaderboard.html` partial: 14개 전부 존재하나 layout에서 0 참조

### 키워드 잔량 (KEYWORD_MAP 정의 − published_products 사용, MIN=24)
| 블로그 | 정의 | 사용 | 잔량 | P14여부 |
|--------|-----|----|-----|--------|
| appliance-hugo | 199 | 164 | 35 | OK |
| baby-hugo | 149 | 184 | -35 | 고갈 |
| fitness-hugo | 180 | 161 | 19 | 고갈 |
| interior-hugo | 140 | 179 | -39 | 고갈 |
| laptop-hugo | 101 | 104 | -3 | 고갈 |
| health-hugo | 152 | 139 | 13 | 고갈 |
| kitchen-hugo | 92 | 127 | -35 | 고갈 |
| beauty-hugo | 109 | 148 | -39 | 고갈 |
| camping-hugo | 103 | 132 | -29 | 고갈 |
| massage-hugo | 12 | 7 | 5 | 고갈 |
| car-hugo | 12 | 7 | 5 | 고갈 |
| homeappliance-hugo | 11 | 6 | 5 | 고갈 |
| golf-hugo | 12 | 5 | 7 | 고갈 |
| bike-hugo | 12 | 4 | 8 | 고갈 |

### 예상 결과
- **appliance-hugo**: 키워드 OK(35) + config 수정 필요 → [config수정필요 후 즉시발행가능]
- **나머지 13개**: 키워드 고갈(잔량 <24) + config 수정 필요 → **[P14고갈]**
  (config를 고쳐도 키워드 소진으로 발행 불가 상태)
- 일괄 활성화 **하지 않음** — 판정까지만 수행

## 잔존 위험
- 모든 판정은 실데이터(현재 DB) 기준. 키워드 정의는 향후 KEYWORD_MAP 확장 시 재계산 필요.
- auto-pause 가드는 코드 경로만 확인했고 실제 3연속 실패 트리거는 시뮬레이션하지 않음
  (실행 시 pet 발행 정상이라 강제 유발 부적절).
- appliance-hugo 1개만 [즉시발행가능] 후보 — 실제 활성화는 별도 검토 대상.