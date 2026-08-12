# 에이전트 진입점 — 오류·운영 신호 처리 표준 절차

> 대상: Solar Pro 4급 이하 모델이 오류코드(P01~P31, M01~M11, R01~R12)를 받았을 때
> 목표: 자율 탐색 최소화, 4단계 고정 절차로 해결 플레이북에 도달
> 최종 갱신: 2026-08-12

## 개요

오류 신호가 오면 아래 4단계를 순서대로 따른다. 단계 건너뛰기·자율 탐색 금지.

1. PLAYBOOK_INDEX.yaml에서 해당 code 조회
2. playbook_file#anchor를 열어 지시 확인
3. target_files를 수정 (automation_level 허용 범위 내에서만)
4. verify로 검증

## 단계 1: PLAYBOOK_INDEX.yaml에서 code 조회

**파일**: `ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml`

오류코드(예: `P25`)를 받으면 이 파일에서 `codes` 리스트를 찾아 `code`가 일치하는 항목을 찾는다.

조회 결과에는 최소한 다음이 포함되어 있다:
- `playbook_ref`: 플레이북 위치와 앵커 (예: `ERROR_PLAYBOOKS.md#p25`)
- `automation_level`: `full_auto` / `human_approval` / `human_only`
- `target_files`: 수정해야 할 파일 경로와 힌트
- `verify`: 검증 방법
- `needs_human`: 사람 필요 여부

**중요**: 코드는 반드시 PLAYBOOK_INDEX.yaml에서 먼저 찾는다. 다른 파일 먼저 읽지 않는다.

## 단계 2: 플레이북 열기

단계 1에서 얻은 `playbook_ref`를 연다.

- `ERROR_PLAYBOOKS.md#p25` → `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md` 파일에서 `<a id="p25"></a>` 앵커 위치를 찾아 해당 코드 행부터 읽는다.
- 앵커는 코드 영문 소문자 (P25→p25, M03→m03, R07→r07)

플레이북에서 확인할 것:
- 증거 확인 방법 (먼저 확인할 증거/원인 판별)
- 안전한 수정 방향
- 수정 권한 경계 (무엇을 해도 되고 무엇을 하면 안 되는지)
- 검증 방법

## 단계 3: target_files 수정

** automation_level 확인 먼저 **

플레이북과 PLAYBOOK_INDEX.yaml의 `automation_level`에 따라:

| automation_level | 행동 |
|---|---|
| `full_auto` | target_files를 직접 수정한다. Hugo 빌드 로컬 검증 후 배포는 dispatcher.py로. |
| `human_approval` | target_files 수정안을 작성하되, 배포·발행·재발행·키 변경 등은 진행하지 않고 사람에게 보고. |
| `human_only` | 수정 시도하지 않는다. PLAYBOOK_INDEX.yaml + playbook 내용을 그대로 보고. |

**target_files가 비어 있거나 `needs_human: true`인 경우**:
- 환각으로 파일을 추측하지 않는다
- PLAYBOOK_INDEX.yaml에 `TODO` 표시된 항목을 사람에게 전달
- "어떤 파일을 수정해야 하는지 정보가 부족함"이라고 보고

**Hugo 파일 수정 시**:
- Hugo 빌드 로컬 검증 필수: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그`
- 빌드 에러 0건 확인 전에는 배포하지 않음

## 단계 4: verify로 검증

PLAYBOOK_INDEX.yaml의 `verify` 항목에 명시된 방법으로 검증:

1. 대시보드 재검사 트리거 (개별 블로그 수정 후):
   ```
   POST /api/run-checks?blog_id={blog_id}
   ```
   (인증: OPS_USER/OPS_PASSWORD 환경변수, 없으면 ops/112233)

2. /api/registry 상태 확인:
   ```
   GET /api/registry?blog_id={blog_id}
   ```
   해당 code의 status가 `fail` → `pass` 또는 `unknown`으로 바뀌었는지 확인

3. FAIL→PASS 확인 없이 완료 보고 금지

## automation_level 요약

- `full_auto` (코드 수정만): P07,P08,P09,P21,P23,P24,P29,R01~R12 (+ playbook 확인 후 추가)
- `human_approval` (코드 제안 가능, 원격 조치 승인): P01,P02,P03,P04,P05,P06,P10,P11,P12,P13,P14,P15,P16,P19,P20,P22,P25,P26,P27,P28,P30,P31,M01~M11
- `human_only` (사람 전담): data 정책·키/토큰·대량 삭제·기준 완화 등 playbook에 명시

## 금지 사항

- 오류 제거를 위해 duplicate guard·품질 게이트·검증 규칙을 끄지 않는다
- 원인 확인 없이 일괄 재발행·대량 데이터 삭제·기준 완화를 수행하지 않는다
- target_files가 불확실할 때 파일을 추측해 수정하지 않는다
- Hugo 빌드 검증 없이 배포하지 않는다
- 재검사 트리거 없이 "FAIL→PASS 예상"으로 완료 보고하지 않는다

## 빠른 참조

| 신호 유형 | 코드 범위 | 먼저 볼 파일 |
|---|---|---|
| 발행 오류 | P01~P31 | PLAYBOOK_INDEX.yaml → ERROR_PLAYBOOKS.md |
| 운영·정비 검사 | M01~M11 | PLAYBOOK_INDEX.yaml → ERROR_PLAYBOOKS.md §4 |
| 표준 준수 규칙 | R01~R12 | PLAYBOOK_INDEX.yaml → ERROR_PLAYBOOKS.md §4 |
