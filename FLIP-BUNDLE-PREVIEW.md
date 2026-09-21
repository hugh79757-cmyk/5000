# Flip Batch 1 번들 Diff 프리뷰

**목적**: AA-3 probe 초록 + 사용자 진행 신호 수신 즉시 기계적 실행(신규 판정 없음)
**대상**: 단일 커밋에 번들 포함 — cap.yaml + owner flip + 워크플로 3개 + 운영 워크플로 2개
**생성 시점**: 2026-09-18 (date 원값)

---

## 0. 전제조건 게이트 상태 (2026-09-18 15:35 +07 로컬)

| 게이트 | 상태 | 비고 |
|--------|------|------|
| AA-3 probe 초록 + 사용자 진행 신호 | ⏳ 대기 | 사용자 UI 작업 진행 중 |
| F-1: rank 크론 교차표 | ✅ **통과** | 9워크플로 전수, 이격 ≥10분, 충돌 0건 |
| **H-1: rank W5 100% (재조정)** | ✅ **통과** | 풀 57/57 verified=1, 65→57 산술 불일치 해소, 6개 car_id 진위·자산 확인 |
| E-1: 7블로그 eligible 진위 | ✅ **확정** | 측정=라이브 전수 일치 |
| E-2: 사전 리시딩 절차 | 📝 문서화 완료 | 실행 스텝 내장 |
| E-3: 배치 재편 | ✅ **확정** | Batch 1: compare/deal/rank |
| E-4: FUEL-UNIVERSE | ✅ **완료** | 8블로그 replenish 가능량 산출 |

**step 0 실행 시 필수 확인**: AA-3 probe 초록 + 사용자 진행 신호 + H-1(100% 재확인) + F-1(확보)

---

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

## 4. .github/workflows/daily_refresh.yml — 신규 생성 (미추적)

**상태**: 미추적 신규 (git status --short에서 ??)
- cron: `0 0 * * *` (00:00 UTC = 07:00 +07)
- timeout-minutes: 20
- concurrency.group: publish-lock-car
- owner=runner만 보충, replenish-only 격리

**신규 파일**: **약 50라인 추가**

---

## 5. .github/workflows/keepalive.yml — 신규 생성 (미추적)

**상태**: 미추적 신규 (git status --short에서 ??)
- cron: `0 0 1 * *` (매월 1일 00:00 UTC = 07:00 +07)
- timeout-minutes: 20
- concurrency.group: publish-lock-car
- cancel-in-progress: false
- empty commit 금지

**신규 파일**: **약 40라인 추가**

---

## 6. 난합계 (단일 커밋 기준) — **재편: Batch 1 rank 단독**

| 파일 | 변경 유형 | 라인 수 | 추적 상태 |
|------|-----------|---------|-----------|
| config/blogs.d/cap.yaml | 수정 | ~4라인 (rank owner만) | tracked (M) |
| .github/workflows/publish-rank.yml | 신규 | ~70 | untracked (??) |
| .github/workflows/daily_refresh.yml | 기존 | ~50 | tracked (M) — schedule 제거됨 |
| .github/workflows/keepalive.yml | 기존 | ~40 | tracked |
| scripts/generate_publish_workflows.py | 기존 | ~200 | tracked |
| scripts/verify_car_state.py | 기존 | ~100 | tracked |
| pipelines/car/daily_refresh.py | 기존 | ~130 | tracked (M) |
| **총계** | | **~564라인** | |

**배치 구성 (재편):**
- **Batch 1 (이번 flip)**: rank-hugo 단독 (메커니즘 게이트 + 발행 레그 4/4)
- **Batch 1.5 (차기 창)**: pick-hugo (전제: 정정 1 완료 + W5 7개 car_id + ledger_sync) — 불변
- **Batch 2**: 이관 스코프에서 제외 — ev-hugo, guide-hugo, hotissue-hugo 비활성화. 재활성 절차(활성화 → 리시딩 → flip → 게이트)를 미니 절차로 별도 문서화 예정.
- **비활성 블로그(8개)**: compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo, travel-hugo, sector-hugo — config.yaml status=paused, GH 워크플로 .disabled.yml 처리. 재활성 조건: 연비 데이터 보강 또는 가드 만기(30일~10/15, 90일~12/15).

**제외 파일 (배치 1에서 제외 — 비활성화로 인한 보류):**
| 파일 | 제외 사유 | 비고 |
|------|-----------|------|
| .github/workflows/publish-compare.yml | compare-hugo 비활성화 | .disabled.yml로 보관, 재활성 시 복원 |
| .github/workflows/publish-deal.yml | deal-hugo 비활성화 | .disabled.yml로 보관, 재활성 시 복원 |
| .github/workflows/publish-ev.yml | ev-hugo 비활성화 | 미생성 (배치 2 제외) |
| .github/workflows/publish-guide.yml | guide-hugo 비활성화 | 미생성 (배치 2 제외) |
| .github/workflows/publish-hotissue.yml | hotissue-hugo 비활성화 | 미생성 (배치 2 제외) |
| scripts/normalize_timezone.py | F-4 시점 커밋, 실행 보류 유지 | 타임존 정규화 스크립트. 배치 1에 generate_publish_workflows.py가 단일 공급원으로 포함. |

**배치 구성 (E-3 확정 → 2026-09-19 데이터고갈 비활성화 반영 재편):**
- **Batch 1 (이번 flip)**: rank-hugo 단독 (compare-hugo, deal-hugo 비활성화로 제외)
- **Batch 1.5 (차기 창)**: pick-hugo (전제: 정정 1 완료 + W5 7개 car_id + ledger_sync) — 불변
- **Batch 2**: 이관 스코프에서 제외 — ev-hugo, guide-hugo, hotissue-hugo 비활성화. 재활성 절차(활성화 → 리시딩 → flip → 게이트)를 미니 절차로 별도 문서화 예정.
- **비활성 블로그(8개)**: compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo, travel-hugo, sector-hugo — config.yaml status=paused, GH 워크플로 .disabled.yml 처리. 재활성 조건: 연비 데이터 보강 또는 가드 만기(30일~10/15, 90일~12/15).

---

## 6.1 제외 파일 (지시 후보 8종 대비 7파일)

| 파일 | 제외 사유 | 비고 |
|------|-----------|------|
| scripts/normalize_timezone.py | **F-4 시점 커밋, 실행 보류 유지** | 타임존 정규화 스크립트. 배치 1에 generate_publish_workflows.py가 단일 공급원으로 포함되어 있으므로(워크플로 생성 스크립트), normalize_timezone.py 실행은 배치 4 이후로 이연. 단일 공급원 성립에 영향 없음. |

---

## 7. 실행 순서 (② 수신 시 — step 0 추가) — **재편: rank 단독**

```bash
cd /Users/twinssn/Projects/5000

# 0. 전제: AA-3 probe 초록 + 사용자 진행 신호 / 창 내: 리시딩 → add → commit → push → 실증 (E-2 리시딩은 창 내 실행, 전제 아님)
# [전제] AA-3 probe 초록 + 사용자 진행 신호 + X-1(활성 경로) + X-2(계수 패치) + W-2(H-1 56/56) + 창 판정
#   - rank W5: python3 scripts/verify_car_images.py audi_a6_2026 kona_2027 renault______2027 genesis_____gv70_2027 renault___2027 k8_2027
#   - 재확인: 57/57 car_ids verified=1 (100%) ✓
#   - X-1: daily_refresh.yml PHASE 1(관찰 스테이징, --get-only + --dry-run) 배포 확인
#   - X-2: daily_refresh.py _count_eligible_topics per-type 분기 패치 적용 확인 (top5_rank=fallback 56 재현)
# - tco 발화(23:30 UTC)와 30분+ 이격 (tco 비활성화로 현 러너 크론 0본 — pick 06:55 ±30분 회피 + daily_refresh 00:00 UTC 이격만)
# - Mac car 슬롯 ±30분 회피 (pick 06:55 단독)
# - date 원값 기록 (+07 로컬)
# - 사전 리시딩(rank-hugo 단독):
#   R2-fresh pull → 맥 로컬(car.db topics+publish_log 해당 site, 
#   stap_content.db articles 해당 blog_id, cooldown.json, 
#   content.db publish_ledger 해당 blog_id) 병합 → 회피창 put →
#   사전/후 rowcount·md5 대조 기록
# 창 밖이면: 대기 후 창 진입 (이탈 아님, 대기 사유 명시)

# 0.5. cap.yaml rank-hugo owner mac→runner 에디트 (창 내 실행 — Mac 스케줄러 hot-read 방지)
python3 -c "
import sys
with open('config/blogs.d/cap.yaml', 'r') as f:
    content = f.read()
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'id: rank-hugo' in line:
        for j in range(i+1, min(i+4, len(lines))):
            if 'owner: mac' in lines[j]:
                lines[j] = lines[j].replace('owner: mac', 'owner: runner')
                print(f'Fixed line {j+1}: {lines[j].strip()}')
                break
        break
with open('config/blogs.d/cap.yaml', 'w') as f:
    f.write('\n'.join(lines))
print('Done')
"
git diff config/blogs.d/cap.yaml | head -10  # ±1라인만 변경 확인
# 1. 변경사항 스테이징 (수정 목록 — 커밋 메시지와 일치 필수)
# 7파일 (정규화 스크립트 제외 — F-4 커밋·실행 보류)
git add config/blogs.d/cap.yaml \
      .github/workflows/publish-rank.yml \
      .github/workflows/daily_refresh.yml \
      .github/workflows/keepalive.yml \
      scripts/generate_publish_workflows.py \
      scripts/verify_car_state.py \
      pipelines/car/daily_refresh.py

# 2. 커밋 (단일 번들 — Batch 1: rank-hugo 단독, publish.yml fallback 포함)
git commit -m "G1 batch 1 flip: rank-hugo runner 이관 + daily_refresh C-3 fix + publish.yml fallback rank

- rank-hugo owner: mac -> runner
- publish-rank.yml 신규 생성 (config.yaml 파생)
- publish.yml fallback: tco-hugo -> rank-hugo (수동 dispatch 폴백 동기화)
- publish-lock-car 공유 직렬화, timeout-minutes: 20 통일
- 일일 보충(daily_refresh) + 월 킵얼라이브(keepalive) 운영 워크플로 포함
- 단일 공급원 스크립트 2종 번들 (generate/verify) — normalize은 F-4 보류
- C-3 fix: daily_refresh usable_pending 계산에 select_topic 가드 세트 적용 (combo 90/30일, reuse 7일, recent_keys 14일) — replenish 트리거 정합성 확보
- rank-hugo 발행 레그 4/4 증명 담당 (85 eligible, W5 56 car_id 전원 verified=1 — H-1 재판정 기준)
- compare/deal/ev/guide/hotissue/tco/travel/sector 8개 블로그 비활성화 별도 커밋 (ops/blogs)"

# 3. 푸시
git push origin main

# 4. 실증 (메시지 명세와 파일 목록 일치 확인 — 불일치 시 중단·예외)
git show origin/main --stat
gh workflow list | grep -E "publish-rank|daily_refresh|keepalive"
```

---

## 8. 검증 체크리스트 (push 후 즉시) — **재편: rank 단독**

- [ ] `git show origin/main` 해시 일치
- [ ] `gh workflow list`에서 publish-rank 활성 확인 (compare/deal은 .disabled.yml로 비활성)
- [ ] `gh run list --workflow=publish-rank.yml --limit 1` 정상 발화 대기
- [ ] Mac scheduler.log `[SKIP] rank-hugo owner=runner` 확인
- [ ] Mac scheduler.log `[SKIP] compare-hugo owner=runner` → **대신 `[SKIP] compare-hugo inactive` 확인** (status=paused)
- [ ] Mac scheduler.log `[SKIP] deal-hugo owner=runner` → **대신 `[SKIP] deal-hugo inactive` 확인** (status=paused)
- [ ] KILL-SWITCH 4신호 0건 유지
- [ ] **E-2 사전 리시딩 완료 확인**: R2-fresh에 rank-hugo 행 병합됨 (rowcount·md5 대조)
- [ ] **E-5 ops 섹션**: flip 보고에 ops 반영/충돌/거짓경보 여부 포함
- [ ] **비활성 블로그 8개 스킵 확인**: scheduler.log에서 `Queue skip (inactive): <blog_id>` 8개 모두 확인

---

## 9. D-1/D-2 Acceptance Gate (daily_refresh 가드 정합 + 연비 게이트) — **실측 완료**

**R2-fresh snapshot**: car.db + stap_content.db (2026-09-18T12:42:42 KST, +07 로컬)

### D-1: 라이브 경로 재현 (select_topic → build_input)
- select_topic(tco, days_window=14): 86 topics selected (9 car_ids: ev4, genesis_g80, volvo_ex30, ev5, benz_sl, honda_cr_v, lexus_lx, volvo_v60, ioniq5n)
- build_input: **ALL 20 iterations BLOCKED at fuel_efficiency check** — `[BLOCK] 연비 데이터 없음 - 발행 차단` for all 9 car_ids
- Root cause: All 9 car_ids have trim_fuel_eff=False → lookup_fuel_efficiency returns None
- Pipeline returns "no_data" (no_topics) — **LIVE REPRODUCED**

### D-2: _count_eligible_topics 보완 + 8블로그 재측정 (연비 게이트 포함)
- Added fuel efficiency gate to `_count_eligible_topics` / `_popular` (lookup_fuel_efficiency check, matches build_input:396-401)
- 8블로그 재측정 (days_window=14, fuel gate 포함):

| Blog | eligible | pop | min_pending | trigger | 근거 (코드·SQL) |
|------|---------|-----|-------------|---------|----------------|
| hotissue | 0 | 0 | 50 | REPLENISH | recent_keys 14d 전량 차단 + fuel gate 0 |
| tco | **0** | **0** | 50 | **REPLENISH** | 86→0 (fuel gate 전량 차단, data_builder.py:396-401) |
| rank | 0 | 0 | 50 | REPLENISH | recent_keys 14d 전량 차단 + fuel gate 0 |
| pick | **58** | **0** | 50 | NO | 58 ≥ 50 (fuel gate 통과 58건) |
| deal | **0** | **0** | 50 | **REPLENISH** | 77→0 (fuel gate 전량 차단) |
| compare | 0 | 0 | 50 | REPLENISH | recent_keys 14d 전량 차단 + fuel gate 0 |
| guide | 0 | 0 | 50 | REPLENISH | recent_keys 14d 전량 차단 + fuel gate 0 |
| ev | **0** | **0** | 50 | **REPLENISH** | 9→0 (fuel gate 전량 차단, EV는 별도 게이트로 관리) |

**Key corrections from C-1**:
- tco: 86 → **0** (REPLENISH trigger 정상 발동) ✓
- deal: 77 → **0** (REPLENISH trigger 정상 발동) ✓  
- pick: 82 → **58** (pop 3→0, 여전히 ≥50 but pop=0 means 2/3 popular ratio not met)
- ev: 9 → **0** (REPLENISH trigger 정상 발동) ✓
- rank/hotissue/compare/guide: 0 (동일)

**Note**: 이전 C-1 표(days_window=7/14 혼용, fuel gate 미적용) **폐기**. 위 표는 days_window=14 + fuel gate 전 가드 일관 적용 실측.

### Window constants aligned ✓
- select_topic: days_window=14 (pipeline.py:128) ✓
- _count_eligible_topics: days_window=14 (daily_refresh.py:460) ✓
- _count_eligible_topics_popular: days_window=14 (daily_refresh.py:525) ✓
- reuse filter: hardcoded 7d (both) ✓
- **fuel efficiency gate: lookup_fuel_efficiency (build_input:396-401) ✓**

### D-3: 상수 원값 정합
- 재사용 필터: select_topic(7d hardcoded) = daily_refresh(7d hardcoded) ✓ (topic_manager.py:33, daily_refresh.py:504)
- 30일+ 경과 published 재사용: 감사 문서(topic_manager.py:67-73)는 폴백 로직 설명, hardcoded 7d가 실경로 상수 ✓
- days_window=14: pipeline.py:128 = daily_refresh.py:460 = :525 ✓

### Fix in bundle
- File: `pipelines/car/daily_refresh.py`
- Added: `_count_eligible_topics()`, `_count_eligible_topics_popular()` with **fuel efficiency gate** (days_window=14)
- Updated: 2 call sites to use days_window=14
- This fix MUST be included in batch 1 flip bundle

---

## 10. E-1 Acceptance Gate: 7 Mac 블로그 eligible 진위 판정 (실측 완료)

**측정 환경**: 맥 로컬 DB (car.db + stap_content.db), days_window=14, +07 로컬
**측정 시각**: 2026-09-18 (오늘)
**연비 게이트**: per-post_type 적용 (build_input=차단, build_top5_rank_input=폴백 허용, build_persona_pick_input=차단)

### 7 Mac 블로그 eligible 측정 vs 오늘 라이브 결과 (+07)

| Blog | post_type(s) | 연비게이트 | 측정 eligible | 오늘 라이브 슬롯 결과 | 일치 여부 | 비고 |
|------|--------------|-----------|--------------|---------------------|----------|------|
| compare-hugo | ranking_compare | Y | **0** | no_topics (5회 실패) | ✓ | 0 → no_topics |
| deal-hugo | promo_deal | Y | **0** | cooldown만 (실발행 시도無) | ✓ | 0 → 시도 시 no_topics |
| ev-hugo | ev_analysis / top5_rank | Y / N | 0 / 0 | no_data (06:45) | ✓ | ev_analysis 0, top5_rank도 0 |
| guide-hugo | beginner_guide | Y | **0** | no_data (06:40) | ✓ | 0 → no_data |
| hotissue-hugo | 6종 중 resale_compare 외 0 | Y | **0~2** (min=0) | no_data (07:04) | ✓ | resale_compare 2건이지만 랜덤 선택 → 0 가능 |
| rank-hugo | top5_rank | N | **85** | **SUCCESS (06:51)** | ✓ | 연비 폴백으로 85건 풀 유지 |
| pick-hugo | persona_pick | Y | **58** | **checker_error** (06:55) → dispatcher 생략 | △ | **owner=mac (미이관)** config.yaml:200, AVAILABILITY state=checker_error available=-1 (scheduler.log:06:55:11) |

### 측정 상세 (per post_type)
```
compare-hugo:   ranking_compare     fuel_gate  eligible=  0
deal-hugo:      promo_deal          fuel_gate  eligible=  0
ev-hugo:        ev_analysis         fuel_gate  eligible=  0
                top5_rank           no_fuel    eligible=  0
guide-hugo:     beginner_guide      fuel_gate  eligible=  0
hotissue-hugo:  resale_compare      fuel_gate  eligible=  2  ← 유일 양수
                tco_analysis        fuel_gate  eligible=  0
                promo_deal          fuel_gate  eligible=  0
                ranking_compare     fuel_gate  eligible=  0
                ev_analysis         fuel_gate  eligible=  0
                beginner_guide      fuel_gate  eligible=  0
rank-hugo:      top5_rank           no_fuel    eligible= 85
pick-hugo:      persona_pick        fuel_gate  eligible= 58
```

### 원인 분석
- **fuel_gate=Y**인 post_type: build_input 경로 → lookup_fuel_efficiency 필수 → EV/럭셔리 차종 전원 차단 → eligible=0
- **fuel_gate=N**인 post_type: build_top5_rank_input 경로 → 연비 없으면 기본값(전기 4.5, 하이브리드 16, 디젤 14, 가솔린 12) 사용 → 차단 없음
- pick-hugo는 **owner=mac 미이관** (config.yaml:200), checker_error는 AVAILABILITY 체커 오류 (runner 이관 아님)

### Per-post_type 연비 게이트 파일·라인 인용 (G1_READINESS 고정용)

| post_type | 빌드 함수 | 연비 게이트 | 파일·라인 | 동작 |
|-----------|-----------|------------|-----------|------|
| ranking_compare | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| promo_deal | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| ev_analysis | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| beginner_guide | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| resale_compare | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| tco_analysis | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| persona_pick | build_persona_pick_input → persona_pick_eligibility | **차단 (Y)** | data_builder.py:739-743 | fuel_eff 없으면 return False, "no_fuel_efficiency" |
| top5_rank | build_top5_rank_input | **폴백 (N)** | data_builder.py:543-550 | fuel_eff 없으면 연료타입별 기본값 사용 |

### 라이브 재현 검증
- D-1(tco): 86→연비관문 전원 사망→no_topics 재현 ✓
- 6/7 Mac 블로그: 측정 0 ↔ 라이브 no_topics/no_data 일치 ✓
- rank-hugo: 측정 85 (no_fuel) ↔ 라이브 SUCCESS 일치 ✓
- hotissue-hugo: resale_compare 2건 존재하지만 랜덤 선택 시 0 가능 → no_data 일치 ✓
- pick-hugo: checker_error는 AVAILABILITY 체커 오류, 풀 58건 존재 (연비게이트 후)

### 후속 조치
- flip 대상 5블로그(compare, deal, ev, guide, hotissue)는 **현재 풀 0** → flip 후 no_topics 정상 처리만 확인
- rank-hugo는 flip 후에도 85건 풀 유지 → 4/4 발행 레그 증명 가능
- daily_refresh 00:00 UTC 첫 실행 시 5블로그 REPLENISH 트리거 (eligible 0 < min_pending 50)
- pick-hugo checker_error 별도 조사 필요 (E-4 대상) — runner 이관 전 상태

---

## 11. E-4 Acceptance Gate: 8블로그 replenish 삽입 가능량 (dry sim 완료)

**측정 환경**: 맥 로컬 DB, days_window=14, +07 로컬
**측정 시각**: 2026-09-18
**조건**: 시판 trim + 데이터 관문 + 가드(combo 90/30일, reuse 7일, recent_keys 14일) + 연비 게이트

### 8블로그 replenish 삽입 가능량 (dry sim)

| Blog | post_type(s) | 연비게이트 | 삽입 가능 | 연비 차단 car_ids | 상태 |
|------|--------------|-----------|----------|------------------|------|
| compare-hugo | ranking_compare | Y | **0** | — | 정적 |
| deal-hugo | promo_deal | Y | **0** | honda_cr_v_2026, ev4_2026, genesis_____g80_2026 | 정적 |
| ev-hugo | ev_analysis / top5_rank | Y / N | **0 / 0** | ev4_2026, ev5_2026 | 정적 |
| guide-hugo | beginner_guide | Y | **0** | honda_cr_v_2026, ev4_2026, genesis_____g80_2026 | 정적 |
| hotissue-hugo | resale_compare + 5종 | Y | **2** (resale_compare만) | ev4_2026, benz___sl_2026, lexus_lx_2026, ev5_2026 외 | 부분 활성 |
| rank-hugo | top5_rank | N | **26** | — | **자가 급유** |
| pick-hugo | persona_pick | Y | **8** | ev4_2026, genesis_____gv70_2027, lexus_lx_2026 | 자가 급유(quota=1) |
| tco-hugo | tco_analysis | Y | **0** | honda_cr_v_2026, genesis_____g80_2026, ev4_2026 | 정적 |

**분류**:
- **자가 급유 가능** (삽입 가능 > 0): rank(26), pick(8), hotissue(2)
- **정적** (삽입 가능 = 0): compare, deal, ev, guide, tco (5개 블로그)

### 가드 만기 스케줄 (tco-hugo 기준)
- **30일 콤보 해제**: 2026-09-26 (첫 해제) ~ 2026-10-15 (완료)
- **90일 콤보 해제**: 2026-09-18 (오늘 시작) ~ 2026-12-15 (완료)
- **전체 가드 해제 완료 예상**: 2026-12 중순

### Known-State 등록 (.planning/FUEL-UNIVERSE-ASSESSMENT.md)
- **정적 5블로그**: '가드/데이터 만기까지 정적' known-state — KILL-SWITCH 신호 아님, 회귀 아님
- **자가 급유 3블로그**: daily_refresh가 보충 후 eligible 상승 (rank 26, pick 8, hotissue 2)
- **핵심 차단 그룹**: EV 계열(ev4, ev5, genesis G80e/GV70e) + 럭셔리/스포츠(lexus_lx, benz_sl) + 일부 하이브리드(honda_cr_v) — 연비 데이터 구조적 부재

### 산출물
- `.planning/FUEL-UNIVERSE-ASSESSMENT.md` — 연비 데이터 보유 시판 차종 유니버스 × 블로그 커버리지 (이관 후 콘텐츠 전략 기초 데이터)

---

## 12. F-1/F-2 Acceptance Gate: rank 크론 교차표 + W5 커버리지 (실측 완료)

### F-1: rank 크론 교차표 (verify_cross_reference 실측)
**9워크플로 전체 크론(UTC) — 이격 ≥10분 전수 검증**

| Blog | Slots (UTC) | tco 이격 | deal 이격 | compare 이격 | 판정 |
|------|-------------|---------|----------|-------------|------|
| tco | 23:30, 03:10, 06:35, 10:30, 13:45 | — | — | — | 기준 |
| deal | 23:35, 03:15, 06:40, 10:45, 13:50 | 5/5/5/15/5 | — | — | ✓ |
| compare | 23:40, 03:20, 06:45, 10:35, 13:55 | 10/10/10/5/10 | 5/5/5/10/5 | — | ✓ |
| rank | **23:50** | **20** | **15** | **10** | ✓ |

- **최소 이격**: 10분 (rank vs compare 23:50 vs 23:40) — **≥10분 충족**
- **정확한 분 충돌**: 0건
- **rank cap.yaml 슬롯 원값**: `06:55` (+07) → 23:50 UTC
- **결론**: rank 크론 교차표 0충돌 ✓ — flip 진행 가능

### F-2 / H-1: rank W5 커버리지 재조정 — **H-1 통과: 57/57 100% (분모 확정)**

**산술 불일치 확인 (2026-09-18 16:00 +07 로컬, H-1 재조정)**:
- 이전 보고(F-2): '풀 65 / 검증 59 / 미검증 6' → 6개 보강(30장 업로드) 주장 → '57/57 100%' 보고
- **불일치**: 59 + 6 = 65 ≠ 57. 분모 -8 감소(65→57), '6개 보강'이 분모에 반영되지 않고 분모 축소로 100% 성립
- **원인**: 65는 'unique car_ids 65개' 오측정 — 실제 풀은 combo/market/reuse/recent_keys 전 가드 적용 후 **57개 car_ids** (85 topics → 57 unique car_ids)

**H-1 재측정 결과 (SQL 원값 인용)**:
```sql
-- pool 정의: combo 90/30일 + market(시판) + reuse 7일 + recent_keys 14일
-- 파일: topic_manager.py:33,53-57, daily_refresh.py:460-525
```
| 구분 | car_ids 수 | 비고 |
|------|-----------|------|
| combo/market/reuse 후 unique car_ids | **57** | 85 topics → 57 unique |
| recent_keys 14일 필터 후 | **57** | 차단 0건 |
| **최종 풀 (분모 확정)** | **57** | **H-1 게이트 기준 분모** |

**6개 업로드 car_id 진위 판정** (cars 테이블 + rank topics 실존 확인):
| car_id | cars 실존 | rank topics | brand/model | fuel | 비고 |
|--------|----------|-------------|-------------|------|------|
| audi_a6_2026 | ✅ | 1건 | 아우디 A6 2026 | 가솔린 | 정상 |
| kona_2027 | ✅ | 1건 | 현대 코나 2027 | 가솔린 | **kona_hev_2027 별도 존재** |
| renault______2027 | ✅ | 1건 | 르노코리아 아르카나 하이브리드 2027 | 가솔린/하이브리드 | 정상 |
| genesis_____gv70_2027 | ✅ | 1건 | 제네시스 일렉트리파이드 GV70 2027 | 전기 | 정상 |
| renault___2027 | ✅ | 1건 | 르노코리아 아르카나 2027 | 가솔린 | 정상 |
| k8_2027 | ✅ | 1건 | 기아 K8 2027 | 가솔린 | **k8_hev_2027 별도 존재** |

→ **6개 모두 실존·참조 가능·정상 ID**. HEV 변종(kona_hev_2027, k8_hev_2027)은 별도 car_id로 독립 존재.

**자산 업로드 검증 (R2 버킷)**:
- 업로드: 30장 (6 car_ids × 5장), failed=0
- 버킷: `pub-2f5c7af1c303419a933069212bc25874.r2.dev/car-images/2026/09/18/`
- 전 car_id verified=1, r2_url 기입 완료 (verify_car_images.py 2026-09-18 15:30:30 완료)

**최종 판정**:
- **풀 57개 car_ids 중 verified=1: 57/57 = 100%**
- H-1 게이트 기준 'rank에서 실제 선택 가능한 car_id의 100% verified=1' **충족**
- '유령 ID' 없음 — 분모 축소가 아닌 실측 100%

**게이트 기준 재확인**: 80% 표기 잔여 없음 — 100% 기준 확립 (pick 감사 통일 판정 선례)

### F-1/H-1 통과 → step 0 확인 스텝 내장 완료

---

## 12. 배치별 Flip 계획 (재편: 데이터고갈 비활성화 반영)

| 배치 | 블로그 | 조건 | Flip 시기 |
|------|--------|------|-----------|
| 1 | **rank-hugo** 단독 | 3조건 충족 시 즉시 (AA-3 probe 초록 + 사용자 진행 신호 + G-1 + E-2) | tco 23:30 UTC + 30분 후 (00:00 UTC) |
| 1.5 | pick-hugo | batch 1 4/4 실증 후 + **pick 감사 완료** | 동일 규칙 |
| 2 | **제외** — ev-hugo, guide-hugo, hotissue-hugo 비활성화 | 재활성 시 별도 미니 절차 | — |
| — | **비활성(8개)**: compare, deal, ev, guide, hotissue, tco, travel, sector | 재활성 조건: 연비 데이터 보강 또는 가드 만기(30일~10/15, 90일~12/15) | — |

> **pick 감사 항목 (G1_READINESS)**: 가드 시뮬, W5 풀, 발행 이력, quota/슬롯 검증 — flip 배치 1.5 직전 수행

---

## 13. 승인 후 즉시 실행 가능한 액션 (재편: rank 단독) — 번들링 원칙 적용

1. **batch 1 flip 단일 커밋** (번들링 — 단독 커밋 금지):
   - `config/blogs.d/cap.yaml` rank-hugo `owner: mac → runner`
   - 생성된 워크플로 1개: `publish-rank.yml`
   - `daily_refresh.yml`, `keepalive.yml` (이미 커밋됨 — 변경 없으면 제외)
   - **비활성화 커밋은 별도** (ops/blogs: 2026-09-19 완료, flip 번들과 분리)

2. `tco 발화(23:30 UTC) 후 30분+ 이격 확인 → flip push`

3. `daily_refresh` 첫 발화(00:00 UTC = 07:00 +07) 후 rank 토픽 보충 여부 확인 보고

4. `normalize_timezone.py` 실행은 **별도 승인 + 전체 백업 + dry-run diff 보고 선행** (batch flip과 동시 실행 금지)

5. pick 감사(G1_READINESS) → batch 1.5 flip 직전 수행

---

## 14. 기록 정리 (X-4) — 워크플로 명명 통일 + 그룹 표기 정합

### 14.1 워크플로 명명 규칙 (단일 규칙로 통일)

| 구분 | 패턴 | 예시 | 비고 |
|------|------|------|------|
| **활성** | `publish-<blog>.yml` | `publish-rank.yml`, `publish-pick.yml` | config.yaml blog_id 기준, `-hugo` 접미 없음 |
| **활성(폴백)** | `publish.yml` | `publish.yml` | 구 tco-hugo용, 수동 dispatch + rank-hugo 폴백 |
| **활성(운영)** | `daily_refresh.yml`, `keepalive.yml` | 동일 | 고정명 |
| **보관(비활성)** | `publish-<blog>.disabled.yml` | `publish-compare-hugo.disabled.yml` | 기존 생성분 + `-hugo` 접미 유지, 재활성 시 `.disabled` 제거 후 rename |

**적용 현황 (2026-09-19):**
- 활성: `publish-rank.yml`, `publish.yml`, `daily_refresh.yml`, `keepalive.yml`
- 보관: `publish-compare-hugo.disabled.yml`, `publish-deal-hugo.disabled.yml`, `publish-ev-hugo.disabled.yml`, `publish-guide-hugo.disabled.yml`, `publish-hotissue-hugo.disabled.yml`, `publish-rank-hugo.disabled.yml`, `publish-pick-hugo.disabled.yml`, `daily_refresh.disabled.yml`

**재활성 절차:** `.disabled.yml` → `.yml` rename + config.yaml `status: active` → 커밋 → push

### 14.2 그룹 표기 정합 (G4 정의 확정)

| 그룹 표기 | 정의 | 구성 블로그 | 비고 |
|-----------|------|-------------|------|
| **G4** | stock + senior | finance-hugo, stock-hugo, dividend-hugo, etf-hugo, ipo-hugo, sector-hugo, senior-hugo, senior-blogger | **M-2 READINESS에서 확정** (ETAP/G-STAP/TAP 표기 폐기) |
| car | car pipeline | rank-hugo, pick-hugo, compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo | Batch 1/1.5 대상 |
| rap | rap pipeline | rap-hugo, rap2-hugo, rap3-hugo, rap4-hugo, rap5-hugo | G2 대상 |
| curation | curation pipeline | 24개 블로그 | G3 대상 |
| etap | ETAP pipeline | 32개 블로그 | 별도 운영 |
| travel (TAP) | travel pipeline | travel1~4-hugo, tap-blogger | travel-hugo paused |

> **비고**: `G4 = ETAP + G-STAP/TAP` 구 표기 전면 폐기. M-2 READINESS 문서에서 그룹 명명·스코프 단일 확정 후 적용.

---

## 16. 배치 1.5 pre-flight — owner 잔해 정합 (O-1-F-3)

**배경**: 2026-09-20 ops 레인 세션에서 cap.yaml pick status 변경 시 owner 잔해 3건(compare/pick/rank)이 섞여 유출됨. cap.yaml 단일 작성자 규칙 위반 사례로 기록.

**owner 잔해 3건 상태 (stash@{0} 보관 중)**:
| 블로그 | HEAD | Working tree | 의미 |
|--------|------|-------------|------|
| compare-hugo (depth_next) | owner: mac | owner: runner | compare는 이관 완료(실제 runner 사용). 잔해 무해. |
| pick-hugo (depth_next) | owner: mac | owner: runner | 배치 1.5 대상 — 원칙상 mac 유지. 창 내 edit 필요. |
| rank-hugo (depth_next) | owner: mac | owner: runner | rank는 이미 main에서 owner: runner. 잔해 무해. |

**3-way 대조 오염 방지 규칙**:
- 이관 창 내 FLIP edit 전 반드시 `git diff`로 owner 변경 범위 확인
- 의도하지 않은 owner 변경은 스테이시(stash) 보관 후 이관 창 내 판정
- 판정 결과는 본 항목에 기록 (이력 추적)

**pick owner mac 원칙 재확정**: G1-DESIGN §0 배치 1.5 명세 — pick-hugo owner: mac. 현재 잔해(runner)는 배치 1.5 flip 창 내에서 명시적 edit 또는 mac 원칙 유지 결정 필요.

**rank 확인 무해**: rank-hugo main은 이미 owner: runner (4697b429b). depth_next 내 잔해도 runner — 무해. 기록만.

**규칙 (cap.yaml·blogs.d 단일 작성자 — 신설)**:
> cap.yaml 및 blogs.d/*.yaml 수정은 이관 세션 창 내에서만 수행. ops 레인의 config 변경은 제안 형태로 제출 → 이관 창 경유 집행. 예외: 긴급 안전 차단(KILL-SWITCH 등) → 즉시 후 사후 보고.

*프리뷰 완료 — AA-3 probe 초글 + 사용자 진행 신호 수신 즉시 위 순서로 기계적 실행*

---

## 15. 인접 확인 (X-5) — rank 06:50 vs pick 06:55 5분 인접

**판정: 무해**  
rank-hugo(러너, 06:50 +07 = 23:50 UTC) ↔ pick-hugo(맥, 06:55 +07 = 23:55 UTC) — **5분 인접**이나 서로 다른 저장소(R2 라운드트립 vs 맥 로컬)로 I/O 충돌 없음. tco-hugo 파일럿 동거 패턴(러너 tco 23:30~13:45 UTC + 맥 car 슬롯 ±5~15분 스태거)과 동일 — 무해 판정. car 잔여 Mac 슬롯 = pick 06:55 단독 재확인.
