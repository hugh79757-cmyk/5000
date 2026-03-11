#!/usr/bin/env python3
"""
Hugo 블로그 백업 스크립트
- 포스트(content) 제외
- 테마, 설정, 레이아웃만 백업
"""
import os
from datetime import datetime
from pathlib import Path
import argparse

# 설정값
MAX_FILE_SIZE = 30 * 1024      # 30KB 초과 파일은 요약만
MAX_LINES_PER_FILE = 500       # 파일당 최대 라인 수
SKIP_LARGE_FILES = True        # 대용량 파일 스킵 여부

# 제외할 폴더 (Hugo 특화)
EXCLUDE_DIRS = {
    '__pycache__', 'venv', '.venv', '.git', 
    'node_modules', 'backup', 'logs', '.idea', 'dist', 'build',
    # Hugo 포스트/리소스 제외
    'content',           # 포스트 폴더
    'public',            # 빌드 결과물
    'resources',         # 캐시된 리소스
    'static',            # 정적 파일 (이미지 등)
    # 추가 제외
    'rankingoneto-1-1',  # 백업/임시 폴더
}

# 제외할 파일
EXCLUDE_FILES = {
    '.env', 'credentials.json', 'blogger_token.pickle',
    '.DS_Store', 'Thumbs.db', '.hugo_build.lock',
    'image_urls.txt', 'zero_clicks.txt'  # 대용량 텍스트
}

# 제외할 패턴
EXCLUDE_PATTERNS = [
    'client_secret', '.pickle', '.pyc', '.png', '.jpg', 
    '.jpeg', '.gif', '.ico', '.sqlite', '.db', '.log',
    'backup_', '.lock', '.woff', '.woff2', '.ttf', '.eot',
    'hugo_backup_'  # 이전 백업 파일
]

# 포함할 확장자 (Hugo 특화)
ALLOWED_EXT = {
    '.py', '.yaml', '.yml', '.toml', '.json', '.sh',
    '.html', '.css', '.js', '.xml', '.scss', '.sass'
}

# 민감 키워드 (마스킹 대상)
SENSITIVE_KEYS = [
    'api_key', 'apikey', 'secret', 'token', 'password', 'passwd',
    'client_id', 'client_secret', 'credential', 'private_key',
    'access_key', 'auth', 'bearer', 'disqus', 'google_analytics',
    'googleAnalytics', 'ga_id'
]


def should_include(path: Path) -> bool:
    """파일 포함 여부 판단"""
    # 폴더 체크
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False
    
    name = path.name
    
    # 제외 파일 체크
    if name in EXCLUDE_FILES:
        return False
    
    # 제외 패턴 체크
    for pattern in EXCLUDE_PATTERNS:
        if pattern in name.lower():
            return False
    
    # 숨김 파일 (예외 허용)
    if name.startswith('.'):
        if name in {'.gitignore', '.env.example', '.dockerignore', '.gitmodules'}:
            return True
        return False
    
    # 확장자 체크
    if path.suffix.lower() in ALLOWED_EXT:
        return True
    
    # 특수 파일 (Hugo 설정)
    if name in {'config.toml', 'config.yaml', 'hugo.toml', 'hugo.yaml', 
                'Makefile', 'Dockerfile', 'netlify.toml', 'vercel.json'}:
        return True
    
    return False


def mask_sensitive(content: str) -> str:
    """민감 정보 마스킹"""
    lines = []
    for line in content.split('\n'):
        line_lower = line.lower()
        
        # 주석은 그대로
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//'):
            lines.append(line)
            continue
        
        # 민감 키워드 체크
        is_sensitive = any(key in line_lower for key in SENSITIVE_KEYS)
        
        if is_sensitive:
            # = 또는 : 기준 마스킹
            if '=' in line:
                key_part = line.split('=')[0]
                lines.append(f"{key_part}=***MASKED***")
            elif ':' in line and not line.strip().startswith('-'):
                key_part = line.split(':')[0]
                lines.append(f"{key_part}: ***MASKED***")
            else:
                lines.append(line)
        else:
            lines.append(line)
    
    return '\n'.join(lines)


def truncate_content(content: str, max_lines: int) -> tuple[str, bool]:
    """내용 자르기"""
    lines = content.split('\n')
    if len(lines) <= max_lines:
        return content, False
    
    truncated = '\n'.join(lines[:max_lines])
    truncated += f"\n\n... (이하 {len(lines) - max_lines}줄 생략)"
    return truncated, True


def export_project(output_name: str = None, summary_only: bool = False, root_path: str = None):
    """프로젝트 코드 내보내기"""
    if root_path:
        root = Path(root_path)
    else:
        root = Path(__file__).parent
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if output_name:
        output_file = Path(output_name)
    else:
        output_file = root / f'hugo_backup_{timestamp}.txt'
    
    files_exported = []
    files_skipped = []
    total_size = 0
    
    with open(output_file, 'w', encoding='utf-8') as out:
        # 헤더
        out.write(f"# Hugo 블로그 백업\n")
        out.write(f"# 생성: {datetime.now().isoformat()}\n")
        out.write(f"# 경로: {root}\n")
        out.write(f"# 모드: {'요약' if summary_only else '전체'}\n")
        out.write(f"# 제외: content/, public/, resources/, static/\n")
        out.write("=" * 60 + "\n\n")
        
        # 파일 목록 먼저 출력
        out.write("## 파일 목록\n")
        all_files = []
        for path in sorted(root.rglob('*')):
            if path.is_file() and should_include(path):
                rel_path = path.relative_to(root)
                size = path.stat().st_size
                all_files.append((rel_path, size))
                out.write(f"- {rel_path} ({size:,} bytes)\n")
        out.write("\n")
        
        # 제외된 폴더 정보
        out.write("## 제외된 폴더\n")
        for exclude_dir in ['content', 'public', 'resources', 'static', 'rankingoneto-1-1']:
            exclude_path = root / exclude_dir
            if exclude_path.exists():
                file_count = sum(1 for _ in exclude_path.rglob('*') if _.is_file())
                out.write(f"- {exclude_dir}/ ({file_count}개 파일)\n")
        out.write("\n")
        
        if summary_only:
            out.write("## 요약 모드 - 파일 목록만 출력됨\n")
        else:
            # 파일 내용 출력
            for rel_path, size in all_files:
                path = root / rel_path
                
                # 대용량 파일 스킵
                if SKIP_LARGE_FILES and size > MAX_FILE_SIZE:
                    files_skipped.append((str(rel_path), "대용량"))
                    out.write(f"\n{'='*60}\n")
                    out.write(f"FILE: {rel_path} [스킵 - {size:,} bytes]\n")
                    out.write(f"{'='*60}\n")
                    continue
                
                try:
                    content = path.read_text(encoding='utf-8')
                    
                    # 민감 정보 마스킹
                    content = mask_sensitive(content)
                    
                    # 라인 수 제한
                    content, was_truncated = truncate_content(content, MAX_LINES_PER_FILE)
                    
                    out.write(f"\n{'='*60}\n")
                    out.write(f"FILE: {rel_path}\n")
                    out.write(f"{'='*60}\n\n")
                    out.write(content)
                    out.write("\n")
                    
                    files_exported.append(str(rel_path))
                    total_size += len(content)
                    
                except UnicodeDecodeError:
                    files_skipped.append((str(rel_path), "바이너리"))
                except Exception as e:
                    files_skipped.append((str(rel_path), str(e)))
        
        # 요약
        out.write(f"\n\n{'='*60}\n")
        out.write(f"# 백업 완료\n")
        out.write(f"# 포함: {len(files_exported)}개\n")
        out.write(f"# 스킵: {len(files_skipped)}개\n")
        if files_skipped:
            out.write(f"# 스킵 목록: {', '.join(f[0] for f in files_skipped[:5])}\n")
        out.write("=" * 60 + "\n")
    
    print(f"✅ 백업 완료: {output_file}")
    print(f"   포함 파일: {len(files_exported)}개")
    print(f"   스킵 파일: {len(files_skipped)}개")
    print(f"   출력 크기: {output_file.stat().st_size:,} bytes")
    
    return output_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hugo 블로그 백업')
    parser.add_argument('-o', '--output', help='출력 파일명')
    parser.add_argument('-s', '--summary', action='store_true', help='파일 목록만 출력')
    parser.add_argument('-p', '--path', help='Hugo 프로젝트 경로')
    parser.add_argument('--max-lines', type=int, default=500, help='파일당 최대 라인')
    parser.add_argument('--max-size', type=int, default=30, help='최대 파일 크기 (KB)')
    
    args = parser.parse_args()
    
    if args.max_lines:
        MAX_LINES_PER_FILE = args.max_lines
    if args.max_size:
        MAX_FILE_SIZE = args.max_size * 1024
    
    export_project(args.output, args.summary, args.path)
