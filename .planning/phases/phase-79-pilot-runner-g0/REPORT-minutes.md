# Phase 79 REPORT — Minutes 실측 (Task 7, 스코프 ④)

> 기준: Actions API steps 데이터, 성공 run 4종 (2026-09-13~14)
> 계정: hugh79757-cmyk (private 2,000분/월 기본 한도)

## 스텝별 실측

| 스텝 | run 34810345834 | run 34800267076 | run 34773754514 | run 34773062833* | 평균 |
|---|---|---|---|---|---|
| setup+checkout | 4s | 8s | 5s | — | ~6s |
| pip install | 39s | 37s | 37s | — | ~38s |
| Hugo setup | 1s | 1s  | 1s | — | ~1s |
| wrangler install | 10s | 14s | 12s | — | ~12s |
| clone site+theme | 2s | 2s | 2s | — | ~2s |
| run slot (R2 왕복+발행+배포) | 89s | 92s | 66s | — | ~82s |
| **합계** | 2m31s | 2m44s | 2m13s | ~2m13s | **~2m30s** |

*추정치 제외. RESEARCH.md 예산(5-8분/run) 대비 **실측 2~2.5분** — 워크플로 간소화(pip 캐시, clone depth 50) 효과.

## 월 환산

| 시나리오 | runs/일 | 분/일 | 분/월 | private 2,000분 대비 |
|---|---|---|---|---|
| G0 파일럿 (tco 1블로그, quota 5) | 5 | ~12.5 | ~375 | 여유 |
| G1 전체 (car/cap 8블로그 × quota 평균 4.5) | ~36 | ~90 | **~2,700** | **초과 — public 전환 필수** |
| G4 ETAP (40블로그 ~170건/일) | ~170 | ~425 | ~12,750 | public 무료 필요 |

indexnow.yml ~6분/일 별도 소모 — 포함 시 G1 ~3,000분/월.

## 결론 (G1 진입 판단 입력값)

- G1 확대 전 **public 전환 선행** (MASTER-PLAN RESEARCH §4 원칙 재확인).
- public 전환 전제: Blogger OAuth refresh_token + client_secret 로테이션 (SECRET-AUDIT P0 — 사용자 개입 필수).
- 실측 근거: `gh api /actions/runs/{id}/jobs` steps 배열 — 2026-09-14 수집.
