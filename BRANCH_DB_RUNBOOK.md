# BRANCH_DB_RUNBOOK.md — 분기 DB 복원 런북 (Branch DB Restore Runbook)

> **목적**: 5000 파이프라인이 소유하는 분기별 SQLite DB(`data/*.db`) 손실/오염 시, 복구 등급 A/B/C별로 대응하는 표준 절차. content.db 오염 사고(STRUCT-11: 15,514행 재삽입, 1,412건 제목 오염) 재발을 막는다. 본 문서는 **절차서**일 뿐 실제 파괴적 작업은 수행하지 않는다. 실제 복원은 사용자 승인 + 본 런북 + AGENTS.md Destructive Ops 규칙을 따른다.
> **상태**: 📋 문서화 완료 (Phase 74 Wave 3, SC-5)
> **위험도**: 복원 작업 자체는 HIGH 파괴적 — 본 런북을 따르는 한 단계마다 destructive-ops 4단계 + 라이브 스케줄러 정지 선행.

---

## 0. ANY 복원 전 선행 조치 (mandatory)

모든 등급(A/B/C) 복원 이전에 **무조건** 수행한다.

1. **라이브 스케줄러 정지** — 프로덕션 DB에 쓰는 작업이므로 선행 조건.
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist
   # 정지 확인
   launchctl list | grep 5000.scheduler || echo "STOPPED_OK"
   ```
2. **등급 식별** — 아래 §1/§2/§3 맵에서 대상 DB의 등급 확인.
3. **Class B만 해당**: `content.db`의 `source=''` 실발행 행 보존 확인(아래 §2 필수 단계 참조). **이 행을 건드리는 것은 금지** — 영구 보존 대상.
4. **예방 메커니즘 숙지**: 본 phase Wave 1의 `shared/db.py:connect_branch_db(branch, allow_create=False)` 가드가 누락 파일에서 **무음 생성을 막고 `BranchDbMissingError`를 raise**한다. 신규 코드/호출부는 이 가드를 우선 사용할 것(§5 참조). 가드가 있었다면 STRUCT-11 계열 사고 대부분이 사전 차단되었을 것.

> **destructive-ops 4단계** (AGENTS.md): 본 런북의 모든 쓰기 절차는 이 순서를 따른다 — **① 사전 카운트/영향 범위 → ② 되돌림 수단(백업) 확보 → ③ 실행 → ④ 사후 대조**. 대량 삭제/UPDATE/재생성/배포는 반드시 사용자 확인 선행. 라이브 스케줄러 정지 후에만 실행. 파괴적 작업 1건마다 `logs/destructive_YYYY-MM-DD.log`에 한 줄 append, 종료 시 `.planning/worklog/WL-<날짜>-db-restore.md` 작성.

---

## 1. Recovery Grade A — 재수집 복구 (re-collect from source)

**대상**: `car.db`, `rap.db`, `senior.db`, `stock.db`, `festival.db`, `course.db`, `travel-en.db`, `gap.db`

**트리거**: DB 파일 누락 / 0-byte / corrupt AND 유효한 백업이 없거나 재수집 소스가 authoritative.

**원칙**: 소스가 단일 진실원이므로 백업 복원이 불필요. 수집기 재실행만으로 재구성. (백업은 보조 안전망 — 재수집 소스 생존 불확실 시에만 §B로 전이, RESEARCH OQ-3.)

### A 절차 (destructive-ops 4단계 통합)

**① 사전 카운트**
```bash
# 형제 DB / 소스 예상 볼륨 확인 (참고용, 강제 아님)
ls -la data/<db>.db
```

**② 백업 (되돌림 수단)** — 실행 전 원본 보존. 0-byte여도 복사.
```bash
TS=$(date +%Y%m%d_%H%M%S)
cp data/<db>.db data/<db>.db.bak_$TS
echo "BACKUP=$TS"
```

**③ 실행 — 브랜치 수집기 재실행**
```bash
# car
python pipelines/car/daily_refresh.py
# rap
python pipelines/rap/rap_data_sync.py && python pipelines/rap/keyword_generator.py
# senior
python pipelines/senior/fetcher.py            # init_senior_db() 동반
# stock
python pipelines/stock/fetcher.py             # corps/etf_daily/dividend_ranking 재수집
# festival
python scripts/refresh_festival.py
# course
python scripts/refresh_course.py
# gap (news-keyword-pro CSV 재임포트)
python scheduler.py 680                       # CSV import 경로
# travel-en (ETAP 엔티티 — travel 아님, RESEARCH F2)
python -c "from cuap_entity_linker import init_cuap_tables; init_cuap_tables()"
# + ETAP entity collector 재실행
```

**④ 사후 대조**
```bash
# 재수집 행 수 vs 소스/기대치 확인, 발행 슬러그 1건 렌더 스팟체크
sqlite3 data/<db>.db "SELECT count(*) FROM <key_table>;"
```
> **주의(RESEARCH OQ-3 / A5 HIGH)**: `course.db`(과정 API), `gap.db`(CSV 피드), `travel-en.db`(ETAP) 소스가 사라지면 class A → class B로 전이. 재수집 전 소스 생존을 반드시 먼저 확인.

---

## 2. Recovery Grade B — 원장/백업 복원 (restore from backup)

**대상**: `content.db`, `stap_content.db`, `curation.db`

**트리거**: 오염 / 잘못된 backfill(STRUCT-11 유형) / corrupt. 원장은 시스템 오브 레코드 — 재수집 금지.

> ⚠️ **CRITICAL — `content.db` `source=''` 실발행 행 영구 보존**
> `content.db`의 `source=''` 행은 실제 발행 기록(실발행 행)이다. AGENTS.md 영구 보존 규칙: **유실 0**. 복원 전후로 반드시 보존 건수를 검증하고, **이 행을 건드리는 어떤 쓰기(DELETE/UPDATE/재생성)도 금지**한다. 보존 검증 단계를 빠뜨리면 복원 불가.

### B 절차 (destructive-ops 4단계 통합)

**① 사전 카운트**
```bash
# content.db 실발행 행(보존 대상) 건수 스냅샷
sqlite3 data/content.db "SELECT count(*) FROM publish_ledger WHERE source='';"
# stap_content.db articles 건수
sqlite3 data/stap_content.db "SELECT count(*) FROM articles;"
# curation.db
sqlite3 data/curation.db "SELECT count(*) FROM published_products;"
```

**② 백업 (되돌림 수단)** — 복원 전 원본 + 실발행 행 스냅샷 보존.
```bash
TS=$(date +%Y%m%d_%H%M%S)
cp data/content.db data/content.db.bak_$TS
cp data/stap_content.db data/stap_content.db.bak_$TS
cp data/curation.db data/curation.db.bak_$TS
# 실발행 행 별도 덤프 (복원 후 대조용)
sqlite3 data/content.db ".dump \"SELECT * FROM publish_ledger WHERE source=''\"" > data/content_source_empty_$TS.sql
echo "BACKUP=$TS SRC_EMPTY=$(sqlite3 data/content.db "SELECT count(*) FROM publish_ledger WHERE source='';")"
```

**③ 실행 — 타임스탬프 백업에서 gunzip 복원**
```bash
# 가장 최신 정상 백업 선택 (RETAIN_DAYS=7 주의, RESEARCH OQ-2)
ls -t db-backups/db/5000/<db>_*.db.gz | head -1
gunzip -c db-backups/db/5000/<db>_<DATE>.db.gz > data/<db>.db
```
> 복원 전 백업 무결성 확인 권장: `sqlite3 db-backups/db/5000/<db>_<DATE>.db.gz ... "PRAGMA integrity_check;"` (RESEARCH Pitfall 3 — 0-byte/trunc 백업 오염 방지).

**④ 사후 대조 — [필수] `source=''` 보존 검증**
```bash
# 복원 후 실발행 행 건수 == ① 사전 카운트 (유실 0이어야 함)
AFTER=$(sqlite3 data/content.db "SELECT count(*) FROM publish_ledger WHERE source='';")
BEFORE=<①에서 기록한 값>
[ "$AFTER" = "$BEFORE" ] && echo "PRESERVE_OK loss=0" || echo "PRESERVE_FAIL before=$BEFORE after=$AFTER"
# 무결성
sqlite3 data/content.db "PRAGMA integrity_check;"
```
> **PRESERVE_FAIL 시 즉시 중단**: ①의 `.bak_$TS`에서 재복원. 실발행 행 유실은 영구 유실로 취급.

---

## 3. Recovery Grade C — drop + reinit 안전 (self-heal)

**대상**: `ops.db`, `analytics.db`, `scanner.db`, `indexnow.db` (＋ `quality.db`, `metrics.db`, `cuap_entities.db`, orphan 0-byte 파일)

**트리거**: 파일 누락 / corrupt. 데이터는 유실되나 `CREATE TABLE IF NOT EXISTS`로 다음 실행 시 자가 복구(의도된 drop+reinit). 백업 불필요.

### C 절차 (destructive-ops 4단계 통합)

**① 사전 카운트** — N/A (재생성 가능, 데이터 유실 의도됨).

**② 백업** — 선택(존재 시에만).
```bash
[ -f data/<db>.db ] && cp data/<db>.db data/<db>.db.bak_$(date +%Y%m%d_%H%M%S)
```

**③ 실행 — 파일 삭제 후 self-heal 유도**
```bash
# 직접 drop + 재실행(자가 복구)
rm -f data/ops.db && python -c "from ops_dashboard.db import get_conn, init_db; init_db()"
rm -f data/indexnow.db && python scripts/indexnow.py --init
# 나머지(analytics/scanner/quality/metrics/cuap_entities)는 다음 파이프라인 실행 시 자가 heal
```

**④ 사후 대조**
```bash
sqlite3 data/ops.db "SELECT name FROM sqlite_master WHERE type='table';"   # 테이블 존재 확인
# 대시보드 로드 확인 (ops_dashboard/app.py :5060)
```

---

## 4. 복원 트리거 / 커뮤니케이션

- **실행 주체**: Class B(무음 유실 위험)는 **사람만** 수동 실행. Class A/C는 script-assisted.
- **경고(alert)**: `BranchDbMissingError` 발생 시 Telegram 라우팅 — 재사용 `shared/telegram_notifier._tg_error(...)`.
- **worklog**: 파괴적 단계마다 `logs/destructive_YYYY-MM-DD.log` append + 종료 시 `.planning/worklog/WL-<date>-db-restore.md`.
- **커밋/배포**: 복원 작업은 DB 파일 대상. git push 금지(사용자 요청 시에만). wrangler deploy는 본 복원과 무관.

---

## 5. Reference (예방 메커니즘 + 자산 맵)

- **무음 생성 방지 가드 (Wave 1, SC-1·SC-6)**: `shared/db.py:connect_branch_db(branch, allow_create=False)`
  - `allow_create=False`(기본) + 파일 누락 → `BranchDbMissingError` raise.
  - `stock`→`stap_content.db`(기존 시맨틱 보존), `stock_metrics`→`data/stock.db`(collision 해소) 양등록.
  - 모든 신규/마이그레이션 branch-DB read 경로는 이 가드 우선 사용.
- **DB 맵 (전수)**: `.planning/phase-74-branch-db-resilience/RESEARCH.md` Deliverable 1 (26개 `data/*.db` → branch/table/init-fn/backup/class).
- **백업 스크립트**: `scripts/master_backup.py` (`DB_TARGETS["5000"]` — class-A 3종 `senior.db`/`course.db`/`gap.db` Wave 2에서 보강).
- **사고 선례**: STRUCT-11 (content.db 15,514행 재삽입 / 1,412 제목 오염) — 본 런북 §2 보존 검증으로 재발 방지.

---

## 잔존 위험

1. **백업 보존 기간**: `RETAIN_DAYS=7` — class-B 오염 시 7일 이전 정상 복사본 부재 가능(RESEARCH OQ-2). 본 런북은 커버리지만 문서화, 보존 기간은 미변경(별도 검토 필요, ≥30일 권장).
2. **재수집 소스 생존 불확실**: course/gap/travel-en 소스 소실 시 class A→B 전이(RESEARCH OQ-3, A5 HIGH). §1에 "소스 확인 선행" 명시.
3. **self-heal 유실**: class-C 미백업 파일은 drop+reinit로 데이터 유실(의도됨) — §3 명시.
4. **`5000_content.db` 용도 불명**: 라이브 원장 아님 가정(RESEARCH OQ-6). 본 런북은 `content.db`를 단독 시스템 오브 레코드로 취급.
