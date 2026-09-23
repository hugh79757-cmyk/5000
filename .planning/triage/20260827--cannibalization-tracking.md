---
date: 2026-08-27
type: chore
status: ongoing
---

# Cannibalization 추적 인프라 구축 (AI-크롤러 잠식 측정)

## What
AI 크롤러 인덱싱/인용이 인간 방문을 대체해 AdSense 수익 하락할 리스크 측정. 4~6주 추적 시작.

## Why
fire-your-seo-agency 파일럿으로 AI-크롤러 Allow 오픈 → 노출↑ 기대이나, 요약 답변으로 방문↓(AdSense 잠식) 가능성. 정량 확인 필요.

## Files changed
- scripts/track_cannibalization.py (신규: 주간 롤업 → analytics.db:cannibalization_tracking)
- ~/Library/LaunchAgents/com.5000.cannibalization-tracker.plist (월 09:30 --week, launchctl load 완료)

## How
- 데이터: adsense_daily(도메인), gsc_pages(blog_id), ga4_daily(blog_id). 코호트 10개(blog_id↔domain 매핑, rotcha.kr은 blog_lifecycle 미등록이나 gsc_pages blog_id 존재).
- `--backfill 6 --week` → 70행(10×7주) 기록. 월요일 주차, INSERT OR REPLACE.

## Verification
- py_compile OK. 70행 기록 확인. launchctl list에 LOADED 확인.
- AI-Allow 라이브 5개(hotissue/guide/deal/escape/nomad)는 08-24주부터 after 누적. 미배포 5개(travel1/3/2/techpawz/rotcha)는 배포 후 시작.
- 이번 주(08-24~08-30)는 배포 후 3일 포함 → 진짜 before = 08-17주 이전(백필 확보).

## Next observation
**다음 관측일: 2026-09-24 (배포 2026-08-27 기준 4주 후) — 1차 판정**
**확정 관측일: 2026-10-08 (6주 후) — 최종 판정**
- 대조: cannibalization_tracking에서 배포 전(≤08-17) vs 후(≥08-31) 주차별 AdSense 수익/GA4 세션 추세.
- 미배포 5개 사이트는 배포되는 시점부터 after 구간 편입.
