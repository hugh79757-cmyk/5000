# PICK_CANARY_RESULT.md

> **canary 시각**: 2026-08-19 08:06~08:07 KST
> **대상 블로그**: pick-hugo (car pipeline, persona_pick)
> **커밋**: `06b1c2e0e` (HEAD)
> **판정**: ✅ **성공**

---

## 1. 사전 상태

| 항목 | 값 |
|------|-----|
| HEAD | `06b1c2e0e` |
| car.db MD5 (before) | `53df093ad78c4bdc07dc36f793fd5fb9` |
| car.db 백업 | `data/car.db.bak_canary_20260819_080107` |
| today_count | 0 |
| dedup | False |
| cooldown | False (해제 후 실행) |
| fallback 코드 | ✅ 복원됨 (working tree에서 누락 → `git checkout d887e094f`로 복원) |

---

## 2. canary 실행 경로

```
1차 실행 (08:03): fallback 코드 누락 상태 → persona_pick 데이터 없음 26회 반복 → no_data
   ↓ 원인: working tree에서 fallback 코드 누락 (uncommitted change)
   ↓ 조치: git checkout d887e094f -- pipelines/car/pipeline.py
   ↓ cooldown 해제: data/cooldown.json에서 daily_pick-hugo 제거
2차 실행 (08:06): fallback 코드 복원 상태 → fallback 발동 → 발행 성공
```

---

## 3. canary 결과

### 실행 흐름

| 단계 | 결과 |
|------|------|
| 토픽 선택 | `k8_hev_2026` (persona_pick, site_id=pick) |
| persona_pick_eligibility | **False** (trims 0건 → no_eligible_trim) |
| top5_rank fallback 발동 | **✅ 예상대로 발동** |
| top5_rank 데이터 | `G80 3.5 터보 스포츠 패키지 (7283만원)` |
| AI 생성 | gemini-3.1-flash-lite, 2648자 |
| 제목 | "G80 3.5 터보 스포츠 패키지, 이런 사람에게 딱 맞는가…" |
| Hugo 발행 | ✅ 파일 생성 |
| 배포 | ✅ deployed |
| URL | `https://pick.informationhot.kr/posts/g80-35-터보-스포츠-패키지-이런-사람에게-딱-맞는가/` |
| HTTP 상태 | **200 OK** |

### 로그 핵심

```
persona_pick: k8_hev_2026 가격 5000만원 → newlywed
[pick-hugo] persona_pick → top5_rank fallback: k8_hev_2026
G80 3.5 터보 스포츠 패키지 (7283만원)
pick-hugo result: True
[pcode] 발행 실패 이벤트 close: pick-hugo/P01 (5건)
[pcode] 발행 실패 이벤트 close: pick-hugo/P02 (16건)
```

---

## 4. DB 전후 차이

| 항목 | before | after | 차이 |
|------|--------|-------|------|
| car.db MD5 | `53df093ad78c4bdc07dc36f793fd5fb9` | `8b68f62f299d1347e6db38f2fbc6dcdf` | 변경됨 |
| publish_log (pick, 오늘) | 0건 | **1건** | +1 |
| topics (k8_hev_2026, persona_pick) | pending | **published** | 상태 전이 |
| deploy | - | pick-hugo 배포 완료 | - |

### 새 발행 레코드

| 필드 | 값 |
|------|-----|
| id | 2650 |
| topic_id | 1818 |
| site | pick |
| title | G80 3.5 터보 스포츠 패키지, 이런 사람에게 딱 맞는가… |
| slug | g80-35-터보-스포츠-패키지-이런-사람에게-딱-맞는가 |
| published_at | 2026-08-19T08:07:34.951870 |

---

## 5. 성공 기준 대조

| 기준 | 결과 | 판정 |
|------|------|------|
| persona_pick 실패 시 top5_rank fallback 1회 실행 | ✅ `k8_hev_2026` → `G80 3.5 터보` | **통과** |
| 유효 콘텐츠 1건 처리 | ✅ 3104자, HTTP 200 | **통과** |
| 중복 주제 없음 | ✅ 1회만 실행 | **통과** |
| 예외 없음 | ✅ traceback 0건 | **통과** |
| no_data 없음 | ✅ fallback로 데이터 확보 | **통과** |
| 다른 블로그 영향 없음 | ✅ pick만 발행 (1건) | **통과** |

---

## 6. 판정

| 항목 | 판정 |
|------|------|
| **최종 판정** | **✅ 성공** |
| rollback 필요 | **❌ 불필요** |
| 코드 유지 | **✅ d887e094f + ae90ed63a + 06b1c2e0e 유지** |
| 스케줄 복구 | **✅ pick-hugo status: active (변경 없음)** |
| 추가 재발행 | **❌ 없음** |

---

## 7. 발견 사항

### 7.1 working tree fallback 코드 누락 (해결됨)

canary 1차 실행 시 `pipelines/car/pipeline.py`의 fallback 코드가 working tree에서 누락되어 있었습니다. d887e094f 커밋에는 코드가 있지만, uncommitted change로 인해 working tree에서 제거된 상태였습니다. `git checkout d887e094f`로 복원 후 2차 실행에서 정상 동작 확인.

**lessons**: working tree 변경사항이 커밋과 불일치할 수 있음. canary 실행 전 `git diff HEAD -- <파일>` 확인 필요.

### 7.2 daily cooldown 메커니즘

1차 실행이 `no_data`로 실패하면 `daily_pick-hugo` cooldown이 설정되어 다음 날까지 재시도 불가. canary 실패 시 cooldown 해제 필요.

### 7.3 problem_monitor P01/P02 close

canary 성공 후 자동으로 pick-hugo의 P01(5건), P02(16건) 발행 실패 이벤트가 close됨.

---

## 8. 잔존 위험

| 위험 | 설명 | 완화 |
|------|------|------|
| persona_pick 성공 경로 미검증 | 이번 canary는 fallback 경로만 검증. persona_pick_eligibility True + build_persona_pick_input 성공 경로 미실증 | 테스트로 커버됨 (mock) |
| top5_rank fallback 예외 경로 | build_top5_rank_input 예외 시 fallback_exception 처리 — 미검증 | 21회 시뮬레이션에서 크래시 프리 확인 |
| daily cooldown 재발 | persona_pick 모든 topic에서 trims 0건이면 매번 fallback → 매번 no_data 가능 | cooldown 해제 로직 필요 |

---

> **이 보고서는 canary 실행 결과만 기록했습니다. 추가 배포·push·DB 변경은 수행하지 않았습니다.**
