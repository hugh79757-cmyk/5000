# B1 정의 — 재정의 (2026-09-19)

> **B1 = 공개 전환(완료) + 미사용 2종 철회(사용자) + DATA_GO_KR 로테이션(완료) + SA 판정 + OPS_PASSWORD(에이전트) + CAP_PAT probe(게이트)**

---

## 상세 구성

| 구성 요소 | 상태 | 비고 |
|-----------|------|------|
| **공개 전환** | ✅ 완료 | 5000 리포 public 전환 완료 |
| **미사용 2종 철회** | ⏳ 사용자 진행 중 | 1) `.sa_creds_tmp` (SearchAdvisor 평문) 2) `ga4_admin_*.json` (GA4 서비스 어카운트) — 사용자 직접 철회/로테이션 |
| **DATA_GO_KR 로테이션** | ✅ 완료 | 신규 키 `1a7bd07dda3f66dcfdc0101f19cebda907cf5a3aecae7f6dc43cd89d4c3912d9` 적용, RAP/Travel/Senior 정상화 확인 |
| **SA 판정** | ⏳ 대기 | SearchAdvisor 크리듀얼(`.sa_creds_tmp`, `ga4_admin_*.json`) 사용처 없음 확인 완료 — 사용자 로테이션/철회 대기 |
| **OPS_PASSWORD (에이전트)** | ⏳ 절차 제안 대기 | 신규 값 생성 → env+대시보드 적용 → AGENTS.md 평문 제거 diff 제안 대기 |
| **CAP_PAT probe (게이트)** | ⏳ 대기 | `probe.yml` workflow_dispatch 1회 (CAP_PAT: rank-hugo+tco-hugo ls-remote, CF: wrangler whoami, GHP_5000: ls-remote — exit code만, 값 echo 금지, 실패 재시도 1회 한도) |

---

## B1 완료 조건 (Flip 트리거)

```
B1 완료 = AA-3 probe 초록 + 사용자 진행 신호
        = probe.yml 1회 실행 성공 (exit code 0)
        + 사용자 "진행" 신호 수신
```

> **기존 "② B1 완료" 표기 전체 → "AA-3 probe 초록 + 사용자 진행 신호"로 정정 완료**

---

## B1과 연관된 작업

| 작업 | 상태 | 비고 |
|------|------|------|
| **V-1** 키 노출 스크럽 | ✅ 완료 | 노출 없음, ~/.env.common만 정상 |
| **V-6** probe.yml + OPS_PASSWORD | ⏳ 대기 | probe.yml 커밋 허용, OPS_PASSWORD 절차 제안 대기 |
| **AA-3 probe** | ⏳ 대기 | CAP_PAT probe.yml workflow_dispatch 1회 |
| **AA-4 OPS_PASSWORD** | ⏳ 대기 | 절차 제안서 제출 대기 |

---

*B1 정의 재정의 완료 — Flip/게이트 문서에서 참조*
