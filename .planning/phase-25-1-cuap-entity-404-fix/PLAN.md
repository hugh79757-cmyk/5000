---
phase: 25-1-cuap-entity-404-fix
plan: 01
type: execute
wave: 1
depends_on: ["25-cuap-spider"]
files_modified:
  - scripts/fix_cuap_entity_urls.py
  - data/travel-en.db (16 rows updated)
autonomous: true
requirements: [R1, R2, R3]

must_haves:
  truths:
    - "150개 엔티티 중 16개 keyword-based slug로 404 유발 확인"
    - "pipeline.py:1064 슬러그 추출 로직으로 신규 발행분 보호됨"
    - "백필 스크립트로 15개 URL 수정, 1개 unpublished 처리"
  artifacts:
    - path: "scripts/fix_cuap_entity_urls.py"
      provides: "CUAP 엔티티 URL 백필 수정 스크립트"
    - path: "data/travel-en.db"
      provides: "수정된 cuap_entities 테이블 (150개 중 135개 published=1, 1개 published=0)"
  key_links:
    - from: "scripts/fix_cuap_entity_urls.py"
      to: "data/travel-en.db"
      via: "sqlite3 UPDATE on cuap_entities"
      pattern: "UPDATE cuap_entities SET post_slug=?, post_url=? WHERE blog_id=? AND entity_name=?"
    - from: "pipelines/curation/pipeline.py:1064"
      to: "shared/cuap_entity_linker.py"
      via: "register_cuap_entity(post_slug=_actual_slug)"
      pattern: "실제 배포 slug 추출 후 등록"

---

# Phase 25.1: CUAP 엔티티 카드 404 수정 — 실행 완료

## 완료 작업

### Task 1: 백필 수정 스크립트 생성 및 실행 ✅
- **파일:** `scripts/fix_cuap_entity_urls.py`
- **실행:** `PYTHONPATH=/Users/twinssn/Projects/5000 python3 scripts/fix_cuap_entity_urls.py`
- **결과:** 15개 업데이트, 1개 unpublished, 0개 에러

### Task 2: 수정된 URL 실시간 검증 ✅
- **검증:** 15/15 수정 URL → HTTP 200 확인 (HEAD 요청)
- **상세:** `curl -I` 또는 `requests.head()`로 리다렉트 팔로우 후 200 확인

### Task 3: 파이프라인 등록 로직 회귀 방지 확인 ✅
- `pipelines/curation/pipeline.py:1064` 실제 slug 추출 로직 정상 작동 확인
- 신규 발행 시 `register_cuap_entity(post_slug=_actual_slug)`로 title-based slug 저장

## 성공 기준 달성

| 기준 | 결과 | 검증 방법 |
|------|------|-----------|
| 16개 오염 엔티티 수정 | ✅ | 15개 업데이트, 1개 unpublished |
| 수정된 엔티티 URL 200 응답 | ✅ | 15/15 HEAD 요청 200 확인 |
| 신규 발행 시 정상 등록 | ✅ | pipeline.py:1064 로직 검증 |
| 퍼널 헤더 URL 200 응답 | ✅ | 동일 엔티티 사용으로 자동 보장 |

## 수정된 엔티티 상세 (15개)

| 블로그 | 엔티티 | 조치 |
|--------|--------|------|
| health-hugo | 비오틴 탈모 영양제 | URL 수정 (이미 일치) |
| baby-hugo | 아기 이유식 용품 추천 | **slug 변경** (keyword → title-based) |
| fitness-hugo | 밸런스보드 추천 | URL 수정 (이미 일치) |
| kitchen-hugo | 수동착즙기 추천 | URL 수정 (이미 일치) |
| beauty-hugo | 파우더 추천 | **slug 변경** |
| baby-hugo | 아기 카시트 추천 | URL 수정 (이미 일치) |
| health-hugo | 면역력 강화 영양제 | URL 수정 (이미 일치) |
| appliance-hugo | 여름철 제습기 추천 | **slug 변경** |
| beauty-hugo | 향수 추천 | **slug 변경** |
| health-hugo | 피로회복 영양제 추천 | **slug 변경** |
| fitness-hugo | 덤벨 추천 | URL 수정 (이미 일치) |
| health-hugo | 간 건강 영양제 추천 | **slug 변경** |
| interior-hugo | 평상형 침대 추천 | URL 수정 (이미 일치) |
| fitness-hugo | 스쿼트 보조 기구 추천 | URL 수정 (이미 일치) |
| baby-hugo | 아기 쏘서 추천 | URL 수정 (이미 일치) |

## 미발행 처리 (1개)
- **laptop-hugo** | MSI 게이밍 노트북 → `published=0` (콘텐츠 폴더에 해당 글 없음)

## 잔여 리스크

| 리스크 | 상태 | 완화 |
|--------|------|------|
| 기존 배포 포스트 내 404 링크 잔존 | 인지됨 | Phase 29 전량 재배포로 해소 |
| 슬러그 매칭 오류 | 없음 | 수동 검증된 FIXES 매핑 사용 |
| 신규 발행 회귀 | 방지됨 | pipeline.py:1064 로직으로 보호 |

## 다음 단계

1. **Phase 29** — CUAP 전량 재배포 (기존 포스트 내 404 링크 완전 제거)
2. 정기 모니터링: `cuap_entities` URL 주기적 검증 스크립트 추가 고려