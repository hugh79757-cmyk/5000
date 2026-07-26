# Phase 25.1: CUAP 엔티티 카드 404 수정 — 완료 요약

## 실행 일시
2026-07-26

## 작업 내용
Phase 25 CUAP 거미줄 엔티티 시스템 초기 구현 시 `register_cuap_entity()`가 `_make_slug(keyword)` 기반 slug로 등록했으나, 실제 `publish()`는 `slugify(title)` 기반 slug로 배포하여 **150개 엔티티 중 16개(10.7%)가 404 유발**.

## 수정 결과

| 구분 | 개수 | 비고 |
|------|------|------|
| DB 엔티티 업데이트 | 15 | 실제 콘텐츠 slug로 `post_slug`, `post_url` 수정 |
| 미발행 처리 | 1 | laptop-hugo "MSI 게이밍 노트북" → `published=0` |
| 에러 | 0 | - |

## 검증 결과
- 수정된 15개 URL 모두 **HTTP 200** 응답 확인 (`curl -I` / `requests.head`)
- 전체 `published=1` 엔티티: **149개** (수정 전 150개 → 미발행 1개 제외)
- 신규 발행 보호 로직(`pipeline.py:1064`) 정상 작동 확인

## 변경 파일
| 파일 | 변경 내용 |
|------|-----------|
| `scripts/fix_cuap_entity_urls.py` | 신규 생성 — 백필 수정 스크립트 (16건 매핑 테이블 포함) |
| `data/travel-en.db` | `cuap_entities` 테이블 16행 UPDATE/UNPUBLISH |

## 실행 명령
```bash
cd /Users/twinssn/Projects/5000
PYTHONPATH=/Users/twinssn/Projects/5000 python3 scripts/fix_cuap_entity_urls.py
```

## 잔여 리스크 & 후속 조치
| 리스크 | 상태 | 대응 |
|--------|------|------|
| 기존 배포 포스트 내 cross-sell 카드 404 링크 잔존 | 인지됨 | **Phase 29** 전량 재배포 시 완전 해소 |
| 신규 발행 회귀 | 방지됨 | `pipeline.py:1064`에서 `result["url"]` 기반 실제 slug 추출 로직 적용됨 |

## Phase 29 연계
Phase 29(CUAP 콘텐츠 오염 + 퍼널 카드 404 + 광고 공백 수정)에서 전량 재배포 예정으로, 기존 포스트에 구워진 404 링크도 그때 함께 제거됨.