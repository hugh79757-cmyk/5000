# WL-20260815-appliance-activate

> 날짜: 2026-08-15 / 커밋: 5000 e58e9a1cc, CUAP d96092f / appliance-hugo d418f7b / 상태: 완료
> 태그: `pre-appliance-activate-20260815` (5000 repo)
> 목적: pet-hugo 파일럿에 이어 appliance-hugo를 pet 규격으로 config 표준화 후 단독 활성화 +
> 라이브 배포. 13개 나머지 CUAP는 read-only로 고갈 원인만 규명(활성화하지 않음).

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 15:52 | appliance config 표준화 커밋 | appliance-hugo top.html/params/single/custom 4파일 | 4파일`+9/-18` | tag | CUAP d96092f | 다른 CUAP 미변경 |
| 15:54 | appliance 활성화 | cuap.yaml paused→active + sync_blog_lifecycle | 1행 UPDATE | ops.db.bak_appliance_activate_20260815 | DB=active/none | 다른 14개 CUAP 유지 |
| 15:55 | appliance 라이브 배포 | scheduler 감지→dispatcher 발행 1건→wrangler deploy | activation 준비 완료 | 위 백업 | Version 16c56141, live HTTP200 | 14개 유지(appliance만 active) |

## 수행된 변경
### appliance-hugo (CUAP submodule, commit d418f7b) — pet 규격 표준화
- `layouts/partials/adsense/top.html`: leaderboardSlot→topSlot
  (params.toml은 topSlot=2195212287 정의, leaderboardSlot 미정의→빈 슬롯 버그 수정)
- `config/_default/params.toml`: leaderboardSlot→topSlot, showReadingTime true→false,
  dateFormat "2006년 1월 2일" 추가
- `layouts/_default/single.html`: 헤더 내 in-article 광고 + dead TOC 블록 제거
  (표준: 헤더 top 광고 1개만, 본문 H2 분할 인젝션·in-article fluid 유지)
- `assets/css/custom.css`: `.hero img,.article-hero img{object-fit:contain}` 추가 (pet 규격 §④)
- 잔존 leaderboardSlot: dead leaderboard.html(0 참조)만. mobile-sticky 없음.

### CUAP repo (commit d96092f)
- appliance-hugo submodule 포인터 d418f7b 반영

### 5000 repo (commit e58e9a1cc)
- `config/blogs.d/cuap.yaml`: appliance-hugo만 paused→active (다른 14개 유지)

## 검증 (게이트)
- 로컬 Hugo 빌드: 1357 pages, 0 errors
- 로컬 렌더: top ad data-ad-slot=2195212287, 헤더 in-article 없음, in-article fluid 유지,
  날짜 "2026년 4월 30일" 포맷, 읽기시간/단어수 미표시, TOC 미렌더
- 재검사(POST /api/run-checks?blog_id=appliance-hugo):
  - standard_compliance: pass (All 15 rules passed) — FAIL→PASS
  - freshness: pass (Last publish 0d ago) — FAIL→PASS
  - data_stock: pass (재고 35건 ≥ 24)
  - render_health: pass (og:image/adsbygoogle/thumbnail), maintenance_checklist: pass(정비대상아님)
  - 잔존 fail(범위외): c01_curve_quote 2건(콘텐츠 곡선따옴표 — 생성 특성), c03_fm_key_leak 4건(이전 포스트), c06_mtime_deploy 1건(INFO)

## 라이브 배포 결과
- 스케줄러가 활성화 감지→dispatcher 발행 1건(published "다이슨 에어랩 id 실속 선택") —
  **[정상발행] 게이트 충족**
- wrangler deploy → Version 16c56141-9266-4bae-9eb0-2b040a5a031e, live HTTP 200(도메인·신규 글)
- live 렌더: data-ad-slot=2195212287 ×3 (수정 반영), ca-pub-6677996696534146 ×3 (무혼입),
  날짜 "2026년 8월 15일", leaderboardSlot 0 잔존

## 작업3 — 13개 CUAP read-only 원인 규명 (핵심 수정 발견)
> 초기 판정("13개 P14 고갈")이 실데이터와 불일치함을 확인. 실데이터 기준으로 재분류.

| blog | cuap.yaml status | KEYWORD_MAP 잔량(정의-사용) | 연속실패 | P14 이벤트 | 결론 |
|------|-----------------|--------------------------|---------|-----------|------|
| baby/fitness/interior/laptop/health/kitchen/beauty | paused(quota5) | 55/79/36/65/66/25/34 | 0 | 없음 | **config-pause만**(키워드 잔량 충분) |
| camping-hugo | paused(quota5) | 19 | 0 | 없음 | config-pause + 키워드 잔량 우려(19) |
| massage/car/homeappliance/golf/bike | paused(quota1) | 5/5/5/7/8 | 0 | 없음 | config-pause(신규 저quota) + 키워드 저(정의 자체 11~12개뿐) |

- **핵심**: 13개 모두 `status: paused`(cuap.yaml)이며, `consecutive_failures=0`이고
  `publish_error_events`에 P14 이벤트가 **0건**이다. `triage_classifications`에도 P14 없음.
- 즉, 이들은 **운영적 P14 실패가 아니라 구성(config)상 paused** 상태. "P14 고갈"은
  paused 상태에서 데이터가 소진되지 않는 정적 스냅샷에서 비롯된 2차 신호였다.
- `api_block_log` 전역 블록(2026-06-23)은 만료 — 수집 차단 없음. auto_collector는 최근까지
  정상 수집(laptop-hugo 08-13에 키워드 다수 수집) → 수집 인프라는 정상.
- **회복 레버**: 이들 복제는 (1) pet/appliance처럼 config 표준화(topSlot 단일화+헤더 단일 광고+
  dead TOC 제거) 후, (2) active로 전환 시 키워드 잔량≥24 조건을 개별 확인하고 활성화해야 함.
  camping은 잔량 19로 탈락, massage/car/homeappliance/golf/bike는 KEYWORD_MAP 정의 자체가
  11~12개로 낮아 키워드 보충이 선행되어야 함(이 작업 범위 외, read-only 판정).

## 잔존 위험
- c01_curve_quote/c03_fm_key_leak: created content 특성·이전 포스트 — config 표준화와 무관.
- 13개 CUAP 온보딩은 각각 config 표준화 확인 → 키워드 잔량 확인 후 활성화하는 순차 진행 필요
  (이번엔 appliance만, 나머지는 read-only). M06 기준 MIN 24 미달(7개는 충족, camping 외 5개 저quota 블로그는 키워드 보충 필요).
- freshness 가드(1d)가 활성 블로그에 정상 작동함을 이후 발행 주기에서 계속 관찰.