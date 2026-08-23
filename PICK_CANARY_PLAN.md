# PICK_CANARY_PLAN.md

> **작성 시각**: 2026-08-19 01:30 KST
> **대상 블로그**: pick-hugo (car pipeline, persona_pick post_type)
> **변경 내용**: persona_pick 0건 시 top5_rank 자동 fallback (d887e094f)
> **目的**: pick-hugo canary 배포 절차 정의

---

## 1. 커밋 체인

| 순서 | SHA | 내용 | net diff |
|------|-----|------|----------|
| 1 | `d887e094f` | car/pipeline.py fallback 핵심 로직 + 구조화 로그 | car/pipeline.py **+22줄** |
| 2 | `ae90ed63a` | curation 변경 원복 (import 누락 제거) + 테스트 보강 | **0줄** (net) |
| 3 | `06b1c2e0e` | success 테스트 mock 검증 + 12건 전부 pass | test only |
| **합산** | | d887e094f^ → HEAD | **car +22, curation 0, test +417** |

---

## 2. 배포 대상

| 항목 | 값 |
|------|-----|
| 블로그 ID | `pick-hugo` |
| 파이프라인 | `car` |
| post_type | `persona_pick` |
| 도메인 | `pick.rotcha.kr` |
| 플랫폼 | Cloudflare Pages |
| Publisher ID | `ca-pub-8772455780561463` (rotcha.kr 계열) |

---

## 3. 배포 전 체크리스트

| # | 항목 | 상태 |
|---|------|------|
| 1 | `python3 -m pytest tests/test_pick_hugo_fallback.py` 12/12 통과 | ✅ |
| 2 | `python3 -m py_compile pipelines/car/pipeline.py` | ✅ |
| 3 | `python3 -m py_compile pipelines/curation/pipeline.py` | ✅ |
| 4 | curation/pipeline.py net diff = 0 확인 | ✅ |
| 5 | car/pipeline.py +22줄만 변경 확인 | ✅ |
| 6 | rollback SHA `037404d8a` tree 동일 검증 | ✅ |
| 7 | `CLOUDFLARE_API_TOKEN` 격리 확인 | ✅ (dispatcher.py 내부 처리) |
| 8 | push·배포·DB 변경 없음 | ✅ |

---

## 4. Canary 배포 절차

### 4.1 스케줄 격리

```bash
# pick-hugo만 발행 격리 (다른 블로그 영향 없음)
# scheduler.py에서 pick-hugo만 비활성화
```

**주의**: pick-hugo는 `scheduler.py`에서 `cap-hugo` 파이프라인의 일부로 실행됨. `cap.yaml`의 `pick-hugo` 엔트리에서 `status: active`를 `status: paused`로 변경하여 격리.

### 4.2 DB 백업

```bash
cp data/car.db data/car.db.bak_canary_$(date +%Y%m%d_%H%M%S)
```

### 4.3 Canary 실행 (1회)

```bash
# pick-hugo만 1회 실행
python3 dispatcher.py pick-hugo
```

**예상 결과**:
- `persona_pick_eligibility` True → `build_persona_pick_input` 데이터 반환 → fallback 미실행 → 발행 성공
- 또는 `persona_pick_eligibility` False → top5_rank fallback 시도 → 성공/실패

### 4.4 발행 전 결과 확인

| 확인 항목 | 방법 |
|-----------|------|
| 로그에 `persona_pick → top5_rank fallback` 포함 | `grep "top5_rank fallback" logs/*.log` |
| 또는 `persona_pick:` 로그에 `persona_type` 포함 | `grep "persona_pick:" logs/*.log` |
| `no_data_detail` 로그 없음 | `grep "no_data_detail" logs/*.log` |
| Hugo 빌드 성공 | `ls -la pick-hugo/public/index.html` |
| DB publish_log 기록 | `sqlite3 data/car.db "SELECT * FROM publish_log ORDER BY id DESC LIMIT 3"` |

### 4.5 성공/실패 판정

| 결과 | 판정 | 다음 단계 |
|------|------|-----------|
| `persona_pick:` 로그 + 발행 성공 | ✅ **성공** | 배포 확정 |
| `persona_pick → top5_rank fallback:` 로그 + 발행 성공 | ✅ **성공 (fallback 경로)** | 배포 확정 |
| `no_data_detail:` 로그 + 발행 실패 | ⚠️ **예상된 실패** | fallback이 동작했으나 데이터 부족 — 로그 분석 후 재시도 |
| 예외 발생 (traceback) | ❌ **비정상 실패** | 즉시 롤백 |

### 4.6 즉시 롤백 조건

| # | 조건 | 조치 |
|---|------|------|
| 1 | traceback 발생 | 즉시 롤백 |
| 2 | `no_data_detail:` 로그 2회 이상 | 롤백 + 원인 분석 |
| 3 | Hugo 빌드 실패 | 롤백 |
| 4 | 다른 블로그(car-hugo 등) 영향 감지 | 즉시 롤백 + 전체 파이프라인 점검 |

### 4.7 롤백 절차

```bash
# 1. pick-hugo 스케줄 복원
# cap.yaml에서 pick-hugo status를 'active'로 복원

# 2. 코드 롤백 (3개 커밋)
git revert --no-edit 06b1c2e0e ae90ed63a d887e094f

# 3. DB 백업에서 복원 (필요 시)
cp data/car.db.bak_canary_* data/car.db

# 4. 재배포
python3 dispatcher.py pick-hugo
```

---

## 5. 롤백 검증 결과

| 검증 항목 | 결과 |
|-----------|------|
| d887e094f revert 시 car/pipeline.py가 037404d8a로 복원 | ✅ MD5 일치 |
| ae90ed63a revert 시 curation/pipeline.py net diff = 0 유지 | ✅ |
| 06b1c2e0e revert 시 test 파일 삭제 | ✅ |
| 3개 커밋 모두 revert 시 tree가 037404d8a와 동일 | ✅ (파일별 검증) |

---

## 6. 잔존 위험

| 위험 | 설명 | 완화 |
|------|------|------|
| persona_pick 성공 시 fallback 미실행 검증 | mock 테스트로 확인됨 — 실제 런타임과 차이 가능 | canary 1회로 실증 |
| curation 변경 혼재 없음 | curation/pipeline.py net diff = 0 확인 | ✅ |
| 테스트 커버리지 gaps | top5_rank fallback 예외 경로 미커버 — 21회 시뮬레이션에서 크래시 프리만 검증 | canary 실증 |

---

> **이 문서는 READ-ONLY 절차 문서입니다. push·배포·DB 변경은 수행하지 않습니다.**
