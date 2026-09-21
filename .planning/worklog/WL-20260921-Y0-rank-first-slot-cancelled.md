# WL-20260921-Y0 — rank-hugo 첫 슬롯 소급 판정

## 날짜
2026-09-21 03:31 UTC (10:31 +07)

## 배경
- Flip: 09-20 12:48 +07 (05:48 UTC) — Mac scheduler → GH Actions runner 전환
- 첫 슬롯 예정: 09-20 23:50 UTC = 09-21 06:50 +07
- 관찰 시점: 09-21 03:31 UTC — 슬롯 종료 ~3.7h 후

## 관찰 착오
- 초기 관찰 시 "~20h 대기"로 판정 → 첫 슬롯 이미 종료 시점
- 원인: 타임라인 역산 오류 (UTC→+07 변환 미적용)

## GH Actions 실행 이력

| run ID | workflow | event | conclusion | created | jobs |
|--------|----------|-------|------------|---------|------|
| 35551785126 | publish (rank-hugo) | schedule | **cancelled** | 2026-09-21T01:42:47Z | 0 |

- 예정 시각: 23:50 UTC Sep 20 → 실제 시작: 01:42 UTC Sep 21 (지연 1h52m)
- GitHub Actions cron 딜레이 범위 내 (최대 수시간 지연 허용)
- **결과: cancelled, 0 jobs — 발행/배포 전부 미실행**

## 취소 원인 분석

### 동시성 그룹 `publish-lock-car`
| 워크플로우 | 동시성 그룹 | cancel-in-progress |
|------------|------------|-------------------|
| publish-rank.yml | publish-lock-car | false |
| publish-compare.yml | publish-lock-car | false |
| publish-deal.yml | publish-lock-car | false |
| publish.yml (universal) | publish-lock-car | false |
| daily_refresh.yml | publish-lock-car | false |

### 동시 슬롯 타임라인 (01:36-01:45 UTC)
```
01:36:17 — guide-hugo (success)  ← publish-lock-car에 안 속함 (별도 그룹)
01:39:38 — deal-hugo (success)   ← publish-lock-car
01:41:21 — ev-hugo (success)     ← publish-lock-car 미사용 (별도 그룹)
01:42:47 — rank-hugo (CANCELLED) ← publish-lock-car — 0 jobs, 30초 만에 취소
01:43:15 — compare-hugo (success) ← publish-lock-car
```

`cancel-in-progress: false` → 새 run은 기존 run 완료 후 큐에 들어가야 함.
그런데 rank-hugo는 **0 jobs로 즉시 취소** — GitHub Actions 자체 취소 또는 수동 취소.

### 가능한 원인
1. GitHub Actions 내부 취소 (큐 오버플로/스케줄러 이슈)
2. 수동 취소 (누군가 콘솔에서 취소)
3. 동시성 그룹 관련 GitHub Actions 버그

## Mac scheduler 상태

### 09-20 23:50 UTC (flip 직전, Mac scheduler 마지막 실행)
```
2026-09-20 06:50:14,689 [INFO] Queue executing: rank-hugo (remaining: 0)
2026-09-20 06:50:39,273 [INFO] {"success": true, "file": "...준대형suv-구매-고민이라면-가성비-기준-top5로-답을-찾는다/index.md", "deployed": false, "deploy_error": "Wrangler deploy failed", "pipeline_status": "FAILED_TRANSIENT"}
```
- 발행 성공 (파일 작성), 배포 실패 (FAILED_TRANSIENT)
- article_id: 14408, source_id: bmw_x5_2026

### 09-21 (flip 후, Mac scheduler)
- 전부 `[SKIP] rank-hugo owner=runner — runner 소유 (catchup)` → 정상 skip

## articles 테이블 최신 rank-hugo 기록

| id | title | published_at | status | source_id | created_at |
|----|-------|-------------|--------|-----------|------------|
| 14451 | 테스트 제목 | NULL | pending | test_car_2026 | 2026-09-20 12:00:00 |
| 14408 | 준대형SUV 구매 고민이라면... | 2026-09-19 23:50:29 | published | bmw_x5_2026 | 2026-09-20 06:50:25 |

- 14451 = flip 테스트 행 (status: pending, source: test_car_2026)
- 14408 = 마지막 실발행 (Mac scheduler, FAILED_TRANSIENT deploy)

## 4/4 판정

| 기준 | 상태 | 근거 |
|------|------|------|
| event=schedule | ✅ | run event=schedule 확인 |
| rank 바인딩 | ❌ | 0 jobs — 실행 자체 없음 |
| 발행 rc=0 | ❌ | 미실행 |
| 배포 rc=0·라이브 200 | ❌ | 미실행 |
| push-back(CAP_PAT) | ❌ | 미실행 |
| round-trip md5 | ❌ | 미실행 |
| Mac 06:50 SKIP | ✅ | scheduler.log에서 runner 소유 skip 확인 |

**최종: 4/4 미달성 (2/7 충족). 첫 슬롯 cancelled by GitHub Actions.**

## 영향
- G-C 발행 레그: **미종결** — rank-hugo 마지막 실발행은 09-20 06:50 (Mac, FAILED_TRANSIENT deploy)
- 배치 1.5 창: **진입 불가** — 4/4 미달성
- R-ACCEL: **일정 당김 불가**

## 다음 슬롯
- 예정: 2026-09-21 23:50 UTC = 2026-09-22 06:50 +07
- 관찰 필요: 동시성 충돌 재발 여부, GitHub 취소 원인

## 교훈
1. 타임라인 역산 시 UTC→+07 변환표 필수 — "20h 대기" 착오 재발 금지
2. GitHub Actions cron 지연은 최대 수시간 — 정확한 시작 시각은 gh run list로 확인
3. `publish-lock-car` 동시성 그룹이 5개 워크플로우 공유 → 슬롯 경쟁 심각
