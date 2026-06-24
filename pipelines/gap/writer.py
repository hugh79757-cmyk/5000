import os
import re
import logging

logger = logging.getLogger(__name__)


def _clean_html(text):
    return re.sub(r"</?b>", "", text or "")


def _build_reference_block(data):
    lines = []
    lines.append(f"## 키워드: {data['keyword']}")
    lines.append(f"수집일시: {data['fetched_at']}")
    lines.append(f"총 소스: {data['total_sources']}건\n")

    if data.get("news"):
        lines.append("### 뉴스")
        for i, item in enumerate(data["news"][:5], 1):
            title = _clean_html(item.get("title", ""))
            desc = _clean_html(item.get("description", ""))
            lines.append(f"{i}. {title}")
            if desc:
                lines.append(f"   {desc[:200]}")
        lines.append("")

    if data.get("web"):
        lines.append("### 웹문서")
        for i, item in enumerate(data["web"][:5], 1):
            title = _clean_html(item.get("title", ""))
            desc = _clean_html(item.get("description", ""))
            lines.append(f"{i}. {title}")
            if desc:
                lines.append(f"   {desc[:200]}")
        lines.append("")

    if data.get("blog"):
        lines.append("### 블로그")
        for i, item in enumerate(data["blog"][:3], 1):
            title = _clean_html(item.get("title", ""))
            desc = _clean_html(item.get("description", ""))
            lines.append(f"{i}. {title}")
            if desc:
                lines.append(f"   {desc[:200]}")

    return "\n".join(lines)


def generate_gap_article(keyword, fetched_data, model=None):
    from shared.ai_writer import generate as ai_generate

    if model is None:
        model = os.getenv("OPENAI_MODEL", "mimo-v2.5")

    reference = _build_reference_block(fetched_data)

    system_prompt = """당신은 생활정보 전문 블로그 작가입니다.
아래 참고자료를 바탕으로 독자에게 실질적으로 유용한 블로그 글을 작성하세요.

[핵심 규칙]
1. 참고자료에 없는 수치, 날짜, 금액, 조건을 절대 지어내지 마세요
2. 정보가 부족한 부분은 "공식 사이트에서 확인하세요"로 안내
3. 참고자료 원문을 그대로 복사하지 말고 자연스럽게 재구성
4. 같은 내용을 반복하지 마세요

[제목]
- SEO 최적화 한국어, 40자 이내
- 연도(2026)를 포함하면 좋음
- 독자가 클릭하고 싶은 구체적 제목

[본문 형식]
- 마크다운 형식, 2000~3000자
- H2(##) 소제목 3~5개로 구조화
- 자연스러운 구어체, 한 단락 3~5문장
- 도입부에서 독자의 관심을 끌 것
- 본문 중간에 실용적인 팁이나 체크리스트 포함
- 마지막에 핵심 요약 3줄 포함
- "특히" 표현 사용 금지

출력 형식:
---
title: "제목"
category: "카테고리"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""

    user_prompt = f"키워드: {keyword}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)

    if not result or not result.get("content"):
        logger.error(f"AI 글 생성 실패: {keyword}")
        return None

    return _parse_article(result["content"], keyword)


def _parse_article(response, keyword):
    fm_match = re.search(r"---\s*\n(.+?)\n---", response, re.DOTALL)
    if not fm_match:
        logger.warning(f"frontmatter 파싱 실패: {keyword}")
        return None

    fm_text = fm_match.group(1)
    body_md = response[fm_match.end():].strip()

    title = ""
    category = "생활정보"
    tags = ""
    description = ""

    for line in fm_text.split("\n"):
        line = line.strip()
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("category:"):
            category = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("tags:"):
            tags = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'")

    if not title or not body_md:
        logger.warning(f"제목 또는 본문 없음: {keyword}")
        return None

    return {
        "title": title,
        "body_md": body_md,
        "category": category,
        "tags": tags,
        "description": description,
        "keyword": keyword,
    }
