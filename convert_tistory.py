#!/usr/bin/env python3
"""
티스토리 HTML → Hugo Markdown 변환 스크립트
- HTML 파싱 → Markdown 변환
- 이미지 URL 추출
- aliases 자동 추가 (기존 티스토리 URL)
"""

import os
import re
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime
import html

BACKUP_DIR = '/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1'
OUTPUT_DIR = '/Users/twinssn/Desktop/rotcha-hugo/content/posts'
IMAGE_LOG = '/Users/twinssn/Desktop/rotcha-hugo/image_urls.txt'

class TistoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.date = ''
        self.category = ''
        self.content = []
        self.images = []
        self.in_title = False
        self.in_date = False
        self.in_category = False
        self.in_content = False
        self.current_tag = ''
        self.skip_tags = ['script', 'style', 'head']
        self.in_skip = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.current_tag = tag
        
        if tag in self.skip_tags:
            self.in_skip = True
            return
            
        if tag == 'h2' and 'title-article' in attrs_dict.get('class', ''):
            self.in_title = True
        elif tag == 'p' and 'date' in attrs_dict.get('class', ''):
            self.in_date = True
        elif tag == 'p' and 'category' in attrs_dict.get('class', ''):
            self.in_category = True
        elif tag == 'div' and 'contents_style' in attrs_dict.get('class', ''):
            self.in_content = True
            
        if self.in_content:
            if tag == 'img':
                src = attrs_dict.get('src', '') or attrs_dict.get('data-origin', '')
                if src:
                    self.images.append(src)
                    self.content.append(f'\n![image]({src})\n')
            elif tag == 'h2':
                self.content.append('\n## ')
            elif tag == 'h3':
                self.content.append('\n### ')
            elif tag == 'h4':
                self.content.append('\n#### ')
            elif tag == 'p':
                self.content.append('\n')
            elif tag == 'br':
                self.content.append('\n')
            elif tag == 'li':
                self.content.append('\n- ')
            elif tag == 'a':
                href = attrs_dict.get('href', '')
                self.content.append(f'[')
                self._pending_link = href
            elif tag == 'strong' or tag == 'b':
                self.content.append('**')
            elif tag == 'em' or tag == 'i':
                self.content.append('*')
                
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.in_skip = False
            return
            
        if tag == 'h2' and self.in_title:
            self.in_title = False
        elif tag == 'div' and self.in_content:
            pass
            
        if self.in_content:
            if tag == 'a' and hasattr(self, '_pending_link'):
                self.content.append(f']({self._pending_link})')
                del self._pending_link
            elif tag == 'strong' or tag == 'b':
                self.content.append('**')
            elif tag == 'em' or tag == 'i':
                self.content.append('*')
            elif tag in ['h2', 'h3', 'h4']:
                self.content.append('\n')
                
    def handle_data(self, data):
        if self.in_skip:
            return
            
        data = data.strip()
        if not data:
            return
            
        if self.in_title:
            self.title = data
        elif self.in_date:
            self.date = data
        elif self.in_category:
            self.category = data
        elif self.in_content:
            self.content.append(html.unescape(data))

def slugify(text):
    """한글 슬러그 생성"""
    text = re.sub(r'[^\w가-힣\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-').lower()

def extract_tistory_slug(filename, title):
    """티스토리 원본 슬러그 추출"""
    # 파일명에서 숫자 제거하고 슬러그 추출
    name = Path(filename).stem
    match = re.match(r'\d+-(.+)', name)
    if match:
        return match.group(1)
    return slugify(title)

def convert_html_to_md(html_path):
    """HTML 파일을 Markdown으로 변환"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(html_path, 'r', encoding='cp949') as f:
                content = f.read()
        except:
            print(f"❌ 인코딩 오류: {html_path}")
            return None, []
    
    parser = TistoryParser()
    try:
        parser.feed(content)
    except:
        print(f"❌ 파싱 오류: {html_path}")
        return None, []
    
    if not parser.title:
        # title 태그에서 추출 시도
        title_match = re.search(r'<title>(.+?)</title>', content)
        if title_match:
            parser.title = title_match.group(1)
        else:
            parser.title = Path(html_path).stem
    
    if not parser.date:
        # 파일 수정 시간 사용
        mtime = os.path.getmtime(html_path)
        parser.date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    else:
        # 날짜 형식 정리
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', parser.date)
        if date_match:
            parser.date = date_match.group(1)
        else:
            parser.date = datetime.now().strftime('%Y-%m-%d')
    
    # 티스토리 원본 슬러그
    tistory_slug = extract_tistory_slug(html_path, parser.title)
    
    # Hugo 파일명용 슬러그
    hugo_slug = slugify(parser.title)[:50]
    
    # Markdown 생성
    md_content = f"""---
title: "{parser.title.replace('"', "'")}"
date: {parser.date}
draft: false
categories: ["{parser.category or '미분류'}"]
aliases:
  - /entry/{tistory_slug}/
---

{''.join(parser.content)}
"""
    
    return {
        'content': md_content,
        'slug': hugo_slug,
        'date': parser.date,
        'images': parser.images
    }, parser.images

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_images = []
    converted = 0
    failed = 0
    
    # 모든 HTML 파일 찾기
    html_files = list(Path(BACKUP_DIR).rglob('*.html'))
    print(f"총 {len(html_files)}개 HTML 파일 발견")
    
    for html_path in html_files:
        result, images = convert_html_to_md(str(html_path))
        
        if result:
            # 파일명 생성
            filename = f"{result['date']}-{result['slug']}.md"
            output_path = os.path.join(OUTPUT_DIR, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result['content'])
            
            all_images.extend(images)
            converted += 1
            print(f"✅ {filename}")
        else:
            failed += 1
    
    # 이미지 URL 저장
    with open(IMAGE_LOG, 'w', encoding='utf-8') as f:
        for img in set(all_images):
            f.write(img + '\n')
    
    print(f"\n완료! 변환: {converted}개, 실패: {failed}개")
    print(f"이미지 URL: {IMAGE_LOG} ({len(set(all_images))}개)")

if __name__ == '__main__':
    main()
