# STAGE 1 — 라이브 발행글 실측 감사 (a~d 위반율표)

> Phase 57 (rap-quality-fix) — Stage 1 산출물 (읽기 전용)
> 작성: 2026-08-03 | 상태: Gate G1→2 승인 대기
> 감사 기준: content.db publish_ledger 최신순 + site_path/content/posts/{slug}/index.md 실물 대조

---

## 0. 감사 대상 선정

- 선정 방식: 각 블로그 `content/posts/`에서 mtime 최신순 5건, `draft: true` 제외
  (실제 서빙 중인 발행글만 감사 — draft 아티팩트는 별도 기록)
- 감사 건수: **5블로그 × 5건 = 25건**
- 선정 명령:
  ```bash
  python3 - <<'PY'
  import pathlib, re
  blogs = {"rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo", ...}
  for b, base in blogs.items():
      posts = sorted(pathlib.Path(base+"/content/posts").iterdir(),
                     key=lambda p: p.stat().st_mtime, reverse=True)[:5]
  PY
  ```

샘플 slug (json: `/tmp/rap_stage1_samples.json`):
- rap-hugo: 목동롯데캐슬마에스트로, 광명시-주공13, 마포구-실거래가-종합, 광교호반베르디움, 관악드림동아
- rap2-hugo: 경남-거창군, 임대주택-청약-정정공고, 대전중촌2, 보령-국민임대, 충북-청약-8월
- rap3-hugo: 범어쌍용예가, 동천마을동문굿모닝힐6차, 관악구-실거래가, 관악구-현대아파트, 천연뜨란채
- rap4-hugo: 분당-무지개5단지, 광명-주공12, 마포구-한화오벨리스크, 용인-수지구-정자뜰, 하남-미사
- rap5-hugo: 등촌동아이파크, 롯데캐슬클라시아, 래미안수지이스트파크, 사당롯데캐슬2차, 힐스테이트녹번

---

## 1. 위반율표 (항목별 / 블로그별)

| 블로그 | a1 공고통짜 | a2 후기프레임 | a3 리터럴제목 | b1 1인칭경험 | b2 효능단정 | b3 CoT | b4 800자미만 | c 관련성불일치 | c 타주제오염 | d1 퍼널카드 | d3 퍼널내부링크 |
|--------|------|------|------|------|------|------|------|------|------|------|------|
| rap-hugo | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| rap2-hugo | 0/5* | 0/5 | 0/5 | 0/5 | 0/5 | **2/5** | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| rap3-hugo | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | **1/5** | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| rap4-hugo | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | **1/5** | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| rap5-hugo | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | **2/5** | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| **합계 (25)** | 0 | 0 | 0 | 0 | 0 | **6** | 0 | 0 | 0 | 0 | 0 |

*rap2 a1: 샘플 5건에는 공고통짜 없었으나, 8/3 중복 발행된
"음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.] 청약 정보"
(live, draft:false, 2회 발행)가 a1 공고통짜 실측 사례 — 아래 3절 참고.

---

## 2. 항목별 상세 실측

### 항목 a — 제목

- a1 (공고명 통짜): 샘플 25건 0건. 단, **8/3 중복 발행된 음성군 글은
  title="음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.] 청약 정보"
  로 raw 공고명 포맷 그대로** (draft: false, live) — a1 실측 사례 1건.
- a2 (후기 프레임): 0건 — 제목에서 "후기/체험담/다녀와서" 없음. **RAP은 후기
  프레임으로부터 자유로움** (cuap의 주 문제였던 항목과 대조).
- a3 (리터럴 "제목"): 샘플 0건. 단, **rap2 `제목` slug 아티팩트 실존** (8/2 11:13,
  title='제목', slug='제목', draft: **true**) — 발행 전 차단됨(승격 안 됨)이지만
  제목 생성 폴백이 리터럴 "제목"을 산출한 실물 증거 (Stage 2 체크리스트 (4) 근거).

### 항목 b — 본문

- b1 (1인칭 경험 주장): 0건. 초기 스캔에서 "직접 방문하거나" 등이 잡혔으나
  전부 **조언형 표현**(advisory instruction — "주민센터를 직접 방문하거나" = 신청
  방법 안내)으로 1인칭 경험 서술 아님 → 정밀 패턴(저는/제가 … 알아봤/다녀왔/체험)
  재스캔 결과 0건. **RAP은 1인칭 프레임 없음** (확정).
- b2 (효능 단정): 0건. "무조건 평균값만 보고 접근하는 것은 위험합니다"는
  경고성 조언, 효능/수익 단정 아님.
- b3 (CoT 노출): **6건** — 전 블로그에서 확인 (아래 사례).
- b4 (800자 미만): 0건 — 최소 1440자(rap5 힐스테이트녹번) ~ 최대 7727자(rap-hugo
  광명시-주공13). **길이 위반 없음**.

### 항목 c — 상품(키워드) 관련성

- 제목 키워드 vs 본문 불일치: 0건 — 제목의 주요 명사(아파트명/지역명)가 본문에
  전부 존재. **관련성 위반 없음**.
- 타주제 오염 (강아지/고양이/반려/펫): 0건 — RAP에 자기차단 회귀 없음.
  (키워드 풀 내 중국어/혼합어 오염은 Stage 2에서 전수 덤프로 확인 예정 — P5)

### 항목 d — cross-sell/내부링크

- d1 (퍼널 카드): **샘플 25건 전부 0건. 전체 2620개 글 중 3건뿐 (0.11%)** —
  모두 2026-07-18 발행 (v1 era). 최신 발행글에는 0건.
  - 3건 예외: rap-hugo "2026년 7월 용산구 실거래가 완벽 분석", rap5 "롯데캐슬
    브랜드 가치", rap5 "반포 래미안원베일리" — 전부 `href="pending://blog/ts"`
    미해결 URL 보유 → **실제로는 깨진 링크**
  - v2 (markdown-level, 7/19 커밋 5c705ab51) 이후 **단 1건도 카드 주입 안 됨**
- d3 (퍼널/브릿지 내부링크): 0건 — 라이브 글의 내부링크는 전부 **동일 블로그
  무작위 샘플 9개** (`_post_process` 방식, pipeline.py:736-763 실측과 일치).
  rap2→finance-hugo 브릿지, rap-hugo→rap3/4/2 depth_next 링크 **전무**.

---

## 3. 대표 위반 사례 (slug + 인용)

| 블로그/slug | 항목 | 인용 (실물) |
|-------------|------|-------------|
| rap2/음성군-지역-국민임대주택-예비입주자-모집-공고-20260323-청약-정보 | a1 | title: "음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.] 청약 정보" (8/3 2회 발행, draft:false) |
| rap2/경남-거창군-임대-청약-정보 | b3 | "...**1단계에서** 청약통장 순위와 예치금을 확인하고, **2단계에서** 원하는 주택형·면적을 골라 신청서를 낸..." (추론 사슬 서술) |
| rap2/임대주택-청약-정정공고-총정리 | b3 | CoT 단계 서술 (경남-거창군과 동일 패턴) |
| rap3/범어쌍용예가-취득세양도세-분석 | b3 | "취득세 계산 결과를 표로 **정리하면 다음과 같습니다.** ..." (사고 정리 리터럴) |
| rap4/분당-무지개5단지-전세-59000만원-8월-시세-분석 | b3 | CoT 단계 서술 |
| rap5/등촌동아이파크-실거래가-분석 | b3 | "핵심 요약을 세 줄로 **정리하면 다음과 같습니다.** ..." |
| rap5/래미안수지이스트파크-실거래가-분석-2026년-8월 | b3 | CoT 단계 서술 |
| rap2/제목 | a3 | title='제목', slug='제목' (8/2 11:13, draft:true — 차단됨, 발행 폴백 산출 증거) |
| rap-hugo/2026년-7월-용산구-실거래가-완벽-분석 | d1 | `funnel-links` 존재하나 `href="pending://rap3-hugo/1784349132.053442"` 미해결 (7/18) |

---

## 4. 정적 스캐너 미탐 항목 (shared/validators 등 탐지 범위와 실제 위반 차이)

| 항목 | 스캐너 탐지 여부 | 실측 | 비고 |
|------|------------------|------|------|
| b3 CoT 노출 (6건) | **미탐** (0건으로 통과) | 6건 위반 | validate_post가 CoT 패턴(1단계/정리하면 다음과)을 안 잡음 — 스캐너 사각지대 실증 |
| a1 공고명 통짜 (1건) | 미탐 | 1건 | 제목 포맷 검사 부재 |
| a3 리터럴 "제목" (1건, draft) | 미탐 (draft 차단으로 라이브 방지됨) | 아티팩트 1건 | 제목 폴백 검사 부재 — 단, draft:true로 승격 차단됨 (긍정) |
| d1 퍼널카드 0건 | 미탐 (기능 부재 자체) | 0건 | funnel resolution AttributeError로 전수 skip (Stage 2 확정) |

**요약:** 스캐너(validate_post)는 b1(1인칭)/b4(길이)/c(관련성)를 잘 커버하지만,
**b3(CoT)와 a1/a3(제목 포맷)은 탐지 사각지대**. cuap Phase 54의 CoT 라이브
오염 경험과 동일 패턴 — RAP에서도 b3 6건이 라이브 상태로 서빙 중.

---

## 5. Stage 1 결론

1. **RAP 발행글 품질은 대체로 양호**: 1인칭 0건, 효능단정 0건, 800자 미만 0건,
   관련성 불일치 0건, 타주제 오염 0건 — cuap 발행글 대비 위반율 현저히 낮음.
2. **b3 CoT 노출 6건 (24%)** — 가장 빈번한 라이브 위반. 프롬프트/파싱 계층에서
   CoT 리터럴 제거 필요 (Stage 2 원인 확정).
3. **a1 공고명 통짜 1건 + a3 `제목` 아티팩트 1건(draft)** — 제목 생성 폴백 결함.
4. **d1 퍼널카드 0건 (라이브 전수 3건뿐, 전부 pending:// 깨진 링크)** — P7의
   라이브 실측 확정. Stage 2에서 `_resolve_funnel_card_post` AttributeError
   (row.get)를 코드로 확정 (Stage 0/1 사전 스캔에서 원인 특정됨 — 5c705ab51).
5. **내부링크 = 동일 블로그 무작위 9개뿐** — depth_next/bridge_to 퍼널 링크 전무.

---

## 6. 재현 명령

```bash
# 샘플 선정 + 1인칭/퍼널 스캔 (Task 2 automated)
python3 - <<'PY'
import pathlib, re
blogs = {"rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo",
         "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
         "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo",
         "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
         "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo"}
tot = 0
for b, base in blogs.items():
    posts = sorted(pathlib.Path(base + "/content/posts").iterdir(),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    tot += len(posts)
    for p in posts:
        md = (p / "index.md")
        if md.exists():
            t = md.read_text(errors="replace")
            assert "draft:" in t
            if re.search(r"저는|제가 직접|다녀왔|체험", t):
                print(f"[HIT] {b}/{p.name}: 1인칭")
            if "funnel-card" not in t:
                print(f"[NO-FUNNEL] {b}/{p.name}")
assert tot >= 15, f"감사 대상 부족: {tot}건"
print(f"감사 대상: {tot}건")
PY

# funnel 전수
for b in rap-hugo rap2-hugo rap3-hugo rap4-hugo rap5-hugo; do
  echo "$b: $(grep -rl 'funnel-card\|data-funnel' /Users/twinssn/Projects/RAP/$b/content/posts/ | wc -l)"
done
```
