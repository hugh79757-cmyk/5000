# Phase 68-B: 파일럿 B 사전 리서치 — ETAP 36개 광고 삽입 경로 실태

**_researched: 2026-08-08 (코드 + 라이브 fetch 조사 완료)**
**Scope:** ETAP 36개 (adventure-hugo ~ watertours-hugo) 광고 삽입 경로 확정. 진단 전용 — 코드/DB/배포/push/git tag 변경 없음.
**Parallel:** Phase 67(dead 링크 청소 + camping/pet/beauty/baby/cuap-hugo 재배포) 실행 중. **67 대상 5개 블로그 접근 금지 준수.**
**Confidence:** HIGH (실제 소스 대조 + 5개 블로그 라이브 HTML fetch + 36개 layouts 스캔 + 생성 코드 역추적)

---

## 요약 (한 줄 결론)

> **ETAP 36개 광고는 [콘텐츠 마크다운 하드코딩 — `pipelines/etap/post_processor.py::ADSENSE_BLOCK`(본문 H2 사이 삽입, 라이브 기준 2개/글, 46~52% 위치)]에서 [auto] 노출 중, 경로 [단일 — layouts 파셜/테마/단일html 전부 미사용], 파일럿 B 성립방식은 [c — in-article.html 신규 생성 + 기존 콘텐츠 하드코딩 제거 동시], 중복위험 [있음 — 파셜만 신설하면 콘텐츠 하드코딩과 동일 위치 중복 노출], A방식(파셜 교체) [불가 — ETAP은 파셜 자체가 없어 '교체' 대상이 없음, 신설+제거가 필요], _check_r06 [로직 변경 필요·설계완료], 다음은 [방식 재검토 — 파일럿 B는 '파셜 신설'이 아니라 '콘텐츠 하드코딩 제거 + 파셜 신설' 동시 트랙으로 재정의 필요].**

---

## 조사 1 — 광고 실제 삽입 경로 확정 (대표 3개 표본)

### 표본: adventure-hugo / walking-hugo / tours-hugo

**실측 (라이브 HTML fetch):**

| 표본 | 라이브 도메인 | 인아티클 `<ins class=adsbygoogle>` | 위치 | ad-format | ad-slot | ad-client |
|------|------|------|------|------|------|------|
| adventure-hugo | adventure.techpawz.com | 2개 | 46% / 52% | `auto` | 4276065235 | ca-pub-8772455780561463 |
| walking-hugo | walking.techpawz.com | 2개 | 43% / 50% | `auto` | 4276065235 | ca-pub-8772455780561463 |
| tours-hugo | tours.techpawz.com | 2개 | 본문 중간 | `auto` | 4276065235 | ca-pub-8772455780561463 |

**라이브 헤드 로더 여부:** 3개 표본 모두 `<head>` 영역에 `adsbygoogle.js` 로더 **0건**. (즉, ETAP 광고는 헤드 로더 → `<ins>` 구조가 아니라, 콘텐츠 내부에 로더 스크립트 + `<ins>` + push 가 각각 포함된 **완결형 블록**으로 렌더됨.)

### 렌더 출처 역추적 (로컬 소스 대조)

| 후보 경로 | 존재 여부 | 판정 |
|------|------|------|
| `layouts/partials/adsense/in-article.html` | ❌ 없음 (36개 전부) | 사용 안 함 |
| `layouts/_default/single.html` 오버라이드 | ❌ 없음 | 테마 기본 사용 |
| `layouts/partials/extend-head.html` | ✅ 있음 (tpembars 스크립트 — **광고 아님**) | 사용 안 함 |
| `layouts/partials/head/custom.html` | ✅ 있음 (adsbygoogle.js 로더) | **라이브에 안 나감** (테마 head가 이 partial 호출 안 함) |
| `layouts/partials/head/head.html` | ❌ | 사용 안 함 |
| 테마(shared-themes/blowfish) adsense 파셜 | ❌ 없음 | 사용 안 함 |
| **콘텐츠 마크다운 하드코딩** | ✅ | **실제 렌더 소스 확정** |

**메커니즘 확정:**
- ETAP 글의 `content/posts/{slug}/index.md` 본문에 `ADSENSE_BLOCK`(로더+`<ins data-ad-format="auto">`+push)이 **두 번** 하드코딩되어 있음.
- 생성 주체: **`pipelines/etap/post_processor.py:186-197` `ADSENSE_BLOCK` + `insert_adsense()`(L199-219)** — 첫 번째 단락 뒤 + 두 번째 `## ` H2 뒤에 삽입.
- Hugo가 이 markdown을 그대로 `.Content`로 렌더 → 테마 `single.html`이 `{{ .Content }}`로 출력 → 광고 블록이 본문 46~52% 지점에 노출.
- `head/custom.html`의 adsbygoogle.js 로더는 테마 `shared-themes/blowfish/layouts/partials/head.html`이 호출하지 않으므로 **라이브에 렌더 안 됨** (실제 렌더는 각 콘텐츠 블록의 자체 로더 스크립트가 담당).

**왜 `adsense/` 파셜이 없는데도 광고가 나오는가:** 광고가 파셜/테마 경로가 아니라 **본문 마크다운 자체에 심어져 있기 때문**. `_check_r06`가 `layouts/partials/adsense/in-article.html` 파일 존재를 검사하는데, 이 파일이 없으므로 "파일 없음 → return True(PASS)"가 되고, 실제로는 콘텐츠 하드코딩 광고가 렌더되고 있는 상태.

---

## 조사 2 — 36개 광고 경로 단일성 + 포맷 분류

### 36개 layouts 구조 스캔 (전수)

36개 전부 **완전히 동일**한 layouts 트리:
```
layouts/partials/extend-head.html      (tpembars — 광고 아님)
layouts/partials/head/custom.html      (adsbygoogle.js 로더 — 비활성)
layouts/partials/related.html          (관련 글)
```
- `layouts/partials/adsense/` 디렉토리: **36개 전부 없음** (no-adsense)
- `layouts/_default/single.html`: **36개 전부 없음** (no-single → 테마 기본)
- 예외 1건: `nomad-hugo` — `head/custom.html` 없음(하지만 로더가 어차피 비활성이라 렌더 영향 없음). `tour-hugo` — `head/custom.html` 없음.

### 콘텐츠 하드코딩 광고 전수 스캔 (36개)

| 항목 | 값 | 일치율 |
|------|------|------|
| `data-ad-slot` | `4276065235` | 36/36 (100%) |
| `data-ad-format` | `auto` | 36/36 (100%) |
| `data-ad-client` | `ca-pub-8772455780561463` | 36/36 (100%) |
| `data-ad-layout` | **없음 (0건)** | — |
| `fluid` | **없음 (0건)** | — |
| 광고 포함 콘텐츠 파일 | 1,902개 | — |
| `<!-- ETAP -->` 블록(인아티클 광고) | 3,804개 | — |

### 판정

- **경로 단일성: 단일.** 36개 모두 콘텐츠 마크다운 하드코딩(동일 생성 코드)만 사용. 갈래 없음 → **파일럿 B "일괄 표준화" 성립 가능**.
- **포맷: 전부 `auto`, `data-ad-layout` 없음.** ADSENSE-GUIDE 표준(§3-5 `fluid` + `in-article`)과 **불일치** — 표준화 필요 대상임을 확정.

> 참고: publisher ID `ca-pub-8772455780561463`는 rotcha.kr/techpawz 계열 매핑(AGENTS.md §1)과 일치. informationhot/aikorea24 ID 아님 — 통일 규칙 위반 없음.

---

## 조사 3 — 성립 방식 판정 (중복 노출 위험 중심)

### 후보 방식 검토

| 방식 | 내용 | 중복 노출 위험 | 적용성 |
|------|------|------|------|
| **(a)** 기존 경로 제거 + in-article.html로 이전 | 콘텐츠 하드코딩 제거 + 파셜 신설 | — | 기존 경로(콘텐츠 하드코딩)를 **제거하는 전처리**가 없으면 파셜 신설만으로 중복 |
| **(b)** 기존 경로를 표준 포맷으로 직접 수정 | 콘텐츠 하드코딩을 fluid+in-article로 **직접 변경** (파일 신규생성 불필요) | 낮음 | 콘텐츠 마크다운 1,902개 파일 내 광고 블록 전부 수정 필요(대량) |
| **(c)** in-article.html 신규 + 기존 제거 동시 | 파셜 신설 **+** 콘텐츠 하드코딩 제거 동시 | 없음(동시 제거 시) | **파일럿 B 권장 방식** |

### 중복 노출 위험 판정 (핵심)

- **위험 있음.** ETAP은 현재 **콘텐츠 마크다운 하드코딩**으로 인아티클 광고가 렌더됨. 이 상태에서 단순히 `layouts/partials/adsense/in-article.html` 파셜을 만들고 `single.html` H2 분할 인젝션을 추가하면:
  - 기존 콘텐츠 하드코딩 광고 (위치 46%/52%) **+** 파셜 인젝션 광고 (같은 첫 본문/H2 위치) → **동일 페이지 내 2배 중복 노출**.
- AdSense 정책: **동일 페이지에 광고 중복 게재 위반 위험** (in-article 광고가 2중으로 렌더되면 수익 편식 + 정책 위반 소지).
- **따라서 파일럿 B는 (c) "파셜 신설 + 콘텐츠 하드코딩 제거" 동시 트랙이 필수.** 파셜만 신설하는 방식(a 단독)은 중복 노출을 유발.

### 파일럿 A(CUAP) 방식과의 비교

| 기준 | 파일럿 A (CUAP, health-hugo) | 파일럿 B (ETAP) |
|------|------|------|
| 기존 상태 | `layouts/partials/adsense/in-article.html` **이미 존재**, auto로 설정 | **파셜 자체가 없음**, 콘텐츠 하드코딩 |
| 작업 | 파셜 **내용 교체** (auto → fluid+in-article) | 파셜 **신설** + 콘텐츠 하드코딩 **제거** |
| A방식(교체) 적용 가능 여부 | ✅ | ❌ **불가** — 교체할 기존 파셜이 없음 |

**결론:** A방식(파셜 교체)은 ETAP에 **그대로 통하지 않는다**. ETAP은 파셜 교체가 아니라 **신설(c) + 기존 콘텐츠 제거**가 필요.

### 부수 고려사항 (파일럿 B 재정의 시)

1. **콘텐츠 제거 규모**: 광고 포함 1,902개 파일 × 2블록 = 3,804개 `<!-- ETAP -->` 블록 제거. 이는 `post_processor.py`의 `insert_adsense()`가 재삽입하지 않도록 **생성 코드 차단(또는 전환)** 없이는 재발.
2. **재발 방지**: `post_processor.py` `insert_adsense()`를 비활성화/표준 파셜 방식으로 전환해야 기존 1,902개 파일 수정 후 재생성되지 않음.
3. **단일html 재정의**: 파셜 신설 시 `layouts/_default/single.html` 오버라이드(Blowfish H2 분할 인젝션, ADSENSE-GUIDE §3-6)도 36개에 추가 필요 — 이는 파일럿 A의 단일html과 동일 구조.
4. **결과적으로 파일럿 B는 "단순 파셜 신설"이 아니라 "콘텐츠 하드코딩 제거 + 파셜 신설 + 생성코드 전환"의 3중 트랙**으로 스코프가 확장됨. **이 리서치의 최우선 산출물** — 방식 재검토 필요.

---

## 조사 4 — _check_r06 로직 정합성 재설계 (설계만, 코드 변경 금지)

### 현재 로직 (코드 인용) — `ops_dashboard/checks/standard.py:339-357`

```python
def _check_r06(site: Path) -> tuple[bool, str]:
    """R06: adsense/in-article.html — fluid+in-article format (no auto)."""
    in_article = site / "layouts/partials/adsense/in-article.html"
    if not in_article.exists():
        return True, "No adsense/in-article.html (not applicable)"  # 파일 없으면 pass
    ...
```

**문제 확인:** `in_article.exists()`가 False면 `return True, "not applicable"` → ETAP 36개는 `layouts/partials/adsense/`가 없으므로 **모두 PASS(오탐)**. 대시보드 R06이 실태(콘텐츠 하드코딩 auto 광고)를 반영하지 못함.

**추가 확인:** `check_standard_compliance()`(L497) → `_find_hugo_root()`(L163)는 `blog_lifecycle.site_path`를 사용. **ETAP 36개는 ops.db `blog_lifecycle`에 등록됨**(brand='etap' 36건, site_path `/Users/twinssn/Projects/ETAP/*` 전부 유효). 즉 조사 대상 36개는 이미 대시보드가 검사 가능한 대상이며, 오탐 PASS가 실제 노출됨.

### 재설계안 (설계 전용 — 파일 없음 상태를 측정가능/미준수로 전환)

**원칙:** "파일 없음 = PASS(적용 안 함)"가 아니라, **콘텐츠 하드코딩 광고 경로까지 검사**해 실제 상태를 반영한다.

```
_check_r06(site):
  1. partial = site/layouts/partials/adsense/in-article.html
  2. if partial 존재:
       → 기존 검사(fluid+in-article, no auto) 유지
  3. else (partial 없음):
       a. content_hardcoded = grep '<!-- ETAP -->' 또는 'data-ad-format="auto"'
          in site/content/** (in-article 위치 하드코딩)
       b. if content_hardcoded 감지 → return (False, "콘텐츠 하드코딩 in-article auto —
          표준 파셜 없음, 미준수/측정가능")
       c. else (광고 없음, AdSense 미사용) → return (True, "N/A — 광고 없음")
```

- **ETAP 현재 상태** (조사 2): partial 없음 + 콘텐츠 하드코딩 auto 있음 → 2a 분기에 걸려 **FAIL(측정가능)** → 대시보드가 오탐 PASS가 아니라 "표준 미준수"로 정확 표시.
- **파일럿 B 완료 후** (파셜 신설 + 콘텐츠 하드코딩 제거 + fluid+in-article): 1번 분기(partial 존재, fluid+in-article, no auto) → **정당하게 PASS**.

**연결 (파일럿 B 실행 후 R06가 정당 PASS를 주는 조건):**
1. `layouts/partials/adsense/in-article.html` 생성 (ADSENSE-GUIDE §3-5 표준: `data-ad-layout="in-article" data-ad-format="fluid"`, `site.Params.advertisement.adsense`/`inArticleSlot` 사용)
2. 콘텐츠 하드코딩 `<!-- ETAP -->` 블록 제거 (3,804개)
3. `single.html` H2 분할 인젝션 (ADSENSE-GUIDE §3-6)
4. `params.toml`에 `[advertisement] adsense / inArticleSlot` 설정 (R02 통과 조건)
5. `post_processor.py::insert_adsense()` 광고 삽입 중단(생성 코드 전환)

이 5가지가 완료되면 R06는 partial 존재 + fluid+in-article + no auto로 **PASS**, 대시보드 36개가 오탐이 아닌 실제 준수 상태로 표시됨.

**검증 제약:** 본 리서치는 진단 전용 — `_check_r06` 코드 변경은 **하지 않음**. 위는 설계안이며, 파일럿 B 실행 단계에서 구현한다.

---

## 부록 — 접근 제약 준수 확인

- Phase 67 대상 5개(camping/pet/beauty/baby/cuap-hugo): **접근/수정 없음.** (cuap-hugo는 조사 3에서 파일럿 A 기준으로만 참조, 경로 변경 없음)
- 코드/DB/배포/push/git tag 변경: **없음.**
- 라이브 fetch: 조사 1(3개) + 조사 2(0개 추가) = **3개 이내**. (조사 2는 로컬 layouts 스캔으로 수행, 제약 준수)
- 읽기 전용 SELECT 3회(ops.db blog_lifecycle / check_results / tables) — 데이터 변경 없음.

---

## 산출물 / 다음 단계

- 본 문서: `RESEARCH.md` (조사 1~4 + 한 줄 결론)
- **다음 (파일럿 B 재정의)**: 67 완결 → **68-A(파일럿 B 스코프 재검토) → 68-B(콘텐츠 제거 + 파셜 신설 + 생성코드 전환 + _check_r06 확장)** 순서로 실행 설계 요청.
- **핵심 재고 필요 항목:** 파일럿 B가 "표준 in-article.html 생성" 단독으로는 **중복 노출을 유발**하므로, 반드시 **콘텐츠 하드코딩 제거 + 생성코드 전환**을 함께 포함하도록 스코프 확장.
