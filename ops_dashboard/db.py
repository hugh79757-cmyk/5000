"""ops_dashboard.db — SQLite 데이터 모델 + YAML sync

테이블:
  - blog_lifecycle: 블로그별 라이프사이클 상태 (진실의 단일 출처)
  - known_issues: GSD 문서에서 추출한 알려진 이슈
  - check_results: 헬스체크 실행 이력
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "ops.db"
PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_D = PROJECT_ROOT / "config" / "blogs.d"

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _alter_columns(conn: sqlite3.Connection) -> None:
    """기존 테이블에 새 컬럼 추가 (이미 존재하면 무시)."""
    alters = [
        # blog_lifecycle 정비 컬럼
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_status TEXT NOT NULL DEFAULT 'none'",
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_started_at TEXT",
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_completed_at TEXT",
        "ALTER TABLE blog_lifecycle ADD COLUMN resume_ready INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 이미 컬럼이 있으면 무시
    conn.commit()


def get_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    p = str(db_path or DB_PATH)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """테이블 생성 (IF NOT EXISTS)."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS blog_lifecycle (
        blog_id TEXT PRIMARY KEY,
        brand TEXT NOT NULL,
        config_status TEXT NOT NULL DEFAULT 'inactive',
        lifecycle_status TEXT NOT NULL DEFAULT 'unknown',
        pause_reason TEXT DEFAULT '',
        paused_at TEXT,
        days_since_last_publish INTEGER,
        consecutive_failures INTEGER DEFAULT 0,
        theme TEXT DEFAULT '',
        pipeline_path TEXT DEFAULT '',
        domain TEXT DEFAULT '',
        cf_project TEXT DEFAULT '',
        site_path TEXT DEFAULT '',
        quality_grade TEXT DEFAULT '',
        domain_health TEXT DEFAULT '',
        standard_compliance TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        -- 정비·재개 프레임워크 필드 (Phase 60 Part 2)
        maintenance_status TEXT NOT NULL DEFAULT 'none',
        maintenance_started_at TEXT,
        maintenance_completed_at TEXT,
        resume_ready INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    -- 정비 체크리스트 항목 추적
    CREATE TABLE IF NOT EXISTS maintenance_checklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        check_id TEXT NOT NULL,
        check_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        detail TEXT DEFAULT '',
        checked_at TEXT,
        UNIQUE(blog_id, check_id)
    );

    CREATE INDEX IF NOT EXISTS idx_maint_blog ON maintenance_checklist(blog_id);

    CREATE TABLE IF NOT EXISTS known_issues (
        issue_id TEXT PRIMARY KEY,
        blog_ids TEXT DEFAULT '',
        category TEXT NOT NULL,
        symptom TEXT NOT NULL,
        recorded_date TEXT NOT NULL,
        gsd_status TEXT NOT NULL DEFAULT 'open',
        auto_detectable TEXT NOT NULL DEFAULT 'no',
        detection_method TEXT DEFAULT '',
        resolution_status TEXT NOT NULL DEFAULT 'open',
        current_detection TEXT DEFAULT 'na',
        notes TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS check_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        check_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'unknown',
        detail TEXT DEFAULT '',
        evidence_url TEXT DEFAULT '',
        checked_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

CREATE INDEX IF NOT EXISTS idx_check_blog ON check_results(blog_id);
CREATE INDEX IF NOT EXISTS idx_check_name ON check_results(check_name);
CREATE INDEX IF NOT EXISTS idx_check_time ON check_results(checked_at);

CREATE TABLE IF NOT EXISTS standard_rules (
    rule_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MAJOR',
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_standard_rules_target ON standard_rules(target);
""")

    # Phase 60: 기존 테이블에 새 컬럼 추가 (IF NOT EXISTS는 컬럼 추가 안 됨)
    _alter_columns(conn)


# ---------------------------------------------------------------------------
# YAML → blog_lifecycle sync
# ---------------------------------------------------------------------------

def _parse_yaml_file(path: Path) -> list[dict]:
    """간단한 YAML 파서 (pyyaml 없이, blogs.d 형식 전용).

    블로그 항목은 '- key:' 패턴으로 시작하는 항목을 찾아서 파싱한다.
    blog_id는 다음 키에서 추출 (우선순위): id, cf_project, blogger_blog_id,
    blog_id_env(환경변수 이름 → 값은 런타임에 확인 불가하므로 이름 기록).

    지원하는 시작 키:
      - id: compare-hugo          (cap, cuap, etap, rap, tap)
      - cf_project: compare-hugo  (cap, stap)
      - blogger_blog_id: ...      (seap)
      - domain: ...               (manual)
      - blog_id_env: ...          (tap - tvshow-blogger, ud-blogger)
    """
    blogs = []
    current = None
    in_schedule = False

    with open(path) as f:
        for line in f:
            stripped = line.rstrip()

            # 새 블로그 항목 시작: 들여쓰기 없는 '- ' 접두사
            if stripped.startswith("- ") and not stripped.startswith("  "):
                # 새 항목 시작
                if current:
                    blogs.append(current)
                current = {"blog_id": "", "source_file": path.name}
                in_schedule = False

                # 첫 키에서 ID 추출 시도
                after_dash = stripped[2:].strip()  # "- " 제거
                if ":" in after_dash:
                    key, _, val = after_dash.partition(":")
                    key = key.strip()
                    val = val.strip()
                    _assign_id_from_key(current, key, val)
                continue

            if current is None:
                continue

            # 스케줄 블록 내부
            if stripped.startswith("schedule:"):
                in_schedule = True
                continue
            if in_schedule and stripped.startswith("times:"):
                continue
            if in_schedule and stripped.startswith("- "):
                # 스케줄 항목 (무시)
                continue
            if in_schedule and not stripped.startswith(" ") and stripped:
                in_schedule = False

            # 일반 키: 값 파싱
            if ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if key == "id":
                current["blog_id"] = val
            elif key == "cf_project":
                current["cf_project"] = val
                if not current.get("blog_id"):
                    current["blog_id"] = val
            elif key == "blogger_blog_id":
                current["blog_id"] = current.get("blog_id") or val
            elif key == "blog_id_env":
                current["blog_id_env"] = val
                if not current.get("blog_id"):
                    current["blog_id"] = f"env:{val}"
            elif key == "status":
                current["config_status"] = val
            elif key == "domain":
                current["domain"] = val
            elif key == "site_path":
                current["site_path"] = val
            elif key == "theme":
                current["theme"] = val
            elif key == "pipeline":
                current["pipeline"] = val
            elif key == "daily_quota":
                current["daily_quota"] = val

    if current:
        blogs.append(current)

    return blogs


def _assign_id_from_key(blog: dict, key: str, val: str) -> None:
    """첫 '- key: val' 라인에서 blog_id를 할당."""
    if key == "id":
        blog["blog_id"] = val
    elif key == "cf_project":
        blog["cf_project"] = val
        blog["blog_id"] = val
    elif key == "blogger_blog_id":
        blog["blog_id"] = val
    elif key == "domain":
        blog["domain"] = val
        # domain에서 blog_id 유추 불가 — 나중에 보완
    elif key == "blog_id_env":
        blog["blog_id_env"] = val
        blog["blog_id"] = f"env:{val}"
    else:
        # 알 수 없는 시작 키 — 일단 빈 ID
        pass


def _detect_brand(filename: str) -> str:
    """YAML 파일명에서 계열 감지."""
    mapping = {
        "cap.yaml": "cap",
        "cuap.yaml": "cuap",
        "etap.yaml": "etap",
        "rap.yaml": "rap",
        "seap.yaml": "seap",
        "stap.yaml": "stap",
        "tap.yaml": "tap",
        "manual_blog_for_backup.yaml": "manual",
    }
    return mapping.get(filename, "unknown")


def sync_blog_lifecycle(conn: sqlite3.Connection) -> int:
    """YAML 파일을 파싱하여 blog_lifecycle 테이블을 동기화.

    반환: 삽입/업데이트된 행 수.
    """
    count = 0
    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.name.endswith(".bak") or yaml_file.name.startswith("."):
            continue
        brand = _detect_brand(yaml_file.name)
        blogs = _parse_yaml_file(yaml_file)

        for b in blogs:
            blog_id = b.get("blog_id", "")
            if not blog_id:
                continue

            # 기존 레코드 확인
            existing = conn.execute(
                "SELECT blog_id FROM blog_lifecycle WHERE blog_id = ?",
                (blog_id,),
            ).fetchone()

            now = datetime.now(timezone.utc).isoformat()

            if existing:
                conn.execute("""
                    UPDATE blog_lifecycle SET
                        brand = ?,
                        config_status = ?,
                        theme = ?,
                        domain = ?,
                        cf_project = ?,
                        site_path = ?,
                        updated_at = ?
                    WHERE blog_id = ?
                """, (
                    brand,
                    b.get("config_status", "unknown"),
                    b.get("theme", ""),
                    b.get("domain", ""),
                    b.get("cf_project", ""),
                    b.get("site_path", ""),
                    now,
                    blog_id,
                ))
            else:
                conn.execute("""
                    INSERT INTO blog_lifecycle
                    (blog_id, brand, config_status, lifecycle_status,
                     theme, domain, cf_project, site_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    blog_id,
                    brand,
                    b.get("config_status", "unknown"),
                    "unknown",
                    b.get("theme", ""),
                    b.get("domain", ""),
                    b.get("cf_project", ""),
                    b.get("site_path", ""),
                    now,
                ))
            count += 1

    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Known issues seed
# ---------------------------------------------------------------------------

SEED_ISSUES: list[dict] = [
    # Phase 58 PROBLEM_REGISTRY (24건)
    {"issue_id": "P01", "blog_ids": "", "category": "general", "symptom": "no_result — 데이터 수집 성공이나 가드 차단으로 결과 없음", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "P02", "blog_ids": "", "category": "general", "symptom": "no_content — 토픽 소진/중복 가드로 콘텐츠 생성 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "P03", "blog_ids": "", "category": "general", "symptom": "similar_title — 유사 제목 80% 초과로 차단", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "title_similar_exists() SequenceMatcher"},
    {"issue_id": "P04", "blog_ids": "", "category": "general", "symptom": "deploy_error — 배포 실패 (Wrangler/CF 인증/Workers)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "wrangler exit code != 0"},
    {"issue_id": "P05", "blog_ids": "", "category": "general", "symptom": "hugo_build_failed — Hugo 빌드 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "hugo --gc --minify stderr 패턴 매칭"},
    {"issue_id": "P06", "blog_ids": "", "category": "cuap", "symptom": "broken_featureimage — 썸네일 URL 깨짐 (404)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "post_publish HTTP HEAD 200 확인"},
    {"issue_id": "P07", "blog_ids": "", "category": "general", "symptom": "cjk_leak — CJK 언어 누수 (한자/일본어/중국어)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "regex + 한글비율 0.5"},
    {"issue_id": "P08", "blog_ids": "", "category": "general", "symptom": "cot_leak — CoT/프롬프트 누수", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "ko_thinking/prompt_instruction_leak 패턴"},
    {"issue_id": "P09", "blog_ids": "", "category": "general", "symptom": "url_token_repeat — 이미지 URL 토큰 반복", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "4자+ 5회+ 반복 패턴 regex"},
    {"issue_id": "P10", "blog_ids": "", "category": "cuap", "symptom": "title_blocked — 제목 차단", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "TITLE_BLOCKED 플래그"},
    {"issue_id": "P11", "blog_ids": "", "category": "cuap", "symptom": "title_regenerate_failed — 제목 재생성 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "_title_gate() return None"},
    {"issue_id": "P12", "blog_ids": "", "category": "cuap", "symptom": "content_quality_gate — 품질 게이트 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "_content_quality_gate() return False"},
    {"issue_id": "P13", "blog_ids": "", "category": "general", "symptom": "rate_limited — API 속도 제한", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "HTTP 429 응답"},
    {"issue_id": "P15", "blog_ids": "", "category": "general", "symptom": "post_publish_validation — 발행 후 검증 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "validate_post_extended() False"},
    {"issue_id": "P17", "blog_ids": "", "category": "general", "symptom": "quota_exceeded — 할당량 초과", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "publish_log 일일 한도"},
    {"issue_id": "P22", "blog_ids": "", "category": "general", "symptom": "llm_fallback_exhausted — LLM 폴백 전체 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "17개 모델 전부 실패"},
    {"issue_id": "P23", "blog_ids": "", "category": "general", "symptom": "image_url_long — 이미지 URL 길이 초과 (255자)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 > 255자"},

    # 품질 진단 (미해결)
    {"issue_id": "Q1", "blog_ids": "baby-hugo,laptop-hugo,pet-hugo,beauty-hugo", "category": "cuap", "symptom": "experience_claim — 경험/체험 허위 주장 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 1인칭 금지 지시 미적용"},
    {"issue_id": "Q2", "blog_ids": "beauty-hugo,fitness-hugo,health-hugo", "category": "cuap", "symptom": "unsource_number — 소스 불명 수치 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 퍼지 표현 필터 미적용"},
    {"issue_id": "Q3", "blog_ids": "beauty-hugo,health-hugo", "category": "cuap", "symptom": "health_efficacy — 건강 효능 단정 (20%, 법적 리스크)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 건강 효능 금지 지시 없음"},
    {"issue_id": "Q4", "blog_ids": "baby-hugo,camping-hugo,pet-hugo", "category": "cuap", "symptom": "template_h2 — 반복 H2 템플릿 구조 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트가 ## N위: 제품명 고정 강제"},
    {"issue_id": "Q5", "blog_ids": "beauty-hugo", "category": "quality", "symptom": "금지어 dead config: quality_checklist.yaml global_forbidden_words 6개 정의되나 writer.py 런타임 미적용", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "re.findall(pattern, content) — 좋은(12건), 최고의(4건) 실측"},
    {"issue_id": "Q6", "blog_ids": "beauty-hugo", "category": "quality", "symptom": "H2 검증 허점: writer.py:496이 H2 카운트만 하고 H2>=1 미검증. 옛 TOP5 포맷 잔존글에서 H2=0 발생", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "re.findall(r'^## ', content) — H2=0 포스트 1건 실측"},

    # 품질 감사 (미해결)
    {"issue_id": "QA-01", "blog_ids": "travel3-hugo", "category": "tap", "symptom": "title_body_region — 제목 '계룡시' vs 본문 '서산시' 지역 불일치", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "제목-본문 지역 검증 게이트 미구현"},
    {"issue_id": "QA-02", "blog_ids": "compare-hugo", "category": "cap", "symptom": "irrelevant_coupang — 차량 비교글에 무관 쿠팡 링크", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "상품-주제 관련도 필터 미구현"},
    {"issue_id": "QA-03", "blog_ids": "travel2-hugo", "category": "tap", "symptom": "excessive_coupang — 문화유산 글에 쿠팡 18건 과다", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "쿠팡 링크 상한(3건) 미설정"},
    {"issue_id": "QA-04", "blog_ids": "hotissue-hugo", "category": "cap", "symptom": "empty_body — 본문 2자 포스트 (RSS 더미)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "본문 길이 < 100자 검사"},
    {"issue_id": "QA-05", "blog_ids": "travel1-hugo", "category": "tap", "symptom": "title_body_count — 제목 '5곳' vs 본문 3곳 숫자 불일치", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "제목-본문 숫자 검증 미구현"},
    {"issue_id": "QA-06", "blog_ids": "travel1-hugo,travel3-hugo", "category": "tap", "symptom": "generic_text — 범용 문장 과다 ('이번 글에서는' 등)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "범용 패턴 카운트 미구현"},

    # 구조적 불균일성
    {"issue_id": "STRUCT-01", "blog_ids": "", "category": "etap", "symptom": "etap_write_hugo — _write_hugo_post() 30+ 파일 중복", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "ETAP *_pipeline.py별 _write_hugo_post 존재 검사"},
    {"issue_id": "STRUCT-02", "blog_ids": "", "category": "general", "symptom": "publisher_token — publisher.py CLOUDFLARE_API_TOKEN 유지 (불일치)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "grep CLOUDFLARE_API_TOKEN in publisher.py"},
    {"issue_id": "STRUCT-03", "blog_ids": "hotissue-hugo", "category": "cap", "symptom": "theme_mismatch — PaperMod 테마 (Blowfish 통일 기준 위반)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "YAML theme 필드 != blowfish"},
    {"issue_id": "STRUCT-04", "blog_ids": "stock-hugo", "category": "stap", "symptom": "theme_mismatch — Congo 테마 (Blowfish 통일 기준 위반)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "YAML theme 필드 != blowfish"},
    {"issue_id": "STRUCT-06", "blog_ids": "flights-hugo", "category": "etap", "symptom": "flights_flight — flights-hugo(YAML/CF) vs flight-hugo(dispatcher) 불일치", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "grep flight-hugo in dispatcher.py vs YAML"},
    {"issue_id": "STRUCT-07", "blog_ids": "beauty-hugo", "category": "structural", "symptom": "publish_ledger title 공백: 발행 성공(published) 시 title=\"\" 45.9%(187/407). ledger 기록 누락", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "SELECT COUNT(*) WHERE title=\"\" AND status=\"published\" — 187/407건"},

    # Triage 해결 이슈 (대표적 10건)
    {"issue_id": "T-04", "blog_ids": "tap-blogger", "category": "tap", "symptom": "tap_meta_response — 메타 응답 발행 (해결됨)", "recorded_date": "2026-07-26", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "validators.py 메타 패턴 매칭"},
    {"issue_id": "T-07", "blog_ids": "kitchen-hugo", "category": "cuap", "symptom": "kitchen_blank_body — 모바일 본문 공백 (해결됨)", "recorded_date": "2026-07-21", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "모바일 뷰포트 본문 공백 확인"},
    {"issue_id": "T-14", "blog_ids": "kuta-hugo", "category": "cap", "symptom": "kuta_broken_thumbnail — WordPress 도메인 경로 404 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "HTTP HEAD 200 확인"},
    {"issue_id": "T-16", "blog_ids": "appliance-hugo", "category": "cuap", "symptom": "file_name_too_long — 이미지 URL 300자 초과 (해결됨)", "recorded_date": "2026-07-09", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 > 255자 검사"},

    # Incident (AGENTS.md)
    {"issue_id": "INC-01", "blog_ids": "travel2-hugo", "category": "tap", "symptom": "no_result_10 — 시군구 가드 연속 10회 실패 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "INC-03", "blog_ids": "appliance-hugo", "category": "cuap", "symptom": "similar_title — 듀스핀 키워드 유사 제목 반복 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "SequenceMatcher 80%"},
    {"issue_id": "INC-04", "blog_ids": "laptop-hugo", "category": "cuap", "symptom": "deploy_error_image_url — 이미지 URL 255자 초과→빌드 실패 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 검사"},
]


def seed_known_issues(conn: sqlite3.Connection) -> int:
    """known_issues 테이블에 GSD 이슈를 시드.

    반환: 삽입된 행 수 (기존과 중복된 것은 무시).
    """
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for issue in SEED_ISSUES:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO known_issues
                (issue_id, blog_ids, category, symptom, recorded_date,
                 gsd_status, auto_detectable, detection_method,
                 resolution_status, current_detection, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                issue["issue_id"],
                issue.get("blog_ids", ""),
                issue["category"],
                issue["symptom"],
                issue["recorded_date"],
                issue["gsd_status"],
                issue["auto_detectable"],
                issue.get("detection_method", ""),
                issue["gsd_status"],  # resolution_status = gsd_status 초기값
                "na",
                now,
            ))
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Standard rules seed
# ---------------------------------------------------------------------------

SEED_STANDARD_RULES: list[dict] = [
    {"rule_id": "R01", "target": "hugo.toml", "severity": "CRITICAL", "description": "showTableOfContents must be false"},
    {"rule_id": "R02", "target": "hugo.toml", "severity": "CRITICAL", "description": "Advertisement section with adsense slots required"},
    {"rule_id": "R03", "target": "extend-head.html", "severity": "CRITICAL", "description": "adsbygoogle.js must use site.Params (no hardcoding)"},
    {"rule_id": "R04", "target": "extend_head.html", "severity": "MAJOR", "description": "GA4 + mobile correction CSS required"},
    {"rule_id": "R05", "target": "adsense/top.html", "severity": "MAJOR", "description": "overflow:hidden;min-height:100px wrapper + outside push div"},
    {"rule_id": "R06", "target": "adsense/in-article.html", "severity": "CRITICAL", "description": "fluid+in-article format (no auto) + outside push div"},
    {"rule_id": "R07", "target": "single.html", "severity": "MAJOR", "description": "H2 split injection + prose wrapper"},
    {"rule_id": "R08", "target": "single.html", "severity": "MAJOR", "description": "Description (lead) must be removed"},
    {"rule_id": "R09", "target": "baseof.html", "severity": "MAJOR", "description": "No custom override — use theme default"},
    {"rule_id": "R10", "target": "custom.css", "severity": "MAJOR", "description": "Unfilled space removal + dark mode + min-height rules"},
    {"rule_id": "R11", "target": "layouts/", "severity": "MAJOR", "description": "mobile-sticky.html must not be used"},
    {"rule_id": "R12", "target": "layouts/", "severity": "MAJOR", "description": "No override files beyond the allowed set"},
]


def seed_standard_rules(conn: sqlite3.Connection) -> int:
    """standard_rules 테이블에 R01~R12 규칙을 시드.

    반환: 삽입된 행 수 (기존과 중복된 것은 무시).
    """
    count = 0
    for rule in SEED_STANDARD_RULES:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO standard_rules
                (rule_id, target, severity, description)
                VALUES (?, ?, ?, ?)
            """, (rule["rule_id"], rule["target"], rule["severity"], rule["description"]))
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Maintenance status seed — Phase 60 Part 2
# ---------------------------------------------------------------------------

MAINTENANCE_SEED_BLOGS: list[dict] = [
    # P03으로 차단된 7개 블로그 + RAP 정비 대상
    {"blog_id": "beauty-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "interior-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "kitchen-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "pick-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "senior-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "senior-blogger", "maintenance_status": "awaiting"},
    {"blog_id": "travel4-hugo", "maintenance_status": "awaiting"},
]


def seed_maintenance_status(conn: sqlite3.Connection) -> int:
    """정비 대상 블로그에 maintenance_status를 시드.

    반환: 업데이트된 행 수.
    """
    count = 0
    for item in MAINTENANCE_SEED_BLOGS:
        try:
            conn.execute("""
                UPDATE blog_lifecycle
                SET maintenance_status = ?
                WHERE blog_id = ? AND maintenance_status = 'none'
            """, (item["maintenance_status"], item["blog_id"]))
            count += conn.total_changes
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 정비 체크리스트 — Phase 60 Part 2 표준
# ---------------------------------------------------------------------------

MAINTENANCE_CHECKLIST_ITEMS: list[dict] = [
    #CUAP/RAP 정비 경험에서 추출한 표준 항목
    {"check_id": "M01", "name": "제목 CJK 없음", "description": "제목에 한자/일본어/중국어 누수 없음"},
    {"check_id": "M02", "name": "이미지 정상 (동일 반복 없음)", "description": "썸네일/본문 이미지가 동일 이미지를 반복 사용하지 않음"},
    {"check_id": "M03", "name": "크로스링크 주제 일관", "description": "내부 링크가 블로그 주제와 무관하지 않음"},
    {"check_id": "M04", "name": "본문 품질 게이트 통과", "description": "Q1~Q4 품질 이슈 없음 (허위 경험, 소스불명 수치, 건강효능 단정, 템플릿 반복)"},
    {"check_id": "M05", "name": "표준 (광고/테마) 준수", "description": "R01~R12 표준 규칙 모두 통과"},
    {"check_id": "M06", "name": "토픽/키워드 잔량 충분", "description": "active 키워드 100개 이상, 7일 내 사용 키워드 30% 미만"},
    {"check_id": "M07", "name": "P03 유사제목 안전", "description": "최근 3일 내 발행 제목과 유사한 제목이 파이프라인에서 생성되지 않음"},
    {"check_id": "M08", "name": "CoT/프롬프트 누수 없음", "description": "본문에 사고 과정(CoT)이나 프롬프트 문구 누수 없음"},
    {"check_id": "M09", "name": "publish_log 기록 정상", "description": "발행 성공 시 publish_log에 기록이 정상적으로 남음"},
    {"check_id": "M10", "name": "도메인 가용성", "description": "HTTP HEAD 200 정상 응답"},
]


def init_maintenance_checklist(conn: sqlite3.Connection, blog_id: str) -> None:
    """특정 블로그의 정비 체크리스트 항목을 초기화."""
    for item in MAINTENANCE_CHECKLIST_ITEMS:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO maintenance_checklist
                (blog_id, check_id, check_name, status)
                VALUES (?, ?, ?, 'pending')
            """, (blog_id, item["check_id"], item["name"]))
        except sqlite3.IntegrityError:
            pass
    conn.commit()


def get_maintenance_checklist(conn: sqlite3.Connection, blog_id: str) -> list[dict]:
    """특정 블로그의 정비 체크리스트 조회."""
    rows = conn.execute("""
        SELECT * FROM maintenance_checklist
        WHERE blog_id = ? ORDER BY check_id
    """, (blog_id,)).fetchall()
    return [dict(r) for r in rows]


def get_maintenance_summary(conn: sqlite3.Connection) -> dict:
    """전체 블로그별 정비 진행 상황 요약."""
    rows = conn.execute("""
        SELECT
            bl.blog_id,
            bl.brand,
            bl.maintenance_status,
            bl.resume_ready,
            bl.config_status,
            COUNT(CASE WHEN mc.status = 'pass' THEN 1 END) as pass_count,
            COUNT(CASE WHEN mc.status = 'fail' THEN 1 END) as fail_count,
            COUNT(CASE WHEN mc.status = 'pending' THEN 1 END) as pending_count,
            COUNT(*) as total_checks
        FROM blog_lifecycle bl
        LEFT JOIN maintenance_checklist mc ON bl.blog_id = mc.blog_id
        WHERE bl.maintenance_status != 'none'
        GROUP BY bl.blog_id
        ORDER BY bl.brand, bl.blog_id
    """).fetchall()
    return [dict(r) for r in rows]


def set_check_item_status(
    conn: sqlite3.Connection,
    blog_id: str,
    check_id: str,
    status: str,
    detail: str = "",
) -> None:
    """정비 체크리스트 항목 상태 업데이트."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE maintenance_checklist
        SET status = ?, detail = ?, checked_at = ?
        WHERE blog_id = ? AND check_id = ?
    """, (status, detail, now, blog_id, check_id))
    conn.commit()


def update_maintenance_status(
    conn: sqlite3.Connection,
    blog_id: str,
    maintenance_status: str,
) -> None:
    """블로그의 정비 상태 업데이트."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    fields = {"maintenance_status": maintenance_status}
    if maintenance_status == "in_progress":
        fields["maintenance_started_at"] = now
    elif maintenance_status == "ready":
        fields["maintenance_completed_at"] = now
        fields["resume_ready"] = 1
    elif maintenance_status == "none":
        fields["resume_ready"] = 0

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [blog_id]
    conn.execute(f"UPDATE blog_lifecycle SET {set_clause} WHERE blog_id = ?", values)
    conn.commit()


def get_all_blogs(conn: sqlite3.Connection) -> list[dict]:
    """blog_lifecycle 전체 조회."""
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle ORDER BY brand, blog_id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_attention_items(conn: sqlite3.Connection) -> list[dict]:
    """주의 필요 항목: fail/stale check_results + open known_issues."""
    # 1) 최근 실패한 헬스체크가 있는 블로그
    fail_checks = conn.execute("""
        SELECT cr.blog_id, cr.check_name, cr.status, cr.detail, cr.evidence_url, cr.checked_at
        FROM check_results cr
        INNER JOIN (
            SELECT blog_id, check_name, MAX(checked_at) as latest
            FROM check_results GROUP BY blog_id, check_name
        ) latest ON cr.blog_id = latest.blog_id
            AND cr.check_name = latest.check_name
            AND cr.checked_at = latest.latest
        WHERE cr.status = 'fail'
        ORDER BY cr.checked_at DESC
    """).fetchall()

    # 2) 미해결 known_issues
    open_issues = conn.execute("""
        SELECT * FROM known_issues
        WHERE gsd_status = 'open'
        ORDER BY category, issue_id
    """).fetchall()

    # 3) stale 블로그 (active인데 오래된 발행)
    stale = conn.execute("""
        SELECT blog_id, days_since_last_publish, lifecycle_status
        FROM blog_lifecycle
        WHERE config_status = 'active'
          AND days_since_last_publish IS NOT NULL
          AND days_since_last_publish > 3
        ORDER BY days_since_last_publish DESC
    """).fetchall()

    return {
        "fail_checks": [dict(r) for r in fail_checks],
        "open_issues": [dict(r) for r in open_issues],
        "stale_blogs": [dict(r) for r in stale],
    }


def get_blog_detail(conn: sqlite3.Connection, blog_id: str) -> dict | None:
    """특정 블로그의 전체 정보 + 최근 헬스체크 + 관련 이슈."""
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return None

    checks = conn.execute("""
        SELECT * FROM check_results
        WHERE blog_id = ?
        ORDER BY checked_at DESC
        LIMIT 50
    """, (blog_id,)).fetchall()

    issues = conn.execute("""
        SELECT * FROM known_issues
        WHERE blog_ids LIKE ?
        ORDER BY issue_id
    """, (f"%{blog_id}%",)).fetchall()

    return {
        "blog": dict(blog),
        "checks": [dict(r) for r in checks],
        "issues": [dict(r) for r in issues],
    }


def record_check(
    conn: sqlite3.Connection,
    blog_id: str,
    check_name: str,
    status: str,
    detail: str = "",
    evidence_url: str = "",
) -> None:
    """헬스체크 결과를 기록."""
    conn.execute("""
        INSERT INTO check_results (blog_id, check_name, status, detail, evidence_url)
        VALUES (?, ?, ?, ?, ?)
    """, (blog_id, check_name, status, detail, evidence_url))
    conn.commit()
