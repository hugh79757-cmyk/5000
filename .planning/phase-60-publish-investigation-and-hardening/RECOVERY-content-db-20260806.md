# content.db 복구 절차서 — 2026-08-06 오염 사고

> 상태: **문서만 작성, 실행 금지.** 스케줄러 정지 시점에 별도 승인 후 진행.
> 작성일: 2026-08-06
> 오염 원인: `shared/ledger_sync.py` `run_sync()`을 라이브 상태에서 수동 실행.
> - `idx_ledger_dedup`이 실제 DB에서 non-unique(선존 버그, STRUCT-11) → `INSERT OR IGNORE` 무력 → 소스 전체 행 15,514건 재삽입
> - `backfill_blank_titles()`이 같은 블로그+날짜의 여러 blank 행에 첫 소스 제목을 덮어씀 (오염 의심 1,412곳)

## 전제

라이브 스케줄러(PID 31420)를 먼저 멈춘다. 정지 확인 전에는 어떤 DELETE/UPDATE/인덱스 재생성도 하지 마라.
`source=''`(실발행 36행)은 어떤 단계에서도 삭제 금지.

## 단계 0 — 스케줄러 정지 및 확인

스케줄러 프로세스(PID 31420 및 관련 launchd 잡)를 정지하고, content.db에 쓰는 프로세스가 0인지 확인하라(lsof 등).
정지 사실과 확인 근거를 출력하라.

## 단계 1 — 클린 백업(정지 후)

동시 쓰기가 없는 상태에서 현재 content.db를 `data/content.db.clean_before_recovery_<타임스탬프>`로 복사하라.
이건 "오염 상태이나 정지 후"의 기준선이다. 기존 bak 파일은 덮어쓰지 마라.

복구 전 총 행수, source별 행수(특히 source='' 36행, source=src 계열), 중복 추정치를 표로 출력하라.

**2026-08-06 작성 시점 기준치(복구 전 현재 상태):**
- 총 행: 57,770 / published: 51,053 / failed: 6,717
- 중복 초과행: 39,734 (선존 28,936 + run_sync 실행분 15,514, 일부 겹침)
- id>42260 `source=''` 실발행 보존 대상: 36행
- 증거본: `data/content.db.EVIDENCE_polluted_20260806` (해시 4bfddcda...)
- 백업본: `data/content.db.bak_20260806_202605` (오염 후 상태 — 원상복구 아님)
- **클린 스냅샷: 없음** (gitignored, Time Machine 스냅샷 없음, 백업은 모두 오염 후)

## 단계 2 — 코드 커밋(아직 미커밋이면)

정상 확인된 수정(dispatcher fallback, M09, days_since_last_publish, stale 쿼리)과 run_sync 비파괴 가드를 커밋하라. 테스트 회귀 0 확인.

## 단계 3 — dedup 인덱스 UNIQUE 마이그레이션

non-unique `idx_ledger_dedup`을 DROP 후 UNIQUE로 재생성하라. 단, UNIQUE 인덱스를 만들려면 기존 중복이 먼저 제거돼야 하므로 단계 4를 먼저 하거나, 중복 제거와 인덱스 생성을 한 트랜잭션에서 순서대로 처리하라. 어느 순서로 했는지 명시.

현재 인덱스 정의(evidence):
```
CREATE INDEX idx_ledger_dedup ON publish_ledger(blog_id, slug, DATE(created_at))  -- UNIQUE 없음
```
기대 인덱스(ledger_sync._ensure_schema):
```
CREATE UNIQUE INDEX idx_ledger_dedup ON publish_ledger(blog_id, slug, DATE(created_at))
```

## 단계 4 — 중복 정리(정밀)

정리 대상: source=src 계열 중복 행. 보존: source='' 36행은 무조건 보존.

방식: (blog_id, 날짜, title, source) 기준 동일 그룹에서 최소 id 1건만 남기고 나머지 삭제하는 식으로, "실발행 유실 0"을 보장하라. 방금 추가한 id>42260뿐 아니라 선존 중복 28,936건도 같은 규칙으로 정리.

삭제 전 "삭제 예정 건수"를 먼저 카운트해 출력하고, 삭제 후 실제 삭제 건수·잔여 행수를 대조하라. source='' 행수가 여전히 36인지 반드시 재확인.

## 단계 5 — 백필 오염 원복(1,412곳)

`backfill_blank_titles()`이 같은 블로그+날짜의 여러 행에 첫 소스 제목을 잘못 덮어쓴 1,412곳을, 원래 blank('')로 되돌릴 수 있는지 판단하라. 원본 제목을 복원할 근거가 없으면 억지 추정 대신 blank로 원복(원래 스키마 NOT NULL DEFAULT '')하고, 이유를 명시하라.

## 단계 6 — 검증

- run_sync를 다시 호출해도 행수가 늘지 않는지(idempotent) 확인하라.
- days_since_last_publish/stale/M09가 실값으로 정상 산출되는지 active 전수로 확인하고, 확장 준비도 stale 지표가 몇으로 바뀌는지 보고하라.
- 최종 커밋 후, 스케줄러는 정상화 완료 전까지 정지 상태로 둔다(finance.techpawz.com 외 발행 재개 금지).

## 보고 항목

단계별 before/after 행수, 삭제 건수, source='' 36행 보존 확인, 백필 원복 결과, idempotent 검증 결과, 준비도 stale 신규값, 커밋 해시.
