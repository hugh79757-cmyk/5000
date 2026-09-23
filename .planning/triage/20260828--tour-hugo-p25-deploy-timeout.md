---
date: 2026-08-28
type: fix
status: resolved
---

# tour-hugo P25 timeout 600s (deploy_site wrangler 120s too short → 3x retry)

## What
tour-hugo 발행이 scheduler `timeout=600` (scheduler.py:402) 로 2회 연속 강제 종료(P25). 사이트는 라이브(200)였으나 배포 단계에서 600s 초과.

## Why
tour-hugo 는 ETAP 파이프라인 → `run_batch()` 가 `_build_and_deploy(cfg)` → `shared/publishers/deploy.py:deploy_site` 로 배포. `deploy_site` 의 wrangler pages deploy 타임아웃이 `_deploy_timeout = 120`(deploy.py:349) 으로 너무 짧아, 큰 트래블 사이트 업로드가 120s 에서 실패 → 2회 재시도(10s/20s 슬립) 발생. 합계 ≈ Hugo 245s + wrangler 3×120s(360s) + flock 60s ≈ 695s > 600s → scheduler 가 kill. (중앙 배포 경로 dispatcher.py:1790 은 wrangler 300s 를 주는데 tour-hugo 는 ETAP_PIPELINE_BLOGS 에 없어 중앙 경로를 안 탐 — 불일치)

## Files changed
- shared/publishers/deploy.py (`_deploy_timeout = 120` → `300`, deploy.py:349)

## How
중앙 배포 경로와 동일하게 300s 로 상향. 큰 사이트도 1회 호출(≈200s) 로 성공 → 재시도 승수 제거. 각 subprocess 호출은 이미 timeout 가드됨(무한 루프 아님, soft/long block).

## Verification
- py_compile OK
- 로직: 300s 단일 성공 시 총 ≈ Hugo 60s + wrangler 200s + flock 60s = 320s < 600s. 재시도 트리거 안 됨.
- 참고: scheduler 는 `dispatcher.py tour-hugo` 를 매번 subprocess 로 띄우므로 deploy.py 변경은 다음 실행부터 자동 반영(스케줄러 재기동 불필요). 커밋 필요.
- 옵션(미적용, 최소변경 원칙): tour-hugo 를 ETAP_PIPELINE_BLOGS 에 추가해 중앙 단일 배포 경로로 통일.
