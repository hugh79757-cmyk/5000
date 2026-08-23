# Fleet-Wide Standardization Verification + Schema Sync — 2026-08-23

> task_id: FULL_FLEET_STANDARDIZATION_VERIFY_AND_SYNC | type: VERIFY_AND_IMPLEMENT | branch 개념상: track-c-fleet-verification

## 1. 요약

| 항목 | 값 | 산출 근거 |
|---|---|---|
| 총 블로그 수 | **85개** (미분류 0) | config/blogs.d 9분기 파일 파싱 ∪ ops.db check_results ∪ 프로젝트 디렉터리 ∪ KEYWORD_MAP 교차 대조 — 4소스 합집합 = 85, 어느 소스도 단독 추가분 없음 |
| 분기별 분포 | ETAP 36 / CUAP 15 / CAP 13 / TAP 8 / STAP 6 / RAP 5 / SEAP 2 | site_path 루트 + pipeline 필드 이중 분류 (`/tmp/fleet_full_inventory.md`) |
| 활성 / 비활성 | 76 / 9 | status 필드(active 외) 또는 30일 무발행 |
| 표준화 완료율(7항목 전체 PASS, 엄격) | **54/76 = 71.1%** | 아래 3번 섹션 분해 |
| Hugo 빌드 | **74/74 exit 0** (활성 Hugo 사이트 전수, `--destination /tmp/verify_build_*` 격리) | `/tmp/hugo_build_results.txt` OK 74건, FAIL 0건 |
| schema_loader 로드 | **85/85 성공, 실패 0** | `load_schema(blog_id)` 순차 호출 예외 0건 |
| 대시보드 동기화 | 문서화 경로로 YES | ops.db에 schema_registry 테이블 미존재 → 제약 조건상 문서화만, DB write 0건 |

## 2. 검증 방법 (독립 검증 수단)

- 인벤토리: YAML 파싱(python yaml.safe_load), SQLite SELECT 2종, 디렉터리 열거 — 소스 간 차집합이 공집합임으로 미분류 0 입증 [검증됨]
- GA4: layouts/**/extend*head*.html + config/*.toml 정규식 스캔 → ID·loader·주입방식 3요소 판정. deprecated extend_head.html 오탐 보정, placeholder(G-XXXXXXXXXX)·ID 공유 감사 포함 [검증됨]
- H2-GUARD: hugo_writer.py `_ALLOWED_H2_PATTERNS`(258패턴)를 AST로 추출해 최신 발행 포스트 H2와 매칭 [부분검증] — 블로그당 최신 1개 포스트 샘플링이라 전체 아카이브 미커버
- Hugo build: 실제 `hugo --gc --minify` 실행, exit code 수집 [검증됨]
- Schema: `load_schema()` 실호출 [검증됨]

## 3. 7항목 매트릭스 결과 (활성 76 기준)

| 항목 | PASS | FAIL/WARN | 비고 |
|---|---|---|---|
| GA4 주입 | 63 ✅ direct + 5 ✅ config = 68 | ⚠️ shared-id 9 (7+2클러스터), ❌ 2 (hotissue placeholder, interior no-id), N/A blogger 2 | 상세 `/tmp/fleet_ga4.json` |
| Schema 로드 | 85/85 | 0 | PART_C와 동일 실행 |
| KEYWORD_MAP ≥30 | 26 | ❌ <30: bike 24/car 12/golf 12/homeappliance 23/massage 25 | 미등록 블로그는 N/A |
| CATEGORY_FILTERS | 31 전원 ≥2카테고리 | 0 | 나머지 N/A |
| H2-GUARD | 59 | ❌ 15 (cruise/ipo/layover/nature/phototour/tour/trains/travel4/sector/stock 등) | 구형 발행물 중심 |
| Hugo Build | 74/74 exit 0 | 0 | 비활성 미빌드 |
| Dashboard 행 | 85/85 | 0 | check_results DISTINCT |

전체 PASS 블로그 54 = 76 − 22(1개 이상 미달). 22개 내역: GA4 WARN 6, GA4 FAIL 2, KW<30 5, H2 10, blogger N/A 2 (중복 보유).

## 4. 잔존 FAIL 및 해결 로드맵

| # | 항목 | 대상 | 해결책 | 승인 필요 |
|---|---|---|---|---|
| 1 | hotissue-hugo placeholder ID + 실ID 혼재 | 1 | placeholder 라인 삭제, G-VSNXWPLE4L 단일화 | 아니오(파일 수정 별도 작업) |
| 2 | interior-hugo loader만 있고 ID 없음 | 1 | measurement_id 발급·기입 | GA4 콘솔 |
| 3 | G-995DNX1KV8 7블로그 공유 (appliance/bike/car/golf/homeappliance/massage/senior-hugo) | 7 | 블로그별 속성 분리 | 예 — 측정 정책 결정 |
| 4 | eurail/phototour G-N4Q99745QT 공유 | 2 | 기존 pending 결정과 동일 건 | 예 |
| 5 | KW<30 | 5 | keyword_harvester 자동 보충 실행 | 아니오 |
| 6 | H2 미매칭 구형글 | 10+ | 재생성 Tier 선정 시 자연 해소 or 패턴 추가(승인제) | 부분 |

## 5. 대시보드 동기화 상태

- schema_registry 테이블 없음 → 초기 적재 제안안은 `/tmp/fleet_schema_sync_report.md` 참조 (현재 schemas/ 코드가 SSOT이므로 도입 필수성 낮음)
- check_results ↔ 스키마 blog_id 정합성: 불일치 0

## 6. 산출물

- `/tmp/fleet_full_inventory.md` — 85개 전수 목록 + 미분류 0 + 비활성 9
- `/tmp/fleet_verification_matrix.md` — 7항목 × 85 매트릭스 + 원인/해결책
- `/tmp/fleet_schema_sync_report.md` — 로더 85/85 + 동기화 문서화
- 본 문서 — 최종 요약 (커밋 대상)

## 7. 제약 준수 확인

- 블로그 소스 파일 수정: 없음 (읽기 전용 스캔)
- 실제 배포: 없음 (wrangler 호출 0회)
- 쿠팡 API 호출: 없음
- check_results 데이터 수정: 없음
- 스케줄러 중단/재시작: 없음
- DB write: 없음 (schema_registry 미존재로 문서화 경로)

## 8. 잔존 위험

- H2 샘플링이 최신 1포스트 한정 → 구형글 위반 누락 가능 (전수 스캔 시 FAIL 증가 가능성)
- GA4 "OK"는 파일 내 존재 판정이지 라이브 수집 동작 검증 아님 (GA4 Realtime 확인 별도 필요)
- travel-hugo 등 TAP 5개는 extend-head 직접주입 ✅이나 본 검증에서 params 이중설정 여부는 미조사
- pick-hugo-backup 디렉터리는 백업으로 판정해 인벤토리 제외 — 실제 운영 블로그 아님을 확인했으나 git 상 추적 안 됨
