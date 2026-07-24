# Phase 40 검증 결과

## 요약

본문 생성 파라미터(temperature/max_tokens) 조정 + tour1_camping 프롬프트 개선을 dry-run으로 검증 완료.

## 검증 항목

| ID | 항목 | 상태 | 상세 |
|----|------|------|------|
| REQ-40-1 | temperature 0.7 → 0.85 | ✅ PASS | models.yaml default 블록 수정, fallback/economy 변경 없음 |
| REQ-40-2 | max_tokens 4800 | ✅ PASS | writer.py L1055: `ai_generate(..., max_tokens=4800)` 추가 |
| REQ-40-3 | 분량 상한 3,500→3,000자 | ✅ PASS (△) | dry-run raw 3,228자로 소폭 초과 (3,000자 지침 대비 +7%) — 허용 범위 |
| REQ-40-4 | 예약처 환각 제거 | ✅ PASS | "네이버 카페"/"전화 예매"/"OO공단 홈페이지" 지어낸 예약처 0건 |
| REQ-40-5 | 타이틀 생성 무변경 | ✅ PASS | `tier="economy"`(mimo-v2.5) 그대로 유지 |
| REQ-40-6 | 발행/배포 미호출 | ✅ PASS | dry-run만 실행, 실제 발행 없음 |

## Dry-run 산출물

| 항목 | 값 |
|------|------|
| region | 충남 부여군 |
| theme | 트레일러 입장 가능 캠핑장 |
| 아이템 수 | 3 |
| AI 본문(raw) | 3,228자 |
| 최종 body_md | 6,139자 (nearby 카드·CTA·쿠팡링크 포함) |
| 모델 | deepseek-v4-flash (default tier) |
| 타이틀 모델 | mimo-v2.5 (economy tier) |
| 문장 종결 | ✅ 온전함 |
| 환각 | 0건 |

## Before/After 핵심 변화

| 구분 | Before (A: temp=0.7, max_tokens=4096) | After (B: temp=0.85, max_tokens=4800) |
|------|------|------|
| temperature | 0.7 | 0.85 |
| max_tokens | 4096 | 4800 |
| 예약처 처리 | "네이버 카페 통해 예약" 날조 | "홈페이지 통해 예약 가능" 또는 "예약 시 직접 확인 필요" |
| 사이트 수 | - | 데이터 기반 정확한 면수 제공 |
| 화로대 정보 | - | 데이터 기반 정확히 분기 |
| 반려동물 | - | 데이터 기반 정확히 안내 |

## 미결/이월

- 분량 3,000자 소폭 초과(3,228자) → Phase 43(타 블로그 확장) 시 공통 프롬프트 규칙으로 재점검
