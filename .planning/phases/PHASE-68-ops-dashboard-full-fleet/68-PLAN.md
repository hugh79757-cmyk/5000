---
phase: 68
title: "Ops Dashboard — 전 5000 파이프라인 블로그 반영 + 진화 이력 표시"
research: skip
---

# Phase 68: Ops Dashboard — 전 5000 파이프라인 블로그 반영 + 진화 이력 표시

**목표:** Ops Dashboard가 cuap/seap/stap 3개만이 아니라 5000 파이프라인 전체(약 83개 블로그)를 반영하고, 에이전트가 API로 확인·조작할 수 있게 한다. "대시보드가 어떻게 진화됐는지" 한눈에 볼 수 있는 진화 이력 표시 포함.

**배경:** Phase 59에서 대시보드 최초 구축, Phase 62에서 C01~C08 체크 통합, Phase 64에서 규칙 체계 진화. 현재 DB에 cap(8)/etap(36)/rap(5)/tap(8)이 보이지 않는 문제 + pipeline 컬럼 부재로 에이전트가 "계열별 상태"를 볼 수 없는 문제.

**제약:** 기존 기능 보존. `_ensure_db()`·`seed_*`는 `INSERT OR IGNORE`로 중복 방지 이미 됨. YAML 파서 한계 확인이 선행 필요.

**참고:** 이 Phase는 Phase 59의 후속 확장 작업. Phase 59가 "첫 구축"이라면 68은 "전체 파이프라인 반영 + 진화 이력 + 에이전트 조작"으로 확장.

---

## 부록 A — 감사 결과 (2026-08-08 실행, 진단 전용)

Phase 68 "규격 측정·통일" 사전 감사. 4개 규격의 대시보드 측정 현황 파악. 코드 수정·배포·push 없음.

### 감사 1 — 대시보드 커버리지 매핑

| 규격 | 측정 | 부분 측정 | 미측정 |
|------|------|------|------|
| (a) 썸네일 생성 방식 일관성 | □ | □ | **✅ 미측정** |
| (b) R2 버킷·키 패턴 통일 | □ | □ | **✅ 미측정** |
| (c) 애드센스 형식 (ADSENSE-GUIDE.md) | □ | **✅ R02, R06** | □ |
| (d) Blowfish 표준지침 v1.2 | □ | **✅ R01~R12(일부)** | □ |

### 감사 2 — 측정 신뢰도

- **R06 체크:** ADSENSE-GUIDE.md 규격과 **정합**. fluid+in-article 확인, auto 감지, div 밖 push 확인. R06 실패는 체크 오류가 아니라 규격 미준수.
- **R06 실패 원인 분해 (78개 블로그 실태 조사, 2026-08-08):**
  - **PASS (fluid+in-article):** 27개 — 규격 준수
  - **FAIL (auto):** 15개 — 규격 미갱신. 교체로 해소 가능
  - **파일 없음:** 36개 — in-article.html 자체 없음. 신규 생성 필요
  - **합계:** 78개
- **R02:** 섹션 존재만 검사. 세부 슬롯 값 누락 놓침 (약한 측정).

### 감사 3 — 미측정 규격 지표화 설계 (코드 없이 설계만)

- **THUMBNAIL-01:** frontmatter의 featureimage 값을 R2 URL vs Coupeang CDN vs 외부 URL vs 없음으로 분류. R2 URL인 경우 키 패턴 검사 (표준: `thumbnails/{site_id}/{slug}.webp`). per-blog 지표: R2 표준 비율.
- **R2-01:** R2 URL 파싱 → 버킷 판정 (pub-2f5c7af1c303419a933069212bc25874 → hotissue-images, pub-3f702c9170934a72bc62a5436c406aa6 → senior-images). 키 패턴 판정. 혼합 버킷 블로그 감지.
- **통제 불가 영역:** TAP, ETAP 외부 30여개, 완전 분리 블로그는 측정 제외.

### 감사 4 — 저위험·고효과 후보 선정

| 후보 | 리스크 | 효과 | 파일럿 난이도 |
|------|------|------|-------------|
| ① R06 in-article 규격화 (auto→fluid) | 낮음 — 파셜 1개 교체, 빌드·배포만, 콘텐츠 무변경 | 중 — R06 통과 블로그 증가, 규격 통일 | 낮음 |
| ② 썸네일 통합 (중앙 생성기) | 높음 — 파이프라인 3종 변경, R2 키 변경, frontmatter 대량 수정 | 중 | 높음 |
| ③ R2 키·버킷 통일 | 중 — frontmatter R2 URL 변경, 재배포 | 중 — 지표 2종 확보 | 중간 |
| ④ Blowfish 표준 감사·정비 | 높음 — 80여개 블로그, 복합 | 중-높음 | 높음 |

**최우선 파일럿 추천:** ① R06 in-article 규격화 — 저위험·측정가능·고효과.

### R06 파일럿 A 결과 (health-hugo, 2026-08-08)

- **git tag:** pre-r06-pilot-a-2026-08-08
- **교체:** in-article.html auto → fluid+in-article (ADSENSE-GUIDE.md §3-5 표준)
- **Hugo 빌드:** 0 에러, 1093 pages
- **wrangler 배포:** 259 files, Success (Version ID: 2b03c355)
- **라이브 검증:** HTTP 200, in-article 광고 3개 모두 fluid+in-article 확인 (top.html은 auto가 표준상 정상)
- **대시보드 R06:** `check_standard_compliance(conn, 'health-hugo')` → pass, failed_rules: 0
- **게이트 4종:** 빌드 O / 배포 O / 라이브 fluid+in-article O / 대시보드 R06 PASS O → **전부 통과**

### 파일럿 A 확대 계획 (14개 블로그, 2배치)

- **대상:** appliance-hugo, baby-hugo, fitness-hugo, interior-hugo, laptop-hugo, pet-hugo, kitchen-hugo, beauty-hugo, camping-hugo, massage-hugo, car-hugo, homeappliance-hugo, golf-hugo, bike-hugo (14개)
- **백업 태그:** pre-r06-rollout-2026-08-08
- **배치 1 (파일럿 재현 검증용, 3개):** appliance-hugo, baby-hugo, fitness-hugo
- **배치 2 (배치 1 통과 후, 11개):** 나머지 11개
- **공통 안전 규칙:**
  - 각 블로그 배포 직전 in-article.html 실제 auto 재확인. 이미 fluid+in-article이거나 파일 없으면 스킵
  - 스케줄러 PID 78295/auto-triage 03:00 KST와 배포 시각 충돌 확인
  - health-hugo 동일 표준 파셜만 사용, 블로그별 임의 변형 금지
- **파일없음 36개(ETAP):** 파일럿 B 별도 트랙. 이번 턴 착수 안 함.
- **push 금지, wrangler 배포는 대상 블로그당 1회만.**

---

## 부록 B — 리서치 결과 (2026-08-08, 파일럿 A 확대 사전 조사)

### B-1. 14개 확대 대상 실태 확인

| 구분 | 개수 | 내용 |
|------|------|------|
| auto → 교체 필요 | 13개 | appliance-hugo 제외한 CUAP 13개 전부 |
| 이미 규격 준수 (스킵) | 1개 | appliance-hugo — 이전 작업으로 이미 PASS |
| 파일 없음 | 0개 | 14개 모두 in-article.html 존재 |
| YAML 미등록 | 0개 | 14개 모두 YAML에 등록됨 |

**핵심 발견:** appliance-hugo가 이미 fluid+in-article인 이유는 이전 세션에서 15개 CUAP 블로그 대상 작업이 있었을 가능성. 확인 필요.

### B-2. R06 체크 함수 실제 코드 (`ops_dashboard/checks/standard.py:339-358`)

```python
def _check_r06(site: Path) -> tuple[bool, str]:
    in_article = site / "layouts/partials/adsense/in-article.html"
    if not in_article.exists():
        return True, "No adsense/in-article.html (not applicable)"  # 파일 없으면 pass
    content = _read_file_safe(in_article)
    has_fluid = "fluid" in content              # 단순 substring
    has_in_article = "in-article" in content    # 단순 substring
    has_auto = re.search(r'data-ad-format\s*=\s*"auto"', content)  # regex
    if has_fluid and has_in_article and not has_auto:
        return True, "in-article.html: fluid+in-article format, no auto"
```

**함의:**
- 파일 없으면 pass → 36개 ETAP 블로그는 R06에서 "pass"로 나옴 (체크 안 함)
- substring 매칭이라 "fluid"가 다른 맥락에서 매칭될 가능성은 낮음
- `check_standard_compliance(conn, blog_id)` 호출 시 `_find_hugo_root(blog_row)`로 site 경로 찾음 → DB에 blog_lifecycle 있어야 체크 가능

### B-3. THUMBNAIL-01/R2-01 지표화 구체화 (설계 수준)

```python
# THUMBNAIL-01: frontmatter에서 featureimage 파싱 → R2/Coupang/external/none 분류
# R2-01: R2 URL → 버킷+키 패턴 판정 (hotissue-images/senior-images/unknown)
# 실제 구현 시: yaml.safe_load(frontmatter) → meta.get('featureimage') → 패턴 매칭
```

---

## Task 68.1 — YAML 파서 확인 + 전체 블로그 DB 동기화

**목표:** `sync_blog_lifecycle()`가 cap/etap/rap/tap YAML을 제대로 파싱하는지 확인하고, 안 되면 파서 수정 후 전체 83개 블로그를 `blog_lifecycle`에 반영.

**실행:**
1. `ops_dashboard/db.py`의 `_parse_yaml_file()`이 cap/yaml, etap/yaml, rap/yaml, tap/yaml을 파싱 못하는 원인 확인
2. 원인별 수정:
   - YAML 구조 차이(예: tap의 `blogger_blog_id`, `blog_id_env` 등) → 파서가 지원하도록 확장
   - 파일명 기반 brand 감지(`_detect_brand`)는 이미 작동 중 — brand 누락이 아니라 파싱 누락이면 파서 수정
3. `sync_blog_lifecycle()` 재실행 → 전체 블로그 `blog_lifecycle`에 반영
4. 검증: `SELECT DISTINCT brand FROM blog_lifecycle` → cap/cuap/etap/rap/seap/stap/tap + manual 모두 나와야 함

**검증:**
- [ ] `blog_lifecycle`에 8개 brand 모두 존재
- [ ] blog 수 약 83개 (ETAP 36 + CUAP 15 + STAP 6 + CAP 8 + RAP 5 + TAP 8 + SEAP 2 + manual 1)
- [ ] 각 blog에 `config_status` (active/inactive/paused) 정확히 반영

**산출물:** 없음 (DB 수정만). STATE.md에 결과 기록.

---

## 부록 C — 추가 리서치 결과 (2026-08-08)

### C-1. appliance-hugo 이미 PASS 원인

git log 확인 결과, appliance-hugo의 in-article.html은 2026-07-22 commit 24be963 "fix(single.html): pass page context"에서 설정됨. commit 7d437d3 "fix: activate AdSense auto ads"와 함께 AdSense가 활성화됐고, 당시 already fluid+in-article format이었던 것으로 보임 (v1.2 표준 발행일 2026-07-30 이전이지만 내용상 일치). → 스킵 확정.

### C-2. ETAP 36개 파일없음 블로그 실태

36개 모두 `layouts/partials/` 디렉토리는 존재하나 `adsense/` 서브디렉토리가 없음. 파일럿 B 시:
1. `layouts/partials/adsense/` 디렉토리 생성
2. 표준 in-article.html 생성
3. Hugo 빌드 → 배포 → R06 확인

ETAP 블로그는 5000 외부 파이프라인(etap)이지만 Hugo 사이트 자체는 5000이 build/deploy 관여. in-article.html 생성은 5000 통제 범위 내.

### C-3. 대시보드 check_standard_compliance 동작 확인

`check_standard_compliance(conn, 'health-hugo')` 호출 시:
1. `get_blog_detail(conn, blog_id)` → blog_lifecycle에서 blog 정보 조회
2. `_find_hugo_root(blog_row)` → site 경로 결정
3. STANDARD_RULES의 각 rule_id에 대해 `_CHECK_FUNCTIONS[rule_id](site)` 호출
4. R06은 `_check_r06(site)` → in-article.html 검사
5. 결과: pass/fail + failures 리스트

**DB 반영:** check_standard_compliance는 결과를 DB에 기록하지 않음 (호출자가 기록해야 함). 실제 체크 결과는 별도 체크 실행 모듈에서 DB insert.

---

## Task 68.2 — pipeline 컬럼 추가 + YAML pipeline 값 동기화

**목표:** 에이전트가 "계열별 상태"를 파이프라인 단위로 볼 수 있도록 `blog_lifecycle`에 `pipeline` 컬럼 추가, YAML의 `pipeline` 값을 동기화.

**실행:**
1. `db.py`의 `init_db()` + `_alter_columns()`에 `pipeline TEXT DEFAULT ''` 추가
2. `sync_blog_lifecycle()`의 UPDATE/INSERT에 `pipeline` 값 포함
3. `_parse_yaml_file()`이 YAML의 `pipeline:` 키를 파싱하도록 확인
4. API `/api/fleet` 응답에 `pipeline` 필드 포함 확인
5. 에이전트 조작: `/api/fleet` GET → pipeline별 필터링은 클라이언트 측에서 (또는 API에 `?pipeline=xxx` 추가 검토)

**검증:**
- [ ] `blog_lifecycle`에 `pipeline` 컬럼 존재
- [ ] 모든 블로그에 pipeline 값 채워짐 (car/curation/etap/rap/senior/stock/travel)
- [ ] `/api/fleet` 응답에 pipeline 포함

**산출물:** `db.py` 수정 커밋, STATE.md에 결과 기록.

---

## Task 68.3 — 대시보드 진화 이력 표시 (UI)

**목표:** "대시보드가 어떻게 진화됐는지" 한눈에 볼 수 있도록 Phase 59 → 62 → 64 → 68 흐름을 UI에 버전 지표로 표시.

**실행:**
1. `app.py`의 인덱스 페이지에 "대시보드 버전 이력" 섹션 추가:
   - Phase 59 (2026-08-06): 초기 구축 — Flask UI + JSON API + 7개 체크 모듈
   - Phase 62 (2026-08-07): C01~C08 콘텐츠 무결성 체크 통합 + preflight 게이트
   - Phase 64 (2026-08-07): 규칙 체계 진화 — C05→P 이동, 네임스페이스 분리, S01/S04 severity 확정, Task 6 체크리스트
   - Phase 68 (현재): 전 파이프라인 블로그 반영 + pipeline 컬럼 + 에이전트 조작 + 진화 이력
2. 버전별 "추가된 기능"을 아이콘/태그로 표시 (예: ✓ API, ✓ 체크, ✓ 규칙)
3. `/api/readiness` 응답에 `dashboard_version` 필드 추가 (현재 버전: "68")

**검증:**
- [ ] 인덱스 페이지에 버전 이력 섹션 표시
- [ ] 각 버전별 주요 기능 태그 표시
- [ ] `/api/readiness`에 `dashboard_version` 포함

**산출물:** `app.py` 수정 커밋, `templates/index.html` 수정, STATE.md에 결과 기록.

---

## Task 68.4 — 에이전트 API 조작 강화 검토

**목표:** 에이전트가 대시보드를 더 효율적으로 조작할 수 있도록 기존 API 검토 + 필요 시 개선.

**실행:**
1. 기존 API 검토:
   - `POST /api/run-checks?blog_id=` — 단일 블로그 체크 실행 (전체 지정 방법 확인)
   - `POST /api/maintenance/status` — 정비 상태 변경
   - `POST /api/maintenance/checklist` — 정비 체크리스트 실행
2. 필요 개선 검토 (선택적 — 전면 수정이 아니라 필요 최소한):
   - 전체 블로그 한 번에 체크 실행 시 응답 시간 — 배치 처리 또는 async 고려?
   - 계열별(brand) 필터 체크 실행 옵션 추가? (`?brand=cuap`)
   - 체크 결과의 `check_results` 데이터를 에이전트가 쉽게 소비할 수 있는 형태인지 확인
3. **전면 수정 금지** — 기존 API로 충분하면 수정하지 않고 문서만 정리

**검증:**
- [ ] 에이전트가 `/api/run-checks`로 단일 블로그 체크 실행 가능 확인
- [ ] 전체 블로그 체크 실행에 문제 없는지 (응답 시간, 타임아웃)
- [ ] 필요 개선 사항 목록 문서화 (실제 수정 여부는 별도 결정)

**산출물:** 검토 결과 메모 (db.py/app.py 수정 필요할 수도, 안 할 수도 있음).

---

## Task 68.5 — 통합 검증

**목표:** Phase 68 전체가 의도대로 동작하는지 확인.

**실행:**
1. API 호출로 전체 블로그 목록 확인:
   ```
   GET /api/fleet → brand 8종, pipeline 7종 모두 포함
   ```
2. 특정 계열(예: cap) 블로그만 필터해서 상태 확인
3. 특정 블로그(예: compare-hugo)에 체크 실행 → `check_results`에 기록
4. 대시보드 UI에서 "대시보드 진화 이력" 표시 확인
5. `/api/readiness` 응답에 dashboard_version 포함 확인

**검증:**
- [ ] `GET /api/fleet` → 8개 brand, pipeline 정보 포함, 약 83개 블로그
- [ ] `POST /api/run-checks?blog_id=compare-hugo` → check_results 기록
- [ ] 인덱스 페이지 버전 이력 표시
- [ ] 대시보드 진화 이력이 "한눈에" 이해되는 수준

**산출물:** VERIFICATION.md (검증 결과 기록)

---

## 파스 차단기

- Task 68.1에서 YAML 파서가 cap/etap/rap/tap을 전혀 파싱 못하는 구조적 문제면 → 파서 전면 수정 필요할 수 있음. 이 경우 Task 분할 재검토.
- `sync_blog_lifecycle()`가 이미 전체를 파싱하고 있는데 DB 조회 쿼리 문제였다면 → Task 68.1은 쿼리 확인으로 단축.

---

## 실행 순서

1. **68.1 먼저** — DB에 전체 블로그가 있어야 이후 작업이 의미 있음
2. **68.2** — pipeline 컬럼은 68.1과 병행 가능 (같은 db.py 수정)
3. **68.3** — UI 작업은 DB 수정 후 (데이터가 있어야 진화 이력도 의미 있음)
4. **68.4** — API 검토는 68.1/68.2 이후에 (실제 데이터로 테스트 가능)
5. **68.5** — 마지막에 통합 검증
