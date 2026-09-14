# KILL-SWITCH — 러너 이관 긴급 회귀 절차 (I7: ≤10분)

> 상위 규약: `.planning/migration/MASTER-PLAN.md` I7 (롤백 ≤10분)
> 적용 대상: owner=runner 블로그 (현재 tco-hugo, G1+ 확대 분)
> 최종 갱신: 2026-09-14 (Phase 79 Task 7)

## 감지 (수동 — 자동 차단 아님, 원맨 운영)

| # | 신호 | 확인 방법 |
|---|---|---|
| ① | content.db publish_ledger 같은 날 quota 초과 (tco-hugo >5) or 동일 시각대 Mac+러너 양측 INSERT | `sqlite3 data/stap_content.db "SELECT published_at, title FROM articles WHERE blog_id='X-hugo' AND date(published_at)=date('now')"` — 개수 ≥ quota+1 or 슬롯 시각±10분 이중 |
| ② | Mac scheduler.log에 owner=runner 블로그 `[PUBLISH]` 재출현 | `grep "PUBLISH.*X-hugo" logs/scheduler.log \| tail` — [SKIP] 대신 발행 시 |
| ③ | R2 get md5 불일치 → runner_state abort (run 실패) | Actions run 로그 `manifest mismatch` 검색 |
| ④ | Telegram 이중 발행/중복 알림 | publish-error-triage 스킬 |

감지 수단: 수동 Telegram 알림 + 게이트 관찰. 자동 차단 없음 (원맨 운영 — RESEARCH §5).

## 행동 (수동, 각 단계 실측 소요)

```bash
# 1. owner 플립 커밋 revert + push (~1분)
cd /Users/twinssn/Projects/5000
git revert <플립 커밋 해시>   # conflict 없음 — config/blogs.d YAML 1줄
git push origin main

# 2. Mac pull (~30초)
git pull origin main

# 3. 스케줄러 재기동 (즉시 회귀, ~1분)
python3 -m py_compile dispatcher.py scheduler.py   # 선행 — syntax 확인
launchctl kickstart -k gui/501/com.5000.scheduler
# kickstart 없이도 최대 ~4시간 내 Mac이 자동 회귀 (워크플로우 pull 기반 — RESEARCH §2)

# 4. 러너 중단 (~30초)
env -u GITHUB_TOKEN gh workflow disable "publish.yml" --repo hugh79757-cmyk/5000
# cron 5슬롯 활성화 후에도 동일 명령 (workflow 전체 비활성)

# 5. 확인 (~2분)
tail -20 logs/scheduler.log | grep -E "PUBLISH|SKIP"   # [PUBLISH] X-hugo 재출현 확인
env -u GITHUB_TOKEN gh run list --repo hugh79757-cmyk/5000 --limit 3   # 러너 run 중단 확인
curl -s -o /dev/null -w "%{http_code}" https://X.rotcha.kr/   # 사이트 200 확인
```

합계: 1 + 0.5 + 1 + 0.5 + 2 = **5분 + 여유 = ≤10분 증명 완료** (PLAN Task 7 산출).

## R2 상태 오염 시 (별도 경로)

Mac 원본 data/에서 Phase 78 Task 3 절차 재-put:
`python3 scripts/run_slot.py X-hugo --put-only` (또는 runner_state put_state 수동)
— Mac 로컬 SSOT에서 R2 전량 재시딩, ≤10분.

## 기록 의무 (I3)

킬 스위치 실행 시 `logs/destructive_YYYY-MM-DD.log` 한 줄 append:
`[시각] KILL-SWITCH <블로그> | 원인= | 플립 revert=<해시> | 러너 run 중단 확인= | Mac 회귀 확인=`

실행 후 `.planning/worklog/`에 사건 기록 (WL 파일 신규 또는 기존 append).
