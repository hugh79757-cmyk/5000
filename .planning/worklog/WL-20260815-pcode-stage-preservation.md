# WL-20260815 — P계열 stage 보존 + 자동 close + stderr 캡처 + dispatcher 푸시 정합

> 진행: phase-71e-pcode-1~3. 커밋 3건(비파괴·additive), 태그 3개.
> 근거: sector 누적 stap_subprocess_error 50회 근본원인(실제 예외)이 publish_error
> stage=spec.hook(result_parse) 뭉개짐 + run_subprocess stderr 폐기로 유실됨.

## 변경 요약

| 태그 | 파일 | 내용 |
|------|------|------|
| phase-71e-pcode-1 | ops_dashboard/db.py, shared/problem_monitor.py, 테스트 2 | stage를 실제 reason으로 보존, severity/action/playbook_ref를 PROBLEM_REGISTRY 유도(P25=CRITICAL), P02 선행근본원인 묶기 |
| phase-71e-pcode-2 | dispatcher.py, tests/test_dispatcher_pcode_close.py | 발행 성공 시 P01/P02/P20/P26-28/P30 자동 close, report detail 실reason/stderr 전달, _deploy_log_hint(SEAP 오귀속 해소) |
| phase-71e-pcode-3 | shared/subprocess_runner.py, test_subprocess_runner.py | non-zero exit stderr(1000자·마스킹)을 result['stderr']에 보존 |

## 파괴적 작업 이력

없음 — 모두 additive 구현 + 신규 테스트. 사전 커밋된 비관련 변경(.planning/, logs/)은 스테이징 제외.

## 사후 대조

- 신규 테스트 6건 + 기존 관련 테스트 33건 = 39 passed.
- stage: no_content→"no_content"(P02), stap_subprocess_error→reason 보존 + stderr 캡처 확인.
- 실측(라이브 ops.db): P25→CRITICAL #p25, cruise-hugo P02 root_cause="P04(post_deploy)@...".

## 잔존 위험

- 기존 open 행(stage=consecutive_failures/result_parse)은 히스토리로 남음 — 백필 안 함(의도).
- 실제 STAP 섹터 성공 발행까지는 파이프라인 가동 필요(진단 캡처만 가능해짐).