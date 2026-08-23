"""Free-form CUAP title generation with evidence injection and retry scoring."""
from __future__ import annotations
import re
from shared.title_quality import normalize_title, title_issues
from shared.cuap_title_safety import normalize_cuap_title, cuap_title_issues

def build_title_facts(keyword, products, blog_id=None):
    lines = [f"keyword: {keyword}", f"site: {blog_id or 'cuap'}"]
    for p in (products or [])[:5]:
        name = str(p.get("product_name", "")).strip()
        brand = str(p.get("brand", "") or p.get("maker", "")).strip()
        price = p.get("product_price", 0) or 0
        specs = p.get("parsed_specs", {}) or {}
        spec_text = ", ".join(f"{k}={v}" for k, v in list(specs.items())[:5])
        row = [x for x in (f"name={name}" if name else "", f"brand={brand}" if brand else "", f"price={price}" if price else "", f"specs={spec_text}" if spec_text else "") if x]
        if row:
            lines.append("; ".join(row))
    return "\n".join(lines)

def score_title(title, keyword, products, recent_titles):
    value = normalize_cuap_title(title)
    if not value or not (12 <= len(value) <= 60):
        return -100, ["length"]
    issues = title_issues(value, language="ko", recent_titles=recent_titles)
    names = []
    for p in (products or [])[:5]:
        for key in ("product_name", "brand", "maker"):
            item = str(p.get(key, "") or "").strip()
            if len(item) >= 2:
                names.append(item)
    topic_hit = any(token and token in value for token in re.findall(r"[\uac00-\ud7a3A-Za-z0-9]{2,}", keyword))
    evidence_hit = any(item in value for item in names)
    if not topic_hit and not evidence_hit:
        issues.append("no_known_topic_or_product")
    score = 50 + (20 if topic_hit else 0) + (20 if evidence_hit else 0)
    score -= 10 * len(issues)
    if re.search(r"(\ucd94\ucc9c|\ube44\uad50|\uc120\ud0dd|\uac00\uaca9|\ubb34\uac8c|\uc6a9\ub3c4|\ucd9c\ud1f4\uadfc|\uc6d0\ub8f8|\ub300\ud559\uc0dd|\uc800\uc18c\uc74c|\ud734\ub300)", value):
        score += 10
    return score, issues

def select_llm_title(keyword, products, blog_id, recent_titles, fallback, ai_generate, logger, attempts=3):
    facts = build_title_facts(keyword, products, blog_id)
    system = """You are a Korean commerce title editor. Do not use a fixed template.
Generate natural, specific titles that make a reader think: this page contains the answer I need.
Use only facts in the supplied fact sheet. Include one concrete product, use case, price, spec, or decision point when supported.
Do not use clickbait, vague emotional claims, keyword stuffing, or generic endings such as recommendation guide, buying guide, complete summary, BEST, TOP 5, or curated picks.
A title may be a question, a contrast, a use-case sentence, or a practical decision statement.
Return exactly 8 different title candidates, one per line, with no numbering, markdown, quotation marks, or commentary."""
    best, best_score = fallback, -100
    for attempt in range(attempts):
        user = f"FACT SHEET:\n{facts}\n\nRECENT TITLES TO AVOID:\n" + "\n".join(recent_titles[-8:])
        try:
            result = ai_generate(system, user, temperature=0.7 if attempt == 0 else 0.55, max_tokens=500)
        except Exception as exc:
            logger.warning("[title_candidates] attempt=%s failed: %s", attempt + 1, exc)
            continue
        text = result if isinstance(result, str) else result.get("content", "")
        for line in str(text).splitlines():
            candidate = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip().strip('"')
            candidate = normalize_cuap_title(candidate)
            safety_issues = cuap_title_issues(candidate, keyword, products, recent_titles)
            score, issues = score_title(candidate, keyword, products, recent_titles)
            issues.extend(safety_issues)
            blocked = {"length", "overly_promotional", "repeated_template", "no_known_topic_or_product", "internal_identifier", "disallowed_character", "foreign_script", "missing_topic", "too_short", "too_long", "repeated_title"}
            if score > best_score and not blocked.intersection(issues):
                best, best_score = candidate, score
        if best_score >= 80:
            break
    logger.info("[title_candidates] selected score=%s title=%s", best_score, best)
    return best
