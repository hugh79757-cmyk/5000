# Part 6: CUAP 확장 게이트 + 잔존 2건 확정 보고서

> 작성일: 2026-08-06
> 범위: 6-1 확장 준비도 지표, 6-2 대시보드 표시, 6-3 시범 발행(게이트 미충족 → 미실행),
>       6-4 설계 최종 확인, Part 5 잔존 2건(render_health og:image, maintenance 무력) 확정
> 데이터: ops.db (check_results, known_issues), content.db (publish_ledger), curation.db (publish_log)

---

## 1. 확장 준비도 지표 (6-1)

**구현:** `ops_dashboard/readiness.py` (신규) — `compute_readiness()` 3지표 + CLI 출력.
**API:** `GET /api/readiness` (app.py). **표시:** index.html 첫 화면 한 줄.

세 지표가 모두 녹색일 때만 확장 허용(🟢), 하나라도 적색이면 확장 금지(🔴):

| 지표 | 임계값(녹색) | 현재값 (2026-08-06) | 판정 |
|------|-------------|--------------------|------|
| 표준 준수율 (standard_compliance 최신 pass 비율) | 100% (fail 0) | **0.0%** — pass 0/85 (fail 81, unknown 4) | 🔴 |
| stale active 블로그 수 | 0 | **7** (발행 기록 없음 5 + 3일 초과 2) | 🔴 |
| 미해결 known_issue 수 | 0 | **21** | 🔴 |

**현재 상태: 🔴 확장 금지** — 3지표 전부 적색. 이는 기대된 상태로, 확장(15→50)은
표준 준수율 정상화·stale 재개·이슈 해소 후 재평가해야 함.

**stale 산출 방식 주의:** `blog_lifecycle.days_since_last_publish`는 현재 전부 NULL
(집계 로직 미가동) → 이를 그대로 쓰면 stale=0으로 오판됨. readiness.py는 실제 소스인
`content.db publish_ledger`(status='published' 최근 발행)에서 직접 산출하도록 구현함.

---

## 2. 대시보드 표시 (6-2)

- index.html 최상단: `확장 준비도: 🔴 확장 금지 — 표준 0.0% | stale 7 | 미해결 21`
  + "표준 100% · stale 0 · 미해결 0 모두 충족 시 확장 허용" 안내 + API 링크
- `GET /api/readiness` JSON: `{ready, status, metrics{standard_compliance, stale_active_blogs, open_known_issues}, computed_at}`
- 검증: test_client로 `/`·`/api/readiness` 200 + 지표 렌더 확인

---

## 3. 시범 발행 (6-3) — 게이트 미충족으로 미실행

계획상 6-3은 "확장 준비도가 🟢일 때만 실행". 현재 🔴(표준 0%, stale 7, 미해결 21)
이므로 시범 발행을 실행하지 않음. **확장 검토 시점**: 3지표가 모두 녹색이 된 뒤에만
`python dispatcher.py {신규 블로그}` 실행 + 전수 체크 pass 확인.

---

## 4. 확장 대비 설계 최종 확인 (6-4)

| 확인 항목 | 결과 | 근거 |
|-----------|------|------|
| 계열 하드코딩 없음 | ✅ 확인 | `_detect_brand()`가 YAML 파일명 첫 세그먼트에서 동적 판정 (Part 5 커밋 9125b1ba7) |
| 새 YAML 추가만으로 편입 | ✅ 확인 | 더미 YAML add→86개, remove→85개 정상 (Part 5) |
| 헬스체크 플러그인 계열 무관 | ✅ 확인 | 6개 check가 blog_id 기준으로만 동작 (Part 5) |
| 계열 전용 규칙 추가 등록 구조 | ✅ 확인 | `register_check()` 플러그인 레지스트리 + `standard_rules` 테이블 (R01~R12) |

---

## 5. 잔존 2건 확정 (Part 5 후속)

### 5-1. render_health og:image 22/23 fail — 판정: (b) 검사기 오판

**증거 (실제 사이트 조회, 2026-08-06):**
- Hugo(Blowfish/PaperMod) 사이트는 og:image를 **홈페이지가 아닌 포스트 페이지**에서 발행.
  홈페이지에는 og:url/title/description만 있고 og:image 없음 → 기존 체크는 홈페이지만 검사해 전부 fail로 오판.
- 포스트 페이지 og:image 존재 확인: beauty, pet, senior, techpawz, rotcha, informationhot 등 전부 확인.
- Blogger(2.techpawz.com)는 `content='...' property='og:image'` **속성 역순**으로 발행 → 기존 정규식이 미매칭.
- 기존 `featureimage` meta 체크는 어떤 테마도 발행하지 않는 태그를 찾고 있었음.
- 홈페이지 href가 minified(unquoted) 형식(`href=/posts/...`)이라 기존 quoted-only 정규식이 포스트 링크를 못 찾음.

**수정 (ops_dashboard/checks/render.py):**
1. `_check_og_image()`: property/name 역순(Blogger) 패턴 추가
2. `_find_post_url()`: unquoted href + 목록/정적 에셋/feeds 제외 + Blogger `/YYYY/MM/slug.html` + 루트 슬러그(PaperMod) 지원
3. og:image 검사를 홈페이지 → **최근 포스트 1개**에서 수행
4. `_check_featureimage()`: 테마가 발행하지 않는 meta 대신 포스트 og:image로 대체

**결과:** 22/23 fail → **23/23 pass** (og:image URL 23개 전부 HTTP 200 확인 포함).

**실제 결함 1건 남음 (stock-hugo):** paused 상태인 STAP 사이트. `_find_post_url()`이 찾은
포스트(HTTP 200)의 meta에 og:image가 **실제로 없음** (Congo 테마 — 기존 STRUCT-04
theme_mismatch와 동일 근원). 검사기 오판이 아니라 실결함이며, 대시보드 주의필요에 그대로 노출됨.

**senior 썸네일 404 여부:** senior-hugo og:image
`https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/senior/*.webp`
→ **HTTP 200** (kuta-hugo 사례의 404와 동일 원인 아님). kuta의 broken_featureimage(P06)는
R2 미업로드가 원인이고, senior는 R2 업로드 정상.

### 5-2. maintenance M01/M07/M09 — M01·M07 무력 확정, M09 작동 중

**근거 (ops.db 테이블 확인 + 23개 active 블로그 전수 실행):**
- `publish_log`는 curation.db, `publish_ledger`는 content.db 소유. **ops.db에는 없음.**
- **M01** (`_check_cjk_in_title`): ops.db에서 publish_log/publish_ledger 조회 → 매회
  `sqlite3.OperationalError` → graceful pass. **23/23 전부 pass = 무력** (CJK 누수 미검출).
- **M07** (`_check_similar_title_safety`): 동일하게 ops.db에서 publish_ledger 조회 →
  항상 pass. **23/23 전부 pass = 무력** (similar_title 차단 미감지).
- **M09** (`_check_publish_log_integrity`): content.db/curation.db를 직접 연결 —
  **정상 작동**. finance-hugo에서 실질 실패 검출: ledger 발행 35건 vs publish_log 0건.

**등록 (known_issues, 모두 open):**
- `STRUCT-08` M01 무력 — 수정 후보: content.db/curation.db 연결 전환 또는 ops.db
  publish_ledger 스키마 미러링 + ledger_sync로 채움
- `STRUCT-09` M07 무력 — 수정 후보: content.db 직접 연결 (M01과 일괄 처리)
- `STRUCT-10` finance-hugo M09 실패 — 수정 후보: finance 발행 경로에서 curation
  publish_log 기록 누락 여부 확인
- **실수정은 Part 6 이후 별도 묶음으로 보류** (미해결 → 대시보드에 노출 유지).

---

## 6. 잔존 위험

1. **표준 준수율 0%** — 81개 블로그의 standard_compliance fail은 확장의 직접 차단 요인.
   원인(테마/광고/레이아웃 규칙 위반) 정상화 작업이 별도 필요.
2. **stale 7개** — 발행 기록 없는 5개(techpawz 계열 등) + 3일 초과 2개(senior)는
   파이프라인 재가동 또는 명시적 비활성화 필요.
3. **M01/M07 실수정 보류** — 무력 상태 그대로 두면 CJK 누수·유사제목 차단이
   감지되지 않음. 별도 묶음에서 반드시 수정 필요.
4. **`days_since_last_publish` 미집계** — blog_lifecycle 컬럼이 항상 NULL.
   ledger_sync 개선 시 이 컬럼도 채워야 freshness 체크가 정상화됨.
