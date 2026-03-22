# SEAP (Senior Auto Publisher) 기술문서

_최종 업데이트: 2026-03-22_

---

## 1. 프로젝트 개요

SEAP는 5000 Dispatcher의 하위 파이프라인으로, 공공데이터포털 API(10,918건)에서 시니어 복지 서비스를 수집하여 블로그 글을 자동 생성·발행한다.

### 데이터 흐름
공공데이터포털 API -> fetcher.py (키워드 필터, 중복 제거) -> writer.py (GPT-4o-mini) -> pipeline.py (Hugo + Wrangler 배포)

### 시스템 위치
5000 Central Dispatcher 내 CAP(Car), TAP(Tour), STAP(Stock), GAP(General)과 병렬로 SEAP(Senior)가 senior.informationhot.kr에 배포된다. 확장 예정: youth, parenting, housing 등.

---

## 2. 파일 구조

프로젝트 루트: /Users/twinssn/Projects/5000/pipelines/senior/ (fetcher.py, writer.py, pipeline.py)
사이트 루트: /Users/twinssn/Projects/senior-hugo/ (hugo.yaml, content/posts/, themes/blowfish/)

---

## 3. 데이터 소스

공공서비스(혜택) API: https://api.odcloud.kr/api/gov24/v3/serviceList, 인증키 DATA_GO_KR_API_KEY, 전체 10,918건, 시니어 필터 후 약 800건 고유 서비스, 수집 약 90초.
노인일자리 API: http://apis.data.go.kr/B490007/sjfd100/sjfd100, 현재 500 오류.

---

## 4. 필터링 로직

SENIOR_KEYWORDS: 노인, 고령, 65세, 어르신, 시니어, 기초연금, 장기요양, 경로, 치매, 임플란트, 틀니, 요양원, 요양급여, 국민연금, 에너지바우처, 난방비, 주거급여, 경로우대, 노인맞춤돌봄, 노인일자리, 배회감지기, 치매안심, 개안수술, 인공관절.

EXCLUDE_KEYWORDS: 유아, 영유아, 어린이, 유치원, 임산부, 발달장애, 청소년, 아동, 어선, 어업, 귀어, 귀산촌, 국가유공자, 감염병, 해산급여, HIV, AIDS, 자활근로, 출산크레딧, 장애인 활동지원, 차상위 본인부담, 영아, 태아, 신생아, 모자보건, 산후조리.

카테고리 분류 우선순위: 의료지원 > 돌봄서비스 > 연금생활지원 > 교통복지 > 일자리금융 > 문화여가 > 생활지원(기본값).

---

## 5. 글 생성 (writer.py)

서비스 선택: 카테고리별 분류 -> 기발행 서비스 제외(content/posts 스캔) -> 데이터 풍부도 순 정렬 -> 미발행 최상위 선택.

프롬프트: system(시니어 전문 블로거, anti-hallucination 규칙 6개), user(서비스 데이터 블록 + 관련 3건 + 카테고리별 H2 6개).

품질 검증: 본문 2000자+, H2 4개+, 빈문장 3회 이하, 미달 시 1회 재생성.

---

## 6. blogs.yaml 설정

id: senior-hugo, pipeline: senior, platform: hugo, daily_quota: 5, domain: senior.informationhot.kr, schedule: 07:34/10:34/13:34/16:34/20:34.

---

## 7. 2026-03-22 수정 이력

fetcher.py: fetch_all 중복 호출 제거(170건->17건 고유), 전체 페이지 스캔(3->110페이지, 17->약800건), EXCLUDE_KEYWORDS 보강, 카테고리 분류 순서 수정(보건소->돌봄서비스, 기초연금->연금생활지원).
writer.py: _select_service에 published 파라미터 추가, 기발행 서비스 회피 로직.
pipeline.py: _get_published_services 함수 추가.
콘텐츠 정리: 42건->11건(31건 중복/오분류 삭제).

---

## 8. 확장 전략

공공서비스 API 10,918건을 대상별 키워드로 필터링하면 다른 블로그 라인 생성 가능: 육아(약500건), 청년(약400건), 장애인(약300건), 주거(약200건). 공통 모듈 리팩토링 후 키워드+프롬프트만 교체.

---

## 9. 알려진 이슈

노인일자리 API 500 오류, serviceDetail API 미연동, 썸네일 모듈 미연결, GA4/GSC 데이터 0(신규 색인 대기), 전체 스캔 90초(캐싱 미구현).
