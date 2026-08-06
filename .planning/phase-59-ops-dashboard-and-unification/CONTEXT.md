# Phase 59: Ops Dashboard + Blowfish 표준 단일화 + 파이프라인 통합

> 작성일: 2026-08-06
> 기반: audit_5000.md (읽기 전용 감사), ADSENSE-GUIDE.md, Blowfish-Hugo-테마-업그레이드-표준-지침서.md
> 원칙: "조용한 실패 없음" — 모든 검사에 detail + evidence 필수, 확인 불가는 UNKNOWN + 사유

---

## 0. 이 페이즈의 두 가지 목표

### Part 1: Ops Dashboard 구축
"무엇이 왜 고장났고, 언제 멈췄고, 표준에서 얼마나 벗어났고, 어떻게 조치하는가"를
사람과 에이전트가 모바일/웹 어디서든 파악하는 대시보드.

### Part 2: 구조 단일화
(1) Blowfish 표준 서브테마를 단일 소스로 고정하여 git 레포/로컬 용량 최소화
(2) 7갈래로 갈라진 분기를 단일 표준 경로로 수렴

---

## 1. 참조 표준 문서 (유일한 진실)

### 1-1. ADSENSE-GUIDE.md (issue-techpawz-hugo 기반)
- 섹션 2: `showTableOfContents = false` 필수 (true면 광고 전체 unfilled)
- 섹션 3-1: hugo.toml `[params.advertisement]` adsense/topSlot/inArticleSlot 정의
- 섹션 3-2: extend-head.html — adsbygoogle.js 즉시 로드, site.Params 사용
- 섹션 3-3: extend_head.html — GA4 + 모바일 보정 CSS
- 섹션 3-4: adsense/top.html — overflow:hidden;min-height:100px 래퍼, push div 밖
- 섹션 3-5: adsense/in-article.html — fluid+in-article 포맷 (auto 금지), push div 밖
- 섹션 3-6: single.html — H2 분할 인젝션, prose 래퍼 유지, Description(lead) 제거
- 섹션 3-7: baseof.html — 커스텀 오버라이드 금지
- 섹션 3-8: custom.css — unfilled 공간제거, 다크모드, min-height
- 섹션 8: 금기사항 10개 (mobile-sticky.html 사용 금지 등)

### 1-2. Blowfish-Hugo-테마-업그레이드-표준-지침서.md v1.2
- 섹션 1: 허용 오버라이드 파일 목록 5종만
- 섹션 3.1: hugo.toml 필수 설정
- 섹션 3.2~3.8: 각 파일 표준 코드
- 섹션 7: 체크리스트 11항목
- 섹션 8: 금기사항 9개

---

## 2. 표준 규칙 변환 (0단계 산출물)

두 문서의 체크리스트/금기사항을 기계 검사 규칙으로 변환:

| rule_id | 출처 | 검사 대상 | 검사 방법 | 심각도 |
|---------|------|----------|----------|--------|
| R01 | ADSENSE §2, 지침서 §3.1 | hugo.toml / params.toml | `showTableOfContents` 값 = false | CRITICAL |
| R02 | ADSENSE §3-1, 지침서 §3.1 | hugo.toml | `[params.advertisement]` adsense/topSlot/inArticleSlot 존재 | CRITICAL |
| R03 | ADSENSE §3-2, 지침서 §3.2 | extend-head.html | adsbygoogle.js site.Params 사용 (하드코딩 금지) | CRITICAL |
| R04 | 지침서 §3.3 | extend_head.html | GA4 + 모바일 보정 CSS 존재 | MAJOR |
| R05 | ADSENSE §3-4, 지침서 §3.4 | adsense/top.html | overflow:hidden;min-height:100px 래퍼 + push div 밖 | MAJOR |
| R06 | ADSENSE §3-5, 지침서 §3.5 | adsense/in-article.html | fluid+in-article 포맷 (auto 금지) + push div 밖 | CRITICAL |
| R07 | ADSENSE §3-6, 지침서 §3.6 | single.html | H2 분할 인젝션 로직 존재 + prose 래퍼 유지 | MAJOR |
| R08 | ADSENSE §8-8, 지침서 §2.3 | single.html | Description(lead) 제거됨 | MAJOR |
| R09 | ADSENSE §8-9, 지침서 §3.7 | baseof.html | 커스텀 오버라이드 없음 (테마 기본 사용) | MAJOR |
| R10 | ADSENSE §3-8, 지침서 §3.8 | custom.css | unfilled 공간제거 + 다크모드 + min-height 규칙 | MAJOR |
| R11 | ADSENSE §8-3, 지침서 §8 | layouts/ | mobile-sticky.html 미사용 | MAJOR |
| R12 | 지침서 §1 | layouts/ | 허용 파일 외 오버라이드 없음 | MAJOR |

---

## 3. Ops Dashboard 요구사항

### 3-1. 데이터 모델 (SQLite: ops.db)

**테이블 4개:**
- `blog_lifecycle`: blog_id(PK), brand, config_status, lifecycle_status, pause_reason, paused_at, days_since_last_publish, consecutive_failures, theme, pipeline_path, domain, cf_project, site_path, quality_grade, domain_health, standard_compliance, notes, updated_at
- `known_issues`: issue_id(PK), blog_ids, category, symptom, recorded_date, gsd_status, auto_detectable, detection_method, resolution_status, current_detection, notes, updated_at
- `standard_rules`: rule_id(PK), source, target, detection_method, severity, description
- `check_results`: id(PK), blog_id, check_name, status(pass/fail/unknown), detail, evidence_url, checked_at

**YAML sync 함수:** config/blogs.d/*.yaml → blog_lifecycle 자동 동기화

### 3-2. GSD 이슈 추출 (이미 완료)

52건 추출됨 (db.py SEED_ISSUES에 포함):
- P01~P24 (Phase 58): 자동 감지 가능 17건
- Q1~Q4 (Phase 55): 수동 확인 4건
- QA-01~QA-06 (감사): 수동 확인 6건
- STRUCT-01~STRUCT-06 (감사): 자동 감지 가능 5건
- T-04, T-07, T-14, T-16 (해결됨): 자동 감지 가능 4건
- INC-01, INC-03, INC-04 (해결됨): 자동 감지 가능 3건

자동 감지 가능: 35건 (67%), 수동: 17건 (33%)

### 3-3. 헬스체크 엔진 (플러그인 구조)

**독립 함수 registry, blog_id → {status, detail, evidence_url}**

(A) 운영 헬스체크:
- `freshness`: 마지막 성공 발행 후 경과일 vs 계열 예상 주기 → stale 탐지
- `cjk_leak`: 최근 발행 글 제목/본문 CJK/타언어 혼입 정규식
- `title_body_match`: 제목-본문 지역명/숫자 일관성
- `render_health`: 도메인 HTTP + 대표글 썸네일/og:image 200 + adsbygoogle.js 로드
- `definition_consistency`: YAML vs dispatcher 대조 (flights/flight류)

(B) 표준 준수 검사 (standard_rules 기반):
- 각 rule_id를 blog별로 실제 검사 → pass/fail + detail
- `gsd_crosscheck`: known_issues auto_detectable ↔ check_results 대조

### 3-4. 웹 UI + JSON API

Flask, 포트 5060, 반응형 (모바일 카드 뷰)

**사람용 페이지:**
- `/` : 함대 요약 (계열×상태 매트릭스, 가동률, stale 수, 미해결 issue 수, 표준위반 blog 수) + "주의 필요" 섹션
- `/blog/<id>` : 상세 (운영 헬스 + 표준 준수 + known_issues + 발행이력 + 조치 명령어)
- `/issues` : known_issues 목록 (gsd_status × current_detection 매트릭스)
- `/standards` : standard_rules + 계열별 준수율 매트릭스

**에이전트용 JSON:**
- `GET /api/fleet`, `/api/attention`, `/api/issues`, `/api/standards`

**인증:** Basic Auth 또는 Cloudflare Access

### 3-5. 원격 접근 (Cloudflare Tunnel)
- cloudflared named tunnel로 고정 hostname 연결
- 인증 필수 (ops 데이터에 도메인/설정정보 포함)

### 3-6. 알림 연결
- 기존 텔레그램 알림에 대시보드 상세 링크 삽입
- 표준 준수 검사가 신규 위반 발견 시 텔레그램 알림 발송

---

## 4. Blowfish 표준 단일화 (Part 1)

### 4-1. 현재 상태 (감사 결과)
- Blowfish: 대부분의 블로그
- PaperMod: hotissue-hugo (CAP 계열 1개)
- Congo: stock-hugo (STAP 계열 1개)

### 4-2. 목표
- Blowfish 본체: git submodule 또는 Hugo Modules로 참조 (각 레포에 테마 전체 복제본 없음)
- 표준 오버라이드: 공유 소스 1곳에서 관리, 각 블로그가 참조/동기화
- 효과 측정: 적용 전/후 레포 용량, 중복 파일 수

### 4-3. 허용 오버라이드 파일 (지침서 §1)
1. `layouts/_default/single.html`
2. `layouts/partials/extend-head.html`
3. `layouts/partials/extend_head.html`
4. `layouts/partials/adsense/*.html`
5. `assets/css/custom.css`

### 4-4. 작업 범위
- Phase 52 Wave 1~4에서 35개 블로그 extend-head.html 수정 완료
- 나머지: 테마 submodule 전환, 공유 소스 구조 구축, PaperMod/Congo → Blowfish 마이그레이션

---

## 5. 파이프라인 분기 단일화 (Part 2)

### 5-1. 감사에서 드러난 7갈래 분기

| 단계 | CUAP | CAP | TAP | RAP | SEAP | STAP | ETAP |
|------|------|-----|-----|-----|------|------|------|
| 진입점 | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher |
| 토픽 수집 | DB 키워드 | DB topics | API fetcher | DB keywords | DB services | 외부 DB | DB topics |
| LLM 생성 | ai_writer.generate() | ai_writer.generate_car() | ai_writer via writer | rap/writer.py 자체 | senior/writer.py 자체 | STAP 자체 | ai_writer via writer |
| 품질 검증 | title_gate+content_gate | validate_body+title_similar | source_id/제목/시군구 중복 | assert_korean+normalize_table+numeric_guard | assert_korean | record_quality only | quality_guard+post_processor |
| Hugo 변환 | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | STAP 자체 | 각 *_pipeline.py 자체 (30+ 중복) |
| 테마 | Blowfish | Blowfish/PaperMod | Blowfish | Blowfish | Blowfish | Blowfish/Congo | Blowfish |
| 배포 | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | ETAP 자체 |

### 5-2. 최우선 통합 항목
1. **ETAP _write_hugo_post() 30+ 중복 제거** → shared/hugo_writer.py로 수렴 (36개 블로그 영향)
2. **ETAP 배포 경로 통일** → dispatcher 중앙으로
3. **flights-hugo/flight-hugo 이름 불일치 해소**
4. **publisher.py vs deploy.py CLOUDFLARE_API_TOKEN 처리 통일**
5. **테마 3종 → Blowfish 1종**

### 5-3. 안전 절차
- 브랜치 분리 + 리팩토링 전 상태 백업(태그/커밋)
- 각 변경은 소수 블로그에 먼저 적용 → ops 대시보드 표준검사·render_health 재실행 → 회귀 0 확인
- 한 번에 전체 적용 금지 (staged rollout)
- "없앨 것/합칠 것" 목록+근거 제시 → 사용자 승인 후에만 삭제

---

## 6. 검증 기준

### 6-1. Ops Dashboard
- [ ] 실제 1회 실행하여 CUAP stale, senior 썸네일, CJK 릭, 표준 위반 최소 1건이 "주의 필요"에 뜨는지 확인
- [ ] 85개 블로그 전수 → blog_lifecycle 테이블 동기화 확인
- [ ] 52건 이슈 → known_issues 테이블 시드 확인
- [ ] 12건 표준 규칙 → standard_rules 테이블 등록 확인
- [ ] Flask UI 모바일 반응형 확인
- [ ] JSON API 응답 구조 확인

### 6-2. Blowfish 단일화
- [ ] 적용 전/후 레포 용량 수치 기록
- [ ] 중복 테마 파일 수 0 확인
- [ ] 모든 Blowfish 블로그 Hugo 빌드 0 에러

### 6-3. 파이프라인 통합
- [ ] ETAP _write_hugo_post() 중복 0건 확인
- [ ] dispatcher.py에서 ETAP 배포 경로 통일 확인
- [ ] flights-hugo/flight-hugo 이름 일치 확인
- [ ] publisher.py CLOUDFLARE_API_TOKEN 제거 확인
- [ ] 테마 3종 → 1종 확인

---

## 7. 잔존 위험

1. **ETAP _write_hugo_post() 통합 시 회귀 위험:** 36개 블로그에 영향, 테스트 필수
2. **publisher.py 수정 시:** 기존 호출 코드 영향 확인 필요
3. **테마 변경 시:** frontmatter 생성 로직 변경, Hugo 빌드 영향
4. **프롬프트 경로 변경 시:** 기존 프롬프트 파일 형식 호환성 확인 필요
5. **도메인 75개 미확인:** HTTP 전수 확인 필요
6. **Blogger 블로그 3개:** 파이프라인 미정의, 수동 관리

---

## 8. GSD 문서 업데이트 필요

- STATE.md에 Phase 59 등록
- ROADMAP.md에 Phase 59 항목 추가
- Quick Tasks Completed에 ops_dashboard 관련 기록
