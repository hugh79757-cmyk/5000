---
wave: 1
depends_on: [67]
gap_closure: true
---

# PPM-5: images:// URL 생성 로직 — 정규 표현식 검증 추가

**Created:** 2026-08-09
**Gap closure for:** `PPM-5 regex validation on images:// URL generation`

## Context

PPM-4에서 `HUGO_BASEURL`/`ASSET_DOMAIN` 없는 환경(baby-hugo)에서 `images://` 스킴 생성 후 `_normalize_hugo_asset_url()`이 `None`을 반환하면서 FrontMatter 삭제가 발생. 코드 자체는 정상 동작이나, 의도치 않은 호출 시 silently fail → 의도 명확화 필요. PPM-5는 **정규 표현식 검증 추가**만 수행. 기본 스킴 변경은 PPM-6에 이월.

## 결정 사항

- `images://` 생성에 정규식 검증 추가 — 유효한 `images://`만 생성되도록
- 기본 스킴(`https://`) 변경은 PPM-6으로 이월 (검증만으로는 사용성 개선 불충분)

## Acceptance Criteria

- [x] `shared/app_images/core.py`에 `IMAGES_URL_PATTERN` 상수 정의 (`^images://`)
- [x] `_build_images_asset_path()`에서 `images://` 생성 전 정규식 검증 추가
- [x] `IMAGES_URL_PATTERN`이 유효하지 않은 경우 생성 거부/로그
- [x] 기존 테스트 통과 확인

## 검증 기준

- [x] `shared/app_images/core.py`에 `IMAGES_URL_PATTERN` 존재
- [x] `_build_images_asset_path()`에서 정규식 검증 코드 존재
- [x] 기존 테스트 통과

## 범위 (Scope)

### 포함할 파일

- `shared/app_images/core.py`

### 포함하지 않을 파일

- 다른 파일 변경 없음
- 기본 스킴 변경은 PPM-6으로 이월

## 하위 작업

### Task 1: IMAGES_URL_PATTERN 상수 정의

- `shared/app_images/core.py`에 정규식 패턴 상수 추가
- 패턴: `^images://` — `images://`로 시작하는 문자열만 허용

### Task 2: _build_images_asset_path()에 검증 추가

- `images://` 생성 전 `IMAGES_URL_PATTERN` 검증
- 검증 실패 시 생성 거부 (None 반환 또는 로그)

## 완료 기준

- [x] `IMAGES_URL_PATTERN` 상수 정의됨
- [x] `_build_images_asset_path()`에서 검증 사용
- [x] 기존 테스트 통과
