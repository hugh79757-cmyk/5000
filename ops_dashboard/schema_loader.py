"""ops_dashboard.schema_loader — 파일 기반 스키마 로더 (트랙C S1).

설계 참조: docs/superpowers/specs/2026-08-22-schema-as-code-design.md
  - §3 SchemaSpec 정의
  - §3b c08 2단계 판정 (Stage 1 로컬 → Stage 2 라이브)
  - §4 로더 모듈

원칙:
  - **파일 기반만** — 트랙A DB/레지스트리 직접 의존 금지. 스키마는 `schemas/` YAML로만 선언.
  - **체커 무수정** — 기존 체커(frontmatter.py, content_integrity.py 등)는 하드코딩
    규칙을 유지. 이 로더가 중간 레이어로 들어가 SchemaSpec을 제공한다.
  - **트랙A 어댑터는 인터페이스만** — `adapt_rule_registry()` 시그니처 선언,
    구현은 트랙A G5 해소 후.

캐시 전략 (2026-08-22):
  - **인메모리 TTL 캐시**: `load_schema(blog_id)` 결과를 TTL 딕셔너리로 캐시.
    TTL 300초(5분). 캐시 키: blog_id.
  - **캐시 무효화**:
    1. `schemas/` 관련 YAML mtime 변경 감지 (캐시 히트 시 stat 비교)
    2. `invalidate_cache(blog_id=None)` 수동 flush (CI 머지 후 deploy hook)
  - **성능 예산**: 80 blog_id × frozen dataclass < 1MB. YAML 파싱 최대 6회/5분.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 300          # 5분 TTL
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SCHEMAS_ROOT = _PROJECT_ROOT / "schemas"
_BLOGS_D_DIR = _PROJECT_ROOT / "config" / "blogs.d"

# ---------------------------------------------------------------------------
# SchemaSpec — 체커들이 공통 참조하는 데이터 구조
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaSpec:
    """블로그 구조 선언 — 로더가 YAML에서 구성해 반환하는 공통 스키마.

    체커는 이 필드만 소비한다. 기존 하드코딩 상수(frontmatter.REQUIRED_KEYS 등)는
    유지되며, 스키마 도입 후 단계적으로 대체한다 (체커 수정 없음).
    """

    branch: str                              # 분기명 (etap, cap, cuap, ...)
    blog_id: str | None                      # blog 단위 로드 시 해당 blog_id
    required_frontmatter: list[str]          # frontmatter.py REQUIRED_KEYS 대체 후보
    allowed_og_patterns: list[str]           # og:image / og:title 허용 URL 정규식 패턴
    directory_layout: dict = field(default_factory=dict)      # {"content_root", "post_pattern"}
    disclosure_rules: dict = field(default_factory=dict)      # {"required", "position"}
    rel_rules: dict = field(default_factory=dict)             # {"affiliate_links"}
    template_constraints: dict = field(default_factory=dict)  # {"twitter_card_required", ...}
    featureimage_guard: dict = field(default_factory=dict)    # {"max_len": 200, ...}
    rule_refs: dict = field(default_factory=dict)             # 트랙A 연계용(비사용)
    # ── [2026-08-22 갭 보완] c08 2단계 판정 필드 ──────────────────────────
    title_format_rule: dict = field(default_factory=dict)    # {"max_len", "forbid_ellipsis", "allow_suffix"}
    live_og_format_rule: str = "exact_match"  # enum[exact_match|contains|prefix_match|case_insensitive_match]
    empty_value_policy: dict = field(default_factory=dict)   # {field: "allow"|"disallow"}, 기본 disallow
    og_rule: dict = field(default_factory=dict)              # {"og_image_required", "og_image_source"}


# ---------------------------------------------------------------------------
# TTL 캐시 저장소
# ---------------------------------------------------------------------------
# _cache: {blog_id: {"spec": SchemaSpec, "loaded_at": float, "mtimes": {path: float}}}
_cache: dict[str, dict] = {}
_cache_hits = 0
_cache_misses = 0

# blog_id → brand 역방향 매핑 (config/blogs.d 스캔 결과, 디렉토리 mtime으로 무효화)
_branch_index: dict[str, str] | None = None
_branch_index_mtime: float | None = None


# ---------------------------------------------------------------------------
# 순수 함수: 분기 매핑
# ---------------------------------------------------------------------------


def _resolve_branch(blog_id: str, blogs_d_dir: Path | None = None) -> str:
    """blog_id → 분기(branch) 매핑. config/blogs.d/{brand}.yaml 파일명 stem 기준.

    - 파일 기반만 (트랙A DB 조회 금지): blogs.d의 각 YAML을 스캔해 블로그 id 목록을
      추출하고, id → brand(파일명 stem) 역방향 인덱스를 만든다.
    - 매핑 실패 시 "default" 반환 (→ _base/default.yaml 폴백). 에러 아님, 경고 로그만.
    - 인덱스는 blogs.d 디렉토리 mtime으로 무효화한다 (재스캔).
    """
    global _branch_index, _branch_index_mtime

    d = blogs_d_dir or _BLOGS_D_DIR
    try:
        dir_mtime = d.stat().st_mtime
    except OSError:
        logger.warning("[schema_loader] blogs.d 디렉토리 없음: %s — 기본 분기 사용", d)
        return "default"

    if _branch_index is not None and _branch_index_mtime == dir_mtime:
        return _branch_index.get(blog_id, "default")

    index: dict[str, str] = {}
    for yaml_file in sorted(d.glob("*.yaml")):
        if yaml_file.name.endswith(".bak") or yaml_file.name.startswith("."):
            continue
        brand = yaml_file.stem
        # manual_blog_for_backup.yaml / manual_blogs.yaml → manual 통일
        # (파일명 stem은 manual 계열이 여러 파일로 쪼개져 있어 brand로 부적합)
        if brand.startswith("manual_"):
            brand = "manual"
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("[schema_loader] blogs.d 파싱 실패(스킵): %s: %s", yaml_file.name, e)
            continue
        if not data or not isinstance(data, dict):
            continue
        for entry in data.get("blogs", []) or []:
            if not isinstance(entry, dict):
                continue
            bid = entry.get("id")
            if bid:
                index[str(bid)] = brand

    _branch_index = index
    _branch_index_mtime = dir_mtime

    branch = index.get(blog_id, "default")
    if branch == "default":
        logger.warning("[schema_loader] 분기 매핑 실패(폴백 default): %s", blog_id)
    return branch


# ---------------------------------------------------------------------------
# 순수 함수: YAML 파싱 / deep-merge
# ---------------------------------------------------------------------------


def _parse_schema(path: Path) -> dict | None:
    """YAML 스키마 파일 파싱 → dict. 실패 시 None (에러 로그, 폴백 유도)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[schema_loader] YAML 파싱 실패(폴백 대상): %s: %s", path, e)
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        logger.warning("[schema_loader] YAML 루트가 dict 아님(폴백): %s", path)
        return None
    return data


def _deep_merge(base: dict, override: dict | None) -> dict:
    """deep-merge: override가 base를 덮어씀.

    - dict 값: 키 단위 재귀 머지.
    - list 값: **교체** (append 아님).
    - 그 외(스칼라): override 우선.
    """
    if not override:
        return dict(base)
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# 순수 함수: 스키마 조립
# ---------------------------------------------------------------------------


def _schema_files_for(blog_id: str, branch: str, schemas_dir: Path) -> list[Path]:
    """deep-merge 순서대로 스키마 파일 목록 반환 (존재하는 것만)."""
    files = [
        schemas_dir / "_base" / "default.yaml",
        schemas_dir / branch / "schema.yaml",
        schemas_dir / branch / "blog-overrides" / f"{blog_id}.yaml",
    ]
    return [f for f in files if f.exists()]


def _build_schema_dict(blog_id: str, branch: str, schemas_dir: Path) -> dict | None:
    """_base → 분기 → blog-override 순서로 deep-merge한 스키마 dict 반환.

    schemas/ 디렉토리 자체가 없으면 None (전체 _base 폴백 + 경고).
    """
    if not schemas_dir.is_dir():
        logger.warning("[schema_loader] schemas/ 디렉토리 없음: %s", schemas_dir)
        return None

    merged: dict = {}
    for path in _schema_files_for(blog_id, branch, schemas_dir):
        data = _parse_schema(path)
        if data is None:
            continue  # 개별 파일 파싱 실패는 스킵 — 하위 병합 결과 유지
        merged = _deep_merge(merged, data)

    if not merged:
        logger.warning("[schema_loader] 스키마 파일 없음: blog=%s branch=%s", blog_id, branch)
    return merged or None


def _dict_to_spec(blog_id: str, branch: str, data: dict) -> SchemaSpec:
    """스키마 dict → SchemaSpec frozen dataclass 변환.

    필수 필드(required_frontmatter) 누락 시 경고 로그 후 빈 리스트로 폴백
    (대시보드 운영 중단 방지).
    """
    if "required_frontmatter" not in data:
        logger.warning(
            "[schema_loader] 필수 필드 누락(required_frontmatter): blog=%s branch=%s — 빈 목록 폴백",
            blog_id, branch,
        )
    return SchemaSpec(
        branch=branch,
        blog_id=blog_id,
        required_frontmatter=list(data.get("required_frontmatter", []) or []),
        allowed_og_patterns=list(data.get("allowed_og_patterns", []) or []),
        directory_layout=dict(data.get("directory_layout", {}) or {}),
        disclosure_rules=dict(data.get("disclosure_rules", {}) or {}),
        rel_rules=dict(data.get("rel_rules", {}) or {}),
        template_constraints=dict(data.get("template_constraints", {}) or {}),
        featureimage_guard=dict(data.get("featureimage_guard", {}) or {}),
        rule_refs=dict(data.get("rule_refs", {}) or {}),
        title_format_rule=dict(data.get("title_format_rule", {}) or {}),
        live_og_format_rule=str(data.get("live_og_format_rule", "exact_match")),
        empty_value_policy=dict(data.get("empty_value_policy", {}) or {}),
        og_rule=dict(data.get("og_rule", {}) or {}),
    )


def _schema_mtimes(files: list[Path]) -> dict[str, float]:
    """스키마 파일들의 {경로: mtime} — 캐시 무효화 비교용."""
    out: dict[str, float] = {}
    for f in files:
        try:
            out[str(f)] = f.stat().st_mtime
        except OSError:
            pass
    return out


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def load_schema(blog_id: str, schemas_dir: str | Path | None = None) -> SchemaSpec:
    """blog_id에 해당하는 스키마를 로드. TTL 캐시 적용.

    조회 순서 (deep-merge):
      1. schemas/_base/default.yaml
      2. schemas/{branch}/schema.yaml
      3. schemas/{branch}/blog-overrides/{blog_id}.yaml (존재 시)

    캐시: blog_id 키, TTL 300초. 캐시 히트 시에도 관련 YAML mtime이 캐시 시점보다
    새로우면 무효화 후 재로드.

    매핑 실패(분기 미확인) → _base/default.yaml 폴백 (에러 아님, 경고 로그).
    """
    global _cache_hits, _cache_misses

    root = Path(schemas_dir) if schemas_dir else _DEFAULT_SCHEMAS_ROOT
    branch = _resolve_branch(blog_id)

    # 이 블로그가 사용할 스키마 파일 목록 (mtime 비교용)
    files = _schema_files_for(blog_id, branch, root)
    now = time.monotonic()

    cached = _cache.get(blog_id)
    if cached is not None:
        spec = cached["spec"]
        loaded_at = cached["loaded_at"]
        mtimes = cached.get("mtimes", {})
        # TTL + mtime 무효화 검사
        fresh = (now - loaded_at) < _CACHE_TTL_SECONDS
        if fresh and mtimes == _schema_mtimes(files):
            _cache_hits += 1
            return spec
        # 캐시 만료 또는 파일 변경 → 재로드
        _cache.pop(blog_id, None)

    _cache_misses += 1

    data = _build_schema_dict(blog_id, branch, root)
    if data is None:
        # schemas/ 자체 부재 — 빈 필드의 base 스펙 폴백 (경고는 _build_schema_dict에서)
        spec = _dict_to_spec(blog_id, "default", {})
    else:
        spec = _dict_to_spec(blog_id, branch, data)

    _cache[blog_id] = {
        "spec": spec,
        "loaded_at": now,
        "mtimes": _schema_mtimes(files),
    }
    return spec


def invalidate_cache(blog_id: str | None = None) -> None:
    """특정 blog_id 또는 전체 캐시 무효화.

    - blog_id 지정: 해당 blog_id 캐시만 제거.
    - blog_id=None: 전체 캐시 제거 (CI 머지 후 deploy hook에서 호출).
    """
    if blog_id is None:
        _cache.clear()
    else:
        _cache.pop(blog_id, None)


def get_cache_stats() -> dict:
    """캐시 히트율, 크기, 마지막 로드 시각 반환. 대시보드 디버그용."""
    total = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total) if total else 0.0
    last_load = None
    if _cache:
        last_load = max((e["loaded_at"] for e in _cache.values()), default=None)
    return {
        "size": len(_cache),
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": round(hit_rate, 4),
        "ttl_seconds": _CACHE_TTL_SECONDS,
        "last_load_time": last_load,
    }


# ---------------------------------------------------------------------------
# 트랙A 어댑터 인터페이스 (미래 연결점 — 구현 금지)
# ---------------------------------------------------------------------------


def adapt_rule_registry(schema: SchemaSpec, registry) -> "ValidatedSchema":
    """SchemaSpec에 rule_id→rule_version 매핑을 주입 (트랙A G5 해소 후 구현).

    연결 조건:
      - 트랙A G5(rule_id→rule_version DB 연결) 해소가 선행.
      - SchemaSpec.rule_refs의 key(rule_id)를 registry에서 조회해 version을 채운다.
    """
    raise NotImplementedError("트랙A G5 해소 후 구현 — 이 설계 단계에서는 금지")
