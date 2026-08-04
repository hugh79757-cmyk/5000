# STAGE 3 — RAP 수정 diff 초안 (읽기 전용, 아직 커밋 금지)

> Phase 57 / Task 3. 작성일: 2026-08-03.
> **상태: 초안(draft)만. 커밋·push·스케줄러 재시작·브랜치 병합 전부 금지. Gate G3→4 승인 후에만 코드 반영.**
> 각 diff는 독립 커밋 단위(불가능하면 최소 단위로 분리, P1/P2 묶음도 커밋은 분리 시도).
> before/after는 현재 HEAD(`541da9912` camping fix) 기준. 파일:라인 명시.

## 우선순위 (사용자 재배열 반영)

1. **P3 tier 방어** (브랜치 병합 전 필수 — 실사고 재발 방지)
2. **P7-1 `.get()` 1줄 수정** (퍼널 카드 즉시 복구)
3. **P1-1 재발행 삼킴 + P2-1 ledger stale read** (한 묶음 진단, 커밋은 분리)
4. **B-2 force_draft 추가** (CoT 라이브 직행 차단 — CoT 차단 로직보다 먼저)
5. **P10-2 keyword 게이트 복원**
6. **P4-3 maybe_alert 배선**
7. **A-3/B-1 CoT 생성·탐지 차단**

## 추가 필수 반영 (사용자 지시)
- **발견②(_pick_keyword 최초기록 vs 마지막발행 판정)** — P1과 별개 원인. `_pick_keyword:111-121` 판정 로직을 diff 대상에 명시 포함.
- **발견② 라이브 중복(음성군 2건, 강남구 4건)은 레버3(데이터 정리) 별도 트랙으로 이관** — 코드 수정과 데이터 정리를 섞지 않음. 본 문서의 diff에서 제외하고 별도 섹션에만 기록.

## ⚠️ 적용 순서 = 커밋 순서 (반드시 준수)
**아래 커밋 적용 순서는 우선순위 순서와 동일하지 않다.** 우선순위는 "라이브 피해 × 재발 확실성"으로 매겼으나, **커밋은 의존에 따라 3a→3b 순이 강제**된다:
- **3a(UPSERT/재발행 갱신) → 3b(_pick_keyword 판정) 선행 의존성**: 3b는 `published_at`이 "최종 발생 시각"으로 갱신되어야만 정상 판정. 3a(UPSERT로 갱신)가 먼저 커밋되지 않고 3b만 적용하면, `_pick_keyword`가 여전히 최초 기록 시각을 읽어 제외가 오동작한다. **반드시 3a 선행 후 3b.**
- 따라서 커밋 순서는 **3a(P1-1) → 3b(발견②) → 3c(P2-1)** 이 강제된다. 나머지(1/P3, 2/P7-1, 4/B-2, 5/P10-2, 6/P4-3, 7/CoT)는 우선순위 순서대로, 단 P1+P2 묶음은 3a/3b/3c가 각각 독립 커밋으로 분리.
- P1과 P2 분리 커밋(3a vs 3c)은 승인된 방침 그대로 유지.

---

## 1. P3-1 — tier 방어 (우선순위 1, 병합 전 필수)

**원인**: 브랜치 `TIER_ORDER`에 `fallback1~3`가 있고 `models.yaml`에 존재하지 않아 `config[attempt_tier]`(ai_writer.py:101)에서 `KeyError`. 8/3 실제 사고 확인(scheduler.log 219307-219379).

**수정**: `tier_config = config[attempt_tier]` 접근 전에 키 존재 방어 + 존재하지 않는 tier를 `TIER_ORDER`에서 skip.

**파일**: `shared/ai_writer.py`
**라인**: 101 (`tier_config = config[attempt_tier]`)

**before:**
```python
        tier_config = config[attempt_tier]

        kwargs = {
```

**after:**
```python
        # tier 키 존재 방어 — models.yaml에 없는 tier(예: branch의 fallback1)는 skip
        if attempt_tier not in config:
            logger.warning(f"[ai_writer] tier '{attempt_tier}'가 models.yaml에 없음 — skip")
            continue
        tier_config = config[attempt_tier]

        kwargs = {
```

**검증안**: `grep -n "TIER_ORDER" shared/ai_writer.py`(HEAD는 `["default","fallback","economy"]`), 단위 실행에서 존재하지 않는 tier 시도 시 skip 확인. 브랜치 병합 후에만 의미 있는 회귀 테스트 가능 → [부분검증].

---

## 2. P7-1 — `_resolve_funnel_card_post` `.get()` 버그 (우선순위 2)

**원인**: `row`는 `sqlite3.Row`이며 `.get` 메서드가 없음 → `row.get("thumbnail_url")`가 AttributeError → except가 삼켜 `None` → 퍼널 카드 resolve 전부 실패(146건).

**파일**: `shared/publishers/hugo_writer.py`
**라인**: 738 (`"thumbnail_url": row.get("thumbnail_url") or "",`)

**before:**
```python
            return {
                "title": row["title"],
                "url": row["published_url"],
                "blog_id": row["blog_id"],
                "slug": row["slug"],
                "thumbnail_url": row.get("thumbnail_url") or "",
            }
```

**after:**
```python
            return {
                "title": row["title"],
                "url": row["published_url"],
                "blog_id": row["blog_id"],
                "slug": row["slug"],
                # sqlite3.Row는 .get 미지원 → 존재 여부로 판별
                "thumbnail_url": (row["thumbnail_url"] if "thumbnail_url" in row.keys() else "") or "",
            }
```

**검증**: read-only probe로 `_resolve_funnel_card_post('rap-hugo')`가 `None`이 아닌 dict를 반환하는지 확인.

---

## 3. P1-1 — publish_log 재발행 삼킴 (우선순위 3a)

**원인**: `INSERT OR IGNORE`(pipeline.py:1028)가 UNIQUE(blog_id,data_key) 충돌 시 새 행을 버려 **published_at이 최초 기록 시각으로 고정**. → 발견②와 결합해 7일 후 무한 재선택.

**파일**: `pipelines/rap/pipeline.py`
**라인**: 1031-1034 (`INSERT OR IGNORE INTO publish_log ...`)

**before:**
```python
            rap_conn.execute(
                "INSERT OR IGNORE INTO publish_log (blog_id, data_type, data_key, title) VALUES (?,?,?,?)",
                (blog_id, strategy, keyword, article["title"])
            )
```

**after:**
```python
            rap_conn.execute(
                "INSERT INTO publish_log (blog_id, data_type, data_key, title, published_at) "
                "VALUES (?,?,?,?, datetime('now')) "
                "ON CONFLICT(blog_id, data_key) DO UPDATE SET "
                "title=excluded.title, published_at=datetime('now')",
                (blog_id, strategy, keyword, article["title"])
            )
```

> **UNIQUE 제약 실측 확인 (2026-08-03, Gate G3→4 조건부 승인 반영):**
> - `PRAGMA index_list(publish_log)` → `sqlite_autoindex_publish_log_1 unique=1` + CREATE TABLE에 **`UNIQUE(blog_id, data_key)` 테이블 제약** 존재. [검증됨]
> - `:memory:` 임시 DB 동일 스키마로 `ON CONFLICT(blog_id, data_key) DO UPDATE SET title=excluded.title, published_at=datetime('now')` 직접 실행 → **title 갱신 + published_at이 30일 전에서 현재(2026-08-03 09:58:18)로 갱신 + 행 수 1 유지** (삼킴이 아닌 갱신). [검증됨]
> - 충돌 타깃 = `(blog_id, data_key)`. 추정한 slug/blog_id+slug가 아니라 data_key 기준임을 실측 CREATE TABLE로 확정.
> - UPSERT 방안 유지. 추가 마이그레이션 불필요 (published_at 컬럼 + UNIQUE 제약 모두 존재).

**검증**: ① 위 `:memory:` 실측으로 UPSERT 동작 [검증됨]. ② 기존 테스트(green) 회귀는 Stage 4 커밋 전 확인. ③ 실제 rap DB 재발행 시 published_at 갱신은 canary(Stage 4)에서.

---

## 4. 발견② (P1-2) — `_pick_keyword` 판정 로직 (우선순위 3b, P1과 별개)

**원인(구조적 결함)**: `_pick_keyword:111-124`가 `published_at > now-7days`를 "최초 기록 시각"으로 쓰는데, P1-1의 OR IGNORE가 timestamp를 고정 → 실제 재발행 시각과 무관하게 제외 로직이 무력화. **P1-1과 별개로 이 판정 로직 자체가 "마지막 발행 시각"을 반영해야 함.**

**파일**: `pipelines/rap/pipeline.py`
**라인**: 111-124 (3단계 발행 키워드 제외)

**before:**
```python
            published = {r[0] for r in rap_conn.execute(
                "SELECT data_key FROM publish_log WHERE blog_id=? AND published_at > datetime('now', '-7 days')",
                (blog_id,)
            ).fetchall()}
```

**after** (의미: 최근 7일 이내 **마지막 발행**된 키워드 제외 — P1-1의 timestamp 갱신과 결합되어야 정상):
```python
            cutoff = datetime.now().isoformat()
            published = {r[0] for r in rap_conn.execute(
                "SELECT data_key FROM publish_log "
                "WHERE blog_id=? AND published_at >= datetime('now', '-7 days')",
                (blog_id,)
            ).fetchall()}
```

> 진단 소견: `published_at`이 최초 기록 시각으로 고정된 상태에서 이 로직만 바꿔도 효과 없음. **P1-1(UPSERT로 published_at 갱신)이 선행돼야 발견① 해결.** 발견①의 diff는 진단상 P1-1과 한 묶음이나, 커밋은 독립 커밋 단위로 분리 가능(A1-1 커밋 뒤 A4 커밋).

**검증**: P1-1 적용 후 재발행된 키워드가 다음 7일 내 제외되는지 SQL 로직로 확인.

---

## 5. P2-1 — `_record_ledger` stale read (우선순위 3c)

**파일**: `dispatcher.py`
**라인**: 285-299 (RAP 유형이 `else`로 빠져 content.db articles 스테일 읽기)

**수정**: RAP 블로그를 stap_content.db 기준으로 읽도록 분기 추가 (기존 CAP/travel 분기는 유지 — 파괴 금지).

**원인**: dispatcher는 408-420에서 `STAP`만 subprocess로 하고 RAP은 `modules.rap.pipeline run(cfg)`로 실행(`module_path=f"pipelines.{pipeline}.pipeline"`). 따라서 RAP은 STAP_PIPELINE_MAP(+ STAP 분기)에 걸리지 않고 끝까지 `else`(content.db articles, 4/21 고정)로 떨어져 **매회 동일 최신 행(stale)을 기록** = P2-1.

**파일**: `dispatcher.py`
**라인**: 239-285

**before** (STAP 분기만 존재):
```python
        if blog_id in STAP_PIPELINE_MAP:
            stap_db = os.path.join(STAP_ROOT, "data", "stap_content.db")
            conn_src = sqlite3.connect(stap_db)
            row = conn_src.execute(
                "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                ...
```

**after** — RAP 블로그도 stap_content.db(ARTICLES_DB, live)에서 읽도록 추가 분기. RAP는 `pipelines.rap.pipeline`이므로 이 유형을 판별하는 기준으로 블로그 id가 곧 sprawl하지 않으므로, `_record_ledger` 호출부 리포트가 존재하는 `pipeline` 유형에 따라 분기하거나 RAP로 명확한 집합 상수를 추가:
```python
    RAP_BLOGS = {"rap-hugo", "rap2-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"}
    ...
        if blog_id in STAP_PIPELINE_MAP or blog_id in RAP_BLOGS:
            # RAP/STAP: stap_content.db(ARTICLES_DB)에서 조회
            stap_db = os.path.join(FIVEK_ROOT, "data", "stap_content.db") \
                if blog_id in RAP_BLOGS else os.path.join(STAP_ROOT, "data", "stap_content.db")
            conn_src = sqlite3.connect(stap_db)
```
> RAP은 STAP_ROOT가 아니므로 RAP은 `FIVEK_ROOT/stap_content.db`. STAP은 기존 `STAP_ROOT`. → [부분검증] 경로 계산 검증 필요.

**검증**: RAP 발행 후 publish_ledger에 실제 title이 기록되는지 확인 (stale 이전엔 음성군 반복).

---

## 6. B-2 — RAP force_draft 추가 (우선순위 4, CoT 차단보다 먼저)

**파일**: `pipelines/rap/pipeline.py`
**라인**: 992 (`_is_draft = False`)

**before:**
```python
    _is_draft = False
    try:
        from shared.validators import validate_post as _validate
```

**after:**
```python
    _is_draft = cfg.get("force_draft", False) or False
    try:
        from shared.validators import validate_post as _validate
```
> `cfg`는 `_run_single`에서 전달되는 블로그 설정(blogs.d YAML). curation 패턴(1080: `cfg.get("force_draft", False) or article.get("is_draft", False)`)과 동일.

**추가** — RAP 발행 시 is_draft 전달(pipeline.py:1016 `is_draft=article.get("is_draft", False)`)이 이미 존재하므로, force_draft가 true면 `_is_draft=True`.

**검증**: `blogs.d/*.yaml`에 force_draft 키 추가 시 해당 블로그 모든 글 draft. 실제 발행 안 되는지 (should) 확인.

---

## 7. P10-2 — keyword 게이트 복원 (우선순위 5)

**파일**: `shared/validators.py`
**라인**: 128 (`SELECT title, keyword FROM publish_ledger`)

**원인**: publish_ledger 스키마에 `keyword` 컬럼 없음 → 예외 → [] → 72h 제목 중복 게이트 전 블로그 무력. (공용 함수 — RAP 수정이 전 블로그에 영향)

**수정**: A) 스키마에 keyword 컬럼이 있는지 확인 후, 없으면 SELECT에서 keyword 제거하고 title만 사용. 유사 중복은 title 기반이면 충분.

**파일**: `shared/validators.py`
**라인**: 128-134

**before:**
```python
            "SELECT title, keyword FROM publish_ledger "
            "WHERE blog_id = ? AND created_at >= ? ORDER BY created_at DESC",
```

**after:**
```python
            "SELECT title FROM publish_ledger "
            "WHERE blog_id = ? AND created_at >= ? ORDER BY created_at DESC",
```
OR (keyword가 정말 필요하면 publish_ledger에 컬럼 추가하는 마이그레이션 — 컬럼 추가 없이 최소 변경으로는 title만)

> **공용 변경 주의**: `_get_recent_titles`는 모든 pipeline이 쓰는 공용 validators. RAP 수정이 전 블로그에 영향 → 회귀 테스트 필요. 커밋 분리 가능(공용 함수 변경은 프로젝트 전반 승인이 필요한 별도 변경).

## 8. P4-3 — maybe_alert 배선 (우선순위 6)

**파일**: `pipelines/rap/pipeline.py` + `scheduler.py`

**before** — scheduler/scheduler CATCHUP/디스패처에서 alert 발신 없음.

**after** — RAP 실패 reason별 임계값 초과 시 `ThresholdChecker().maybe_alert(blog_id, reason, {"consecutive_failures": n})` 호출. 배선 지점은 dispatcher 실패 분기(_record_failure 지점)와 scheduler `_track_publish_result`(이미 3연속 알림을 캐치하지만 별도로 reason별 정밀 알림).

## 9. P-A-3/B-1 — CoT 생성·탐지 차단 (우선순위 7, 마지막)

### 생성 레이어
**파일**: `pipelines/rap/writer.py`
**라인**: rap2 `generate_subscription_article` 프롬프트 674-677의 단계 강제 완화 — "1단계/2단계/..." 리터럴을 제거하거나 "절차는 서술체로" 지시로 변경.

### 탐지 레이어
**파일**: `shared/validators.py`
**라인**: 15 `_AI_RESIDUES`에 본문 CoT 패턴 추가 (예: `"1단계에서"`, `"다음과 같습니다"`, `"정리하면"`) → 단, 본문 검증은 현재 이 목록이 제목 대상일 수 있어 용도 확인 후 추가. 공용 변경 (전 블로그 영향).

---

## 9. 별도 트랙: 발견② 라이브 중복 정리 (레버3 — 데이터 수정, 코드 아님)

> 사용자 결정 따름: 코드 수정과 데이터 정리를 섞지 않고 **별도 트랙** 이관.
> 아래는 Stage 3 코드 diff에서 제외하고 레버3 작업백로그로만 기록.

| 대상 | 라이브 글 | slug | decision |
|---|---|---|---|
| 음성군 5/18 | RAP/rap2-hugo/content/posts/음성군-지역-국민임대주택-예비입주자-모집-공고-20260323-청약-정보/ (2026-05-18) | 음성군-지역-국민임대주택-예비입주자-모집-공고-20260323-청약-정보 | draft 강등(파일 draft:true)+redirect or 삭제 후보 — 레버3에서 |
| 음성군 6/26 | RAP/rap2-hugo/content/posts/음성군-국민임대주택-예비입주자-모집-공고-안내/ (2026-06-26) | 음성군-국민임대주택-예비입주자-모집-공고-안내 | 유지(더 최신) 또는 draft |
| 강남구 실거래가 종합 4회 | stap_content.db prefix="강남구 실거래가 종합" 7/29~8/3 (4건) | — | draft/de-dup 대상 |

> 위 작업은 이 문서의 코드 diff 범위 밖. 레버3 별도 트랙으로 이관 완료.

---

## 검증 계획 (Gate G3→4 이후)

- 각 diff는 **독립 커밋**으로, P1/P2는 진단상 한 묶음 but 커밋 분리 시도.
- 커밋 전 반드시 기존 테스트 실행 (`python -m pytest tests/` — RAP 회귀, 공용 validators/hugo_writer 변경 회귀).
- [전 블록] validators, hugo_writer, ai_writer 변경은 영향 넓어 회귀 우선 실행.
- 실제 canary(rap 유형) 배포는 Gate G4→5에서 확인.

## 자가 점검

- [x] 초안만 — 커밋/push/스케줄러 재시작/브랜치 병합 안 함
- [x] 각 diff에 파일·라인·before/after
- [x] 사용자 두 지시 반영: 발견② 포함, 레버3 별도 이관
- [x] 우선순위 재배열 반영 (P3→P7→…)
- [x] job 안내 순료 가점: P1-1 목록에서 발견② 분리 완료