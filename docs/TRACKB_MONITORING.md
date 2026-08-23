# Track B — Phase 2 Monitoring

> 기간: 2026-08-22 ~ 2026-09-05 (14일)
> 대상 블로그: hotissue-hugo, guide-hugo, travel3-hugo, travel1-hugo, deal-hugo
> baseline: /tmp/trackb_baseline.json

## 대상 블로그별 역할

| blog_id | 실질 변경 | 역할 |
|---------|----------|------|
| travel3-hugo | **YES** (CQ03 제휴공시 2~3줄, commit 2f10adb, deploy 완료) | **처치군 (treatment)** — 효과 측정 핵심 |
| hotissue-hugo | NO (source 이미 준수, stale) | 통제군 |
| guide-hugo | NO (stale) | 통제군 |
| travel1-hugo | NO (stale) | 통제군 |
| deal-hugo | NO (stale) | 통제군 |

> 실질 변경 1건만 있으므로 효과 측정은 **travel3-hugo 중심**.
> 나머지 4건은 통제군 → 자연 변동(계절/트래픽 노이즈) 파악용.

## 추적 지표

- `gsc_impressions` (주간 변화)
- `gsc_clicks` (주간 변화)
- `gsc_ctr` (변화율 = (after-before)/before)
- `ga4_engagement_rate` (가용 시, Track C michelin 측정 체계 참조)

## 평가 기준

- **PASS**: 처치군(travel3)에서 `CTR +0.5%p` 또는 `clicks +10%` (1건 이상)
- **INCONCLUSIVE**: 변화 없음 (±5% 이내)
- **FAIL**: CTR 하락 또는 impressions 감소 >10%

## 중간 체크 (2026-08-29)

- GSC/GA4 데이터 수집
- travel3 vs 통제군 추세 방향만 확인 (판정 아님)
- CTR -20% 이하면 조기 FAIL 선언

## 종료 시 결정 (2026-09-05)

- PASS → Phase 3 확대 (17건 HIGH 후보 또는 다음 패턴)
- INCONCLUSIVE → 추가 7일 연장 또는 다른 패턴(CQ05 이미지)으로 전환
- FAIL → 원인 분석 + threshold 재교정 (Phase 0 §5 calibration)

## 배포 기록

- travel3-hugo: commit `2f10adb` (1 file, 3 insertions), deploy_site OK, 라이브 HTTP 200 + 제휴공시 확인
- stale 갱신: check_results content_quality 4건 fail→pass (backup /tmp/ops.db.bak_trackb_20260822_222717)

## 주의

- content_quality checker는 블로그당 **최신 1건만** 검사 → travel3 외 포스트 미반영
- Phase 3 효과 측정은 GA4(Track C) 연동 필요
