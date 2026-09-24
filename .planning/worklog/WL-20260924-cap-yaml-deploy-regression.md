# WL-20260924 — CAP cap.yaml DEPLOY-REGRESSION (rank/compare/ev/hotissue 4연쇄 실패)

## 날짜
2026-09-24 09:38 +07 (02:38 UTC)

## 분류
DEPLOY-REGRESSION (신규) — 자책 배포 회귀. KILL-SWITCH 1/4 대상 아님 (concurrency 메커니즘 실패 아님).

## 배경
- 09-24 01:27–01:40Z 스케줄 4건 실패: rank-hugo 35943989831, compare-hugo 35943913766/35942960885, ev-hugo 35943860639, hotissue-hugo 35942989530
- 실패 모드: dispatcher가 config 파싱 단계에서 사망 → 생성·R2 I/O·ledger 진입 전. 이중발행·상태오염 위험 없음.
- 반대급부: Mac SKIP (runner 소유) + 러너 사망 = 전 CAP 무발행(dark). 방치 시 tco 슬롯(13:45/17:30/20:45 +07)도 전부 사망.

## 근본원인
- `15f299899 M-5 flip`이 `config/blogs.d/cap.yaml` 들여쓰기 파괴 → `yaml.parser.ParserError` (line 35 col 3 / found '-' line 58 col 3)
- `load_blogs()` → `get_blog_config()` 경로에서 전부 사망. cap.yaml 소속 전 블로그 동일 원인.
- M-5 3-way 체크는 스코프만 검증, 내용 유효성(yaml parse) 미검증 — 잠복 결함.

## Pre-Count (9커밋, 원본)
`git log origin/main..main --format="%h %ad %s" --date=iso-local --stat` (09-24 09:3x +07 실행):

| # | 커밋 | 분류 |
|---|------|------|
| 1 | 68b8f2dda triage docs (29 md + INDEX) | ② docs 무해 |
| 2 | 78a92f73b R12 scripts 4신규 | ① fix/필수 (additive) |
| 3 | 5a0dcaf9b destructive log 1줄 | ② log 무해 |
| 4 | 1874699b5 checker timeout+retry | ① fix/필수 |
| 5 | 5e3afcf73 P코드 checks 추가 | ① fix/필수 |
| 6 | 6e3b173c6 seed preserve + auto-transition (db.py 포함) | ① fix — [부분검증] db.py 동작변경, 단독 테스트 미실행 |
| 7 | 1a38e4f48 rollup 호출 + API | ① fix/필수 |
| 8 | 068ea3767 P36 playbook + check | ① fix/필수 |
| 9 | fe566c651 cap.yaml indent fix 11+/11- | ① P0 fix |

- ③ wip/hugo_writer: 9커밋 내 없음. `M shared/publishers/hugo_writer.py`는 uncommitted working tree — push 미포함 확인.
- ④ 시크릿 스캔: 파일명 grep (env/secret/token/credential/key) 0건.

## Fix 검증 (푸시 전)
- `git diff 15f299899 fe566c651 -- cap.yaml`: indent-only (depth_next/bridge_to +2, 블로그 항목 `-  -` → `- ` 4곳)
- owner 변경 0건 (값 변경 없음, 공백만): `grep -E "^[+-].*owner:"` → mac 2줄 공백 이동만
- runner 8/8 전후 동일, status 1 active/7 paused 전후 동일 → M-5 flip 보존, 되돌림 아님
- `FIX_PARSE_OK` (fe566c651 버전), 로컬 `LOCAL_PARSE_OK`

## Execution
- `git push origin main` → `15f299899..68b8f2dda main -> main`, fast-forward, force 미사용
- 롤백 수단: prev-SHA 15f299899 (revert 또는 prev SHA push)
- Uncommitted 변경(.continue-here.md, hugo_writer.py 등)은 push 영향 없음

## Post-Verification
- `ORIGIN_PARSE_OK` (fetch 후 origin/main cap.yaml safe_load)
- dry-run dispatch `gh workflow run publish.yml -f blog=ev-hugo -f dry_run=true` → run 35947831147 success, failed log 空
- publish_ledger 09-24 4블로그 row 0, articles 09-24 0건 → 부분 기록 없음 실증

## 부분검증 마무리
- daily_refresh 실패 35945620968: 예측(yaml 동일 원인) 불일치 → 별도 결함: `daily_refresh.yml:27`이 `run_slot.py --get-only` 호출하나 해당 인자 없음 (`--dry-run/--skip-opsdb`만 존재). origin/main 현행 동일. 미수정 (별도 결정 필요).
- Runner R2 state put-back on failure 여부: 미확인 (제한).

## 회계
- Phase 1: day 3 슬롯 회귀 소모 → 오늘 23:50 UTC rank 슬롯이 대체 day 3/3. 성공 시 09-25 아침 Phase 2 승인 요청.
- 신규 불변 게이트 CONFIG-PARSE: `64-PREFLIGHT-CHECKLISTS.md` 2.2 배포 항목 □7 등재.
- 불변 유지: force push 금지, wip/hugo_writer push 금지, dry_run=false 수동 dispatch 금지.

## 잔존 위험
- daily_refresh `--get-only` 결함 still open → 다음 daily_refresh 스케줄도 실패 예정. 수정 시 별도 fix + push 결정 필요.
- 6e3b173c6 db.py auto-transition 동작변경: 이번 push 포함, 단독 검증 없음.
- 다음 예약 슬롯(23:50 UTC rank) 자동 회복 예상이나 실측 전까지 미확정.
