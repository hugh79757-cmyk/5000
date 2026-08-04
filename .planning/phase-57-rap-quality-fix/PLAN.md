---
phase: 57-rap-quality-fix
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [pipelines/rap/pipeline.py, pipelines/rap/writer.py, pipelines/rap/rap_data_sync.py, pipelines/rap/fetcher.py, shared/ai_writer.py, shared/alert_thresholds.py, shared/publishers/hugo_writer.py, shared/publishers/deploy.py, scheduler.py, config/models.yaml, config/blogs.d/rap.yaml, tests/rap/test_pipeline.py]
autonomous: false
requirements: [RAP-Q1, RAP-Q2, RAP-Q3, RAP-Q4, RAP-Q5, RAP-Q6, RAP-Q7, RAP-Q8]
user_setup: []

must_haves:
  truths:
    - "동일 키워드의 7일 내 재발행이 0건 (publish_log INSERT가 반드시 성공하고 UNIQUE로 이중 기록 차단)"
    - "라이브 발행글에서 1인칭/후기 프레임·CoT 노출·800자 미만·상품 관련성 위반이 0건"
    - "발행 전 검증 실패 시 전 건 draft 유지 (force_draft 설정이 실제로 동작)"
    - "실패 reason 빈도표에서 write_error/publish_error 계열이 0건, 알림은 임계값 이상일 때만 발송"
    - "퍼널 카드(depth_next/bridge_to)가 라이브 발행글에 실제 삽입됨"
    - "tests/rap/ 에 _pick_keyword 7일 제외·publish_log INSERT·tier 폴백 테스트가 존재"
    - "scheduler.log에 dispatcher 상세 로그가 보존되어 재진단 가능"
  artifacts:
    - path: ".planning/phase-57-rap-quality-fix/STAGE0-terrain.md"
      provides: "분기별 지형도 + 실패 reason 빈도표"
      contains: "reason 빈도표"
    - path: ".planning/phase-57-rap-quality-fix/STAGE1-audit.md"
      provides: "라이브 실측 위반율표 (블로그×3~5건, 항목 a~d)"
      contains: "위반율"
    - path: ".planning/phase-57-rap-quality-fix/STAGE2-rootcause.md"
      provides: "위반→근본원인 매핑표 (코드 라인 특정, Yes/No 확정)"
      contains: "원인 매핑"
    - path: ".planning/phase-57-rap-quality-fix/STAGE3-diffs/"
      provides: "원인별 수정 diff 초안 + 검증 방법 + 커밋 분리 계획"
      contains: "diff"
    - path: ".planning/phase-57-rap-quality-fix/STAGE4-measure.md"
      provides: "카나리 실측표 (a~d 전항목 + draft 유지 + reason 0건)"
      contains: "실측"
    - path: "pipelines/rap/pipeline.py"
      provides: "publish_log INSERT 보강 + _pick_keyword 중복 방지 유지"
      contains: "INSERT INTO publish_log"
    - path: "shared/ai_writer.py"
      provides: "tier config 누락 방어 (미정의 tier skip)"
      contains: "TIER_ORDER"
    - path: "tests/rap/test_pipeline.py"
      provides: "RAP 회귀 방지 테스트"
      contains: "def test_"
  key_links:
    - from: "pipelines/rap/pipeline.py:_pick_keyword (111-121)"
      to: "rap.db publish_log"
      via: "SELECT data_key FROM publish_log WHERE blog_id=? AND published_at > now-7d"
      pattern: "publish_log"
    - from: "pipelines/rap/pipeline.py:1027-1036"
      to: "rap.db publish_log"
      via: "INSERT OR IGNORE INTO publish_log — try/except 삼킴"
      pattern: "INSERT OR IGNORE INTO publish_log"
    - from: "shared/ai_writer.py:100"
      to: "config/models.yaml"
      via: "tier_config = config[attempt_tier]"
      pattern: "config\\[attempt_tier\\]"
    - from: "shared/publishers/hugo_writer.py:961"
      to: "블로그 게시물 index.md"
      via: "_build_funnel_cards_md(blog_cfg, body_md)"
      pattern: "_build_funnel_cards_md"
    - from: "shared/publisher.py:857"
      to: "config/blogs.d/rap.yaml"
      via: "blog_cfg = get_blog_config(blog_id) — depth_next/bridge_to 재조회"
      pattern: "get_blog_config"
    - from: "scheduler.py:268-274"
      to: "dispatcher 상세 로그"
      via: "stdout 마지막 3줄만 [OUT] 기록 → 상세 로그 유실"
      pattern: "\\[-3:\\]"
---

# PLAN: RAP 분기 품질 진단·개선 (cuap 개선 경험 이식판) — Phase 57

## Objective

RAP 분기 5개 블로그의 확정 문제(P1~P8)를 cuap(Phase 55/56)에서 검증된
"읽기전용 진단 → 근본원인 확정 → 좁은 수정 → 실측 → 카나리 확대" 방법론으로
해결한다. cap/seap은 본 페이즈에서 지형 파악만 수행한다.

**Purpose:** 쿼터(7일 35건)는 달성 중이나 동일 키워드 재발행(P1+P2), 브랜치 잠복
위험(P3), 키워드 풀 불균형(P5), 퍼널 미실현(P7), 테스트 부재(P8) 등 품질·안정성
결함을 근본 원인 단위로 제거한다. 발행 승격(draft 해제)은 이 페이즈 범위 밖 —
draft 육안검수 후 별도 승인.

**Output:** STAGE0~STAGE4 산출물 + 원인별 분리 커밋 + 카나리 실측표 + 잔존위험 기록.

## 사용자 확정 게이트 (단계 0→1→2→3→4→5 사이 전부 사용자 승인)

| 게이트 | 시점 | 승인 내용 |
|--------|------|-----------|
| G0→1 | Stage 0 산출 후 | 지형도 + reason 빈도표 승인 |
| G1→2 | Stage 1 산출 후 | 위반율표 + 대표 사례 승인 |
| G2→3 | Stage 2 산출 후 | 위반→원인 매핑표(라인 특정) 승인 |
| G3→4 | Stage 3 산출 후 | 수정 diff + 커밋 분리 계획 승인 |
| G4→5 | Stage 4 실측 후 | 카나리 판정 승인 (통과→확대 / 실패→revert) |

---

<context>
@.planning/phase-57-rap-quality-fix/CONTEXT.md
@.planning/phase-57-rap-quality-fix/RESEARCH.md
@.planning/STATE.md

# Stage 2~4에서 참조할 코드 (본 페이즈가 먼저 검증한 사실)

## 확정된 코드 사실 (2026-08-03 플래너 실측, 추측 아님)

- `_pick_keyword` 3단계(pipeline.py:111-121): publish_log 7일 조회로 중복 제외.
  **publish_log INSERT 실패 시 완전 무력화됨**
- publish_log INSERT(pipeline.py:1027-1036): `INSERT OR IGNORE`를 try/except로
  감싸 예외를 삼킴 → **조용한 실패**. rap.db publish_log에 UNIQUE 제약 없음
  (확인: `idx_publish_blog(blog_id, data_type)` 일반 인덱스만 존재) → INSERT OR
  IGNORE는 중복을 무시하지 못함
- daily_refresh daemon 스레드(pipeline.py:791-809): `join(120)` 후에도 살아있으면
  계속 실행 → sqlite write lock 보유 → `database is locked` 재발 이력 5회 이상
- ai_writer.py:64 main TIER_ORDER = ["default","fallback","economy"] (안전).
  브랜치 `fix/rap-subscription-backfill` 커밋 1dff13638이 fallback1~3 추가 —
  `config/models.yaml`에 키 없음 → ai_writer.py:100 `config[attempt_tier]`
  KeyError 'fallback1' (8/3 11:03 실발생 확인). main 미병합 = 잠복 위험
- **P7 RESEARCH 주장("코드 구현 0건")은 사실과 다름**: `shared/publishers/
  hugo_writer.py:826-889`에 `_build_funnel_cards_md()` 구현 존재, :961에서
  `_write_hugo_post()` 내부에서 호출됨. `publish()`가 :857에서
  `get_blog_config(blog_id)`로 depth_next/bridge_to를 재조회하므로 config 도달은
  확인됨. content.db에 대상 블로그 발행글 존재(rap2 88, rap3 89, rap4 80,
  rap-hugo 94, finance-hugo 26 — 전부 published_url 보유). **그러나 라이브 최신
  발행글 5개 블로그 전부 funnel 카드 0건 실측** → Stage 2에서 "카드 미삽입 원인"
  을 코드/로그로 Yes/No 확정해야 함 (예: `_resolve_funnel_card_post` 반환 None,
  `_keywords_overlap_check` 전량 drop, landing+bridge 억제(:838), 단계 미도달 등)
- RAP 파이프라인은 **force_draft 미지원** (pipeline.py:991-1005, is_draft는
  검증기 위반 시에만 true). curation은 `is_draft = cfg.get("force_draft", False)`
  (curation/pipeline.py:1080) 패턴 존재 → RAP에 동일 패턴 이식 필요
- rap2 content/posts/에 **`제목` 리터럴 slug 아티팩트** 실존 (8/2 11:13 발행,
  title='제목', slug='제목') — 제목 생성 폴백이 리터럴 "제목"을 발행한 실물 증거.
  Stage 1/2의 제목 폴백 체크리스트(4)의 실측 근거
- scheduler.py:268-274: dispatcher stdout **마지막 3줄만** [OUT] 기록 →
  상세 로그 유실 구조 (진단 로깅 개선 대상)
- RAP_EXCLUDE(pipeline.py:23-37)에 음식/잡 키워드 블록 존재하나
  공고명 통짜 키워드("음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.]")
  는 통과 — P5 불균형(rap2 218 / rap5 395 vs rap-hugo 2183, rap3 2068, rap4 2324)
  과 결합 시 재사용 가속
</context>

---

<tasks>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 0: 지형 파악 (읽기 전용)                                        -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 1: Stage 0 — 분기별 지형도 + 실패 reason 빈도표 (읽기 전용)</name>
  <files>.planning/phase-57-rap-quality-fix/STAGE0-terrain.md</files>
  <action>
    생성→게이트→발행 흐름 매핑 (읽기 전용, 코드/설정 변경 금지):

    1. RAP 블로그 5개(rap-hugo/rap2/rap3/rap4/rap5-hugo) + CAP + SEAP의
       활성/비활성 목록을 `config/blogs.yaml` + `config/blogs.d/*.yaml`의
       `status` 필드에서 추출해 테이블 작성 (blog_id | status | pipeline |
       platform | domain | funnel_stage).
    2. 파이프라인 진입점 확인: `dispatcher.py`의 `_resolve_pipeline` →
       `pipelines/rap/pipeline.py:run()` 경로 + scheduler.py → dispatcher
       subprocess(timeout 600s) 흐름을 다이어그램으로 문서화.
    3. run() 전체 흐름 매핑: `_pick_keyword`(74-139) → `_pick_strategy` →
       fetcher → writer → `_post_process`(736-763) → 발행 전 검증(985-1005) →
       `publish()`(1008) → publish_log INSERT(1027-1036). 각 단계의 게이트
       (validator, assert_korean_or_reject, language_error) 명시.
    4. cuap와 코드 공유 확정: 공용 모듈(shared/ai_writer, shared/publisher,
       shared/validators, shared/alert_thresholds, shared/publishers/hugo_writer)
       vs 분기별 복제(pipelines/rap/*) — 파일별로 "공용/분기전용" 판정 기록.
       RAP의 `_post_process`·`_pick_keyword`·publish_log 로직이 curation과
       다른 점을 3줄 이내로 대조.
    5. 실패 reason 빈도표: `logs/scheduler.log`의 8/1~8/3 구간에서
       `grep -oE '"reason": "[^"]+"'` + dispatcher JSON 줄(`[OUT]`) + 
       `content.db publish_ledger`(status != 'published')를 교차 집계.
       reason 카테고리: write_error / low_relevance / irrelevant_products /
       publish_error / similar_title / title_blocked / no_result / no_content /
       quota_met / already_running / language_error / timeout. 블로그별 + reason별
       빈도표로 작성. scheduler.log에 안 보이는 실패는 "로그 유실"로 표기하고
       그 원인(scheduler.py:268-274 마지막 3줄)도 함께 기록.
    6. 산출물 `.planning/phase-57-rap-quality-fix/STAGE0-terrain.md`에 지형도 +
       빈도표 + 흐름 다이어그램 작성. DB 쿼리와 grep 명령을 문서에 남겨 재현 가능하게.
  </verify>
  <automated>
    python3 - <<'PY'
import sqlite3, re, pathlib
p = pathlib.Path('/Users/twinssn/Projects/5000/logs/scheduler.log')
txt = p.read_text(errors='replace')[-2_000_000:]
reasons = re.findall(r'"reason":\s*"([^"]+)"', txt)
from collections import Counter
c = Counter(reasons)
assert len(c) >= 5, f"reason 빈도표 집계 불가: {dict(c)}"
print("reasons:", dict(c.most_common(12)))
conn = sqlite3.connect('/Users/twinssn/Projects/5000/data/rap.db')
n = conn.execute("SELECT COUNT(*) FROM publish_log").fetchone()[0]
assert n > 0
print("publish_log rows:", n)
PY
  </automated>
  <done>
    STAGE0-terrain.md 존재. 분기별 지형도 + 흐름 다이어그램 + reason 빈도표 포함.
    위 grep/sqlite 명령이 빈도표의 수치를 재현함. cap/seap 목록은 존재만 확인.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Gate G0→1: Stage 0 산출물 승인</name>
  <what-built>
    분기별 지형도(rap/cap/seap 활성/비활성, 진입점, 생성→게이트→발행 흐름) +
    8/1~8/3 실패 reason 빈도표 + cuap 코드 공유 판정.
  </what-built>
  <how-to-verify>
    1. `.planning/phase-57-rap-quality-fix/STAGE0-terrain.md` 열기
    2. reason 빈도표의 수치가 scheduler.log/DB에서 재현되는지 확인
    3. 지형도에서 누락된 블로그가 없는지 확인 (rap 5개 + cap/seap 목록)
  </how-to-verify>
  <resume-signal>승인 → Stage 1 진행. 수정 지시 있으면 반영 후 재승인.</resume-signal>
</task>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 1: 라이브 실측 감사 (읽기 전용, 각 블로그 3~5건)                -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 2: Stage 1 — 라이브 발행글 실측 감사 (읽기 전용, 블로그당 3~5건)</name>
  <files>.planning/phase-57-rap-quality-fix/STAGE1-audit.md</files>
  <action>
    실제 발행글 본문 검사 (추측 금지, 실물 근거). 블로그당 최근 발행 3~5건 —
    `content.db publish_ledger`(status='published') 최신순 + 해당
    `site_path/content/posts/{slug}/index.md` 실물 기준. sample 선정 명령을 문서에 기록.

    항목 a — 제목: (a1) 공고명 통짜 포맷(예: "음성군 지역 국민임대주택 예비입주자
    모집 공고 [2026.03.23.]" 그대로) (a2) 후기 프레임("후기", "체험담", "다녀와서")
    (a3) 리터럴 "제목"/옛 포맷 잔존. rap2 `제목` slug 아티팩트(8/2)를 실측 증거로
    포함하되 대표 사례 표에는 별도 기재.
    항목 b — 본문: (b1) 1인칭 경험 주장("저는/제가 직접/다녀왔습니다/체험") (b2)
    효능 단정("반드시 이득", "무조건", "확실히 좋습니다") (b3) CoT 노출("먼저…다음…",
    "1단계, 2단계" 추론 사슬, "결론적으로" 등 사고과정 리터럴) (b4) 본문 800자 미만.
    항목 c — 상품 관련성: 제목 키워드(예: 특정 아파트/지역 청약) vs 본문 실제 내용
    불일치 여부. rap 분기에 펫/타주제 키워드 혼입(자기차단 회귀)이 없는지도 확인.
    항목 d — cross-sell/내부링크: (d1) `funnel-card`/`data-funnel` 마크업 실제 존재
    (grep으로 전수) (d2) 후기프레임 slug·오염 도메인 유입 (d3) 내부링크가 동일
    블로그 무작위 3개인지(pipeline.py:736-763 실측).

    산출: 블로그×항목 위반율표(항목별 %) + 대표 위반 사례(slug + 위반 인용문 1줄) +
    "정적 스캐너(shared/validators 등)가 미탐한 항목" 별도 표기 (스캐너 탐지 범위와
    실제 위반의 차이 기록). 전체 감사 건수 = 5블로그 × 3~5건 명시.
  </verify>
  <automated>
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
            # 1인칭/후기 프레임 스캔
            if re.search(r"저는|제가 직접|다녀왔|체험", t):
                print(f"[HIT] {b}/{p.name}: 1인칭")
            if "funnel-card" not in t:
                print(f"[NO-FUNNEL] {b}/{p.name}")
assert tot >= 15, f"감사 대상 부족: {tot}건"
print(f"감사 대상: {tot}건")
PY
  </automated>
  <done>
    STAGE1-audit.md 존재. 블로그당 3~5건 감사(합계 15~25건) 위반율표 + 대표 사례 +
    스캐너 미탐 항목 표기. a~d 전 항목에 실측 수치가 채워져 있음.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Gate G1→2: Stage 1 실측 감사 승인</name>
  <what-built>
    라이브 발행글 위반율표(제목/본문/관련성/cross-link) + 대표 위반 사례 +
    정적 스캐너 미탐 항목.
  </what-built>
  <how-to-verify>
    1. `.planning/phase-57-rap-quality-fix/STAGE1-audit.md` 열기
    2. 위반율 수치가 실제 발행글과 일치하는지 2~3건 샘플 대조
    3. 대표 위반 사례의 slug로 실물 글 직접 확인
  </how-to-verify>
  <resume-signal>승인 → Stage 2 진행. 위반 사례가 부족하면 보완 지시.</resume-signal>
</task>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 2: 근본 원인 확정 (읽기 전용 — 추측 금지, 코드/로그 Yes/No)      -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 3: Stage 2 — 위반→근본원인 매핑 (코드 라인 특정, Yes/No 확정)</name>
  <files>.planning/phase-57-rap-quality-fix/STAGE2-rootcause.md</files>
  <action>
    Stage 1 위반별로 "생성 로직 vs 게이트 vs 설정 vs 키워드풀" 중 원인을 코드 인용으로
    확정. 추측 금지 — 모든 화살표에 파일:라인 + Yes/No. 출력:
    `.planning/phase-57-rap-quality-fix/STAGE2-rootcause.md`의 위반→원인 매핑표.

    P1+P2 (동일 키워드 재발행):
    - pipeline.py:1027-1036 try/except가 INSERT 예외를 삼키는지 인용 확정 (Yes/No)
    - publish_log에 UNIQUE 제약 부재 실증: `PRAGMA index_list(publish_log)` +
      INSERT OR IGNORE가 중복을 무시 못 하는 구조 확인
    - **재현 시도**: daily_refresh 스레드(pipeline.py:791-809, join 120s)와 동시에
      publish_log INSERT를 수행해 `database is locked` 재현. 재현 불가 시
      "재현 실패 — 원인 후보 유지"로 표기하고 로그/타임스탬프 근거로 대체
    - `_pick_keyword` 111-121의 7일 제외가 INSERT 누락 시 무력화되는 연쇄를
      DB 쿼리로 실증: 오늘 발행 키워드가 publish_log에 없는지
    - 부차 확인: publisher.py:866-892의 duplicate_source_id/duplicate_slug 가드가
      왜 2차 방어를 못 했는지 (source_id=f"{keyword}_{날짜}" 동일 → source_exists
      동작 여부)
    P3 (ai_writer tier):
    - `git show 1dff13638`로 브랜치 TIER_ORDER 변경 확인 + config/models.yaml
      키 대조 → `config[attempt_tier]` KeyError 경로 확정 (Yes/No)
    - main 현재 상태 안전 확인 (`git diff main..origin/main shared/ai_writer.py`)
    P4 (CATCHUP write_failed):
    - scheduler.log 8/3 CATCHUP 구간(10:23~) reason/write_failed 재시도 패턴 집계.
      write_failed 카운터가 alert_thresholds의 임계값과 어떻게 상호작용하는지
      (maybe_alert가 연속 횟수 검사하는지 — alert_thresholds.py:93-143 대조)
    P5 (키워드 풀):
    - rap2/rap5 active 키워드 **전수 덤프** → 중국어/혼합어/타블로그 복사/비주제어
      비율 산출 (cuap 체크리스트 (7)). 공고명 통짜 키워드 수 집계
    P6 (refresh 신선도):
    - `rap_data_sync.py` daily_refresh(397-449)·_parallel_sync(224-243) 소스와
      fetcher.py API 호출부를 읽고, trades_added=0 구간(07-20~27)의 에러 로그/
      빈 응답/예외 처리 흔적 확인 → 원인 Yes/No
    P7 (퍼널):
    - **RESEARCH 주장("구현 0건")과 상충** — 코드엔 구현 존재(hugo_writer.py:
      826-889, wiring :961). "라이브 카드 0건"의 원인을 아래 후보에서 코드/로그로
      하나씩 Yes/No 확정: (a) `_resolve_funnel_card_post`(719-740) 반환 None
      (content_store 조회 실패 여부) (b) `_keywords_overlap_check`(806-823)가
      bridge 전량 drop (c) `funnel_stage=="landing" and bridge_to` 억제(:838)
      (d) `_build_funnel_cards_md` 호출 단계 미도달 (e) Hugo 빌드/테마가 마크업
      제거. 실측 글 index.md에 카드 마크업 부재 확인과 대조.
    cuap 체크리스트 (1)~(7) 대조: 프롬프트 자기모순(1인칭/후기 유도 문자열 —
      writer.py 전수 grep, 문자열 인용), 관련성 검증 부재/우회, 게이트 "평균" 희석,
      제목 폴백 우회/옛 리터럴(rap2 `제목` 아티팩트 실증), 자기주제 하드차단 회귀,
      알림/카운터 결함(maybe_alert 임계 미검사), 키워드 풀 오염. 각 항목 Yes/No.

    최종: 위반→근본원인 매핑표(화살표마다 파일:라인 + Yes/No + 근거 1문장) +
    "증상(publish_error/임계값초과)과 근본원인 혼동 금지" 준수 여부 체크. try 블록
    안/밖 반환 여부로 카운터 도달 가능성 검증.
  </verify>
  <automated>
    bash -lc '
      cd /Users/twinssn/Projects/5000
      echo "--- P1+P2: publish_log UNIQUE 없음 확인 ---"
      sqlite3 data/rap.db "PRAGMA index_list(publish_log);"
      echo "--- P3: main TIER_ORDER ---"
      sed -n "64p" shared/ai_writer.py
      echo "--- P3: models.yaml tiers ---"
      grep -E "^[a-z0-9]+:" config/models.yaml
      echo "--- P7: funnel 코드 존재 ---"
      grep -n "_build_funnel_cards_md" shared/publishers/hugo_writer.py | head -3
      echo "--- P7: 라이브 카드 0건 ---"
      grep -rl "funnel-card" /Users/twinssn/Projects/RAP/rap2-hugo/content/posts/ | wc -l
      echo "--- P8: rap 테스트 0건 ---"
      ls tests/ | grep -i rap || echo "tests/에 rap 없음"
    '
  </automated>
  <done>
    STAGE2-rootcause.md 존재. P1~P8 전부 Yes/No + 파일:라인 인용. P7은 "구현 존재
    vs 라이브 0건"의 실제 원인이 라인 특정으로 확정됨. 미결 항목은 "재현 필요"로
    명시(추측 표기 금지).
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Gate G2→3: 근본 원인 확정 승인 + 수정 범위 결정</name>
  <decision>Stage 2 확정된 원인 중 어느 것을 Stage 3 수정 대상으로 할지</decision>
  <context>
    위반→원인 매핑표가 코드 라인으로 확정됨. cuap 경험상 프롬프트/게이트/키워드풀
    원인은 좁은 수정으로 해결 가능하고, P6(refresh 0건)는 소스 장애 확인이 먼저
    필요할 수 있음. P7은 RESEARCH와 다른 실측(구현 존재)이 나왔으므로 수정 범위를
    함께 확정해야 함.
  </context>
  <options>
    <option id="all-confirmed">
      <name>확정 원인 전부 수정 대상</name>
      <pros>일괄 해결, 카나리 실측 한 번으로 검증</pros>
      <cons>diff 규모 큼, 원인별 revert 책임 분리 필요</cons>
    </option>
    <option id="core-only">
      <name>P1+P2/P3/P5/P7/P8만 우선 (P4/P6 보류)</name>
      <pros>범위 좁음, 재발 최소화, 카나리 실측 신속</pros>
      <cons>P4/P6은 별도 페이즈로 이연</cons>
    </option>
  </options>
  <resume-signal>선택: all-confirmed 또는 core-only (또는 범위 수정 지시)</resume-signal>
</task>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 3: 수정 diff 초안 (배포 금지, 원인별 분리)                      -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 4: Stage 3 — 원인별 수정 diff 초안 (적용·배포 금지)</name>
  <files>.planning/phase-57-rap-quality-fix/STAGE3-diffs/</files>
  <action>
    Stage 2에서 확정된 원인만 좁게 수정하는 diff 초안을 원인별 파일로 작성.
    적용·배포 금지. 각 diff에 검증 방법 + 커밋 분리 계획 명시. cuap 해법 참고하되
    RAP 분기 코드에 맞게 재작성 (복붙 금지).

    D1 — P1+P2 (publish_log 신뢰성):
    - pipeline.py:1027-1036: try/except 삼킴 제거 → 예외 발생 시 logger.error +
    실패를 상위로 전파하거나 최소한 warning에 예외 객체 포함. 조용한 실패 금지
    (파이프라인 Core Value). INSERT OR IGNORE 유지.
    - publish_log에 UNIQUE(blog_id, data_key) 인덱스 추가 (마이그레이션 SQL —
    중복 행 선정리 후 생성. CREATE UNIQUE INDEX IF NOT EXISTS).
    - daily_refresh 스레드(791-809)와의 write lock 경합: 수정은 스레드 join을
    보장하거나 sqlite busy_timeout 증가(timeout=30 이미 존재) 중 선택 — Stage 2
    재현 결과에 따라 결정하고 diff에 근거 명시.
    - 검증: (1) 단위 테스트 — INSERT 2회 동일 키워드 → 두 번째 무시 (2) 실측 —
    발행 후 publish_log row 존재 확인.
    D2 — P3 (ai_writer tier 방어):
    - ai_writer.py: generate()에서 `config[attempt_tier]` KeyError 방어: TIER_ORDER
    순회 시 `attempt_tier not in config` → skip + warning (미정의 tier 통과).
    - 또는 config/models.yaml에 fallback1~3 정의 추가 (브랜치 의도 유지 시).
      둘 다 할 경우 diff 분리. 브랜치 병합 전 방어 필수.
    - 검증: 테스트 — models.yaml에 없는 tier를 generate()에 전달해도 KeyError 없이
      다음 tier로 폴백.
    D3 — P4 (알림 완충, 확정된 경우):
    - alert_thresholds.py maybe_alert: 연속 횟수 검사 추가(임계값 이상일 때만 발송,
    쿨다운과 이중검사 금지 — Phase 56에서 폐기된 패턴 재도입 금지).
    - CATCHUP 일시실패가 카운터에 오르지 않도록 생성계 일시실패 분리 여부 판단.
    - 검증: 연속 1회 실패 시 알림 미발송, 3회 이상 시 발송 (테스트).
    D4 — P5 (키워드 풀 정리, 비파괴):
    - rap2/rap5 비주제·중국어·혼합어 키워드를 `status='active'`→'inactive' UPDATE
      (DB 삭제 금지). 오염 유입경로(소스·백필)를 STAGE3-diffs/에 기록.
    - 공고명 통짜 키워드는 그대로 두되, 필요 시 P1+P2 UNIQUE 인덱스로 7일 재발행
      방지와 조합.
    - 검증: inactive 전환 수 집계 + 재선택 로직에서 제외 확인 (SQL 카운트).
    D5 — P6 (refresh 신선도, 확정된 경우):
    - fetcher/rap_data_sync 에러 처리: 0건 반환 시 빈 응답/예외를 로그로 남기고
      재시도 로직 추가 여부 판단. 원인(API 소스 장애 vs 코드 버그)에 따라 diff.
    - 검증: refresh_log에 trades_added>0 기록 or 에러 로그 확인.
    D6 — P7 (퍼널 카드 실삽입):
    - Stage 2 확정 원인에 따른 좁은 수정 (예: `_resolve_funnel_card_post`의 조회
    조건·컬럼명 보정, `_keywords_overlap_check` 과잉 drop 완화, or blog_cfg 전달
    보정). 구현 신규 추가 금지 — 기존 코드 결함만 수정.
    - 검증: 수정 후 실측 발행글에 funnel-card 마크업 존재 (grep).
    D7 — P8 (RAP 테스트 신설):
    - tests/rap/test_pipeline.py: (1) `_pick_keyword` 7일 제외 로직 (publish_log에
      최근 기록 있는 키워드 제외) (2) publish_log INSERT 중복 무시(UNIQUE) (3)
      ai_writer tier 폴백 (미정의 tier skip). 기존 패턴은 tests/curation/
      test_pipeline.py 참고. production code와 분리 ([TEST CODE]).
    D8 — force_draft 지원 (Stage 4~5 전제):
    - pipeline.py:991-1005: `is_draft = blog_cfg.get("force_draft", False) or
      _is_draft` (curation/pipeline.py:1080 패턴 이식). config/blogs.d/rap.yaml에
      카나리 블로그 force_draft: true 추가는 Stage 4에서.
    D9 — 진단 로깅 (권장):
    - scheduler.py:268-274: 마지막 3줄 → dispatcher 상세 로그를 파일로 보존
      (예: logs/dispatcher/{blog_id}/{date}.log) — 재진단 가능 구조.
    - 검증: 발행 후 로그 파일에 상세 라인 존재.

    각 D 파일: diff 본문 + 수정 이유(Stage 2 라인 인용) + 검증 방법 + 커밋 메시지
    초안 + revert 방법 1줄. 커밋 분리 원칙: **원인별 1커밋, 독립 revert 가능** —
    D1~D9 중 실제 적용 대상만 커밋에 포함 (D3/D5는 Gate G2→3 결정에 따라).
  </verify>
  <automated>
    bash -lc '
      cd /Users/twinssn/Projects/5000
      D=.planning/phase-57-rap-quality-fix/STAGE3-diffs
      test -d "$D" && ls "$D" | wc -l | awk "{print \"diff 파일 수: \" \$1}"
      test -f "$D/D1-publish-log.md" && echo "D1 존재"
      for f in "$D"/*.md; do
        grep -q "커밋 메시지" "$f" || echo "커밋 계획 누락: $f"
        grep -q "검증" "$f" || echo "검증 방법 누락: $f"
      done
      # diff가 문법적으로 유효한지(적용 전 py_compile은 금지 — 적용 안 하므로 생략)
    '
  </automated>
  <done>
    STAGE3-diffs/에 원인별(D1~D9) diff 초안 존재. 각각 검증 방법 + 커밋 메시지 +
    revert 방법 포함. 아무 코드에도 적용되지 않음(git status 변경 없음).
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Gate G3→4: 수정 diff + 커밋 분리 계획 승인</name>
  <decision>Stage 3 diff 초안을 적용(커밋)할지, 수정할지</decision>
  <context>
    원인별 diff 초안이 준비됨. 적용 전 사용자 승인 필수 (커밋은 원인별 분리, force
    push 금지). 수정 범위·방식에 대한 최종 확정을 여기서 한다.
  </context>
  <options>
    <option id="approve-all">
      <name>확정 diff 전부 승인 → Stage 4 커밋 분리 적용</name>
      <pros>원인별 독립 커밋으로 즉시 진행</pros>
      <cons>diff 일부 수정 필요 시 재승인</cons>
    </option>
    <option id="partial">
      <name>일부 diff만 승인 (블로그별 카나리 전제에 맞게 선택)</name>
      <pros>카나리 1~2개 블로그에 필요한 최소 수정만 적용</pros>
      <cons>나머지는 후속 페이즈로 이연</cons>
    </option>
  </options>
  <resume-signal>선택: approve-all 또는 partial (미승인 diff 목록 명시)</resume-signal>
</task>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 4: 배포 + 실측 (승인 후, force_draft 유지)                     -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 5: Stage 4 — 원인별 커밋 분리 push + 카나리 자동생성 실측 (force_draft)</name>
  <files>pipelines/rap/pipeline.py, shared/ai_writer.py, shared/alert_thresholds.py, shared/publishers/hugo_writer.py, scheduler.py, config/models.yaml, config/blogs.d/rap.yaml, tests/rap/test_pipeline.py</files>
  <action>
    Gate G3→4 승인 후에만 실행. 커밋 분리 원칙: 원인별 1커밋, 독립 revert 가능.

    1. 승인된 diff를 원인별로 적용 → **원인별 커밋 분리** (예:
       fix(rap-57): publish_log INSERT 신뢰성 — UNIQUE 인덱스 + 예외 전파,
       fix(rap-57): ai_writer tier config 누락 방어,
       fix(rap-57): rap2/rap5 키워드 풀 오염 제거(비파괴 inactive),
       fix(rap-57): 퍼널 카드 실삽입 보정, fix(rap-57): force_draft 지원,
       test(rap-57): RAP 파이프라인 단위 테스트 추가 등).
       production code와 test code는 별도 커밋. 각 커밋은 `git revert`로 단독
       복구 가능해야 함 (커밋 메시지에 revert 방법 주석 아님 — 커밋 단위만 독립).
    2. push (no force): `git push origin main` — force push 절대 금지.
       배포는 dispatcher.py 경유 — **wrangler 수동 배포 금지** (AGENTS.md 규칙).
    3. 스케줄러 재시작: launchd job 재기동 (또는 수동 `python3 scheduler.py` 재시작
       방법은 사용자 확인). 재시작 전후 scheduler.log 시작 마커로 재기동 확인.
    4. 카나리: 사용자 승인한 대표 블로그 1~2개 (추천: rap2-hugo, rap5-hugo —
       P1+P2/P5 실증 블로그)를 config/blogs.d/rap.yaml에서 `force_draft: true`로
       설정. 미해결 블로그는 활성화 금지.
    5. 자동생성 실측: 카나리 블로그에서 자동 생성 2~3건 대기 후, 생성된
       index.md를 Stage 1 항목 a~d 전항목으로 재검사 + frontmatter draft: true
       확인 + publish_log INSERT 성공(publish_log에 금일 row 존재) + 실패 reason
       0건(scheduler.log).
    6. `.planning/phase-57-rap-quality-fix/STAGE4-measure.md`에 실측표 작성:
       블로그 | 생성건수 | draft | a~d 위반 | publish_log | 실패 reason.
    7. 판정 기준: 전항목 통과 → [통과]. 항목 1건이라도 실패 → 해당 원인 커밋
       revert + 원인 재확정(Stage 2 복귀). revert 후 실측 재실행.
  </verify>
  <automated>
    bash -lc '
      cd /Users/twinssn/Projects/5000
      echo "--- 커밋 상태 ---"
      git log --oneline -12 | head -12
      echo "--- force push 금지 확인 ---"
      git remote -v | head -2
      echo "--- 카나리 force_draft ---"
      grep -A2 "rap2-hugo" config/blogs.d/rap.yaml | grep -c force_draft
      echo "--- 실측 산출물 ---"
      test -f .planning/phase-57-rap-quality-fix/STAGE4-measure.md && echo "STAGE4 존재"
    '
  </automated>
  <done>
    원인별 커밋이 분리되어 push됨 (no force). 카나리 1~2개 force_draft 상태로
    자동 생성 2~3건 실측 완료 — a~d 전항목 위반 0건, draft 유지, publish_log
    INSERT 성공, 실패 reason 0건. STAGE4-measure.md에 실측표 기록.
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Gate G4→5: 카나리 판정 승인</name>
  <decision>Stage 4 실측 결과 통과 여부와 확대 범위</decision>
  <context>
    카나리 실측표(위반율·draft·publish_log·reason)가 준비됨. 전항목 통과 시
    Stage 5 순차 확대, 1건 실패 시 해당 커밋 revert + 원인 재확정.
  </context>
  <options>
    <option id="pass">
      <name>[통과] 전항목 통과 → Stage 5 순차 확대</name>
      <pros>공용 수정 실작동 검증 완료</pros>
      <cons>없음</cons>
    </option>
    <option id="fail-revert">
      <name>[실패] N건 실패 → 해당 커밋 revert + 원인 재확정</name>
      <pros>오염된 수정이 확대 전 제거됨</pros>
      <cons>Stage 2~4 일부 반복</cons>
    </option>
  </options>
  <resume-signal>선택: pass 또는 fail-revert (실패 항목 명시)</resume-signal>
</task>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STAGE 5: 카나리 확대                                                -->
<!-- ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 6: Stage 5 — 안전 블로그부터 순차 확대 (force_draft 유지)</name>
  <files>config/blogs.d/rap.yaml, .planning/phase-57-rap-quality-fix/STAGE5-canary.md</files>
  <action>
    Gate G4→5에서 [통과] 시에만. 한 번에 전 블로그 활성화 금지.

    1. 카나리 확정 후 안전 블로그부터 순차 확대: 추천 순서 rap3-hugo → rap4-hugo
       → rap-hugo (Stage 1 위반율 낮은 블로그 우선, 실측 기준으로 결정). 각 단계
       force_draft 유지 + 1~2건 자동생성 실측 (Stage 1 항목 a~d 재검사) 후 다음
       블로그로.
    2. 미해결 블로그(오염/CoT 잔존)는 확대 제외 — 조건(오염 키워드 정리 완료,
       위반율 0) 충족 후 편입.
    3. 발행 승격(draft 해제)은 이 페이즈 범위 밖: draft 육안검수 후 별도 승인.
       STAGE5-canary.md에 "승격 보류" 기록.
    4. 스케줄 겹침/레이스: 여러 블로그의 동시 발행 시 already_running 또는
       `/tmp/wrangler_deploy.lock` 경합 알림이 뜨면 스케줄 시각을 시차 분산
       (rap.yaml schedule times 조정 검토) — schedule은 이번 수정에서 건드리지
       않고 STAGE5-canary.md에 시차 분산 검토 결과만 기록.
    5. `.planning/phase-57-rap-quality-fix/STAGE5-canary.md`에 확대 판정 기록:
       블로그 | 확대일 | 실측 결과 | 위반율 | 잔존위험(키워드풀 유입경로 등).
  </verify>
  <automated>
    bash -lc '
      cd /Users/twinssn/Projects/5000
      test -f .planning/phase-57-rap-quality-fix/STAGE5-canary.md && echo "STAGE5 존재"
      echo "--- 활성 블로그 수 (일괄 활성화 금지 확인) ---"
      grep -c "status: active" config/blogs.d/rap.yaml
      echo "--- force_draft 유지 ---"
      grep -c "force_draft: true" config/blogs.d/rap.yaml
    '
  </automated>
  <done>
    STAGE5-canary.md 존재. 안전 블로그 순차 확대 완료, 미해결 블로그는 제외,
    발행 승격은 별도 승인으로 보류 기록. 잔존위험(키워드풀 유입경로 등) 명시.
  </done>
</task>

</tasks>

---

## 커밋 분리 계획 (원인별 1커밋, 독립 revert 가능)

| 커밋 | 원인 | 주요 파일 | revert 방법 |
|------|------|-----------|-------------|
| C1 | P1+P2 publish_log 신뢰성 (UNIQUE 인덱스 + INSERT 예외 전파 + lock 경합 완화) | pipelines/rap/pipeline.py, 마이그레이션 SQL | `git revert C1` |
| C2 | P3 ai_writer tier config 누락 방어 (models.yaml 키 추가 또는 skip 로직) | shared/ai_writer.py, config/models.yaml | `git revert C2` |
| C3 | P4 알림 완충 (확정 시) | shared/alert_thresholds.py, pipelines/rap/pipeline.py | `git revert C3` |
| C4 | P5 키워드 풀 오염 정리 (비파괴 inactive 전환) | 마이그레이션 SQL (rap.db) | `git revert C4` |
| C5 | P6 refresh 신선도 (확정 시) | pipelines/rap/fetcher.py, rap_data_sync.py | `git revert C5` |
| C6 | P7 퍼널 카드 실삽입 보정 | shared/publishers/hugo_writer.py | `git revert C6` |
| C7 | P8 RAP 단위 테스트 신설 ([TEST CODE]) | tests/rap/test_pipeline.py | `git revert C7` |
| C8 | force_draft 지원 ([PRODUCTION CODE]) | pipelines/rap/pipeline.py, config/blogs.d/rap.yaml | `git revert C8` |
| C9 | 진단 로깅 개선 (권장) | scheduler.py | `git revert C9` |

- **규칙**: C7(테스트)과 production 커밋 동시 수정 시 순환 검증 → C7은
  production 커밋 이전에 독립 커밋. 각 커밋 push는 no force.
- **브랜치 주의 (P3)**: `fix/rap-subscription-backfill` 병합은 C2 방어 커밋 후에만
  허용. 병합 전에는 작업트리에 해당 브랜치 코드가 남지 않게 유지.

## 리스크와 롤백

| 리스크 | 대응 |
|--------|------|
| publish_log UNIQUE 인덱스 생성 시 기존 중복 행 충돌 | 인덱스 생성 전 중복 행 정리(DELETE 중복) 후 `CREATE UNIQUE INDEX IF NOT EXISTS` — 마이그레이션에 사전 정리 단계 포함 |
| daily_refresh 스레드 lock 경합 재발 | busy_timeout/timeout 증가 + INSERT 실패를 조용히 삼키지 않고 error 전파. 재현 확정 전 C1에 포함 |
| 카나리 실측 1건 실패 | 해당 원인 커밋만 `git revert` + Stage 2 재진단 (전체 롤백 금지 — 원인별 revert) |
| 스케줄러 재시작 후 CATCHUP 폭주 | force_draft 상태라 발행은 안 되고 재시도로 복구. 실패 reason 0건 확인 후 다음 블로그 확대 |
| P3 브랜치 실수 병합 | C2 방어 커밋이 선행되므로 KeyError 없이 fallback tier로 폴백. 병합 전 체크리스트에 C2 포함 |
| wrangler 수동 배포 실수 | 절대 금지 — 배포는 반드시 dispatcher.py 경유 (AGENTS.md). 배포 명령은 Stage 4에서도 dispatcher 경유 확인 |
| 키워드 풀 재오염 | C4 커밋에 오염 유입경로 기록 + Stage 5 잔존위험 항목으로 추적 |

## 요구사항 매핑 (goal-backward)

| 요구사항 | 문제 | 충족 Truth | 산출물/파일 |
|----------|------|------------|-------------|
| RAP-Q1 | P1+P2 동일 키워드 재발행 | 7일 재발행 0건 | C1, STAGE2/4 |
| RAP-Q2 | P3 tier 잠복 위험 | 미정의 tier 폴백 | C2 |
| RAP-Q3 | P4 CATCHUP write_failed | 알림 임계 이상만 발송 | C3 (확정 시) |
| RAP-Q4 | P5 키워드 풀 불균형·오염 | 풀 오염 제거 | C4 |
| RAP-Q5 | P6 refresh 신선도 | refresh 0건 구간 해소 | C5 (확정 시) |
| RAP-Q6 | P7 퍼널 미실현 | 라이브 카드 삽입 | C6 |
| RAP-Q7 | P8 테스트 부재 | 회귀 테스트 존재 | C7 |
| RAP-Q8 | force_draft 미지원 | 카나리 draft 유지 | C8 |

---

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 스케줄러→파이프라인 | scheduler.py가 dispatcher를 subprocess로 실행, stdout 3줄만 기록 |
| 파이프라인→rap.db | publish_log INSERT가 try/except로 삼켜짐 — 무결성 저하 지점 |
| 파이프라인→AI API | ai_writer tier 폴백 시 config 키 누락 → KeyError |
| 파이프라인→블로그 파일시스템 | Hugo 게시물 index.md 기록 (draft/발행 구분) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-57-01 | Tampering | publish_log INSERT (pipeline.py:1027-1036) | mitigate | C1: try/except 삼킴 제거 + UNIQUE(blog_id,data_key) 인덱스 — INSERT 실패가 반드시 로그/에러로 표면화, 중복 발행 구조 차단 |
| T-57-02 | Denial of Service | daily_refresh 스레드 write lock (pipeline.py:791-809) | mitigate | C1: lock 경합 완화(busy_timeout/join 보장) — `database is locked` 재발 방지 |
| T-57-03 | Tampering | ai_writer tier config (ai_writer.py:100) | mitigate | C2: `attempt_tier not in config` skip 방어 + 브랜치 병합 전 C2 선행 |
| T-57-04 | Information Disclosure | AI 생성 CoT 노출·1인칭 주장 (발행글 본문) | mitigate | Stage 1 실측 + prompt sanitize 검토(Stage 2 확정 원인에 따라 C-추가 diff) — draft 게이트 유지 |
| T-57-05 | Tampering | force_draft 설정 우회 (pipeline.py:991-1005) | mitigate | C8: `is_draft = blog_cfg.get("force_draft", False) or _is_draft` — 카나리 기간 draft 강제 |
| T-57-06 | Spoofing | 키워드 풀 오염 (중국어/타블로그 복사) | mitigate | C4: 비파괴 inactive 전환 + 유입경로 기록 — 오염 키워드 재선택 차단 |
| T-57-07 | Elevation of Privilege | wrangler 수동 배포로 인한 계정 오염 | accept | AGENTS.md 규칙 — dispatcher 경유 배포만 허용. 본 페이즈는 배포 대신 force_draft 발행이므로 노출 없음 |
| T-57-SC | Tampering | 새 패키지 설치 없음 (npm/pip/cargo 0건) | accept | 새 의존성 추가 없음 — 기존 환경(venv)만 사용, slopcheck 불필요 |
</threat_model>

---

<verification>
## 페이즈 전체 검증

- **Stage 0**: STAGE0-terrain.md — 지형도 + reason 빈도표 (grep/sqlite 재현 가능)
- **Stage 1**: STAGE1-audit.md — 블로그당 3~5건, a~d 위반율표 (실물 index.md 대조)
- **Stage 2**: STAGE2-rootcause.md — P1~P8 Yes/No + 파일:라인 인용 (추측 표기 금지)
- **Stage 3**: STAGE3-diffs/ — 원인별 diff + 검증 방법 + 커밋 메시지 (적용 금지)
- **Stage 4**: STAGE4-measure.md — 카나리 실측표 (a~d + draft + publish_log + reason)
- **Stage 5**: STAGE5-canary.md — 순차 확대 판정 + 잔존위험
- **게이트**: G0→1, G1→2, G2→3, G3→4, G4→5 전부 사용자 승인 필수 (자동 진행 금지)
- **규칙 준수**: force push 금지, wrangler 수동 배포 금지, force_draft 유지,
  미해결 블로그 활성화 금지, 발행 승격은 별도 승인
</verification>

<success_criteria>
- [ ] RAP 5개 블로그 7일 쿼터 유지 + 동일 키워드 재발행 0건 (publish_log UNIQUE + INSERT 신뢰성)
- [ ] 라이브 발행글 a~d 전항목 위반 0건 (draft 게이트 + prompt/키워드 정화)
- [ ] force_draft 설정이 실제 발행에서 draft로 동작 (카나리 실측에서 확인)
- [ ] 실패 reason 0건, 알림은 임계값 이상 시에만 발송
- [ ] 퍼널 카드(depth_next/bridge_to)가 라이브 글에 삽입됨
- [ ] tests/rap/test_pipeline.py 통과 (production code 회귀 방지)
- [ ] scheduler.log에 dispatcher 상세 로그 보존 (재진단 가능)
- [ ] 원인별 커밋 분리(no force) — 각 커밋 독립 revert 가능
- [ ] cap/seap 지형도 산출 (본 페이즈 적용은 후속 페이즈)
- [ ] 발행 승격(draft 해제) 미수행 — 육안검수 후 별도 승인 대기
</success_criteria>

<output>
Create `.planning/phase-57-rap-quality-fix/STAGE0-terrain.md` ~ `STAGE5-canary.md`
and phase summary `.planning/phase-57-rap-quality-fix/57-01-SUMMARY.md` when done.
</output>
