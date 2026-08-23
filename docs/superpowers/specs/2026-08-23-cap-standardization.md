# CAP 분기 표준화 스펙 (2026-08-23)

> 브랜치: track-c-cap-standardization
> 참조 구현: pet-hugo (pet.informationhot.kr, CUAP 골든 스탠다드)
> GA4 방식: **extend-head.html 직접 gtag 주입** (params/Config.Services 방식 사용 금지)
> 절차 준용: RAP/STAP/SEAP 표준화와 동일 단계
> 근거 문서: `/tmp/cap_phase0_inventory.md` (Phase 0 실측, 2026-08-23)

## 1. 목적·범위

- 대상 8개 블로그 (`config/blogs.d/cap.yaml`, 전원 pipeline=car):
  compare-hugo / deal-hugo / ev-hugo / guide-hugo / hotissue-hugo /
  tco-hugo / rank-hugo / pick-hugo — 전원 blowfish + active.
  site_path=`/Users/twinssn/Projects/cap/{id}`, 각 사이트 독립 git(main).
- 세부:
  - compare.rotcha.kr / deal.rotcha.kr / **newcar.rotcha.kr**(ev) / guide.rotcha.kr /
    hotissue.rotcha.kr / tco.rotcha.kr / rank.informationhot.kr / pick.informationhot.kr
  - AdSense publisher ca-pub-8772455780561463 (rotcha 정보성 계열 일치)
- 제약: TAP/CUAP/ETAP/RAP/STAP/SEAP 기존 파일 수정 금지 · 배포 금지(로컬 빌드만) ·
  포스트 본문 수정 금지 · 외부 패키지 추가 금지 · DB 스키마 변경 금지 ·
  auto_collector.py 수정 금지(데이터 등록으로 자동 인식) · 실제 쿠팡 API 호출 금지

## 2. Phase 0 발견 이슈

| ID | 이슈 | 영향 |
|----|------|------|
| C1 | GA4 미동작 5곳(compare G-JZT8RM1VK9/deal G-T98CY06DDF/ev G-C1GFXL0PHD/guide G-LCPV1CWT9M/tco G-0DCV505VPR): 하이픈 extend-head엔 gtag **로더만**(config 없음), config 전체가 underscore 사장 파일에 고립 | 방문 데이터 수집 누락 |
| C2 | **hotissue GA4 전무**: 하이픈에 없음, underscore엔 placeholder `G-XXXXXXXXXX` | 수집 0 (가짜 ID) |
| C3 | rank/pick(각 G-RN5Y61PZKM/G-6GTJJ8FMD1): **setTimeout 7초 지연** 주입 | 초기 진입 데이터 누락 |
| C4 | 설정 파일 혼재: compare/deal/ev/guide/hotissue/tco는 `hugo.toml`, rank/pick은 `hugo.yaml` | 유지보수 혼선(구조 통일 범위) |
| C5 | hotissue는 `params.services.googleAnalytics` 존재 — **blowfish 무효 경로**(params 미읽음), RAP I7과 동일 | DEAD |
| C6 | underscore `extend_head.html` 전원 존재 — blowfish는 hyphen만 렌더 | 혼선 유발(DEAD) |

**hotissue GA4 실측(ga4_admin_scan_result.json)**: `G-VSNXWPLE4L`
- propertyId 520232186 / displayName "hotissue Rotcha" / defaultUri `https://hotissue.rotcha.kr`

## 3. CAP 표준 결정

### 3.1 GA4 — extend-head.html 완전 스니펫 단일 주입 (hyphen)

RAP(§3.1)와 동일한 **hardcode 스니펫**(loader + config 즉시) 주입. cavity:
1. `<meta name="twitter:card" content="summary_large_image">`
2. adsense async 로더(`site.Params.advertisement.adsense` 참조 — 하드코딩 금지)
3. gtag loader + `gtag('config', '<ID>')` 즉시(setTimeout 금지)

measurement_id per-blog 유지(통합 없음):
compare `G-JZT8RM1VK9` / deal `G-T98CY06DDF` / ev `G-C1GFXL0PHD` /
guide `G-LCPV1CWT9M` / hotissue `G-VSNXWPLE4L` / tco `G-0DCV505VPR` /
rank `G-RN5Y61PZKM` / pick `G-6GTJJ8FMD1`

### 3.2 hugo.toml — 최상위 단일 파일로 정규화

- 6개(compare/deal/ev/guide/hotissue/tco)는 이미 `hugo.toml` — 유지.
- rank/pick은 `hugo.yaml` → `hugo.toml`로 통일(RAP §3.2의 "config/_default 전환 불필요" 원칙에 부합,
  실질 구조만 일치). 기존 YAML 루트 키를 TOML로 변환하는 대공사 없이, 두 파일 공존 시 hugo 우선순위로
  충돌이 나는 경우에만 최소 정규화.

### 3.3 frontmatter — 현행 유지

8개 전원 일치: title/description/date(100%)/draft:false/slug(100%)/tags/categories/featureimage(R2 webp).
- featureimage: 활성 7/8 100%, hotissue만 59% → **선택(allow)** — `schemas/cap/schema.yaml`(2026-08-22 작성)과 일치.
- title ellipsis가 65~90% 존재 → `forbid_ellipsis=false` + `allow_suffix ["…"]` (STAP/SEAP 선례와 동일).
- 스키마 신설 불필요, 기존 `schemas/cap/schema.yaml`을 확정안으로 사용(PHASE_4에서 load_schema 8개 성공 검증).

### 3.4 H2-GUARD — CAP 패턴 추가 (additive)

`shared/publishers/hugo_writer.py _ALLOWED_H2_PATTERNS`에 추가(순서 무관, re.search 부분일치):
자동차 비교/가격/시세/유지비/TCO/가성비/가솔린/디젤/하이브리드/전기차/핫이슈/랭킹 관련.
- quick 추가 세트: `비교(정리)`, `가격`, `시세`, `유지비`, `총비용`, `가성비`,
  `선택(가이드)`, `구매 전`, `스펙 비교`, `한눈에`, `랭킹`, `순위` (이미 일부 커버됨 확인 후 gap만 추가)
- 신규 프롬프트 생성 패턴을 실발행 스캔으로 검증(pipelines/car writer H2 패턴 참조).
- shared 파일이라 TAP/CUAP 금지 조항 저촉 없음(선례: CUAP '구매 전 체크리스트', RAP '실거래/시세' 추가).

### 3.5 디렉토리/사장 파일

- underscore `extend_head.html` 8개: PHASE_2에서 hyphen 파일 완성 후 사장 처리 — 콘텐츠 아닌 템플릿이라
  PHASE_3에서 삭제 여부 결정(git 추적 파일, 복구 가능). 삭제는 파괴적 작업 범위 → 삭제하지 않고 문서화만.
- hotissue 일부 flat .md(content/posts/*.md) 혼재 — 별도 과제, 여기서 미처리.

### 3.6 DB 캐시 수집 구조 (Phase 2B)

- KEYWORD_MAP: CAP 8 blog_id 각 30~42개 쿠팡 키워드 등록 (분기별 자동차 주제 연관).
- CATEGORY_FILTERS: 8 blog_id allowed/blocked 등록.
- run_harvest.py: bestcategories `category_cycle`에 CAP 관련 분류 코드 추가 (additive).
- auto_collector: KEYWORD_MAP.items() 순회 → 신규 id 자동 인식 (수정 금지).
- products 테이블: blog_id 컬럼 없음 확인 → 스키마 변경 불요.

## 4. Phase별 실행 계획

| Phase | 작업 | 허용 파일 |
|-------|------|----------|
| PHASE_2 | 8개 extend-head.html 표준화(GA4 config 주입·hotissue 실측 ID·rank/pick 지연 제거) + HUGO_THEMESDIR 빌드 8개 + grep 검증 | `{cap}/{id}/layouts/partials/extend-head.html` 만 |
| PHASE_2B | keywords.py(KEYWORD_MAP 8 id) + pipeline.py(CATEGORY_FILTERS 8) + run_harvest.py(category 코드) | 5000 pipelines/curation 3개 |
| PHASE_3 | H2-GUARD 패턴 additive + hugo.toml 구조 대조(rank/pick 정규화) | 5000 hugo_writer.py + cap layouts |
| PHASE_4 | load_schema(blog_id) 8개 100% + check_results 연동 + 테스트 + 최종 리포트 + git commit | 리포트 + 공유 파일 |

## 5. 검증 기준

- [ ] hugo build 8개 전부 PASS (HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes)
- [ ] 각 public/index.html에 자기 measurement_id gtag config 존재(주입 1회)
- [ ] H2-GUARD FAIL 0건
- [ ] ops_dashboard schema_loader.load_schema(blog_id) 8/8 성공
- [ ] KEYWORD_MAP 8/8 ≥30키워드, CATEGORY_FILTERS 8/8 매핑
- [ ] auto_collector 모의 iteration CAP 인식
- [ ] 테스트 18 failed/130 passed 전후 동일(신규 회귀 0)
- [ ] git commit 완료 (SHA 보고)