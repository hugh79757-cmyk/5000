"""Live content quality gate for dispatcher post-generate.

Checks:
- P36 hallucination price
- P37 region mismatch
- P38 H2 count

Minimal implementation for now.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 자동 블로그만 검사, 수동/메뉴얼 블로그 제외
EXCLUDE_BLOGS = {
    "techpawz-hugo",  # 메뉴얼 블로그
    # 필요시 추가
}

def _is_auto_blog(blog_id: str) -> bool:
    return blog_id not in EXCLUDE_BLOGS

def _count_h2(md_text: str) -> int:
    return len(re.findall(r'^##\s', md_text, flags=re.MULTILINE))

def check_content_quality(blog_id: str, md_text: str, frontmatter: dict) -> dict:
    issues = []
    suggestions = []
    # P38 H2 부족
    h2_cnt = _count_h2(md_text)
    if h2_cnt < 3:
        issues.append({"code": "P38", "detail": f"H2 count {h2_cnt} < 3"})
        suggestions.append("데이터를 충분히 활용하여 실적 개요, 재무 지표 분석, 리스크 및 전망 등 자연스러운 섹션으로 확장 권장. 강제 삽입보다 공시 데이터 기반 서술 유도.")
    
    # P37 region mismatch
    region = frontmatter.get("region") or frontmatter.get("Region") or ""
    # simple heuristic: region in body
    if region:
        # extract city/district from body
        body_lower = md_text.lower()
        # minimal check: region name appears
        if region.lower() not in body_lower:
            issues.append({"code": "P37", "detail": f"region {region} not found in body"})
    
    # P36 hallucination price placeholder
    # look for price patterns without source
    if re.search(r'₩\s*\d{1,3}(,\d{3})+', md_text):
        # naive: if price appears but no source link
        if "coupang" not in md_text.lower() and "source" not in md_text.lower():
            issues.append({"code": "P36", "detail": "price without source"})
    
    return {"blog_id": blog_id, "issues": issues, "suggestions": suggestions, "h2_count": h2_cnt}

def run_live_check(blog_id: str, md_path: Path):
    if blog_id in EXCLUDE_BLOGS:
        logger.info(f"[QUALITY LIVE] {blog_id} excluded from auto check")
        return {"blog_id": blog_id, "excluded": True}
    if not md_path.exists():
        return {"error": "not found"}
    text = md_path.read_text(encoding="utf-8")
    # simple frontmatter parse
    fm = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_raw = parts[1]
            for line in fm_raw.splitlines():
                if ":" in line:
                    k,v = line.split(":",1)
                    fm[k.strip()] = v.strip()
            md_body = parts[2]
        else:
            md_body = text
    else:
        md_body = text
    result = check_content_quality(blog_id, md_body, fm)
    if result["issues"]:
        logger.warning(f"[QUALITY LIVE] {blog_id} issues: {result['issues']}")
    else:
        logger.info(f"[QUALITY LIVE] {blog_id} clean")
    return result
