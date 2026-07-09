# Phase 16: Production Hardening — 마무리 작업

## Phase Goal

Phase 1-15에서 남은 requirements 미완료 항목(STB-02, STB-13)을 해결하고, 이미 구현만 해둔 기능들(toggle, pipeline hook, body scan)을 활성화/확장하며, uncommitted 변경사항을 정리한다. GitHub Actions CI는 Cloudflare Pages 500회/월 배포 제한으로 인해 활성화하지 않는다.

---

## Phase Scope

### In Scope

| Priority | 항목 | 관련 Phase/Req |
|----------|------|----------------|
| P0 | `keywords.py` circular import 방어 (validate_keyword import 안전성) | Phase 12 |
| P1 | STB-02: Hardcoded absolute paths 제거 | Phase 3 |
| P1 | STB-13: Config schema validation (blogs.yaml, prompts.yaml) | 미할당 |
| P2 | Phase 10 Blowfish shortcode toggle 활성화 | Phase 10 |
| P2 | Phase 15 pipeline hook travel/stock 확장 | Phase 15 |
| P2 | `detect_problematic_posts.py --scan-body` 실행 | Phase 12 |
| P3 | empty_template fix 검증 | 현재 세션 |
| P3 | Uncommitted changes 정리 (7개 파일) | 현재 세션 |

### Out of Scope

- STB-06: GitHub Actions CI 복원 (Cloudflare Pages 배포 제한)
- 새로운 기능 개발
- Phase 11 AdSense 광고 성과 분석
- Phase 14 GSC 미등록 사이트 등록

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Path config | `shared/db_paths.py` 기존 활용 + `env_loader.py` 확장 | 이미 path 중앙화 모듈이 존재함, 거기에 누락된 path만 추가 |
| Config validation | Pydantic model 또는 간단한 dict key 체크 | 복잡한 스키마 불필요, 존재 여부 + 타입만 확인 |
| Shortcode toggle | `hugo_writer.py` 상수 `ENABLE_BLOWFISH_SHORTCODES = True` | 이미 구현됨, False→True만 변경 |
| Pipeline hook | quality_recorder.record_quality() 호출만 추가 | curation pipeline의 패턴을 travel/stock에 동일하게 적용 |
| Body scan | 1회 실행, 결과만 catalog | Phase 8 방식 동일, 자동 삭제는 하지 않음 |

---

## Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| SC-01 | `keyword_expander.py` import `validate_keyword` 성공 (circular import 없음) | `python3 -c "from pipelines.curation.keywords import validate_keyword; print('OK')"` |
| SC-02 | Hardcoded `/Users/twinssn/...` paths zero in `shared/` and `pipelines/` | `grep -rn '/Users/twinssn' shared/ pipelines/ --include='*.py' \| grep -v '.pyc' \| wc -l` = 0 |
| SC-03 | `blogs.yaml` / `prompts.yaml` schema validation pass | `python3 -c "from shared.config_validator import validate_configs; print(validate_configs())"` |
| SC-04 | Hugo build with shortcodes succeeds | `hugo --gc --minify` for travel-hugo |
| SC-05 | travel pipeline publish → quality.db 레코드 생성 | `sqlite3 data/quality.db 'SELECT COUNT(*) FROM article_quality WHERE blog_id LIKE "travel%"'` 증가 확인 |
| SC-06 | body scan 결과 `flagged_posts.yaml`에 source:body 포함 | `grep 'source: body' scripts/phase8/flagged_posts.yaml` |
| SC-07 | empty_template validation이 `{{variable}}`을 false positive로 보고하지 않음 | pipeline validation log 확인 |
| SC-08 | Uncommitted 7개 파일 commit 또는 discard 완료 | `git status --short` = clean |

---

## Task Breakdown

---

### Task 16-01: keywords.py circular import 방어

**Files:**
- `pipelines/curation/keywords.py` (modify)
- `pipelines/curation/keyword_expander.py` (verify)

**Problem:** `keyword_expander.py:273`에서 `from pipelines.curation.keywords import validate_keyword`가 `keywords.py`의 상단 `from pipelines.curation.pipeline import CATEGORY_FILTERS` import와 circular import를 일으킬 수 있음.

**Fix:** `validate_keyword()` 내부에서 lazy import를 사용하고 있으므로(`from pipelines.curation.pipeline import CATEGORY_FILTERS`가 함수 내부에 있음), 실제로 circular import는 발생하지 않음. 확인만 하고 넘어감.

**Verification:**
```bash
python3 -c "from pipelines.curation.keywords import validate_keyword; print(validate_keyword('세럼 추천', 'beauty-hugo'))"
python3 -c "from pipelines.curation.keyword_expander import update_keywords; print('OK')"
```

**Done when:** Both import tests pass without ImportError.

---

### Task 16-02: STB-02 — Hardcoded absolute paths 제거

**Files:**
- `shared/db_paths.py` (extend — 누락된 경로 추가)
- `shared/env_loader.py` (extend)
- `shared/publishers/hugo_writer.py` (modify — hardcoded HUGO_BIN)
- `shared/hugo_builder.py` (modify — hardcoded HUGO_BIN)
- `scripts/master_backup.py` (modify — hardcoded paths)
- `shared/quality_recorder.py` (verify)
- `dispatcher.py` (verify)

**Current state:** `shared/db_paths.py`에 프로젝트 루트 경로가 이미 환경변수 기반으로 설정되어 있음. 하지만 Hugo 바이너리 경로(`/opt/homebrew/bin/hugo`)는 여러 파일에 하드코딩되어 있음.

**Implementation:**
1. `shared/db_paths.py`에 `HUGO_BIN` path 추가:
```python
HUGO_BIN = os.environ.get("HUGO_BIN", "/opt/homebrew/bin/hugo")
```
2. `shared/hugo_builder.py`에서 `HUGO_BIN = "/opt/homebrew/bin/hugo"` → `from shared.db_paths import HUGO_BIN`으로 대체
3. `shared/publishers/hugo_writer.py`에서 하드코딩된 HUGO_BIN 경로 동일하게 대체
4. 그 외 `/Users/twinssn/Projects/...` 패턴 검색:
```bash
grep -rn '/Users/twinssn' shared/ pipelines/ scripts/ --include='*.py' | grep -v '.pyc' | grep -v '__pycache__'
```
5. 발견된 각 경로를 `db_paths.py`를 통한 참조 또는 env var로 변경

**Note:** CUAP/TAP/STAP/ETAP/RAP 등 외부 프로젝트 경로는 `db_paths.py`에 이미 `CUAP_ROOT`, `TAP_ROOT` 등으로 정의되어 있음. 이들을 사용하지 않고 하드코딩된 곳만 수정.

**Verification:**
```bash
grep -rn '/Users/twinssn' shared/ pipelines/ --include='*.py' | grep -v '.pyc' | grep -v '__pycache__'
# → 0 results expected
python3 -c "from shared.db_paths import HUGO_BIN; print(HUGO_BIN)"
```

**Done when:** Zero hardcoded `/Users/twinssn` paths in `shared/`, `pipelines/`, `scripts/`.

---

### Task 16-03: STB-13 — Config schema validation

**Files:**
- `shared/config_validator.py` (new)

**Implementation:**
```python
"""Config validation for blogs.yaml and prompts.yaml."""

import yaml
from pathlib import Path

REQUIRED_BLOG_FIELDS = ["id", "pipeline", "schedule", "platform"]
REQUIRED_SCHEDULE_FIELDS = ["daily_quota", "site_path"]
VALID_PLATFORMS = ["hugo", "blogger", "wordpress"]

def validate_blogs_config(path: str = "blogs.yaml") -> list[str]:
    """Validate blogs.yaml structure. Returns list of error messages."""
    errors = []
    with open(path) as f:
        config = yaml.safe_load(f)
    for i, blog in enumerate(config.get("blogs", [])):
        for field in REQUIRED_BLOG_FIELDS:
            if field not in blog:
                errors.append(f"blogs[{i}]: missing '{field}'")
        if blog.get("platform") not in VALID_PLATFORMS:
            errors.append(f"blogs[{i}]: invalid platform '{blog.get('platform')}'")
        schedule = blog.get("schedule", {})
        for field in REQUIRED_SCHEDULE_FIELDS:
            if field not in schedule:
                errors.append(f"blogs[{i}].schedule: missing '{field}'")
    return errors

def validate_prompts_config(path: str = "prompts.yaml") -> list[str]:
    """Validate prompts.yaml structure."""
    errors = []
    with open(path) as f:
        config = yaml.safe_load(f)
    if "prompts" not in config:
        errors.append("prompts.yaml: missing 'prompts' key")
    return errors

def validate_configs() -> dict:
    return {
        "blogs": validate_blogs_config(),
        "prompts": validate_prompts_config(),
    }
```

**Integration:** Add startup validation call in `dispatcher.py` main entry point (non-blocking warning only).

**Verification:**
```bash
python3 -c "from shared.config_validator import validate_configs; print(validate_configs())"
```

**Done when:** Config validation runs without error, reports actual config issues if any.

---

### Task 16-04: Phase 10 Blowfish shortcode toggle 활성화

**Files:**
- `shared/publishers/hugo_writer.py` (modify)

**Current state (line ~170):**
```python
ENABLE_BLOWFISH_SHORTCODES = False  # Toggle: Phase 10 shortcode conversion
```
이 toggle이 False면 `_apply_lead_shortcode()`, `_apply_figure_shortcode()`, `_apply_gallery_shortcode()` 등이 모두 스킵됨.

**Change:**
```python
ENABLE_BLOWFISH_SHORTCODES = True  # Phase 10 shortcode conversion 활성화
```

**Verification:**
1. travel-hugo Hugo build 성공
```bash
cd /Users/twinssn/Projects/5000 && python3 -c "
from shared.publishers.hugo_writer import ENABLE_BLOWFISH_SHORTCODES
print(f'Blowfish shortcodes: {\"ENABLED\" if ENABLE_BLOWFISH_SHORTCODES else \"DISABLED\"}')"
```

**Done when:** Toggle = True, Hugo build succeeds for travel-hugo.

---

### Task 16-05: Phase 15 pipeline hook 확장 (travel + stock)

**Files:**
- `pipelines/travel/pipeline.py` (modify — publish success hook)
- `shared/quality_recorder.py` (verify — already generic)
- STAP pipeline via `dispatcher.py` _run_stap() (modify)

**Pattern to follow (from curation pipeline ~line 888-909):**
```python
from shared.quality_recorder import record_quality
from shared.post_validator import validate_post_html

# After successful publish:
body_html = ...  # rendered HTML
v = validate_post_html(body_html, blog_id)
metrics = {
    "readability_score": ...,
    "keyword_coverage_ratio": ...,
    "content_length": len(body),
    "paragraph_count": body.count("\n\n") + 1,
    "has_cta": "cta" in body.lower(),
    "has_og_image": 'property="og:image"' in body_html,
    "has_map_text": "지도" in body,
    "min_length_pass": len(body) >= 500,
    "empty_template_count": 0,
}
record_quality(blog_id, slug, title, datetime.now().isoformat(), metrics)
```

**For travel pipeline:** Find the publish success point and add the hook.
**For STAP (stock):** STAP runs as subprocess via `dispatcher.py:_run_stap()`. The STAP output already includes a JSON `{"success": true, ...}`. Post-process this in dispatcher to also record quality metrics.

**Verification:**
```bash
# Publish one travel article, then check:
sqlite3 data/quality.db "SELECT blog_id, COUNT(*) FROM article_quality WHERE blog_id LIKE 'travel%' GROUP BY blog_id;"
```

**Done when:** travel and stock pipeline publish events create `article_quality` records.

---

### Task 16-06: detect_problematic_posts.py --scan-body 실행

**Files:**
- `scripts/phase8/flagged_posts.yaml` (auto-generated output)

**Command:**
```bash
cd /Users/twinssn/Projects/5000 && python scripts/phase8/detect_problematic_posts.py --scan-body
```

**Action:** Body rescan 실행. 결과는 `scripts/phase8/flagged_posts.yaml`에 `source: body` 필드로 추가됨.

**Post-processing:** 결과 catalog — body 스캔으로 발견된 flagged post 수를 기록. 자동 삭제는 하지 않음 (Phase 8 결정사항: body context는 title보다 모호함).

**Verification:**
```bash
grep -c 'source: body' scripts/phase8/flagged_posts.yaml
```

**Done when:** Body scan completes, results in flagged_posts.yaml.

---

### Task 16-07: empty_template fix 검증

**Files (to read/verify):**
- `shared/publishers/hugo_writer.py` line 141 — regex 확인
- `shared/post_validator.py` line 123 — regex 확인

**Current fix (already applied):**
- `hugo_writer.py`: `r"\{\}"` → `r"\{\{[\s]*\}\}"` (only removes `{{}}`, not `{{variable}}`)
- `post_validator.py`: `r'{{[\s]*}}'` (only counts truly empty templates)

**Verify pattern correctness:**
```bash
python3 -c "
import re
body = 'Text {{}} empty and {{variable}} valid and {{< short >}} short'
# hugo_writer clean
cleaned = re.sub(r'\{\{[\s]*\}\}', '', body)
print('After clean:', repr(cleaned))
# post_validator check
matches = re.findall(r'{{[\s]*}}', cleaned)
print('Empty templates found:', len(matches), '(should be 0)')
assert '{{}}' not in cleaned, 'FAIL: empty template not removed'
assert '{{variable}}' in cleaned, 'FAIL: variable template removed'
assert '{{< short >}}' in cleaned, 'FAIL: shortcode removed'
print('PASS: all assertions OK')
"
```

**Wait for next pipeline run** to confirm no `empty_template` validation warnings.

**Done when:** Pattern test passes AND next pipeline run shows no `empty_template` false positives.

---

### Task 16-08: Uncommitted changes 정리

**Current status (7 modified files):**
```
M data/dashboard/scripts/sync_sap_to_dashboard.py
M dispatcher.py
M pipelines/curation/keywords.py
M pipelines/curation/pipeline.py
M scripts/master_backup.py
M shared/post_validator.py
M shared/publishers/hugo_writer.py
```

**Action:** 각 파일의 변경사항을 검토하고, Phase 16 작업과 관련된 것들은 함께 커밋. unrelated 변경은 별도 커밋 또는 stash.

**Suggested commit strategy:**
1. `git add -p`로 변경 검토
2. Phase 16 작업 완료 후 일괄 커밋: `feat: Phase 16 complete - Production Hardening`

**Verification:**
```bash
git status --short  # → clean (or only expected untracked files)
```

**Done when:** All meaningful changes committed, working tree clean.

---

## Dependency Graph

```
16-01 keywords import ──────┐ (independent, 5min)
                            │
16-02 STB-02 hardcoded paths ┤ (independent, 30min)
                            │
16-03 STB-13 config validation ┤ (independent, 20min)
                            │
16-04 shortcode toggle ─────┤ (independent, 2min — just flip a bool)
                            │
16-05 pipeline hook extend ─┼── depends on understanding curation pattern (20min)
                            │
16-06 --scan-body ──────────┤ (independent, 5min to run)
                            │
16-07 empty_template verify ┤ (independent, 2min)
                            │
16-08 uncommitted 정리 ──────┘ (last — after all other tasks done)
```

All tasks are independent except 16-08 (should be last).

---

## Verification Strategy

| Task | Verification Method |
|------|-------------------|
| 16-01 | `python3 -c "from pipelines.curation.keywords import validate_keyword; print('OK')"` |
| 16-02 | `grep -rn '/Users/twinssn' shared/ pipelines/ --include='*.py' \| grep -v '.pyc' \| wc -l` = 0 |
| 16-03 | `python3 -c "from shared.config_validator import validate_configs; print(validate_configs())"` |
| 16-04 | `python3 -c "from shared.publishers.hugo_writer import ENABLE_BLOWFISH_SHORTCODES; print(ENABLE_BLOWFISH_SHORTCODES)"` = True |
| 16-05 | `sqlite3 data/quality.db 'SELECT blog_id, COUNT(*) FROM article_quality GROUP BY blog_id'`에 travel/stock 포함 |
| 16-06 | `grep -c 'source: body' scripts/phase8/flagged_posts.yaml` > 0 |
| 16-07 | Regex test pass + pipeline log에 `empty_template` 없음 |
| 16-08 | `git status --short` clean |

---

## Rollback Strategy

| Change | Rollback |
|--------|----------|
| 16-01 keywords.py | `git checkout HEAD -- pipelines/curation/keywords.py` |
| 16-02 db_paths.py | `git checkout HEAD -- shared/db_paths.py shared/env_loader.py shared/hugo_builder.py shared/publishers/hugo_writer.py` |
| 16-03 config_validator.py | `rm shared/config_validator.py` |
| 16-04 shortcode toggle | `ENABLE_BLOWFISH_SHORTCODES = False` |
| 16-05 pipeline hook | `git checkout HEAD -- pipelines/travel/pipeline.py dispatcher.py` |
| 16-06 body scan | 결과 파일 삭제: `rm scripts/phase8/flagged_posts.yaml` |
| 16-07 regex | 이전 패턴으로 복원: `r"\{\}"` |
| 16-08 commit | `git reset HEAD~1` |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| circular import in keywords.py | Low | High | 이미 lazy import 사용 중, 확인만 하면 됨 |
| hardcoded path 변경 후 import 실패 | Low | Medium | 변경 후 `python3 -c "from shared.db_paths import ..."` 즉시 검증 |
| shortcode toggle 후 Hugo 빌드 실패 | Medium | Medium | travel-hugo로 먼저 테스트, 실패 시 즉시 toggle OFF |
| pipeline hook 추가 후 기존 publish 실패 | Low | High | try/except로 감싸서 quality_recorder 실패가 publish 실패로 이어지지 않게 |
| body scan 결과로 자동 삭제된 글 없음 확인 | Low | Low | scan-only, no auto-delete |
| empty_template 검증을 위한 pipeline run 필요 | Medium | Low | 수동 트리거: `python dispatcher.py fitness-hugo` |

---

## Execution Order

```yaml
order:
  - task_16_01: "keywords.py circular import 확인"   # 5min
  - task_16_02: "STB-02 hardcoded paths 제거"         # 30min
  - task_16_03: "STB-13 config validation"             # 20min
  - task_16_04: "Blowfish shortcode toggle ON"         # 2min
  - task_16_05: "Pipeline hook travel/stock 확장"       # 20min
  - task_16_06: "detect_problematic_posts --scan-body"  # 5min
  - task_16_07: "empty_template fix 검증"               # 2min
  - task_16_08: "Uncommitted changes 정리"              # 10min

estimated_total_time: "~1.5 hours"
```

All tasks parallel except 16-08 (last).
