# STAP 분기 표준화 스펙 (2026-08-23)

> 브랜치: track-c-stap-seap-standardization · 참조: pet-hugo(CUAP 골든 스탠다드), RAP 표준화 선례(2026-08-23)

## 1. 범위

config/blogs.d/stap.yaml 소속 6개 Hugo 블로그 (전원 pipeline=stock, blowfish, active):
finance(stock.landing 아님—금리·예적금 비교), dividend, etf, ipo, sector, stock.
site_path=/Users/twinssn/Projects/STAP/{id}, 각 사이트 독립 git repo(main).
senior-blogger 등 Blogger 플랫폼은 제외.

## 2. PHASE_0 이슈 목록

| ID | 이슈 | 영향 |
|---|---|---|
| S1 | GA4 미동작 4곳(finance G-VJVSEKLVXT, dividend G-LCZKTDERF7, etf G-VY6QY49KTZ, ipo G-SWJF30GPJ8): gtag config가 underscore 사장 파일에 고립, 하이픈 extend-head엔 로더만 | 수집 0 |
| S2 | sector-hugo '정상'이었으나 실제 config 없음(조사 오판 정정) | 수집 0 |
| S3 | stock-hugo params.googleAnalytics=G-79ZXPZZ262 vs extend-head G-KKDB1NXKJG — 이중추적 의심 | 빌드로 판정 |
| S4 | H2-GUARD 미등록 위반 다수(fail_unique 781종) | 서브제목 bold 강등 |
| S5 | 설정 3중 혼재(루트 hugo.toml+hugo.yaml+config/_default) — dividend/etf/ipo/sector/stock은 config/_default 채택 | 유지보수 혼선 |
| S6 | bak 클러터(224/72/43/46/139/15개) | 저장소 비대 |
| S7 | topSlot==inArticleSlot 동일 슬롯 재사용(3368359041, stock만 5841226790) | 슬롯 경고 가능 |

## 3. 표준 결정

- **GA4**: extend-head.html(hyphen) 완전 스니펫 하드코딩(로더+config), per-blog 기존 ID 유지. params/services 경로 금지 — blowfish는 Config.Services만 읽으며 params.googleAnalytics는 무효임을 빌드 산출물로 실증(S3 종결: G-79ZXPZZ262 미주입 확인).
- **H2-GUARD**: _ALLOWED_H2_PATTERNS에 STAP 카테고리 정규식 추가(배당/ETF/공모가/실적/리스크/예적금 금리/의문형 마무리 등 29패턴). writer는 LLM 프롬프트 생성이라 고정 템플릿 없음 → 실발행 스캔으로 검증(781→122 unique, 잔여는 일회성 서술형 소제목으로 강등 적절).
- **설정 구조**: 현행 config/_default 채택 구조 유지(RAP 선례와 동일하게 단일화 강요하지 않음). 루트 dead 파일 삭제는 파괴적 작업으로 별도 승인 필요.
- **frontmatter**: schemas/stap/schema.yaml 확정(required [title,description,date,slug,tags], featureimage allow, ticker 허용, forbid_ellipsis false).
- **AdSense**: publisher 매핑 전원 일치(techpawz→8772, informationhot→6677) 현행 유지.

## 4. Phase별 결과 요약

- PHASE_2: finance/dividend/etf/ipo(+sector 정정) extend-head에 config 추가, 빌드 7/7 PASS, loader=1/config=1/ID 단일 ×6(stock 포함) 검증.
- PHASE_3: frontmatter 필수키 스캔 420표본 100% 충족(featureimage 누락은 allow라 위반 아님), nested 구조 전원 확인.
- PHASE_4: load_schema 8/8 성공, check_results 8개 행 존재(2026-08-23 09:06 자동 검사).

## 5. 잔존 위험

S5/S6/S7 문서화만(범위 밖·파괴적). underscore 사장 partial 5곳 미삭제. 배포 전까지 수정은 라이브 미반영.
