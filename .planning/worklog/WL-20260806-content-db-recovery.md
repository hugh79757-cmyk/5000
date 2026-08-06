# WL-20260806-content-db-recovery

> 날짜: 2026-08-06 / 연관: 커밋 219816b57(가드), d0da88bf2(규칙), 최종 마감 커밋
> 상태: **완료 (백필 원복만 보류)** — 커밋 C(표준위반) 마감 2026-08-06

## 세션 스냅샷 (2026-08-06, 커밋 C 마감)

진행: 대시보드 완성 → content.db 복구 완료 → 커밋 B(무력체크/ledger) 완료 →
커밋 C(표준위반) 완료.

커밋 C 마감 내역 (de386628c):
- 준수율 산정 버킷 분리: actionable(R01/R02/R05/R07~R12, 준수율 반영) /
  deferred(R06, STRUCT-16) / out_of_scope(R03 STRUCT-15, R04 STRUCT-17).
  준수율 = pass/(pass+actionable fail 블록), deferred·out_of_scope는 규칙
  건수로 별도 표기. RULES에 `bucket` 키 추가.
- 재정의 신규 준수율: **12.5%** (pass 1/25, actionable fail 7블록,
  deferred R06 19규칙/16블록, out_of_scope 11규칙/0블록, unknown 1).
  stale 3, 미해결 19 → 전체 🔴 확장 금지.
- R01: finance-hugo TOC 비활성 수정 (STAP/finance-hugo, 커밋 f4fe73d).
- R12: 허용 오버라이드 4→18 확장 (cde31b7bc) — travel4-hugo pass 진입.
- R02: 81→0 (N/A 판정 개선, 0c9657d14). R06: 조사만(보류, STRUCT-16).
- STRUCT-14(SEAP/ETAP git 미관리): **중복 아님 확인** — 파일·HEAD·DB 모두
  1건. 이전 read의 2건 표기는 출력 artifact. 시드 정리 불필요.
- 회귀: tests/ops_dashboard 14 passed.

다음 세션 진입점: entity_linker INC-CL-01~04 → 금지어 Q5 → H2 Q6 →
그 후 finance 외 재개 → 리팩토링.
**스케줄러 정지 상태 유지** (재기동은 별도 승인 필요).

## 배경

`shared/ledger_sync.py` `run_sync()`을 라이브 상태에서 수동 실행. 실제 DB의
`idx_ledger_dedup`이 non-unique(STRUCT-11)라 `INSERT OR IGNORE`가 무력 → 소스
전체 재삽입. `backfill_blank_titles()`이 같은 블로그+날짜 다중 행에 첫 소스
제목을 덮어씀 (오염 의심).

## 파괴적 작업 목록 (전 과정)

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 20:15 | run_sync 재삽입 (사고) | `python -c "run_sync()"` | 42,256행 | 없음 | 57,770행 (+15,514) | source='' 36행 유지 |
| 20:26 | 오염 백업 | `cp` → `bak_20260806_202605` | 57,770 | 본파일 | 해시 동일 | 해당없음 |
| 20:31 | 증거본 보존 | `cp` → `EVIDENCE_polluted_20260806` | 57,770 | 본파일 | 해시 동일 | 해당없음 |
| 20:40 | 클린 백업 (스케줄러 정지 후) | `cp` → `clean_before_recovery_20260806_204047` | 57,771 | 본파일 | 동일 | 해당없음 |
| 20:50 | R2 백업 보존 | `cp` → `r2_20260806_0500` (읽기전용) | 9.2MB | 본파일 | 동일 | 해당없음 |
| 20:52 | **중복 정리 + partial UNIQUE** | 4수치 검증 COMMIT | 삭제 24,061 | 안전망 3벌 | 총 33,710 | **source='' 18,301 유지 ✓** |
| 20:53 | 롤백 1건 | full UNIQUE 시도 실패 | 동일 | 동일 | ROLLBACK 57,771 | source='' 보존 확인 |
| 20:55 | **백필 원복 — 보류 (옵션 C)** | 미실행 | 966행(불안정) | 동일 | 미실행 | 실발행 제목 유실 위험 |

## 4단계 프로토콜 이행

1. **사전 카운트**: 초기 57,771행 / source!='' 중복 24,061행 / source='' 18,301행(전량 보존 불변식).
   클린 스냅샷 없음 확인 (Time Machine 0건, R2 백업도 6/19부터 중복 보유 → 판정 B).
2. **되돌림 수단**: 안전망 3벌 —
   `clean_before_recovery_20260806_204047`(복구 기준선, 43MB),
   `EVIDENCE_polluted_20260806`(증거본, 43MB),
   `r2_20260806_0500`(R2 8/6 05:00, 읽기전용 9.2MB).
3. **실행**: 스케줄러 PID 31420 + com.5000.scheduler 정지 확인 → lsof 0건 → 실행.
   중복 삭제 → partial UNIQUE(WHERE source != '') 재생성. 트랜잭션 내 4수치
   (삭제 24,061 / 총 33,710 / s!='' 15,409 / s='' 18,301) 정확히 일치 → COMMIT.
4. **사후 대조**: run_sync 재실행 +0 (idempotent), partial UNIQUE 중복 INSERT 차단 실측,
   M09 전수 23/23 pass, 준비도 stale 7개 (변경 없음).

## 코드 수정 (커밋 219816b57)

- `run_sync()`: SELECT-존재확인 후 INSERT (중복 재삽입 차단)
- `run_sync()`에서 `backfill_blank_titles()` 호출 제거 (오염 차단)
- `_ensure_schema()`: 기대 인덱스 정의를 partial UNIQUE(4중 키 + WHERE source != '')로 갱신
- 복구 절차서: `RECOVERY-content-db-20260806.md`

## 결과 / 보존 대상 확인

- **source='' 실발행: 18,301행 전량 보존** (삭제 0건 — 최우선 불변식 달성).
- source!='' 중복 24,061행 삭제 → 15,409행 잔여 (4중 키 기준 고유).
- 백필 원복: **보류** — 원복 대상 1,412→872→966행 불안정, URL 동일 233행(정당 재발행)
  + 판정불가 359행 혼재로 추측 기반 blank 원복은 실발행 제목 유실 위험. STRUCT-13 등록.

## 이슈 상태 (known_issues)

| 이슈 | 상태 | 내용 |
|------|------|------|
| STRUCT-11 | **resolved** | non-unique idx_ledger_dedup → partial UNIQUE 재생성. 1/7부터 누적된 반년 묵은 결함 명시 |
| STRUCT-12 | open | source='' 내부 레거시 중복 2,935그룹/15,177행 (관찰용, 삭제 보류) |
| STRUCT-13 | open | 백필 오염 966행 (재발행 233+다른글 374+판정불가 359, 원복 보류) |

## 잔존 위험

- 백필 오염 966행 title은 그대로 (원복 보류) — 향후 백필 실행 시점 로그 기반 정밀 원복 필요.
- source='' 내부 레거시 중복 15,177행 — 카운트 집계 시 DISTINCT 처리 검토.
- 스케줄러 정지 상태 유지 — 정상화 완료 전 재기동 금지 (별도 승인 필요).
