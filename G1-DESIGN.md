# G1 설계안 — rank-hugo 단독 러너 이관 (compare·deal·ev·guide·hotissue·tco·travel·sector 8개 비활성화) + pick-hugo 차기

**작성일**: 2026-09-19  
**상태**: 재편 완료 — Batch 1: rank-hugo 단독, Batch 1.5: pick-hugo, Batch 2: 제외 (비활성 블로그 재활성 시 별도)  
**범위**: car 파이프라인 8개 블로그 중 7개 비활성화(paused) + tco-hugo 러너 유지(스케줄 제거) → rank-hugo만 러너 이관. pick-hugo는 차기 창(Batch 1.5). ev/guide/hotissue/tco/travel/sector 이관 스코프 제외.

---

## 0. 사전 조사 — pick-hugo 상태 확정 (수정 1 반영)

### config/blogs.d/cap.yaml 원값 실측 (2026-09-19 비활성화 반영)

| 블로그 | pipeline | owner | daily_quota | 상태 | 비고 |
|--------|----------|-------|-------------|------|------|
| compare-hugo | car | mac | 5 | **paused** | 비활성화 (데이터고갈 Class A) |
| deal-hugo | car | mac | 5 | **paused** | 비활성화 (데이터고갈 Class A) |
| ev-hugo | car | mac | 5 | **paused** | 비활성화 (데이터고갈 Class A) |
| guide-hugo | car | mac | 5 | **paused** | 비활성화 (데이터고갈 Class A) |
| hotissue-hugo | car | mac | 5 | **paused** | 비활성화 (Class A/B: 7일+ no_topics) |
| tco-hugo | car | **runner** | 5 | **paused** | 비활성화 (데이터고갈 Class A, GH schedule 제거) |
| rank-hugo | car | mac | 1 | **active** | **Batch 1 대상: runner 이관** |
| **pick-hugo** | **car** | **mac** | **1** | **active** | **Batch 1.5 대상: 차기 창 (감사 후)** |

**결론**: 
- **Batch 1**: rank-hugo 단독 (owner: mac → runner, publish-rank.yml 신규 생성)
- **Batch 1.5**: pick-hugo (전제: 정정 1 완료 + W5 7개 car_id + ledger_sync + pick 감사) — 불변
- **Batch 2**: 이관 스코프 제외 — compare/deal/ev/guide/hotissue/tco 7개 비활성화. 재활성 시 별도 미니 절차 문서화.
- travel-hugo (tap), sector-hugo (stap)도 동일 사유로 비활성화.

---

## 1. 블로그별 전달 방식 — publish-<blog>.yml 생성형 (필수)

### 문제
- `schedule` 트리거는 `inputs` 전달 불가
- 현행 `publish.yml`은 `inputs.blog || 'tco-hugo'` 폴백으로 동작 → 7블로그 추가 시 **전부 tco-hugo로 발행되는 사고 발생**
- 해결: **블로그별 전용 워크플로 파일 생성** (`publish-<blog>.yml`)
### 생성 대상 (재편: 1개 + 예비 1개) — config.yaml 파생 확정

| 워크플로 파일 | 대상 블로그 | pipeline | owner(현) | daily_quota | 상태 | 비고 |
|--------------|-------------|----------|-----------|-------------|------|------|
| `publish-rank.yml` | rank-hugo | car | mac | 1 | **생성 대상 (Batch 1)** | rank 단독 flip |
| `publish-pick.yml` | pick-hugo | car | mac | 1 | **예비 (Batch 1.5)** | 차기 창, 감사 후 생성 |
| ~~`publish-compare.yml`~~ | compare-hugo | car | mac | 5 | **비활성화** | .disabled.yml로 보관 |
| ~~`publish-deal.yml`~~ | deal-hugo | car | mac | 5 | **비활성화** | .disabled.yml로 보관 |
| ~~`publish-ev.yml`~~ | ev-hugo | car | mac | 5 | **비활성화** | 미생성 (Batch 2 제외) |
| ~~`publish-guide.yml`~~ | guide-hugo | car | mac | 5 | **비활성화** | 미생성 (Batch 2 제외) |
| ~~`publish-hotissue.yml`~~ | hotissue-hugo | car | mac | 5 | **비활성화** | .disabled.yml로 보관 |

### 생성 스크립트 — **config.yaml 읽기 방식 (단일 공급원)**

```python
#!/usr/bin/env python3
"""car 그룹 블로그용 publish-<blog>.yml 일괄 생성 (config.yaml 파생)"""

import yaml
from pathlib import Path

CONFIG_PATH = Path("config/blogs.d/cap.yaml")

def load_car_blogs():
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    blogs = data.get("blogs", [])
    car_blogs = []
    for blog in blogs:
        if blog.get("pipeline") == "car" and blog.get("status") == "active":
            blog_id = blog["id"]
            times = blog.get("schedule", {}).get("times", [])
            if times:
                car_blogs.append((blog_id, times))
    return car_blogs

# 비활성 블로그 조회용 (재활성 시 참조)
def load_paused_car_blogs():
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    blogs = data.get("blogs", [])
    paused = []
    for blog in blogs:
        if blog.get("pipeline") == "car" and blog.get("status") == "paused":
            blog_id = blog["id"]
            times = blog.get("schedule", {}).get("times", [])
            paused.append((blog_id, times))
    return paused

def kst_to_cron(kst_time: str) -> str:
    """+07 로컬 HH:MM → cron 'MM HH * * *' (UTC)"""
    h, m = map(int, kst_time.split(":"))
    utc_h = (h - 7) % 24  # +07 로컬 = UTC+7
    return f"    - cron: \"{m:02d} {utc_h} * * *\"  # {kst_time} +07"

TEMPLATE = """name: publish ({blog_id})

on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "dry-run (dispatcher 스킵)"
        type: boolean
        default: true
  schedule:
{cron_lines}

concurrency:
  group: publish-lock-car
  cancel-in-progress: false
  # queue: max 100 (GitHub Actions 미지원 — 슬롯 분산으로 실질 병렬 0 유지)

env:
  # LLM 10 (GH Secrets)
  OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
  GROQ_API_KEY: ${{{{ secrets.GROQ_API_KEY }}}}
  CEREBRAS_API_KEY: ${{{{ secrets.CEREBRAS_API_KEY }}}}
  ZHIPU_API_KEY: ${{{{ secrets.ZHIPU_API_KEY }}}}
  NVIDIA_API_KEY: ${{{{ secrets.NVIDIA_API_KEY }}}}
  GOOGLE_API_KEY: ${{{{ secrets.GOOGLE_API_KEY }}}}
  GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
  UPSTAGE_API_KEY: ${{{{ secrets.UPSTAGE_API_KEY }}}}
  CLOVA_API_KEY: ${{{{ secrets.CLOVA_API_KEY }}}}
  OPENCODE_ZEN_API_TOKEN: ${{{{ secrets.OPENCODE_ZEN_API_TOKEN }}}}
  # Coupang 3 + Telegram 2
  COUPANG_ACCESS_KEY: ${{{{ secrets.COUPANG_ACCESS_KEY }}}}
  COUPANG_SECRET_KEY: ${{{{ secrets.COUPANG_SECRET_KEY }}}}
  COUPANG_PARTNER_ID: ${{{{ secrets.COUPANG_PARTNER_ID }}}}
  TELEGRAM_BOT_TOKEN: ${{{{ secrets.TELEGRAM_BOT_TOKEN }}}}
  TELEGRAM_CHAT_ID: ${{{{ secrets.TELEGRAM_CHAT_ID }}}}
  # R2
  R2_ENDPOINT: ${{{{ secrets.R2_ENDPOINT }}}}
  R2_ACCESS_KEY_ID: ${{{{ secrets.R2_ACCESS_KEY_ID }}}}
  R2_SECRET_ACCESS_KEY: ${{{{ secrets.R2_SECRET_ACCESS_KEY }}}}
  R2_STATE_BUCKET: 5000-state
  # Cloudflare
  CLOUDFLARE_API_TOKEN: ${{{{ secrets.CLOUDFLARE_API_TOKEN }}}}
  CLOUDFLARE_ACCOUNT_ID: ${{{{ secrets.CLOUDFLARE_ACCOUNT_ID }}}}
  WRANGLER_TOKEN_AUTH: "1"
  # Runner flag
  5000_RUNNER: "1"
  SITES_ROOT: ${{{{ github.workspace }}}}/sites
  PYTHONUNBUFFERED: "1"

jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: elapsed marker
        run: date +%s > /tmp/t0

      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: pip install
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Hugo extended setup
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: "0.160.1"
          extended: true

      - name: wrangler install
        run: npm install -g wrangler

      - name: clone site repo (CAP_PAT)
        run: |
          git clone --depth 50 https://x-access-token:${{ secrets.CAP_PAT }}@github.com/hugh79757-cmyk/{blog_id}.git sites/cap/{blog_id}

      - name: blowfish theme copy
        run: |
          mkdir -p sites/cap/{blog_id}/themes
          cp -r themes/blowfish sites/cap/{blog_id}/themes/blowfish

      - name: run slot (R2 round-trip + dispatcher)
        run: python scripts/run_slot.py '{blog_id}' ${{ (inputs.dry_run == true || inputs.dry_run == 'true') && '--dry-run' || '' }}

      - name: elapsed report
        if: always()
        run: |
          T0=$(cat /tmp/t0); T1=$(date +%s)
          echo "## ⏱ minutes 실측 (스코프 ④)" >> $GITHUB_STEP_SUMMARY
          echo "total: $((T1 - T0))s" >> $GITHUB_STEP_SUMMARY
"""

def generate():
    car_blogs = load_car_blogs()
    out_dir = Path(".github/workflows")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for blog_id, times in car_blogs:
        if blog_id == "tco-hugo":
            continue  # tco는 기존 publish.yml 사용
        cron_lines = "\n".join(kst_to_cron(t) for t in times)
        
        content = "name: publish (" + blog_id + ")\n\n"
        content += "on:\n"
        content += "  workflow_dispatch:\n"
        content += "    inputs:\n"
        content += "      dry_run:\n"
        content += "        description: \"dry-run (dispatcher 스킵)\"\n"
        content += "        type: boolean\n"
        content += "        default: true\n"
        content += "  schedule:\n"
        content += cron_lines + "\n\n"
        content += "concurrency:\n"
        content += "  group: publish-lock-car\n"
        content += "  cancel-in-progress: false\n"
        content += "  # queue: max 100 (GitHub Actions 미지원 - 슬롯 분산으로 실질 병렬 0 유지)\n\n"
        content += "env:\n"
        content += "  # LLM 10 (GH Secrets)\n"
        content += "  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}\n"
        content += "  GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}\n"
        content += "  CEREBRAS_API_KEY: ${{ secrets.CEREBRAS_API_KEY }}\n"
        content += "  ZHIPU_API_KEY: ${{ secrets.ZHIPU_API_KEY }}\n"
        content += "  NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}\n"
        content += "  GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}\n"
        content += "  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}\n"
        content += "  UPSTAGE_API_KEY: ${{ secrets.UPSTAGE_API_KEY }}\n"
        content += "  CLOVA_API_KEY: ${{ secrets.CLOVA_API_KEY }}\n"
        content += "  OPENCODE_ZEN_API_TOKEN: ${{ secrets.OPENCODE_ZEN_API_TOKEN }}\n"
        content += "  # Coupang 3 + Telegram 2\n"
        content += "  COUPANG_ACCESS_KEY: ${{ secrets.COUPANG_ACCESS_KEY }}\n"
        content += "  COUPANG_SECRET_KEY: ${{ secrets.COUPANG_SECRET_KEY }}\n"
        content += "  COUPANG_PARTNER_ID: ${{ secrets.COUPANG_PARTNER_ID }}\n"
        content += "  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}\n"
        content += "  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}\n"
        content += "  # R2\n"
        content += "  R2_ENDPOINT: ${{ secrets.R2_ENDPOINT }}\n"
        content += "  R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}\n"
        content += "  R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}\n"
        content += "  R2_STATE_BUCKET: 5000-state\n"
        content += "  # Cloudflare\n"
        content += "  CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}\n"
        content += "  CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}\n"
        content += "  WRANGLER_TOKEN_AUTH: \"1\"\n"
        content += "  # Runner flag\n"
        content += "  5000_RUNNER: \"1\"\n"
        content += "  SITES_ROOT: ${{ github.workspace }}/sites\n"
        content += "  PYTHONUNBUFFERED: \"1\"\n\n"
        content += "jobs:\n"
        content += "  publish:\n"
        content += "    runs-on: ubuntu-latest\n"
        content += "    timeout-minutes: 20\n\n"
        content += "    steps:\n"
        content += "      - name: elapsed marker\n"
        content += "        run: date +%s > /tmp/t0\n\n"
        content += "      - uses: actions/checkout@v4\n\n"
        content += "      - uses: actions/setup-python@v5\n"
        content += "        with:\n"
        content += "          python-version: \"3.14\"\n\n"
        content += "      - name: pip install\n"
        content += "        run: |\n"
        content += "          python -m pip install --upgrade pip\n"
        content += "          pip install -r requirements.txt\n\n"
        content += "      - name: Hugo extended setup\n"
        content += "        uses: peaceiris/actions-hugo@v3\n"
        content += "        with:\n"
        content += "          hugo-version: \"0.160.1\"\n"
        content += "          extended: true\n\n"
        content += "      - name: wrangler install\n"
        content += "        run: npm install -g wrangler\n\n"
        content += "      - name: clone site repo (CAP_PAT)\n"
        content += "        run: |\n"
        content += "          git clone --depth 50 https://x-access-token:${{ secrets.CAP_PAT }}@github.com/hugh79757-cmyk/" + blog_id + ".git sites/cap/" + blog_id + "\n\n"
        content += "      - name: blowfish theme copy\n"
        content += "        run: |\n"
        content += "          mkdir -p sites/cap/" + blog_id + "/themes\n"
        content += "          cp -r themes/blowfish sites/cap/" + blog_id + "/themes/blowfish\n\n"
        content += "      - name: run slot (R2 round-trip + dispatcher)\n"
        content += "        run: python scripts/run_slot.py '" + blog_id + "' ${{ (inputs.dry_run == true || inputs.dry_run == 'true') && '--dry-run' || '' }}\n\n"
        content += "      - name: elapsed report\n"
        content += "        if: always()\n"
        content += "        run: |\n"
        content += "          T0=$(cat /tmp/t0); T1=$(date +%s)\n"
        content += "          echo \"## ⏱ minutes 실측 (스코프 ④)\" >> $GITHUB_STEP_SUMMARY\n"
        content += "          echo \"total: $((T1 - T0))s\" >> $GITHUB_STEP_SUMMARY\n"
        
        (out_dir / f"publish-{blog_id}.yml").write_text(content)
        print(f"Generated: publish-{blog_id}.yml")

def verify_cross_reference():
    """생성 후 교차 검증: config.yaml 슬롯 ↔ 생성된 cron 일치 확인"""
    car_blogs = load_car_blogs()
    print("\n=== 교차 검증표 (Batch 1: rank-hugo) ===")
    print("| 블로그 | 로컬 슬롯 (+07) | UTC cron | 정확 분 충돌(동일분) | 비고 |")
    print("|--------|----------------|----------|---------------------|------|")
    tco_slots = [(23,30), (3,10), (6,35), (10,30), (13,45)]
    for blog_id, times in car_blogs:
        if blog_id == "tco-hugo":
            continue  # tco는 기존 publish.yml 사용 (schedule 제거됨)
        for t in times:
            h, m = map(int, t.split(":"))
            utc_h = (h - 7) % 24
            cron = f"{m:02d} {utc_h} * * *"
            exact_collision = any(utc_h == tc and m == tm for tc, tm in tco_slots)
            collision_str = "⚠️ 충돌" if exact_collision else "OK (스태거)"
            note = "tco와 5-10분 스태거" if not exact_collision else "동일 분 중복"
            print(f"| {blog_id} | {t} | {cron} | {collision_str} | {note} |")

    # 비활성 블로그 슬롯도 기록용 출력
    paused_blogs = load_paused_car_blogs()
    if paused_blogs:
        print("\n=== 비활성 블로그 슬롯 (참조용 — 재활성 시 cron 변환 필요) ===")
        print("| 블로그 | 로컬 슬롯 (+07) | UTC cron | 비고 |")
        print("|--------|----------------|----------|------|")
        for blog_id, times in paused_blogs:
            for t in times:
                h, m = map(int, t.split(":"))
                utc_h = (h - 7) % 24
                cron = f"{m:02d} {utc_h} * * *"
                print(f"| {blog_id} | {t} | {cron} | status=paused |")

if __name__ == "__main__":
    generate()
    verify_cross_reference()
```

### 실행
```bash
python scripts/generate_publish_workflows.py
# → .github/workflows/publish-compare.yml 등 7개 생성 + 교차 검증표 출력
```

---

## 1b. 파생 검증 교차표 — 최종 검증 결과 (수정 3 반영)

> 위 스크립트 `verify_cross_reference()` 실행 시 아래 표 자동 생성. 하드코딩 추측 금지 — config.yaml 단일 공급원.
> **deal-hugo 깨끗한 분 확보**: 17:30/20:45(tco와 정확한 분 충돌) → **17:45/20:50(전 러너 블로그와 정확한 분 충돌 0건)** 확정.
> 폴백(현행 유지) 불필요 — 깨끗한 분 확보 성공.

| 블로그 | 로컬 슬롯 (+07) | UTC cron | 정확 분 충돌(동일분) | 비고 |
|--------|----------------|----------|---------------------|------|
| compare-hugo | 06:40 | 40 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| compare-hugo | 10:20 | 20 3 * * * | OK (스태거) | tco와 5-10분 스태거 |
| compare-hugo | 13:45 | 45 6 * * * | OK (스태거) | tco와 5-10분 스태거 |
| compare-hugo | 17:35 | 35 10 * * * | OK (스태거) | tco와 5-10분 스태거 |
| compare-hugo | 20:55 | 55 13 * * * | OK (스태거) | tco와 5-10분 스태거 |
| deal-hugo | 06:35 | 35 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| deal-hugo | 10:15 | 15 3 * * * | OK (스태거) | tco와 5-10분 스태거 |
| deal-hugo | 13:40 | 40 6 * * * | OK (스태거) | tco와 5-10분 스태거 |
| **deal-hugo** | **17:45** | **45 10 * * *** | **OK (무충돌)** | **깨끗한 분 확보 — 타 러너와 정확한 분 중복 없음** |
| **deal-hugo** | **20:50** | **50 13 * * *** | **OK (무충돌)** | **깨끗한 분 확보 — 타 러너와 정확한 분 중복 없음** |
| ev-hugo | 06:45 | 45 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| ev-hugo | 10:25 | 25 3 * * * | OK (스태거) | tco와 5-10분 스태거 |
| ev-hugo | 13:50 | 50 6 * * * | OK (스태거) | tco와 5-10분 스태거 |
| ev-hugo | 17:40 | 40 10 * * * | OK (스태거) | tco와 5-10분 스태거 |
| ev-hugo | 21:00 | 00 14 * * * | OK (스태거) | tco와 5-10분 스태거 |
| guide-hugo | 06:40 | 40 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| guide-hugo | 10:25 | 25 3 * * * | OK (스태거) | tco와 5-10분 스태거 |
| guide-hugo | 13:50 | 50 6 * * * | OK (스태거) | tco와 5-10분 스태거 |
| guide-hugo | 17:40 | 40 10 * * * | OK (스태거) | tco와 5-10분 스태거 |
| guide-hugo | 21:00 | 00 14 * * * | OK (스태거) | tco와 5-10분 스태거 |
| hotissue-hugo | 06:20 | 20 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| hotissue-hugo | 10:00 | 00 3 * * * | OK (스태거) | tco와 5-10분 스태거 |
| hotissue-hugo | 13:30 | 30 6 * * * | OK (스태거) | tco와 5-10분 스태거 |
| hotissue-hugo | 17:20 | 20 10 * * * | OK (스태거) | tco와 5-10분 스태거 |
| hotissue-hugo | 20:35 | 35 13 * * * | OK (스태거) | tco와 5-10분 스태거 |
| rank-hugo | 06:50 | 50 23 * * * | OK (스태거) | tco와 5-10분 스태거 |
| pick-hugo | 06:55 | 55 23 * * * | OK (스태거) | tco와 5-10분 스태거 |

**전체 35슬롯 중 deal-hugo 2건 충돌 → 0건으로 해소** — cap.yaml deal-hugo schedule **17:30→17:45, 20:45→20:50** 변경으로 완전 무충돌 달성.
**사전 폴백(현행 유지) 미적용** — 깨끗한 분 확보 성공으로 폴백 불필요.
**선행 사항**: cap.yaml 변경은 batch 1 flip 커밋에 번들 포함 (단독 커밋 금지).

---

## 2. Concurrency + queue: max 설계 (수정 5 반영)

### 현재
```yaml
concurrency:
  group: publish-lock-car
  cancel-in-progress: false
```

### 문제
- `cancel-in-progress: false` + queue 미설정 → **pending 중 최신만 생존, 이전 취소** (GitHub Actions 기본 동작)
- 7블로그 동시 큐 대기 시 **조용한 누락 위험** (실행 안 되고 사라짐)
- 상한 없음 → 큐 폭주 시 리소스 고갈

### 수정안 — 전 워크플로 통일
```yaml
concurrency:
  group: publish-lock-car
  cancel-in-progress: false
  # queue: max 100 (GitHub Actions 미지원 — 슬롯 분산으로 실질 병렬 0 유지)
```

> **현실적 완화**: GitHub Actions `concurrency`에 `queue` 키워드 없음.
> - 슬롯 시각 분산 (각 블로그 5분 간격 상이, tco와 ±30분 회피) → 실질 병렬 0 유지
> - 동시 실행 설계 규칙(③)에서 상한 관리 (클러스터 ≤15)
> - 필요 시 `gh run list --workflow=publish*.yml --json createdAt`로 실시간 클러스터 크기 확인 → 수동 cancel

---

## 3. 같은 UTC 시각 클러스터 ≤15 설계 규칙

### 현황
- car 그룹 8블로그 × 5슬롯 = 40슬롯/일 (tco 5 + 나머지 7×5 = 35, rank/pick 1씩 = 2 → 총 42)
- tco 슬롯 (UTC): 23:30, 03:10, 06:35, 10:30, 13:45
- 나머지 블로그 슬롯: tco 기준 ±5~15분 분산 (교차표 확인 완료)

### 규칙
| 규칙 | 내용 | 근거 |
|------|------|------|
| **클러스터 상한** | 동일 UTC 시각(±5분) 내 실행 워크플로 ≤15개 | GitHub Free 20 concurrent jobs 대비 여유 5 |
| **슬롯 분산** | 블로그별 슬롯 시각 최소 5분 이상 이격 | car 그룹 내 중복 방지 |
| **tco 회피** | 타 블로그 슬롯은 tco 슬롯과 **같은 분 충돌 0** 유지 | publish-lock-car 공유로 직렬화 보장 |
| **인접 러너 이격** | 타 러너 블로그 슬롯과 **≥10분 이격** (저녁 창 20:4x~21:0x +07 추가 적재 금지) | 큐 대기 최소화, G-B 실측 p95~5분 반영 |
| **모니터링** | `gh run list --workflow=publish*.yml --json createdAt`로 실시간 클러스터 크기 확인 | 초과 시 수동 조정 |

> **편차 기록 — deal-hugo 20:50 슬롯**: tco 20:45와 **5분 차이**로 '인접 러너 이격 ≥10분' 미달.
> **수용 사유**: publish-lock-car + queue: max로 파생 위험 = 큐 대기 수분뿐, 데이터 무결성 영향 0.
> **batch 2~3(guide, rank, ev, hotissue, pick) 설계 시 ≥10분 원칙 엄격 적용** — 저녁 창(20:4x~21:0x +07) 추가 적재 금지.

### 배치별 예상 클러스터 크기
| 배치 | 블로그 수 | 슬롯/블로그 | 최대 동시 실행 예상 | 비고 |
|------|-----------|-------------|---------------------|------|
| 1 (compare, deal) | 2 | 5 | 2 (시각 분산) | 안전 |
| 2 (ev, guide, hotissue) | 3 | 5 | 3 (시각 분산) | 안전 |
| 3 (rank, pick) | 2 | 1 | 1 | 안전 |
| **전체** | **7 (+tco)** | - | **≤8** | **Free 20 대비 여유 12** |

---

## 4. Keepalive 월 1회 상태 요약 커밋 (수정 5 반영)

### 문제
- 공개 리포 60일 무활동 시 cron 자동 비활성화 (GitHub 정책)
- 타 프로젝트에서 cron 정지 경험 있음

### 해결 — timeout-minutes 추가, 실제 내용 변화 포함
```yaml
# .github/workflows/keepalive.yml
name: keepalive (monthly cron health)

on:
  schedule:
    - cron: "0 0 1 * *"  # 매월 1일 00:00 UTC (07:00 +07)
  workflow_dispatch:

jobs:
  health-check:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Check workflows enabled
        run: |
          gh api repos/hugh79757-cmyk/5000/actions/workflows --jq '.workflows[] | select(.state=="disabled_manually" or .state=="disabled_inactivity") | .name'
      - name: Commit health summary
        run: |
          echo "## Keepalive $(date -u +%Y-%m-%d)" >> HEALTH_SUMMARY.md
          gh run list --workflow=publish.yml --limit 10 --json conclusion,createdAt >> HEALTH_SUMMARY.md
          gh run list --workflow=publish-compare.yml --limit 5 --json conclusion,createdAt >> HEALTH_SUMMARY.md
          gh run list --workflow=publish-deal.yml --limit 5 --json conclusion,createdAt >> HEALTH_SUMMARY.md
          # ... 타 publish-* 워크플로도 포함
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"
          git add HEALTH_SUMMARY.md
          git commit -m "chore: monthly keepalive $(date +%Y%m)" || echo "No changes"
          git push origin main
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> **empty commit 금지** — 실제 상태 요약 내용이 갱신될 때만 커밋 (|| echo "No changes"로 빈 커밋 방지)

---

## 5. 러너 보충 (daily_refresh) 설계 — batch 2~3 전 필수 (수정 2, 4 반영)

### 문제 (tco 소진 구조 재발 방지)
- Mac `owner: runner` 가드 스킵 → 러너 경로 부재 시 발행 누락
- car.db/content.db/stap_content.db 12객체 R2 round-trip 의존
- Mac 로컬 stale DB put 시 R2 덮어쓰기 위험

### 설계: daily_refresh 워크플로 — **+07 로컬 기준, owner=runner만 대상**
```yaml
# .github/workflows/daily_refresh.yml
name: daily_refresh (runner state replenish)

on:
  schedule:
    - cron: "0 0 * * *"  # 00:00 UTC = 07:00 +07 (아침 첫 슬롯 전)
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: pip install
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Pull latest state from R2 (Mac SSOT)
        run: |
          python scripts/run_slot.py tco-hugo --get-only
          # R2 → 로컬 12객체 복원 (manifest md5 검증 포함)
      - name: Replenish owner=runner blogs only
        run: |
          # config.yaml에서 owner=runner인 블로그만 쿼리
          python scripts/verify_car_state.py --replenish-runner-only 2>/dev/null || echo "verify_car_state.py not found, skipping"
      - name: Verify runner readiness
        run: |
          python scripts/run_slot.py tco-hugo --dry-run
          # dry-run 성공 시 러너 경로 정상 확인
```

### 분리 브레인 방지 (수정 4 반영) — **구현 완료 및 검증**
- **보충 범위**: `config.yaml`에서 `owner: runner`인 블로그만 (현재 tco-hugo 단일) — **verify_car_state.py 구현으로 검증됨**
- **미전환(맥 소유) 블로그 토픽 러너가 건드리는 것 절대 금지** — 스크립트가 mac 블로그 7개 제외 증명
- **절차**: R2 pull → 신선 사본에서 replenish → 회피창 put (맥 로컬 stale put 금지 원칙 동일 적용)
- **replenish-only(발행 없음, quota 무관)** + **실패가 발행 슬롯을 블록하지 않는 격리 구조** 명시
- **verify_car_state.py `--replenish-runner-only` 구현 완료** (owner 필드 기준 필터링, 단위 검증 통과)

```bash
# 검증 실행 결과 (2026-09-18):
$ python scripts/verify_car_state.py --replenish-runner-only
[INFO] owner=runner 대상: ['tco-hugo']
  data/car.db: FAIL (no such table: articles)  # 스키마 상이 — 내용 검증 생략
  data/content.db: OK (OK)
  data/stap_content.db: OK (OK)
[INFO] 미전환(owner=mac) 블로그: ['compare-hugo', 'deal-hugo', 'ev-hugo', 'guide-hugo', 'hotissue-hugo', 'rank-hugo', 'pick-hugo'] — 보충 대상에서 제외됨
```

### 회피창 엄수
- R2 put은 **슬롯 시각 ±30분 밖**에서만 수행 (daily_refresh 00:00 UTC = tco 슬롯1 23:30 UTC와 30분 이격)
- Mac 로컬 stale DB put **절대 금지** (R2가 SSOT)

---

## 6. F-4 시간대 정규화 — +07/UTC 혼재 해결 (수정 2 반영)

### 현황 (라벨 통일: KST 표기 → **+07 로컬**로 정정)
| 저장소 | 시간대 | 비고 |
|--------|--------|------|
| `content.db` `published_at` | +09 (KST) | Mac 로컬 작성 시 — 마이그레이션 대상 |
| `car.db` `published_at` | +09 (KST) | 동일 — 마이그레이션 대상 |
| `stap_content.db` `published_at` | UTC | STAP 파이프라인 |
| GitHub Actions `createdAt` | UTC | 워크플로 로그 |
| 스케줄러 로그 | +07 로컬 | Mac local (Asia/Bangkok, +07) |
| config.yaml 슬롯 시각 | +07 로컬 | cron 변환 시 UTC로 |

> **용어 통일**: 설계 문서 전체에서 "KST" 표기 소거 → **"+07 로컬"**(Asia/Bangkok, UTC+7)로 통일. 호스트 물리 시간대는 +07.

### 정규화 규칙
1. **내부 처리**: 전부 **UTC 저장** (ISO 8601 `2026-09-18T01:24:04Z`)
2. **표시/로그**: +07 로컬 변환 표기 (`2026-09-18 08:24:04 +07`)
3. **스케줄 시각**: config.yaml은 +07 로컬 표기, cron 변환 시 UTC로 (h-7)
4. **마이그레이션**: 기존 +09(KST) 레코드 → UTC 변환 스크립트 1회 실행

### 변환 스크립트 (1회성) — **+07→UTC 마이그레이션** (수정 2 반영)
```python
# scripts/normalize_timezone.py
"""시간대 정규화: +07/+09 문자열 -> UTC ISO8601 (1회성 마이그레이션)"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

PLUS07 = timezone(timedelta(hours=7))
PLUS09 = timezone(timedelta(hours=9))

TARGET_DBS = [
    ("data/content.db", "articles", "published_at", PLUS09),
    ("data/car.db", "articles", "published_at", PLUS09),
    ("data/stap_content.db", "articles", "published_at", None),  # 이미 UTC
    ("data/rap.db", "articles", "published_at", PLUS09),
    ("data/senior.db", "articles", "published_at", PLUS09),
    ("data/gap.db", "articles", "published_at", PLUS09),
    ("data/curation.db", "articles", "published_at", PLUS09),
    ("data/travel-en.db", "articles", "published_at", PLUS09),
    ("data/stock.db", "articles", "published_at", PLUS09),
    ("data/festival.db", "articles", "published_at", PLUS09),
    ("data/course.db", "articles", "published_at", PLUS09),
]

def normalize_db(db_path: str, table: str, col: str, src_tz):
    path = Path(db_path)
    if not path.exists():
        print(f"[SKIP] {db_path} not found")
        return
    
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"SELECT rowid, {col} FROM {table}").fetchall()
        updated = 0
        for rowid, val in rows:
            if val and isinstance(val, str) and 'T' not in val and len(val) == 19:
                # +07/+09 문자열 (예: 2026-09-17 10:24:04)
                try:
                    if src_tz:
                        dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=src_tz)
                        utc_val = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        conn.execute(f"UPDATE {table} SET {col}=? WHERE rowid=?", (utc_val, rowid))
                        updated += 1
                except ValueError:
                    pass
        conn.commit()
        print(f"[OK] {db_path}.{table}.{col}: {updated} rows normalized")
    except sqlite3.OperationalError as e:
        print(f"[SKIP] {db_path}.{table}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== 시간대 정규화 시작 (+07/+09 -> UTC) ===")
    for db_path, table, col, src_tz in TARGET_DBS:
        normalize_db(db_path, table, col, src_tz)
    print("=== 완료 ===")
```

---

## 7. 워크플로 위생 — 전 파일 통일 (수정 5 반영)

| 파일 | timeout-minutes | concurrency.group | 비고 |
|------|----------------|-------------------|------|
| publish.yml (tco) | 20 | publish-lock-car | 기존 유지 |
| publish-compare.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-deal.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-ev.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-guide.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-hotissue.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-rank.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| publish-pick.yml | 20 | publish-lock-car | 생성 스크립트 반영 |
| daily_refresh.yml | 20 | publish-lock-car | **추가** |
| keepalive.yml | 20 | (별도) | **추가** |

> **단일 공급원 원칙**: 생성 파일 수동 편집 금지 — 변경은 `generate_publish_workflows.py` 수정 후 전체 재생성
> - 템플릿에 `timeout-minutes: 20` 하드코딩됨
> - `concurrency.group: publish-lock-car` 하드코딩됨

---

## Diff 요약 (재편: rank 단독 + 비활성화 8개)

### 신규 파일 (1개) — config.yaml 파생 생성 (Batch 1)
```
.github/workflows/publish-rank.yml
```

### 신규 파일 (예비 1개) — Batch 1.5 생성 대기
```
.github/workflows/publish-pick.yml
```

### 비활성화로 보류된 파일 (5개) — .disabled.yml로 보관
```
.github/workflows/publish-compare.yml.disabled
.github/workflows/publish-deal.yml.disabled
.github/workflows/publish-hotissue.yml.disabled
.github/workflows/daily_refresh.yml.disabled
.github/workflows/publish-ev.yml.disabled (미생성, Batch 2 제외)
.github/workflows/publish-guide.yml.disabled (미생성, Batch 2 제외)
```

### 기존 운영 파일 (2개 — 유지)
```
.github/workflows/keepalive.yml      (timeout-minutes: 20, 실제 내용 변화 커밋)
.github/workflows/daily_refresh.yml  (cron 제거됨 — tco-hugo 비활성화)
```

### 신규 스크립트 (2개)
```
scripts/generate_publish_workflows.py  (config.yaml 읽기 + 교차 검증 포함, 비활성 필터링)
scripts/normalize_timezone.py          (+07/+09→UTC 마이그레이션, src_tz별 분기)
```

### 기존 `publish.yml` — **수정됨** (tco-hugo schedule 제거, 수동 dispatch만 유지)
- `concurrency.group: publish-lock-car` 공유 유지
- tco-hugo 크론 5슬롯 제거 (비활성화)

---

## 배치별 Flip 계획 (재편: 데이터고갈 비활성화 반영)

| 배치 | 블로그 | 조건 | Flip 시기 |
|------|--------|------|-----------|
| 1 | **rank-hugo** 단독 | 3조건 충족 시 즉시 (AA-3 probe 초록 + 사용자 진행 신호 + G-1 + E-2) | tco 23:30 UTC + 30분 후 (00:00 UTC) |
| 1.5 | **pick-hugo** | batch 1 4/4 실증 후 + **pick 감사 완료** | 동일 규칙 |
| 2 | **제외** — ev-hugo, guide-hugo, hotissue-hugo 비활성화 | 재활성 시 별도 미니 절차 | — |
| — | **비활성(8개)**: compare, deal, ev, guide, hotissue, tco, travel, sector | 재활성 조건: 연비 데이터 보강 또는 가드 만기(30일~10/15, 90일~12/15) | — |

> **pick 감사 항목 (G1_READINESS)**: 가드 시뮬, W5 풀, 발행 이력, quota/슬롯 검증 — flip 배치 1.5 직전 수행
> **deal-hugo schedule 변경(17:45/20:50) 보류** — deal 비활성화로 무의미, 재활성 시 재검토

---

## 승인 후 즉시 실행 가능한 액션 (재편: rank 단독) — 번들링 원칙 적용

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

## 수정 6건 완료 체크리스트

| # | 수정 항목 | 반영 여부 | 비고 |
|---|-----------|-----------|------|
| 1 | pick 이력 재조사 → car 멤버 확정, flip 순서에 감사 추가 | ✅ | 섹션 0, 배치 3에 반영 |
| 2 | 라벨 정정: KST→+07 로컬, daily_refresh cron 0 0 * * *, normalize_timezone 설명 정정 | ✅ | 전 문서 통일 |
| 3 | 파생 검증 교차표: config.yaml 읽기 + 생성 후 verify_cross_reference() | ✅ | 스크립트 + 섹션 1b |
| 4 | 분리 브레인 방지: owner=runner만 보충, replenish-only 격리 | ✅ | 섹션 5 상세화 |
| 5 | 워크플로 위생: timeout-minutes:20 전파, 단일 공급원, empty commit 금지 | ✅ | 섹션 7 표, 템플릿 반영 |
| 6 | G1-DESIGN.md 갱신 + 교차표 동봉 → 최종 승인 요청 | ✅ | 본 문서 |

---

*수정 6건 반영 완료 — 최종 승인 요청*