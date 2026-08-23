# WL-20260815-sc4-live-canary

> 날짜: 2026-08-15 / 연관: phase-71b wiring (5d19759df + tag phase-71b-wiring)
> 상태: 완료

## 목적
SC-4 발행 후 훅 자동수정(파괴등급 승인 폐루프)의 실데이터 검증. ev-hugo(R08, 파괴등급)를 canary로 실제 라이브 1회 fix + Pages 배포로 폐루프 확인.

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 02:46 | 파괴등급 R08 위반 주입(테스트) | single.html에 `<p class="lead">{{ .Lead }}</p>` 1라인 | 0 fail → R08 fail 1건 | single.html.bak_sc4_20260815 | R08 fail 감지, pending#2 proposed, 단일.html .Lead 잔존(자동실행 차단) | canary 대상만 |
| 08:12 | 승인(nonce) → fix → Pages 재배포 | dispatcher.execute_pending_fix(conn, 2, redeploy=True) | R08 fail 1건 → pass | ops.db.bak_sc4_20260815 / content.db.bak_sc4_20260815 / git tag pre-sc4-live-20260815 | single.html==HEAD, R08 pass, 배포 b8bc412f, HTTP 200 | cap-hugo pending#1 resolved 유지 |

## 4단계 프로토콜 이행
1. 사전 카운트: baseline ev-hugo 15체크 13pass 0fail 2unknown, standard_compliance pass. pending_fixes baseline=1(id=1 cap-hugo R08 resolved, 사전 존재).
2. 되돌림 수단: 파일 `single.html.bak_sc4_20260815` + DB 백업 2건 + git tag `pre-sc4-live-20260815`(5000·ev-hugo). 복원: ops.db.bak 복원 + `git checkout pre-sc4-live-20260815 -- layouts/_default/single.html`.
3. 실행: 주입 → 재검사(자동실행 아님, proposed 적재 확인) → 승인 게이트(사용자 명시 승인 수락) → execute_pending_fix(redeploy=True) → Pages 배포.
4. 사후 대조: R08/standard_compliance fail→pass, single.html==HEAD(원복), 배포 b8bc412f(1분 전) + ev.rotcha.kr HTTP 200, pending#2 resolved.

## 결과 / 보존 대상 확인
- ev-hugo R08 pending#2: proposed → (승인) → resolved. diff_ref="fix_r08: single.html: .Lead/.Description 1라인 제거".
- single.html 복원: git HEAD blob ca22a0fcf87ae4ec011940681c31d28c974027e7 일치.
- 배포: Pages Production `b8bc412f-0297-430e-8a5f-c6ea66acb61a` (https://b8bc412f.ev-hugo.pages.dev), ev.rotcha.kr + 대표 게시글 HTTP 200.
- 실데이터: execute_pending_fix 재배포가 실제 Pages 배포 생성 + 사후 재검사 반영 확인.

## 이상치 / 부수 발견
- pending_fixes id=1 (cap-hugo R08 resolved, diff_ref="dummy r08") 사전 존재 — canary와 무관, 건드리지 않음.
- canary 진행 중 pending_fixes id 3~19 (ETAP 17개 블로그 R2-01 proposed) 추가됨. 백업(승인 전, id=1만)으로 canary가 유발한 게 아님을 확증 → **병렬 스케줄러(라이브 데몬)의 주기적 fleet check 산물**. 모두 `proposed`(자동실행 안 됨, 안전). 별도 fleet 판단 사안으로 백로그.

## 부속 작업 — ETAP R2-01 17건 자동 처리 시도 (중단·보고)
- **발견**: `fix_r2_images`(shared/autofix/r2.py)는 URL을 보정하지 않는 **순수 탐지기**임. 원본 R2 URL을 매핑하지 못하고 `return False, "...원본 R2 URL 미확인 (잔여 큐)"`만 반환. 쓰기 로직 없음.
- 확증: luxury-hugo 21건 / ghost-hugo 21건 / esim-hugo 28건 비R2 이미지 → 전부 ok=False.
- 따라서 execute_pending_fix 자동배치는 17/17을 failed로 만들 뿐 실제 복원 불가 = gate(b) 대량실패. **무인 배치 미실행**, 17건 전부 proposed 유지.
- 2-1(R2 원본 존재 확인)도 성립 불가 — fixer가 실패 URL→정확한 R2 키 매핑 수단이 없음.
- 권고: fix_r2_images에 URL 매핑 구현(어떤 소스로 원본 R2 키를 알지 결정 필요) 또는 proposed 유지 + 사람 판단.
- dummy 행 삭제: pending_fixes id=1(cap-hugo R08 dummy) 삭제(19→18행).

## 잔존 위험
- ETAP R2-01 proposed 17건: 승인/거부 결정 대기 중. fix_r2_images는 파괴등급 — 일괄 승인 전 원본 이미지 R2 존재 여부 확인 필요(C.2 R2-01 레시피). **현재 fixer로는 자동 복원 불가(탐지기 수준).**
- ev-hugo에 P01/P02/P25 publish_error open 이벤트(consecutive_failures 등) 사전 존재 — 이번 승인·배포와 무관, 별도 처리 필요.
- 테스트 환경에서 사용한 `single.html` 주입 라인은 제거·원복 완료(git HEAD 일치). 잔재 없음.