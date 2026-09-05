# Worklog: WL-20260905-seaprap-quality-audit-fixes

## Operation
SEAP+RAP 블로그 품질 감사(CAP 체크리스트 동일 적용) → 근본 원인 제거 + 결함 수정 + 6사이트 재배포

## Audit Findings (감사 결과)
- 광고: 7블로그 전부 ca-pub-6677996696534146 정합(informationhot 계열 규칙) ✓
- 로더 2중: 6개 Hugo 사이트(SEAP senior-hugo + RAP rap1~5) 전부 — 테마 head.html + extend-head.html 2중 선언
- senior-blogger(Blogger 플랫폼): desc/canonical 부재 + 로더 4중 — Blogger 템플릿 이슈로 수동 이월
- 제목 잘림: 7/1,910 (0.4%) — LLM 자체 32자 지시 희소 사례, 시스템 아님
- [ ] 체크박스 릭: 0건
- desc 오염: 792건(related 블록 '함께 읽으면 좋은 글' 조각이 desc로 저장) — 8/1 이전 과거 결함, 8/3 커밋 이후 재발 0
- 지역 왜곡: 관악드림타운 1건 — 근본 원인은 LLM 아닌 데이터 매핑 버그(아래)
- topSlot: senior-hugo 미정의(rap 5곳은 이미 정의 — 초기 판정 오류 정정)

## Root Cause + Fixes (근본 원인 제거)

### A. 파이프라인 게이트 (5000 repo) [PRODUCTION CODE]
- A1 지역 정합 게이트: `shared/validators.py` `_check_rap()` — keyword에서 시/군/구 추출, 본문 어디에도 없으면 CRITICAL 차단. `_PIPELINE_VALIDATORS`에 "rap" 등록.
- A2 desc 오염 게이트: `_check_rap()` — description에 '함께 읽으면'/'](/posts/' 마커 시 CRITICAL 차단.
- pipeline.py L1201-1214: validate_post_extended 전환 + _val_ctx에 description 추가.
- 관악 이중 미매칭 게이트: `pipelines/rap/pipeline.py` L1049-1050 lawd_matched 플래그 + L1077-1091 apt_kw 존재+keyword_trades 0건+lawd 미매칭 → 키워드 inactive + no_trade_data 반환. 관악드림타운 사례: find_lawd_cd 미매칭 → 랜덤 강남구 fallback → 무관 데이터로 글 작성이었음. 게이트로 원천 차단.
- 검증: 단위 테스트 5케이스 PASS(관악 왜곡 탐지/정상 통과/desc 오염 탐지/무주군 통과/관악(동아) 정상 매칭). pytest 48 passed 회귀 0.

### B. 구조 수정 (SEAP/RAP repo) [PRODUCTION CONFIG/TEMPLATE]
- B1: 6사이트 extend-head.html adsbygoogle 로더 제거(테마 head.html 자동 로드 위임) — 로더 1회 해소.
- senior-hugo hugo.yaml topSlot: "1391844966" 추가(기존 슬롯 재사용).

### C. 데이터 수정 + 폐기 [CONTENT]
- C1: 관악드림타운 글 폐기(rm) — 강남구 30건 데이터(대치동 65억)로 관악구 단지 글 작성. 지역명 교체 불가, 표 전체가 잘못된 원천. 사용자 승인 하 폐기.
- C2: desc 오염 792건 백필 — `scripts/fix_rap_desc_pollution.py`(본문 첫 문단 리드 120자로 재생성). 스크립트 folded scalar 버그로 rap2 6건 YAML 손상 → 개별 수리(링크 유입 라인 제거 + desc 재작성 2건). PyYAML 전수 검증 0 오류.
- CoT 릭 4건 폐기(rap2 '제목'/'청약정정공고15건', rap5 사당롯데캐슬2차/목동마에스트로) — 8/1~8/2 발행 유물(8/3 CoT 차단 커밋 이전). 래미안-원베일리는 오판 정정(정상 수식).

## Deploy (4단계 프로토콜)
- 사전 배포 ID/백업: predeploy_seaprap_20260905_103819(8파일) + 사전 ID 6개(destructive log 참조)
- 1차 재배포 6사이트: senior 11:13, rap 11:26, rap2(빌드 실패→YAML 수리), rap3/rap4 11:13-14, rap2/rap5 11:32 — 전부 rc=0
- stale public 문제: 폐기 글이 고아 HTML로 잔존(Hugo --gc 미제거) → rap/rap2/rap5 public/ rm 후 2차 재배포 3건 rc=0(11:38-39)
- 라이브 검증: 6사이트 loader=1, 오염desc=0, 폐기 글 404(pages.dev 프리뷰 ca6b0b7f.rap-hugo.pages.dev 확인)

## 미해결 — 사용자 액션 필요
- Cloudflare 엣지 캐시: informationhot.kr zone 캐시 퍼지 API 401(OAuth 토큰 권한 부족). 폐기 글 3~5개 URL이 s-maxage=604800 엣지 캐시로 최대 7일 200 서빙 가능. 대시보드 → Caching → Purge by URL 수동 퍼지 필요: (1) https://apt.informationhot.kr/posts/2026년-03월-관악드림타운-부동산-시세-분석/ (2) https://brand.informationhot.kr/posts/사당롯데캐슬2차-실거래가-분석-동작구-브랜드-아파트-가치/ (3) https://brand.informationhot.kr/posts/목동-롯데캐슬-마에스트로-양천구-브랜드-가치-분석/ (+ apply 2건 제목/청약정정공고 — pages.dev에서는 404, apt/brand와 동일 캐시 패턴이므로 함께 퍼지 권장)
- 근본 개선 후보(별도 결정): `_headers`로 /posts/* s-maxage 단축(7일→1시간)

## Logs
- 5000/logs/destructive_2026-09-05.log 5행(백필/폐기 2건/재배포 2건/캐시퍼지 401)

## 커밋 대상 (5000 repo)
- shared/validators.py(_check_rap), pipelines/rap/pipeline.py(게이트 2종), scripts/fix_rap_desc_pollution.py(신규 — 재사용 시 PyYAML 검증 필수 주석 포함)
- RAP/SEAP repo 사이트 파일은 .gitignore — 배포가 유일 반영 수단
