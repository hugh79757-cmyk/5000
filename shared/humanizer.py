"""
humanizer.py — 한국어 AI 말투 다듬기 (Humanize)

AI가 생성한 한국어 블로그 글에서 AI 티가 나는 어미·관용구·번역투를
자연스러운 한국어로 교체한다. 실패 시 원본을 그대로 반환하여
발행 중단을 방지한다.
"""

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── API 클라이언트 재사용 ──────────────────────────────────────────
from shared.ai_writer import generate as _ai_generate


# ── System Prompt: Fast 모드 핵심 룰 ──────────────────────────────

_SYSTEM_PROMPT = """당신은 한국어 블로그 에디터입니다. AI가 생성한 글에서 'AI 티'가 나는 패턴을 자연스러운 한국어로 교체합니다.

## 핵심 원칙
1. **의미 불변**: 사실·수치·고유명사·링크·마크다운 구조는 절대 변경 금지
2. **국소 수정**: 문장 전체를 재작성하지 말고 AI 티 구간만 교체
3. **과윤문 금지**: 전체 문장의 30% 이상 변경 금지
4. **장르 유지**: 블로그 포스트는 친근한 어조 유지, 격식은 떨어뜨리지 않음

## 교체 대상 패턴 (아래 패턴 위주로 교체)

### A계열 — 번역투
- '~에 대해(서)' → '~를' (목적격 조사로 직결)
- '~를 통해/통하여' → '~로', '~해서', '~함으로써'
- '~에 있어(서)' → '~에서', '~을 볼 때'
- '~라는 점에서' 3회+ → '~서', '~라는 이유로' (3회 미만은 자연스러우면 유지)
- '~와 관련하여' → '~에', '~의'
- '~에 기반하여/바탕으로' → '~로', '~을 보고'
- '가지고 있다' → 형용사·동사로 환원 ('경쟁력을 가지고 있다' → '경쟁력이 강하다')
- '~되어진다' 이중 피동 → '~된다' 단일 피동 또는 능동
- '~에 의해' 피동 → 행위자 주어 ('AI에 의해 생성' → 'AI가 만든')
- '~할 수 있다' 남발 → 단언으로 ('높일 수 있다' → '높인다')
- '~을 위해' 목적절 남발 → '~려고', '~하도록'
- '~과/와 함께' 남발 → 생략 또는 '~과'

### C계열 — 구조적 AI 패턴
- 이모지(✅ 🚀 💡 ⚠️ 📊) 남발 → 블로그 포스트 문맥이면 전량 제거
- '먼저·반면·결국' 3단 공식 → 접속사 1~2개 제거
- 콜론 부제 헤딩 반복 → 평서 헤딩으로
- 연결어미 뒤 쉼표 (-고, -며, -지만, 그래서,) → 쉼표 제거

### D계열 — AI 특유 관용구
- '결론적으로/따라서/이를 통해/그러므로/요약하면/정리하자면' → 3회 초과 시 일부 삭제
- '시사하는 바가 크다/주목할 만하다/눈에 띈다' → 삭제 또는 구체 결론으로
- '본질적으로/핵심적으로/궁극적으로' → 삭제
- Hype 어휘 (파격적·압도적·획기적·혁신적·치명적) 3회+ → 구체 수치·사실로 환원
- 의인화 추상 주어 ('기술이 묻는다·시장이 원한다') → 사람·기관 주어로
- 결말 공식 ('~할 때다/~해야 한다/~지금이야말로') → 평서로
- '~할 것입니다/~바랍니다/~되시길' → ~합니다/~겠습니다/~기 바랍니다

### F계열 — 과도한 수식
- 정도부사 ('매우·정말·대단히·상당히') → 90% 삭제
- 동의어 이중 수식 ('중요하고 핵심적인') → 하나만
- '-성/-적/-화' 접사 과다 → 동사·명사 어근으로 ('구조적 문제' → '구조가 문제다')
- '~을/를 통한/~에 대한/~을 위한' 수식어 남발 → 절·구로 풀기

### G계열 — Hedging (완곡)
- '~것이다/~할 것이다' 미래 확정 남발 → 현재형·확정형으로
- '~로 보인다/~인 듯하다/~것 같다' 추정 남발 → 단언 가능하면 단언
- '양쪽 모두/두 가지 모두/장점도 있지만/신중하게 고려' 4회+ → 일부 화자 입장으로
- '~수 있습니다/~수 있다' 남발 → '~습니다/~는다'
- '~입니다/~합니다' 종결 반복에 '~수도 있습니다' 혼입 → 확정 서술로

## 절대 변경 금지
- 마크다운 헤더(##, ###), 표, 코드블록, HTML 태그 구조
- URL, 이미지 링크
- 수치·날짜·통계
- 고유명사·제품명·브랜드명
- 직접 인용문(큰따옴표 내부)
- 마크다운 목록(-, *, 1.) 구조

## 출력 규칙
- 수정된 글만 출력하고 설명·요약·메타 텍스트는 절대 금지
- 원본과 동일한 길이 유지 (95~105% 이내, 불필요한 삭제나 확장 금지)
- 변경 내역은 출력하지 않음
- 문장을 합치거나 불필요하게 단축하지 말고, AI 티 패턴만 교체"""


def humanize_korean(body_md: str, blog_id: str, title: str = "") -> str:
    """
    한국어 AI 말투를 자연스러운 글로 변환한다.
    
    - AI Writer의 generate() 함수를 재사용 (OpenAI API)
    - Fast 모드: 단일 호출 (5,000자 미만/이상 모두)
    - 실패 시 원본 body_md 그대로 반환
    - 영문 텍스트 비율 70% 이상이면 즉시 원본 반환
    - 처리 시간 로깅
    
    Args:
        body_md: AI가 생성한 마크다운 본문
        blog_id: 블로그 ID (로깅용)
        title: 글 제목 (컨텍스트 제공용)
    
    Returns:
        str: 다듬어진 본문 (실패 시 원본)
    """
    start = time.time()
    original_len = len(body_md)
    
    # ── 가드: 빈 본문 ──────────────────────────────────────────
    if not body_md or not body_md.strip():
        logger.debug(f"[HUMANIZE] {blog_id} | 빈 본문 스킵")
        return body_md
    
    # ── 영문 비율 감지: 70% 이상이면 스킵 ────────────────────────
    _hangle = len(re.findall(r'[가-힣]', body_md))
    _english = len(re.findall(r'[a-zA-Z]', body_md))
    total_letters = _hangle + _english
    if total_letters > 0 and (_english / total_letters) >= 0.70:
        elapsed = time.time() - start
        logger.info(f"[HUMANIZE] {blog_id} | 영문 70%+ 스킵 ({_english}/{total_letters}) | {elapsed:.1f}s")
        return body_md
    
    # ── User Prompt 구성 ────────────────────────────────────────
    _title_part = f"제목: {title}\n블로그: {blog_id}\n" if title else f"블로그: {blog_id}\n"
    
    user_prompt = f"""다음 한국어 블로그 글의 AI 말투를 자연스러운 한국어로 다듬어라.

{_title_part}
[원본]
{body_md}

[출력 규칙]
- 내용(사실, 수치, 링크, 마크다운 구조)은 절대 변경하지 말 것
- 마크다운 헤더(##, ###), 표, 코드블록, HTML 태그는 그대로 유지
- 어투와 문장 흐름만 자연스럽게 교체
- 원본과 동일한 길이(±10%) 유지
- 수정된 글만 출력하고 설명, 요약, 메타 텍스트 일절 금지"""
    
    # ── API 호출 ────────────────────────────────────────────────
    try:
        result = _ai_generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tier="economy"  # gpt-4o-mini, 경제적
        )
        
        if result and result.get("content"):
            raw = result["content"].strip()
            
            # ── 후처리: AI가 앞뒤에 설명을 붙인 경우 제거 ────────
            # 가장 긴 마크다운 블록 또는 원본과 유사한 첫 부분 추출
            if raw.startswith(("```", "수정", "변경", "다음", "결과", "원본")):
                # 코드블록 제거
                raw = re.sub(r'^```(?:markdown)?\s*\n?', '', raw)
                raw = re.sub(r'\n?```\s*$', '', raw)
                # '수정된 글:' 같은 접두사 제거
                raw = re.sub(r'^(수정된 글|변경|결과)[:\n]\s*', '', raw)
            
            # 길이 검증: ±15% 초과 시 원본 유지
            length_ratio = len(raw) / original_len if original_len > 0 else 1.0
            if length_ratio < 0.50:
                logger.warning(f"[HUMANIZE] {blog_id} | 결과가 너무 짧음 ({len(raw)} < {original_len*0.5:.0f}), 원본 유지")
                elapsed = time.time() - start
                logger.info(f"[HUMANIZE] {blog_id} | {original_len}자 → {original_len}자 (유지) | {elapsed:.1f}s")
                return body_md
            if length_ratio < 0.85 or length_ratio > 1.15:
                logger.warning(f"[HUMANIZE] {blog_id} | 길이 편차 초과 ({len(raw)}/{original_len}={length_ratio:.0%}), 원본 유지")
                elapsed = time.time() - start
                logger.info(f"[HUMANIZE] {blog_id} | {original_len}자 → {original_len}자 (유지) | {elapsed:.1f}s")
                return body_md
            
            elapsed = time.time() - start
            logger.info(f"[HUMANIZE] {blog_id} | {original_len}자 → {len(raw)}자 | {elapsed:.1f}s")
            return raw
        
        # 결과 없음 → 원본
        elapsed = time.time() - start
        logger.warning(f"[HUMANIZE] {blog_id} | 응답 없음, 원본 유지 | {elapsed:.1f}s")
        return body_md
    
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"[HUMANIZE] {blog_id} | 실패 (원본 유지): {e} | {elapsed:.1f}s")
        return body_md
