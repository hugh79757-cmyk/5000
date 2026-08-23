# TECH_DEBT_PICK_CONTENT_LINEAGE.md

> **등록 시각**: 2026-08-19 08:20 KST
> **심각도**: 중간 (데이터 계보 오염, 발행 자체에는 영향 없음)
> **상태**: 미해결

---

## 문제 설명

`pick-hugo`의 `top5_rank` fallback 동작 시, `publish_log`의 `topic_id`가 **원본 topic** (예: `k8_hev_2026`)을 가리키지만, 실제 발행된 콘텐츠는 **다른 차량** (예: G80 3.5 터보)에 대한 것.

### 재현 경로

```
1. topic = k8_hev_2026 (persona_pick, trims=0건)
2. persona_pick_eligibility → False (trims 부족)
3. top5_rank fallback 발동 → segment(준대형세단) 내 비교 콘텐츠 생성
4. 콘텐츠: G80 3.5 터보 스포츠 패키지
5. publish_log: topic_id=1818 (k8_hev_2026), title="G80 3.5 터보..."
```

### 영향

| 항목 | 상태 |
|------|------|
| 발행 자체 | ✅ 정상 (HTTP 200) |
| SEO / 사용자 경험 | ⚠️ URL과 title이 G80을 가리킴 |
| 분석 / 모니터링 | ⚠️ topic_id로 성과 분석 시 k8_hev_2026으로 집계됨 |
| 콘텐츠 정합성 | ⚠️ k8_hev_2026과 G80의 연결이 명시적이지 않음 |

---

## 해결 방안: source_topic_id + content_subject_id 분리

### 현재 스키마

```sql
publish_log (
    id INTEGER PRIMARY KEY,
    topic_id INTEGER,        -- 원본 topic (k8_hev_2026)
    site TEXT,
    title TEXT,              -- 콘텐츠 제목 (G80 3.5 터보...)
    slug TEXT,
    ...
)
```

### 제안 스키마

```sql
publish_log (
    id INTEGER PRIMARY KEY,
    topic_id INTEGER,        -- 원본 topic (k8_hev_2026) — 호환성 유지
    source_topic_id INTEGER, -- ★ 새로 추가: 실제 사용된 topic
    content_subject TEXT,    -- ★ 새로 추가: 콘텐츠 대상 차량 ID (G80 등)
    content_type TEXT,       -- ★ 새로 추가: 'persona_pick' | 'top5_rank_fallback' | ...
    site TEXT,
    title TEXT,
    slug TEXT,
    ...
)
```

### 마이그레이션 고려사항

| 항목 | 설명 |
|------|------|
| 기존 데이터 | `source_topic_id = topic_id`, `content_subject = NULL` (기본값) |
| 코드 변경 | `pipeline.py`에서 fallback 시 `source_topic_id`와 `content_subject` 기록 |
| 호환성 | `topic_id` 컬럼 유지 — 기존 쿼리 영향 없음 |
| 범위 | car pipeline의 persona_pick/top5_rank fallback만 해당 |

### 구현 복잡도

- **낮음**: `publish_log` 테이블에 3개 컬럼 추가 + `pipeline.py`에서 기록
- **테스트**: 기존 12개 테스트 + 신규 테스트 2~3건
- **리스크**: 없음 (기존 동작 변경 없음, 추가 기록만)

---

## 우선순위

| 기준 | 값 |
|------|-----|
| 발행 차단 | ❌ 아님 |
| 데이터 오염 | ⚠️ 있음 (분석 정확도 저하) |
| 구현 난이도 | 낮음 |
| **권장 시점** | 다음 car pipeline 리팩토링 시 병행 |

---

> **이 문서는 기술부채 등록입니다. 코드 변경은 수행하지 않았습니다.**
