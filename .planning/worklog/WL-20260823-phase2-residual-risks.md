# Phase 2 잔존 위험 문서 (WL-20260823-phase2-residual-risks)

> 작성: 2026-08-23 / Phase 2 ETAP 36블로그 표준화 마감 시점 기준
> 상위 worklog: WL-20260823-etap-phase2-standardization.md

## R1. flights 재배포 상태 — 해소됨
- 초기 배포 차단 원인: W5 이미지 게이트 (기존 글 2건 `cheapest-flights-den-to-pns`, `cheapest-flights-atl-to-cvg` 본문삽입이미지 0장)
- 조치: `pipelines/etap/image_fetcher.fetch_body_images`(Pexels/Unsplash→R2 webp) + `flight_pipeline._insert_body_images`로 각 1장 삽입, 백업 `.bak_img_fix`
- 결과: 빌드·배포 성공, 라이브 `<img>` 태그 양쪽 1개씩 확인
- **잔여**: 동일 패턴(본문 이미지 0장) 포스트가 flights에 수십 건 존재(예: sea-to-* 계열 다수). 게이트는 최근 3일 발행분만 검사하므로 신규 발행 시에만 걸림. 대량 보강은 별도 과제

## R2. head/custom.html pub ID 하드코딩 (금기#10 위반, 별도 과제)
- 35개 블로그의 `layouts/partials/head/custom.html`이 `ca-pub-8772455780561463`을 하드코딩해 adsbygoogle.js를 이중 로드(head/custom + extend-head)
- 현재 ID는 techpawz 계열 정답(8772)이라 즉각 장애 없음. 그러나 계정 이전 시 36곳 수정 필요 + 지침서 금기#10("extend-head.html에 하드코딩된 Publisher ID 금지")와 충돌 구조
- 권고: head/custom.html에서 로더 제거하고 extend-head(params 경유) 단일화하는 별도 태스크

## R3. tour-hugo head/custom.html 결여 (기능 영향 없음)
- tour-hugo만 해당 파일 없음. extend-head가 로더 담당하므로 광고 기능 정상(라이브 검증 ✓)
- 플릿 통일 관점에서는 파일 추가가 "완전 일치"이나 무변경 원칙상 방치. R2 과제 수행 시 자연 해소

## R4. michelin render-link.html 데드파일
- `michelin-hugo/layouts/_default/_markup/render-link.html` 오위치 중복 존재(정석 위치 `layouts/_markup/`도 정상 보유). Hugo가 로드하지 않는 사실상 데드파일
- michelin 일체 수정 금지 제약으로 미삭제. 삭제 시 Hugo 빌드 영향 없음이 예상되나 별도 확인 후 진행할 것

## R5. eurail·phototour hugo.toml 백업 타이밍 실수 (git 복구 가능)
- `[params] ga4_measurement_id` 추가를 먼저 실행하고 `.bak_phase2` 복사가 뒤에 실행됨 → 백업이 이미 변경된 상태를 담음(무효)
- ETAP은 git 저장소가 아니므로 파일 백업이 유일 롤백 수단인데 이 2건은 백업 무효
- 완화: 원본은 4~7줄의 극단적으로 단순한 파일(baseURL/theme/themesDir/enableRobotsTXT)이며 추가분 3줄 제거로 수동 복구 가능. 참고로 5000 저장소에는 원본 구조가 기록된 커밋 존재(16c502e12 이전 세션 문서들)
- 교훈: 백업은 변경 전에. 향후 ETAP git init 권고

## R6. 지침서 §3.3 underscore 불일치 (갱신 후보)
- 문서 v1.3 주장: "Blowfish가 extend_head.html(underscore)도 로드한다"
- 실태: `shared-themes/blowfish/layouts/partials/head.html`은 `extend-head.html`(hyphen)과 `extend-head-uncached.html`만 참조. underscore 버전은 어디서도 로드되지 않음(데드코드)
- 실증: foodtour extend_head = "DEPRECATED" 스텁인데 GA4가 정상 동작(GA 코드는 extend-head 하이픈 쪽에 존재), 반대로 michelin은 extend_head에 twitter:card 활성 코드가 있으나 렌더링되지 않음
- 권고: 지침서 §3.3 갱신(underscore 불로드 명시) — 단, shared-themes/blowfish 직접 수정이 아닌 문서 수정으로 처리

## 선언
Phase 2 확산+마감: 36/36 빌드 성공, 36/36 배포 성공(flights는 이미지 보강 후 재배포 포함), 라이브 샘플 검증 통과 → **COMPLETE**
