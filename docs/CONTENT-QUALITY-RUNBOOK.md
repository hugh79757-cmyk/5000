# 콘텐츠 품질 룩북 (CONTENT-QUALITY-RUNBOOK)

대상: cuap 큐레이션 발행물. content_quality 체크가 감지하는 구조 규격 이탈의
**코드 판정표**와 **해결 절차**. 에이전트는 이 문서를 참조해 오류코드를 판정하고
지정된 조치로 자동 교정한다.

- 감지 위치: `ops_dashboard/checks/content_quality.py` (`_analyze`)
- 교정 위치: `pipelines/curation/pipeline.py` (`_normalize_product_blocks`)
- 규격 원천: 본 문서가 SSOT. 신규 이탈 발견 시 여기에 코드 추가 후 감지·교정 반영.

---

## 판정표 (오류코드 → 증상 → 원인 → 조치)

| 코드 | 결함 문자열(감지) | 증상 | 근본 원인 | 조치 |
|------|------------------|------|-----------|------|
| CQ01 | 빈 불릿(라벨만) / 빈 리스트 항목 | `- 배송:` 뒤 값 없음, `-` 단독 줄 | writer 프롬프트가 값 없는 필드도 라벨 출력 | `_normalize_product_blocks` (1)에서 값 없는 라벨 불릿·단독 대시 제거. writer.py 프롬프트에서 빈 필드 미출력. |
| CQ02 | CTA가 리스트 항목에 갇힘 | 쿠팡 버튼이 `- <div…>` 형태로 리스트 안 | AI가 CTA를 불릿 항목으로 출력 | `_normalize_product_blocks` (3-b)에서 앞의 `- ` 제거 + 앞뒤 빈 줄로 독립 블록화. |
| CQ03 | 제휴문구 누락 / 제휴문구 과다(N회) | 제휴 고지가 0회 또는 3회+ | AI가 상품마다 제휴문구 삽입 | `_normalize_product_blocks` (2)에서 전체 삭제 후 (4)에서 '상품별 상세 비교' 앞 1회 + 글 끝 1회로 고정(정상 1~2회). |
| CQ04 | 상품별 상세 비교 h2 아님 | 소제목이 작은 볼드(strong/**) | AI가 `##` 대신 `<strong>`/`**`로 출력 | `_normalize_product_blocks` (4-b)에서 strong/bold → `## 상품별 상세 비교` 강제. (4-c)에서 누락 시 첫 h3 앞에 삽입. |
| CQ05 | 상품 이미지 부족(상품 N vs 이미지 M) | 상품 개수보다 이미지 적음(5개 중 하나 빠짐) | 특정 상품 `coupang=SKIP` → product_image 미수집 | 수집 단계에서 이미지 없는 상품 대체·재수집. 후처리는 데이터 있으면 자동 삽입(5). ※근본 해결은 수집부, 후처리로는 못 채움. |
| CQ06 | (소스검사) raw img 방식 사용 | `.md`에 `<img>` 직삽입(figure 미사용) | 과거 raw img 삽입 로직 잔재 | 상품 이미지는 `{{< figure src=… alt=… >}}` 숏코드로 통일. `_normalize_product_blocks` (5)가 figure로 생성. ※라이브 HTML로는 감지 불가 → 소스(.md) 기준 검사. |
| CQ07 | 상품 설명 문단 소실(N개) | 상품 h3 블록에 이미지·CTA만 있고 설명 문장(CJK) 없음 | 설명 보존 회귀(desc-fix 재발) — 후처리가 설명 `<p>`를 지우는 경로 | `_normalize_product_blocks`의 설명 문단 보존 로직 점검(이미지와 설명이 같은 `<p>` 안이면 `<p>` 유지·텍스트 소실에 취약). 재발 시 후처리 수정. |
| CQ08 | 상품 이미지 중복(상품당 N장, 규격 1장) | 상품 h3 블록에 이미지 2장+(health 4상품·8이미지) | **이중삽입**: AI가 마크다운 이미지를 쓰고(불규칙), 후처리(5)가 같은 상품에 figure를 또 삽입 → figure 변환·gallery 래핑으로 2장 렌더 | `_normalize_product_blocks` (5)에서 방식A/B 매칭 성공 시 해당 h3 구간의 AI 마크다운 이미지 줄(`![](...)` 단독 줄) 제거 → 상품당 figure 1장만. url 미매칭 폴백 시 AI 이미지 유지(0장 방지). |

---

## 코드별 상세

### CQ01 — 빈 불릿
- 감지: `<li>배송:</li>`, `<li></li>`, `- ` 단독.
- 조치: 후처리 (1) 자동 제거. 반복 시 writer.py 프롬프트 점검(값 없는 필드 출력 금지).

### CQ02 — CTA 리스트 갇힘
- 감지: `<li>…btn-price-check`.
- 조치: 후처리 (3-b) 독립 블록화. CTA는 항상 리스트 밖 중앙 정렬 div.

### CQ03 — 제휴문구 위치·개수
- 규격: 정확히 2회 — '상품별 상세 비교' 직전 1회 + 글 맨 끝 1회.
- 감지: DISCLOSURE 카운트 0 또는 3+.
- 조치: 후처리 (2)+(4). 상품 블록 중간 삽입 금지.

### CQ04 — 상품별 상세 비교 h2
- 규격: `## 상품별 상세 비교` (h2). 그 아래 각 제품은 `###` (h3).
- 감지: '상품별 상세 비교' 존재하나 `<h2>…` 아님.
- 조치(**2곳 짝 필수**):
  1. `pipelines/curation/pipeline.py` `_normalize_product_blocks` (4-b)(4-c) — strong/bold→`##` 변환·누락 시 삽입.
  2. `shared/publishers/hugo_writer.py` `_ALLOWED_H2_PATTERNS` — 발행 시 H2-GUARD가
     allow-list에 없는 `##`을 전부 `<strong>`으로 되돌린다. 강제 h2 문구는 반드시 여기 등재.
- **핵심 함정**: pipeline.py에서 `##`을 만들어도 H2-GUARD allow-list에 없으면 발행 단계에서
  bold로 무력화된다(2026-08-16 근본원인). pipeline.py만 고치면 라이브에 안 먹음.
- CSS로 키우지 말 것 — 소스가 strong이면 h2 변환+allow-list 등재가 정답.

### CQ05 — 상품 이미지 개수 부족
- 규격: 상품 섹션('상품별 상세 비교' h2 ~ 다음 h2)의 h3 개수 = 이미지 개수.
- 감지: 상품 섹션 내 h3 > img.
- 조치: **수집부 문제**. 후처리로 못 채움. 이미지 없는 상품은 수집 단계 재시도/대체.
  당장 급하면 해당 상품 제외 또는 대체 상품으로 교체.

### CQ06 — 이미지 방식 통일(figure)
- 규격: 상품 이미지는 Hugo `{{< figure >}}` 숏코드. raw `<img>` 금지.
- 근거: cuap 15개 블로그 전수조사 결과 figure 83% 우세 → 단일 규격 확정(2026-08-16).
- 감지: 라이브 HTML 불가(둘 다 `<img>` 렌더). `.md` 소스에서 `<img` 검출로 판정.
- 조치: 후처리 (5)가 figure로 생성. 잔재는 raw img → figure 치환.

### CQ07 — 상품 설명 문단 소실
- 규격: 상품 섹션('상품별 상세 비교' h2 ~ 다음 h2) 내 각 h3 블록에 설명 문장(CJK) 1자 이상.
- 감지: 상품 섹션 내 각 h3 블록(`</h3>` ~ 다음 h3)에서 `<img>/<figure>/CTA`는 있으나
  태그·CTA 제거 후 CJK 텍스트가 0자면 위반. FAQ h3는 섹션 밖이라 자동 제외.
- 구조 함정: 발행물은 `<p><figure>…</figure>설명</p>` 형태(이미지와 설명이 같은 `<p>`).
  desc-fix 회귀 시 `<p>`는 남고 **텍스트만 사라짐** → 태그 존재가 아닌 텍스트 기준 판정.
- 조치: `_normalize_product_blocks` 설명 보존 로직 점검(재발 시). 감지로는 재발만 포착,
  교정은 후처리 수정 필요. CQ07은 조기경보(needs_human: false).

### CQ08 — 상품 이미지 중복(상품당 2장+)
- 규격: 상품 섹션('상품별 상세 비교' h2 ~ 다음 h2) 내 **각 상품(h3) 블록 이미지 정확히 1장**.
- 감지: 상품 섹션 내 각 h3 블록(`</h3>` ~ 다음 h3)의 `<img>` 개수(라이브 HTML 기준, figure는
  `<figure><img>`로 렌더되므로 `<img>` 수 = 실제 이미지 수). 2장 이상이면 위반
  (`[CQ08] 상품 이미지 중복(상품당 {n}장, 규격 1장)`). FAQ h3는 섹션 밖이라 자동 제외.
- 근본 원인: **이중삽입** — ① writer 프롬프트가 "상품 이미지 URL 그대로 사용"을 지시해 AI가
  h3 블록에 마크다운 이미지 `![alt](쿠팡URL)`를 직접 작성(LLM 성향에 따라 불규칙: pet 글 미작성,
  health 글 작성) ② 후처리 (5)가 방식A(pageKey)/방식B(이름매칭)으로 같은 상품에
  `{{< figure src=product_image >}}`를 또 삽입 ③ 발행 시 IMAGE-GUARD(URL>200자 → R2 재업로드
  `curation-images/thumbnails/{md5(url)[:16]}.webp` 치환) → figure 변환(caption=다음 줄 소비) →
  연속 figure 2장이 gallery 래핑. 두 이미지는 **동일 이미지 중복**(R2 파일명 = md5(쿠팡URL)[:16],
  health 4쌍 md5 대조로 증명).
- 조치: `_normalize_product_blocks` (5)에서 방식A/B 매칭 성공 시(=`if url:`) 해당 h3 구간 내
  **순수 마크다운 이미지 줄**(`^\s*!\[[^\]]*\]\([^)]*\)\s*$` 단독 줄)을 제거 → 상품당 figure 1장만.
  url 미매칭(폴백, figure 미삽입) 시엔 AI 이미지 유지(0장 방지). 설명 문장 줄은 이미지 줄과
  분리되어 있어 이미지 줄만 제거하면 단락으로 보존(CQ07 유지). gallery 래핑은 이중 figure가
  사라져 자동 발생 안 함.

---

## 강제 H2 등록 원칙 (H2-GUARD 연동)

curation 파이프라인이 강제하는 **모든 h2**는 발행 시 H2-GUARD를 통과해야 살아남는다.

- H2-GUARD 위치: `shared/publishers/hugo_writer.py` `_ALLOWED_H2_PATTERNS` + `_fix_invalid_h2`.
- 동작: allow-list에 없는 `## 제목`은 발행 시 `<strong>제목</strong>`으로 되돌려 디스크 기록.
- 규칙: 후처리가 강제 삽입하는 h2 문구는 **반드시 `_ALLOWED_H2_PATTERNS`에 정규식으로 등재**.
- 현재 등재된 curation 강제 h2: `상품별 상세 비교`.
- 신규 강제 h2 추가 시: (a) 후처리에서 h2 생성 → (b) allow-list 등재 → (c) 발행 테스트로 h2 유지 확인.

---

## 신규 이탈 추가 절차 (에이전트/시니어)
1. 새 규격 이탈 발견 → 본 판정표에 CQnn 코드 신설(증상·원인·조치 명시).
2. `content_quality._analyze`에 감지 룰 추가(라이브 감지 가능한 경우).
3. 소스 기준 규격이면 `standard.py` R-룰 계열로 소스 검사 추가.
4. 교정은 `_normalize_product_blocks`에 결정론적 로직으로 반영(사람 개입 0 목표).
5. 커밋 + 태그. 본 문서 갱신.
