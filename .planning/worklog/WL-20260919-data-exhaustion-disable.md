# Worklog: WL-20260919-data-exhaustion-disable

## Operation
데이터고갈 블로그 8개 비활성화 (config.yaml status=paused + GH 워크플로 .disabled.yml) — 사용자 직접 지시, 가역적 운영 결정

## Pre-Count
- 비활성화 대상: 8개 블로그 (compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo, travel-hugo, sector-hugo)
- 분류: Class A(영구 소스고갈) 5개 + Class A/B(7일+ 정지) 3개
- 보호 명단: rank-hugo(85 eligible), pick-hugo(58 eligible) + 7일 내 발행 성공 27개 블로그
- 직전 24시간 알림 발생: 17건 (hotissue 5, compare 4, deal 2, ev 2, guide 2, sector 1, travel 1)

## Backup
- config/blogs.d/cap.yaml.bak_disable_20260919_143857
- config/blogs.d/tap.yaml, config/blogs.d/stap.yaml 원본 보존
- GH 워크플로: publish-compare/deal/ev/guide/hotissue-hugo.yml → .disabled.yml rename
- daily_refresh.yml → daily_refresh.disabled.yml rename
- publish.yml: tco-hugo cron schedule 5개 제거 (주석 처리)

## Execution
1. config/blogs.d/cap.yaml: 6개 블로그 status=paused (compare, deal, ev, guide, hotissue, tco)
2. config/blogs.d/tap.yaml: travel-hugo status=paused
3. config/blogs.d/stap.yaml: sector-hugo status=paused (들여쓰기 수정 포함)
4. git commit: "ops(blogs): 데이터고갈 블로그 비활성화 (사용자 지시, 가역)"
5. GH 워크플로 6개 .disabled.yml rename + publish.yml schedule 제거
6. git commit: "ops(workflows): 데이터고갈 블로그 GH 워크플로 비활성화"
7. FLIP-BUNDLE-PREVIEW.md, G1-DESIGN.md 배치 재편 반영 (Batch 1: rank 단독)
8. ops_dashboard known_issues에 INTENTIONAL-PAUSE-20260919 등록
9. destructive 로그 기록: logs/destructive_2026-09-19.log

## Post-Verification
- YAML 파싱 검증: 3개 파일 모두 유효
- status=paused 8개 확인, rank-hugo/pick-hugo active 유지 확인
- GH 워크플로 .disabled.yml 6개 확인, publish.yml schedule 제거 확인
- scheduler 실시간 체크: 다음 슬롯(17:05~)부터 `Queue skip (inactive)` 발생 예상

## Logs
- logs/destructive_2026-09-19.log (1줄)
- git commits: 10a13de45 (config), 0f5c0add8 (workflows)

## 재활성 지도
| 블로그 | 분류 | 재활성 조건 | 예상 시점 |
|--------|------|-------------|-----------|
| compare-hugo | Class A | 연비 데이터 보강 (honda_cr_v_2026, ev4_2026, genesis_g80_2026) | 데이터 보강 시 즉시 |
| deal-hugo | Class A | 연비 데이터 보강 (honda_cr_v_2026, ev4_2026, genesis_g80_2026) | 데이터 보강 시 즉시 |
| ev-hugo | Class A | 연비 데이터 보강 (ev4_2026, ev5_2026) 또는 30일 가드 만기 | ~10/15 (30일) |
| guide-hugo | Class A | 연비 데이터 보강 (honda_cr_v_2026, ev4_2026, genesis_g80_2026) | 데이터 보강 시 즉시 |
| hotissue-hugo | Class A/B | 연비 데이터 보강 (ev4_2026, benz_sl_2026, lexus_lx_2026, ev5_2026) 또는 30일 가드 만기 | ~10/15 (30일) |
| tco-hugo | Class A | 연비 데이터 보강 (honda_cr_v_2026, genesis_g80_2026, ev4_2026) 또는 30일/90일 가드 만기 | 30일: ~10/15, 90일: ~12/15 |
| travel-hugo | Class A | heritage 데이터 소스 보강 또는 시군구 가드 완화 | 데이터 보강 시 |
| sector-hugo | Class A/B | 토픽 풀 보충 또는 no_content 가드 완화 | 데이터 보강 시 |

## 이관 스코프 변경 (T-6 반영)
- Batch 1: compare/deal/rank → **rank 단독** (compare/deal 비활성화로 제외)
- Batch 1.5: pick-hugo (불변)
- Batch 2: ev/guide/hotissue → **이관 스코프 제외** (비활성화, 재활성 시 별도 미니 절차)
- deal-hugo schedule 변경(17:45/20:50) 보류
- publish-compare/deal.yml: .disabled.yml로 보관 (재활성 시 복원)
- FLIP-BUNDLE-PREVIEW.md, G1-DESIGN.md 갱신 완료