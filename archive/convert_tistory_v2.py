#!/usr/bin/env python3
"""
티스토리 HTML → Hugo Markdown 변환 스크립트 v2
BeautifulSoup 사용
"""

import os
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import html

BACKUP_DIR = '/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1'
OUTPUT_DIR = '/Users/twinssn/Desktop/rotcha-hugo/content/posts'
IMAGE_LOG = '/Users/twinssn/Desktop/rotcha-hugo/image_urls.txt'

def slugify(text):
    text = re.sub(r'[^\w가-힣\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-').lower()[:50]

def html_to_markdown(element):
    """HTML 요소를 Markdown으로 변환"""
    md = []
    
    for el in element.descendants:
        if el.name is None:  # 텍스트 노드
            text = str(el).strip()
            if text and text != '\xa0':
                md.append(text)
        elif el.name == 'h2':
            text = el.get_text(strip=True)
            if text:
                md.append(f'\n\n## {text}\n\n')
        elif el.name == 'h3':
            text = el.get_text(strip=True)
            if text:
                md.append(f'\n\n### {text}\n\n')
        elif el.name == 'h4':
            text = el.get_text(strip=True)
            if text:
                md.append(f'\n\n#### {text}\n\n')
        elif el.name == 'p':
            pass  # 자식 텍스트로 처리
        elif el.name == 'br':
            md.append('\n')
        elif el.name == 'li':
            text = el.get_text(strip=True)
            if text:
                md.append(f'\n- {text}')
        elif el.name == 'img':
            src = el.get('src') or el.get('data-origin') or ''
            if src:
                md.append(f'\n\n![image]({src})\n\n')
        elif el.name == 'a' and el.parent.name not in ['figure']:
            href = el.get('href', '')
            text = el.get_text(strip=True)
            if href and text and 'rotcha.kr' not in href:
                md.append(f'[{text}]({href})')
    
    return ''.join(md)

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
            return None, []
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # 제목 추출
    title_el = soup.find('h2', class_='title-article')
    title = title_el.get_text(strip=True) if title_el else ''
    if not title:
        title_el = soup.find('title')
        title = title_el.get_text(strip=True) if title_el else Path(html_path).stem
    
    # 날짜 추출
    date_el = soup.find('p', class_='date')
    date_str = date_el.get_text(strip=True) if date_el else ''
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
    date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
    
    # 카테고리 추출
    cat_el = soup.find('p', class_='category')
    category = cat_el.get_text(strip=True) if cat_el else '미분류'
    
    # 태그 추출
    tags_el = soup.find('div', class_='tags')
    tags = []
    if tags_el:
        tag_text = tags_el.get_text(strip=True)
        tags = [t.strip().replace('#', '') for t in tag_text.split('#') if t.strip()]
    
    # 본문 추출
    content_el = soup.find('div', class_='contents_style')
    md_content = ''
    images = []
    
    if content_el:
        # 이미지 추출
        for img in content_el.find_all('img'):
            src = img.get('src') or img.get('data-origin') or ''
            if src:
                images.append(src)
        
        # 본문 변환 (간단한 방식)
        for el in content_el.find_all(['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'figure']):
            if el.name == 'h2':
                text = el.get_text(strip=True)
                if text:
                    md_content += f'\n\n## {text}\n\n'
            elif el.name == 'h3':
                text = el.get_text(strip=True)
                if text:
                    md_content += f'\n\n### {text}\n\n'
            elif el.name == 'h4':
                text = el.get_text(strip=True)
                if text:
                    md_content += f'\n\n#### {text}\n\n'
            elif el.name == 'p':
                # 이미지 체크
                img = el.find('img')
                if img:
                    src = img.get('src') or img.get('data-origin') or ''
                    if src:
                        md_content += f'\n\n![image]({src})\n\n'
                else:
                    text = el.get_text(strip=True)
                    if text and text != '\xa0':
                        # 링크 처리
                        for a in el.find_all('a'):
                            href = a.get('href', '')
                            link_text = a.get_text(strip=True)
                            if href and link_text:
                                text = text.replace(link_text, f'[{link_text}]({href})')
                        md_content += f'\n{text}\n'
            elif el.name in ['ul', 'ol']:
                for li in el.find_all('li', recursive=False):
                    text = li.get_text(strip=True)
                    if text:
                        md_content += f'\n- {text}'
                md_content += '\n'
            elif el.name == 'figure':
                img = el.find('img')
                if img:
                    src = img.get('src') or img.get('data-origin') or ''
                    if src:
                        md_content += f'\n\n![image]({src})\n\n'
    
    # 슬러그 생성
    filename = Path(html_path).stem
    match = re.match(r'\d+-(.+)', filename)
    tistory_slug = match.group(1) if match else slugify(title)
    hugo_slug = slugify(title)
    
    # 태그 문자열
    tags_str = ', '.join([f'"{t}"' for t in tags[:5]]) if tags else ''
    
    # Markdown 생성
    md = f'''---
title: "{title.replace('"', "'")}"
date: {date}
draft: false
categories: ["{category}"]
tags: [{tags_str}]
aliases:
  - /entry/{tistory_slug}/
---

{md_content}
'''
    
    return {
        'content': md,
        'slug': hugo_slug,
        'date': date,
        'images': images
    }, images

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 기존 파일 삭제
    for f in Path(OUTPUT_DIR).glob('*.md'):
        if f.name != 'hello-world.md':
            f.unlink()
    
    all_images = []
    converted = 0
    failed = 0
    
    html_files = list(Path(BACKUP_DIR).rglob('*.html'))
    print(f"총 {len(html_files)}개 HTML 파일 발견")
    
    for html_path in html_files:
        result, images = convert_html_to_md(str(html_path))
        
        if result and result['content'].strip():
            filename = f"{result['date']}-{result['slug']}.md"
            output_path = os.path.join(OUTPUT_DIR, filename)
            
            # 중복 파일명 처리
            counter = 1
            while os.path.exists(output_path):
                filename = f"{result['date']}-{result['slug']}-{counter}.md"
                output_path = os.path.join(OUTPUT_DIR, filename)
                counter += 1
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result['content'])
            
            all_images.extend(images)
            converted += 1
            print(f"✅ {filename}")
        else:
            failed += 1
            print(f"❌ {html_path}")
    
    with open(IMAGE_LOG, 'w', encoding='utf-8') as f:
        for img in set(all_images):
            f.write(img + '\n')
    
    print(f"\n완료! 변환: {converted}개, 실패: {failed}개")
    print(f"이미지 URL: {IMAGE_LOG} ({len(set(all_images))}개)")

if __name__ == '__main__':
    main()
