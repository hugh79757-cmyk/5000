"""CUAP CJK→Korean 변환 스크립트.

소스 마크다운(title/slug/tags/body)에 섞인 중국어(CJK) 문자를 순수 한글로 치환한다.
치환은 의미 보존 원칙: 중국어 문자만 한글 동등어로 교체, 다른 내용(사실/수치/링크/구조)은
절대 변경하지 않는다. AI writer(shared/ai_writer.generate)를 사용.

용법:
    python3 scripts/cuap_cjk_to_korean.py [--blog BLOG] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.ai_writer import generate

_CJK_RE = re.compile(r"[一-鿿]")

_SYSTEM = """너는 한국어 텍스트 교정 전문가다. 입력된 한국어 텍스트에 섞인 중국어(한자) 문자를 \
그에 대응하는 순수 한글로만 교체하라. 다른 모든 내용(사실, 수치, 링크, 마크다운 구조, 문장 흐름)은 \
절대 변경하지 말고 그대로 유지하라. 중국어가 없으면 원문을 그대로 반환하라. 교정된 텍스트만 출력하고 \
설명이나 요약은 일절 금지."""

_TARGET_BLOGS = ["baby", "pet", "kitchen", "camping"]


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _convert_text(text: str, blog_id: str) -> str:
    """CJK가 섞인 텍스트를 순수 한글로 변환."""
    if not _has_cjk(text):
        return text
    user_prompt = f"[입력]\n{text}\n\n[출력 규칙]\n- 중국어 문자만 한글로 교체\n- 나머지는 그대로\n- 교정된 텍스트만 출력"
    try:
        result = generate(_SYSTEM, user_prompt, tier="economy")
        if result and result.get("content"):
            out = result["content"].strip()
            # 프롬프트 누수 제거
            out = re.sub(r"^\[입력\].*?\[출력 규칙\].*?$", "", out, flags=re.DOTALL)
            out = out.strip()
            if out and _has_cjk(out):
                # 변환 실패 시 원본 보존
                logger.warning(f"[{blog_id}] CJK 잔존 — 원본 보존")
                return text
            return out or text
    except Exception as e:  # noqa
        logger.warning(f"[{blog_id}] 변환 실패: {e}")
    return text


def process_post(md_path: Path, blog_id: str, dry_run: bool) -> bool:
    """단일 포스트 마크다운 처리. 변경 시 True 반환."""
    content = md_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # frontmatter 파싱 (간단 방식: --- 사이 블록)
    if lines[0].strip() == "---":
        fm_end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
        if fm_end is None:
            return False

        changed = False
        new_lines = lines[:]
        for i in range(1, fm_end):
            line = lines[i]
            m = re.match(r"^(title|slug|tags):\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2)
                if _has_cjk(val):
                    new_val = _convert_text(val, blog_id)
                    if new_val != val:
                        new_lines[i] = f"{key}: {new_val}"
                        changed = True
                        logger.info(f"[{blog_id}] {md_path.name} | {key} 변환")
            # tags 리스트 항목 ( - 'xxx')
            elif re.match(r"^\s*-\s*'.*'$", line) and _has_cjk(line):
                new_val = _convert_text(line, blog_id)
                if new_val != line:
                    new_lines[i] = new_val
                    changed = True

        # 본문 변환
        body = "\n".join(lines[fm_end + 1 :])
        if _has_cjk(body):
            new_body = _convert_text(body, blog_id)
            if new_body != body:
                new_lines[fm_end + 1 :] = new_body.split("\n")
                changed = True
                logger.info(f"[{blog_id}] {md_path.name} | 본문 변환")

        if changed and not dry_run:
            md_path.write_text("\n".join(new_lines), encoding="utf-8")
        return changed

    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blog", help="특정 블로그만 처리")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import logging
    global logger
    logger = logging.getLogger("cjk2kr")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    base = Path("/Users/twinssn/Projects/CUAP")
    blogs = [args.blog] if args.blog else _TARGET_BLOGS

    total_changed = 0
    for b in blogs:
        posts_dir = base / f"{b}-hugo/content/posts"
        if not posts_dir.exists():
            logger.warning(f"{b}-hugo posts 디렉토리 없음")
            continue
        for md in posts_dir.rglob("index.md"):
            if process_post(md, f"{b}-hugo", args.dry_run):
                total_changed += 1
                logger.info(f"변경: {md}")

    logger.info(f"총 변경 포스트: {total_changed}건")


if __name__ == "__main__":
    main()
