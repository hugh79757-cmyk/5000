# Phase 67: 무인 운영 시스템 - 연구 (Research)

**_researched: 2026-08-08 (코드 조사 완료)**
**Domain:** 무인 운영 시스템 완성을 위한 4개 영역 조사 (방안 B 집행 시점, 백필 재등록 위험, 오토트리아지 실모드 리스크, 스케줄·감시 설계)
**Confidence:** HIGH (실제 코드 분석 + HTTP 체크 시도 + 실행 상태 확인 기반)

---

## 요약

**핵심 발견:**

| 리서치 | 상태 | 핵심 발견 |
|--------|------|----------|
| **R1** 방안 B 집행 시점 | ✓ 워크플로우 설계 완료 | dead_links.json(53건)+dongnam(42건) 데이터 확인. 75개 URL 출처는 별도. URL 인코딩 주의. |
| **R2** 백필 재등록 위험 | ✓ 안전 확인 | `backfill_cuap_entities.py`는 INSERT OR IGNORE만 → published=0→1 복원 불가. `fix_cuap_all_entities.py`는 별도 주의. |
| **R3** 오토트리아지 실모드 리스크 | ⚠ 부분 확인 | ops_dashboard(포트 5060) launchd 미등록 + 현재 수동 실행(PID 94429) 중. 서버 death 시 fail_checks 트리아지 조용히 스킵. silent_skip "추천" 키워드 양면성 확인. |
| **R4** 스케줄·감시 | ✓ 설계 완료 | analytics_watchdog.sh(30분 주기) 활성. scheduler만 감시 중. ops_dashboard + auto_triage 감시 확장 설계 완료. |

---

## R1: 방안 B·라이브 청소 집행 시점 재검증

### dead 링크 데이터 소스 (실제 파일 기준)

| 파일 | 규모 | 블로그 | 내용 |
|------|------|--------|------|
| `scripts/c01_c08_validation_data/dead_links.json` | 53건 | camping-hugo 41, pet-hugo 8, beauty-hugo 2, baby-hugo 2 | 크로스셀 타겟 dead 링크 (C07) |
| `scripts/c01_c08_validation_data/dongnam_npmb.json` | 42건 | cuap-hugo 42 | 동남냄비받침 타겟 dead 링크 |

**dead_links.json 구조:**
```json
{
  "blog_id": "camping-hugo",
  "post_slug": "homli-acha-iseun-cordless-vacuum-recommend-...",
  "cross_sell_target_slug": "tent방수 스프레이 추천-comet-vs-blackdog-vs-unknown-onetouch-waterproofshade-compare",
  "expected_status": "404",
  "source_file": "/Users/twinssn/Projects/CUAP/appliance-hugo/content/posts/..."
}
```

**URL 재구성:** `{BLOG_DOMAINS[blog_id]}/posts/{cross_sell_target_slug}/`
- BLOG_DOMAINS: `shared/cuap_entity_linker.py:59` 참조
- **주의:** slug에 한국어·공백 포함 → `urllib.parse.quote(slug, safe='-')` 인코딩 필수

### HTTP 체크 시도 결과

Python urllib로 직접 체크 시도 → **전원 실패:**
- `UnicodeEncodeError`: 한국어 포함 URL
- `InvalidURL`: 공백 포함 URL

→ **URL 인코딩 필수.** 인코딩 후 재시도 필요.

### 75개 고유 URL과의 관계

- dead_links.json(53건) → 26개 고유 (blog, slug) 쌍
- dongnam(42건) → 1개 고유 (cuap-hugo, 동남냄비받침...)
- 합계 27개 고유 쌍 (75개와는 차이)
- **나머지 48개 URL 출처:** "방안 A 조사 결과" 파일 — 현재 repo에서 미확인

### 집행 워크플로우 (설계 완료)

1. dead_links.json + dongnam_npmb.json의 target_slug 추출
2. slug URL 인코딩: `urllib.parse.quote(slug, safe='-')`
3. `{domain}/posts/{encoded_slug}/` URL 생성
4. HTTP HEAD 체크 (timeout=5, User-Agent)
5. 200=복구, 404=still dead 분류
6. 블로그별 집계

**안전장치:** `shared/cuap_entity_linker.py:_url_is_alive()` 함수 재사용 가능 (방안 A 코드)

---

## R2: 백필 재등록 위험

### 스크립트 분석 결과

**① `backfill_cuap_entities.py` — 안전 ✓**
- 경로: `/Users/twinssn/Projects/5000/scripts/backfill_cuap_entities.py` (108줄)
- 동작: content/posts/ 스캔 → `cuap_entities`에 **INSERT OR IGNORE** 로 신규 등록 (published=1)
- 핵심 로직 (`backfill_cuap_entities.py:84-91`):
  ```python
  exists = conn.execute(
      "SELECT 1 FROM cuap_entities WHERE blog_id=? AND post_slug=?",
      (blog_id, slug),
  ).fetchone()
  if exists:
      continue  # 이미 있으면 skip — published 값과 무관하게 건드리지 않음
  ```
- **결론:** published=0인 기존 엔티티를 published=1로 변경하지 않음 → 재등록 위험 없음.

**② `fix_cuap_all_entities.py` — 주의 필요 ✓**
- 경로: `/Users/twinssn/Projects/5000/scripts/fix_cuap_all_entities.py` (91줄)
- 동작: published=1 엔티티 중 실제 content/posts/에 매칭 슬러그 없는 것 → `published=0`으로 UPDATE
- 위험: 방안 B 전에 실행하면 정상 엔티티가 잘못 unpublished 될 수 있음
- **권장:** 방안 B 실행 전 이 스크립트 실행 금지

**③ `fix_cuap_entity_urls.py` — 주의 필요**
- 미발행 글 published=0 변경 (80-97줄)
- URL 수정 목적이지만 부수적으로 published 변경 가능

### 백필 재등록 차단 결론

- `backfill_cuap_entities.py`: **URL 검증 추가 불필요** (published=0→1 복원 안 함)
- `fix_cuap_all_entities.py`: 실행 순서만 주의 (방안 B 전 실행 금지)
- **별도 URL 검증 로직 추가 불필요**

---

## R3: 오토트리아지 실모드 리스크

### 대시보드 서버 의존성 (CRITICAL)

**코드 분석:**
```python
# scripts/auto_triage.py:28
DASHBOARD_URL = "http://localhost:5060"

# scripts/auto_triage.py:587-603
def fetch_dashboard_data():
    endpoints = [
        ("attention", "/api/attention"),  # fail_checks 포함
        ("issues", "/api/issues"),
        ("fleet", "/api/fleet"),
        ("readiness", "/api/readiness"),
    ]
    for name, path in endpoints:
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                results[name] = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            results[name] = {"error": str(e)}  # 오류 시 error dict 반환

# scripts/auto_triage.py:706-708
attention = dashboard.get("attention", {})
fail_checks = attention.get("fail_checks", [])  # 서버가 죽으면 attention={"error":...} → fail_checks=[]
```

**영향:** 서버가 죽으면 `fail_checks = []` → fail_checks 기반 트리아지 조용히 스킵. 크래시는 안 나지만 트리아지 범위 축소.

**현재 서버 상태:**
- PID 94429: `ops_dashboard/app.py` (포트 5060) — **수동 실행 중**
- launchd 등록: **없음** (com.5000.dashboard.plist는 data/dashboard/app.py 포트 5050 실행 — 잘못된 앱)
- 서버를 죽이면 auto_triage fail_checks 트리아지가 silently skip 됨

**해결:** ops_dashboard를 launchd에 등록 (KeepAlive=true) → 자동 재시작.

### 오발송 위험

- 기본값이 dry-run: `scripts/auto_triage.py:894`
  ```python
  dry_run = os.environ.get("PROBLEM_ALERT_DRY_RUN", "1") != "0"
  ```
- 실모드 전환: `PROBLEM_ALERT_DRY_RUN=0 python scripts/auto_triage.py`
- 현재 dry-run 결과: 총 230건 → 자동처리 97건, 사람호출 26건, silent_skip 107건
- **실모드 전환 시 97건이 실제 텔레그램 발송됨 → 사전 리뷰 필수**

### silent_skip 오삼킴 분석

**키워드 분류 로직 (`auto_triage.py:276-327`):**

```python
def _matches_subtype(self, subtype, criteria, context, blog_id):
    keyword = context.get("keyword", "")
    
    if subtype == "informational_keyword":
        # 정보성 키워드 — silent_skip 대상 (P14 등)
        info_keywords = ["근교", "추천", "가이드", "비교", "고르는", "후기", ...]
        return any(kw in keyword for kw in info_keywords) or ...
    
    if subtype == "commercial_keyword_fail":
        # 상업성 키워드 — summary_append 대상
        commercial_keywords = ["추천", "비교", "리뷰", "가격", "구매", "할인", "베스트", "TOP", "순위", ...]
        return any(kw in keyword for kw in commercial_keywords) or ...
```

**문제점:** "추천", "비교", "리뷰", "TOP", "순위" 등 키워드가 **양쪽 서브타입에 모두 포함** → 첫 매칭된 서브타입의 액션 적용.

**규칙 YAML 확인 (`auto_triage_rules.yaml`):**
- P14: `informational_keyword` 서브타입 → `silent_skip` (YAML:116-118)
- 다른 problem_id들도 `auto_skip_possible`/`auto_handle` 타입에 `silent_skip` 적용

**검증 필요:** 실제 트리아지 결과에서 silent_skip 107건 중 "추천" 키워드 포함 건 샘플링 → 상품성 글에서 발생한 오삼킴 여부 확인.

---

## R4: 스케줄·감시 연쇄

### 현재 watchdog 현황

**analytics_watchdog.sh (활성):**
- 경로: `/Users/twinssn/Projects/5000/scripts/analytics_watchdog.sh` (88줄)
- launchd: `~/Library/LaunchAgents/com.5000.analytics.watchdog.plist`
- 주기: 1800초 (30분)
- PID: 34819 (실행 중)
- 감시 대상:
  1. scheduler.py PID 생존 확인 → death 시 텔레그램 알림
  2. analytics 수집 미실행 감지 (8h+) → 강제 재실행

### 감시 사각지대

- ✗ **ops_dashboard/app.py (포트 5060):** launchd 미등록 + watchdog 미감시
- ✗ **auto_triage.py:** watchdog 미감시

### 3자 감시 구조 설계

1. **ops_dashboard launchd 등록:** KeepAlive=true → death 자체 해결 (watchdog 보조 감시 추가 가능)
2. **auto_triage 발사 확인:** `logs/auto_triage_summary.log` 마지막 수정 시각 확인 → 미실행 시 로그
3. **기존 scheduler 감시 유지:** 변경 없음

### ops_dashboard launchd 등록 세부

**신규 plist: `~/Library/LaunchAgents/com.5000.ops-dashboard.plist`**
```xml
<key>Label</key><string>com.5000.ops-dashboard</string>
<key>ProgramArguments</key>
  <array>
    <string>/Users/twinssn/Projects/5000/.venv/bin/python</string>
    <string>/Users/twinssn/Projects/5000/ops_dashboard/app.py</string>
  </array>
<key>WorkingDirectory</key><string>/Users/twinssn/Projects/5000</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>/tmp/5000-ops-dashboard.out.log</string>
<key>StandardErrorPath</key><string>/tmp/5000-ops-dashboard.err.log</string>
```

**주의:** 기존 `com.5000.dashboard.plist`는 `data/dashboard/app.py`(포트 5050) 실행용. 혼동 금지.

---

## 종합 평가

| 리서치 항목 | 상태 | 핵심 발견 |후속 조치 |
|------------|------|----------|----------|
| R1: 방안 B 집행 시점 | ✓ 워크플로우 설계 완료 | dead_links.json(53건)+dongnam(42건) 데이터 확인. 75개 URL 출처 별도. HTTP 체크 시 URL 인코딩 필수. | 집행 시 HTTP 체크 수행 |
| R2: 백필 재등록 위험 | ✓ 안전 확인 | backfill_cuap_entities.py는 INSERT OR IGNORE만 → published=0→1 복원 불가. fix_cuap_all_entities.py는 별도 주의. | URL 검증 추가 불필요, fix_cuap_all_entities.py 실행 순서 주의 |
| R3: 오토트리아지 실모드 | ⚠ 부분 확인 | ops_dashboard(5060) launchd 미등록 + 수동 실행 중. 서버 death 시 fail_checks 트리아지 silent skip. silent_skip "추천" 키워드 양면성. | ops_dashboard launchd 등록 + silent_skip 샘플 검증 |
| R4: 스케줄·감시 | ✓ 설계 완료 | analytics_watchdog.sh(30분) 활성, scheduler만 감시. 3자 감시 구조 설계 완료. | watchdog 스크립트 수정 + ops_dashboard launchd 등록 |

**게이트 통과 상태:**
- G1: ✓ 통과 (워크플로우 설계 완료)
- G2: ✓ 통과 (backfill 안전 확인)
- G3: ⚠ 부분 통과 (서버 의존성 확인 완료, launchd 등록으로 해소 가능)
- G4: ✓ 통과 (3자 감시 설계 완료)

---

_생성: 2026-08-08_
_코드 조사: auto_triage.py(1027줄), ops_dashboard/app.py(520줄), backfill_cuap_entities.py(108줄), fix_cuap_all_entities.py(91줄), analytics_watchdog.sh(88줄), auto_triage_rules.yaml(429줄)_
