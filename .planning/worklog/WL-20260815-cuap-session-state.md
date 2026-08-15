# WL-20260815-cuap-session-state — CUAP 세션 상태 스냅샷

> 작성일: 2026-08-15 | 성격: 세션 상태 기록(문서만) | 코드·config 변경 없음
> 사전 백업 태그: `pre-session-snapshot-20260815` (5000 @ a4180936a)

## 1. 목표

[검증됨] 발행량 확대가 아니라 **"제대로 운영되는 블로그" 확대**가 목표. pet-hugo 파일럿 규격이 CUAP 표준으로 확정됨(근거: appliance-hugo 활성화 선례 `WL-20260815-appliance-activate.md` + 이번 세션 6개 적용 결과 일관).

## 2. 확정 표준 5건

[검증됨] 출처: `docs/5000_TECHNICAL_DOC.md`(M06 정정 문서, 커밋 `5bbf871ea`) 및 ADSENSE-GUIDE §10-3/§⑥. 6개 서브모듈 커밋 diff로 적용 확인(각 `git show --stat`: top.html/params.toml/single.html/custom.css 4파일).

1. **topSlot 통일** — `layouts/partials/adsense/top.html`의 `leaderboardSlot` → `topSlot`, `config/_default/params.toml [advertisement]` 동일. (근거: 6서브모듈 top.html diff `data-ad-slot=...topSlot`)
2. **dateFormat "2006년 1월 2일"** — params.toml 추가. (근거: 5서브모듈 +kitchen `dateFormat = "2006년 1월 2일"` 라인)
3. **showReadingTime = false** — params.toml `showReadingTime true→false`. (근거: 6서브모듈 params.toml `-  showReadingTime = true` → `+  showReadingTime = false`)
4. **showWordCount = false** — params.toml(이미 false이나 규격 항목으로 명문화). (근거: params.toml `showWordCount = false` 존재 확인)
5. **히어로 object-fit: contain** — `assets/css/custom.css`에 `.hero img,.article-hero img{object-fit:contain}` 추가. (근거: 6서브모듈 custom.css `+2` append diff)

부수 표준(이번 적용): single.html에서 헤더 내 in-article 광고 1개 제거 + dead TOC 블록 15행 제거(본문 H2 분할 인젝션·in-article fluid는 유지).

## 3. active / paused 상태

[검증됨] 출처: `config/blogs.d/cuap.yaml`(커밋 `a4180936a`, +6 -8). 활성화는 6개 블로그 `status: paused→active` + kitchen/beauty `force_draft: true` 2행 제거로 확인.

- **active CUAP 8개**: appliance, pet, fitness, interior, laptop, health, kitchen, beauty
- **paused**: baby(격리·maintenance_status=isolated, cooldown_until 2026-08-15, RuntimeError 사유), camping, massage, car, homeappliance, golf, bike

[검증됨] baby/camping/massage/car/homeappliance/golf/bike는 이번 세션에서 status 변경 없음(paused 유지, `a4180936a` diff에서 해당 블록 미포함).

## 4. M06 발견 사항

[검증됨] 출처: `docs/5000_TECHNICAL_DOC.md`(커밋 `5bbf871ea`) + 재현 계산(`data/curation.db`, `ops.db`).

- 왜곡 원인: M06 all-time 차감(음수 가능) vs 파이프라인 publish_log 30일 윈도우 재활용(`pipelines/curation/pipeline.py:167-171`) 계산 방식 차이 — 소스 불일치 아님.
- `collected_at` 30일 TTL 코드 없음(미작동) — 검증: 해당 TTL 로직 grep 결과 부재.
- `real_candidates_30d` 병기 필드 추가(커밋 `72278e5fc`, `ops_dashboard/checks/maintenance.py:316-350`). 성격: relevance gate 미재현 → 상한 추정치.
- 재현 측정치: fitness 99 / health 85 / interior 76 / laptop 72 / beauty 52 / baby 38 / kitchen 37 / camping 21(real_candidates_30d). camping만 임계 24 미달.

## 5. 주요 커밋·태그

[검증됨] `git show --stat` / `git rev-parse` 기준.

| 대상 | 커밋 | 태그 | 비고 |
|---|---|---|---|
| 서브모듈 fitness-hugo | 338e171 | activate-fitness-20260815 | 4파일 |
| 서브모듈 interior-hugo | 25c925c | activate-interior-20260815 | 4파일 |
| 서브모듈 laptop-hugo | 6ace933 | activate-laptop-20260815 | 4파일 |
| 서브모듈 health-hugo | 4a1566f | activate-health-20260815 | 4파일 |
| 서브모듈 kitchen-hugo | 2dd1c91 | activate-kitchen-20260815 | 4파일(선행 수정분 포함) |
| 서브모듈 beauty-hugo | da4d0a6 | activate-beauty-20260815 | 4파일 |
| 5000 cuap.yaml | a4180936a | activate-cuap-6-20260815 | 6개 활성화 |
| 5000 문서(M06 정정) | 5bbf871ea | — | 14 ins/0 del |
| 5000 M06 real_candidates_30d | 72278e5fc | — | maintenance.py +39 |
| 5000 baby 격리 | 357fc0d10 | — | paused/isolated |

## 6. 미해결

[부분검증] **kitchen/beauty transient publish_error** — kitchen 첫 발행 `publish_error`(STAGE:publish_post END 0.07s, 검증/네트워크 로그 없음) → 동일 명령 재시도 시 `success:true`. 원인 미특정(타임아웃 래퍼와 연동된 일시적 현상으로만 추정, 재현 불가).

[검증불가] **신규 6개 후속 주기 지속발행** — 이번은 1회 발행만 관찰, launchd 스케줄러를 통한 일별 5회 반복 발행 정상 동작 여부는 미관찰(추후 freshness 체크로 확인 필요).

[검증불가] **baby RuntimeError 원인** — baby-hugo는 isolated/paused 상태, RuntimeError 구체 원인 미파악(이번 세션 범위외).

[검증불가] **beauty 로그-DB 불일치** — dispatcher 로그상 발행 성공이나 `ops.db`/소스 DB 기록 정합성 미교차검증.

[검증불가] **ops.db 0바이트 경로** — `ops_dashboard/ops.db` 경로/용량 상태 미확인(대시보드 기동 여부와 무관하게 기록 손실 리스크 잔존 가능).

## 7. 잔존 위험 요약

[부분검증] kitchen/beauty 발행은 force_draft 제거로 정상화됐으나 동일 transient `publish_error` 재현 가능(원인 미특정). [검증불가] 신규 6개 지속발행·baby RuntimeError·beauty 로그-DB 불일치·ops.db 0바이트는 이번 세션에서 확인하지 못한 항목으로, 다음 세션에서 별도 조사 필요.
