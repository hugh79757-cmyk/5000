# 대시보드 오류·운영 신호 플레이북

**사용법:** 이 문서는 에이전트가 특정 `problem_id`, `reason`, `stage`, M 검사 또는 R 규칙 신호를 받았을 때 따르는 실행 표준이다. 각 행의 “수정 권한”은 로컬에서 최소 수정안을 작성할 수 있는지의 기준이며, **원격 푸시·실제 발행·배포·재발행은 별도 사람 승인**이 필요하다.

> **공통 금지:** 오류를 없애기 위해 duplicate guard·품질 게이트·검증 규칙을 끄거나, 원인 확인 없이 일괄 재발행·대량 데이터 삭제·기준 완화를 수행하지 않는다.

## 1. CRITICAL 오류

| 코드 | 신호·단계 | 먼저 확인할 증거 | 안전한 수정 방향 | 검증 | 수정 권한 |
|---|---|---|---|---|---|
<a id="p04"></a>
| **P04** | deploy_error / `post_deploy` | Wrangler 배포 로그, 대상 브랜치·프로젝트, 직전 성공 배포, 배포 락 | 빌드·배포 명령의 실제 실패 지점만 수정; 잘못된 환경변수 참조·경로를 최소 수정 | 로컬 빌드, dry run, 승인 후 대상 URL 확인 | 코드 제안 가능; 배포는 승인 |
<a id="p05"></a>
| **P05** | hugo_build_failed / `post_deploy` | Hugo 버전, themesDir, 모듈·테마 경로, 실패한 콘텐츠 파일 | 테마/경로/Front Matter 문법을 원인 파일에 한정해 수정 | Hugo build, 실패 재현 테스트 | 코드 제안 가능; 배포는 승인 |
<a id="p06"></a>
| **P06** | broken_featureimage / `post_publish` | 라이브 이미지 HTTP 상태, 콘텐츠 Front Matter, R2 객체 키·업로드 로그 | 잘못된 참조 또는 누락된 업로드만 복구; 기존 미디어를 삭제하지 않음 | URL HEAD/GET, 포스트 페이지 샘플 | 업로드·재발행은 승인 |
<a id="p07"></a>
| **P07** | cjk_leak / `post_generate` | 생성 원문, 감지 패턴, 템플릿·프롬프트, 라이브 노출 여부 | 감지기가 맞는지 샘플 확인 후 프롬프트/후처리/차단 로직 수정 | 오염·정상 fixture 모두 검사 | 코드 수정 가능; 재생성·발행은 승인 |
<a id="p08"></a>
| **P08** | llm_cot_leak / `post_generate` | 생성 원문, chain-of-thought 유사 패턴, 프롬프트, 차단 결과 | 원문 노출을 막는 후처리·프롬프트 경계 보완; 추론 본문을 저장하지 않음 | 안전·정상 fixture 테스트 | 코드 수정 가능; 재생성·발행은 승인 |
<a id="p09"></a>
| **P09** | image_url_repeat / `post_generate` | 반복 토큰 위치, 이미지 선택·삽입기, 동일 URL 정책 | URL 토큰 분리·중복 제거 로직을 수정하되 이미지 정책을 우회하지 않음 | 반복·정상 URL fixture 검사 | 코드 수정 가능; 재발행은 승인 |
<a id="p25"></a>
| **P25** | scheduler timeout / `scheduler` | 실행 트리, 600초 제한, subprocess 로그, 네트워크·API 대기, 직전 반복 | 병목 단계를 분리하고 단계별 제한·정리·결과 전파를 보완; timeout 상향만으로 해결하지 않음 | 제한 시간 fixture, 하위 프로세스 정리 테스트, 제한 dry run | 코드 수정 가능; 서비스 재시작은 진행 중 작업 확인 후 |
<a id="p29"></a>
| **P29** | frontmatter/publisher schema mismatch / `publish` | 실패 필드의 실제 타입, 작성기 입력 계약, 최근 변경, 샘플 콘텐츠 | 입력 정규화 또는 명시적 검증을 추가; 임의 문자열 변환으로 데이터 의미를 잃지 않음 | dict/list/string/None fixture, Hugo build | 코드 수정 가능; 발행·배포는 승인 |

## 2. 데이터·수집·파이프라인 오류

| 코드 | 신호·단계 | 원인 판별 | 안전한 수정 | 검증 | 주의점 |
|---|---|---|---|---|---|
<a id="p01"></a>
| **P01** | no_result / `result_parse` | 후보 소진인지, 일시 수집 공백인지, 품질·중복 guard 차단인지 구분 | P26/P27로 세분화할 수 있는 reason 추가; 제한된 재시도만 적용 | 후보 DB·발행 이력 대조, mock fetcher | `no_result`를 성공으로 바꾸지 않음 |
<a id="p02"></a>
| **P02** | no_content / `result_parse` | 원문 수집 실패, LLM 응답 공백, 콘텐츠 후처리 실패를 구분 | 실패 지점별 오류 전파·fallback·입력 검증 보완 | 빈 응답·정상 응답 fixture | 콘텐츠를 임의로 채우지 않음 |
<a id="p03"></a>
| **P03** | similar_title / `result_parse` | 실제 제목 유사도, 비교 대상 범위, 언어·템플릿 오탐 | 유사도 비교의 입력 정규화 또는 후보 선택을 보정 | 유사·비유사 제목 fixture | 제목 guard 우회 금지 |
<a id="p10"></a>
| **P10** | title_blocked / `result_parse` | 템플릿 패턴, 블랙키워드, 정상 제목 오탐 여부 | 제목 생성 규칙·정규식만 최소 수정 | 차단·통과 제목 fixture | 금칙어 완화는 승인 필요 |
<a id="p11"></a>
| **P11** | title_regenerate_failed / `result_parse` | 재생성 횟수, 제공자 응답, 프롬프트·fallback | bounded retry와 실패 사유 전파 보완 | retry budget 테스트 | 무한 재시도 금지 |
<a id="p12"></a>
| **P12** | content quality gate / `result_parse` | 차단한 품질 항목, 실제 원문, 검사기 오탐 여부 | 생성·후처리 품질 보완 또는 검사기 결함 수정 | 실패·정상 콘텐츠 fixture | 품질 게이트 비활성화 금지 |
<a id="p13"></a>
| **P13** | rate_limited / `result_parse` | provider HTTP 상태, reset 정보, 호출량, 공용 키 사용량 | backoff·호출 간격·캐시·작업 큐를 보완 | rate-limit mock, 재시도 상한 | 할당량 증가·키 교체는 승인 |
<a id="p14"></a>
| **P14** | fetch/quality gate failure / `result_parse` | 소스 응답, 필터, 후보 유효성, 차단 사유 | 소스·필터를 정확히 보정; 실패 reason을 구체화 | source fixture + guard 테스트 | 기준 완화는 승인 |
<a id="p16"></a>
| **P16** | duplicate_slug/source_id / `result_parse` | 기존 발행 이력, source_id·slug, 직전 실행 상태 | 재고 선택·상태 기록·idempotency를 수정 | 동시 실행·중복 fixture | 중복 guard 우회·기존 글 삭제 금지 |
<a id="p17"></a>
| **P17** | quota reached / `result_parse` | 일일 quota, 집계 시간대, 이전 발행 수 | 정상 상태면 `suppressed`; 집계 버그만 수정 | timezone·경계 시각 테스트 | quota를 오류처럼 재시도하지 않음 |
<a id="p18"></a>
| **P18** | already_running / `result_parse` | 활성 프로세스, PID·락 파일, 시작 시각 | stale lock 여부를 증거로 확인한 뒤 정리 로직 보완 | 정상 lock·stale lock 테스트 | 활성 작업 종료는 승인 |
<a id="p20"></a>
| **P20** | subprocess error / `result_parse` | stdout/stderr, exit code, 호출 인자, 하위 프로세스 시간 | 입력 인자·결과 계약·정리를 수정 | subprocess mock·exit code 테스트 | shell 문자열 조합·광범위 kill 금지 |
<a id="p21"></a>
| **P21** | config_error / `result_parse` | `blogs.d`, 환경변수 존재 여부, 스키마, 실제 읽힌 설정 | 스키마 검증·명확한 오류 메시지·누락 기본값 보완 | 유효·누락·잘못된 YAML fixture | 비밀값을 로그·대시보드에 저장 금지 |
<a id="p22"></a>
| **P22** | LLM fallback exhausted / `result_parse` | 모델별 오류, fallback 순서, rate limit, 입력 길이 | 모델 호출 실패 전파·fallback 순서·입력 제한 보정 | 각 fallback mock | 모델 계정·결제·키 변경은 승인 |
<a id="p26"></a>
| **P26** | source unavailable / `data_fetch` | API/DB/파일의 존재·HTTP 상태, 네트워크, 캐시 | 캐시 우선, bounded retry, 구체적 reason·HTTP 상태 기록 | 응답 실패/복구 fixture | 데이터 고갈과 혼동하지 않음 |
<a id="p27"></a>
| **P27** | source exhausted / `result_parse` | 미발행 유효 후보 수, 제외 규칙, 발행 이력 | 재고 갱신 작업 제안; 오탐이면 후보 SQL·필터 보정 | 후보 수·중복 제외 fixture | 기준 완화·과거 글 재사용은 승인 |
<a id="p28"></a>
| **P28** | invalid result contract / `result_parse` | pipeline 반환값, dispatcher 기대 스키마, `success` 전파 | 반환 타입·필드 검증, 오류를 성공으로 덮지 않는 전파 수정 | dict/non-dict/`success:false` fixture | 예외를 빈 성공 결과로 변환 금지 |
<a id="p30"></a>
| **P30** | content generation failure / `content_generation` | 모델 응답, 프롬프트, 입력 크기, fallback, 비용·rate limit | 입력 검증·fallback·명확한 실패 구분 | provider mock + 정상 생성 fixture | 실제 재생성·발행은 승인 |

## 3. 검증·설정·신선도 신호

| 코드 | 신호·단계 | 진단과 수정 | 검증 | 승인 경계 |
|---|---|---|---|---|
<a id="p15"></a>
| **P15** | post-publish validation | 검사 항목, 라이브 HTML, 생성 파일, 검사기 자체 오류를 분리한다. 실제 결함은 콘텐츠·템플릿에 최소 수정하고, 검사기 오탐은 검사기만 수정한다. | 단위 fixture + 라이브 샘플 | 재발행은 승인 |
<a id="p19"></a>
| **P19** | stale/expired / post-validate | 데이터 유효기간·발행 일정·외부 이벤트 종료일을 확인한다. 실제 stale이면 갱신 작업으로 큐화한다. | 새 데이터·날짜 경계 테스트 | 대량 갱신·삭제는 승인 |
<a id="p23"></a>
| **P23** | image URL length / post-generate | URL 생성기·서명 파라미터·이미지 호스트 정책을 확인한다. 길이 제한을 무시하지 않고 URL 축약 또는 업로드 경로를 수정한다. | 최대 길이 fixture, 실제 URL 요청 | 스토리지 이동은 승인 |
<a id="p24"></a>
| **P24** | validation defect / post-validate | 오류가 콘텐츠가 아닌 검사기의 DB·정규식·입력 형태·예외 처리에서 왔는지 확인한다. | 실패 재현 + 정상/오탐 fixture | 검사 기준 승격·완화는 승인 |
<a id="p31"></a>
| **P31** | Telegram delivery / notification | 감사 레코드, HTTP 상태, bot 권한, chat ID, 메시지 길이·parse mode를 확인한다. | 전송 성공/4xx/5xx mock, 정제 테스트 | token·chat 변경은 승인 |
<a id="p32"></a>
| **P32** | 빈 본문 배포 / `post_deploy` | publish_log 최근 글의 public HTML 본문 단어수 200 미만, topic의 exhausted=1과 publish_log INSERT 동시 발생 패턴, _write_hugo_post_etap 호출 시 article["content"]가 빈 문자열/공백/200단어 미만 | 가드 통과·차단 dry run, 본문 단어수 계측, H2/disclaimer/adsense 존재 확인 | 가드 변경은 additive; 기존 정상 글 영향 없음 확인. 재생성·배포는 승인 |


## 5. 콘텐츠 품질 이탈 (CONTENT-QUALITY, 큐레이션 발행물)

> 상세 판정표·해결절차: `docs/CONTENT-QUALITY-RUNBOOK.md` (SSOT).
> 감지: `ops_dashboard/checks/content_quality.py` `_analyze` (라이브 HTML). 교정: `pipelines/curation/pipeline.py` `_normalize_product_blocks`.

| 코드 | 신호 | 원인 판별 | 안전한 수정 | 검증 | 주의점 |
|---|---|---|---|---|---|
<a id="cq01"></a>
| **CQ01** | 빈 불릿(라벨만)/빈 리스트 항목 | writer 프롬프트가 값 없는 필드도 라벨 출력 | _normalize_product_blocks (1) 자동 제거; writer.py 프롬프트 보정 | 룩북 CQ01 | 정상 불릿까지 지우지 않음 |
<a id="cq02"></a>
| **CQ02** | CTA가 `<li>`에 갇힘 | AI가 CTA를 불릿 항목으로 출력 | _normalize_product_blocks (3-b) 독립 블록화 | 룩북 CQ02 | CTA는 항상 리스트 밖 |
<a id="cq03"></a>
| **CQ03** | 제휴문구 0회/3회+ | AI가 상품마다 제휴문구 삽입 | (2) 전체 삭제 후 (4) 상세비교 앞 1회+글끝 1회 고정 | 룩북 CQ03 | 정상 2회 초과·미만 금지 |
<a id="cq04"></a>
| **CQ04** | 상품별 상세 비교 h2 아님 | AI가 `##` 대신 strong/bold 출력 | pipeline.py (4-b)(4-c) 변환 **+** hugo_writer.py H2-GUARD allow-list 등재(2곳 짝) | 룩북 CQ04, 강제H2원칙 | CSS로 키우지 말 것; allow-list 누락 시 발행 때 bold로 무력화됨 |
<a id="cq05"></a>
| **CQ05** | 상품 이미지 개수 부족 | 특정 상품 coupang=SKIP → 이미지 미수집 | **수집부** 재수집·대체. 후처리로 못 채움 | 룩북 CQ05 | 임의 이미지로 채우지 않음; 수집 승인 |
<a id="cq06"></a>
| **CQ06** | raw img 방식(figure 미사용) | 과거 raw img 삽입 로직 잔재 | _normalize_product_blocks (5) figure 숏코드로 통일 | 룩북 CQ06(.md 소스 검사) | 라이브 HTML로는 감지 불가 |
<a id="cq07"></a>
| **CQ07** | 상품 설명 문단 소실(N개) | 후처리 설명 보존 회귀 — `<p><figure>…</figure>`만 남고 설명 텍스트 소실 | _normalize_product_blocks 설명 보존 로직 점검(재발 시). **감지 전용·자동 알림** — 발행 차단·재발행 없음 | 룩북 CQ07 + CQ07 재검사 트리거 | 설명은 이미지와 같은 `<p>` 안 — 태그가 아닌 텍스트(CJK) 기준 판정 |


## 4. 대시보드의 비-P 코드 신호

### M01–M11: 운영·정비 검사

<a id="m01"></a>
<a id="m02"></a>
<a id="m03"></a>
<a id="m04"></a>
<a id="m05"></a>
<a id="m06"></a>
<a id="m07"></a>
<a id="m08"></a>
<a id="m09"></a>
<a id="m10"></a>
<a id="m11"></a>
M 검사는 콘텐츠·링크·유사 제목·CoT·발행 로그·도메인·CJK 여부 등 운영 사실을 검사한다. 에이전트는 M 검사 fail이 다수일 때 개별 블로그를 일괄 수정하지 않는다. 먼저 검사기 입력, 실제 DB 테이블·컬럼, 상태값, 라이브 샘플을 점검해 **실제 결함 / 검사기 오탐 / 혼재**로 분해한다.

| 패턴 | 첫 조치 | 자동 수정 가능 | 금지 |
|---|---|---|---|
| 같은 M 코드가 대다수 블로그에서 fail | 검사기 정규식·HTML 파서·공통 입력 샘플 확인 | 오탐이 재현되면 검사기 수정 가능 | 콘텐츠 대량 재작성 |
| 모든 블로그가 pass | DB 연결·컬럼·상태값·예외 삼킴 확인 | 무력 검사 수정 가능 | “전부 pass”를 무조건 정상 처리 |
| 한 블로그만 fail | 라이브 URL, 콘텐츠·설정·발행 이력 확인 | 고립된 코드·설정 수정 가능 | 다른 블로그로 범위 확대 |
| fail과 P 이벤트가 함께 발생 | P 이벤트를 원인, M을 영향 증거로 사용 | 원인 수정 후 M 재검사 | M 결과만으로 원인 확정 |

### R01–R12: 표준 준수 규칙

<a id="r01"></a>
<a id="r02"></a>
<a id="r03"></a>
<a id="r04"></a>
<a id="r05"></a>
<a id="r06"></a>
<a id="r07"></a>
<a id="r08"></a>
<a id="r09"></a>
<a id="r10"></a>
<a id="r11"></a>
<a id="r12"></a>
<a id="thumbnail-01"></a>
<a id="r2-01"></a>
R 규칙은 대체로 구조·템플릿·SEO·운영 표준의 준수 여부를 나타낸다. 에이전트는 R fail을 즉시 발행 장애로 승격하지 않는다. 실제 사용자 영향, 규칙의 진실 원천, 동일 테마·브랜드의 공통성, 라이브 페이지의 재현 여부를 먼저 조사한다.

| 상황 | 처리 |
|---|---|
| 단일 블로그의 명확한 R 위반 | 최소 파일 수정 → 해당 규칙 재실행 → 라이브 확인 제안 |
| 동일 테마 다수의 R 위반 | 테마 또는 검사기 공통 원인부터 표본 검증; 일괄 변경은 파일럿 후 승인 |
| 규칙과 라이브 결과 불일치 | R 규칙의 파서·입력·테마 호환성을 수정하고 오탐 사건으로 기록 |
| 기준 자체가 제품 요구와 충돌 | 변경안·영향 범위·기존 콘텐츠 수를 보고하고 사람 승인을 받음 |

## 5. 해결 보고의 최소 형식

에이전트는 어떤 오류든 아래 정보를 빼지 않고 보고한다.

| 항목 | 요구 내용 |
|---|---|
| 사건 | event ID, P 코드, 블로그, 단계, 첫·마지막 발생 시각, 영향 |
| 증거 | 로그·DB·설정·라이브 확인 중 실제로 확인한 경로와 결론 |
| 판정 | 실제 장애, 정상 제어 흐름, 오탐, 데이터 소진, 미확정 중 하나 |
| 변경 | 수정한 파일·함수·설정과 변경 이유 |
| 검증 | 실행한 테스트·dry run·라이브 점검과 결과 |
| 미실행 외부 조치 | 재발행·배포·푸시·권한 변경 등 승인 대기 항목 |
| 잔여 위험 | 재발 가능성, 관찰 기간, 다음 체크 시각 또는 조건 |

> 오류의 “해결”은 대시보드에서 사라지는 것보다, 같은 입력·같은 실행 경로에서 문제가 재현되지 않고 그 결과가 검증되는 것을 의미한다.

## 6. 이벤트 수명 주기 관리

`publish_error_events` 테이블의 이벤트는 `state='open'`으로 생성되고, 원인이 해소되면 `state='closed'`로 변경되어야 한다. open 이벤트가 누적되면 대시보드가 stale 상태로 보이고 알림 소음이 증가한다.

### 이벤트 close가 필요한 상황

| 상황 | close 조건 | 담당 코드 |
|---|---|---|
| P04 (배포 실패) | 배포 성공(`deployed: true` 또는 `_build_and_deploy_central` 성공), 또는 `deploy_error` 없는 성공 결과 | `dispatcher.py:dispatch()` 성공 경로 |
| P25 (스케줄러 timeout) | timeout 후 재시도에서 발행 성공 | `scheduler.py:_track_publish_result()` 성공 경로 |
| P01/P02 등 재시도 가능 오류 | 재시도 성공 시 (필요 시) | 파이프라인 성공 경로 |

### close 시 주의

- **직전 open 이벤트만 close** — 새 이벤트가 다시 생성될 수 있으므로, close는 최신 1건으로 한정 (`close_publish_error_event`의 LIMIT 1).
- **before 필터** — 특정 시각 이전의 이벤트만 close해야 할 때 `before` 파라미터 사용 (예: 오늘 이전 이벤트 일괄 close).
- **close 실패는 비차단** — close 실패가 발행 파이프라인을 중단하지 않아야 함 (예외 무시하고 로그만).
- **수동 close** — stale 이벤트가 코드 수정 전에 이미 누적되어 있으면 ops.db에서 직접 UPDATE.

### P 코드별 close 책임

| 코드 | 원인 해소 판단 | close 트리거 |
|---|---|---|
| P04 | 배포 성공 (HTTP 200, wrangler 성공) | dispatcher 성공 시 |
| P25 | timeout 후 재시도 성공 | scheduler 성공 시 |
| P06 | featureimage URL 복구 후 재배포 성공 | 배포 성공 시 |
| P15 | 검증 통과 콘텐츠 재배포 성공 | 배포 성공 시 |

> **"해결됨"과 "close"는 별도 상태다.** 코드 수정이 완료되었더라도 이벤트가 close되지 않으면 대시보드에 계속 표시된다. 코드 수정 + 이벤트 close + 재검사를 함께 수행해야 완전한 해결이다.
