---

# 프로젝트 5000 기술 분석 문서

**작성일**: 2026-03-17 (초판) → 2026-03-19 (2차 업데이트)
**프로젝트명**: 5000 (자동 콘텐츠 발행 파이프라인)
**목표**: 일일 5,000건 자동 콘텐츠 발행
**현재 실적**: 일일 약 95~100건 (2026-03-18 기준 94건 발행)
**상태**: 운영 중 / 확장 진행 중

---

## 1. 프로젝트 개요

프로젝트 5000은 공공 API, 웹 스크래핑, 검색 API로 수집한 데이터를 기반으로 AI(OpenAI)를 통해 블로그 글을 자동 생성하고, Hugo 정적 사이트·Blogger·WordPress에 발행한 뒤 Cloudflare Pages로 배포하는 **엔드투엔드 자동 콘텐츠 파이프라인**입니다.

현재 **4개 파이프라인**(TAP, CAP, STAP, GAP)이 **18개 블로그**(Hugo 12 + Blogger 2 + WordPress 2)를 대상으로 운영됩니다.

**일일 5,000건 목표 대비 현황**:
현재 일일 약 100건(활성 블로그 17개 × 평균 5~8건). 목표 달성을 위해 블로그 수 확장, 파이프라인 추가(부동산, 스포츠, 이커머스 등), 발행 속도 병렬화가 필요합니다.

**루트 디렉토리**: `/Users/twinssn/Projects/5000`
**가상환경**: `.venv` (Python 3.14)
**데이터베이스**: SQLite 4개 (`data/content.db`, `data/car.db`, `data/stock.db`, `data/gap.db`)

---

## 2. 시스템 아키텍처

전체 흐름은 스케줄러 → 디스패처 → 데이터 수집 → 콘텐츠 생성 → 발행 → 배포의 6단계로 구성됩니다.

**스케줄러** (`scheduler.py`)가 `blogs.yaml`에 정의된 스케줄에 따라 각 블로그의 발행 시점을 관리합니다. 현재 82개 스케줄 job이 등록되어 있습니다. 시간이 되면 **디스패처** (`dispatcher.py`)가 해당 블로그의 파이프라인(TAP, CAP, STAP, GAP)을 호출합니다. 디스패처는 `blog_id`를 기반으로 일일 할당량(`daily_quota`)을 확인하고, 초과하지 않는 범위 내에서 발행을 진행합니다.

**스케줄 보충 발행 (Catchup)**: `scheduler.py`의 `catchup_missed()` 함수가 5분(300초) 간격으로 밀린 발행을 자동 보충합니다. 각 블로그별로 현재 시각까지 실행됐어야 할 스케줄 횟수와 실제 발행 횟수를 비교하고, 부족분만큼 `run_publish()`를 순차 호출합니다. 보충 발행 중 실패가 발생하면 해당 블로그의 남은 보충을 중단하고 다음 5분 주기에 재시도합니다.

**데이터 수집** 단계에서 각 파이프라인이 독립된 데이터 소스를 활용합니다(3장 상세). **콘텐츠 생성**은 OpenAI API를 호출하여 프롬프트와 데이터를 조합해 마크다운 본문을 생성합니다. **발행** 단계에서 플랫폼별로 분기합니다: Hugo는 `content/posts/{slug}/index.md` 파일로 저장, Blogger는 마크다운→HTML 변환 후 Blogger API로 발행, WordPress는 마크다운→HTML 변환 후 REST API로 발행합니다. **배포**는 매일 22:45에 `batch_push.sh`가 Hugo 빌드 후 Wrangler CLI로 Cloudflare Pages에 배포합니다.

---

## 3. 파이프라인 상세

### 3.1 TAP (Travel Auto Publisher — 여행 파이프라인)

TAP은 한국관광공사 TourAPI 4.0을 주 데이터 소스로 사용합니다. contentTypeId 기준으로 12(관광지), 15(축제/행사), 25(여행코스), 28(레포츠), 39(음식)의 5개 유형을 활용하며, 미활용 유형으로 32(숙박), 14(문화시설), 38(쇼핑)이 남아 있습니다. 웰니스관광 API(`WellnessTursmService`)는 건강/힐링 관광지 데이터를 제공합니다.

**대상 사이트**: Hugo 5개(travel-hugo~travel4-hugo), Blogger 2개(tvshow-blogger, ud-blogger), WordPress 1개(kuta-wordpress) = 총 8개

**핵심 데이터 흐름**: API 호출 → 시군구 단위 지역 추출 → 장소명 검증(`_validate_place_names`) → 중복 장소 확인(`used_places` DB) → 본문 생성 → 이미지 삽입(`_inject_images`) → 이미지 중복 확인(`is_image_used`, blog_id별) → HTTP→HTTPS 변환(`_extract_first_image`) → 프론트매터 생성(빈 thumbnail시 R2 기본 이미지 폴백) → 플랫폼별 발행(Hugo 파일저장 / Blogger·WordPress HTML 변환 후 API 발행)

**지역 세분화** (2026-03-19 개선): `fetch_food()`에서 TourAPI 응답의 `addr1` 필드에서 시군구를 추출하여 `display_region`을 시도 단위("경기")에서 시군구 단위("수원", "용인")로 세분화했습니다. 이를 통해 글 제목과 본문의 지역 특정성이 향상되었습니다.

**이미지 처리 로직**: `_inject_images(items, content, blog_id)`가 API 응답의 `firstImageUrl`, `firstimage`, `image` 키에서 이미지 URL을 추출하고, `is_image_used(img, blog_id)` 검사를 통해 같은 블로그 내에서만 중복을 방지합니다. `_extract_first_image()` 함수는 본문에서 첫 번째 이미지를 추출하면서 `tong.visitkorea.or.kr` 도메인의 HTTP URL을 HTTPS로 자동 변환합니다.

**기본 썸네일 폴백**: `featureimage`가 비어 있을 경우 R2에 호스팅된 기본 이미지(`https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp`)를 사용합니다.

### 3.2 CAP (Car Auto Publisher — 자동차 파이프라인)

CAP은 carisyou.com 스크래핑과 공공데이터 에너지소비효율 API를 주 데이터 소스로 사용합니다.

**대상 사이트**: Hugo 6개(hotissue-hugo, tco-hugo, deal-hugo, compare-hugo, guide-hugo, ev-hugo)

**데이터 빌더** (`data_builder.py`)가 AI에 전달할 입력 데이터를 조립합니다. `lookup_fuel_efficiency()`가 연비를 조회하고, `estimate_resale()`이 브랜드별 감가율로 잔존가치를 추정하며, `lookup_ev_specs()`가 전기차 스펙을 조회합니다.

**모델명 매칭**: `MODEL_NAME_MAP` 딕셔너리가 carisyou의 한글 모델명을 공공데이터의 영문/혼용 모델명으로 변환합니다. 현재 매칭률은 124대 중 115대(92%)입니다.

**토픽 관리**: `car.db`의 `topics` 테이블이 발행 대상을 관리합니다.

**발행 차단 정책**: `build_input()`이 연비 데이터를 찾지 못하면 None을 반환하고, 디스패처가 해당 토픽을 스킵합니다. 현재 차단 차종: 볼보 EX30/EX30 크로스컨트리, 기아 EV5/EV4, KGM 무쏘/무쏘 스포츠, 벤츠 마이바흐 SL, 렉서스 LX, 제네시스 일렉트리파이드 G80 (9대).

### 3.3 STAP (Stock Auto Publisher — 주식 파이프라인)

STAP은 DART(전자공시시스템) OpenAPI를 주 데이터 소스로 사용합니다.

**대상 사이트**: Hugo 1개(stock-hugo, stock.informationhot.kr, Congo 테마)

**핵심 데이터 흐름**: DART API에서 최근 공시 조회(`fetch_recent_disclosure`) → 기업 정보 조회(`fetch_company_info`) → 재무 요약(`fetch_financial_summary`) + 전년도 재무(YoY 비교) + 배당 정보(`fetch_dividend_info`) → AI 글 생성(`generate_disclosure_article`) → Pillow 썸네일 생성(`generate_stock_thumbnail`) → R2 업로드 → Hugo 파일 저장

**발행 전략**: `_pick_strategy()`가 disclosure(공시 분석) 또는 에버그린(배당 랭킹, ETF 비교, 섹터 분석, IPO 일정, CMA 적금 비교) 중 하나를 선택합니다. 현재는 disclosure 고정입니다.

**중복 방지**: `publish_history` 테이블에서 최근 7일 내 동일 `corp_code`로 발행된 공시를 필터링합니다.

### 3.4 GAP (General Article Publisher — 생활정보 파이프라인)

GAP은 네이버 검색 API(웹, 블로그, 뉴스)를 데이터 소스로 사용합니다.

**대상 사이트**: WordPress 1개(gap-kuta, kuta.informationhot.kr). gap-hugo(life.informationhot.kr)는 도메인 미설정으로 inactive 상태입니다.

**핵심 데이터 흐름**: gap.db `keywords` 테이블에서 우선순위 기반 키워드 선택(`_pick_keyword`) → 네이버 검색 API로 웹/블로그/뉴스 수집(`fetch_keyword_data`) → AI 글 생성(`generate_gap_article`) → 마크다운→HTML 변환 → WordPress REST API 발행

**키워드 관리**: `gap.db`의 `keywords` 테이블이 82개 키워드를 관리합니다. 각 키워드는 `category`, `priority`(1=시의성 높음, 3=중간, 5=에버그린), `status`, `use_count`, `last_used_at`으로 구성됩니다. `_pick_keyword()`는 최근 7일 내 발행된 키워드를 제외하고, `use_count` ASC → `last_used_at` ASC 순으로 미사용/오래된 키워드를 우선 선택합니다.

**확장 계획**: blogdex 프로젝트(Google Search Console 데이터)에서 수익 발생 키워드를 자동 추출하여 gap.db에 저장하고, 해당 키워드 기반 글을 자동 생성하는 파이프라인을 추가할 예정입니다.

---

## 4. 인프라 구성

### 4.1 사이트 목록 (18개, 활성 17개)

**TAP 사이트 — Hugo** (테마: Blowfish)

| 사이트 | 카테고리 | 도메인 | 컬러테마 | 로컬 경로 |
|---|---|---|---|---|
| travel-hugo | 캠핑/아웃도어 | tour1.rotcha.kr | forest | /Users/twinssn/Projects/travel-hugo |
| travel1-hugo | 축제/행사 | travel1.rotcha.kr | travel-pink | /Users/twinssn/Projects/travel1-hugo |
| travel2-hugo | 문화유산 | travel2.rotcha.kr | autumn | /Users/twinssn/Projects/travel2-hugo |
| travel3-hugo | 맛집/카페 | tour2.rotcha.kr | fire | /Users/twinssn/Projects/travel3-hugo |
| travel4-hugo | 여행코스 | tour3.rotcha.kr | congo | /Users/twinssn/Projects/travel4-hugo |

**TAP 사이트 — Blogger / WordPress**

| 사이트 | 플랫폼 | 도메인 | 비고 |
|---|---|---|---|
| tvshow-blogger | Blogger | tv-show.informationhot.kr | TV-show 주말 프로그램과 병행 발행 |
| ud-blogger | Blogger | ud.informationhot.kr | TV-show 주말 프로그램과 병행 발행 |
| kuta-wordpress | WordPress | kuta.informationhot.kr | TV-show 주말 프로그램과 병행 발행 |

**CAP 사이트 — Hugo**

| 사이트 | 카테고리 | 도메인 | 테마 |
|---|---|---|---|
| hotissue-hugo | 핫이슈 | hotissue.rotcha.kr | PaperMod |
| tco-hugo | 유지비 분석 | tco.rotcha.kr | Blowfish |
| deal-hugo | 프로모션/딜 | deal.rotcha.kr | Blowfish |
| compare-hugo | 차종 비교 | compare.rotcha.kr | Blowfish |
| guide-hugo | 초보 가이드 | guide.rotcha.kr | Blowfish |
| ev-hugo | 전기차 분석 | ev.rotcha.kr | Blowfish |

**STAP 사이트 — Hugo**

| 사이트 | 카테고리 | 도메인 | 테마 |
|---|---|---|---|
| stock-hugo | 주식/공시 분석 | stock.informationhot.kr | Congo |

**GAP 사이트 — WordPress / Hugo**

| 사이트 | 플랫폼 | 도메인 | 상태 |
|---|---|---|---|
| gap-kuta | WordPress | kuta.informationhot.kr | active (kuta-wordpress와 동일 블로그에 병행 발행) |
| gap-hugo | Hugo | (도메인 미설정) | inactive |

### 4.2 배포 및 스토리지

**Cloudflare Pages**: Hugo 12개 사이트가 Cloudflare Pages에 배포됩니다. Wrangler CLI를 통해 배포합니다.

**Cloudflare R2**: 이미지 저장소. 차량 이미지는 `car-images/`, 주식 썸네일은 `stock-thumbnails/`, GAP 썸네일은 `gap-thumbnails/`, 공용 기본 썸네일은 `common/`에 저장됩니다. 퍼블릭 URL: `https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/`

### 4.3 스케줄러

`scheduler.py`가 `blogs.yaml`의 설정에 따라 82개 스케줄 job을 관리합니다. `run_publish()` 함수가 성공/실패를 `True`/`False`로 반환하며, 메인 루프는 30초 간격 `schedule.run_pending()` + 5분마다 `catchup_missed()`를 실행합니다. launchd plist(`com.5000.scheduler.plist`)는 `KeepAlive: true`, `RunAtLoad: true`로 설정되어 스케줄러 프로세스 재시작이 보장됩니다.

### 4.4 데이터베이스 스키마

**content.db** (TAP + 공용): `articles`(발행 이력, 전 파이프라인 공용), `used_images`(이미지 중복 방지, blog_id별), `used_places`(장소 중복 방지)

**car.db** (CAP): `cars`(차량 기본 정보), `trims`(트림/가격, 668건), `car_images`(차량 이미지 URL), `public_fuel_data`(공공 연비 데이터, 6,672건), `topics`(발행 토픽 큐), `publish_log`(발행 이력). `resale_prices` 테이블은 0건(추정치로 대체 중).

**stock.db** (STAP): `corps`(상장법인 목록), `publish_history`(발행 이력, corp_code 기반 7일 중복 방지), `topic_queue`(에버그린 토픽 큐)

**gap.db** (GAP): `keywords`(키워드 82건, priority/category/use_count 관리), `publish_log`(발행 이력, site_id + keyword 기반)

---

## 5. 데이터 소스 현황

### 5.1 현재 활용 중

| 소스 | 파이프라인 | 용도 | 데이터량 |
|---|---|---|---|
| TourAPI 4.0 (data.go.kr) | TAP | 관광지/축제/코스/레포츠/음식 | 5개 contentTypeId |
| 웰니스관광 API | TAP | 건강/힐링 관광지 | WellnessTursmService |
| carisyou.com 스크래핑 | CAP | 차량 트림/가격/이미지 | 124대, 668트림, 638이미지 |
| 에너지소비효율 API (data.go.kr) | CAP | 연비/배기량/CO2/EV주행거리 | 6,672건 |
| DART OpenAPI | STAP | 전자공시/기업정보/재무요약/배당 | 상장법인 전체 |
| 네이버 검색 API | GAP | 웹/블로그/뉴스 검색 | 키워드당 15건 |

### 5.2 데이터 품질 이슈

**trims 테이블**: 668건 중 연비(fuel_efficiency) 0%, 엔진 설명(engine_desc) 0%, 주요 사양(key_features) 0%가 채워져 있습니다. 연비는 `public_fuel_data`의 `lookup_fuel_efficiency()`를 통해 보완 중이나, trims 테이블 자체는 비어 있습니다.

**resale_prices**: 0건. `estimate_resale()` 함수가 브랜드별 고정 감가율(현대 65%, 기아 63%, BMW 55% 등)로 추정합니다.

**모델명 불일치**: `MODEL_NAME_MAP`으로 수동 매핑. 현재 92% 매칭률(9대 미매칭).

### 5.3 확장 가능 데이터 소스

**여행 (즉시 가능)**: TourAPI contentTypeId 32(숙박), 반려동물 동반 관광, 무장애 관광

**여행 (중기)**: 두루누비 도보/자전거 코스(GPX)

**자동차 (즉시 가능)**: 리콜 현황 API, 종합 자동차 정보 API

**자동차 (중기)**: 신규등록 현황 API, EV 충전기 상세 API

**생활정보 (계획 중)**: blogdex GSC 데이터에서 수익 키워드 자동 추출

---

## 6. 완료된 개선 사항

| 항목 | 내용 | 영향 범위 | 완료일 |
|---|---|---|---|
| Blowfish cardView + 메뉴 | 10개 사이트에 카드뷰와 메뉴 적용 | TAP 5 + CAP 5 | 03-17 이전 |
| 컬러 테마 변경 | forest / fire / congo 적용 | TAP 3개 사이트 | 03-17 이전 |
| 웰니스 API 이미지 수정 | WellnessTursmService 이미지 URL 처리 | TAP 전체 | 03-17 이전 |
| KorService2 폴백 | 이미지 없을 시 KorService2 API 호출 | TAP 전체 | 03-17 이전 |
| HTTP → HTTPS 변환 | _extract_first_image()에서 자동 변환 | TAP 전체 | 03-17 이전 |
| 이미지 중복 방지 개선 | is_image_used()에 blog_id 파라미터 추가 | 전체 | 03-17 이전 |
| 장소명 검증 | _validate_place_names() 함수 | TAP 전체 | 03-17 이전 |
| 장소 발행 이력 DB | used_places 테이블 | TAP 전체 | 03-17 이전 |
| 빈 featureimage 폴백 | R2 기본 썸네일 자동 적용 | TAP + CAP 전체 | 03-17 이전 |
| CAP 데이터 매칭률 개선 | 72% → 92% | CAP 전체 | 03-17 이전 |
| EV 스펙 보강 | lookup_ev_specs() 추가 | CAP EV 분석 | 03-17 이전 |
| 미매칭 차종 발행 차단 | build_input() None 반환 시 스킵 | CAP 전체 | 03-17 이전 |
| 스케줄 보충 발행 (catchup) | 5분마다 밀린 발행 자동 보충 | 전체 | 03-17 |
| STAP 파이프라인 추가 | DART 공시 기반 주식 분석 블로그 | stock-hugo | 03-18 |
| GAP 파이프라인 추가 | 네이버 검색 기반 생활정보 블로그 | gap-kuta | 03-19 |
| GAP writer.py import 수정 | call_openai → ai_generate 함수명 변경 | GAP 전체 | 03-19 |
| GAP 키워드 DB 전환 | 하드코딩 22개 → gap.db 82개 (priority 기반) | GAP 전체 | 03-19 |
| GAP 프롬프트 품질 강화 | TV-show 스타일 규칙 적용 (허위정보 방지) | GAP 전체 | 03-19 |
| WordPress 마크다운→HTML 변환 | publisher.py에 markdown 변환 추가 | WordPress 전체 | 03-19 |
| TAP 지역 세분화 | fetch_food() 시군구 단위 추출 | TAP food | 03-19 |
| Blogger/WordPress 부실 글 삭제 | tvshow-blogger 5건, kuta-wordpress 4건 삭제 | Blogger+WP | 03-19 |
| stock-hugo 스케줄러 등록 | 스케줄러 재시작으로 stock-hugo 등록 완료 | STAP | 03-19 |
| gap-kuta WordPress 블로그 추가 | kuta.informationhot.kr에 GAP 병행 발행 | GAP | 03-19 |

---

## 7. 미해결 이슈 및 리스크

### 7.1 긴급 (P0)

**CAP 5개 사이트 부실 글 존재**: deal-hugo 6건, ev-hugo 2건, tco-hugo 2건, compare-hugo 3건, guide-hugo 2건이 데이터 보강 전에 발행되어 품질 미달 상태입니다. 삭제 후 재발행이 권장됩니다.

**trims 테이블 스펙 데이터 부재**: 668개 트림의 연비, 엔진 설명, 주요 사양이 모두 비어 있습니다. AI가 추정하여 허위 데이터 생성 리스크가 있습니다.

### 7.2 높음 (P1)

**resale_prices 테이블 비어 있음**: 잔존가치가 브랜드별 고정 비율로만 추정됩니다. 실제 중고차 시세 데이터 연동이 필요합니다.

**autoSwitchAppearance 미배포**: TAP 4개 사이트에서 `autoSwitchAppearance = true`가 남아 있어 다크모드에서 컬러 테마가 정상 표시되지 않습니다.

**ev-hugo 도메인 혼선**: `hugo.toml`의 `baseURL`이 `newcar.rotcha.kr`로 되어 있을 수 있으나, 실제 작동 도메인은 `ev.rotcha.kr`입니다.

### 7.3 보통 (P2)

**hotissue-hugo 혼합 콘텐츠**: 자동차 글과 방송 글이 한 사이트에 혼재하여 SEO 주제 일관성이 떨어집니다.

**공공데이터 미보유 9대 차종**: 발행이 차단된 상태입니다.

**네트워크 장애 시 실시간 알림 미구현**: catchup으로 발행은 보충되나, 장애 발생 자체를 즉시 인지하는 수단이 없습니다.

**gap-hugo 도메인 미설정**: `life.informationhot.kr` 도메인이 설정되지 않아 inactive 상태입니다.

**Daily report 오류**: `shared.monitor`에서 `send_daily_report` import 실패로 23:50 리포트가 작동하지 않습니다.

---

## 8. 기술 부채

**carisyou 스크래퍼 한계**: 가격과 상태만 수집하고 연비/엔진/사양을 가져오지 않습니다.

**config.loader 모듈 미정리**: 수동 발행 테스트 시 `ModuleNotFoundError` 발생.

**publish_log 테이블 불일치**: `car.db`의 `publish_log`와 `content.db`의 `articles` 간 발행 이력 정합성 미검증.

**프롬프트 품질 관리**: 데이터가 비어 있을 때 AI가 숫자를 임의 생성하는 것을 방지하는 검증 로직이 없습니다.

**car.db publish_log 스키마**: `site_id` 컬럼이 없어 사이트별 발행 조회가 불가합니다.

---

## 9. 일일 발행량 분석 및 5,000건 로드맵

### 현재 발행량 (2026-03-18 기준)

| 파이프라인 | 사이트 수 | 일일 쿼터 합 | 실 발행량 | 비고 |
|---|---|---|---|---|
| TAP | 8 | 265 (Hugo 250 + Blogger 10 + WP 5) | ~54 | 스케줄 시간 제한으로 쿼터 미달 |
| CAP | 6 | 300 | ~44 | 토픽 소진 시 감소 |
| STAP | 1 | 5 | 12 | 공시 기반, 변동 있음 |
| GAP | 1 | 5 | 0 | 03-19 신규, 첫 발행 시작 |
| **합계** | **16** | **575** | **~100** | |

### 5,000건 달성 로드맵

**Phase 1 (현재→1개월)**: 기존 파이프라인 최적화. 발행 속도 병렬화, 스케줄 간격 축소. 목표 일일 300건.

**Phase 2 (1~3개월)**: 파이프라인 확장. 부동산(RAP), 스포츠(SAP), 이커머스(EAP), 생활/건강(LAP) 추가. 블로그 수 30~50개. 목표 일일 1,000건.

**Phase 3 (3~6개월)**: 대규모 확장. 키워드 자동 발굴(blogdex GSC 연동), 다국어(영문/일문) 블로그, 콘텐츠 품질 자동 검증. 목표 일일 5,000건.

---

## 10. 권장 개선 로드맵

### 즉시 (이번 주)

CAP 5개 사이트 부실 글 삭제 및 재발행, `autoSwitchAppearance = false` 배포, ev-hugo 도메인 정리, GAP 첫 발행 검증 및 안정화, 5000 프로젝트 git commit + push

### 단기 (1~2주)

carisyou 스크래퍼 상세 스펙 수집 추가, `resale_prices` 테이블에 실 중고차 시세 데이터 연동, 네트워크 장애 시 Slack/Telegram 알림 추가, 발행 전 본문 품질 자동 검증, blogdex GSC 수익 키워드 → gap.db 자동 연동, Daily report 수정

### 중기 (1개월)

TAP 숙박 블로그 추가, 반려동물 동반 여행 블로그, 자동차 리콜 현황 블로그, STAP 에버그린 전략 활성화, 발행 속도 병렬화(asyncio 또는 멀티프로세스)

### 장기 (3개월)

EV 충전 인프라 분석, 무장애 관광, 신차 등록 트렌드, 부동산/스포츠/이커머스 파이프라인, 다국어 블로그

---

## 11. 주요 파일 맵

/Users/twinssn/Projects/5000/ ├── scheduler.py # 스케줄러 메인 + 보충 발행 (catchup) ├── dispatcher.py # 파이프라인 라우터 (TAP/CAP/STAP/GAP) ├── config/ │ └── blogs.yaml # 18개 블로그 설정 ├── data/ │ ├── content.db # 공용 DB (articles, used_images, used_places) │ ├── car.db # CAP DB (cars, trims, topics, publish_log) │ ├── stock.db # STAP DB (corps, publish_history, topic_queue) │ └── gap.db # GAP DB (keywords, publish_log) ├── shared/ │ ├── publisher.py # 플랫폼별 발행 (Hugo/Blogger/WordPress) │ ├── blogger_publisher.py # Blogger API 발행기 │ ├── wp_publisher.py # WordPress REST API 발행기 │ ├── ai_writer.py # OpenAI 호출 (generate, generate_car) │ ├── r2_uploader.py # Cloudflare R2 업로드 │ ├── content_store.py # DB 접근 (is_image_used 등) │ └── telegram_notifier.py # 텔레그램 알림 ├── pipelines/ │ ├── travel/ │ │ ├── fetcher.py # 관광 API 수집 (9개 함수, 시군구 세분화) │ │ └── writer.py # 콘텐츠 생성 + 이미지 삽입 │ ├── car/ │ │ ├── daily_refresh.py # carisyou 스크래핑 + 데이터 수집 │ │ └── data_builder.py # AI 입력 데이터 조립 │ ├── stock/ │ │ ├── pipeline.py # STAP 메인 (DART 공시 → 글 생성) │ │ ├── fetcher.py # DART API 수집 │ │ ├── writer.py # 공시/에버그린 글 생성 │ │ └── thumbnail.py # Pillow 썸네일 생성 │ └── gap/ │ ├── pipeline.py # GAP 메인 (키워드 → 검색 → 글 생성) │ ├── fetcher.py # 네이버 검색 API 수집 │ ├── writer.py # 생활정보 글 생성 │ └── thumbnail.py # GAP 썸네일 생성 ├── prompts/ │ └── ev/ │ └── ev_analysis.md # EV 분석 프롬프트 └── .env # API 키, R2 자격증명


---

_이 문서는 2026-03-19 기준 프로젝트 5000의 기술 현황을 정리한 것입니다. 코드 변경 및 데이터 보강에 따라 업데이트가 필요합니다._

---

## 12. 2026-03-19 추가 업데이트 (3차)

### 12.1 GAP 키워드 자동 동기화 파이프라인

**스크립트**: `/Users/twinssn/Projects/5000/scripts/sync_golden_to_gap.py`

news-keyword-pro 프로젝트가 매일 생성하는 golden CSV(`/Users/twinssn/Projects/news-keyword-pro/output/csv/golden_YYYY-MM-DD.csv`)를 읽어 gap.db에 자동 upsert합니다.

**필터 조건**: 카테고리 맵 기반 허용(자동차 카테고리 제외), 블랙리스트 정규식(다시보기, ev2, 실구매가, 출고가, 견적, 브랜드명 등), 월간 검색량 1,000~100,000, 포화도 0.5 이하, 블로그수 10,000 이하, 난이도 🟢만 통과, 키워드 길이 4자 이상.

**우선순위 자동 계산**: 검색량 5,000 이상 + 포화도 0.2 이하 → P1, 검색량 3,000 이상 → P2, 나머지 → P3. 기존 키워드의 우선순위가 낮으면 자동 업그레이드.

**이중 실행 구조**: (1) news-keyword-pro/daily_run.sh 끝에서 CSV 생성 직후 1차 동기화, (2) 5000 scheduler.py 매일 05:00에 `_run_gap_keyword_sync()` 2차 백업 동기화. INSERT OR IGNORE로 중복 실행 안전.

**백필 결과**: 75일치(2026-01-04~03-19) 백필 완료, gap.db 총 499개 키워드(P1: 282, P2: 83, P3: 92, P5: 42). 일일 5건 기준 약 100일치 재고.

**키워드 중복 수집 이슈**: news-keyword-pro의 포화도 필터 기준이 고정이라 동일 키워드가 반복 통과됨. 다음 스테이지에서 키워드 수집 소스 다변화 필요(네이버 데이터랩, Google Trends, 실시간 급상승 검색어, 커뮤니티 크롤링).

### 12.2 GAP 발행 품질 개선

**WordPress featured image 자동 설정**: wp_publisher.py에 R2 썸네일 URL → WP 미디어 업로드 → featured_media 설정 로직 추가. 파일명은 한글 인코딩 에러 방지를 위해 MD5 해시 기반(`gap-{hash}.webp`).

**WordPress 자동 카테고리**: pipeline.py에 `WP_CATEGORY_MAP` 딕셔너리 추가. gap.db 키워드의 category를 WP 카테고리 ID로 매핑(생활정보→150, 여행→149 등). publisher.py가 `wp_category` 파라미터를 받아 `publish_to_wordpress()`에 전달.

**내부링크 자동 삽입**: `pipelines/gap/internal_links.py` 신규 생성. kuta-wordpress의 entities.db(1,326개 엔티티)에서 service/life_info 타입 86개를 로드, 본문에서 엔티티명과 매칭되는 첫 등장에 내부링크 자동 삽입(최대 3개). `<a>` 태그 내부는 건너뛰는 안전 로직 포함.

**CTA 블록 자동 삽입**: 카테고리별 CTA 맵(rotcha.kr, informationhot.kr, techpawz.com 트래픽 유도)으로 글 하단에 관련 CTA 2개 자동 삽입.

### 12.3 travel1-hugo 빌드 에러 수정

**원인**: 빈 `categories:` front-matter 24건 + `- 축제` 잔여 항목으로 YAML 파싱 에러(`non-map value is specified`).

**수정**: 빈 categories를 `['여행']`으로 일괄 변경, 잔여 리스트 항목 제거(23건), "강원-축제행사" 포스트 front-matter 수동 재작성(1건). 빌드 성공 확인(94 KO pages).

### 12.4 LAP 배포 방식 변경 (git push → Wrangler)

**대상**: `/Users/twinssn/Projects/LAP/publishers/hugo.py`

git add/commit/push 방식을 Hugo 빌드(`hugo --gc --minify`) + Wrangler Pages 배포(`wrangler pages deploy ./public`)로 변경. config.py에 cf_project 추가: rotcha → `rotcha-blog`, informationhot → `informationhot-hugo`.

**결과**: rotcha-blog 배포 성공 확인(`https://4560e962.rotcha-blog.pages.dev`).

### 12.5 텔레그램 알림 개선

5000 프로젝트의 `shared/telegram_notifier.py`의 `send_error()` 함수가 blogs.yaml에서 domain과 repo 정보를 읽어 에러 메시지에 포함하도록 수정. 에러 발생 시 해당 블로그의 도메인과 로컬 레포 경로를 즉시 확인 가능.

### 12.6 카테고리 분포 (gap.db, 499건 기준)

여가/축제 29, 세금/재테크 19, 여행/축제 15, 행정/민원 14, 세금/납부 13, 금융/부동산 11, 여행/자연 10, 엔터테인먼트 10, 스포츠/야구 10, 생활/보조금 10, 여행/항공 9, 자동차/교통 8, 생활정보 8, 생활/행정 8, 건강/복지 7, 고용/취업 4 (일부 카테고리 명명 규칙 중복 존재: 여가/축제↔여행/축제, 세금/재테크↔세금/납부, 생활/행정↔행정/민원)

---

_3차 업데이트: 2026-03-19 작업 완료 내역 반영_

### 12.7 blogdex D1 → gap.db 키워드 연동

**스크립트**: `/Users/twinssn/Projects/5000/pipelines/gap/keyword_sync.py`

blogdex 프로젝트의 Cloudflare D1 API(`https://blogdex-api.hugh79757.workers.dev`)에서 Bing Webmaster 키워드를 조회하여 gap.db에 자동 upsert합니다.

**blogdex daily_sync 현황**: blogdex는 매일 06:00에 launchd(`com.blogdex.daily-sync.plist`)로 실행되며, 3개 Google 계정(twinssn, mdddmddd0322, udcho622)의 Bing Webmaster API에서 40개 이상 사이트, 약 2,500개 키워드를 수집하여 D1에 저장합니다. GSC 스냅샷은 단일 계정 19개 사이트만 수집하며, 대부분 신규 사이트라 데이터가 적습니다. GA4 데이터도 수집(2,920건, 5,130 PV, $21.88).

**keyword_sync.py 필터링 로직**: D1에서 최대 1,000건 조회 → GAP 적합성 검사(제외 패턴: 번역기, 게임, 다시보기, 누누티비, 르노필랑트, 5090, ev2 등) → 고가치 패턴 매칭(신청, 방법, 발급, 보험, 대출, 보조금, 추천, 비교, 후기 등) → 노출 3건 이상 → 우선순위 자동 계산(노출 100+ → P1, 20+ 또는 순위 5~20 → P2, 나머지 → P3) → 카테고리 자동 분류(세금, 금융/부동산, 행정/민원, 건강/복지 등).

**초기 실행 결과**: 1,000건 조회 → 36건 후보 → 31건 신규 추가, 5건 스킵. 이후 부적합 키워드 19건 제거(다시보기, 누누티비 등). 최종 gap.db 94건(당시 기준, 이후 golden CSV 백필로 499건까지 증가).

**키워드 수집 소스 다변화 과제**: 현재 news-keyword-pro golden CSV와 blogdex D1 Bing 키워드 2개 소스에 의존. 포화도 필터 고정으로 동일 키워드 반복 수집 문제 있음. 다음 스테이지에서 네이버 데이터랩 트렌드, Google Trends, 실시간 급상승 검색어, 커뮤니티 크롤링(뽐뿌, 클리앙, 디시인사이드 등) 추가 필요.

**blogdex GSC 스냅샷 이슈**: gsc_snapshot.py와 daily_sync.py가 동일 파일명(`gsc_YYYY-MM-DD.json`)으로 스냅샷을 저장하며, 먼저 생성된 쪽이 우선됨. SITES 리스트가 19개로 하드코딩되어 있어 신규 사이트(5000 프로젝트 블로그 등) 미반영. 향후 SITES 리스트를 blogs.yaml 또는 D1에서 동적으로 로드하도록 개선 필요.

### 12.8 Bing Webmaster 트래픽 현황 (2026-03-10 ~ 03-16)

5000 프로젝트 블로그 16개 중 Bing에 48개 사이트가 등록되어 있으며 (life.informationhot.kr 1개만 미등록, inactive라 무시), 주간 트래픽은 다음과 같습니다.

**주간 합계**: 클릭 153, 노출 13,905, 일평균 클릭 21.9

**사이트별 (노출 기준 상위)**: rotcha.kr 클릭 113 / 노출 9,618 (LAP 자격증), informationhot.kr 클릭 22 / 노출 2,181 (TAP 생활정보), kuta.informationhot.kr 클릭 14 / 노출 1,915 (TAP+GAP), hotissue.rotcha.kr 클릭 2 / 노출 110 (CAP 핫이슈), ud.informationhot.kr 클릭 2 / 노출 36, stock.informationhot.kr 노출 29, tv-show.informationhot.kr 노출 16.

**미반영 사이트**: travel1~2, tour1~3, tco, deal, compare, guide, ev — 신규 사이트로 Bing 인덱싱 진행 중. 콘텐츠 누적에 따라 노출 증가 예상.

**트래픽 추적 방법**: blogdex D1 API(`/bing/daily`)에서 일별 클릭/노출 데이터 조회 가능. 향후 텔레그램 일일 리포트에 Bing 트래픽 요약 추가 예정.

**Bing 전략**: Google 인덱싱 미진으로 Bing에 집중. 3개 계정(twinssn, mdddmddd0322, udcho622)으로 48개 사이트 등록 완료. sitemap 자동 제출은 Hugo 빌드 시 생성되는 sitemap.xml로 Bing이 자동 크롤링.

---

## 13. 공공데이터 API 현황 (2026-03-19 테스트 완료)

### 13.1 API 키 위치

| 키 이름 | 파일 | 용도 |
|---|---|---|
| `DART_API_KEY` | `.env` | DART 전자공시 (기존) |
| `FINLIFE_API_KEY` | `.env` | 금감원 금융상품한눈에 |
| `DATA_GO_KR_API_KEY` | `.env` | 공공데이터포털 통합키 |

### 13.2 동작 확인된 API (9개)

| # | API명 | 엔드포인트 | 상태 | 블로그 매핑 |
|---|---|---|---|---|
| 1 | DART 전자공시 | `https://opendart.fss.or.kr/api/list.json` | OK | stock |
| 2 | 금감원 정기예금 | `http://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json` | OK (37건) | finance |
| 3 | 금감원 적금 | `http://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json` | OK (56건) | finance |
| 4 | 주식배당정보 | `http://apis.data.go.kr/1160100/service/GetStocDiviInfoService/getDiviInfo` | OK | dividend |
| 5 | 증권상품시세(ETF) | `http://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo` | OK (1,065,055건) | etf |
| 6 | KRX상장종목정보 | `http://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo` | OK (3,887,864건) | 공통 |
| 7 | 지수시세정보 | `http://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex` | OK (234,180건) | sector |
| 8 | 주식발행정보 V2 | `http://apis.data.go.kr/1160100/service/GetStocIssuInfoService_V2/getItemBasiInfo_V2` | OK | ipo |
| 9 | 주식권리일정정보 | `http://apis.data.go.kr/1160100/service/GetStocRighScheService/getRighExerReasSche` | OK | dividend, ipo |

### 13.3 기업재무정보 V2 (3개 오퍼레이션)

서비스: `GetFinaStatInfoService_V2` (주의: `FinaStat`이며 `FinStat`이 아님)

| 오퍼레이션 | 용도 | 상태 |
|---|---|---|
| `getBs_V2` | 재무상태표 (자산, 부채, 자본) | OK |
| `getIncoStat_V2` | 손익계산서 (매출, 영업이익) | OK |
| `getSummFinaStat_V2` | 요약재무제표 (매출, 영업이익, 당기순이익 일괄) | OK |

### 13.4 미해결 API (1개)

| API명 | 서비스명 | 상태 | 비고 |
|---|---|---|---|
| 공시정보 V2 | `GetDiscInfoService_V2` | 오퍼레이션명 미확인 | DART API로 대체 가능, 우선순위 낮음 |

### 13.5 블로그별 데이터 소스 매핑

| 블로그 | 도메인 | 데이터 소스 | 일 5건 가능 |
|---|---|---|---|
| stock-hugo | stock.informationhot.kr | DART공시 + 기업재무V2 + KRX상장종목 | O |
| dividend | dividend.techpawz.com | 주식배당정보 + 권리일정 + 기업재무V2 | O |
| etf | etf.techpawz.com | 증권상품시세(ETF) + KRX상장종목 + 지수시세 | O |
| sector | sector.techpawz.com | 기업재무V2 + 지수시세 + KRX상장종목 + 네이버업종(129개) | O |
| ipo | ipo.techpawz.com | 주식발행V2 + 권리일정 + DART공시 | O |
| finance | finance.techpawz.com | 금감원 finlife(예금37+적금56) + 한국은행ECOS | O |

### 13.6 공공데이터포털 API 디버깅 가이드

동일 기관(금융위원회) API라도 서비스명·오퍼레이션명이 제각각이므로 404 발생 시 아래 순서로 대응:

1. **상세페이지 HTML에서 실제 엔드포인트 추출**: `re.findall(r'apis\.data\.go\.kr/[^\s<"]+', html)` — 문서에 적힌 URL과 실제 URL이 다른 경우가 많음.
2. **서비스명 오타 주의**: `FinStat` vs `FinaStat`, `StocRighScheInfo` vs `StocRighSche` 등 한 글자 차이.
3. **V2 suffix**: 최신 API는 서비스명과 오퍼레이션 모두 `_V2` 필요 (예: `GetFinaStatInfoService_V2/getBs_V2`).
4. **http vs https**: 일부 API는 http에서만 동작.
5. **활용신청 별도 필요**: 같은 기관이라도 API별로 개별 신청, 자동승인이지만 반영에 1~2분 소요.
6. **응답 본문 확인**: HTTP 200이어도 `resultCode`가 에러인 경우 있음 — 필수 파라미터 누락 등.

_4차 업데이트: 2026-03-19 공공데이터 API 테스트 완료_
