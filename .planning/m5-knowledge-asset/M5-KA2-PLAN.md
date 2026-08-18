---
milestone: M5
sub_plan: M5-KA2
title: Traffic Validation Pilot (최소 트래픽 검증 파일럿)
status: PLANNED
depends_on: [M5-KA1]
enables: []
last_updated: 2026-08-18
---

# M5-KA2 — 최소 트래픽 검증 파일럿 (Traffic Validation Pilot)

> **2026-08-18 재계획**: 기존 "거대한 지식 adapter 구축" 계획을 폐기하고,
> 지식 자산이 실제 트래픽/수익에 효과가 있는지 **최소 규모로 검증**하는 실험으로
> 재설계. 판정 근거는 코드·DB 연동이 아니라 **발행 글의 실측 지표 비교**다.

## 목표

KA1이 검증·격리한 179개 자동화 후보(VERIFIED + non-POLICY_CLAIM + risk 미제외) 중
**최대 10개 규칙 + 최대 2개 템플릿**만 사용해 소규모 A/B 실험을 수행하고,
지식 자산 적용이 트래픽/수익에 유의한 개선을 내는지 **28일 관찰로 판정**한다.
판정 결과만으로 다음 단계(SCALE_CANDIDATE 시 확장)의 근거를 남긴다.

## 선행 게이트

- **M5-KA1 판정 = READY_WITH_GAPS 통과 확인 완료** (verdict.json).
- 파일럿 선택 풀: `automation_eligible=true` 324건 중
  **POLICY_CLAIM 145건·UNVERIFIED·HUMAN_REVIEW·DERIVED·risk 제외 3건을 제외한
  179건** (공통규칙 114, 글구조 29, 기타 15, 프롬프트 13, 금지 8;
  EXPERIENCE 178, OFFICIAL_POLICY 1 — R-B02-27).
- 4개 통합 파일 물리 존재 확인 (파일 미존재 시 즉시 중단 + 사용자에게 경로 요청).

## 작업 (KA2) — 3개로 제한

### KA2-T1: 파일럿 블로그 선정 · baseline · Control/Treatment 배정 · 성공/중단 기준

- **블로그 선정**: CAP 계열(5000 내부 curation/gap) 중 발행 안정 + 지표 측정
  가능한 블로그 1개(후보: category/curation 계열). 후보가 없으면 pilot 보류.
- **Baseline**: 실험 시작 전 28일간 글 20건 이상 기준 지표 수집 — 노출,
  클릭, CTR, 평균 체류시간, 애드센스 RPM (측정 불가 지표는 해당 항목 제외하고
  가용 지표만 baseline으로).
- **Control/Treatment 배정**: 동일 주제·길이·시기 풀에서 번갈아 배정 —
  Control = 기존 파이프라인 글, Treatment = 규칙·템플릿 적용 글.
  블로그 내 주제 편향 방지를 위해 같은 키워드 그룹 내 짝 배정.
- **성공/중단 기준** (고정 판정 5종):
  | 판정 | 기준 |
  |------|------|
  | SCALE_CANDIDATE | Treatment CTR/체류/RPM이 Control 대비 유의 개선(예: CTR +10%p 이상) + 위반·오탐 0건 |
  | ITERATE | 개선 신호 있으나 통계적 유의성 부족 → 규칙·템플릿 조합 수정 후 재실험 |
  | NO_EFFECT_STOP | 유의한 차이 없음 → 파일럿 종료, 지식 자산 효과 없음으로 기록 |
  | HARM_STOP | Treatment 지표가 Control 대비 유의 악화 또는 콘텐츠 품질 이슈 → **즉시 중단** |
  | INSUFFICIENT_SIGNAL | 발행 20건 미달 또는 관찰 28일 미달 → 관찰 연장 또는 재실행 |
- **사전 중단 조건**: 이미지 PDF 6개 공백 커버리지 항목이 Treatment에 섞이면
  즉시 제외 (HUMAN_REVIEW 처리 후 재배정).

### KA2-T2: 최소 report-only adapter + 글별 메타데이터

- **규칙·템플릿 선택**: 179건 풀에서 **최대 10개 규칙 + 최대 2개 템플릿**만 선택.
  선택 우선순위: ① 검증 상태 VERIFIED ② 중복·충돌 미해소 항목 제외 ③ 적용이
  콘텐츠 품질을 해칠 위험 없는 항목. (지식 파일의 금지목록 8건 중 상위 1~2개,
  글구조 템플릿 2개, 공통규칙 중 CTR/체류와 직결된 항목 우선.)
- **adapter 형식**: RuleSpec 호환 구조(scope/code/severity)의 **메모리 내
  report-only 검사기**. DB INSERT·파이프라인 게이트·dispatcher 연결 **금지**.
  block=False 고정. 적용 대상 = Treatment 글 생성 시 정적 검사 + 생성 후 위반
  리포트만.
- **글별 메타데이터**: Treatment/Control 글마다
  `experiment_id / rule_id 목록 / template_id 목록 / 발행일 / 배정군(T|C)`를
  사이드카 파일(JSON)로 기록. 운영 DB 변경 금지 — 메타데이터는 실험 산출물
  디렉터리에만 저장.
- 324개 전체 runtime 연결·enforcement(강제 차단)·자동 차단·자동수선·전체
  블로그 확장은 **전부 금지** (아래 Scope OUT 참조).

### KA2-T3: 20~40건 발행 → 최소 28일 관찰 → 결과 판정

- **발행**: Control 10~20건 + Treatment 10~20건 (합계 20~40건). 기존 파이프라인
  발행 흐름·prompts.yaml·코드 변경 없이, 적용할 규칙·템플릿 지침을 글 생성
  입력에 반영하는 방식(Treatment만).
- **관찰**: 발행 완료 후 **최소 28일** — 지표(노출·CTR·체류·RPM) 수집.
- **판정**: 28일 경과 후 KA2-T1 기준표의 5종 판정 중 하나로 확정,
  `M5-KA2-VERDICT.md`에 기록. 판정 결과는 M5/Phase 64 이후 확장 여부의 근거로만
  사용 — 판정 자체로 코드·게이트·DB를 변경하지 않음.

## 산출물 목록

| 파일 | 내용 |
|------|------|
| `M5-KA2-EXPERIMENT-DESIGN.md` | 블로그 선정 근거 + baseline + C/T 배정표 + 성공/중단 기준 |
| `M5-KA2-ADAPTER.md` | 선택 규칙(≤10) + 템플릿(≤2) 목록 + RuleSpec 매핑표 + report-only 검사기 정의 |
| `M5-KA2-METADATA/` | 글별 experiment_id/rule_id/template_id/배정군 사이드카 JSON |
| `M5-KA2-RESULTS.md` | 28일 관찰 지표 비교(Control vs Treatment) + 통계 요약 |
| `M5-KA2-VERDICT.md` | 최종 판정: SCALE_CANDIDATE / ITERATE / NO_EFFECT_STOP / HARM_STOP / INSUFFICIENT_SIGNAL 중 1개 + 근거 |
| `M5-KA2-UNVERIFIED.md` | KA1에서 격리된 UNVERIFIED 13·HUMAN_REVIEW 16·DERIVED 7·risk 3·POLICY_CLAIM 149 목록 (연결 금지 명시) |

## 제외 (Scope OUT — 명시적 금지)

- **324개 전체 runtime 연결** — 파일럿은 최대 10규칙+2템플릿만 사용
- **enforcement(강제 차단)** — block=True·배포 중단·게이트 연결 전면 금지
- **자동 차단·자동수선·전체 블로그 확장**
- UNVERIFIED·HUMAN_REVIEW·DERIVED·risk 제외 항목·POLICY_CLAIM의 파일럿 선택
- 운영 DB(ops_dashboard.db 등)·파이프라인 코드·prompts.yaml·발행 흐름·Hugo
  배포 변경
- 4개 통합 파일의 하드코딩 검사기 연결, 완료된 Phase 62·63 디렉터리 변경,
  새 Phase 번호·마일스톤 생성

## 잔존 위험

- 이미지 PDF 6개 커버리지 공백 — 해당 주제는 파일럿 선택 풀에서 제외됨(이미
  반영). OCR/인간 확인 후 후속 등록 필요.
- 28일 관찰은 계절·알고리즘 변동에 취약 — Control 동시 배정으로 상쇄하되,
  외부 변동이 크면 INSUFFICIENT_SIGNAL로 판정.
- 통계적 유의성: 20~40건은 소표본 — 5종 판정은 엄밀한 검정보다 방향성+규모로
  판단하고, 한계를 M5-KA2-VERDICT.md에 명시.
- report-only 검사기는 4개 통합 파일 경로에 의존 — 파일 이동/삭제 시 즉시 경고.

---

# 부록 A — Interior Sitemap Discovery Experiment (실행 런북)

> 실험 실행 근거: AUDIT_INTERIOR_ZERO_VISIBILITY에서 interior.informationhot.kr의
> sitemap이 GSC에 정상 등록(오류 0)됨에도 Google이 어떤 URL도 모름
> ("URL is unknown to Google", 20/20 NEUTRAL)을 확인 → sitemap 재제출이
> discovery를 개선하는지 검증하는 대조 실험.

## A.1 실험 식별 정보

| 항목 | 값 |
|------|-----|
| Experiment ID | `APPROVE_INTERIOR_SITEMAP_RESUBMIT_EXPERIMENT` |
| 대상 사이트 | `https://interior.informationhot.kr/` (GSC property, siteOwner) |
| Sitemap URL | `https://interior.informationhot.kr/sitemap.xml` |
| 재제출 시각 (lastSubmitted) | `2026-08-18T06:31:53.937Z` |
| lastDownloaded | `2026-08-18T06:31:54.778Z` (재제출 직후 Google 다운로드 완료) |
| isPending / errors / warnings | false / 0 / 0 |
| 제출 전 라이브 상태 | HTTP 200, URL 수 **589**, SHA-256 `f7d358193ab4e1950510aa11382e96518d8b5b255f64245171f7b13a400cd39c`, 189,230 bytes |
| GSC contents (재제출 후) | web: submitted=589, indexed=0 |
| Baseline (재제출 직전) | 20/20 NEUTRAL — coverageState "URL is unknown to Google" |

## A.2 고정 표본 (변경·추가 금지)

**Treatment 18** (sitemap 포함 글):
1. https://interior.informationhot.kr/posts/%ED%97%88%EB%A6%AC-%ED%8E%B8%ED%95%9C-%EA%B2%8C%EC%9D%B4%EB%B0%8D%EC%9D%98%EC%9E%90-%EC%9E%A5%EC%8B%9C%EA%B0%84-%EA%B2%8C%EC%9E%84%EC%9A%A9-%EC%A0%9C%ED%92%88-%EB%B9%84%EA%B5%90-%EB%B6%84%EC%84%9D/
2. https://interior.informationhot.kr/posts/%ED%94%8C%EB%9F%AD%EC%8A%A4%EC%9E%A5%EC%88%98%EB%9E%A8%ED%94%84-%EB%8B%A4%EC%9A%B4%EB%9D%BC%EC%9D%B4%ED%8A%B8-2026%EB%85%84-%EC%B5%9C%EC%8B%A0-%EC%8A%A4%ED%8E%99%EA%B3%BC-%EA%B0%80%EA%B2%A9-%EB%B9%84%EA%B5%90/
3. https://interior.informationhot.kr/posts/%EA%B9%8C%EB%A5%B4%EC%97%A0%EA%B0%80%EA%B5%AC-%EC%B9%A8%EC%8B%A4-%EC%9D%B8%ED%85%8C%EB%A6%AC%EC%96%B4-%EC%99%84%EC%84%B1%ED%95%98%EB%8A%94-%EC%88%98%EB%82%A9-%EC%B9%A8%EB%8C%80-%EC%8B%A4%EC%82%AC%EC%9A%A9-%ED%9B%84%EA%B8%B0/
4. https://interior.informationhot.kr/posts/%ED%97%88%EB%A6%AC-%ED%86%B5%EC%A6%9D-%EC%A4%84%EC%97%AC%EC%A3%BC%EB%8A%94-%ED%95%99%EC%83%9D%EC%9A%A9-%EA%B3%B5%EB%B6%80%EC%9D%98%EC%9E%90-%EA%B3%A0%EB%A5%B4%EB%8A%94-%ED%95%B5%EC%8B%AC-%EA%B8%B0%EC%A4%80/
5. https://interior.informationhot.kr/posts/%EA%B1%B0%EC%8B%A4-%EB%B6%84%EC%9C%84%EA%B8%B0-%EB%B0%94%EA%BE%B8%EB%8A%94-t5-led-%EA%B0%84%EC%A0%91%EC%A1%B0%EB%AA%85-%EC%84%A4%EC%B9%98-%ED%8C%81/
6. https://interior.informationhot.kr/posts/%EA%B1%B0%EC%8B%A4%EB%93%B1-%EA%B5%90%EC%B2%B4-%EB%88%88-%ED%94%BC%EB%A1%9C-%EC%A0%81%EC%9D%80-led-%EC%8A%AC%EB%A6%BC%ED%98%95-%EC%A0%9C%ED%92%88-%EB%B9%84%EA%B5%90/
7. https://interior.informationhot.kr/posts/%EC%A7%91%EC%A4%91%EB%A0%A5-%EB%86%92%EC%9D%B4%EB%8A%94-%EA%B1%B0%EC%8B%A4-%EA%B3%B5%EB%B6%80%EB%B0%A9-%EC%9D%B8%ED%85%8C%EB%A6%AC%EC%96%B4-%EA%B0%80%EA%B5%AC-%EB%B0%B0%EC%B9%98%EB%B2%95/
8. https://interior.informationhot.kr/posts/%EC%A2%81%EC%9D%80-%EC%9B%90%EB%A3%B8-%EA%B3%B5%EA%B0%84-%ED%99%9C%EC%9A%A9%EB%8F%84-%EB%86%92%EC%9D%80-%EA%B0%80%EA%B5%AC-%EB%B0%B0%EC%B9%98%EC%99%80-%EC%8B%A4%EC%86%8D-%EC%A0%95%EB%B3%B4/
9. https://interior.informationhot.kr/posts/%EA%B0%80%EA%B5%AC%EB%8A%90%EB%82%8C-%EB%B2%A0%EC%8A%A4%ED%8A%B8-%EC%B1%85%EC%83%81-%EC%8B%A4%EC%86%8D-%EC%9E%88%EB%8A%94-%EC%9D%B8%ED%85%8C%EB%A6%AC%EC%96%B4-%EA%B0%80%EA%B5%AC-top-5/
10. https://interior.informationhot.kr/posts/%EB%8B%A8%EC%9D%BC%EC%83%89%EC%83%81-%EA%B1%B0%EC%8B%A4%EA%B0%80%EA%B5%AC-%EC%9D%B8%ED%85%8C%EB%A6%AC%EC%96%B4-%ED%86%A4%EC%98%A8%ED%86%A4-%EB%B0%B0%EC%B9%98-%EC%9A%94%EB%A0%B9/
11. https://interior.informationhot.kr/posts/%EC%A2%81%EC%9D%80-%ED%98%84%EA%B4%80-%EC%88%98%EB%82%A9%EC%9E%A5-%EA%B3%B5%EA%B0%84-%ED%99%9C%EC%9A%A9%EB%8F%84-%EB%86%92%EC%9D%B4%EB%8A%94-%EC%8B%A0%EB%B0%9C%EC%9E%A5-%EB%B9%84%EA%B5%90/
12. https://interior.informationhot.kr/posts/%EC%9C%A0%EB%8B%88%ED%99%88%EB%B0%94%EC%9D%B4%EC%95%B3%EC%98%AC-%EC%9D%B4%EB%8F%99%EC%8B%9D-%ED%96%89%EA%B1%B0-%EC%B6%94%EC%B2%9C-%EC%8B%A4%EC%86%8D-%EC%9E%88%EB%8A%94-%EA%B3%B5%EA%B0%84-%ED%99%9C%EC%9A%A9-%EA%B0%80%EC%9D%B4%EB%93%9C/
13. https://interior.informationhot.kr/posts/%EC%88%98%EB%82%A9%EC%9E%A5-%EC%B6%94%EC%B2%9C---%EC%86%8C%EC%9B%B0%ED%99%88%EC%98%A4%EC%95%84%EB%A3%A8-%EC%8B%A4%EC%86%8D-%EB%B9%84%EA%B5%90/
14. https://interior.informationhot.kr/posts/%EA%B0%80%EA%B5%AC%EB%B0%B8%EB%A6%AC-%EC%95%84%EB%A6%AC%EB%B8%8C%EB%A6%AC-top-5-4%EB%A7%8C%EC%9B%90%EB%8C%80%EB%B6%80%ED%84%B0-18%EB%A7%8C%EC%9B%90%EB%8C%80-%EC%86%8C%ED%8C%8C%EC%9D%98%EC%9E%90-%EC%B6%94%EC%B2%9C/
15. https://interior.informationhot.kr/posts/%ED%94%84%EB%A6%B0%ED%99%88-%EB%AA%A8%EC%85%98%ED%95%8F-vs-%ED%81%B4%EB%A0%99%ED%8A%BC-%EC%A0%84%EB%8F%99-%EB%A6%AC%ED%81%B4%EB%9D%BC%EC%9D%B4%EB%84%88-36%EB%A7%8C99%EB%A7%8C%EC%9B%90%EB%8C%80-%EC%8B%A4%EC%86%8D-%EB%B9%84%EA%B5%90/
16. https://interior.informationhot.kr/posts/%EA%B0%80%EC%A3%BD%EC%86%8C%ED%8C%8C-%EC%B6%94%EC%B2%9C-50%EB%A7%8C%EC%9B%90-%EC%9D%B4%ED%95%98-%ED%95%A9%EA%B2%A9%EC%A0%90-top-5/
17. https://interior.informationhot.kr/posts/top-5-%EA%B0%80%EA%B5%AC%EA%B3%A0%EB%9E%98-%EC%84%A0%ED%83%9D%ED%95%9C-%EC%9D%B4%EC%9C%A0%EC%99%80-%ED%8A%B9%EC%A7%95/
18. https://interior.informationhot.kr/posts/%EB%8B%A4%EC%9A%A9%EB%8F%84%ED%85%8C%EC%9D%B4%EB%B8%94-%EA%B3%A0%EB%A5%B4%EB%8A%94-%EB%B2%95-2026%EB%85%84-%EC%B5%9C%EC%8B%A0-%EA%B0%80%EC%9D%B4%EB%93%9C/

**Negative Control 2** (sitemap 미포함 오펀 글):
1. https://interior.informationhot.kr/posts/%EC%A3%BC%EB%B0%A9-%EC%88%98%EB%82%A9%EC%9E%A5-%EC%B6%94%EC%B2%9C-top5-2026%EB%85%84/
2. https://interior.informationhot.kr/posts/%EA%B0%80%EA%B5%AC%EB%B0%B8%EB%A6%AC-%EC%B6%94%EC%B2%9C-top5-2026%EB%85%84/

## A.3 체크포인트 일정

| 체크포인트 | 날짜 | 기준 시각 |
|------|------|------|
| Day 0 (baseline 재확인) | 2026-08-18 (재제출 당일) | treatment 18/18 unknown, control 2/2 unknown |
| **Day 3** | **2026-08-21** | next_action (ROADMAP/STATE 반영 완료) |
| Day 7 | 2026-08-25 | — |
| Day 14 | 2026-09-01 | — |

## A.4 체크포인트 실행 절차 (/tmp 불필요 — 부록만으로 재실행 가능)

1. **표본 로드**: A.2의 treatment 18 + control 2 URL을 그대로 사용 (변경·추가 금지).
2. **인증**: GSC token 원본(`~/Projects/blogdex/credentials/token_2_informationhot.json`)을
   임시 위치에 복사(chmod 600) → refresh_token grant
   (`POST https://oauth2.googleapis.com/token`, body: client_id/client_secret/
   refresh_token/grant_type=refresh_token)로 access token 발급. 사용 후 임시 복사본 삭제.
3. **조회**: `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect`
   (Authorization: Bearer, body: `{"inspectionUrl": "<URL>", "siteUrl": "https://interior.informationhot.kr/"}`)
   — 20개 URL 전수.
4. **기록 필드**: `coverageState`, `verdict`, `robotsTxtState`, `indexingState`,
   `pageFetchState`, `lastCrawlTime`, `googleCanonical`.
5. **집계·판정**: 아래 A.5 기준으로 treatment 탈출 건수와 control 탈출 건수를
   각각 집계 → `checkpoint_dayN.json`(sanitized) 저장.

## A.5 상태 전환 판정식

- **탈출(escaped) 정의**: `coverageState`가 "URL is unknown to Google"에서
  다른 상태(예: "Crawled, currently not indexed", "Submitted and indexed")로 전환.

판정 기준 (각 체크포인트 종료 시):
| 판정 | 조건 |
|------|------|
| **SITEMAP_DISCOVERY_SIGNAL** | treatment에서 ≥1 URL 탈출 **AND** control(2건)은 0건 탈출 → sitemap 재제출이 discovery 신호로 작동함 |
| **WEAK_SITEMAP_SIGNAL** | treatment 탈출 1건 이상 **AND** control도 탈출 → sitemap 외 원인 공존 (비특이적) |
| **NON_SPECIFIC_DISCOVERY** | treatment 0건 탈출 **AND** control ≥1건 탈출 → sitemap과 무관한 크롤링 |
| **NO_CHANGE** | treatment 0건 **AND** control 0건 탈출 → sitemap 신호 효과 없음 |

## A.6 결과별 후속 조치

- **SITEMAP_DISCOVERY_SIGNAL**: discovery 성공으로 기록 → M5-KA2 트래픽 파일럿
  개방 조건(discovery 성공 + 28일 baseline)의 discovery 측 충족. 이후 M5-KA2 재개 여부는 별도 승인.
- **WEAK_SITEMAP_SIGNAL**: 진입점 다양화(내부 링크 등) 후 재시도 — **ITERATE 최대 1회** 제한.
  재시도는 별도 승인 필요.
- **NON_SPECIFIC_DISCOVERY**: sitemap 효과로 보지 않음 — 크롤링 확대 원인 조사 후 별도 승인.
- **NO_CHANGE** (Day 14 종료 시): **NO_EFFECT_STOP** — 확장 종료, 도메인 수준 재조사
  (외부 링크 부재, 사이트 품질 신호 등). KA2 재개·Phase 64·M6·M7 진행 불가.
- Day 14까지 신호 없으면 확정 NO_EFFECT_STOP 기록 후 실험 종료.

## A.7 금지사항 (실험 기간 내내)

- URL Inspection 개별 **색인 요청** 금지 (조회는 허용, index:inspect는 조회 전용)
- Hugo 재빌드·재배포·sitemap 파일 수정·내부 링크 추가 금지
- DB·코드·scheduler·운영 환경 변경 금지
- 표본 URL 추가·제거·변경 금지
- token·credential·secret을 문서·로그에 기록 금지 (임시 복사본은 사용 후 삭제)

## A.8 참고 (authoritative source 아님)

- 실험 산출물(manifest/pre_submit_snapshot/resubmit_result/checkpoint_day0)은
  이전 세션에서 `/tmp/5000-m5-ka2/interior-sitemap-experiment/`에 보존 —
  이 부록 A.1~A.7이 **authoritative source**이며 /tmp는 참고 증거일 뿐.
- Day 0 관측: treatment 18/18 unknown, control 2/2 unknown (NO_CHANGE에 가까운
  초기 상태 — 실질 판정은 Day 3 이후).