# STAP 콘텐츠 시스템 운영 규칙 (Content System Rules)

> 목적: STAP(finance/stock/dividend/etf/sector/ipo) 콘텐츠 발행 시스템의 운영 규칙을 문서화하여,
> 향후 블로그 재활성화 시 finance-hugo에서 겪은 시행착오(제목 중복·발행 실패·배포 인증 오류)를 반복하지 않는다.
>
> 기준: 2026-08-05 finance-hugo DB 기반 상품 다양화 + 프로덕션 실발행 검증 완료 시점.
> 모든 "대응 코드 위치"는 grep으로 실제 존재를 확인한 파일·함수명이며, 존재하지 않는 항목은 `미구현(TODO)`로 표기했다.

---

## 규칙 1 — 데이터 무결성 (Data Integrity)

**(a) 규칙 한 줄 요약**
원천 데이터(finlife API 수집 결과)가 없는 주제는 생성 금지, 계산값은 함수 결과만 주입(`calc_after_tax()`),
발행 전 논리 불변식 검증(세후이자 < 세전이자)을 통과해야 발행한다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- 실발행 검증에서 본문의 세후 수치가 "예금 80만 세전 → 12.32만 세금 → 67.68만 세후"로 정합해야 하는데,
  계산이 LLM에 맡겨지면 소수점·세율 오류가 발생한다. 실제로 프롬프트 샘플(`writer.py:634, 641`)에
  `35만 - 5.39만 = 29.61만 원`, `36.89만 - 5.68만 = 31.21만 원` 등 하드코딩된 예시가 있어,
  LLM이 이 수치를 그대로 날조 재사용할 위험이 확인되었다.
- 세후 < 세전 불변식이 깨지면(예: 세금이 음수 계산) 독자에게 잘못된 수령액을 노출하는 수익·신뢰 손상 사고가 된다.
- 원천 데이터(금리) 없이 생성하면 "날조 수치" 블로그가 되어 SEO 품질 저하 + 금융 정보 신뢰성 문제가 된다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| 세후 계산 단일 함수 | `pipelines/stock/writer.py:254` `calc_after_tax(principal, annual_rate, term_months, rate_type, monthly_deposit)` |
| 세율 상수 | `pipelines/stock/writer.py:251` `TAX_RATE = 0.154` |
| 계산 예시 프롬프트 (수치 하드코딩 위험 구간) | `pipelines/stock/writer.py:629-644` `FINANCE_CALC_EXAMPLE` |
| 원천 데이터 조회 (금리 상품) | `pipelines/stock/writer.py:98-116` `_regenerate_title_from_data()` 내 `finance_rates` SELECT |
| 상품 후보 조회 | `pipelines/stock/writer.py:406-424` `_get_diverse_products()` 내 SELECT (finlife 수집 DB `finance_rates`) |
| 데이터 수집 (finlife API) | `scripts/collect_finance_rates.py` (retry + 에러 로깅, `logger.warning` line 135, 144) |
| 세후이자 < 세전이자 불변식 검증 | **미구현(TODO)** — `calc_after_tax`는 `interest_pretax`/`interest_posttax`를 반환하지만(283-284행), 발행 전 `interest_posttax < interest_pretax`를 assert하는 게이트가 없음 |

---

## 규칙 2 — 파싱 계약 (Parsing Contract)

**(a) 규칙 한 줄 요약**
LLM 출력 포맷(TITLE:/CATEGORY:/TAGS:/DESC:/BODY:)을 강제하고, 포맷 미준수 시 마크다운 폴백을 구현한다.
조용한 폴백은 금지하고 반드시 사유를 로깅한다. fail-closed(고정 기본값으로 통과)는 금지한다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- LLM이 프롬프트를 무시하고 순수 마크다운을 반환하는 경우가 있다. 태그 파서만 있으면 `title=""`, `body=""`로
  조용히 실패하거나, 고정 기본값으로 넘어가면 "빈 글/깨진 글"이 발행된다.
- `_parse_response`는 `BODY:` 마커가 없으면 **첫 H1/H2 헤더를 제목으로, 나머지를 본문으로** 폴백한다
  (`writer.py:1099-1123`). 이 폴백은 문서화된 계약이며, 폴백 사용 시 사유 로깅이 필요하다.
- 태그 파서가 "조용한 실패"로 끝나면 (예: body가 공백 문자열로 남아도 게이트 없이 발행) —
  생성 성공 ≠ 유효 콘텐츠라는 규칙 5와 맞물려, 파싱 실패가 바로 발행 실패/깨진 글 사고로 이어진다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| 태그 파서 + 마크다운 폴백 | `pipelines/stock/writer.py:1063` `_parse_response(content)` (폴백 블록 1099-1123) |
| 폴백 시 로깅 | `pipelines/stock/writer.py:1255` `logger.warning("[_parse_response] 재생성 실패..., 제목 유지")` |
| sector 파이프라인 유사 폴백 (마커 없음 → 전체 본문) | `pipelines/sector/writer.py:219` `logger.warning("BODY: 마커 없음 — 전체 응답을 본문으로 사용")` |
| 기타 파이프라인 파서 | `pipelines/finance/writer.py:551`, `pipelines/dividend/writer.py:228`, `pipelines/etf/writer.py:207`, `pipelines/ipo/writer.py:359`, `pipelines/sector/writer.py:195` — 각각 `_parse_response` |
| fail-closed 고정 기본값 방지 | **미구현(TODO)** — 파싱 후 `title`/`body_md` 빈 값이면 반환 실패를 강제하는 공통 게이트가 파이프라인마다 상이. stock pipeline은 `if not (article.get("title") and article.get("body_md")): return None` (`pipeline.py:311-312`)으로 방어하나, 모든 파이프라인에 동일 보장은 아님 |

---

## 규칙 3 — 중복 방지 영속화 (Dedup Persistence)

**(a) 규칙 한 줄 요약**
상품 다양화 상태는 **DB에 저장**한다(`finance_rates.last_used_at`). 제목 유사도 중복은 **DB 발행이력 기준**
(Jaccard 유사도 임계값)으로 검사하며, 메모리(set)는 프로세스 수명 내 보조 수단으로만 쓴다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- 기존에는 `LAST_USED_PRODUCTS` 세션 set과 `GENERATED_TITLES` set만 사용해,
  **프로세스가 새로 뜰 때마다(스케줄 발행마다) 상태가 초기화**되어 동일 상품(웰컴 라이킷 등)이 반복 선택됐다.
- 실발행 검증에서 이 문제를 확인: `last_used_at` 마이그레이션 후 5건 → 발행 시 +5건이 DB에 기록되고,
  다음 subprocess에서 웰컴/라이킷 상품이 제외되어 "애큐온 청년플랜" 등 새로운 상품이 선택되는 것을 검증했다.
- 메모리 set은 순서 비보장이라 "최근 N개 제외"가 정확하지 않고, 프로세스 크래시 시 소멸한다 → DB가 주 방어선이어야 한다.
- 제목 유사도는 `difflib.SequenceMatcher`(ratio >= 0.8)가 쓰이는데, 이는 Jaccard와 다른 메트릭이므로
  "DB 발행이력 기준 Jaccard 임계값"을 정식으로 도입하려면 구현이 필요하다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| DB 컬럼 (사용 이력) | `pipelines/stock/writer.py` 마이그레이션 — `finance_rates.last_used_at` (인덱스 포함) |
| DB 사용 이력 조회 | `pipelines/stock/writer.py:298` `_get_recently_used_keys(days=USED_LOOKBACK_DAYS)` |
| DB 사용 기록 | `pipelines/stock/writer.py:322` `_mark_products_used(products)` — 발행 성공 후 호출 (호출 지점 `writer.py:1058`) |
| 사용 이력 초기화 | `pipelines/stock/writer.py:349` `_reset_used_history(days=None)` |
| 조회 기간 상수 | `pipelines/stock/writer.py:295` `USED_LOOKBACK_DAYS = 7` |
| 다양화 선택 로직 | `pipelines/stock/writer.py:361` `_get_diverse_products()` — DB 배제 + 고갈 시 재사용+사유 로깅 (480-483, 502-506행) |
| 세션 메모리 (보조) | `pipelines/stock/writer.py:291-293` `LAST_USED_PRODUCTS` / `GENERATED_TITLES` |
| 제목 유사도 (현행: SequenceMatcher) | `pipelines/stock/writer.py:163,180` (ratio >= 0.8), `pipelines/stock/writer.py:1222,1228` |
| 제목 유사도 (DB 발행이력) | `shared/content_store.py:237` `title_similar_exists(blog_id, title, threshold=0.6)` — SequenceMatcher 기반, DB `content` 테이블 조회 |
| Jaccard 임계값 기반 유사도 | **미구현(TODO)** — 현재는 SequenceMatcher(0.8 / 0.6)만 존재. Jaccard 기반 판정 필요 시 신규 함수 구현 |

---

## 규칙 4 — 제목 정제 (Title Sanitization)

**(a) 규칙 한 줄 요약**
제목은 길이 제한(35자) 준수, 특수문자(괄호) 정규화(하이픈 대체), 상투구·뻔한 어미 블랙리스트 차단,
필수 검색 키워드 강제를 적용하되, **표 내부의 상품명 괄호는 보호**한다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- LLM이 `웰컴저축은행 (WELCOME) 아이사랑 적금`처럼 상품명에 괄호를 넣어 제목을 생성한다.
  제목에 괄호가 있으면 SEO 제목 규칙을 위반하고, 파일명(slug)에도 괄호가 포함되어 Hugo URL이 비정상화된다.
- 실발행에서 `sanitize_title`이 `(WELCOME)` 괄호를 `-` 하이픈으로 정규화해
  `웰컴저축은행 아이사랑 정기적금 12개월 연 8.0%`로 정제된 것을 확인했다.
- "뻔한 어미"(예: 반복 패턴)와 필수 키워드 부재(금리/예금/적금/저축/세후/우대 중 0개) 제목은
  발행을 차단해야 한다 — 미검출 시 SEO 중복·품질 저하 글이 양산된다.
- 단, 본문 **표의 상품명 괄호**(`WELCOME 아이사랑 정기적금`)는 유지해야 상품 식별이 정확하다.
  제목에서만 제거하고 본문 표는 보호하는 이중 처리(finance-hugo 실검증 완료)가 필요하다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| 제목 후처리 (괄호→하이픈, 연속공백, 35자) | `pipelines/stock/writer.py:57` `sanitize_title(title)` (괄호 제거 67-68행, 공백 정규화 66,69행) |
| 제목 규칙 검증 (괄호 금지·뻔한 어미·필수 키워드) | `pipelines/stock/writer.py:45-54` — `re.search(r"[()（）]", title)` 금지, `_TITLE_TEMPLATE_PATTERNS` 블랙리스트(47행), 키워드 리스트(51행 `금리/예금/적금/저축/세후/우대`) |
| 표 내부 상품명 괄호 보호 | **미구현(TODO)** — `sanitize_title`은 제목에만 적용되고 표 마크다운은 원문 유지되는 구조이지만, "표 내부 괄호만 제거/보호"하는 명시적 함수는 없음. 현재는 표를 건드리지 않아 자연 보호됨(별도 게이트 아님) |
| 상투구 블랙리스트 (`_TITLE_TEMPLATE_PATTERNS`) | `pipelines/stock/writer.py:47` — 패턴 정의는 파일 상단(미검증 주석: 45-49행에서 사용됨) |
| 5000 공통 제목 검증 (길이/잔여물) | `/Users/twinssn/Projects/5000/shared/validators.py:313-318` — 제목 너무 짧음/김, AI 잔여물 감지 |

---

## 규칙 5 — 검증 게이트 다층화 (Multi-layer Validation Gate)

**(a) 규칙 한 줄 요약**
생성 성공 ≠ 발행 가능. 발행 전 다항목 체크리스트(제목 길이·본문 길이·키워드 출현·원문복사 의심·빈 데이터·일일 한도 등)를
자동 실행해 pass/fail을 정량화하고, 이슈가 있으면 **draft 발행**(라이브 차단)으로 강등한다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- 실발행에서 `validate_post_extended`가 이슈를 발견하면 `_is_draft=True`로 강등해 라이브 노출을 차단하는 구조임을 확인했다
  (`stock/pipeline.py:168-170` `[Validate] N issues → draft`).
- 이 게이트가 없으면 "LLM이 생성했다"는 이유만으로 깨진 마크다운·빈 본문·날조 수치가 그대로 프로덕션에 배포된다.
- 이슈 개수(`len(_issues)`)를 로그로 남겨 **pass/fail을 정량화**하며, draft로 강등돼도 DB 기록·로그는 남아 재현 가능하다.
- 추가로 `shared/content_store.py`의 `title_similar_exists`와 결합해 제목 중복도 발행 전 게이트로 동작한다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| 발행 전 검증 (공시 경로) | `pipelines/stock/pipeline.py:151-170` — `validate_post_extended` 호출, 이슈 시 `_is_draft=True` |
| 발행 전 검증 (evergreen 경로) | `pipelines/stock/pipeline.py:319-340` — `[Validate-EG] N issues -> draft` |
| draft 강등 후 발행 | `pipelines/stock/pipeline.py:174-186` / `346-358` — `publish(is_draft=_is_draft_eg)` |
| 다항목 검증 구현체 | `/Users/twinssn/Projects/5000/shared/validators.py:672` `validate_post_extended(blog_id, title, html_content, context, pipeline)` |
| 검사 항목 (일부) | `validators.py` — 본문 부족(324행), CoT 잔여물(329행), 일일 한도(358행), 키워드 출현(393행), 원문복사 의심(400행), 빈 데이터 글(538행) |
| STAP 외부 검증 경로 | `pipelines/dividend/pipeline.py:24-29`, `pipelines/etf/pipeline.py:24-29` — `STAP_VALIDATOR_PATH` env로 외부 validator 경유 (미설정 시 validation disabled 로깅) |
| 제목 중복 게이트 | `shared/content_store.py:237` `title_similar_exists(blog_id, title, threshold=0.6)` — 사용처 `pipelines/sector/pipeline.py:137` |
| 다항목 pass/fail 정량화 리포트 | **미구현(TODO)** — 현재는 `len(_issues)`를 로그로만 남김. 발행 이력에 pass/fail 항목별 기록(예: DB 칼럼)은 없음 |

---

## 규칙 6 — 안전 배포 (Safe Deployment)

**(a) 규칙 한 줄 요약**
파일 전체 재작성 금지·라인 편집만, 커밋과 push는 분리, 비밀정보는 코드에 하드코딩하지 말고 `os.environ`에서만 참조한다.

**(b) 왜 필요한가 (finance-hugo 실사례)**
- STAP `deploy_site`(`shared/publisher.py:274`)는 wrangler subprocess를 **환경변수를 그대로 상속**해 실행한다.
  agent 세션에 `CLOUDFLARE_API_TOKEN`이 설정돼 있으면 OAuth profile(hugh79757)보다 env token이 우선 적용되어
  **실제로 첫 배포가 인증 오류로 실패**했다 (`Wrangler deploy failed (project=finance-hugo)`).
  해결: `env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID`로 재배포 → 성공.
- 이는 AGENTS.md의 "wrangler 명령 시 반드시 CLOUDFLARE_API_TOKEN 해제" 규칙과 정확히 일치한다.
  5000 중앙 경로(`dispatcher.py:575-577`)는 이미 token을 pop하는 `deploy_env`를 사용하지만,
  STAP 직접 호출 경로(`_run_stap` → STAP subprocess)는 env를 명시하지 않아 **agent 세션에서 재발 위험**이 남아 있다.
- 비밀정보(API key)는 `.env`에 있고 `.env`는 심볼릭링크(STAP/.env → 5000/.env)로 공유되므로,
  코드에 절대 평문 키를 넣지 않아야 한다.

**(c) 대응 코드 위치**
| 항목 | 위치 |
|---|---|
| STAP 배포 함수 (token 미제거 → 위험) | `pipelines/stock/publisher.py:274` (STAP) `deploy_site(site_path, cf_project)` — wrangler `pages deploy` subprocess (297-310행), Hugo 빌드 `--gc --minify` (287-292행) |
| 5000 중앙 배포 (token 제거 정상) | `/Users/twinssn/Projects/5000/dispatcher.py:575-577` — `deploy_env = {k: v for k,v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}` |
| 5000 Pages/Workers 배포 공통 | `/Users/twinssn/Projects/5000/shared/publishers/deploy.py:39` `deploy_site()`, `_wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)` (78행), wrangler deploy 락 `/tmp/wrangler_deploy.lock` (43행) |
| STAP subprocess 호출 (env 미명시 → token 상속 위험) | `/Users/twinssn/Projects/5000/dispatcher.py:360-363` `_sp.run([stap_python, runner_path], ...)` — `env=` 미전달 |
| draft 글 라이브 제외 | `/Users/twinssn/Projects/STAP/shared/publisher.py:227` `if is_draft:` — Hugo 빌드에 `--buildDrafts` 없으므로 draft 글은 라이브에서 제외됨 |
| 비밀정보 env 로드 | STAP `.env`(`load_dotenv`), `/Users/twinssn/Projects/5000/.env` — `os.environ`/`os.getenv("OPENAI_MODEL")` 등 코드 전체에서 env로만 참조 (평문 키 하드코딩 없음) |
| 커밋/push 분리 | git 브랜치 `main`, 커밋은 형상관리용·push는 명시적 요청 시 (AGENTS.md 배포 규칙) |

---

## 블로그 신규 활성화 체크리스트

> stock / dividend / etf / sector / ipo 블로그를 재활성화(paused → active)할 때
> 아래 6개 규칙을 순서대로 점검한다. 각 항목은 "완료" 확인 시 근거(grep·테스트·실발행)를 함께 기록한다.

### 1. 데이터 무결성
- [ ] 재활성화할 블로그의 원천 데이터(finlife/dart/공시/ETF 시세)가 수집 DB에 존재하는가? (`collect_finance_rates.py`/`common_fetcher.py` 실행 후 `SELECT COUNT(*)` 확인)
- [ ] 금리/수익률 계산이 `calc_after_tax()` 등 단일 함수로 주입되는가? (프롬프트에 하드코딩 수치 남아있지 않은지 grep)
- [ ] 발행 전 "세후이자 < 세전이자" 불변식 게이트가 있는가? (없으면 TODO — 추가 전 라이브 발행 금지)
- [ ] `TAX_RATE = 0.154` 상수를 사용하는가?

### 2. 파싱 계약
- [ ] 해당 파이프라인의 `_parse_response`가 TITLE:/BODY: 태그 + 마크다운 폴백을 모두 처리하는가?
- [ ] 폴백(포맷 미준수) 시 사유가 `logger.warning`으로 남는가?
- [ ] 파싱 결과 title/body_md 빈 값 → 발행 중단(fail-closed)인가? (고정 기본값으로 통과되지 않는지)

### 3. 중복 방지 영속화
- [ ] `finance_rates` 등 DB에 `last_used_at` 컬럼이 있고 인덱스가 있는가?
- [ ] 발행 성공 경로에서 `_mark_products_used()`가 호출되는가? (호출 시점이 발행 확정 후인지 확인 — TODO 항목)
- [ ] `_get_diverse_products()`가 DB 이력을 배제하고, 고갈 시 사유 로깅 후 재사용하는가?
- [ ] 제목 유사도가 DB 발행이력 기반으로 동작하는가? (SequenceMatcher 0.8/0.6이 Jaccard 임계값 도입 전 최소 방어선인지 명시)

### 4. 제목 정제
- [ ] `sanitize_title()`이 제목 괄호를 하이픈으로 정규화하고 35자 제한을 준수하는가?
- [ ] 괄호 금지·뻔한 어미 블랙리스트·필수 키워드(금리/예금/적금/저축/세후/우대) 검증이 있는가?
- [ ] 본문 표 내부 상품명 괄호는 보호(원문 유지)되는가?
- [ ] 5000 `shared/validators.py`의 제목 길이/잔여물 검증을 통과하는가?

### 5. 검증 게이트 다층화
- [ ] 발행 전 `validate_post_extended` 호출이 파이프라인에 존재하는가? (공시 경로 + evergreen 경로 모두)
- [ ] 이슈 발생 시 `is_draft=True` 강등으로 라이브를 차단하는가?
- [ ] 이슈 개수가 `logger.warning`으로 정량화되어 남는가?
- [ ] `title_similar_exists` 제목 중복 게이트가 발행 전에 동작하는가?

### 6. 안전 배포
- [ ] `dispatcher.py`를 통한 배포인가? (wrangler 직접 실행 금지)
- [ ] 배포 subprocess에 `CLOUDFLARE_API_TOKEN`이 전달되지 않는가? (STAP `_run_stap` 경로는 agent 세션에서 재발 위험 — 수정(TODO) 전 수동 발행 시 `env -u` 필수)
- [ ] draft 글은 Hugo `--buildDrafts` 없이 빌드되어 라이브 제외되는가?
- [ ] 비밀정보가 코드에 평문으로 없는가? (`.env` + `os.environ` 참조 확인)

### 7. 재활성화 사전 검증
- [ ] `python3 dispatcher.py {blog_id}` dry-run(또는 테스트)으로 생성 → 검증 → 발행 전까지 1회 통과하는가?
- [ ] 발행 후 라이브 URL `curl -L` HTTP 200 + 렌더링 HTML(a~f: 제목/표/세후계산/교차/FAQ/관련글) 점검했는가?
- [ ] `last_used_at`에 발행 상품이 기록되었는가? (다음 프로세스에서 제외 확인)
