# WL-20260823-etap-phase2-standardization

## 작업 개요
ETAP 36개 블로그 Blowfish 표준 통일(Phase 2 확산). 표준 지침서: `5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` v1.3 (커밋 6c37f3701). 기준 구현체: foodtour-hugo (라이브 검증됨, 지침서 금기사항 전부 준수 확인).

## 변경 내역
- custom.css (foodtour 신버전: 로고테두리 제거+H2가드) → 34개 블로그 복사
- extend-head.html 정규화 → 5개 (citytours deals nomad eurail phototour); michelin 제외(Track C Task 6 신버전), airports 별도
- eurail/phototour root hugo.toml에 `[params] ga4_measurement_id = "G-N4Q99745QT"` 추가 (기존 하드코딩 폴백 대체 — 미추가 시 GA 중단)
- nomad related.html 복원
- airports 온보딩: 신규 7파일 + single.html/extend-head.html 교체 (기존 AdSense 로더 전무 상태 해소)

## 실행 실적
- 복사 49건 (40+airports 9), 백업 .bak_phase2 43개
- Hugo 빌드 36/36 통과
- 배포 35/36 성공 — flights만 W5 이미지 게이트 차단(기존 글 2건 R13 본문삽입이미지 0장, Phase 2와 무관한 선존재 문제)
- cf_project 함정: Pages 프로젝트명은 `{name}-hugo` (bare name → "project does not exist" 오류)

## 라이브 검증 (13 기준 도메인 최신 포스트)
- adsbygoogle.js 로더(ca-pub-8772): 13/13 ✓ (airports 포함 — 신규 활성화)
- custom.css font-size:inherit: 12/13 (flights=구버전 번들, 배포 차단 반영)
- disclosure: 조건부(제휴링크 보유 글만) — foodtour/eurail/daytrips/airports/esim/nomad 확인

## 실수 기록
- eurail/phototour hugo.toml 백업을 append 후 생성 → 백업 무효. 원본은 git 이력으로 복구 가능
- 첫 배포 시도: bare project name 오류 + blogs 목록에서 foodtour 누락 → 수정 후 재실행

## 잔존 위험
- flights-hugo 미배포 (W5 게이트 — 콘텐츠 수정 후 재배포 필요)
- michelin top.html 비활성·extend-head 신버전 유지 (의도, 문서§3.2와 구조 상이)
- head/custom.html 전 플릿 하드코딩 pub ID (금기#10 위반하나 전부 동일+검증됨 — 별도 과제)
- tour head/custom.html 결여 (extend-head가 로더 담당 — 기능 영향 없음)
- michelin _default/_markup/render-link.html 오위치 중복 (데드파일, 미삭제)
