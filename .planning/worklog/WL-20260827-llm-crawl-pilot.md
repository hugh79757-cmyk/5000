# WL-20260827-llm-crawl-pilot

## 목적
fire-your-seo-agency 스킬 평가 결과: 인터랙티브 스킬은 5000 비적합, 참고 playbook만 흡수.
사용자(승인) 파일럿 선정: robots.txt AI-crawler Allow(우선) + llms.txt(보조), cannibalization 측정.
후보 10개 사이트(gsc_rows 기준): rotcha.kr, hotissue-hugo, guide-hugo, travel1-hugo,
travel3-hugo, deal-hugo, escape-hugo, travel2-hugo, techpawz.com, nomad-hugo.

## 실행 (2026-08-27)
1. baseline 스냅샷: data/analytics.db gsc_pages (range 2026-08-15..08-24) 저장
   → .planning/pilot_llm_crawl_baseline_2026-08-27.json
   rotcha.kr(clk16/imp1079/426), hotissue(clk18/imp762/356), guide(clk46/imp540/272),
   travel1(clk3/imp161/127), travel3(clk1/imp195/87), deal(clk5/imp109/68),
   escape(clk0/imp90/43), travel2(clk3/imp57/34), techpawz(clk1/imp25/23), nomad(clk0/imp21/20).
2. 9개 사이트 static/ 에 robots.txt(AI-allow 블록) + llms.txt 작성.
   기존 robots.txt 4건(travel1/3/2, techpawz) 백업(.bak_20260827_142410).
   - 신규(hotissue/guide/deal/escape/nomad): User-agent:* Allow:/ + AI-allow + Sitemap.
   - travel1/3/2: 기존 allow-all에 AI-allow 블록 병합.
   - techpawz: 기존 AI-disallow 전부 → allow 로 플립(핵심 변경).
3. 배포 dispatcher.py x9 (승인). 결과:
   - 배포 완료(robots/llms 라이브): hotissue-hugo, guide-hugo, deal-hugo, escape-hugo (4건)
   - 미배포:
     * techpawz-hugo: "not active" → 핵심 AI-crawler 플립 미반영
     * nomad-hugo: "not active"
     * travel1/3-hugo: travel4-hugo YAML 파싱 오류로 pre-deploy 실패(별개 인시던트)
     * travel2-hugo: daily cooldown SKIP(다음 스케줄 run 배포)
   - rotcha.kr: 로컬 Hugo repo 미발견 → 미처리(수동 필요)

## 잔존 위험
- techpawz.com(가장 중요한 disallow→allow 플립)이 inactive여서 라이브 미반영. 활성화 필요.
- travel1/3-hugo 배포는 travel4-hugo 프론트매터 YAML 버그 해결 선행 필요(별개 수정).
- 라이브 robots.txt/llms.txt fetch 불가(sandbox 네트워크 차단 HTTP 000) → 사용자 브라우저 확인.
- cannibalization(AdSense 트래픽 잠식) 측정은 4-6주 추적 필요(baseline 확보됨).
- rotcha.kr 처리 보류.

## 위반 감지
- 없음(승인된 범위 내 파일 편집+배포; destructive-ops 백업/로그 준수).
