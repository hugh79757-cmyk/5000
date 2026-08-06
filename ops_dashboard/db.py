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
        updated_at TEXT DEFAULT (datetime('now'))
    );

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
    """)


# ---------------------------------------------------------------------------
# YAML → blog_lifecycle sync
# ---------------------------------------------------------------------------

def _parse_yaml_file(path: Path) -> list[dict]:
    """간단한 YAML 파서 (pyyaml 없이, blogs.d 형식 전용).

    블로그 항목은 '- id:'로 시작하는 항목을 찾아서 파싱한다.
    """
    blogs = []
    current = None
    in_schedule = False

    with open(path) as f:
        for line in f:
            stripped = line.rstrip()

            # 새 블로그 항목 시작
            if stripped.startswith("- id:"):
                if current:
                    blogs.append(current)
                blog_id = stripped.split(":", 1)[1].strip()
                current = {"blog_id": blog_id, "source_file": path.name}
                in_schedule = False
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
            if stripped.startswith("status:"):
                current["config_status"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("domain:"):
                current["domain"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("cf_project:"):
                current["cf_project"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("site_path:"):
                current["site_path"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("theme:"):
                current["theme"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("pipeline:"):
                current["pipeline"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("daily_quota:"):
                current["daily_quota"] = stripped.split(":", 1)[1].strip()

    if current:
        blogs.append(current)

    return blogs


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
# Public helpers
# ---------------------------------------------------------------------------

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
