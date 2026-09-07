# WL-20260907 — ETAP H2-GUARD 영어 강등 해제 + affiliate 카드 마크업

**날짜:** 2026-09-07
**작업 유형:** 코드 수정 [PRODUCTION] + 라이브 콘텐츠 일괄 변환 (파괴적) + 14 블로그 재배포
**Quick task:** `.planning/quick/260906-etap-h2-guard-affiliate-btn/`

## 배경

watersports-hugo 마지막 발행글 분석에서 발견:
1. 영어 블로그임에도 H2가 전부 `<strong>`으로 강등 — shared hugo_writer.py의 H2-GUARD가 한국어 전용 허용 패턴이라 영어 H2 전부 강등
2. Viator 카드의 Book Now 링크가 plain 텍스트 — `.affiliate-btn` 파란 버튼 CSS가 custom.css에 존재하는데 마크업이 미사용

## 변경 내역

### FIX #1 [PRODUCTION] hugo_writer.py H2-GUARD 영어 바이패스
- `_ALLOWED_H2_RE` 컴파일 후 `_has_hangul = bool(re.search(r"[\uAC00-\uD7A3]", body_md))` 감지
- `_fix_invalid_h2()`: 한글 없으면 `return match.group(0)` (원본 유지)
- 최종 `re.sub` 강등 라인: `if _has_hangul:` 조건부 실행
- 한국어 블로그(rap/stap/car/커리에이션) 로직 무변경 — 테스트 3 케이스 PASS (영어 보존/한국어 강등 유지/한국어 허용 패턴 생존)

### FIX #2 [PRODUCTION] post_processor.py insert_product_cards() 마크업
- 각 카드를 `<div class="affiliate-card">...</div>`로 감쌈
- Book Now 링크에 `class="affiliate-btn"` 부착 → 파란 버튼 CSS 적용
- 기존 `.etap-product-cards` wrapper, `etap-card-title` h2 유지
- 검증: 테스트 렌더 — 카드 2/div 균형 3/Travel Tips 앞 삽입/중복방지 True

### FIX #3 라이브 콘텐츠 일괄 변환 (파괴적, 4단계 프로토콜)
- **대상:** ETAP 14 블로그 (watersports/bus/multiday/tours/transfers/walking/citytours/culture/escape/ghost/layover/luxury/nightlife/watertours) — shared hugo_writer 경유 블로그
- **사전 카운트:** 강등 H2 4,196개 / 1,084 파일 (단독 라인+앞뒤 빈줄 판별 규칙, 정밀 샘플에서 other=0 오분류 없음 확인)
- **백업:** `/tmp/etap_h2_backup_20260907000338.tar.gz` (6.6MB, 14사이트 content 트리)
- **실행:** `<strong>X</strong>` 단독 라인 → `## X` 변환 4,196개 (링크 포함 H2도 정상 변환 — Playa del Carmen 사례)
- **사후:** 잔여 강등 H2 0 (dry-run 재측정 0), 강등 아닌 strong(가격 `$449`/disclaimer/인라인) 무변경 — 판별 규칙이 앞뒤 빈줄+단독라인만 변환하므로 인라인 strong은 원본 유지
- **FIX #3b:** 기존 포스트 Book Now 링크 2,573개에 `class="affiliate-btn"` 부착 (rel="sponsored noopener" target="_blank" 패턴 정확 매칭, 사전 grep 카운트와 일치)

### 배포
- 14 블로그 Hugo 재빌드 + Pages 재배포 2회차 (H2 변환 후 1회, btn 클래스 후 1회) — 전부 rc=0
- deploy_site() 사용, CLOUDFLARE_API_TOKEN 추출 관례 준수

## 검증 분류

- [검증됨] FIX #1 H2-GUARD 바이패스 — 직접 테스트 3 케이스 PASS. 근거: 영어 H2 보존 + 한국어 강등 유지 + 한국어 허용 패턴 생존
- [검증됨] FIX #2 카드 마크업 — 테스트 렌더 카드 2/버튼 2/div 균형/중복방지 True
- [검증됨] FIX #3 강등 H2 변환 — dry-run 사전 4,196 = 적용 4,196 = 잔여 0. 근거: tmp_h2_restore.py 3회 실행 (dry/apply/dry)
- [검증됨] FIX #3b btn 부착 — dry-run 2,573 = grep 사전 카운트 2,573 = 적용 2,573 = 잔여 0
- [검증됨] py_compile 2 파일 PASS
- [검증됨] 관련 테스트 — post_processor/hugo_writer/h2 관련 7 passed + test_preflight_c01 단독 PASS (OPS_TEST_MODE 필요한 conftest 가드는 환경 이슈, C06 ImportError는 사전 존재)
- [검증됨] 라이브 검증 — watersports.techpawz.com/playa-del-carmen H2 7개 렌더링 (`<h2 class="relative group">...`), affiliate-btn 5개 라이브, bus.techpawz.com 잔여 강등 strong 0
- [부분검증] 14 블로그 전체 라이브 — watersports/bus/citytours 홈 HTTP 200 + watersports 상세 페이지 정밀 검증. 나머지 11개는 배포 rc=0만 확인. 제한 사유: 전 포스트 크롤링 미수행
- [부분검증] 발행 파이프라인 반영 — 다음 스케줄 발행 시 신규 포스트에 H2+버튼 적용 여부는 미래 이벤트

## 잔존 위험

- **[부분검증] 11 블로그 라이브 상세 미검증** — 배포는 성공(rc=0)했으나 개별 포스트 HTML 확인 안 함. 대응: 다음 발행 사이클에서 대시보드/H2 체크로 확인 가능
- **404 칩 링크 리스크** — playa-del-carmen H2 내부 `tours.techpawz.com/posts/best-tours-playa-del-carmen/` 크로스셀 링크 존재. 원래부터 있던 링크로 변환 무관하나, 링크 대상 포스트 존재 여부 미확인
- **스케줄러 재발행 시 신규 포스트 검증 필요** — FIX #1/#2는 발행 시점에 적용되므로 다음 watersports 발행(오늘 예정)에서 H2 생존+버튼 확인 필요
- tmp 스크립트 2종 (`tmp_h2_restore.py`, `tmp_btn_class.py`) 미삭제 — 재사용 가능성 있어 유지 (5000/scripts/)

## 배포 로그

logs/destructive_2026-09-06.log 2건 append (H2 복원+btn 부착 / 재배포 2회차)
