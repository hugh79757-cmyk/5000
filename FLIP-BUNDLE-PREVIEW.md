# Flip Batch 1 번들 Diff 프리뷰

**목적**: ② B1 완료 수신 즉시 기계적 실행(신규 판정 없음)
**대상**: 단일 커밋에 번들 포함 — cap.yaml + owner flip + 워크플로 2개 + 운영 워크플로 2개
**생성 시점**: 2026-09-18 (date 원값)

---

## 1. config/blogs.d/cap.yaml — deal-hugo schedule 변경 + owner flip

### 변경 전 (deal-hugo)
```yaml
- cf_project: deal-hugo
  daily_quota: 5
  domain: deal.rotcha.kr
  id: deal-hugo
  owner: mac
  deploy_type: pages
  name: 프로모션
  pipeline: car
  platform: hugo
  post_type: promo_deal
  prompt: deal/promo_deal.md
  repo: deal-hugo
  schedule:
    times:
    - 06:35
    - '10:15'
    - '13:40'
    - '17:30'
    - '20:45'
  site_path: /Users/twinssn/Projects/cap/deal-hugo
  status: active
  theme: Blowfish
  managed_by: pipeline
```

### 변경 후 (deal-hugo)
```yaml
- cf_project: deal-hugo
  daily_quota: 5
  domain: deal.rotcha.kr
  id: deal-hugo
  owner: runner  # mac → runner
  deploy_type: pages
  name: 프로모션
  pipeline: car
  platform: hugo
  post_type: promo_deal
  prompt: deal/promo_deal.md
  repo: deal-hugo
  schedule:
    times:
    - 06:35
    - '10:15'
    - '13:40'
    - '17:45'    # 17:30 → 17:45 (깨끗한 분 확보)
    - '20:50'    # 20:45 → 20:50 (깨끗한 분 확보)
  site_path: /Users/twinssn/Projects/cap/deal-hugo
  status: active
  theme: Blowfish
  managed_by: pipeline
```

### 변경 전 (compare-hugo) — owner만 변경
```yaml
- cf_project: compare-hugo
  ...
  owner: mac
  ...
```

### 변경 후 (compare-hugo)
```yaml
- cf_project: compare-hugo
  ...
  owner: runner  # mac → runner
  ...
```

**변경 라인 수**: ~8라인 (schedule 2 + owner 2) × 2 블로그 = **약 16라인**

---

## 2. .github/workflows/publish-compare.yml — 신규 생성

**파일 크기**: ~70라인
**주요 내용**:
- name: publish (compare-hugo)
- schedule: 5개 cron (06:40, 10:20, 13:45, 17:35, 20:55 +07 → UTC 변환)
- concurrency: publish-lock-car
- timeout-minutes: 20
- env: LLM 10 + Coupang 3 + Telegram 2 + R2 + Cloudflare + 5000_RUNNER=1
- jobs: checkout → python → hugo → wrangler → clone → theme copy → run_slot → elapsed

**신규 파일**: **70라인 추가**

---

## 3. .github/workflows/publish-deal.yml — 신규 생성

**파일 크기**: ~70라인
**주요 내용**: compare와 동일, deal-hugo 전용
- schedule: 5개 cron (06:35, 10:15, 13:40, 17:45, 20:50 +07 → UTC 변환)

**신규 파일**: **70라인 추가**

---

## 4. .github/workflows/daily_refresh.yml — 기존 반영 확인

**상태**: 이미 커밋됨 (변경 없음)
- cron: `0 0 * * *` (00:00 UTC = 07:00 +07)
- timeout-minutes: 20
- owner=runner만 보충, replenish-only 격리

**변경**: **0라인** (이미 반영)

---

## 5. .github/workflows/keepalive.yml — 기존 반영 확인

**상태**: 이미 커밋됨 (변경 없음)
- cron: `0 0 1 * *` (매월 1일 00:00 UTC = 07:00 +07)
- timeout-minutes: 20
- empty commit 금지

**변경**: **0라인** (이미 반영)

---

## 6. 난합계 (단일 커밋 기준)

| 파일 | 변경 유형 | 라인 수 |
|------|-----------|---------|
| config/blogs.d/cap.yaml | 수정 | ~16 |
| .github/workflows/publish-compare.yml | 신규 | ~70 |
| .github/workflows/publish-deal.yml | 신규 | ~70 |
| .github/workflows/daily_refresh.yml | 기존 반영 | 0 |
| .github/workflows/keepalive.yml | 기존 반영 | 0 |
| **총계** | | **~156라인** |

---

## 7. 실행 순서 (② 수신 시)

```bash
cd /Users/twinssn/Projects/5000

# 1. 변경사항 스테이징
git add config/blogs.d/cap.yaml \
      .github/workflows/publish-compare.yml \
      .github/workflows/publish-deal.yml

# 2. 커밋 (단일 번들)
git commit -m "G1 batch 1 flip: compare/deal runner 이관 + deal 깨끗한 분 확보

- compare-hugo, deal-hugo owner: mac -> runner
- deal-hugo schedule: 17:30/20:45 -> 17:45/20:50 (tco 충돌 해소)
- publish-compare.yml, publish-deal.yml 신규 생성 (config.yaml 파생)
- publish-lock-car 공유 직렬화, timeout-minutes: 20 통일
- 일일 보충(daily_refresh) + 월 킵얼라이브(keepalive) 운영 워크플로 포함"

# 3. 푸시
git push origin main

# 4. 실증
git show origin/main --stat
gh workflow list | grep -E "publish-compare|publish-deal"
```

---

## 8. 검증 체크리스트 (push 후 즉시)

- [ ] `git show origin/main` 해시 일치
- [ ] `gh workflow list`에서 publish-compare, publish-deal 활성 확인
- [ ] `gh run list --workflow=publish-compare.yml --limit 1` 정상 발화 대기
- [ ] `gh run list --workflow=publish-deal.yml --limit 1` 정상 발화 대기
- [ ] Mac scheduler.log `[SKIP] compare-hugo owner=runner` 확인
- [ ] Mac scheduler.log `[SKIP] deal-hugo owner=runner` 확인
- [ ] KILL-SWITCH 4신호 0건 유지

---

*프리뷰 완료 — ② B1 완료 수신 즉시 위 순서로 기계적 실행*
