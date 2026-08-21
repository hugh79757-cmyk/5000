# ETAP Quality Overhaul — Single Spec (S0~S3)  (2026-08-21, Track C timebox)

> **상태**: DRAFT — 90분 타임박스 20~50분 architectural 산출, 승인 대기
> **범위**: ETAP 34 active 단일 문서. S0 P0 복구, S1 렌더 일괄, S2 본문 재설계(파일럿), S3 데이터 최소. airports paused 유지, car/curation 금지.
> **입력**: spike-full.md(§1-6) + etap-auto-branches-discovery.md 정정(SG-A 13/10, dead31 제거, pipeline fallback)
> **성공 판정**: 내일(08-22) 새벽 발행 michelin 파일럿 글이 오늘 글보다 체류시간 측정 가능하게 낫다. 라이브 URL로 검증.

---

## S0 — P0 발행 파이프라인 복구 (draft_detected + 95일 침묵, 오늘 밤)

### S0-1 문제 정의 (라이브 근거)

- `logs/scheduler.log:331114/203/307` — 08-21 07:34/39/45 세 회 `airports-hugo stage=draft_detected → CATCHUP 1/3,2/3,3/3 → consecutive 1/3 정체`. 동일 패턴이 08-21 08:xx bus/ferry/watersports/dining에도 발생. 원인: `quality_guard.postprocess_content()`의 is_draft 7게이트 중 `word_count<400`·`H2<3`·`benefit_connection_issues`(etap_writing_rules) 발동. 0허위(`Airlines 0 / Destinations 0`, `Route Count 0`)는 `\$0` 게이트(`quality_guard:381`)나 empty 섹션 정규식(434-438)에 안 잡혀 08-16 lille 가이드는 `draft:false`로 통과 → 허위 라이브 잔존.
- sitemap 공통 갭 05-06→08-10(95~108일) = (a) 05-06 이후 미발행 휴지기(로그 rotate로 원인 미규명) + (b) 08-10 `cd1accf02` 전 fleet `status:paused`(etap 40) + 08-12 `c268f0b81` 복구. deals만 106일째 미복구(별도 topic/원소스 고갈).
- 두 원인은 별개: 전역 paused ≠ draft 게이트. paused 해제만으로는 draft 연쇄 재발.

### S0-2 설계 결정 (수정 금지 기간 제외, 조사 결과 반영)

- **신규 게이트 1 — 빈 데이터 허위 단정 차단** (`pipelines/etap/quality_guard.py:postprocess_content` 확장, ~15줄):
  - 트리거: 본문에 `0`/`no|none|not operating` + `Airlines|Destinations|Route Count|Airports Served` 등 count 필드가 `0`/`—`/`empty`로 렌더될 때를 정규식으로 탐지. 예: `\|.*(Airlines|Destinations|Route Count).*\|\s*0\s*\|`, `there are no airlines.*operating`, `Route Count 0`.
  - 동작: `is_draft=True`, `issues+= "[CRITICAL] empty-data hallucination: count=0 rendered as fact"`, 텔레그램 CRITICAL. 데이터 소스 빈 배열이면 본문에서 사실 단정 대신 **명시적 "데이터 없음" 카드**로 치환하거나 H2 자체를 생략(후술 S2 구조와 연동). **파일**: `pipelines/etap/quality_guard.py` 단일 지점, 모든 ETAP `*_pipeline.py`가 경유하므로 분기별 수정 불필요.
  - **LaTeX 게이트** 동시: `\$\rightarrow\$|\\rightarrow` 탐지 → `Auto-replaced: $\rightarrow$ → →` 로 치환 (airlines 누수 해소).

- **benefit gate 완화 검토** — `shared/etap_writing_rules.py:benefit_connection_issues()`가 현재 `is_draft=True`로 CATCHUP 실패 다수 유발. 단기 완화: benefit 0개 시 `is_draft=False` + `[WARNING]` 로 다운그레이드, 본문 후처리기에서 부족 시 템플릿 문장 1줄 보강. 장기: S2에서 정보 밀도 설계로 자연 충족.

- **CATCHUP 리셋 정책** — `scheduler`의 `consecutive failures 1/3`은 `draft_detected`에서도 카운트되나 08-21 airports는 3회 모두 1/3에 머무름(리셋 로직 있음). 유지하되 실패 원인별 카운트 분리 검토는 다음 세션 — 오늘은 게이트로 재발 차단이 우선.

- **deals 단독 진단** — `pipelines/etap/deals_pipeline.py:99 draft_detected` + sitemap 05-06 정지. `topic_manager.pick_topic_by_id("deals_topics"?)` 잔여 카운트 + `data/travel-en.db` `omio`/`aviasales` 원소스 0 여부 확인을 spike §6 후속 태스크로 분리. 오늘은 S0 밖.

- **검증**: `python dispatcher.py michelin-hugo --dry?` 대신 실제 파이프라인 1회 수동 실행 후 `logs/scheduler.log`에 `stage=draft_detected` 0건, `consecutive` 미증가, `content/posts/{slug}/index.md`에 `draft:false` + 0허위 문장 0건. 라이브는 다음 날 sitemap lastmod 갱신으로 확인.

- **롤백**: `quality_guard.py` 단일 파일 revert.

- **미규명 한계**: 05-06→08-10 96일 중 05-06 이전 단절 계기는 로그 소실로 미규명(§6 기재). 재발 시 `scheduler.log` rotate 정책 변경 안건 별도.

---

## S1 — 템플릿/렌더 레이어 일괄 수정 (P1, 오늘 밤·전 블로그, 파일럿 선행)

> 원칙: 한 곳에서 고치면 34 블로그에 전파. Blowfish 기반 `layouts/partials/` + `hugo.toml`이 단일 소스여야 함. 현재 ETAP 34개는 `ETAP/{blog}-hugo/hugo.toml`가 개별이지만 `shared-themes/blowfish`를 공유하므로 `layouts/partials/head.html` 유사 분기는 `ETAP` 루트의 공통 partial 또는 `shared-themes` 오버라이드가 정답. 파일 위치 확정 전 grep으로 실체 확인 후 단일 지점 패치.

### S1-1 GA4 per-blog 분리 + G-DEFAULT 제거 (측정 가능성의 전제 — 최우선)

- **현재**: 라이브 head에 `<script src="...gtag/js?id=G-DEFAULT"></script>` + `gtag("config","G-N4Q99745QT")`가 전 도메인 동일, adsbygoogle 로더도 동일 `ca-pub-877...` 2회. `config/blogs.d/etap.yaml`에는 `ga4_id` 있어도 렌더 미사용. 결과: 블로그별 engagement 귀속 불가, S2 체류시간 비교 자체가 불가능.
- **결정**:
  1. `G-DEFAULT` 플레이스홀더 로드 제거 — `layouts/partials/head.html` 또는 `extend_head.html`에서 `G-DEFAULT` 하드코딩 삭제.
  2. `hugo.toml`의 `services.googleAnalytics.id` 또는 `params.analytics.googleSiteVerificationTag`를 `config/blogs.d/etap.yaml`의 `ga4_id`와 빌드 시 동기화하는 스크립트(또는 `hugo --source` 전 `yq` 주입) 도입. 각 도메인 head가 자기 `G-XXXX`만 1회 로드.
  3. 미보유 블로그는 `G-` 자체를 미출력(빈 GA 로드 금지) — 노이즈 방지.
- **대상 파일 후보** (실측 후 확정, 1곳): `shared-themes/blowfish/layouts/partials/head.html` 또는 `ETAP/{blog}-hugo/layouts/partials/head.html` 오버라이드, `ETAP/{blog}-hugo/hugo.toml`. **grep으로 단일 소스 확정 후 패치** — 34개 개별 수정 금지.
- **검증(라이브 기준)**: 34 도메인 각 `curl -s https://{domain}/posts/{slug}/ | grep -o 'G-[A-Z0-9]*'` 가 해당 `ga4_map.csv`/`etap.yaml` 값과 1:1 일치, `G-DEFAULT` 0건, `gtag` 스크립트 1회. 실패 시 롤백.
- **AdSense 채널 분리**: 계정 분리가 아니라 `ca-pub-877...` 내 블로그별 채널/광고단위(`data-ad-slot`)로 귀속. 가능 여부 확인 후 `layouts/partials/adsense-*.html`에 per-blog slot 매핑 추가. 불가 시 spec에 대안(동일 슬롯 + URL 채널 보고서) 기재.

### S1-2 AdSense 로더 중복 제거

- **현재**: `adsbygoogle.js?client=ca-pub-877...` 2회 로드 (head 중복 include).
- **결정**: `head.html`과 `baseof.html` 중 한 곳만 로드, 중복 include 가드(`if .Site.Params.adsense.client` 1회). `meta name=google-adsense-account`는 1회 유지.

### S1-3 author 귀속

- **현재**: `{"@type":"Person","name":""}` 공란.
- **결정**: `hugo.toml: [author]` 또는 `params.author`에 ETAP 공용 저자/에디터 1명 설정, JSON-LD `author.name` 채움. 글별 저자 분리는 다음 세션.

### S1-4 고지문 삽입 (FTC)

- **현재**: 34/34 sample 0건, 링크는 Viator/sjv.io 포함.
- **결정**: `layouts/partials/affiliate-disclosure.html` 신설, 본문 첫 affiliate 카드 직전에 `We may earn a commission…` 1줄 삽입. 조건: 본문에 `viator.com|sjv.io|airalo` 링크 있을 때만. CSS는 기존 `.etap-disclaimer-card` 재사용.

### S1-5 LaTeX 깨짐

- S0 게이트에서 치환하되 렌더 레이어에서도 `layouts/_default/single.html` 후처리에서 `$\rightarrow$` 잔존 시 `→` 치환 백업.

> S1 전체 검증은 라이브 렌더 기준: 각 도메인 샘플 2개씩 curl head/body grep, `G-DEFAULT` 0, `G-XXXX` 1, `adsbygoogle` 1, `author.name` non-empty, disclosure 1, `$\rightarrow$` 0.

---

## S2 — 본문 구조 재설계 (체류시간 기준, 파일럿 michelin-hugo)

> 파일럿 선정: **michelin-hugo** (시니어 추천 채택). 이유: 제휴 링크 0건이라 CTA 신설 설계 여백, 원소스 `michelin_restaurants`(별점/Bib/가격대/요리종류/도시) 구조화로 정보 밀도 변수 풍부, airports 0허위 리스크 없음. 검증은 라이브 URL.

### S2-0 원소스 필드 전수 (정보 밀도 입력)

- **michelin 원소스 스키마 조사** (`data/travel-en.db: michelin_restaurants`): `name, award(3/2/1 Stars/Bib Gourmand/Selected), cuisine, price_tier(€€€), city, country, address, phone?, url?`. 현재 writer는 `name/award/cuisine`만 쓰고 `price_tier/city/country/address` 버림 추정 → 목록화 후 구조에 투입.
- **다른 ETAP 원소스** (다음 확산 시): `viator_tours(deep_link, price, duration, rating, review_count, category, image_url, product_name)`, `airalo_esim(price, data, validity, coverage)`, `omio(route, train_min_price/duration, bus… )`, `aviasales(cheapest price, airline, flight_no, date)`. 현재 버리는 필드: `duration/rating/review_count/image` 등 비교 데이터.

### S2-1 정보 배치 ( (a)(b)(c) 통합 — 스캔 가능한 구조)

- **도입부 (a) 해소**: 현재 `{{< lead >}}This guide provides…` 자기소개 2문장 → **의도에 즉답**. 첫 뷰포트에 3줄 요약 박스(Answer Box) 배치: `요약 테이블(Quick Facts) → 즉답 2문장 → CTA 1`. 예: michelin라면 `📍 Glasgow — 7 starred, 4 Bib — price €€ / cuisine: French, Scottish` 테이블 + `The standout is X (1 Star, French) — book 2 weeks ahead` 즉답. H2 전에 이탈 방지.
  - **대상 파일**: `pipelines/etap/michelin_writer.py: generate_michelin_guide()` 도입부 템플릿 + `layouts/partials/michelin-summary.html`(신설) 또는 writer가 마크다운 테이블로 직접 생성. S1 렌더와 중복 없게 writer가 마크다운 소유.

- **밀도 (b)**: 길이가 아니라 **비교 가능한 사실 수**. 파일럿 목표: 동일 도시 내 식당 간 비교 테이블 1개(award/price/cuisine 3열, N=5~7) + **선택 근거 3문장**(왜 여기 갔는지: 가격대/접근성/메뉴). 원소스에서 버리는 `price_tier`를 테이블에 필수 노출.

- **구조 (c)**: `요약 테이블(Answer) → 상세(식당별 H3, 각 120~180단어, award/시그니처 메뉴 1개) → 비교(테이블) → FAQ(3문항)`. H2는 `## At a Glance`, `## Where to Eat`, `## Compare`, `## FAQ` 4개 고정, writer가 강제. FAQ는 `FAQPage` JSON-LD 동시 출력(템플릿에서 `hugo.toml` 없이 본문 FAQ 마커 파싱). 스캔: 요약→상세→비교→FAQ 순서가 michelin 비교 의사결정에 적합(근거: 식당 선택은 비교가 체류시간을 늘림).

### S2-2 CTA/광고/내부링크/신뢰 ( (d)(e)(f)(g) 수치화)

- **(d) CTA 위치/수**: michelin 현재 0건 → 신설. 첫 CTA는 **요약 테이블 직후**(첫 스크롤 1회 내), 본문당 **2개**(상단 1 + 비교 테이블 후 1). 후보: Viator "food tour in {city}" 1개 + Airalo 미사용. CTA 카드 간 **최소 600px(또는 400단어) 간격**, 광고 슬롯과 CTA는 **교차 금지**(한 뷰포트에 둘 다 노출 시 CTA가 가려짐).
  - **대상**: `pipelines/etap/michelin_pipeline.py:_add_product_cards()` 신설 + `michelin_writer.py`에서 CTA 마커 삽입.

- **(e) AdSense 위치**: 현재 `ad-top / ad-leaderboard / ad-inarticle` 3슬롯, `unfilled display:none`. 재정의: **`ad-top` 제거**(첫 화면 이탈 유발) → `ad-inarticle` 1개를 **H2 두 번째 직후**로 이동, `ad-leaderboard`는 비교 테이블 후 1개. 본문 대비 광고 비중 ≤30%, 본문 상단 300px 내 광고 금지(오조작 회피, Google 정책). 슬롯 수는 2개로 축소.
  - **대상**: `layouts/partials/adsense-*.html` + `pipelines/etap/post_processor.py: insert_adsense()` 위치 로직.

- **(f) 내부링크 밀도/원칙**: 현재 `tour/flights/esim/visafree→본문 자동 링크`가 체류에 도움인지 이탈인지 미측정. 결정: **같은 ETAP 도메인 내 관련글 우선**(예: michelin → 같은 도시 michelin 다른 글), **외부 ETAP 교차는 1개 이하**, 본문 500단어당 링크 **3개 상한**. `shared/entity_linker.py: inject_internal_links()` 밀도 파라미터로 제어. 파일럿에서 링크 전수 로그 후 체류 비교.

- **(g) 신뢰 신호**: `author.name` 공란 해소(S1-3) + **데이터 출처/갱신일 명시**: 본문 하단에 `Data: Michelin Guide 2026, last verified {lastmod}` 1줄 + JSON-LD `dateModified`는 Hugo `lastmod`와 동기화(현재 sitemap lastmod와 일치하도록 `frontmatter lastmod` 갱신). 출처 표기는 writer가 주입.

### S2-3 파일럿 검증/롤백

- **검증(라이브)**: `https://michelin.techpawz.com/posts/{new-slug}/` curl로 (1) 요약 테이블 존재 (2) 비교 테이블 행 ≥5 (3) CTA 2개(viator 링크) (4) 광고 2개 위치(H2 두번째/비교 후) (5) FAQ 3문항 + FAQPage 스키마 (6) `author.name` non-empty (7) `wordCount` 900~1400, `0` 허위 0건. GA4 `G-XXXX` 단일 로드. 체류는 GA4 `engagement_rate` 다음 날 비교(어제 michelin 평균 vs 파일럿).
- **롤백**: `michelin_writer.py` + `michelin_pipeline.py` + `head.html` revert, `hugo.toml` GA ID 원복. 단일 블로그이므로 전파 없음.

---

## S3 — 데이터 원소스/DB (P3, P2에 필요한 최소만 오늘 정의)

- **빈 데이터 게이트 최소 정의**: `data/travel-en.db`의 빈 배열(예: `michelin_restaurants WHERE city=?` 0건)이 writer에 도달하면 writer가 **사실 단정 문장을 생성하지 않고** `no_result → {"success": false, "reason": "no_result"}`로 반환, `topic_manager.mark_published_by_id`로 **exhausted 처리 금지**(재시도 가능). 현재 airports는 빈 카운트를 0으로 렌더 후 draft로 차단하므로 스키마보다 writer 분기가 우선.
- **스키마 변경 금지(오늘)**: `travel-en.db` 테이블 스키마 변경, 마이그레이션, 인덱스 추가 모두 다음 세션. 오늘은 `SELECT` 필드 목록화(§S2-0)까지만.
- **원소스 조사 태스크**: `pipelines/etap/collectors/{viator,airalo,omio,aviasales}_*.py`의 link 생성부에서 실제 버리는 필드 목록을 `docs/superpowers/specs/ETAP-source-fields.md` 1페이지로 산출(다음 세션 입력).

---

## 질문 1 (6개 중 1, 한 번에 하나)

> 파일럿을 michelin으로 채택했는데, CTA를 Viator food tour로 박는 것에 대해 시니어는 Viator 귀속(`pid/mcid`)이 현재 `VIATOR_PID` 미주입으로 0건임을 이전 spike에서 확인했습니다. 파일럿에서 `VIATOR_PID` 주입을 S1에서 함께 할지, 아니면 michelin은 Viator 대신 Airalo/제휴 없는 순수 정보형으로 갈지 중 어느 쪽이 체류/수익 트레이드오프에 맞다고 보십니까? 답 없으면 **기본안: Airalo 없이 순수 정보형 1편으로 검증, Viator PID는 S1 별도 트랙**으로 문서에 남기고 진행합니다.

*파일 단일 원칙 준수: 본 spec이 유일 산출, 쪼개지 않음.*
