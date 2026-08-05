#!/usr/bin/env python3
"""
LLM 응답 파서 및 오염 방어 모듈
finance-hugo에서 정립된 규칙을 적용한 명시적 출력 계약 구현
"""

import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# LLM 사고과정 누수 시그니처 (다국어 확장)
THINKING_PATTERNS = [
    # 한국어 사고과정
    r'사용자가 제공한 데이터',
    r'절대 .* 말라고 했습니다',
    r'초안:',
    r'이제 .* 작성',
    r'H2-\d',
    r'문장 수:',
    r'주의:',
    r'규칙:',
    r'~해야 합니다\.$',
    r'생각:', 
    r'추론:',
    r'계획:',
    r'다음 단계:',
    # 영어 사고과정 누수
    r'(?:^|\n)\s*(?:The user has provided|Let me re-?[Rr]ead|Wait,|we need to|Let me\b|I should\b|Actually,|First,)',
    # 프롬프트 지시문 노출
    r'bold-list로 정리|테이블 금지|1~2문장으로 소개|H2 없이|최소 \d+문장|~를 명시해야|금지 표현|체크포인트|구조:|도입부 \(',
    # thinking/reasoning 태그 잔재
    r'<think(?:ing)?>|</think(?:ing)?>|<reasoning>|</reasoning>',
]

# CJK 누수 — 한국어 블로그에서 중국어 간체 키워드 등장 (instruction leak)
CJK_INSTRUCTION_LEAK = [
    r'我们根据|需要遵守|禁止词汇|注意所有|根据要求',
    r'应当|必须遵守|不得|禁止|规则如下',
]

# 금지어 역노출 — 프롬프트가 금지한 표현이 본문에 등장
FORBIDDEN_WORD_REVERSE = [
    r'바랍니다', r'되시길', r'있으시', r'마무리하며', r'마치며',
    r'정리하며', r'알아보겠습니다', r'과연', r'놀랍게도', r'충격적으로',
]


def _strip_thinking_tags(content: str) -> str:
    """LLM 응답에서 thinking/reasoning 태그를 구조적으로 제거"""
    if not content:
        return content
    # <thinking>...</thinking> 제거
    content = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', content, flags=re.DOTALL)
    # <reasoning>...</reasoning> 제거
    content = re.sub(r'<reasoning>.*?</reasoning>', '', content, flags=re.DOTALL)
    # <chain-of-thought>...</chain-of-thought> 제거
    content = re.sub(r'<chain[- ]of[- ]thought>.*?</chain[- ]of[- ]thought>', '', content, flags=re.DOTALL)
    return content.strip()


def _check_multilingual_leak(content: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    다국어 누수 검사 (언어 불문)
    Returns: (has_leak, pattern_name, matched_text)
    """
    # 한국어 + 영어 사고과정 + 프롬프트 지시문
    for pattern in THINKING_PATTERNS:
        m = re.search(pattern, content)
        if m:
            return True, "thinking_leak", m.group()[:80]
    
    # CJK instruction leak (중국어 지시문 누수)
    for pattern in CJK_INSTRUCTION_LEAK:
        m = re.search(pattern, content)
        if m:
            return True, "cjk_instruction_leak", m.group()[:80]
    
    return False, None, None

def _parse_structured_response(content: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    명시적 출력 계약 파서: TITLE:/BODY: 마크다운 태그 추출
    
    Returns:
        Tuple[title, body, fallback_used]: 
        - title: 추출된 제목
        - body: 추출된 본문 
        - fallback_used: 폴백 사용 여부
    """
    if not content:
        return None, None, False
    
    content = content.strip()
    
    # 1. 명시적 태그 파싱 (우선순위 최상) - 더 유연한 매칭
    if content.startswith('TITLE:'):
        # Case 1: TITLE: ... \n\n BODY: ... format
        body_marker = '\n\nBODY:'
        title_end = content.find(body_marker)
        if title_end != -1:
            title = content[6:title_end].strip()
            body = content[title_end + len(body_marker):].strip()
            logger.info("[ai_writer] 명시적 TITLE:/BODY: 태그 파싱 성공 (표준)")
            return title, body, False
        
        # Case 2: TITLE: ... \nBODY: ... format
        body_marker = '\nBODY:'
        title_end = content.find(body_marker)
        if title_end != -1:
            title = content[6:title_end].strip()
            body = content[title_end + len(body_marker):].strip()
            logger.info("[ai_writer] 명시적 TITLE:/BODY: 태그 파싱 성공 (간결)")
            return title, body, False
        
        # Case 3: TITLE: ... (단독으로 존재하고 그 뒤 내용은 전부 본문)
        lines = content.split('\n')
        title_line = lines[0]
        title = title_line[6:].strip()  # "TITLE:" 제거
        
        # TITLE: 다음 줄부터가 모두 본문 (첫 번째 H2 이전까지)
        body_lines = []
        in_body = False
        for line in lines[1:]:
            if line.strip().startswith('## ') and not in_body:
                # 첫 번째 H2 이전까지는 제목의 일부로 간주
                if body_lines:  # 이미 본문이 시작된 경우
                    body_lines.append(line)
                in_body = True
            else:
                body_lines.append(line)
        
        body = '\n'.join(body_lines).strip()
        logger.info("[ai_writer] 명시적 TITLE:/BODY: 태그 파싱 성공 (유연)")
        return title, body, False
    
    # 2. H1 제목 추출 (대체)
    lines = content.split('\n')
    title = None
    body_lines = []
    
    # 첫 번째 H1 제목 찾기
    for i, line in enumerate(lines):
        if line.strip().startswith('# '):
            title = line[2:].strip()  # "# " 제거
            # H1 이후부터 본문 시작
            body_lines = lines[i+1:]
            break
    
    if title:
        # H1 이후 첫 비어있지 않은 라인부터 본문 시작
        filtered_body = []
        in_body = False
        for line in body_lines:
            if line.strip():
                in_body = True
                filtered_body.append(line)
            elif in_body:
                # 빈 줄은 유지하되, 연속 빈 줄은 제거
                if filtered_body and filtered_body[-1].strip():
                    filtered_body.append('')
        
        body = '\n'.join(filtered_body).strip()
        logger.info("[ai_writer] H1 제목 추출 파싱 성공")
        return title, body, False
    
    # 3. 마크다운 폴백 파싱
    # 첫 번째 H2 이전 내용을 제목으로 추정
    lines = content.split('\n')
    title_lines = []
    body_lines = []
    found_h2 = False
    
    for line in lines:
        if line.strip().startswith('## '):
            found_h2 = True
            break
        elif not found_h2:
            title_lines.append(line)
        else:
            body_lines.append(line)
    
    # 첫 번째 H2 이전 텍스트가 3줄 이내이면 제목으로 사용
    if len([l for l in title_lines if l.strip()]) <= 3 and found_h2:
        title = '\n'.join(title_lines).strip()
        body = '\n'.join(body_lines).strip()
        logger.info("[ai_writer] 마크다운 H2 기반 폴백 파싱 성공")
        return title, body, True
    
    # 4. 완전한 폴백 - 전체 content를 본문으로 사용
    logger.warning("[ai_writer] 폴백 진입: 전체 content를 본문으로 사용")
    return None, content, True


def _check_thinking_leak(content: str) -> Tuple[bool, Optional[str]]:
    """
    LLM 사고과정 누수 검사 (다국어 확장)
    
    Returns:
        Tuple[has_leak, leak_pattern]: 누수 여부와 패턴
    """
    has_leak, pattern_name, matched = _check_multilingual_leak(content)
    if has_leak:
        logger.warning(f"[ai_writer] 사고과정 누수 감지 ({pattern_name}): {matched}")
        return True, f"{pattern_name}:{matched}"
    
    return False, None


def _clean_thinking_content(content: str) -> str:
    """사고과정 누수 내용 정리"""
    # 정확한 패턴 매칭을 위한 개선된 정리
    cleanup_patterns = [
        (r'사용자가 제공한 데이터\s*', ''),
        (r'절대 .* 말라고 했습니다\s*', ''),
        (r'초안:\s*', ''),
        (r'이제 .* 작성\s*', ''),
        (r'이제 작성 시작\s*', ''),
        (r'이제 시작\s*', ''),
        (r'H2-\d\s*', ''),
        (r'문장 수:\s*\d+\s*', ''),
        (r'주의:\s*', ''),
        (r'규칙:\s*', ''),
        (r'규칙\s*', ''),
        (r'~해야 합니다\.\s*', ''),
        (r'~해야 합니다\s*', ''),
        (r'생각:\s*', ''),
        (r'추론:\s*', ''),
        (r'계획:\s*', ''),
        (r'다음 단계:\s*', ''),
    ]
    
    # 패턴 반복 적용 (여러 번 실행하여 중첩 패턴 제거)
    for pattern, replacement in cleanup_patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # 빈 줄 정리
    lines = content.split('\n')
    cleaned_lines = []
    for i, line in enumerate(lines):
        # 빈 줄이 아닌 경우 또는 이전 줄도 빈 줄이 아닌 경우
        if line.strip() or (i > 0 and lines[i-1].strip()):
            cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines).strip()
    
    # 연속 빈 줄 정리
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    return content.strip()


def parse_ai_response(content: str, is_fallback: bool = False) -> Dict:
    """
    AI 응답 파싱 및 오염 검증 메인 함수
    
    Args:
        content: 원본 AI 응답
        is_fallback: 폴백 응답 여부
        
    Returns:
        Dict: {
            'title': str,           # 추출된 제목
            'body': str,            # 정리된 본문
            'is_fallback': bool,    # 폴백 사용 여부
            'has_thinking_leak': bool,  # 사고과정 누수 여부
            'leak_pattern': str,    # 누수 패턴 (있을 경우)
            'should_fail': bool     # 발행 차단 여부
        }
    """
    result = {
        'is_fallback': False,
        'has_thinking_leak': False,
        'leak_pattern': None,
        'should_fail': False
    }
    
    # 1. 명시적 출력 계약 파싱
    title, body, fallback_used = _parse_structured_response(content)
    result['is_fallback'] = fallback_used
    
    if not title or not body:
        # 파싱 실패 → 전체 content를 본문으로 사용 (기존 로직 유지)
        title = None
        body = content
        logger.warning("[ai_writer] 파싱 실패 - 전체 content를 본문으로 사용")
    
    # 2. 사고과정 누수 검사
    has_leak, leak_pattern = _check_thinking_leak(body)
    result['has_thinking_leak'] = has_leak
    result['leak_pattern'] = leak_pattern
    
    # 3. 오염 방어 로직
    if has_leak:
        logger.error("[ai_writer] 사고과정 누수 발견 → 발행 차단")
        result['should_fail'] = True
        
        # 만약 fallback이 아니면 정리 시도
        if not fallback_used:
            body = _clean_thinking_content(body)
            logger.info("[ai_writer] 폴백이 아닌 경우 사고과정 정리 시도")
        else:
            logger.error("[ai_writer] 폴백 응답에 사고과정 누수 → 무조건 차단")
    
    # 4. 제목 정리 (생략 가능)
    # if title:
    #     title = title.strip()
    #     if len(title) > 80:
    #         title = title[:77] + "..."
    
    result['title'] = title
    result['body'] = body
    
    logger.info(f"[ai_writer] 파싱 결과: fallback={fallback_used}, leak={has_leak}, fail={result['should_fail']}")
    
    return result