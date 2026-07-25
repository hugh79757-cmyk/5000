#!/usr/bin/env python3
"""
Phase 44 Quality Verification Script
6개 블로그(블로거1 + 휴고5) 전수 품질 검증

Usage:
    python3 scripts/verify_quality.py --all-blogs --output phase-44-full-audit/QUALITY-AUDIT-REPORT.md
    python3 scripts/verify_quality.py --blog travel-hugo --output phase-44-full-audit/travel-hugo-report.md
"""

import argparse
import os
import re
import sys
import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

# 5000 프로젝트 루트 추가
sys.path.insert(0, '/Users/twinssn/Projects/5000')


@dataclass
class BlogCriteria:
    """블로그별 품질 기준"""
    blog_id: str
    name: str
    type: str  # 'hugo' or 'blogger'
    path: str
    pipeline: str
    fetcher: str
    prompt_id: str
    
    # 전역 기준
    min_body_length: int = 2500
    title_gen_success_rate: float = 1.0
    hallucination_tolerance: int = 0
    empty_field_mentions: int = 0
    title_body_consistency: bool = True
    
    # 구조
    min_h2: int = 3
    max_h2: int = 4
    min_h3: int = 3
    max_h3: int = 4
    min_sentences_per_h3: int = 6
    
    # 블로그별 특화
    required_keywords_any: list = field(default_factory=list)
    min_required_keywords: int = 0
    required_data_fields: list = field(default_factory=list)
    required_body_elements: list = field(default_factory=list)
    required_context_words_any: list = field(default_factory=list)
    min_context_words: int = 0
    brand_keywords_any: list = field(default_factory=list)
    min_brand_keywords: int = 0
    min_heritage_sites: int = 0
    min_course_sections: int = 0
    course_name_pattern: str = ""
    price_format_check: bool = False
    forbidden_price_patterns: list = field(default_factory=list)
    forbidden_words: list = field(default_factory=list)
    forbidden_patterns: list = field(default_factory=list)
    forbidden_movement_patterns: list = field(default_factory=list)
    use_global_only: bool = False
    recommended_replacement: str = ""


@dataclass
class VerificationResult:
    """단일 포스트 검증 결과"""
    blog_id: str
    post_path: str
    post_title: str
    status: str  # PASS, FAIL, NEEDS_REVIEW
    checks: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class QualityVerifier:
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.global_criteria = self.config.get('global_criteria', {})
        self.blogs_config = self.config.get('blogs', {})
        self.execution_config = self.config.get('execution', {})
        self.output_config = self.config.get('output', {})
        
        # 블로그별 기준 객체 생성
        self.blog_criteria = {}
        for blog_id, bc in self.blogs_config.items():
            self.blog_criteria[blog_id] = BlogCriteria(
                blog_id=blog_id,
                name=bc.get('name', blog_id),
                type=bc.get('type', 'hugo'),
                path=bc.get('path', ''),
                pipeline=bc.get('pipeline', ''),
                fetcher=bc.get('fetcher', ''),
                prompt_id=bc.get('prompt_id', ''),
                min_body_length=self.global_criteria.get('min_body_length', 2500),
                title_gen_success_rate=self.global_criteria.get('title_generation_success_rate', 1.0),
                hallucination_tolerance=self.global_criteria.get('hallucination_tolerance', 0),
                empty_field_mentions=self.global_criteria.get('empty_field_mentions', 0),
                title_body_consistency=self.global_criteria.get('title_body_consistency', True),
                min_h2=self.global_criteria.get('structure', {}).get('min_h2', 3),
                max_h2=self.global_criteria.get('structure', {}).get('max_h2', 4),
                min_h3=self.global_criteria.get('structure', {}).get('min_h3', 3),
                max_h3=self.global_criteria.get('structure', {}).get('max_h3', 4),
                min_sentences_per_h3=self.global_criteria.get('structure', {}).get('min_sentences_per_h3', 6),
                required_keywords_any=bc.get('required_keywords_any', []),
                min_required_keywords=bc.get('min_required_keywords', 0),
                required_data_fields=bc.get('required_data_fields', []),
                required_body_elements=bc.get('required_body_elements', []),
                required_context_words_any=bc.get('required_context_words_any', []),
                min_context_words=bc.get('min_context_words', 0),
                brand_keywords_any=bc.get('brand_keywords_any', []),
                min_brand_keywords=bc.get('min_brand_keywords', 0),
                min_heritage_sites=bc.get('min_heritage_sites', 0),
                min_course_sections=bc.get('min_course_sections', 0),
                course_name_pattern=bc.get('course_name_pattern', ''),
                price_format_check=bc.get('price_format_check', False),
                forbidden_price_patterns=bc.get('forbidden_price_patterns', []),
                forbidden_words=bc.get('forbidden_words', []),
                forbidden_patterns=bc.get('forbidden_patterns', []),
                forbidden_movement_patterns=bc.get('forbidden_movement_patterns', []),
                use_global_only=bc.get('use_global_only', False),
                recommended_replacement=bc.get('recommended_replacement', ''),
            )
    
    def parse_post(self, post_path: Path) -> dict:
        """Hugo 포스트 파일 파싱 (frontmatter + 본문)"""
        content = post_path.read_text(encoding='utf-8')
        
        # Frontmatter 파싱 (--- 사이의 내용)
        frontmatter = {}
        body = content
        
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except yaml.YAMLError:
                    pass
        
        return {
            'frontmatter': frontmatter,
            'body': body,
            'title': frontmatter.get('title', ''),
            'path': str(post_path)
        }
    
    def count_korean_sentences(self, text: str) -> int:
        """한국어 문장 수 계산 (간단 버전)"""
        # 마침표, 물음표, 느낌표 기준
        sentences = re.split(r'[.!?]+\s*', text)
        return len([s for s in sentences if s.strip()])
    
    def extract_h2_sections(self, body: str) -> list:
        """H2 섹션 추출 (## 로 시작)"""
        return [h.strip() for h in body.split('##') if h.strip() and len(h.strip()) > 10]
    
    def extract_h3_sections(self, body: str) -> list:
        """H3 섹션 추출 (### 로 시작)"""
        return [h.strip() for h in body.split('###') if h.strip() and len(h.strip()) > 10]
    
    def extract_numbers_from_title(self, title: str) -> list:
        """타이틀에서 숫자 추출"""
        return [int(n) for n in re.findall(r'\b(\d+)\b', title)]
    
    def verify_post(self, blog_id: str, post_data: dict) -> VerificationResult:
        """단일 포스트 검증"""
        criteria = self.blog_criteria.get(blog_id)
        if not criteria:
            return VerificationResult(
                blog_id=blog_id,
                post_path=post_data['path'],
                post_title=post_data['title'],
                status='NEEDS_REVIEW',
                errors=[f'Unknown blog_id: {blog_id}']
            )
        
        body = post_data['body']
        title = post_data['title']
        frontmatter = post_data['frontmatter']
        
        checks = {}
        errors = []
        warnings = []
        
        # 1. 본문 길이 검증
        body_len = len(body)
        checks['body_length'] = body_len
        if body_len < criteria.min_body_length:
            errors.append(f'본문 길이 미달: {body_len} < {criteria.min_body_length}')
        
        # 2. 타이틀 존재 검증
        checks['title_exists'] = bool(title)
        if not title:
            errors.append('타이틀 없음')
        
        # 3. 금지어 검증 (전역 + 블로그별)
        all_forbidden = set(criteria.forbidden_words)
        forbidden_found = [w for w in all_forbidden if w in body]
        checks['forbidden_words'] = forbidden_found
        if forbidden_found:
            errors.append(f'금지어 발견: {forbidden_found}')
        
        # 4. 금지 패턴 검증
        pattern_violations = []
        for pattern in criteria.forbidden_patterns:
            if re.search(pattern, body, re.IGNORECASE):
                pattern_violations.append(pattern)
        checks['forbidden_patterns'] = pattern_violations
        if pattern_violations:
            errors.append(f'금지 패턴 위반: {pattern_violations}')
        
        # 5. 이동시간 패턴 검증 (코스 블로그)
        movement_violations = []
        for pattern in criteria.forbidden_movement_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                movement_violations.extend(matches)
        checks['movement_time_violations'] = movement_violations
        if movement_violations:
            errors.append(f'이동시간 패턴 위반: {movement_violations[:5]}...' if len(movement_violations) > 5 else f'이동시간 패턴 위반: {movement_violations}')
        
        # 6. 필수 키워드 검증 (캠핑 등)
        if criteria.required_keywords_any:
            found_keywords = [kw for kw in criteria.required_keywords_any if kw in body]
            checks['required_keywords_found'] = found_keywords
            if len(found_keywords) < criteria.min_required_keywords:
                errors.append(f'필수 키워드 부족: {len(found_keywords)}/{criteria.min_required_keywords} (발견: {found_keywords})')
        
        # 6b. 브랜드 키워드 검증
        if criteria.brand_keywords_any:
            found_brands = [kw for kw in criteria.brand_keywords_any if kw in body]
            checks['brand_keywords_found'] = found_brands
            if len(found_brands) < criteria.min_brand_keywords:
                errors.append(f'브랜드 키워드 부족: {len(found_brands)}/{criteria.min_brand_keywords}')
        
        # 7. 필수 데이터 필드 검증 (frontmatter)
        missing_data_fields = [f for f in criteria.required_data_fields if f not in frontmatter or not frontmatter[f]]
        checks['missing_data_fields'] = missing_data_fields
        if missing_data_fields:
            warnings.append(f'Frontmatter 필수 필드 누락: {missing_data_fields}')
        
        # 8. 필수 본문 요소 검증
        missing_body_elements = [e for e in criteria.required_body_elements if e not in body]
        checks['missing_body_elements'] = missing_body_elements
        if missing_body_elements:
            errors.append(f'본문 필수 요소 누락: {missing_body_elements}')
        
        # 9. 컨텍스트 연결 단어 (문화유산)
        if criteria.required_context_words_any:
            found_context = [w for w in criteria.required_context_words_any if w in body]
            checks['context_words_found'] = found_context
            if len(found_context) < criteria.min_context_words:
                errors.append(f'컨텍스트 연결 단어 부족: {len(found_context)}/{criteria.min_context_words}')
        
        # 10. 문화유산 사이트 수 (H3 섹션 수로 근사)
        if criteria.min_heritage_sites > 0:
            h3_sections = self.extract_h3_sections(body)
            checks['heritage_h3_count'] = len(h3_sections)
            if len(h3_sections) < criteria.min_heritage_sites:
                errors.append(f'문화유산 H3 섹션 부족: {len(h3_sections)} < {criteria.min_heritage_sites}')
        
        # 11. 코스 섹션 검증
        if criteria.min_course_sections > 0:
            h3_sections = self.extract_h3_sections(body)
            course_sections = [h for h in h3_sections if re.match(criteria.course_name_pattern, h.split('\n')[0])]
            checks['course_sections'] = len(course_sections)
            if len(course_sections) < criteria.min_course_sections:
                errors.append(f'코스 섹션 부족: {len(course_sections)} < {criteria.min_course_sections}')
        
        # 12. 가격 포맷 검증 (맛집)
        if criteria.price_format_check:
            price_violations = []
            for pattern in criteria.forbidden_price_patterns:
                if re.search(pattern, body):
                    price_violations.append(pattern)
            checks['price_format_violations'] = price_violations
            if price_violations:
                errors.append(f'가격 포맷 위반: {price_violations}')
        
        # 13. 타이틀-본문 일관성 (숫자 매칭)
        if criteria.title_body_consistency and title:
            title_numbers = self.extract_numbers_from_title(title)
            if title_numbers:
                h2_sections = self.extract_h2_sections(body)
                h3_sections = self.extract_h3_sections(body)
                # 타이틀 숫자 중 하나가 H2 또는 H3 섹션 수와 일치하는지 확인
                matched = any(n in [len(h2_sections), len(h3_sections)] for n in title_numbers)
                checks['title_body_numbers_match'] = matched
                checks['title_numbers'] = title_numbers
                checks['h2_count'] = len(h2_sections)
                checks['h3_count'] = len(h3_sections)
                if not matched:
                    errors.append(f'타이틀-본문 숫자 불일치: 타이틀={title_numbers}, H2={len(h2_sections)}, H3={len(h3_sections)}')
            else:
                checks['title_body_numbers_match'] = True  # 숫자 없으면 패스
        
        # 14. 구조 검증 (H2/H3 개수)
        h2_sections = self.extract_h2_sections(body)
        h3_sections = self.extract_h3_sections(body)
        checks['h2_count'] = len(h2_sections)
        checks['h3_count'] = len(h3_sections)
        
        if len(h2_sections) < criteria.min_h2 or len(h2_sections) > criteria.max_h2:
            warnings.append(f'H2 섹션 수 범위 벗어남: {len(h2_sections)} (기대: {criteria.min_h2}-{criteria.max_h2})')
        if len(h3_sections) < criteria.min_h3 or len(h3_sections) > criteria.max_h3:
            warnings.append(f'H3 섹션 수 범위 벗어남: {len(h3_sections)} (기대: {criteria.min_h3}-{criteria.max_h3})')
        
        # 15. H3당 문장 수 검증
        short_h3 = []
        for h3 in h3_sections:
            sentences = self.count_korean_sentences(h3)
            if sentences < criteria.min_sentences_per_h3:
                short_h3.append(f'{sentences}문장')
        checks['short_h3_sections'] = len(short_h3)
        if short_h3:
            warnings.append(f'H3 최소 문장 수 미달: {len(short_h3)}개 섹션 ({", ".join(short_h3[:3])}...)')
        
        # 16. 빈/0값 필드 언급 검증 (휴리스틱)
        empty_mentions = []
        zero_patterns = [r'0개', r'0명', r'없습니다', r'제공되지 않습니다', r'정보 없음', r'미정']
        for pattern in zero_patterns:
            if re.search(pattern, body):
                empty_mentions.append(pattern)
        checks['empty_field_mentions'] = empty_mentions
        if empty_mentions:
            warnings.append(f'빈/0값 필드 언급 가능성: {empty_mentions}')
        
        # 최종 상태 결정
        if errors:
            status = 'FAIL'
        elif warnings:
            status = 'NEEDS_REVIEW'
        else:
            status = 'PASS'
        
        return VerificationResult(
            blog_id=blog_id,
            post_path=post_data['path'],
            post_title=title,
            status=status,
            checks=checks,
            errors=errors,
            warnings=warnings,
            metadata={
                'body_length': body_len,
                'frontmatter_keys': list(frontmatter.keys()),
                'h2_count': len(h2_sections),
                'h3_count': len(h3_sections),
            }
        )
    
    def verify_blog(self, blog_id: str) -> list:
        """블로그 전체 포스트 검증"""
        criteria = self.blog_criteria.get(blog_id)
        if not criteria:
            return []
        
        if criteria.type == 'blogger':
            # Blogger는 별도 처리 (TODO)
            print(f'  ⚠️  {blog_id} (blogger): Blogger API 연동 필요, 스킵')
            return []
        
        post_dir = Path(criteria.path)
        if not post_dir.exists():
            print(f'  ❌ {blog_id}: 경로 없음 - {post_dir}')
            return []
        
        # index.md 파일들 찾기
        post_files = list(post_dir.rglob('index.md'))
        print(f'  📁 {blog_id}: {len(post_files)}개 포스트 발견')
        
        results = []
        for post_file in post_files:
            post_data = self.parse_post(post_file)
            result = self.verify_post(blog_id, post_data)
            results.append(result)
        
        return results
    
    def verify_all_blogs(self) -> dict:
        """모든 블로그 검증 실행"""
        all_results = {}
        
        for blog_id in self.blog_criteria.keys():
            print(f'\n🔍 검증 중: {blog_id} ({self.blog_criteria[blog_id].name})')
            results = self.verify_blog(blog_id)
            all_results[blog_id] = results
            
            # 요약 출력
            pass_count = sum(1 for r in results if r.status == 'PASS')
            fail_count = sum(1 for r in results if r.status == 'FAIL')
            review_count = sum(1 for r in results if r.status == 'NEEDS_REVIEW')
            print(f'  결과: PASS={pass_count}, FAIL={fail_count}, NEEDS_REVIEW={review_count}')
        
        return all_results
    
    def generate_report(self, all_results: dict, output_path: str):
        """검증 리포트 생성 (Markdown)"""
        lines = [
            '# Phase 44 품질 전수조사 리포트',
            f'**생성일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            f'**대상**: 6개 블로그 (블로거1 + 휴고5)',
            '',
            '---',
            '',
            '## 📊 전체 요약',
            ''
        ]
        
        # 전체 통계
        total_pass = 0
        total_fail = 0
        total_review = 0
        total_posts = 0
        
        blog_summaries = []
        for blog_id, results in all_results.items():
            criteria = self.blog_criteria.get(blog_id, {})
            name = criteria.name if hasattr(criteria, 'name') else blog_id
            
            pass_c = sum(1 for r in results if r.status == 'PASS')
            fail_c = sum(1 for r in results if r.status == 'FAIL')
            review_c = sum(1 for r in results if r.status == 'NEEDS_REVIEW')
            total_c = len(results)
            
            total_pass += pass_c
            total_fail += fail_c
            total_review += review_c
            total_posts += total_c
            
            pass_rate = (pass_c / total_c * 100) if total_c > 0 else 0
            
            blog_summaries.append({
                'blog_id': blog_id,
                'name': name,
                'total': total_c,
                'pass': pass_c,
                'fail': fail_c,
                'review': review_c,
                'pass_rate': pass_rate
            })
            
            lines.append(f'| {blog_id} | {name} | {total_c} | {pass_c} | {fail_c} | {review_c} | {pass_rate:.1f}% |')
        
        # 전체 요약 테이블
        lines.insert(-1, '| 블로그ID | 블로그명 | 전체 | PASS | FAIL | NEEDS_REVIEW | PASS율 |')
        lines.insert(-1, '|----------|----------|------|------|------|--------------|--------|')
        
        overall_rate = (total_pass / total_posts * 100) if total_posts > 0 else 0
        lines.append('')
        lines.append(f'**전체 통계**: {total_posts}개 포스트, PASS {total_pass}개, FAIL {total_fail}개, NEEDS_REVIEW {total_review}개')
        lines.append(f'**전체 PASS율**: {overall_rate:.1f}%')
        lines.append('')
        lines.append('---')
        lines.append('')
        
        # 블로그별 상세
        for blog_id, results in all_results.items():
            criteria = self.blog_criteria.get(blog_id, {})
            name = criteria.name if hasattr(criteria, 'name') else blog_id
            
            lines.append(f'## {blog_id} — {name}')
            lines.append('')
            
            fail_results = [r for r in results if r.status == 'FAIL']
            review_results = [r for r in results if r.status == 'NEEDS_REVIEW']
            
            if fail_results:
                lines.append(f'### ❌ FAIL ({len(fail_results)}개)')
                lines.append('')
                for r in fail_results[:10]:  # 상위 10개만
                    lines.append(f'- **{r.post_title[:50]}** (`{Path(r.post_path).parent.name}`)')
                    for err in r.errors[:3]:
                        lines.append(f'  - {err}')
                    lines.append('')
            
            if review_results:
                lines.append(f'### ⚠️ NEEDS_REVIEW ({len(review_results)}개)')
                lines.append('')
                for r in review_results[:10]:
                    lines.append(f'- **{r.post_title[:50]}** (`{Path(r.post_path).parent.name}`)')
                    for warn in r.warnings[:3]:
                        lines.append(f'  - {warn}')
                    lines.append('')
            
            pass_results = [r for r in results if r.status == 'PASS']
            if pass_results:
                lines.append(f'### ✅ PASS ({len(pass_results)}개) — 목록 생략')
                lines.append('')
            
            lines.append('---')
            lines.append('')
        
        # FAIL 상세 목록 (전체)
        all_fails = []
        for blog_id, results in all_results.items():
            for r in results:
                if r.status == 'FAIL':
                    all_fails.append(r)
        
        if all_fails:
            lines.append('## 🔴 전체 FAIL 상세 목록')
            lines.append('')
            for r in all_fails:
                lines.append(f'### {r.blog_id} — {r.post_title[:60]}')
                lines.append(f'- 경로: `{r.post_path}`')
                lines.append(f'- 본문: {r.metadata.get("body_length", 0)}자')
                lines.append(f'- H2: {r.metadata.get("h2_count", 0)}, H3: {r.metadata.get("h3_count", 0)}')
                lines.append('')
                for err in r.errors:
                    lines.append(f'  - {err}')
                lines.append('')
        
        # 저장
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text('\n'.join(lines), encoding='utf-8')
        print(f'\n📄 리포트 저장: {output_path}')
    
    def generate_json_summary(self, all_results: dict, output_path: str):
        """JSON 요약 저장"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'phase': 44,
            'total_blogs': len(all_results),
            'total_posts': sum(len(r) for r in all_results.values()),
            'by_blog': {},
            'by_status': {'PASS': 0, 'FAIL': 0, 'NEEDS_REVIEW': 0}
        }
        
        for blog_id, results in all_results.items():
            pass_c = sum(1 for r in results if r.status == 'PASS')
            fail_c = sum(1 for r in results if r.status == 'FAIL')
            review_c = sum(1 for r in results if r.status == 'NEEDS_REVIEW')
            
            summary['by_blog'][blog_id] = {
                'total': len(results),
                'PASS': pass_c,
                'FAIL': fail_c,
                'NEEDS_REVIEW': review_c,
                'pass_rate': pass_c / len(results) * 100 if results else 0
            }
            summary['by_status']['PASS'] += pass_c
            summary['by_status']['FAIL'] += fail_c
            summary['by_status']['NEEDS_REVIEW'] += review_c
        
        summary['overall_pass_rate'] = (
            summary['by_status']['PASS'] / summary['total_posts'] * 100
            if summary['total_posts'] > 0 else 0
        )
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'📄 JSON 요약 저장: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Phase 44 품질 검증')
    parser.add_argument('--config', default='config/quality_checklist.yaml', help='품질 기준 YAML 경로')
    parser.add_argument('--blog', help='특정 블로그만 검증 (blog_id)')
    parser.add_argument('--all-blogs', action='store_true', help='모든 블로그 검증')
    parser.add_argument('--output', default='phase-44-full-audit/QUALITY-AUDIT-REPORT.md', help='리포트 출력 경로')
    parser.add_argument('--json-output', default='phase-44-full-audit/AUDIT-SUMMARY.json', help='JSON 요약 출력 경로')
    
    args = parser.parse_args()
    
    if not args.all_blogs and not args.blog:
        parser.error('--all-blogs 또는 --blog 중 하나는 필수입니다')
    
    print('=' * 60)
    print('Phase 44 품질 전수조사 시작')
    print('=' * 60)
    
    verifier = QualityVerifier(args.config)
    
    if args.all_blogs:
        all_results = verifier.verify_all_blogs()
    else:
        all_results = {args.blog: verifier.verify_blog(args.blog)}
    
    # 리포트 생성
    verifier.generate_report(all_results, args.output)
    verifier.generate_json_summary(all_results, args.json_output)
    
    # 최종 요약
    total_pass = sum(1 for results in all_results.values() for r in results if r.status == 'PASS')
    total_fail = sum(1 for results in all_results.values() for r in results if r.status == 'FAIL')
    total_review = sum(1 for results in all_results.values() for r in results if r.status == 'NEEDS_REVIEW')
    total_posts = sum(len(results) for results in all_results.values())
    
    print('\n' + '=' * 60)
    print('검증 완료')
    print('=' * 60)
    print(f'전체: {total_posts}개 포스트')
    print(f'✅ PASS: {total_pass} ({total_pass/total_posts*100:.1f}%)')
    print(f'❌ FAIL: {total_fail} ({total_fail/total_posts*100:.1f}%)')
    print(f'⚠️  NEEDS_REVIEW: {total_review} ({total_review/total_posts*100:.1f}%)')
    print(f'📄 리포트: {args.output}')
    print(f'📄 JSON: {args.json_output}')
    
    # 종료 코드 (FAIL 있으면 1)
    sys.exit(1 if total_fail > 0 else 0)


if __name__ == '__main__':
    main()