# airports-hugo Deep Pass — CLOSED (2026-08-21)

## 상태
- `config/blogs.d/etap.yaml`: `status: disabled`, `daily_quota: 0` (기존 `paused` → 명시 비활성)
- 163개 포스트 전부 `noindex: true` 프런트매터 추가 (134건 신규 + 29건 기존 보유)
- 배포 경로 단일 이미지 게이트 `deploy._pre_deploy_image_gate`가 65건으로 차단 중

## 폐쇄 근거
- **정직 단어수 한계**: R15 정직단어수 측정 결과 lhr 111 / dme 111 / ewr 112 / 기타 172~224.
  모두 문턱 **400 미달**. Layer1 원시 소스(OpenFlights / OurAirports runways.csv /
  airline_routes) 자체가 박물관-style 팩트(좌표·고도·IATA·ICAO·Route Snapshot)
  위주라 산문 확장 재료가 구조적으로 부족 → 400 도달 불가.
- **문턱 하향 금지**(검산 게이트) → 회귀 없이 400을 맞출 수단 없음 → 폐쇄로 결론.

## 이미지 회귀 (회피)
- 실제 작성 주체: 미추적 PoC `.planning/airports_poc_20260821/`
  (stn-pilot.md / lil-pilot2.md / kdl-pilot3.md + airports.csv / routes.dat).
- PoC가 `featureimage` / 본문 `![...](r2 body_N.jpg)` 링크를 누락.
- R2 자산은 존재(`etap/{slug}/cover.jpg` 13/13, body 이미지 다수 존재) — 자산 결핍 아님.
- 복원 리비전 `b70392318`의 `featureimage:` / `![...]` emit 참조 가능.
- writer 수정 금지(게이트) → 폐쇄로 회귀 재발 방지.

## 미확정 사항 (세션 종결 지시대로 명기)
- **Y1[미확정]**: W("hotissue-images cover=NO") vs X("r2_uploader cover.jpg 존재") 충돌.
  실측에서는 X측(13/13 cover.jpg 존재, 버킷 불일치 아님)이 우세하나, 세션 종결로
  최종 확정은 보류하고 "미확정"으로 기록. (webp 부재 11/13 → THUMBNAIL-01 FAIL 정당성은 별개.)
- **Y2[미확정]**: writer 신원. `airports_writer.generate_airport_guide('STN')`는
  airline_routes=0 으로 guard(None) 반환 → STN 미작성. 실제 13건 작성 주체는
  미추적 PoC로 추정되나 경로 불명 → "미확정" 기록.

## 게이트 준수
- 재생성 금지 / 배포 금지 / 신규 규칙 추가 금지 — 모두 준수.

## 오늘 확정 수치 (2026-08-21 종결)
- airports 정직 단어수 111~224 — 문턱 400 전부 미달
- 라이브 wordCount: STN 359 · PEK 374 · KDL 302
- 오늘 발행 13건 전건: 본문 이미지 0장, og:image 부재
- 미쉐린 라이브 wordCount: median 947 · min 706
- 미쉐린 15건 중 어필리에이트 생존 2건(bath·ensenada), 나머지 13건 0
- 검증불가: 어필리에이트 사망 커밋 시점(미특정), tier 매칭 로그(보존 정책 부재)

## 백로그
- 미쉐린 어필리에이트 사망 시점 추적(bath·ensenada 16건 외 전부 0)
- twitter:card 템플릿 36블로그 적용
- 36블로그 per-post 광고·어필리에이트 실측
- CJK 누출 전수 grep
- tier 로그 보존 정책 부재
