# Worklog: WL-20260920-pick-infra-pause

**Date**: 2026-09-20
**Scope**: pick-hugo 일시 정지 (ops 레인 단독 cap.yaml 수정) + 사유 정정 + 사후 승인 요청
**Constraint**: cap.yaml·blogs.d 단일 작성자 규칙 (신규) — ops 레인 변경은 제안→이관 창 경유

---

## 사후 승인 요청 (REQUEST FOR RETROACTIVE APPROVAL)

### 사유
- 정지 시점: 2026-09-20 (오늘), ops 레인 세션 중
- G1 batch 1 flip (4697b429b, 2026-09-20 12:48) 이후 cap.yaml 직접 수정 — **이관 창 밖**
- cap.yaml 단일 작성자 규칙 사후 적용 대상

### cap.yaml 변경 내용 (working tree, uncommitted)
1. `pick-hugo` main: `status: active → paused`
2. `hotissue-hugo.depth_next[]` 내 `compare-hugo/pick-hugo/rank-hugo` `owner: mac → runner`

### Pick 정지 사유 (정정)
- **기록됨 (오류)**: 데이터고갈 → INTENTIONAL-PAUSE(데이터고갈)
- **실제 (확인)**: checker DB open 결함
  - 증거: scheduler.log 9/11~9/20 매일 `AVAILABILITY: pick-hugo state=checker_error available=-1`
  - `CATCHUP candidates 없음` + `unable to open database file` 반복
  - 9월 10일 이후 발행 0건 (10 Sept publishes / 596 all-time 기준)
  - **재고 58 존재** — 정지 기준은 "재고 소진"이 아닌 "DB 접근 불가"
- **정정 사유**: INFRA-PAUSE-DB-REPAIR-PENDING

### 재활성 지도 (갱신)
1. pick checker DB open 결함 원인 규명 (file:line + DB 경로 + 권한/락)
2. 결함 수리
3. 리시딩 (수리된 DB 기반 read 검증)
4. 배치 1.5 flip 창 내 unpause + owner 전환 (mac→runner — G1-DESIGN §0 batch 1.5)
- 수리가 배치 1.5 일정을 넘기면 pick는 병행 레인 격리 — car 완결 선언은 rank 단독, pick 후속 기록

### cap.yaml 단일 작성자 규칙 (신규)
- cap.yaml·blogs.d/*.yaml 모든 수정은 이관 세션 창 내에서만 수행
- ops 레인의 config 변경은 제안 형태로 제출 → 이관 창 경유 집행
- 예외: 긴급 안전 차단 (KILL-SWITCH 등) — 즉시 후 사후 보고

---

## Pre-Count
- cap.yaml 수정 대상 블로그: 4개 (pick-hugo status, compare/pick/rank depth_next owner)
- 다른 파일 동시 수정 없음 (cap.yaml 단독)

## Backup
- cap.yaml HEAD: 4697b429b (G1 batch 1 flip)
- cap.yaml.bak_disable_20260919_143857 기존 백업 존재

## Execution
- cap.yaml 변경 적용 (uncommitted working tree)
- YAML 파싱 검증 완료 (python yaml.safe_load)

## Post-Verification
- status=paused → pick-hugo만 해당, rank-hugo active 유지 확인
- YAML 유효성 확인

## 완료 항목 (사후 승인 완료)
- [x] 사용자 사후 승인 수신 후 git commit: "ops(blogs): pick-hugo 일시 정지 — checker DB open 결함 (데이터 고갈 아님, 재고 58)" — **커밋 3f0fa87d5 완료**
- [x] ops_dashboard known_issues에 INFRA-PAUSE entry 등록 — **.planning/known_issues/INFRA-PAUSE-DB-REPAIR-PENDING.md 생성 완료**
- [ ] DB open 결함 원인 규명 (O-2 연계) — **진행 중**

---

## 신규 규칙 worklog 반영 (O-1-F-4)
**규칙**: cap.yaml·blogs.d 단일 작성자(이관 창 경유, 긴급 안전 차단만 예외·후 사후 보고)
- 적용 대상: cap.yaml, blogs.d/*.yaml 모든 설정 파일
- 예외: KILL-SWITCH 4신호 중 어느 하나라도 발동 시 즉시 차단 허용, 단 사후 1시간 내 보고 의무
- 위반 시: 사후 승인 프로세스 필수 (본 worklog가 선례)
- 기계적 절차 추가: flip edit 스텝 실행 후 잔해 잔존 여부 확인 스텝을 FLIP-BUNDLE-PREVIEW 배치 1.5 pre-flight에 명세화 완료 (§16)

---

## Owner 잔해 3건 처리 현황 (FLIP-BUNDLE-PREVIEW §16 / O-1-F-3)
stash@{0}에 보관 중 (HEAD b4fbe15cf 기준):

| 블로그 | 필드 | HEAD | Stash | 판정 | 조치 |
|--------|------|------|-------|------|------|
| compare-hugo (hotissue-hugo depth_next) | owner | mac | runner | 이관 완료(실제 runner 사용) — **무해** | 배치 1.5 창 내 origin 판정 재확정 기록만 |
| pick-hugo (hotissue-hugo depth_next) | owner | mac | runner | 배치 1.5 대상 — **원칙상 mac 유지** | 배치 1.5 창 내 명시적 edit (mac→runner) 필요 |
| rank-hugo (hotissue-hugo depth_next) | owner | mac | runner | main 이미 owner: runner (4697b429b) — **무해** | 확인 기록만 |

**3-way 대조 오염 방지**: FLIP-BUNDLE-PREVIEW §16에 기계적 절차 명세 완료. 이관 창 내 flip edit 전 `git diff`로 owner 변경 범위 확인, 의도하지 않은 변경은 stash 보관 후 창 내 판정.