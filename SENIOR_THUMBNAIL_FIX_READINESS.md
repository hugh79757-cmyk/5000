# SENIOR_THUMBNAIL_FIX_READINESS.md

> 조사 시각: 2026-08-19 22:00 KST
> 조사 유형: READ-ONLY — 코드/템플릿/DB/설정 변경·이미지 생성·API 호출·재발행·배포 수행하지 않음

---

## 1. 근본원인 확정

**Playwright chromium 브라우저 바이너리 미설치**

| 단계 | 위치 | 상태 |
|------|------|------|
| Unsplash 검색 | `generator.py:341-366` | ✅ 성공 (5장 반환) |
| 이미지 다운로드 | `generator.py:353` | ✅ 성공 (15초 타임아웃) |
| 이미지 리사이즈 | `generator.py:355-360` | ✅ 성공 (600x600 webp) |
| **Playwright 실행** | **`generator.py:222`** | **❌ 실패** — `chromium_headless_shell-1228` 미존재 |
| R2 업로드 | — | 미도달 |

**에러 메시지**:
```
playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at
/Users/twinssn/Library/Caches/ms-playwright/chromium_headless_shell-1228/
chrome-headless-shell-mac-arm64/chrome-headless-shell
```

### 오류 소실 경로 (에러 스와인딩 체인)

| 위치 | 동작 | 결과 |
|------|------|------|
| `generator.py:222` | `pw.chromium.launch()` 예외 발생 | `Error: Executable doesn't exist` |
| `pipeline.py:74` | `except Exception as e:` 전체 캐치 | `logger.warning(f"Thumbnail failed: {e}")` |
| `pipeline.py:76` | `return ""` | 빈 문자열 반환 |
| `scheduler.py:411-413` | returncode=0 → stderr 폐기 | **`Thumbnail failed:` 로그 소실** |
| `hugo_writer.py:1142-1143` | `if not thumbnail_url:` → True, stock 체크 실패 | `"stock" in "senior-hugo"` → False |
| `hugo_writer.py:153` | frontmatter else 분기 | `common/default-thumbnail.webp` 적용 |

**핵심 설계 결함**: 파이프라인이 "성공"(article published)으로 판정되므로 subprocess stderr가 폐기됨. `Thumbnail failed:` 로그가 어떤 로그에도 기록되지 않음.

---

## 2. 영향 범위

| 블로그 | 영향 | 비고 |
|--------|------|------|
| **senior-hugo** | 전부 기본 썸네일 | 8/19~16:28 전 기사 영향 |
| **stock-hugo** | 일부 기본 썸네일 | 2건 확인 (표본에서) |
| **travel-hugo** | 1건 기본 썸네일 | 1건 확인 |

**변경 시점 추정**: Playwright chromium 바이너리가 macOS 업데이트 또는 캐시 정리로 삭제된 시점부터 전부 실패. 8/17까지는 thumbnails/senior/*.webp 생성됨 → 8/19부터 전부 default.

---

## 3. 최소 수정안 (READ-ONLY 제안)

### 수정안 A: Playwright 재설치 (최소 변경)

```bash
# 1. Playwright chromium 재설치
playwright install chromium

# 2. 확인
python3 -c "from playwright.sync_api import sync_playwright; pw = sync_playwright().start(); b = pw.chromium.launch(); b.close(); pw.stop(); print('OK')"
```

**변경 범위**: 환경 설정만. 코드 변경 없음.
**리스크**: 낮음. 기존 동작 복원.
**검증**: senior-hugo 1건 canary 발행 후 featureimage URL 확인.

### 수정안 B: batch_thumbnails.py에 senior-hugo 등록

```python
# scripts/batch_thumbnails.py SITE_CONFIGS에 추가
"senior-hugo": {
    "site_path": "/Users/twinssn/Projects/SEAP/senior-hugo",
    "content_dir": "content/posts",
    "thumbnail_dir": "thumbnails/senior",
    "palette": "senior",
},
```

**변경 범위**: `scripts/batch_thumbnails.py` 1줄 추가.
**리스크**: 낮음. Playwright 재설치 후에만 의미 있음.
**검증**: `python3 scripts/batch_thumbnails.py --site senior-hugo --dry-run`

### 수정안 C: _make_thumbnail() 에러 로깅 강화

```python
# pipelines/senior/pipeline.py:74-76
except Exception as e:
    logger.warning(f"Thumbnail failed [{type(e).__name__}]: {e}")
    # 스케줄러가 stderr를 폐기하므로 파일 로그도 추가
    import logging
    thumb_logger = logging.getLogger("thumbnail_failures")
    thumb_logger.warning(f"senior-hugo thumbnail failed: {type(e).__name__}: {e}")
```

**변경 범위**: `pipelines/senior/pipeline.py` 3줄 추가.
**리스크**: 매우 낮음. 로깅만 추가.
**검증**: 다음 실행 시 `logs/thumbnail_failures.log` 확인.

---

## 4. 테스트 계획

### 4.1 Playwright 설치 확인

```bash
python3 -c "
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
b = pw.chromium.launch()
print(f'Browser: {b.version}')
b.close()
pw.stop()
print('Playwright OK')
"
```

### 4.2 generate_image_thumbnail() 단위 테스트

```bash
python3 -c "
from shared.thumbnail_generator import generate_image_thumbnail
url = generate_image_thumbnail(
    site_id='senior',
    slug='test-thumb-verification',
    title='테스트 썸네일 생성',
    category='생활지원'
)
print(f'Result: {url}')
assert url and 'r2.dev' in url, f'Expected R2 URL, got: {url}'
print('PASS')
"
```

### 4.3 senior-hugo canary 발행

```bash
# dispatcher.py로 1건 발행 (이미지 생성 포함)
python3 /Users/twinssn/Projects/5000/dispatcher.py senior-hugo
# featureimage가 default-thumbnail.webp가 아닌 R2 URL인지 확인
```

---

## 5. Canary 계획

| 단계 | 작업 | 검증 기준 | 롤백 |
|------|------|-----------|------|
| 1 | `playwright install chromium` | `python3 -c "..."` → OK | — |
| 2 | `generate_image_thumbnail()` 테스트 | R2 URL 반환 | — |
| 3 | senior-hugo 1건 canary 발행 | featureimage ≠ default-thumbnail.webp | stap.yaml에서 senior-hugo pause |
| 4 | 라이브 URL HTTP 200 확인 | curl 200 + image/webp | — |
| 5 | 24시간 모니터링 | 다음 2건 발행에서도 썸네일 생성 | — |

---

## 6. 롤백 절차

| 시나리오 | 롤백 |
|----------|------|
| Playwright 설치 실패 | 수정안 A 취소, 환경 복원 불필요 (코드 변경 없음) |
| canary 발행 실패 | `config/blogs.d/seap.yaml`에서 senior-hugo status를 paused로 변경 |
| 썸네일 품질 불만족 | `scripts/batch_thumbnails.py`로 기존 포스트 일괄 재생성 |
| 다른 파이프라인 영향 | Playwright 설치는 senior-hugo 전용 아님 — stock-hugo, travel-hugo 등에도 적용 가능 |

---

## 7. 관련 파일

| 파일 | 역할 |
|------|------|
| `pipelines/senior/pipeline.py:53-76` | `_make_thumbnail()` — 썸네일 진입점 |
| `shared/thumbnail_generator/generator.py:323-380` | `generate_image_thumbnail()` — Playwright + Unsplash |
| `shared/thumbnail_generator/generator.py:141-275` | `generate_thumbnail()` — Playwright 렌더링 |
| `shared/publishers/hugo_writer.py:1117-1155` | 썸네일 fallback 로직 |
| `scripts/batch_thumbnails.py` | 일괄 썸네일 생성 (senior-hugo 미등록) |
| `ops_dashboard/checks/standard.py:541` | THUMBNAIL-01 — R2+webp만 검증, 반복 미감지 |
| `THUMBNAIL_FLEET_AUDIT.md` | 플릿 감사 결과 (2차 검증 완료) |

---

## 8. 대시보드 탐지 여부

| 항목 | 상태 | 비고 |
|------|------|------|
| THUMBNAIL-01 | ❌ 미탐지 | R2+webp 통과, 반복 미감지 |
| R2-01 | ❌ 미탐지 | R2 도메인 통과 |
| broken_featureimage | ❌ 미탐지 | HTTP 200 (default thumbnail) |
| **신규 규칙 필요** | — | "기본 이미지 반복 N회 이상" 탐지 |

---

*이 문서는 READ-ONLY 조사 결과입니다. 코드·설정·DB 변경은 수행하지 않았습니다.*
