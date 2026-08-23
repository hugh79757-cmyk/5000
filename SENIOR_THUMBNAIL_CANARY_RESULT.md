# SENIOR_THUMBNAIL_CANARY_RESULT.md

> 실행 시각: 2026-08-19 22:12~22:13 KST
> 조사 유형: 복구 + 1건 canary (코드 변경 없이 Playwright chromium 설치만 수행)

---

## 1. 환경 확인

| 항목 | 값 |
|------|-----|
| 사용자 | twinssn (uid=501, admin) |
| Python | 3.14.6 (`/Users/twinssn/.kaggle-env/bin/python3`) |
| venv | `/Users/twinssn/.kaggle-env` |
| Playwright | 1.61.0 |
| PLAYWRIGHT_BROWSERS_PATH | 미설정 (기본: `~/Library/Caches/ms-playwright/`) |
| 디스크 여유 | 9.7GB (55% 사용) |

---

## 2. Chromium 설치

### 설치 전

| 항목 | 상태 |
|------|------|
| `~/Library/Caches/ms-playwright/` | **미존재** |
| chromium_headless_shell-1228 | **미존재** |
| chromium-1228 | **미존재** |

### 설치 후

| 항목 | 값 |
|------|-----|
| 명령어 | `python3 -m playwright install chromium` |
| chromium v1228 | Chrome for Testing 149.0.7827.55 (171MB) |
| chromium_headless_shell v1228 | Chrome Headless Shell 149.0.7827.55 (93.5MB) |
| ffmpeg v1011 | 1MB |
| **총 디스크 사용** | **539MB** |
| Playwright 버전 변경 | **없음** (1.61.0 유지) |
| 시스템 패키지 변경 | **없음** |

---

## 3. Smoke Test

```
✅ chromium launch → 렌더링 → webp 변환 성공
   브라우저: 149.0.7827.55
   생성 webp: 4,456 bytes
```

```
✅ generate_image_thumbnail() → R2 업로드 성공
   URL: https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/senior/canary-test-verification.webp
   HTTP: 200 OK, image/webp, 47,190 bytes
   hash: 3730b9205ba42140fc598a5f1b902b4445e8559856491ce748dc722d6b74e52d
   default hash: 685d93b96d44d8652e1a9629dcda44e830ec39f42df5f1a74d2bccc83534fb5b
   불일치: ✅ (고유 이미지 확인)
```

---

## 4. Canary 결과

| 항목 | 값 |
|------|-----|
| article_id | 11562 |
| 제목 | 광양시 저소득층 단열 및 창호공사 현물 지원 조건과 신청 방법 |
| slug | `광양시-저소득층-단열-및-창호공사-현물-지원-조건과-신청-방법` |
| featureimage | `https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/senior/20260819-a054965c96.webp` |
| pipeline_status | SUCCESS |
| deployed | true |
| **featureimage hash** | **778539cf3c2b3c53d47764a571bded6b069ff4f55d360a8af14b3f24038c58c9** |
| default hash | 685d93b96d44d8652e1a9629dcda44e830ec39f42df5f1a74d2bccc83534fb5b |
| hash 불일치 | ✅ (고유 썸네일 확인) |
| 파일 크기 | 48,222 bytes |
| HTTP 상태 | 200 OK |
| Content-Type | image/webp |

### 라이브 검증

| URL | HTTP | 비고 |
|-----|------|------|
| `https://senior.informationhot.kr/` | 200 | 홈페이지 정상 |
| `https://senior.informationhot.kr/posts/광양시-저소득층-단열-및-창호공사-현물-지원-조건과-신청-방법/` | 200 | 게시글 정상 |
| R2 thumbnail URL | 200 | image/webp, 48,222 bytes |

### 로그 핵심

```
22:12:48 [ThumbGen] Unsplash 검색 성공 → 이미지 다운로드
22:13:02 [ThumbGen] R2 업로드: thumbnails/senior/20260819-a054965c96.webp
22:13:02 [SeniorThumb] 생성 완료: https://pub-...r2.dev/thumbnails/senior/20260819-a054965c96.webp
22:13:07 [PUBLISH] Hugo post written: .../content/posts/광양시-저소득층-단열-및-창호공사-현물-지원-조건과-신청-방법/index.md
22:13:24 [VALIDATE] senior-hugo ✅ (0 issues)
22:13:24 Hugo published: ... -> https://senior.informationhot.kr/posts/.../
```

---

## 5. quota 원복

| 항목 | Before | After |
|------|--------|-------|
| daily_quota | 6 (canary용 임시) | **5 (원복)** |

---

## 6. 롤백 여부

| 항목 | 상태 |
|------|------|
| Playwright chromium 설치 | **유지** — canary 성공, 정규 스케줄 필요 |
| quota 변경 | **원복됨** (5) |
| DB 백업 | `/Users/twinssn/Projects/5000/data/senior.db.bak_canary_20260819_221122` |
| Content 백업 | `/tmp/senior-hugo-content-20260819_221122.tar.gz` |
| 롤백 필요 여부 | **아니오** — canary 성공 |

---

## 6.5 travel HEAD_FALSE_POSITIVE 재분류 + GET fallback 수정안

### 재분류 결과

| 기존 분류 | 새 분류 | 건수 | 근거 |
|----------|---------|-----:|------|
| BROKEN (405) | **HEAD_FALSE_POSITIVE** | 7 | GET 200 OK, HEAD만 차단 |

tong.visitkorea.or.kr는 HTTP HEAD 요청을 405로 차단하지만, GET 요청은 정상 응답(200 OK, image/jpg). 브라우저는 GET을 사용하므로 사용자에게 보이는 장애 없음.

### HEAD 405 GET fallback 수정안 (미적용)

**대상 파일**: `monitor_sector.py:79-96` — `check_http()` 함수

**변경 내용**:
```python
def check_http(url, retries=1, delay=2):
    """HTTP HEAD → 405 시 GET fallback. retries회 시도."""
    import subprocess
    for attempt in range(retries):
        try:
            # 1차: HEAD
            result = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=10
            )
            code = int(result.stdout.strip()) if result.stdout.strip() else 0
            
            # HEAD 405 → GET fallback
            if code == 405:
                result = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     "-H", "User-Agent: Mozilla/5.0", url],
                    capture_output=True, text=True, timeout=10
                )
                code = int(result.stdout.strip()) if result.stdout.strip() else 0
            
            if code == 200 or attempt == retries - 1:
                return code
        except Exception:
            if attempt == retries - 1:
                return 0
        if attempt < retries - 1:
            time.sleep(delay)
    return 0
```

**변경 범위**: `monitor_sector.py` 10줄 추가
**리스크**: 매우 낮음. HEAD 실패 시에만 GET 시도
**검증**: travel-hugo 405 URL → GET fallback → 200 확인

**적용 시점**: 별도 후속 변경으로 분리. 현재 섹터-hugo 모니터링에만 집중.

---

## 7. 정규 스케줄 유지 여부

**유지 권장.**

- Playwright chromium이 정상 설치됨
- `generate_image_thumbnail()`이 Unsplash → 다운로드 → 리사이즈 → Playwright 렌더링 → R2 업로드 전 과정 성공
- 고유 썸네일 생성 확인 (hash 불일치)
- 라이브 게시글 HTTP 200 + image/webp 확인
- 다음 정규 실행(내일 07:34)에서 자동 썸네일 생성 예상

---

## 8. 부작용 없음

| 항목 | 상태 |
|------|------|
| sector-hugo | 변경 없음 (paused 유지) |
| visa-hugo | 변경 없음 |
| 다른 블로그 | 변경 없음 |
| 코드 변경 | **없음** |
| 템플릿 변경 | **없음** |
| DB 변경 | article 1건 추가 (canary) |
| 설정 변경 | quota 원복 완료 |
| 재발행 | **없음** |
| 배포 | canary 1건만 |

---

## 9. 후속 작업 (별도 변경으로 분리)

| 작업 | 우선순위 | 비고 |
|------|---------|------|
| `pipelines/senior/pipeline.py` stderr 로깅 강화 | 중 | `_make_thumbnail()` 실패 시 파일 로그 |
| `scripts/batch_thumbnails.py`에 senior-hugo 등록 | 중 | 기존 5건 일괄 재생성 (별도 canary 필요) |
| THUMBNAIL-01에 DEFAULT_REPEATED 규칙 추가 | 낮 | hash 비교 탐지 |
| travel HEAD 405 GET fallback 수정안 | 낮 | `check_http()`에 GET fallback |
| stock-hugo, travel-hugo 기본 썸네일 점검 | 낮 | Playwright 설치로 자동 해결 기대 |

---

*이 문서는 READ-ONLY 조사 + 1건 canary 결과입니다. Playwright chromium 설치만 수행.*
