# WL-20260816-cuap-activate

## 작업 단위
커밋(범위 한정) → scheduler 재시작 → cuap 7개 블로그 활성화 (active 8→15)

## 명령/파괴적 작업 로그
- `logs/destructive_2026-08-16.log` 2줄 append (kickstart -k + 사후대조) — 11:54:52 / 11:55:xx

## 백업/롤백
- `config/blogs.d/cuap.yaml.bak_activate15_20260816` (편집 전 사본)
- git tag `pre-activate15-20260816` (31debf58f)
- 복구: `cp config/blogs.d/cuap.yaml.bak_activate15_20260816 config/blogs.d/cuap.yaml` + 재시작

## 변경 내용
| 항목 | before | after |
|------|--------|-------|
| active 블로그 | 8 (appliance/fitness/interior/laptop/health/pet/kitchen/beauty) | 15 (+baby/camping/massage/car/homeappliance/golf/bike) |
| baby-hugo | status:paused + maintenance_status:isolated + cooldown_until:'2026-08-15' | status:active (메타데이터 2줄 제거, quota 5 유지) |
| camping-hugo | paused, quota 5 | active, quota 5 |
| massage/car/homeappliance/golf/bike | paused, quota 1 | active, quota 1 |

- 게이트: scheduler.py:346/434/533/910 + dispatcher.py:1246 `status != "active"` — status 전환이 유일 해제 수단 (maintenance_status/cooldown_until은 코드 소비자 0건, 대시보드 표시용)
- 커밋: `59c95032f` config(cuap): 7개 블로그 활성화 — 1 file changed, 7 insertions(+), 9 deletions(-)

## 사후 대조 (검증)
- YAML 파싱: total=15, active=15, non-active=0
- git diff: 7줄 status 변경 + baby 2줄 제거만
- 재시작: PID 79836 → 23963 (11:54:55 부팅, "=== 5000 Scheduler Starting ===", 370 jobs registered, CATCHUP compare-hugo 즉시 진행)
- 프로덕션 DB 미변경 (DB 스키마 변경·재발행 없음)

## 잔존 리스크
- fleet/new_check_fail 실발송 검증: 첫 hourly RecheckAll이 11:54:55 앵커 → ~12:54:55 이후. 그때 ops.db notification_debounce의 fleet 행 + 텔레그램 발송 확인 필요.
