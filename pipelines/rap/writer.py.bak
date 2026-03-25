"""RAP writer — 부동산 기사 생성 (GAP frontmatter 방식)"""
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _build_trade_reference(keyword, trades, region_info=None):
    """실거래가 데이터를 참고자료 블록으로 변환"""
    lines = []
    month = datetime.now().strftime("%Y년 %m월")
    city = region_info.get("city", "") if region_info else ""
    district = region_info.get("district", "") if region_info else ""
    lines.append(f"## 키워드: {keyword}")
    lines.append(f"지역: {city} {district}")
    lines.append(f"기준: {month}")
    lines.append(f"총 거래건수: {len(trades)}건\n")

    # 통계 계산
    prices = [t.get("dealAmountInt", 0) for t in trades if t.get("dealAmountInt")]
    if prices:
        lines.append("### 시세 요약")
        lines.append(f"- 최고가: {max(prices):,}만원")
        lines.append(f"- 최저가: {min(prices):,}만원")
        lines.append(f"- 평균: {sum(prices)//len(prices):,}만원")
        lines.append("")

    lines.append("### 최근 거래 내역")
    for t in trades[:15]:
        apt = t.get("aptNm", "")
        amount = t.get("dealAmount", "").strip()
        area = t.get("excluUseAr", "")
        floor = t.get("floor", "")
        dong = t.get("umdNm", "")
        year = t.get("buildYear", "")
        deal_date = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
        lines.append(f"- {dong} {apt}({year}년식) {area}㎡ {floor}층: {amount}만원 ({deal_date})")

    return "\n".join(lines)


def _build_subscription_reference(keyword, subscriptions):
    """청약 공고 데이터를 참고자료 블록으로 변환"""
    lines = []
    month = datetime.now().strftime("%Y년 %m월")
    lines.append(f"## 키워드: {keyword}")
    lines.append(f"기준: {month}")
    lines.append(f"총 공고: {len(subscriptions)}건\n")

    lines.append("### 분양/임대 공고 목록")
    for s in subscriptions[:10]:
        name = s.get("PAN_NM", "")
        region = s.get("CNP_CD_NM", "")
        start = s.get("PAN_NT_ST_DT", "")
        end = s.get("CLSG_DT", "")
        typ = s.get("AIS_TP_CD_NM", "")
        status = s.get("PAN_SS", "")
        url = s.get("DTL_URL", "")
        lines.append(f"- [{typ}] {name}")
        lines.append(f"  지역: {region} | 공고: {start} ~ 마감: {end} | 상태: {status}")
        if url:
            lines.append(f"  상세: {url}")

    return "\n".join(lines)


def generate_trade_article(keyword, trades, region_info=None):
    """실거래가 기반 기사 생성"""
    from shared.ai_writer import generate as ai_generate
    reference = _build_trade_reference(keyword, trades, region_info)
    month = datetime.now().strftime("%Y년 %m월")

    system_prompt = f"""당신은 부동산 시세 분석 전문 블로그 작가입니다.
아래 국토교통부 실거래가 데이터를 바탕으로 블로그 글을 작성하세요.

[핵심 규칙]
1. 참고자료에 없는 가격, 날짜를 절대 지어내지 마세요
2. 제공된 실거래가 데이터의 수치만 사용하세요
3. "투자 추천"이나 "매수/매도 권유"는 절대 하지 마세요
4. 참고자료 원문을 그대로 복사하지 말고 자연스럽게 재구성
5. 같은 내용을 반복하지 마세요
6. "특히" 표현 사용 금지

[제목]
- SEO 최적화 한국어, 40자 이내
- "{month}" 포함 권장
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 2500~3500자
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실거래 데이터를 마크다운 표(table)로 정리 (단지명, 면적, 층, 가격)
- 도입부: 해당 지역 부동산 시장 개요
- 중반: 주요 단지별 거래 분석 + 전월 대비 시세 변동
- 후반: 투자 시 체크리스트 3~5항목
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

출력 형식:
---
title: "제목"
category: "부동산"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""

    user_prompt = f"키워드: {keyword}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)
    if not result or not result.get("content"):
        logger.error(f"RAP 실거래가 글 생성 실패: {keyword}")
        return None
    return _parse_article(result["content"], keyword)


def generate_subscription_article(keyword, subscriptions):
    """청약 정보 기반 기사 생성"""
    from shared.ai_writer import generate as ai_generate
    reference = _build_subscription_reference(keyword, subscriptions)
    month = datetime.now().strftime("%Y년 %m월")

    system_prompt = f"""당신은 부동산 청약 전문 블로그 작가입니다.
아래 한국부동산원 청약홈 공고 데이터를 바탕으로 블로그 글을 작성하세요.

[핵심 규칙]
1. 참고자료에 없는 일정, 조건을 절대 지어내지 마세요
2. 청약 자격, 일정, 신청 방법 등 실용 정보 중심으로 작성
3. "당첨 보장" 등 과장 표현 금지
4. 같은 내용을 반복하지 마세요
5. "특히" 표현 사용 금지

[제목]
- SEO 최적화 한국어, 40자 이내
- "{month}" 포함 권장
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 2500~3500자
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 공고 목록을 마크다운 표(table)로 정리 (공고명, 유형, 지역, 접수기간)
- 신청 자격과 준비 서류 체크리스트 포함
- 청약 당첨 확률 높이는 팁 포함
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

출력 형식:
---
title: "제목"
category: "청약정보"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""

    user_prompt = f"키워드: {keyword}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)
    if not result or not result.get("content"):
        logger.error(f"RAP 청약 글 생성 실패: {keyword}")
        return None
    return _parse_article(result["content"], keyword)


def _parse_article(response, keyword):
    """GAP과 동일한 frontmatter(---) 방식 파싱"""
    fm_match = re.search(r"---\s*\n(.+?)\n---", response, re.DOTALL)
    if not fm_match:
        logger.warning(f"frontmatter 파싱 실패: {keyword}")
        return None

    fm_text = fm_match.group(1)
    body_md = response[fm_match.end():].strip()

    title = ""
    category = "부동산"
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
