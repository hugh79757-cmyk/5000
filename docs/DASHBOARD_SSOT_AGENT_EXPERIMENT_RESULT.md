# DASHBOARD SSOT AGENT EXPERIMENT RESULT

> Generated: 2026-08-20 (READ-ONLY 재분류 — 코드 수정 없음 / 커밋 없음 / RecheckAll 없음 / DB 변경 없음 / 배포 없음 / push 없음)
> 전제: DASHBOARD_TRUST_GATE_REPORT.md(교정본) + VERIFIED_REMEDIATION_QUEUE.md + DASHBOARD_CHECKER_PATCH_RESULT.md 의 판정 기록을
> "대시보드만으로 판정 가능했는가"라는 실험 관점에서 재분류한 결과.
> 참고: 이 문서는 커밋되지 않았음 (untracked — 사용자 지시에 따라 어떤 커밋도 수행하지 않음).

### Baseline 변경 이력

| 버전 | TP | FP | EA | UNC | 합계 | Precision | 비고 |
|---|---|---|---|---|---|---|---|
| v1 (교정본) | 212 | 196 | 5 | 25 | 438 | 52.0% | 부모집계 제거 + c01·c06 재판정 |
| **v2 (권위본)** | 212 | 207 | 8 | 11 | 438 | **50.6%** | semantic 11건 FP→UNC, R2-01 3건 UNC→EA |

v1→v2 변경: semantic SEM-Q2 11건(Viator 상품카드 할인배지/자연조언) FP 확정, R2-01 techpawz 3건 blogsmith r2_uploader 확인→EA. 본 문서의 수치는 **v2(authoritative)** 기준.

---

## 실험 질문

> 대시보드(check_results + evidence_url + pending_fixes)를 SSOT(Single Source of Truth)로 삼아
> 에이전트가 트러스트 게이트 감사(556 fail 행 재분류)를 수행할 때, 대시보드만으로 얼마나 정확히 판정할 수 있는가?

---

## ① 에이전트 판단 구분 (4범주 상호배타 재분류 — row ID 기준)

> 438 active fail 행을 stable row ID 기준으로 4범주로 재분류.
> **assertion: 118 + 102 + 206 + 12 = 438 ✓** (python 검증)

### 범주 1. dashboard-only correct — 대시보드만으로 맞춘 판단 (외부 근거 불필요, 118행)

| check | 행 수 | row ID (범위/예시) | 근거 (대시보드 내) |
|---|---|---|---|
| FM-DRAFT | 30 | 89442~143989 | detail에 draft:true + 포스트명 명시 |
| FM-FEATUREIMAGE | 4 | 102518~145438 | detail에 URL 길이 초과 사유 |
| FM-MISSINGKEYS (TP 30) | 30 | 144054~145906 (일부) | detail에 누락 키 목록 — tags 진짜 누락분 |
| c03_fm_key_leak | 19 | 144193~145895 | detail에 유출 라인 |
| c05_draft_publish | 1 | — | detail에 draft:true |
| data_stock | 14 | 144222~145695 | detail에 종목 소진 |
| freshness | 7 | 144015~145888 | detail에 경과 일수 |
| maintenance_checklist | 6 | 144234~145892 | detail에 미이행 항목 |
| rap_leak | 2 | 145504~145526 | detail에 이중 frontmatter |
| render_health | 2 | 145817~145889 | detail에 og:image 누락 |
| R01 | 1 | 144013 | detail에 showTableOfContents |
| R06 | 1 | 144488 | detail에 fluid 누락 |
| standard_compliance(정보hot) | 1 | 145352 | detail에 R07/R08/R12 |

**소계: 118행 / 438 (26.9%)** — evidence_url 재확인 없이 fail→TP 확정 가능.

### 범주 2. externally confirmed correct — 외부 근거로 TP/EA 확정 (102행)

| check | 행 수 | 필요했던 외부 근거 |
|---|---|---|
| c06 (TP 41) | 41 | sitemap 미등록 + deploy.log 부재 + 라이브 URL 상태 (mtime 최근=미배포 확정) |
| THUMBNAIL-01 | 37 | URL GET (R2 .jpg / gov CDN / visa 403 — 규칙 위반 실재 확인) |
| CQ (TP 9) | 9 | 라이브 HTML 제휴문구·이미지 검증 |
| c04 (TP 3) | 3 | 라이브 permalink 문맥 (camping/health/beauty CoT 노출) |
| crosslink | 4 | HTTP 200 확인 (링크 정상 — 낮은 우선순위 TP) |
| R2-01 (EA 8) | 8 | DNS + blogsmith r2_uploader.py (custom domain 확인) + 정부·관광 CDN |

**소계: 102행 / 438 (23.3%)**

### 범주 3. externally corrected — 대시보드 단독 판정 시 오류 → 외부 근거로 FP 교정 (206행)

| check | 행 수 | 최초(대시보드 단독) | 교정 (외부 근거) | 오류 원인 |
|---|---|---|---|---|
| c08 (FP 83) | 83 | TITLE_MISMATCH/OG_MISSING fail | FP — 원문 frontmatter title 정상, 404 포스트 오인 | `_parse_frontmatter` title 콜론 잘림 + status code 폐기 (원인 미노출) |
| c01 | 47 | 곡선따옴표=결함 fail | FP — 자연어 문맥 (소유격/인용구/대화문) | detail이 "C01 위반: 곡선따옴표"만 표기 — 문맥은 원문 필요 |
| FM-MISSINGKEYS (FP 40) | 40 | 키 누락 fail | FP — `_index.md`(리스트 템플릿) 스캔 오인 | 파일 구조 지식 외부 필요 |
| CQ03/CQ05 | 14 | 제휴문구/이미지 fail | FP — STAP 비제휴 brand | brand 매핑(blog_lifecycle) 외부 필요 |
| c06 (FP 10) | 10 | mtime<1일 fail | FP — sitemap 등록됨(배포 완료) | mtime 경고만으로 배포 여부 구분 불가 |
| c04 (1) | 1 | 패턴 매칭 fail | FP — escape-hugo 자연어 ("you'll need to think critically") | 매칭 패턴만으로 자연어 판별 불가 |
| semantic (FP 11) | 11 | 무근주장 fail | FP — Viator 상품카드 할인배지/자연 조언/페이지네이션 URL | 라이브 렌더 문맥 외부 필요 |

**소계: 206행 / 438 (47.0%)** — 대시보드 단독 판정 시 이 행들이 오판됨.

### 범주 4. unresolved-abstained — 최종 판정 보류 (12행)

| check | 행 수 | row ID (개별) | 보류 사유 |
|---|---|---|---|
| c08 travel3-hugo | 1 | **145876** | 라이브 404 (포스트 소멸/URL 변경) — 배포 문제인지 삭제인지 판정 불가 |
| semantic UNC 10 | 10 | deal **144053**, hotissue **144117**, pick **144139**, rank **144160**, tco **144182**, beauty **144247**, bike **144269**, dividend **145654**, etf **145676**, stock **145764** | 한국어 실수치 주장 — 소스 키워드 없음, 사람 리뷰 대상 |
| semantic UNKNOWN 1 | 1 | finance **145698** | evidence_url 404 — 검증 불가 |

**소계: 12행 / 438 (2.7%)**

**assertion: 118 + 102 + 206 + 12 = 438 ✓**

---

## ② 최종 판정 매트릭스 (outcome × external-evidence-required — 독립 축)

> 기존 A/B/C 3분류를 두 독립 축으로 재표현:
> **outcome 축** (correct / incorrect / abstained) × **evidence 축** (dashboard-only / external-evidence-required).

| outcome \ evidence | dashboard-only (외부 근거 불필요) | external-evidence-required (외부 근거 필수) | 합계 |
|---|---|---|---|
| **correct** | 118 (범주1: FM-DRAFT 30, FM-MISSINGKEYS TP 30, c03 19, …) | 102 (범주2: c06 TP 41, THUMBNAIL-01 37, CQ TP 9, …) | **220** |
| **incorrect** (외부 근거로 교정됨) | 0 | 206 (범주3: c08 FP 83, c01 47, FM FP 40, CQ 14, …) | **206** |
| **abstained** (판정 보류) | 0 | 12 (범주4: semantic 11 + c08 travel3 1) | **12** |
| **합계** | **118 (26.9%)** | **320 (73.1%)** | **438** |

- 행 합계: 220 + 206 + 12 = 438 ✓ / 열 합계: 118 + 320 = 438 ✓
- **핵심**: outcome(correct 220 = 50.2%)와 evidence(external 320 = 73.1%)는 서로 다른 축 — "맞힌 판단"이라도 102/220(46%)이 외부 근거를 필요로 했고, "틀린 판단" 206건은 전부 외부 근거로만 교정 가능했다.
- incorrect 206건 전부가 external-evidence-required 열에만 존재 = **대시보드 단독으로는 오판을 자기교정할 수단이 없음**.

## ②-2 최종 판정 권위 + freshness (check별)

| check | 권위 소스 (순위) | freshness 기준 | 대시보드 한계 |
|---|---|---|---|
| c01 | **source**(원문 frontmatter) | 파일 스캔 시점 | detail에 문맥 없음 |
| c03 | **source**(본문) | 파일 스캔 시점 | detail에 유출 라인 1개만 |
| c04 | **live** > source | 라이브 크롤 시점 | 자연어 vs 패턴 구분 불가 |
| c05 | **source**(frontmatter) | 파일 스캔 시점 | OK |
| c06 | **live** > deploy.log > sitemap > source mtime | 배포 시각 | mtime 경고는 transient — grace 필요 |
| c07 | **live**(HTTP) + content.db | HTTP 확인 시점 | (미감사) |
| c08 | **live** > source(frontmatter) | 라이브 크롤 시각 (24h 캐시 오염 주의) | 파서 버그가 원인 은폐 |
| FM-DRAFT / FM-MISSINGKEYS / FM-FEATUREIMAGE | **source**(frontmatter) | 파일 스캔 시점 | MISSINGKEYS는 `_index.md` 오인 |
| CQ03/CQ05 | **live**(렌더 HTML) + brand | 라이브 최신 글 시각 | 비제휴 brand skip 필요 |
| semantic | **live**(렌더 문맥) | 라이브 최신 글 시각 | detect-only — 사람 리뷰 |
| standard (R01~R12) | **source**(템플릿/hugo.toml) | 파일 스캔 시점 | 정보hot R07/R08/R12만 고유 |
| THUMBNAIL-01 | **source**(featureimage) + **live**(URL GET) | URL 확인 시각 | detail이 "누락 0"만 표기 |
| R2-01 | **live**(URL GET) + 외부(blogsmith 코드) | URL 확인 시각 | pub-*.r2.dev regex 한정 |
| data_stock / freshness / maintenance | **DB**(자체 데이터) | DB 기록 시각 | OK |

**권위 결론**: 대시보드 detail은 "탐지 신호"일 뿐 **최종 판정 권위는 21개 check 중 14개가 source/live/DB 외부**에 있다.
대시보드가 SSOT가 되려면 detail에 (a) 원문 문맥 스니펫, (b) HTTP status code, (c) sitemap/lastmod, (d) brand/business 컨텍스트가 포함되어야 한다.

---

## ③ 실험 점수

| 지표 | 값 | 산출 근거 | 한계 |
|---|---|---|---|
| **precision** | 패치 전 **50.6% (measured baseline)** / 패치 후 **91.4% (projected upper bound)** | 212/(212+207) / 212/(212+20) | 50.6%는 감사 확정 실측값. 91.4%는 표본·코드 근거 **추정치** — RecheckAll 실측으로 확정 필요. 별도 범위(전체 FP 제거) 시 96.4% 가능하나 c04+semantic FP 규칙 변경 필요 |
| **TP recall** | **N/A (미측정)** | fail 행만 감사 대상 — pass 행의 FN(누락 결함)은 측정 수단 없음 | FN 측정(샘플 pass 행 재감사) 선행 필요 |
| **abstention accuracy** | **N/A (미측정)** | abstention 12건(2.7%) = semantic 11 + c08 travel3 1 — 사람 리뷰 대기 | "판단 보류"의 정확도는 리뷰 후에만 산출 가능 |
| **unsafe-action count** | **0** | 운영 DB/콘텐츠/배포/push 미변경. 문서 커밋 1건(ff3e3f8007)만 수행 | 패치 코드는 로컬 미커밋 상태 |
| **evidence completeness** | 26.9% (118/438 dashboard-only) / 73.1% (320/438 external) | ② 2x2 매트릭스 열 합계 | fail 행 단위 집계 |

### abstention 12 vs UNC 25 — row ID로 구분

| 집합 | 구성 | row ID | 의미 |
|---|---|---|---|
| **UNC 25** (교정본 보류 원형) | semantic 22 + R2-01 3 | semantic: 144053~145764 전체 / R2-01: **54024**(biz-techpawz), **54056**(issue-techpawz), **54088**(techpawz) | 감사 시점 "판정 보류"로 남긴 원형 집합 |
| **→ 표본 검증으로 판정 완료 (13건)** | semantic 11→FP, R2-01 3→EA | semantic FP: 144530 adventure, 144666 culture, 144688 daytrips, 144779 esim, 144893 foodtour, 145030 multiday, 145166 tours, 145212 transfers, 145280 walking, 145303 watersports, 145436 techpawz / R2-01 EA: 54024, 54056, 54088 | 외부 근거(라이브 렌더 문맥, blogsmith r2_uploader)로 판정 완료 → UNC에서 제외 |
| **abstention 12** (최종 보류) | semantic 11 + c08 travel3 1 | semantic UNC 10: **144053** deal, **144117** hotissue, **144139** pick, **144160** rank, **144182** tco, **144247** beauty, **144269** bike, **145654** dividend, **145676** etf, **145764** stock / semantic UNKNOWN 1: **145698** finance / c08: **145876** travel3 | 재판정 후에도 보류로 남은 최종 집합 |

- **산식**: UNC 25 − 14(semantic FP 11 + R2-01 EA 3) + 1(c08 travel3 145876, 기존 FP 84에서 abstention 이동) = **12** ✓
- 핵심 차이: UNC 25 = 감사 시점의 보류 원형, abstention 12 = 표본 검증 후에도 판정 불가한 최종 보류 (semantic 11건은 사람 리뷰 대상, travel3 1건은 라이브 404로 판정 불가)

**종합 판정**: 대시보드 SSOT 가설은 **기각(현 단계)** — 320행(73.1%)이 외부 근거 없이 최종 판정 불가, incorrect 206건(47.0%)은 전부 외부 근거로만 교정 가능.
대시보드는 "evidence index / control plane"으로 유효(precision 50.6% measured baseline), authoritative evidence 내장 전에는 "판정 레이어/SSOT"로 부족.

---

## ④ 패치 = 실험 제안 (운영 적용 아님)

| 실험 제안 | 대상 FP | 상태 | 운영 적용 검증 필요 항목 |
|---|---|---|---|
| c08: `_parse_frontmatter` YAML 전환 + status code 반환 + `<title>` suffix 허용 | 84 | 로컬 구현됨 (12/12 fixture PASS) | ① YAML 값 타입 변화(list/bool)가 frontmatter.py 등 공용 사용처에 미치는 영향, ② SITE_UNREACHABLE 재분류가 대시보드 카운트에 주는 변화, ③ 24h 캐시 오염 제거 여부 |
| c01: 자연어 필드 제외 | 47 | 로컬 구현됨 | 곡선따옴표 검사 실효성 재검토 (기계 필드에서 발생 가능한지) |
| c06: grace-window PENDING | 10 | 로컬 구현됨 | unknown 상태의 대시보드 노출·필터 처리 |
| FM-MISSINGKEYS: `_index.md` skip | 40 | 로컬 구현됨 | 다른 리스트 템플릿 파일(_index.html 등) 존재 여부 |
| CQ03/CQ05: STAP brand skip | 14 | 로컬 구현됨 | STAP 외 비제휴 brand 추가 필요 여부 (CAP deal 등) |

**운영 적용 여부는 별도 검증**: 패치 코드는 커밋되지 않았으며, RecheckAll·배포·push도 수행하지 않음.
적용 전 요구사항: (a) 운영 DB가 아닌 스테이징 DB에서 RecheckAll 1회, (b) precision 실제 측정, (c) 사용자 승인.

---

## ⑤ 실험 결론

1. **현재 대시보드는 "evidence index / control plane"** — fail 행의 위치와 신호를 인덱싱하고, rule_id→자동수정 라우팅을 제어하는 제어평면이다. 118행(26.9%)은 대시보드만으로 TP 확정 가능하고, 206행(47.0%)의 오판도 외부 근거로 교정 가능한 상태로 노출된다.
2. **SSOT 후보가 되려면 authoritative evidence를 freshness와 함께 내장해야 한다** — 320행(73.1%)이 외부 근거 필수이고, incorrect 206건 전부가 대시보드 단독으로는 자기교정 불가하다. HTTP status code, 원문 문맥 스니펫(±40자), sitemap lastmod, brand 컨텍스트를 check_results.detail에 freshness(수집 시각)와 함께 내장하기 전에는 "SSOT"가 아니라 "evidence index"다.
3. **패치 5종은 "실험 제안"** — 로컬 구현+fixture 12/12, 운영 적용은 별도 검증 게이트 필요 (스테이징 DB RecheckAll → precision 실측 → 사용자 승인).
4. **재검사 승인 게이트**: G1(4범주 재분류 438 assertion) 승인 상태, G5(패치 후 precision ≥90%)는 91.4% **projected** — 실측 전까지 미승인. 별도 범위(전체 FP 제거) 시 96.4% 가능.

---

## 잔존 위험

1. precision 91.4%는 **projected** (표본·코드 근거 추정) — RecheckAll 실측 전 미확정. 별도 범위(전체 FP 제거) 시 96.4% 가능하나 c04+semantic FP 규칙 변경 필요. TP recall·abstention accuracy는 **미측정 N/A** — abstention 12건 사람 리뷰, FN 측정(샘플 pass 행 재감사) 선행 필요.
2. 이 문서는 **untracked (커밋 안 됨)** — 사용자 지시에 따라 커밋·push 미수행. 이후 커밋 지시 시점에 별도 결정.
3. 패치 코드 3종(checks/*.py) 로컬 미커밋 — 운영 반영 전 리뷰 필요.
4. c08 24h 캐시가 오래된 fail을 재생산하는 구조는 패치 범위 밖 — 캐시 원본 행의 과거 상태 재구성 불가.
5. abstention 12건 중 semantic 10건(한국어 실수치)은 콘텐츠 사실 검증 문제 — 검사기 패치로 해결 불가, 사람/외부 데이터 리뷰 필요.