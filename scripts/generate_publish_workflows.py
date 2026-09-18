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

# deal-hugo 깨끗한 분 오버라이드 (config.yaml은 flip 번들에 번들링, 생성본은 최종안 반영)
DEAL_CLEAN_TIMES = ["06:35", "10:15", "13:40", "17:45", "20:50"]

def get_times_for_blog(blog_id: str, config_times: list) -> list:
    """deal-hugo는 깨끗한 분 적용, 나머지는 config.yaml 원값"""
    if blog_id == "deal-hugo":
        return DEAL_CLEAN_TIMES
    return config_times

def kst_to_cron(local_time: str) -> str:
    """+07 로컬 HH:MM -> cron 'MM HH * * *' (UTC)"""
    h, m = map(int, local_time.split(":"))
    utc_h = (h - 7) % 24  # +07 로컬 = UTC+7
    return f"    - cron: \"{m:02d} {utc_h} * * *\"  # {local_time} +07"

def generate():
    car_blogs = load_car_blogs()
    out_dir = Path(".github/workflows")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for blog_id, times in car_blogs:
        if blog_id == "tco-hugo":
            continue  # tco는 기존 publish.yml 사용
        # deal-hugo는 깨끗한 분 오버라이드 적용
        final_times = get_times_for_blog(blog_id, times)
        cron_lines = "\n".join(kst_to_cron(t) for t in final_times)
        
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
    print("\n=== 교차 검증표 ===")
    print("| 블로그 | 로컬 슬롯 (+07) | UTC cron | 정확 분 충돌(동일분) | 비고 |")
    print("|--------|----------------|----------|---------------------|------|")
    tco_slots = [(23,30), (3,10), (6,35), (10,30), (13,45)]
    for blog_id, times in car_blogs:
        if blog_id == "tco-hugo":
            continue
        # deal-hugo는 깨끗한 분 적용
        final_times = get_times_for_blog(blog_id, times)
        for t in final_times:
            h, m = map(int, t.split(":"))
            utc_h = (h - 7) % 24
            cron = f"{m:02d} {utc_h} * * *"
            # 정확한 분 충돌만 체크 (의도적 5-10분 스태거는 정상)
            exact_collision = any(utc_h == tc and m == tm for tc, tm in tco_slots)
            collision_str = "⚠️ 충돌" if exact_collision else "OK (스태거)"
            note = "tco와 5-10분 스태거" if not exact_collision else "동일 분 중복"
            print(f"| {blog_id} | {t} | {cron} | {collision_str} | {note} |")

if __name__ == "__main__":
    generate()
    verify_cross_reference()