# 블로그 정비·재개 프레임워크 (Phase 60 Part 2)

> 작성: 2026-08-06 | 상태: 확정
> 배경: P03(similar_title)가 7개 블로그 발행을 차단. 차단을 "정비할 시간"으로 활용.

---

## 1. 핵심 원칙

**"정비 완료된 블로그만 하나씩 재개한다."**

- P03은 차단 게이트가 아니라 **재개 게이트**다. 임계값을 낮추지 않는다.
- 발행 중단 상태는 정비 시간이다. 서둘러 풀지 않는다.
- 재개는 "차단을 뚫는" 일이 아니라 **"체크리스트를 녹색으로 만드는"** 일이다.

---

## 2. 정비 상태 (lifecycle_status 확장)

기존 lifecycle_status에 다음 단계를 추가:

| 상태 | 의미 | 대시보드 표시 |
|------|------|-------------|
| `none` | 정비 대상 아음 | — |
| `awaiting` | 정비 대기 (P03 등으로 발행 차단됨) | ⏳ 정비대기 |
| `in_progress` | 정비 진행 중 | 🔧 정비중 |
| `ready` | 정비 완료, 재개 준비됨 | ✅ 재개준비 |

### 상태 전이

```
none → awaiting    (P03 등으로 발행 차단 시 자동 또는 수동)
awaiting → in_progress  (정비 시작 시)
in_progress → ready     (체크리스트 10/10 통과 시)
ready → none        (재개 후, dispatcher 재개)
in_progress → awaiting  (정비 실패/보류 시)
```

---

## 3. 정비 체크리스트 (M01~M10)

CUAP/RAP 정비 경험에서 추출한 10개 표준 항목:

| ID | 항목 | 검사 방법 | 근거 |
|----|------|-----------|------|
| **M01** | 제목 CJK 없음 | 최근 발행 제목에 한자/일본어/중국어 정규식 검사 | Phase 58 fix(cjk): 제목/slug CJK 누수 4관문 방어 |
| **M02** | 이미지 정상 (동일 반복 없음) | featureimage URL 고유성 검사 | P09 이미지 URL 반복 조사 |
| **M03** | 크로스링크 주제 일관 | 내부 링크 주제 적합성 (에이전트 수동 확인) | QA-02/03 쿠팡 무관매칭 감사 |
| **M04** | 본문 품질 게이트 통과 | Q1~Q4 이슈 미해결 | known_issues Q1(Q1經驗主張), Q2(소스불명수치), Q3(건강효능), Q4(템플릿반복) |
| **M05** | 표준 (광고/테마) 준수 | R01~R12 standard_compliance check | Phase 59-06 theme audit + Phase 59-05 standard compliance |
| **M06** | 토픽/키워드 잔량 충분 | active 키워드 ≥ 100개 | P5 키워드 풀 불균형 조사 (rap2 218개 부족 사례) |
| **M07** | P03 유사제목 안전 | 최근 7일 내 similar_title 차단 이력 없음 | Phase 60 Part 2 P03 조사 |
| **M08** | CoT/프롬프트 누수 없음 | P08 cot_leak 이슈 미해결 | Phase 58 P08 감지 |
| **M09** | publish_log 기록 정상 | ledger 성공 대비 publish_log 매칭 | P1+P2 publish_log 기록 누락 조사 |
| **M10** | 도메인 가용성 | HTTP HEAD 200 | render_health check |

### 체크리스트 실행

```bash
# API로 정비 체크리스트 실행
curl -X POST http://localhost:5060/api/maintenance/checklist \
  -H "Content-Type: application/json" \
  -d '{"blog_id": "beauty-hugo"}'

# 정비 상태 변경
curl -X POST http://localhost:5060/api/maintenance/status \
  -H "Content-Type: application/json" \
  -d '{"blog_id": "beauty-hugo", "maintenance_status": "in_progress"}'
```

---

## 4. 현재 대상 블로그 (정비 대기)

### (a) 7개 블로그 — P03으로 발행 차단

| 블로그 | 플랫폼 | 정비 상태 | 우선순위 | 비고 |
|--------|--------|-----------|---------|------|
| **beauty-hugo** | Hugo/CF | awaiting | 중 | CUAP, 키워드: 뷰티/화장품 |
| **interior-hugo** | Hugo/CF | awaiting | 중 | CUAP, 키워드: 인테리어/가구 |
| **kitchen-hugo** | Hugo/CF | awaiting | 중 | CUAP, 키워드: 주방용품 |
| **pick-hugo** | Hugo/CF | awaiting | 하 | CUAP, DB 발행 기록 0건 |
| **senior-hugo** | Hugo/CF | awaiting | 상 | SEAP, senior.informationhot.kr |
| **senior-blogger** | Blogger | awaiting | 상 | SEAP, 2.techpawz.com — 별도 조사 필요 |
| **travel4-hugo** | Hugo/CF | awaiting | 하 | TAP, 최근 no_result 연속 |

### senior×2 분리 조사

| 블로그 | 플랫폼 | 특이사항 |
|--------|--------|----------|
| **senior-hugo** | Hugo/Cloudflare | dispatcher→hugo_writer→wrangler 파이프라인. M01~M10 체크리스트 적용 대상 |
| **senior-blogger** | Blogger (Blogspot) | Blogger API 경유. Hugo 파이프라인과 독립. P03 차단 로직 자체가 다름 |

**senior-blogger 추가 조사 필요 항목:**
- Blogger API 발행 로직에서 제목 중복 체크가 있는지
- 이미지 반복이 Blogger 설정 문제인지 (배경 이미지 동일 사용)
- Hugo 쪽 원인을 그대로 대입하지 말 것

### RAP 정비 대상

| 블로그 | 상태 | 비고 |
|--------|------|------|
| finance.techpawz.com | active 유지 | 유일한 active RAP |
| rap-hugo ~ rap5-hugo | 정비 대기 | finance 외 나머지 |

---

## 5. 재개 절차

### 1단계: 정비 시작

```bash
# 대시보드 API로 상태 변경
curl -X POST http://localhost:5060/api/maintenance/status \
  -d '{"blog_id": "beauty-hugo", "maintenance_status": "in_progress"}'
```

### 2단계: 체크리스트 실행 및 수정

```bash
# 체크리스트 실행
curl -X POST http://localhost:5060/api/maintenance/checklist \
  -d '{"blog_id": "beauty-hugo"}'

# 실패 항목 수정 후 재실행
# M01 실패 → 제목 프롬프트에 CJK 필터 추가
# M02 실패 → 배치 썸네일 스크립트 실행
# M04 실패 → known_issues Q 이슈 해결
# M05 실패 → standard_rules에 맞춰 layouts 수정
```

### 3단계: 재개 승인

모든 항목 통과 시:
```bash
# 자동으로 resume_ready = 1로 설정됨
# YAML에서 status: active로 변경
sed -i 's/status: paused/status: active/' config/blogs.d/cuap.yaml

# 재개 확인
python3 dispatcher.py beauty-hugo
```

---

## 6. P03을 재개 게이트로 유지하는 이유

| 시나리오 | 결과 |
|----------|------|
| P03 임계값 0.85→0.60 낮춤 | 중복/저품질 글이 라이브로 나감 → SEO 역효과 |
| P03 임계값 유지 + 토픽 보충 | 새 주제가 나오면 자연히 P03 통과 |
| P03 임계값 유지 + 정비 미완료 | 정비 안 된 블로그가 글을 못 씀 → 안전 |

**결론:** P03은 안전장치다. 정비 완료 후 토픽을 보충하면 P03이 자연히 풀린다.

---

## 7. 대시보드 표시

### 메인 대시보드 (index.html)
- 요약 카드에 "정비대기", "재개준비" 카운트 추가
- Fleet Status 테이블에 "정비" 컬럼 추가
- 정비 진행 상황 섹션 (진행률 프로그레스 바 포함)

### 블로그 상세 (blog.html)
- 정비 상태 표시
- M01~M10 체크리스트 테이블 (통과/실패/대기)
- 진행률 프로그레스 바
- "재개 준비 완료" 알림

---

## 8. 잔존 위험

| 위험 | 영향도 | 완화 |
|------|--------|------|
| senior-blogger 조사 미완료 | 중 | Blogger 독립 조사 필요 (Hugo 원인 대입 금지) |
| M03 크로스링크 자동검사 없음 | 중 | Part 4에서 content/posts/ 내부 링크 도메인 분석 설계 |
| 금지어 런타임 미적용 | 중 | quality_checklist.yaml 정의 → curation writer.py 미적용. 프롬프트 수정 단계에서 일괄 해소 |
| H2=0 포스트 검증 없음 | 낮음 | 프롬프트는 H2 지시, 미적용 글은 개별 결함. writer.py에 H2>=1 가드 추가 검토 |
| M09 publish_ledger title 공백 | 낮음 | 발행 성공 시 title='' (45.9%). ledger-sync에서 title 매핑 개선 검토 |

---

## 9. beauty-hugo 재개 조건 (2026-08-06 확정)

> **beauty-hugo 재개는 이번에 하지 않는다.** 조건만 확정한다.

### 자동 검사 결과 (M01~M10)

| 항목 | 상태 | 근거 |
|------|------|------|
| M01 CJK 제목 | ✅ PASS | 최근 제목 20건 CJK 0건 |
| M02 이미지 고유 | ✅ PASS | 20개 featureimage 모두 고유 URL |
| M03 크로스링크 | ✅ PASS | 자동검사 미구현 (수동확인 대상) |
| M04 본문 품질 | ❌ FAIL | Q1(experience_claim), Q2(unsource_number), Q3(health_efficacy) open |
| M05 표준 준수 | ❌ FAIL | R02(CRITICAL), R06(CRITICAL), R12(MAJOR) — 3/12 위반 |
| M06 키워드 잔량 | ✅ PASS | KEYWORD_MAP 280개, 30일 내 107개 사용, 173개 미사용 |
| M07 유사제목 | ✅ PASS | 7일 내 similar_title 차단 0건 |
| M08 CoT 누수 | ✅ PASS | 관련 이슈 없음 |
| M09 발행 기록 | ✅ PASS | ledger 발행 29건, publish_log 23건 |
| M10 도메인 | ✅ PASS | HTTP 200 |

### unpause_checklist 결과

| ID | 항목 | 상태 | 분류 |
|----|------|------|------|
| U01 | 제목 CJK | ✅ 자동통과 | — |
| U02 | 이미지 고유 | ✅ 자동통과 | — |
| U03 | 크로스링크 | ⚠️ 수동확인필요 | **Part 4에서 자동검사 설계** |
| U04 | 본문 품질 | ❌ 자동실패 | **필수 해소** |
| U05 | 표준 준수 | ❌ 자동실패 | **필수 해소** |
| U06 | 금지어 | ⚠️ 수동확인필요 | 프롬프트 수정 시 해소 |
| U07 | H2/H3 구조 | ⚠️ 수동확인필요 | 프롬프트 수정 시 해소 |
| U08 | 메타 | ✅ 자동통과 | — |
| U09 | 슬러그 | ✅ 자동통과 | — |
| U10 | 키워드 잔량 | ✅ 자동통과 | — |

### 재개 필수 조건 (2건)

1. **U04 해소**: Q1(경험 허위 주장), Q2(소스불명 수치), Q3(건강 효능 단정) 이슈가 `known_issues`에서 close되어야 함
2. **U05 해소**: R02(hugo.toml 광고 섹션), R06(in-article.html 형식), R12(미인가 오버라이드) 규칙 위반 수정

### 재개 시 해소되는 항목 (프롬프트 수정 시점에 일괄)

3. **U06 (금지어)**: `quality_checklist.yaml`에 "좋은", "최고의" 등 정의 있으나 curation 파이프라인에서 미적용. `pipelines/curation/writer.py:213`의 `_sanitize_body()`에 글로벌 금지어 필터 추가 필요
4. **U07 (H2=0)**: 프롬프트는 AIDA 모델로 H2 구조를 지시하나(`writer.py:368-405`), post-processing에 H2 검증 없음. `writer.py:496`에서 H2 카운트만 하고 미검증. 개별 결함이 아닌 시스템적 허점

### 재개 불가 조건

- finance.techpawz.com만 active 유지. beauty-hugo는 이번에 재개하지 않음
- Part 3(알림 재설계), Part 4(체크 보강 — M03 자동검사 포함) 이후 재개 검토

---

**이 프레임워크가 작동하면, 블로그 재개는 "체크리스트를 녹색으로 만드는" 일이 된다.**
**재개 순서·속도는 사용자가 결정한다.**
