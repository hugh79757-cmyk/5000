# SECTOR_DIAGNOSTIC_RESULT.md

> **진단 시각**: 2026-08-19 11:30~11:33 KST
> **진단 방법**: redacted 구조화 로그 추가 → 1회 직접 실행 → 실패 지점 확정
> **대상**: sector-hugo 18일 연속 no_content (59회 실패)

---

## 1. 근본원인: _parse_response() TITLE: 마커 미존재

**[검증됨] LLM 호출은 전부 성공. 파싱 단계에서 title이 비어 pipeline이 no_content 반환.**

### 증거 (진단 실행 로그)

5회 LLM 호출 전부 RESULT=ok, gemini-3.5-flash-lite 사용:

| 시도 | run_id | topic | model | content_len | elapsed | result |
|------|--------|-------|-------|-------------|---------|--------|
| 1 | 8b623f1b | comparison | gemini-3.5-flash-lite | 2725 | 9.60s | RESULT=ok |
| 2 | 133ee670 | rate_sensitive | gemini-3.5-flash-lite | 2725 | 8.57s | RESULT=ok |
| 3 | 9cf637f2 | rotation | gemini-3.5-flash-lite | 3111 | 8.57s | RESULT=ok |
| 4 | f2784db8 | value | gemini-3.5-flash-lite | 2451 | 7.63s | RESULT=ok |
| 5 | 37e6022c | daily_top | gemini-3.5-flash-lite | 2628 | 12.78s | RESULT=ok |

**모든 호출에서 `BODY: 마커 없음 — 전체 응답을 본문으로 사용` 경고 발생:**
```
parse_response 입력 첫 300자: 다각화된통신서비스·도로와철도운송 업종 순환 주기 분석, 2026년 8월 매수 타이밍

오늘 장 마감 후 가장 많이 검색된 업종은...
(바로 본문 시작 — TITLE: 마커 없음)
```

**파싱 결과 전부 `title=[]`:**
```
parse 결과: title=[], body_len=2725
parse 결과: title=[], body_len=2725
parse 결과: title=[], body_len=3096
parse 결과: title=[], body_len=2441
parse 결과: title=[], body_len=2613
parse 결과: title=[], body_len=2722
```

**pipeline.py 동작:**
```python
# sector writer 결과 (시도1): topic=comparison title=[]
# sector writer 결과 (시도2): topic=rate_sensitive title=[]
# sector writer 결과 (시도3): topic=rotation title=[]
# sector writer 결과 (시도4): topic=daily_top title=[]
# sector writer 결과 (시도5): topic=comparison title=[]
# → 5회 전부 title 비어있음 → no_content 반환
```

### 실패 메커니즘 (단계별)

```
1. data_selection    → 237건 sector 데이터에서 topic별 데이터 선택 ✅ 성공
2. llm_call          → gemini-3.5-flash-lite 호출, content 수신 ✅ 성공 (2451~3111자)
3. parse_response    → TITLE: 마커 없음 → title="" 반환 ❌ 실패
4. pipeline guard    → if not _article.get("title") → True → None 반환
5. 5회 반복 후       → no_content
```

### 왜 TITLE: 마커가 없는가

프롬프트에 다음 출력 형식을 지정:
```
[출력]
TITLE: (제목)
CATEGORY: 업종비교
TAGS: (쉼표 구분, 5개)
BODY:
(본문)
```

그러나 **gemini-3.5-flash-lite가 이 형식을 무시하고 기사 본문을 바로 시작**. 이 모델은 한국어 프롬프트의 `[출력]` 형식 지시를 준수하지 않는 경향.

### 근본원인 요약

| 항목 | 값 |
|------|-----|
| **근본원인** | `_parse_response()`가 `TITLE:` 마커를 찾지만, gemini-3.5-flash-lite가 해당 마커 없이 본문 직접 출력 |
| **LLM 호출** | 전부 성공 (5/5, content_len=2451~3111) |
| **파싱 실패** | 5/5 전부 title="" (BODY: 마커도 없음 → 전체 본문 사용) |
| **pipeline guard** | `if not _article.get("title")` → True → None |
| **신뢰도** | **높음** — 직접 실행으로 확인 |

### 왜 이전에는 성공했는가

- 마지막 성공(08-01) 이후 `_call_api()` → `ai_generate()`로 전환
- 기존 `_call_api()`는 OpenAI gpt-4o-mini를 직접 호출 → `TITLE:` 형식 준수
- `ai_generate()`는 fallback chain 사용 → gemini-3.5-flash-lite가 1순위 → 형식 무시
- gemini-3.5-flash-lite는 한국어 `[출력]` 형식 지시를 무시하는 모델 특성

---

## 2. 수정 없이 확인된 사실

| 항목 | 값 |
|------|-----|
| 데이터 선택 | ✅ 정상 (sector 237건/3일, index 49건/3일) |
| LLM 호출 | ✅ 정상 (5/5 성공, gemini-3.5-flash-lite) |
| 파싱 | ❌ TITLE: 마커 없음 → title="" |
| 중복 가드 | 미도달 (title이 비어있어 slug 생성 불가) |
| 콘텐츠 길이 | 2451~3111자 (3500자 미달 — body_md 기준) |
| 쿨다운 | cleared (진단 목적) |

---

## 3. 최소 수정안 (우선순위순)

### 수정안 A: _parse_response에 title fallback 추가 (1줄)

```python
# writer.py _parse_response() — TITLE: 마커 없을 때 첫 H1/H2에서 title 추출
if not title:
    for line in content.strip().split("\n")[:10]:
        line = line.strip()
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
        elif line.startswith("## "):
            title = line.lstrip("## ").strip()
            break
```

**효과**: gemini-3.5-flash-lite가 제목을 H1/H2로 출력하면 자동 추출
**위험도**: 낮음 — 기존 동작에 추가만 함
**테스트**: mock 테스트로 검증 가능

### 수정안 B: 프롬프트에 TITLE: 마커 강화

```
[출력] (반드시 아래 형식을 정확히 지켜주세요)
TITLE: (제목)
```

**효과**: 모델이 형식 준수 유도
**위험도**: 낮음
**단점**: gemini-3.5-flash-lite가 여전히 무시할 수 있음

### 수정안 C: model 교체 (gemini-3.5-flash-lite 제외)

`models.yaml`에서 sector-hugo용 tier에서 gemini-3.5-flash-lite 비활성화

**효과**: 형식 준수하는 모델로 전환
**위험도**: 중간 — 다른 모델의 품질/속도 영향

### 권장: 수정안 A + B 병행

1. `_parse_response`에 title fallback 추가 (모델 관계없이 방어)
2. 프롬프트에 TITLE: 마커 강화 (모델 유도)

---

## 4. 롤백안

| 단계 | 조치 |
|------|------|
| 1 | `_parse_response` fallback 코드 제거 |
| 2 | 프롬프트 원복 |
| 3 | sector-hugo status: paused |
| 4 | 스케줄러가 다음 실행에서 no_content 반환 → 기존 상태로 복귀 |

---

## 5. deals-hugo 기술부채

### catchup 오판 기록

| 항목 | 값 |
|------|-----|
| 블로그 | deals-hugo |
| 파이프라인 | etap |
| 패턴 | 성공 후 catchup에서 "no_data" 오판 기록 |
| 오늘 성공 | ✅ publish_log id=6425, 09:29:38 |
| 영향 | 로그상 "12회 no_data" — 실제 발행은 정상 |
| 기술부채 분류 | low — 로그 노이즈만 해당, 실제 장애 아님 |
| 수정 불필요 | ✅ catchup 메커니즘 개선은 별도 작업 |

---

## 6. 커밋·변경 요약

| 파일 | 커밋 | 내용 |
|------|------|------|
| `STAP/pipelines/sector/writer.py` | `b5ee63c2` | ai_generate 레퍼터링 + redacted 구조화 로그 |
| `STAP/tests/test_sector_writer_diag.py` | `50ab77e1` | mock 테스트 6건 (독립 커밋) |
| `5000/data/cooldown.json` | (config) | sector-hugo daily cooldown 해제 (진단 목적) |

### DB 백업

| 파일 | 경로 |
|------|------|
| pre-diagnostic | `STAP/data/stap_content.db.bak_sector_diag_20260819_112753` |

---

## 7. 잔존 위험

1. **sector-hugo cooldown 해제됨**: 진단 중 cooldown을 제거했으므로, 스케줄러가 다음 실행에서 다시 no_content → daily cooldown 설정 예정. **정상 동작** — 추가 조치 불필요.
2. **gemini-3.5-flash-lite 형식 미준수**: 수정안 A/B 미적용 시 sector-hugo는 계속 no_content. **가장 시급한 수정 대상**.
3. **STAP subprocess 로그 가시성**: scheduler log에는 stderr 요약만 기록. sector-diag 로그는 직접 실행 시에만 확인 가능. **모니터링 개선 필요**.

---

> **이 보고서는 READ-ONLY 진단 + 진단용 로그 추가 + 1회 실행으로 작성되었습니다.**
> **push·다른 블로그 변경·85개 커밋 반영은 수행하지 않았습니다.**
