# SEAP 분기 표준화 스펙 (2026-08-23)

> 브랜치: track-c-stap-seap-standardization · 참조: pet-hugo(CUAP 골든 스탠다드), RAP 표준화 선례(2026-08-23)

## 1. 범위

config/blogs.d/seap.yaml 소속 2개:
- senior-hugo(senior.informationhot.kr, pipeline=senior, /Users/twinssn/Projects/SEAP/senior-hugo) — 표준화 대상.
- senior-blogger(Blogger 플랫폼, 2.techpawz.com, 430건 활성) — **Hugo 표준화 대상 아님(예외)**.

## 2. PHASE_0 이슈 목록

| ID | 이슈 | 영향 |
|---|---|---|
| E1 | GA4 삼중 분산: extend-head 하드코딩 G-995DNX1KV8(setTimeout 7초 지연) + services.googleAnalytics.ID=G-KY522ZJ3T6 + params.googleAnalytics=G-SPW68ZGGLW(사장) | 지연 주입+ID 혼선 |
| E2 | params.advertisement topSlot 키 누락 → single.html이 top 광고 2회 호출하나 빈 슬롯 렌더 | 상단 광고 미노출 |
| E3 | hugo.yaml(toml 아님)+config/_default 부재 — 타 사이트와 상이 | 구조 비일관 |
| E4 | bak 클러터 247개 + yaml 백업 3개 | 클러터 |
| E5 | leaderboardSlot 사장 키 | 무해 |

## 3. 표준 결정

- **GA4**: extend-head.html 직접 주입만 허용(과제 지시). setTimeout 7초 지연 블록을 즉시 로더+config 표준 블록으로 교체(G-995DNX1KV8 유지). services.googleAnalytics(G-KY522ZJ3T6)는 테마 analytics/ga.html이 프로덕션에서 렌더하여 **더블 주입 확정**(빌드 산출물 loader=2/config=2) — hugo.yaml 수정은 PHASE_2 허용 범위(exteend-head+hugo_writer) 밖이라 예외 문서화. 후속 권고: 사용자 승인 후 hugo.yaml에서 services.googleAnalytics 블록 제거.
- **topSlot(E2)**: hugo.yaml(params.advertisement) 수정이 필요하나 PHASE_3 허용 범위도 extend-head+hugo_writer로 한정됨 → 예외 문서화. 후속 권고: topSlot: "1391844966" 추가.
- **frontmatter**: schemas/seap/schema.yaml 확정(required [title,description,date,slug,tags,featureimage], featureimage disallow — 최근 60표본 누락 0으로 정합).
- **구조(E3)**: hugo.yaml→config/_default 마이그레이션은 범위 밖(파일 교체=위험). 문서화만.

## 4. Phase별 결과 요약

- PHASE_2: extend-head 표준화 완료, 빌드 PASS, senior만 더블 주입(E1 후속) 외 통과.
- PHASE_3: frontmatter 필수키 100% 충족(60표본), nested 539 index.md 확인.
- PHASE_4: load_schema(senior-hugo/senior-blogger) OK, check_results 존재(2026-08-23 09:06).

## 5. 잔존 위험

E1 더블 주입(G-KY522ZJ3T6)과 E2 빈 topSlot은 사용자 승인 후 hugo.yaml 수정으로 해소 필요. E4/E5 문서화만. 배포 전까지 라이브 미반영.
