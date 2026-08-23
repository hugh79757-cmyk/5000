# RAP 분기 표준화 스펙 (2026-08-23)

> 참조 구현: pet-hugo (pet.informationhot.kr, CUAP 골든 스탠다드)
> 절차 준용: TAP/CUAP 표준화와 동일 단계 (Phase 0 인벤토리 → 스펙 → 적용 → 검증)
> 근거 문서: `/tmp/rap_phase0_inventory.md` (Phase 0 실측, 2026-08-23)

## 1. 목적·범위

- 대상 5개 블로그 (`config/blogs.d/rap.yaml`): rap-hugo(apt), rap2-hugo(apply),
  rap3-hugo(tax), rap4-hugo(rent), rap5-hugo(brand) — 전부 *.informationhot.kr
- 공통: pipeline=rap / theme=blowfish(shared-themes) / status=active /
  daily_quota=10 / Publisher ca-pub-6677996696534146(informationhot 계열 일치)
- 제약: TAP/CUAP/ETAP 기존 파일 수정 금지 · 배포 금지(로컬 빌드만) ·
  포스트 본문 수정 금지 · 외부 패키지 추가 금지 · DB 스키마 변경 금지

## 2. Phase 0 발견 이슈

| ID | 이슈 | 영향 |
|----|------|------|
| I1 | GA4 미동작 3개: rap(G-ZWGYYMYW74)/rap3(G-GENY3H27YE)/rap4(G-MBRJG4BBNS) extend-head에 gtag config 블록 없음(사장 underscore 파일에 고립). rap5(G-KFRHWF8W70)는 setTimeout 7초 지연 주입 | 방문 데이터 수집 누락 |
| I2 | H2-GUARD 위반 8건: 세금 시뮬레이션 / 절세 체크리스트 / 매수 전 체크리스트 / 단지별 전세·월세 시세 / 전세가율·깡통전세 점검 / 브랜드 프리미엄 분석 / 실거래 시세 분석 / 지역 특성 | 발행본에서 H2→strong 강등 실측됨(rap-hugo 최신글 L33/L42/L46) |
| I3 | 사장 파일 `extend_head.html`(underscore) 전원 존재 — blowfish는 hyphen만 렌더 | 혼선 유발(DEAD) |
| I4 | .bak 클러터 수백 건(rap3 454, rap4 437 등) | 빌드 영향 없음 |
| I5 | `adsense/halfpage.html` 파라미터 경로 오류(`Params.adsense.halfpageSlot`, advertisement 누락) + single.html 미호출 | 무해(사장) |
| I6 | top 광고 본문 전후 2회 호출(rap2/rap3/rap4 single.html) | 동일 슬롯 중복 노출 |
| I7 | **CUAP 표준의 params.toml googleAnalytics 방식은 무효** — pet-hugo 라이브 HTML에 GA ID 0개 실측(curl, 2026-08-23). blowfish는 `site.Config.Services.GoogleAnalytics.ID`(루트 설정)만 읽고 params를 읽지 않음 | CUAP 표준 문서 정정 필요(별도 과제) |

## 3. RAP 표준 결정

### 3.1 GA4 — extend-head.html 완전 스니펫 단일 주입 (rap2 패턴 채택)

CUAP param 방식(I7)과 **다르게** 결정. 근거:
- blowfish 테마 analytics/ga.html은 Config.Services.GoogleAnalytics.ID만 읽음
- params 방식은 골든 스탠다드인 pet-hugo에서조차 라이브 미작동 실측
- rap2-hugo의 하드코딩 스니펫은 라이브 동작 확인된 유일 패턴

표준 스니펫 구조(hyphen `extend-head.html`):
1. `<meta name="twitter:card" content="summary_large_image">`
2. adsense async 로더(`site.Params.advertisement.adsense` 참조 — 하드코딩 금지)
3. gtag loader + `gtag('config', 'G-{블로그 고유 ID}')` 즉시 주입(setTimeout 금지)

measurement_id는 블로그별 기존 ID 유지(통합 없음):
G-ZWGYYMYW74 / G-T02JYWS566 / G-GENY3H27YE / G-MBRJG4BBNS / G-KFRHWF8W70

### 3.2 hugo.toml — 최상위 단일 파일 유지

config/_default 전환(pet-hugo 구조)은 기능적으로 동등한 대공사라 불필요.
PHASE_3에서 실질 불일치만 확인 후 무변경 또는 최소 정규화.

### 3.3 frontmatter — 현행 유지

5개 전원 일치: title/date/draft:false/description/slug/categories/tags/featureimage(R2 webp).
`schemas/rap/schema.yaml`(2026-08-22 작성, 표본 40×2 근거)와 일치 — 스키마 신설 불필요,
기존 파일을 확정안으로 사용(PHASE_4에서 load_schema 5개 성공으로 검증).

### 3.4 H2-GUARD — 6패턴 추가 (additive)

`shared/publishers/hugo_writer.py _ALLOWED_H2_PATTERNS`에 추가(순서 무관, re.search 부분일치):
체크리스트(일반) / 전세 / 월세 / 프리미엄 / 실거래 / 특성 / 시뮬레이션 —
8건 위반 전부 커버하는 최소 세트. shared 파일이라 TAP/CUAP/ETAP 금지 조항 저촉 없음
(선례: CUAP '구매 전 체크리스트' 패턴 추가, 2026-08-22).

### 3.5 AdSense — 현행 유지

Publisher ID 계열 일치로 광고 정상. I5/I6는 수익 로직 변경에 해당해 본 스펙 범위 밖 —
문서화만 수행(§2), 수정은 별도 승인 과제.

### 3.6 디렉토리/사장 파일

- underscore `extend_head.html` 5개: PHASE_2에서 hyphen 파일 완성 후 PHASE_3에서 삭제
  (git 추적 파일이라 복구 가능, 콘텐츠 아님)
- .bak 클러터: 대량 삭제는 파괴적 작업 프로토콜 대상 — 본 과제에서 미처리(권고만)

## 4. Phase별 실행 계획

| Phase | 작업 | 허용 파일 |
|-------|------|----------|
| PHASE_2 | 5개 extend-head.html 표준화(GA4 config 보강·지연 제거·동일 구조) → hugo build 5개 + grep 검증 | `{blog}/layouts/partials/extend-head.html` 만 |
| PHASE_3 | hugo_writer.py H2 패턴 6종 추가 + underscore 파일 삭제 + hugo.toml 대조 확인 | 5000 shared + RAP layouts |
| PHASE_4 | load_schema(blog_id) 5개 성공 + 대시보드 연동 확인 + 최종 리포트 | 리포트만 |

## 5. 검증 기준

- [ ] hugo build 5개 전부 PASS (HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes)
- [ ] 각 public/index.html에 자기 measurement_id gtag config 존재(주입 1회)
- [ ] H2-GUARD FAIL 0건 (재구성 테스트 재실행)
- [ ] ops_dashboard schema_loader.load_schema(blog_id) 5/5 성공
- [ ] AdSense client 6677 일치 재확인
