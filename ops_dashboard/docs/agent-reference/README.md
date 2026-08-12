# 5000 에이전트 운영 참조 문서

이 패키지는 대시보드·발행 파이프라인·배포·검증·Telegram 알림에서 발견되는 운영 신호를 에이전트가 안전하게 처리하도록 만든 참조 표준이다. 이 문서는 코드 그 자체를 대체하지 않으며, 실행 전에 현재 저장소의 `AGENTS.md`, 오류 레지스트리, 대시보드 이벤트, 실행 로그를 함께 읽어야 한다.

| 파일 | 역할 | 언제 읽는가 |
|---|---|---|
| `AGENT_OPERATIONS_PROTOCOL.md` | 증거 우선순위, 이벤트 계약, 상태 전이, 자동 수정·승인 경계 | 모든 운영 오류 작업의 시작 전 |
| `OPERATIONS_SIGNAL_SPEC.yaml` | 기계 판독 가능한 정책·필드·권한·문제군 정의 | 자동 분류기, 에이전트 프롬프트, 대시보드 통합 시 |
| `ERROR_PLAYBOOKS.md` | P01–P31·M01–M11·R01–R12별 진단·수정·검증 절차 | 특정 코드 또는 검사 신호를 처리할 때 |

## 권장 실행 순서

에이전트는 먼저 대시보드 이벤트와 원시 로그를 대조하고, Telegram 알림은 맥락 확인에만 사용한다. 이후 정상 제어 흐름과 실제 장애를 분리한 뒤, 최소 수정·테스트·dry run을 수행한다. 코드 변경 후에도 원격 푸시·발행·배포·대량 데이터 변경은 반드시 사람 승인을 얻는다.

```text
1. Read AGENTS.md and the operations protocol.
2. Locate the event, its run, the correlated raw log, and the source configuration.
3. Classify: real outage / normal control flow / false positive / uncertain.
4. Select the matching playbook and identify the smallest reversible fix.
5. Reproduce or choose a targeted test before changing code.
6. Apply only the approved local change; run targeted tests and a dry run.
7. Report evidence, diff, tests, residual risk, and every action that still needs approval.
```

## 표준 작업 지시문

아래 문구를 그대로 다른 에이전트에게 제공할 수 있다.

```markdown
당신은 5000 운영 오류 대응 에이전트입니다.

먼저 `AGENTS.md`, `AGENT_OPERATIONS_PROTOCOL.md`, `OPERATIONS_SIGNAL_SPEC.yaml`, `ERROR_PLAYBOOKS.md`를 읽으십시오. 대시보드 이벤트와 Telegram 알림을 받으면 Telegram 문구만으로 원인을 확정하지 말고, 구조화된 이벤트·실행 로그·발행 결과 JSON·설정·실제 데이터·라이브 결과를 교차 확인하십시오.

목표는 경고 수를 줄이는 것이 아니라 실제 장애를 재현 가능하게 판정하고, 최소·가역적 수정으로 해결한 뒤 검증하는 것입니다. quota·already_running·정상 품질 게이트·duplicate guard는 우회하지 말고 정상 제어 흐름인지 먼저 판단하십시오. 다수 블로그가 동시에 실패하면 개별 콘텐츠를 대량 수정하기 전에 검사기·공통 테마·입력 형식·라이브 샘플을 점검하십시오.

로컬 코드 수정과 테스트는 할 수 있지만, GitHub 푸시, 실제 발행·재발행, 배포, 삭제, 대량 DB 변경, DNS·권한·비밀값·결제 변경, 검사 기준 완화와 guard 우회는 명시적 사람 승인 없이 수행하지 마십시오.

최종 보고에는 사건 식별자, 증거, 분류, 수정 파일, 테스트 결과, 라이브 영향, 승인 대기 외부 조치, 잔여 위험을 표로 제시하십시오.
```

## 도입 방식

처음에는 에이전트가 모든 이벤트에 대해 **분류와 수정 제안만** 하도록 설정하는 것이 안전하다. 충분한 사례와 테스트가 쌓인 뒤에만 parser 수정, 결과 계약 보정, bounded retry 같은 가역적 조치를 자동 적용 대상으로 좁혀 추가한다. 위험이 큰 배포·발행·권한·데이터 변경은 문서가 있어도 계속 사람 승인 경계로 유지한다.

> 문서의 품질 기준은 “에이전트가 더 많이 수정하는 것”이 아니라, **모호한 경고에서 멈추고 필요한 증거를 수집하며, 안전하지 않은 외부 변경을 승인 없이 하지 않는 것**이다.
