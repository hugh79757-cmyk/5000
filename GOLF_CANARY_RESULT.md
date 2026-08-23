# GOLF_CANARY_RESULT.md

> **Canary 시각**: 2026-08-19 09:29-09:30 KST
> **커밋 SHA**: `fd524d742` (fix(golf-hugo): add relevance threshold override 0.50)
> **블랜치**: `_rollback_test`

---

## 1. 커밋 정보

| 항목 | 값 |
|------|-----|
| SHA | `fd524d742` |
| 메시지 | `fix(golf-hugo): add relevance threshold override 0.50` |
| 변경 파일 | `shared/relevance_scorer.py` (+1줄), `tests/test_golf_relevance_gate.py` (신규 121줄) |
| 변경 범위 | RELEVANCE_CONFIG에 golf-hugo threshold 0.50 추가 (1줄 config 변경) |

## 2. 테스트 결과

| 테스트 | 결과 |
|--------|------|
| `test_golf_relevance_gate.py` (19개) | ✅ 19/19 통과 |
| `test_pick_hugo_fallback.py` (12개) | ✅ 12/12 통과 |
| `py_compile relevance_scorer.py` | ✅ 통과 |
| 신규 실패 | **0건** |

## 3. DB 전후 차이

| 항목 | 값 |
|------|-----|
| 사전 체크섬 | `396a8ee36033362f34eb76e35bc933a9` |
| 사후 체크섬 | `33b4d2b9450f6a39992b2aeb3461950f` |
| 차이 원인 | publish_log 신규 1건 추가 (id=2376) |
| 백업 | `data/curation.db.bak_golf_canary_20260819_092916` |

## 4. 선택 키워드 및 상품

| 항목 | 값 |
|------|-----|
| 선택 키워드 | **골프클럽** |
| 상품 수 | 5건 |
| 선택 방식 | `_select_keyword()` → relevance gate 통과 (threshold 0.50 적용) |

### 선택 근거

- 30일 중복 억제: 골프클럽은 30일 내 미사용 → available
- quarantine: 없음
- low_relevance: 없음
- products ≥3: 21건 → 통과
- **relevance gate: avg score ≥ 0.50 → 통과** (기존 0.75 미통과 → 수정 후 통과)

## 5. 발행 결과

| 항목 | 값 |
|------|-----|
| 발행 성공 | **✅** |
| 제목 | "혼마 남성 골프채풀세트 외 - 합격점 스펙 비교" |
| 키워드 | 골프클럽 |
| 글자수 | 7721자 |
| 모델 | gemini-3.5-flash-lite |
| URL | `https://golf.informationhot.kr/` |
| HTTP 상태 | **200 OK** |
| publish_log id | 2376 |
| 배포 | wrangler deploy 성공 |
| Hugo build | 성공 |
| 검증 | VALIDATE golf-hugo ✅ (0 issues) |

## 6. golf-hugo 상태

| 항목 | 값 |
|------|-----|
| canary 전 | `status: paused` |
| canary 중 | `status: active` (임시 활성화) |
| canary 후 | **`status: active`** (성공으로 복원) |
| 오늘 발행 수 | 1건 (id=2376) |
| daily_quota | 1 → 추가 발행 없음 |
| 정규 스케줄 | 유지 (다음 실행 시 정상 동작 예상) |

## 7. 롤백 여부

| 항목 | 값 |
|------|-----|
| 롤백 필요 | **❌ 불필요** — canary 성공 |
| 롤백 방법 | `git revert fd524d742` (필요 시) |
| 롤백 시 영향 | threshold 0.75 복귀 → golf-hugo 다시 no_keyword |

## 8. 잔존 위험

1. **콘텐츠 반복**: 6개 키워드 순환 → 6일 주기 반복 가능 (daily_quota=1)
2. **threshold 0.50의 장기적 안정성**: 골프 상품 카테고리 확장 시 오탐 가능성 (현재 없음)
3. **브랜드명 상품**: "핑 G440" 등 "골프" 미포함 상품은 score 0.00 → 여전히 차단 (의도된 동작)

---

> **Canary 성공. golf-hugo는 active 상태로 정규 스케줄 유지.**
