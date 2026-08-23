# Track B Decision Threshold Specification

> 상태: DRAFT (2026-08-22). 대표 승인 전 초안. Track B design doc §5 MISSING_DECISION_THRESHOLD 해소 목적.
> 제약: DESIGN_ONLY. 코드/DB 변경 없음. §5 임계값은 "초안" — 승인 후 확정.

## 1. Eligibility (개선 후보 최소 조건)

| 조건 | 임계값 (초안) | 근거 |
|------|--------------|------|
| 체커 fail 다수성 | `fail 건수 ≥ 2` (서로 다른 check_name) | 단일 fail은 노이즈 가능 |
| content_quality 필수 | **필수 포함** (`content_quality` fail 존재) | §11 품질 프록시가 핵심 판정 입력 |
| 트래픽 잠재력 | `gsc_pages.impressions > 0` | 개선 효과 측정 가능 대상만 |
| 발행 경과일 | `≥ 14일` | 신규 글은 효과 측정 불안정 |
| gate_filtered 제외 | hotel/airport/restaurant 블로그 제외 | Track A/B 일관 게이트 |

> 보너스 가중: `c08_*`/`FM-*` 구조결함 동반 시 confidence 상향.

## 2. Confidence (개선 제안 신뢰도)

| 등급 | 조건 (초안) | 실행 정책 |
|------|------------|----------|
| HIGH | content_quality fail + GSC data 존재 + schema violation 동반 | 자동 실행 후보 (안전망 적용) |
| MEDIUM | content_quality fail + schema OK | 수동 검토 후 실행 |
| LOW | 단일 체커 fail만 (content_quality 아님) | 모니터링 대기 |

## 3. Effect Size (개선 효과 추정)

| 지표 | MDE (최소 유의 효과, 초안) | 근거 |
|------|--------------------------|------|
| GSC CTR | `baseline 대비 +0.5%p` | michelin 트랙 C 목표 참조 |
| 체류시간 | `baseline 대비 +10초` | GA4 (Track C michelin 14일 데이터) 기반 |
| 페이지/세션 | `+0.1` | 보조 지표 |

> 효과 미달 시: eligibility 강화 또는 MDE 상향 재교정.

## 4. Safety (개선 적용 안전 조건 — Track A Exp1 안전망 재활용)

- `dry_apply.safe_to_apply == True` 필수 (verify_before_apply)
- `create_rollback_point` 생성 필수 (적용 전)
- recheck `passed == False` → `execute_rollback` 자동
- 동시 개선 상한: **5건/배치**
- 배포는 dispatcher/deploy 경로 (Track A Phase C 준수)

## 5. Calibration Plan (임계값 조정)

1. 첫 배치(5건) 결과로 `precision`/`recall` 측정
2. `false_positive_rate > 20%` → eligibility 강화 (fail 건수 ≥3 등)
3. 효과 미달 → `effect_size` MDE 상향
4. 분기별 재교정 (quarterly recalibration)

## 부록: Phase 0~3 로드맵

| Phase | 작업 | 의존 |
|-------|------|------|
| 0 | 핸드오프 + threshold 정의 (본 문서) | — |
| 1 | content_quality 55건 분석 + eligibility 적용 후보 선정 | Track A check_results + GSC(Track C) |
| 2 | HIGH confidence 5건 파일럿 개선 | Track A 안전망(recheck/rollback/verify) |
| 3 | 파일럿 결과 기반 threshold 재교정 + 확대 | GA4 효과측정 (Track C michelin 14일) |

> 재개 조건: human roles 지정 + 대표 구현 승인 (track-b handoff §7). 본 초안만으로는 실행 불가.
