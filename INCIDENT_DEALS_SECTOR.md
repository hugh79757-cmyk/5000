# INCIDENT_DEALS_SECTOR.md

> **진단 시각**: 2026-08-19 10:10 KST
> **진단 유형**: READ-ONLY — 코드/설정/DB 변경·재실행·API/LLM 호출·push·배포 없음

---

## A. deals-hugo 12회 no_data 진단

### 핵심 발견: deals-hugo는 정상 동작 중

deals-hugo는 **실제 실패가 아님**. catchup 메커니즘의 오판.

### 실행별 재구성 (최근 12회)

| # | 시각 | reason | 세부 | publish_log 확인 |
|---|------|--------|------|-----------------|
| 1 | 08-16 20:10 | no_result | catchup 보충 실패 (1/3) | 08-16 09:25 성공 (id=6229) |
| 2 | 08-16 20:24 | no_result | catchup 보충 실패 ( scheduler 재시작 후) | — |
| 3 | 08-17 14:09 | **no_data** | catchup 보충 실패 (1/3) | 08-17 14:09 성공 (id=6362) |
| 4 | 08-17 14:14 | no_result | catchup 보충 실패 (2/3) | — |
| 5 | 08-17 14:18 | no_result | catchup 보충 실패 (3/3) | — |
| 6 | 08-19 09:29 | **no_data** | catchup 보충 실패 (1/3) | 08-19 09:29 **성공** (id=6425) |
| 7 | 08-19 09:36 | no_result | catchup 보충 실패 (2/3) | — |
| 8 | 08-19 09:41 | no_result | catchup 보충 실패 (3/3) | — |

**#3과 #6은 특히 중요**: no_data를 보고했지만, 실제 publish_log에는 동일 시각에 성공 기록 존재.

### 패턴: flights-hugo와 동일

| 비교 항목 | flights-hugo | deals-hugo |
|-----------|-------------|-----------|
| 파이프라인 | etap | etap |
| 실패 유형 | content_quality_gate (draft) | no_data / no_result |
| self-healing | ✅ 다른 route 시도 → 성공 | ✅ 다른 route 시도 → 성공 |
| 오늘 성공 | ✅ 08:50 (sea→slc) | ✅ 09:29 (Montego Bay) |
| catchup 오판 | 있음 (성공 후 보충 실패) | 있음 (성공 후 보충 실패) |

### 근본원인

**catchup 메커니즘 오판**: 파이프라인이 성공하면 `expected=1 actual=0` → `actual=1`로 갱신해야 하는데, 성공 직후의 catchup 시도가 아직 `actual=0`으로 남아 보충 실패로 기록됨.

**실제 발행은 정상** — 08-13~19 기간 매일 1건 이상 발행 성공 확인.

### 판정

| 항목 | 값 |
|------|-----|
| 근본원인 | catchup 메커니즘 오판 (성공 후 보충 실패 기록) |
| 신뢰도 | **높음** — publish_log에서 성공 기록 확인 |
| 영향 범위 | deals-hugo만 해당 (다른 ETAP 블로그와 동일 패턴) |
| 최소 수정안 | **불필요** — 정상 동작. catchup 로직 개선은 별도 작업 |
| 테스트 | 다음 정규 실행에서 성공 확인 |
| canary | 불필요 |
| rollback | 불필요 |

---

## B. sector-hugo 17회 no_content 진단

### 마지막 정상 발행

| 항목 | 값 |
|------|-----|
| 마지막 성공 | 2026-08-01 10:30:37 |
| 마지막 기사 | "최근 하락세 두드러진 에너지장비및서비스, 반등 가능성은?" |
| 이후 경과 | **18일 연속 발행 실패** (59회 실패) |

### 데이터 현황

| 소스 | 전체 | 미사용 (3일) | 상태 |
|------|------|-------------|------|
| sector | 7,268 | 237 | ✅ 충분 |
| index | 2,352 | 49 | ✅ 충분 |
| krx | 103 | 0 | ❌ 소진 |

**데이터는 충분** — sector 237건, index 49건. 데이터 부족이 아님.

### 실행별 재구성 (최근 17회)

| # | 시각 | reason | 세부 |
|---|------|--------|------|
| 1 | 08-13 07:51 | **no_content** | 5 토픽 전부 시도, LLM 생성 실패 |
| 2 | 08-13 08:56 | **no_content** | 동일 패턴 |
| 3-10 | 08-13 10:08~20:28 | no_result | 30분 쿨다운 차단 (도미노) |
| 11-12 | 08-14 07:32 | stap_subprocess_error | subprocess 크래시 2회 |
| 13 | 08-14 07:47 | **no_content** | LLM 생성 실패 |
| 14-17 | 08-14 07:54~16:28 | no_result | 30분 쿨다운 차단 |

**패턴**: no_content 3회 (실제 파이프라인 실행) → subprocess error 2회 → no_content 1회 → no_result 12회 (쿨다운 도미노)

### 형제 블로그 비교

| 블로그 | 파이프라인 | 최근 성공 | 특이사항 |
|--------|-----------|-----------|---------|
| stock-hugo | stock | 08-16 | duplicate_slug (데이터→생성은 됨) |
| ipo-hugo | stock | 08-19 | 정상 |
| **sector-hugo** | stock(sector) | **08-01** | **LLM 생성 자체 실패** |

**핵심 차이**: stock-hugo는 데이터 수집→LLM 생성이 정상. sector-hugo는 **LLM 생성 자체가 실패**하여 article을 생성하지 못함.

### 근본원인

**[부분검증] LLM 생성 실패 — 가장 높은 확률**

가설 1 (높음): `ai_generate()`가 모든 토픽에서 None 또는 빈 content 반환
- LLM 폴백 체인(무료 모델 16개 → DeepSeek 유료)이 전부 실패하거나
- 반환 content의 BODY: 마커 없음 + 파싱 실패로 title이 빈 값
- `generate_sector_article()`이 `{"title": "", "body_md": ...}` 반환 시 None 처리

가설 2 (중간): stap_subprocess_error — Python 환경 문제
- 08-14 2회 발생, `.venv` 의존성 또는 import 에러

가설 3 (낮음): 3중 가드에 모두 차단
- 마지막 기사가 18일 전이라 2일 lookback 가드가 발동 안 됨 → 확률 낮음

### 신뢰도

**중간** — LLM 생성 실패가 원인이라는 추론은 강하지만, STAP subprocess stdout/stderr 로그에 `ai_generate` 결과가 남아 있지 않아 **직접 확인 불가**.

확인된 사실:
- [검증됨] 데이터는 충분히 있음 (sector 237건/3일, index 49건/3일)
- [검증됨] 쿨다운 메커니즘이 no_content → no_result 도미노를 유발
- [검증불가] `ai_generate()`의 실제 반환값 — STAP subprocess 로그 미보유

### 최소 수정안

| 순위 | 수정안 | 설명 | 위험도 |
|------|--------|------|--------|
| 1 | **ai_generate 결과 로깅** | writer.py에 상세 로그 추가 → 원인 직접 확인 가능 | 낮음 |
| 2 | **days 파라미터 확대** | `get_unused_data(..., days=3)` → `days=7` | 낮음 |
| 3 | **collect_all 주기 단축** | 20시간 → 12시간 | 낮음 |
| 4 | **parse_response 강화** | BODY: 마커 없음 시 title 파싱 폴백 | 중간 |
| 5 | **프롬프트 완화** | "수치 데이터가 없는 항목은 테이블에서 제외" 완화 | 중간 |

### 테스트 방법

```bash
# 1. ai_generate 반환값 확인 (진단용 로그 추가 후)
python3 dispatcher.py sector-hugo 2>&1 | grep 'ai_generate\|BODY:\|title.*EMPTY'

# 2. 데이터 수집 상태 확인
sqlite3 data/stap_content.db "SELECT source, COUNT(*) FROM collected_data WHERE used=0 GROUP BY source"

# 3. 토픽 선택 확인
python3 -c "
from pipelines.sector.pipeline import _pick_topic
import sqlite3
conn = sqlite3.connect('data/stap_content.db')
for _ in range(5):
    t = _pick_topic(conn, 'sector-hugo')
    print(t)
"
```

### canary 절차

1. 진단용 로그 추가 (writer.py, pipeline.py)
2. `python3 dispatcher.py sector-hugo` 1회 실행
3. 로그에서 `ai_generate` 반환값 확인
4. 성공 시 로그 제거 + 정규 스케줄 유지
5. 실패 시 원인 분석 후 추가 수정

### 롤백 절차

| 단계 | 조치 |
|------|------|
| 1 | 추가된 로그 코드 제거 |
| 2 | sector-hugo `status: paused` |
| 3 | 스케줄러가 다음 실행에서 no_content 반환 → 정상 복귀 (기존 상태) |

---

## C. 공통 분석

### 최근 코드·설정·프롬프트 변경

| 항목 | deals-hugo | sector-hugo |
|------|-----------|------------|
| 코드 변경 | 없음 (8/1 이후) | 없음 (8/1 이후) |
| 설정 변경 | 없음 | 없음 |
| 프롬프트 변경 | 없음 | 없음 |
| API 상태 | 정상 (ETAP 파이프라인 공통) | 추정 (STAP subprocess 의존) |

### API/quota 상태

| 항목 | 값 |
|------|-----|
| LLM fallback chain | 16개 무료 모델 + DeepSeek 유료 |
| Coupang API | 정상 (다른 블로그 발행 확인) |
| ETAP 파이프라인 | 정상 (flights, deals, foodtour 등 발행) |
| STAP subprocess | 불안정 (08-14 크래시 2회) |

### 잔존 위험

1. **deals-hugo**: catchup 오판가 지속될 수 있음. 정상 동작이므로 임계치 미달.
2. **sector-hugo**: 18일 연속 실패. LLM 생성 실패 원인 미확인. 데이터는 충분하나 생성 자체가 안 됨.
3. **STAP subprocess 안정성**: 08-14 크래시가 환경 문제인지 코드 문제인지 미확인.

---

> **이 보고서는 READ-ONLY 진단만 수행했습니다. 코드/설정/DB 변경·재실행·API/LLM 호출·push·배포는 수행하지 않았습니다.**
