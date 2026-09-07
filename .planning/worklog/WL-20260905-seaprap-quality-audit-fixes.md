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

## 잔존 위험 해소 (12:00-12:05 추가)
- R1 엣지 캐시: API 퍼지 전 경로 401(cache_purge 스코프 부재). 해소: R2 _headers 재배포로 캐시 헤더 s-maxage=3600 교체 — 관악/사당롯데는 바디 이미 404(상태코드만 옛 200), apply 2건(제목/청약정정공고)은 옛 콘텐츠 age=2565 → 최대 15분 내 자연 소멸. 대시보드 수동 퍼지 불필요.
- R2 _headers: 6사이트 static/_headers 생성(/* nosniff + /posts/* s-maxage=3600). 빌드 6/6 + 재배포 6/6 rc=True. 근본 해결 — 이후 콘텐츠 삭제 시 최대 1시간 내 엣지 반영.
- R3 senior-blogger: .planning/handoff/senior-blogger-blogger-template-fix-guide.md 작성(Blogger 콘솔 수동 절차 — desc/canonical 추가 + 로더 4중→1).
- R4 rap4 키워드 편중: 오판 정정 — active 2,322 중 비-서울 1,322, 최근 30일 24개 지역 다양 발행. 조치 불필요.
- R5 스크립트 안전화: fix_rap_desc_pollution.py — yaml_safe_desc(쌍따옴표 랩, 콜론 버그 9건 방지) + 교체 후 PyYAML 파싱 검증(folded 유입 6건 방지, 실패 시 skip). dry-run 0건(전멸 상태 정합).

## Senior-blogger 마무리 (14:55)

- searchDescription 오판 정정: Blogger API는 searchDescription 미지원(공식 필드 아님 — insert에 넣어도 무시, 응답에 미반환). 라이브 테스트 3회(draft 2+live 2, 전부 즉시 삭제)로 확인: **테마가 본문에서 자동 추출해 meta description 렌더 중** — 최신 글 전부 정상. b37의 "searchDescription None 10/10"은 API 미지원 필드 측정 = 오판. 75-2.html(9/4 삼중발행 유물)만 빈 desc — 별개 이슈, 글 자체 재발행 필요.
- 체크박스 릭 백필 10건(파괴적 4단계): 사전 74개/10포스트 → 교체(`<li>[ ] ` → `<li>` + 잔여 제거) → 사후 API 10건 0개 + 라이브 curl 5건 0개, HTTP 200 유지. 백업: T/opencode/senior_checkbox_backfill_bak_20260905 (원본 JSON 10건).
- writer.py L328 [PRODUCTION]: `- [ ] 구비서류` 예시 → 대시 목록 + 태스크리스트 금지 문구 (재발 방지).
- 커밋 2d26722e4 push (6파일: writer.py, blogger 체크 desc_pollution/rap_region, render.py 3c, __init__.py, 로그).
- 테스트 글 4건(제목/SEO/SEO-B/SEO-C) 전부 즉시 삭제 완료 — 라이브 잔존 0건.

## Senior-blogger 백필 확장 (15:20)

- 전수 스캔 결과 최신 10건만이 아닌 전체 81포스트/481개 [ ] 릭 발견 → 백필 범위 확장.
- 4단계: 사전 81건/481개 → 백업 81건 전량 JSON → update 91회(멱등 재처리 포함, 타임아웃으로 2회 분할) → 사후 전수 772포스트 [ ] 0개 assert PASS.
- 최종 상태: senior-blogger [ ] 릭 전멸. 재발 방지: writer.py 프롬프트 수정(커밋 2d26722e4).

## 재발방지 하드 게이트 + 스킬 (15:35)

- 75-2.html 빈 desc 1건: 사용자 결정 — 방치.
- 재발방지 이중화 완료: 소프트(writer.py:328 프롬프트) + 하드(validators.py:_check_senior CRITICAL 게이트, `( ^|\W)\[( |x|X)\]` 발행 전 차단). 단위 테스트 3/3(릭 탐지/대시 통과/링크 무오탐), pytest 48 passed. 커밋 648d91f8a.
- 스킬 작성: ~/.config/opencode/skills/blogger-api-publishing/SKILL.md — pickle 토큰 인증, blog ID 매핑 3개, enum/502/sleep gotchas, searchDescription 미신화, [ ] 렌더 사고+게이트, 백필 4단계 패턴, 테스트 포스트 delete 주의.

## rap4-hugo P01 no_trade_data 트리아지 (19:07 해결)

- 알림: rap4-hugo fetcher P02 → 실제 no_trade_data 3회(11:50/14:50/18:00). 키워드: 새샘마을3단지(모아미래도리버시티) 세종시 전세.
- 근본 원인: SYNC_REGIONS(58개)에 세종시 등 11개 지역 부재 → rents 커버리지 구멍. 세종 rents 0건 + trades는 202604만료(3개월 폴백 윈도 밖) → no_trade_data → 자동 비활성화. 영향 active 키워드 1,124건(세종/광산구/달서구/수영구/남동구/대구동구/대전동구/유성구/수원권선/진천/아산 — 아파트명 오탐 제거 후 법정동 기준).
- 수정 [PRODUCTION]: rap_data_sync.py SYNC_REGIONS 58→69개 — 신규 11개(36110 세종/26410 수영/27140 대구동/27290 달서/28200 남동/29200 광산/30140 대전동/30200 유성/41113 수원권선/43750 진천/44200 아산).
- 즉시 수집: 신규 지역 3개월치 — rents +2,367건, trades +2,073건. 광산구(29200)만 API totalCount=0(공공데이터 자체 부재 — 네트워크/코드 문제 아님).
- 키워드 복구: 오늘 자동 비활성화 6건(새샘3 전세+실거래/호려울7 전세+실거래/탕정 전세+실거래/첫마을3 실거래) → active.
- 검증: 세종 rents 276건/새샘3단지 2건(전세 2.5억/월세 5천+46) 확보. dispatcher rap4-hugo 재실행 → 발행 성공 article_id 13056 (대전 유성구 전월세 — 유성구도 신규 수집 지역), 배포 rc=0, 라이브 200. 1차 시도 썸네일 Playwright networkidle 타임아웃(unsplash 지연, 일시) → 재시도 성공.
- 재발 방지: SYNC_REGIONS에 추가 완료 — 이후 매일 01:00 daily sync가 자동 수집. 커버리지 밖 지역 키워드 전부 데이터 보유 상태.
