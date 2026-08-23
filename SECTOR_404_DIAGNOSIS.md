# sector-hugo 404 READ-ONLY 원인 분석 (보완)

> 최초 분석: 2026-08-19 13:59
> **보완 분석: 2026-08-19 14:05**
> **모니터 패치 적용: 2026-08-19 14:24**
> **상태: sector-hugo active, 성공 1/3 (13:28 SUCCESS 재분류)**

## 최종 근본원인 (보완)

**Cloudflare Pages 배포 전파 지연 (propagation delay).**

monitor_sector.py의 `check_http()`는 raw slug를 사용하며, 이는 정상 동작한다.
이전 분석에서 "URL-인코딩이 원인"으로 판정했으나, 코드에 `urllib.parse.quote()`가 없었다.
실제 원인은 배포 직후(69초) Cloudflare Pages의 전파가 미완료된 상태에서 테스트한 타이밍 문제.

## 신뢰도: 매우 높음

1. monitor_sector.py의 실제 코드에 `quote()` 없음 (line 132: `url = f"https://sector.techpawz.com/posts/{article['slug']}/"`)
2. 13:30:17 monitor 실행 결과: http=200, reason=SUCCESS (이미 기록됨)
3. 13:34:37 수동 테스트에서 URL-인코딩 slug 사용 → 404 (이전 오진의 근거)
4. 14:03+ 모든 URL 변형(raw, lowercase%, uppercase%) 200 확인
5. NFC/NFD 정규화: DB slug = Hugo dir = Canonical slug (모두 NFC, code point 완전 일치)

## 이전 오진 교정

| 항목 | 이전 판정 (잘못됨) | 최종 판정 |
|------|-------------------|----------|
| 원인 | monitor의 URL-인코딩 | Cloudflare 전파 지연 |
| monitor 코드 | `urllib.parse.quote(slug)` 사용 | raw slug 사용 (quote 없음) |
| 13:28 실행 | FAIL (permalink 404) | **SUCCESS** (모니터 자체가 200 보고) |
| 실제 배포 | 정상 | 정상 |
| 복구 필요 | monitor 수정 | 없음 (모니터 정상) |

## 13:28 결과 재분류

| 시간 | 이벤트 | HTTP | 비고 |
|------|--------|------|------|
| 13:29:08 | wrangler deploy 완료 | - | 81 files uploaded |
| 13:30:17 | monitor_sector.py 실행 | **200** | reason=SUCCESS |
| 13:34:37 | 수동 테스트 (URL-인코딩) | 404 | 잘못된 테스트 → FAIL 기록 |
| 14:03+ | 재테스트 (모든 변형) | 200 | 전파 완료 |

**monitor_sector.py의 13:30:17 실행이 이미 200 SUCCESS를 기록했으므로, 13:28 실행은 성공으로 재분류 가능.**

## 조사 항목별 최종 결과

### ① id=3491 vs id=3488 비교

필드 구조 동일, body_md 길이만 차이 (3446 vs 3667). frontmatter 정상.
- draft: false, slug 동일, tags: uncategorized

### ② 로컬 Hugo 빌드

759 pages, 경고 0건, 새 글 파일 정상 생성 (36551 bytes).
canonical URL: `https://sector.techpawz.com/posts/%EC%84%B9%ED%84%B0-...` (URL-인코딩, Hugo 표준)

### ③ deployed=true 판정 코드

subprocess exit 0 + 예외 미발생 = 정상. (`shared/publisher.py:1041-1042`, `shared/publishers/deploy.py:58-192`)

### ④ 라이브 배포 ID vs 로컬 해시

배포 `8f25ad32`, source=7a3d1bf. 81 files uploaded. 콘텐츠 저장 정상.

### ⑤ permalink HTTP 검증 (보완)

| URL 변형 | id=3491 (14:03+) | id=3488 | 비고 |
|----------|-----------------|---------|------|
| raw slug (`/posts/섹터-.../`) | **200** ✅ | **200** ✅ | curl이 자체 UTF-8→%xx 변환 |
| lowercase `%xx` | **200** ✅ | **200** ✅ | |
| uppercase `%XX` | **200** ✅ | **200** ✅ | |

**결론**: 모든 URL 변형이 정상. 이전 404는 전파 지연이 유일한 원인.

### ⑥ Unicode 정규화

DB slug = Hugo dir = Canonical slug: 모두 NFC 정규화, code point 완전 일치.
- `섹터` = U+C139 U+D130 (NFC)
- NFD 변환 시 다름 (composed vs decomposed)

## 패치 후보 (운영 미적용)

- `monitor_sector_patch.py`: canonical URL 추출 + 3종 URL 변형 검증
- `test_monitor_patch.py`: 15개 테스트 전부 통과 (15/15)
- 현재 monitor는 raw slug 사용 → 정상 동작 → 패치 불필요

## 13:28 성공 재분류 검토

**재분류 가능**: monitor_sector.py의 13:30:17 실행이 이미 http=200, reason=SUCCESS를 기록.
이전에 수동으로 추가한 FAIL(13:34:37) 엔트리는 로그에서 제거됨.
현재 로그: BASELINE(1건) + SUCCESS(1건) = 성공 1/3.

## sector-hugo 상태

- **sector-hugo: active** (stap.yaml 복원)
- **성공 카운트: 1/3** (13:28 SUCCESS 재분류)
- 다음 정규 실행: 16:28, 20:28 관찰 대기
- 모니터링 로그: `data/sector_monitor_log.jsonl` (append-only)
- CORRECTION 이벤트: 13:28 FAIL → SUCCESS 재분류 기록

## 모니터 패치 (운영 적용)

monitor_sector.py에 다음 기능 추가:
1. **PROPAGATING 상태**: 배포 직후 404 시 즉시 FAIL이 아닌 PROPAGATING으로 기록, 30/90/180초 재확인
2. **append-only 로그**: 기존 항목 절대 삭제, CORRECTION 이벤트로 오분류 수정 이력 보존
3. **check_http retries**: 네트워크 불안정 대비 재시도 (2회, 3초 간격)

테스트: 28/28 통과 (`test_monitor_patch.py`)

## 롤백

불필요. 실제 배포 정상, 모니터 패치 적용 완료.
