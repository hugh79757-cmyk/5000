## Appendix D — Fleet 확장(온보딩) 런북

> 목적: 5000 대시보드에 새 블로그·새 분기를 추가할 때, 코드 구조를 읽지 않고도 안전하게 등록·검증할 수 있는 표준 절차. Appendix C와 동일한 "의도·경계형" 철학 — 정확한 명령은 실행 시점 생성, 목표 상태·허용 범위·STOP 조건만 못 박음.

---

### D.0 등급 요약표

| 작업 | 기본등급 | 조건부 분기 | 사용자 결정지점 |
|------|---------|-----------|--------------|
| 신규 블로그 추가 (active) | A | blog_id 중복·domain 중복 → B(중지·확인) / site_path 실존 확인 불가 → B | 도메인·blog_id 중복 의심 시 1회 |
| 신규 블로그 추가 (inactive/paused) | A | 위와 동일 | 위와 동일 |
| 신규 brand(YAML 파일) 추가 | A | brand명 충돌 → B(중지) / _detect_brand 패턴 불일치 → B | brand명 충돌 시 1회 |
| 신규 pipeline 추가 (코드 처리 필요) | B | pipeline 유형이 기존 STAP_PIPELINE_MAP/CAP_BLOGS 패턴이면 A에 가까움 / 완전 신규 파이프라인이면 B→C | dispatcher 분기 로직 필요 여부 확인 1회 |
| 기존 blog의 brand/pipeline 재분류 | 🔴 비가역 | — | 별도 웨이브 승인 필수 |

---

### D.1 시나리오 1 — 신규 블로그 추가

#### 필요 입력 (사용자 제공 — 하나라도 없으면 STOP)

| 입력값 | 예시 | 필수 여부 | 누락 시 |
|--------|------|----------|---------|
| `blog_id` | `test-hugo` | 필수 | 등록할 ID 없음 → 중단 |
| `brand` (YAML 파일명 유래) | `cuap` | 권장 (파일 선택으로 결정) | 몰르면 `config/blogs.d/testbrand.yaml` 생성 → brand=testbrand |
| `pipeline` | `curation` | 필수 | dispatcher 분기 로직 적용 불가 → B |
| `domain` | `test.informationhot.kr` | 필수 (현실적) | 도메인 없거나 중복 시 B |
| `theme` | `blowfish` | 권장 | 없으면 `theme=''` (표준 검사 R09 등에서 unknown 가능) |
| `site_path` (Hugo 소스 디렉토리) | `/Users/twinssn/Projects/cuap/test-hugo` | 필수 | 없으면 Hugo 빌드·배포 불가 |
| `status` | `active` 또는 `paused` | 필수 | 기본값 없음 → 명시 필요 |
| `daily_quota` | `5` | 권장 | 미지정 시 발행 빈도 통제 불가 |

**STOP-1:** 위 표 필수 입력 중 하나라도 비어 있으면 진행 중단. 사용자에게 나머지를 요청.

#### 등록 순서 (의도)

**목표 상태: 새 blog_id가 `/api/fleet`에 1건으로 뜨고, 표준 검사(R01~R14) 대상에 자동 편입되며, dispatcher가 blog_id→site_path 매핑을 아는 상태.**

1. **YAML 파일 생성** — `config/blogs.d/{brand}.yaml`에 새 블로그 엔트리 추가. 기존 파일이 있으면 그 아래에 `- id: ...` 블록 추가, 없으면 새 파일 생성. YAML 포맷은 기존 엔트리 복사 (필수 필드: id, pipeline, platform, status, domain, site_path, theme, schedule.times[]).
   - 허용: 해당 brand YAML 파일만 수정.
   - 금지: 다른 brand YAML, config/blogs.yaml (블로그 정의 아님) 수정.

2. **DB 동기화** — 대시보드 서버에서 `sync_blog_lifecycle()` 실행. 방법: `POST /api/run-checks` 호출 시 내부적으로 `_ensure_db()` → `sync_blog_lifecycle()` 호출됨. 또는 `python ops_dashboard/seed.py --run-checks`.
   - 목표 상태: `blog_lifecycle`에 새 blog_id 1행 INSERT/UPDATE.
   - 검증: `SELECT * FROM blog_lifecycle WHERE blog_id='{blog_id}'` → 1행 반환, brand/pipeline/site_path 정확.

3. **검사 대상 편입 확인** — `POST /api/run-checks?blog_id={blog_id}` 실행. goal: 해당 blog_id의 check_results 행이 check_name별로 1건씩 생성됨.
   - 허용: 특정 blog_id만 재검사.
   - 금지: 전체 재검사로 다른 블로그 baseline 흔드는 행위 (필요 시에만).

4. **dispatcher 경로 매핑 확인** — dispatcher.py가 blog_id를 인식할 수 있는지. 대부분의 경우 YAML의 `site_path`가 실제 소스 경로와 일치하면 자동 매핑됨. STAP/CAP 계열이면 각각 `STAP_PIPELINE_MAP`/`CAP_BLOGS`에 등록 필요할 수 있음 (파이스라인 유형 확인).

#### 허용 범위

- ✅ 건드려도 됨: `config/blogs.d/{brand}.yaml` (해당 brand 파일만), DB 동기화, 해당 blog_id 재검사.
- ❌ 건드리면 안 됨: 기존 블로그 YAML, dispatcher.py 원본 로직, ops_dashboard/db.py 스키마, 다른 brand 파일, 스케줄러 설정.

#### 검증 게이트

- [ ] `/api/fleet` 응답에 `{blog_id}` 1건 포함 (GET /api/fleet → JSON에서 blog_id 검색)
- [ ] `/api/registry` 또는 `POST /api/run-checks?blog_id={blog_id}` → check_results에 해당 blog_id 행 생성
- [ ] baseline 증가분이 예상 범위 내: active면 check_results +N행(N=check 수 ≈15), inactive/paused면 check_results 행은 생기지만 fail_checks에는 안 들어가고 excluded_fail_checks로만 편입
- [ ] excluded 총량 증가분이 의도대로만: inactive/paused 1건 추가 시 excluded_fail_checks +0건(실패 없으면) ~ +N건(실패 있으면). active면 fail_checks 쪽으로 편입.

#### STOP 조건

- (a) **허용 범위 벗어남** — brand YAML 외 파일이 계획에 포함됨
- (b) **blog_id 중복** — 이미 `blog_lifecycle`에 동일 blog_id 존재 → 중단, 사용자에게 기존 레코드 확인 요청
- (c) **domain 중복** — 다른 블로그가 동일 domain 사용 중 → 중단, 의도 확인
- (d) **baseline 예상 외 변동** — check_results/excluded 증가분이 예측 모델 범위를 벗어남
- (e) **검사가 안 도는 반쪽 상태** — `/api/fleet`에는 뜨나 `/api/registry`나 run-checks 결과에서 해당 blog_id의 check_results가 생성 안 됨
- (f) **dispatcher 경로 매핑 실패** — site_path가 실존하지 않거나 dispatcher가 blog_id 인식 못 함 → 중단, site_path 확인

#### 고친 뒤 화면 반영

- 수동 재검사 트리거: `POST /api/run-checks?blog_id={blog_id}` → check_results 즉시 갱신 → `/api/attention`·`/blog/{blog_id}` 페이지 새로고침 시 반영.
- 대기시간: 수동 실행 시 curl 반환 직후. 자동 갱신 스케줄 없음 (갱신 지도 참조).

---

### D.2 시나리오 2 — 신규 분기(brand/pipeline/카테고리) 추가

#### 분기 유형 판별 (먼저 결정)

| 유형 | 판별 기준 | 처리 방향 |
|------|---------|----------|
| **(a) 새 검사 규칙 축** | 새 R-규칙, 새 M-체크, 새 C-체크를 추가하려는 경우 | **Appendix C.W7 패턴**으로 위임: `rules.py` UnifiedEntry 1줄 + `standard.py`/`maintenance.py` 해당 함수 1개. 자동 편입. 이 런북 범위 밖. |
| **(b) brand/pipeline 분류 축** | 새 YAML 파일(brand) 추가, 기존 파이프라인과 다른 pipeline 값 사용, 카테고리/funnel_stage 확대 | 아래 절차. config 스키마·fleet 분류·excluded 필터·dispatcher 매핑을 건드리는 중량 작업. |

#### (b) brand/pipeline 분류 축 — 등록 순서 (의도)

**목표 상태: 새 brand/pipeline의 블로그가 fleet에 올바르게 분류되고, 표준 검사·excluded 필터·dispatcher가 의도대로 작동하는 상태.**

1. **brand 추가 (새 YAML 파일):**
   - `config/blogs.d/{새brand}.yaml` 생성. 파일명 → `_detect_brand()`로 자동 brand 추출.
   - 목표 상태: `/api/fleet` 응답의 `brand` 필드에 새 brand 값 등장, 해당 brand 블로그들이 함께 분류됨.
   - 허용: 새 YAML 파일 1개 생성 + 내용 작성.
   - 금지: 기존 YAML 파일 수정 (기존 블로그 재분류 위험).

2. **pipeline 값 확인:**
   - YAML의 `pipeline:` 필드가 기존 파이프라인 값(curation/car/stock/etap/travel/rap/senior) 중 하나면 추가 코드 변경 불필요.
   - 새 pipeline 값이 완전 신규면 → dispatcher.py의 파이프라인 분기 로직에 등록 필요할 수 있음 (B등급, 사용자 확인 1회).
   - **결정지점:** "이 pipeline이 dispatcher에서 별도 run() 호출·시범 매핑·DB 처리가 필요한가?" → 예면 B, 아니오면 A.

3. **기존 블로그 재분류 영향 확인 (중요 — STOP 유발 가능):**
   - 새 brand YAML은 기존 블로그를 건드리지 않음 (파일별 독립).
   - 단, 기존 블로그의 `pipeline:` 값을 바꾸거나 `status:`를 바꾸면 baseline·검사 대상 집합 변동 → **🔴 비가역.**
   - **STOP-3:** 기존 블로그의 field 수정이 계획에 포함되면 즉시 중단. 재분류는 별도 웨이브·명시적 승인 필요.

4. **dispatcher 매핑 확인 (필요 시):**
   - STAP 계열 새 블로그 → `STAP_PIPELINE_MAP` (dispatcher.py:79-86)에 blog_id→pipeline명 매핑 추가.
   - CAP 계열 새 블로그 → `CAP_BLOGS` 집합 (dispatcher.py:258-261)에 blog_id 추가.
   - ETAP 계열 → `_ETAP_BLOG_EXCEPTIONS` 확인.
   - cuap/rap/seap/tap 계열 → 일반적으로 YAML site_path로 충분, 추가 매핑 불필요.
   - 허용: dispatcher.py의 해당 매핑 dict/집합에만 추가.
   - 금지: dispatcher.py 분기 로직 전체 재구성.

#### 허용 범위

- ✅ 건드려도 됨: 새 brand YAML 파일, dispatcher.py의 매핑 dict/집합(STAP_PIPELINE_MAP/CAP_BLOGS 등), DB 동기화.
- ❌ 건드리면 안 됨: 기존 brand YAML, dispatcher.py 분기 로직 본문, db.py 스키마, 다른 pipeline의 처리 로직.

#### 검증 게이트

- [ ] `/api/fleet` → 새 brand 값 존재, 해당 블로그들이 brand 기준으로 분류됨
- [ ] `/api/registry` 또는 `POST /api/run-checks` → 새 블로그들의 check_results 생성, 표준 검사 정상 동작
- [ ] excluded 필터 정상: active 블로그는 fail_checks 쪽, inactive/paused는 excluded_fail_checks 쪽
- [ ] dispatcher가 새 blog_id 인식: `_load_all_blogs()` → `get_blog_config(blog_id)` → site_path 반환

#### STOP 조건

- (a) **기존 블로그 재분류** — 기존 YAML 레코드의 field 수정 포함 시 즉시 STOP (🔴 비가역)
- (b) **brand명 충돌** — `_detect_brand()` 결과가 기존 brand와 중복 → 중단, 파일명 변경
- (c) **dispatcher 매핑 누락** — 새 pipeline이 dispatcher에서 처리 못 해 발행·DB 기록 실패 가능성 → 중단, 매핑 추가 또는 승인
- (d) **baseline 흔들림** — 기존 블로그의 check_results/excluded가 의도치 않게 변동
- (e) **검사 반쪽 상태** — 일부 check만 돌고 일부 안 돔 (예: M체크는 maintenance_status 조건상 초기엔 의도적 미실행이나, R체크조차 안 돌면 문제)

#### 비가역 주의

- **기존 blog의 brand/pipeline/status/field 변경 = 🔴 별도 웨이브·명시 승인.** 이 런북은 신규 추가만 다룸. 기존 레코드 수정은 파괴적 작업 프로토콜(사전 카운트→백업→스케줄러 정지→실행→사후 대조) 적용 대상.

---

### D.3 공통 프로토콜

**백업 (매 등록 전):**
```bash
git tag pre-onboard-{blog_id 또는 brand}-{YYYYMMDD}
cp ops_dashboard/ops.db ops_dashboard/ops.db.bak_onboard_{YYYYMMDD}
```
- 코드 변경 전: git tag
- DB 변경 전: ops.db 백업

**스케줄러 정지 (DB 대량 변경 시):**
- launchd 스케줄러 정지 확인 전에는 DB 대량 UPDATE/INSERT 금지.
- 현재 scheduler.py는 계속 실행 중(PID 78295). `sync_blog_lifecycle()`는 단일 INSERT/UPDATE라 스케줄러 정지 불필요하나, 여러 블로그를 한 트랜잭션으로 대량 갱신하는 경우는 정지.

**화면 반영 (매 등록 후):**
```bash
# 신규 블로그 검사 실행 → 화면 즉시 갱신
curl -s -X POST -u "${OPS_USER}:${OPS_PASSWORD}" "http://localhost:5060/api/run-checks?blog_id={blog_id}"
# 또는 전체 (기존 블로그 영향 감안)
curl -s -X POST -u "${OPS_USER}:${OPS_PASSWORD}" http://localhost:5060/api/run-checks
```
- 반영 확인: `/api/attention`·`/api/registry`·`/blog/{blog_id}` 페이지에서 새 blog_id의 검사 결과 확인.

**로그:**
- `logs/destructive_YYYY-MM-DD.log`에 한 줄 append: `[시각] 신규 블로그/brand 온보딩: blog_id={id}, brand={brand}, pipeline={pipeline}, status={status}, baseline증가=+{추정행수}행`
- `.planning/worklog/WL-{YYYYMMDD}-onboarding-{blog_id}.md` 작성 (커밋 포함 시 필수).

---

### D.4 매뉴얼 시뮬레이션 증명 (실제 등록 없이)

**가상 입력:** blog_id=`test-hugo`, brand=`cuap`(기존 YAML에 추가 가정), pipeline=`curation`, domain=`test.informationhot.kr`, theme=`blowfish`, site_path=`/Users/twinssn/Projects/cuap/test-hugo`, status=`active`, daily_quota=`5`.

#### 필요 입력 체크

| 입력 | 값 | 충족? |
|------|-----|------|
| blog_id | test-hugo | ✅ |
| brand | cuap (cuap.yaml에 추가) | ✅ |
| pipeline | curation | ✅ |
| domain | test.informationhot.kr | ✅ (기존 도메인과 중복 아님 가정) |
| theme | blowfish | ✅ |
| site_path | /Users/twinssn/Projects/cuap/test-hugo | ✅ (실존은 미확인 — B등급 지점) |
| status | active | ✅ |
| daily_quota | 5 | ✅ |

→ **STOP-1 통과** (필수 입력 전부 있음). site_path 실존 여부는 실행 시점에 확인 — 레시피 범위 내.

#### 등록 순서 계획 (생성)

1. 대상 파일: `config/blogs.d/cuap.yaml` — 기존 15개 엔트리 아래에 새 `- id: test-hugo` 블록 추가 (1파일, 약 20줄 추가)
2. DB 동기화: `POST /api/run-checks?blog_id=test-hugo` → 내부 `_ensure_db()` → `sync_blog_lifecycle()` → blog_lifecycle에 test-hugo 1행 INSERT
3. 검사 확인: 동일 호출로 check_results에 test-hugo × ~15 check_name 행 생성
4. dispatcher 매핑: cuap 계열이므로 `site_path`가 YAML에 명시되어 있으면 추가 매핑 불필요 (dispatcher.py:208 `_load_all_blogs()`로 충분)

예상 변경 규모: 1파일(cuap.yaml) + DB 1행 + check_results 약 15행.

#### baseline 예상 증가분

- blog_lifecycle: +1행 (total 85→86)
- check_results (run-checks 1회): +~15행 (test-hugo active 기준)
- fail_checks: test-hugo에 fail 체크가 있으면 그 건수만큼 증가. 없음(모두 pass/unknown)이면 fail_checks 변화 0.
- excluded_fail_checks: active이므로 0 (excluded로 편입 안 됨)
- standard_compliance aggregate: +1행 (test-hugo)

#### STOP 조건 대조

- (a) 허용 범위[cuap.yaml만] 준수? 예 — 1파일만 수정 계획. 통과.
- (b) blog_id 중복? test-hugo는 현재 blog_lifecycle에 없음(실데이터 85건에 없음) → 통과. 단, 기존 중복 확인은 실행 전 필수.
- (c) domain 중복? test.informationhot.kr은 현재 fleet에 없음 → 통과. 실행 전 확인 필수.
- (d) baseline 예상 외 변동? +1(blog_lifecycle) +~15(check_results) +0~N(fail_checks) → 예측 모델 범위 내. 통과.
- (e) 검사 반쪽 상태? run-checks 호출 시 R체크+M체크 전부 실행 예정 → 통과 (M체크는 maintenance_status='none'이므로 check_maintenance_checklist는 스킵되나, 이는 의도적. R체크는 정상 실행).
- (f) dispatcher 매핑 실패? cuap 계열, site_path YAML 명시 → `_load_all_blogs()`로 충분 → 통과. 단, site_path 디렉토리가 실존하지 않으면 Hugo 빌드·배포 시 실패 → 그건 이 런북 범위 밖(배포 단계 문제).

#### 결과

**STOP 조건 걸리지 않음. 계획 안전.** 단, (b) blog_id 중복·(c) domain 중복·(f) site_path 실존은 실행 전 확인 필수 — 확인 불가면 B등급 지점으로 멈추고 사용자에게 확인 요청.

시뮬레이션 결론: 레시피 경계 안에서 계획이 안전하게 생성되고, 애매한 지점(b/c/f)에서는 제대로 STOP함.

---

커밋: `docs(agents): Appendix D Fleet 확장(온보딩) 런북 추가 — 신규 블로그·분기 두 시나리오.

---
