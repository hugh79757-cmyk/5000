import os
import re
from datetime import datetime
from pathlib import Path
import argparse

# ── 크기 제한 ──
MAX_FILE_SIZE = 50 * 1024
MAX_LINES_PER_FILE = 300
MAX_TOTAL_SIZE = 200 * 1024

# ── 제외 디렉토리 ──
EXCLUDE_DIRS = {
    "venv", ".venv", "env", "node_modules", "vendor",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", "out", "target",
    ".git", ".svn", ".idea", ".vscode",
    "logs", "log", "tmp", "temp", "cache",
    "htmlcov", "coverage", ".coverage", ".DS_Store",
}

# ── 제외 패턴 ──
EXCLUDE_PATTERNS = [
    "backup", ".bak", "test_", "_test.",
    "service_account", "client_secret", "token.pickle",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".sqlite", ".db", ".pkl", ".pickle",
    ".log", ".cache", ".map",
    ".pem", ".key", ".crt",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".o",
    "package-lock.json", "yarn.lock", "poetry.lock", "bun.lockb",
    "backup_",  # ← 출력 파일 자기 포함 방지
]

# ── 허용 확장자 ──
ALLOWED_EXT = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".html", ".css", ".scss", ".vue", ".svelte",
    ".go", ".rs", ".rb", ".php", ".java", ".c", ".cpp", ".h",
    ".yaml", ".yml", ".toml", ".json", ".jsonc",
    ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".md", ".txt", ".csv",
    ".editorconfig", ".tf", ".hcl", ".conf",
}

# ── 항상 포함 ──
ALWAYS_INCLUDE = {
    "wrangler.toml", "package.json", "tsconfig.json", "jsconfig.json",
    "pyproject.toml", "Cargo.toml", "go.mod", "go.sum",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "vercel.json", "netlify.toml", "fly.toml",
    "requirements.txt", "setup.py", "setup.cfg",
    ".gitignore", ".env.example", ".dockerignore",
    "README.md", "README.txt",
}

# ── 설정 파일 (항상 전체 포함) ──
CONFIG_FILES = {
    "wrangler.toml", "package.json", "tsconfig.json", "jsconfig.json",
    "pyproject.toml", "Cargo.toml", "go.mod",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "vercel.json", "netlify.toml", "fly.toml",
    "requirements.txt", "setup.py", "setup.cfg",
    ".gitignore", ".env.example",
    "schema.sql", "create-tables.sql",
}

# ── 민감 키워드 ──
SENSITIVE_KEYS = [
    "api_key=", "apikey=", "api-key=", "api_key:",
    "secret_key", "secret=", "token=",
    "password=", "passwd=", "pwd=",
    "credential", "private_key",
    "client_secret", "database_url", "db_pass",
    "aws_secret", "access_key=", "refresh_token=",
    "app_password", "database_id",
]

# ── 민감 값 패턴 ──
SENSITIVE_VALUE_PATTERNS = [
    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
    r"eyJ[a-zA-Z0-9_-]{50,}",
    r"-----BEGIN[^-]*-----[\s\S]*?-----END[^-]*-----",
]

# ── 진입점 ──
ENTRY_POINTS = {
    "main.py", "app.py", "run.py", "index.js", "index.ts",
    "worker.js", "worker.ts", "server.js", "server.ts",
}

# ── [신규] 노이즈 제거 패턴 ──
NOISE_PATTERNS = [
    r"^\s*#\s*(TODO|FIXME|HACK|XXX|NOTE):.*$",    # TODO 주석
    r"^\s*#\s*-{3,}\s*$",                          # 구분선 주석
    r"^\s*(#|//)\s*={3,}\s*$",                      # 구분선 주석
    r"^\s*logging\.(debug|info)\(.*\)\s*$",         # debug/info 로깅
    r"^\s*console\.log\(.*\)\s*$",                  # console.log
    r"^\s*print\(f?['\"]DEBUG.*\)\s*$",             # 디버그 프린트
]
NOISE_RE = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]


def should_exclude_dir(dirname):
    return dirname.lower() in {d.lower() for d in EXCLUDE_DIRS}


def should_include(path, root):
    rel_path = path.relative_to(root)
    parts = rel_path.parts
    name = path.name
    name_lower = name.lower()

    for part in parts[:-1]:
        if should_exclude_dir(part):
            return False

    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in name_lower:
            return False

    if name in ALWAYS_INCLUDE:
        return True

    if name.startswith(".") and name not in ALWAYS_INCLUDE:
        return False

    return path.suffix.lower() in ALLOWED_EXT


def get_priority(path):
    name = path.name
    if name in CONFIG_FILES:
        return 0
    if name in ENTRY_POINTS:
        return 1
    if name in {"cli.py", "gui.py", "routes.py", "handlers.py", "api.py"}:
        return 2
    if name in {"models.py", "schema.py", "types.ts", "types.py"}:
        return 3
    if path.suffix == ".sql":
        return 4
    if name.lower().startswith("readme"):
        return 5
    return 10


def mask_sensitive(content, filename):
    ext = os.path.splitext(filename)[1].lower()
    base = os.path.basename(filename).lower()
    is_env_file = (
        ext in {".env", ".toml", ".yaml", ".yml", ".cfg", ".ini", ".conf", ".json"}
        or base.startswith(".env")
    )

    lines = []
    for line in content.split("\n"):
        line_lower = line.lower().strip()

        if line_lower.startswith("#") or line_lower.startswith("//"):
            lines.append(line)
            continue

        if is_env_file:
            has_key = any(key in line_lower for key in SENSITIVE_KEYS)
            if has_key:
                if "=" in line and not line.strip().startswith(("#", "//")):
                    key_part = line.split("=", 1)[0]
                    lines.append(key_part + "= ***")
                elif ":" in line and not line.strip().startswith(("#", "//", "-")):
                    key_part = line.split(":", 1)[0]
                    lines.append(key_part + ": ***")
                else:
                    lines.append(line)
                continue

        masked = line
        for pattern in SENSITIVE_VALUE_PATTERNS:
            masked = re.sub(pattern, "***", masked)
        lines.append(masked)

    return "\n".join(lines)


# ── [신규] 노이즈 줄 제거 ──
def strip_noise(content):
    """디버그 로그, TODO 주석, 구분선 등 맥락에 불필요한 줄을 제거"""
    lines = content.split("\n")
    cleaned = []
    prev_blank = False
    for line in lines:
        # 노이즈 패턴 매칭
        if any(r.match(line) for r in NOISE_RE):
            continue
        # 연속 빈 줄 압축 (2줄 이상 → 1줄)
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        prev_blank = is_blank
        cleaned.append(line)
    return "\n".join(cleaned)


# ── [신규] 함수/클래스 시그니처 + docstring만 추출 (Python) ──
def extract_signatures_python(content):
    """파일이 너무 클 때, 함수/클래스 시그니처와 docstring만 추출"""
    lines = content.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # class 또는 def 라인
        if stripped.startswith(("def ", "class ", "async def ")):
            result.append(line)
            # 다음 줄에 docstring이 있는지 확인
            j = i + 1
            # 여러 줄에 걸친 시그니처 처리 (괄호가 닫히지 않은 경우)
            full_sig = line
            while j < len(lines) and ")" not in full_sig and ":" not in full_sig.split(")")[-1] if ")" in full_sig else True:
                if j < len(lines):
                    result.append(lines[j])
                    full_sig += lines[j]
                j += 1
                if j - i > 10:  # 안전 장치
                    break

            # docstring 추출
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                doc_line = lines[j].strip()
                if doc_line.startswith(('"""', "'''", '"', "'")):
                    # docstring 시작
                    result.append(lines[j])
                    if doc_line.count('"""') == 1 or doc_line.count("'''") == 1:
                        # 여러 줄 docstring
                        j += 1
                        while j < len(lines):
                            result.append(lines[j])
                            if '"""' in lines[j] or "'''" in lines[j]:
                                break
                            j += 1
            result.append("")  # 빈 줄 구분
            i = j + 1
        # import 문도 포함
        elif stripped.startswith(("import ", "from ")):
            result.append(line)
            i += 1
        # 최상위 변수 할당 (들여쓰기 없는 것)
        elif not line.startswith((" ", "\t")) and "=" in stripped and not stripped.startswith("#"):
            result.append(line)
            i += 1
        else:
            i += 1

    return "\n".join(result)


# ── [신규] 함수/클래스 시그니처 추출 (JS/TS) ──
def extract_signatures_js(content):
    """JS/TS 파일에서 export, function, class 시그니처 추출"""
    lines = content.split("\n")
    result = []
    i = 0
    brace_depth = 0

    for line in lines:
        stripped = line.lstrip()

        # import/export 문
        if stripped.startswith(("import ", "export ")):
            result.append(line)
        # function 선언
        elif stripped.startswith(("function ", "async function ", "const ", "let ", "class ")):
            if not line.startswith((" ", "\t")) or stripped.startswith("export"):
                result.append(line)
        # 타입/인터페이스 정의
        elif stripped.startswith(("interface ", "type ", "enum ")):
            result.append(line)
        # JSDoc 주석
        elif stripped.startswith("/**"):
            result.append(line)

    return "\n".join(result)


def truncate_content(content, max_lines, is_config, filepath=None):
    """내용 잘라내기. 초과 시 시그니처 추출로 대체"""
    if is_config:
        return content, False

    lines = content.split("\n")
    if len(lines) <= max_lines:
        return content, False

    # 시그니처 추출 시도
    if filepath:
        ext = filepath.suffix.lower()
        if ext == ".py":
            sig = extract_signatures_python(content)
            sig_lines = sig.split("\n")
            if len(sig_lines) < len(lines) * 0.7:  # 30% 이상 줄었을 때만
                header = f"# [시그니처 모드] 원본 {len(lines)}줄 → 시그니처 {len(sig_lines)}줄\n"
                return header + sig, True
        elif ext in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}:
            sig = extract_signatures_js(content)
            sig_lines = sig.split("\n")
            if len(sig_lines) < len(lines) * 0.7:
                header = f"// [시그니처 모드] 원본 {len(lines)}줄 → 시그니처 {len(sig_lines)}줄\n"
                return header + sig, True

    # 시그니처 추출이 불가하면 기존 방식으로 잘라내기
    kept = lines[:max_lines]
    omitted = len(lines) - max_lines
    kept.append("")
    kept.append(f"# ... ({omitted}줄 생략)")
    return "\n".join(kept), True


def build_tree(root, files_map):
    tree_lines = []
    all_paths = sorted(files_map.keys())
    dirs_seen = set()

    for rel_str in all_paths:
        parts = Path(rel_str).parts
        for i in range(len(parts) - 1):
            dir_path = "/".join(parts[: i + 1])
            if dir_path not in dirs_seen:
                dirs_seen.add(dir_path)
                indent = "  " * i
                tree_lines.append(f"{indent}{parts[i]}/")
        indent = "  " * (len(parts) - 1)
        fname = parts[-1]
        size = files_map[rel_str]
        if size >= 1024:
            size_str = f"{size/1024:.1f}KB"
        else:
            size_str = f"{size}B"
        tree_lines.append(f"{indent}{fname}  ({size_str})")

    return "\n".join(tree_lines)


# ── [신규] .gitignore 파싱 ──
def parse_gitignore(root):
    """프로젝트의 .gitignore를 읽어 추가 제외 패턴 반환"""
    gitignore_path = root / ".gitignore"
    patterns = []
    if gitignore_path.exists():
        try:
            for line in gitignore_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except Exception:
            pass
    return patterns


def matches_gitignore(rel_path, gitignore_patterns):
    """간이 .gitignore 매칭 (완전한 구현은 아니지만 실용적)"""
    rel_str = str(rel_path)
    name = rel_path.name

    for pattern in gitignore_patterns:
        # 디렉토리 패턴 (끝에 / 있는 경우)
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if dir_name in rel_str.split(os.sep):
                return True
        # 확장자 패턴 (*.ext)
        elif pattern.startswith("*."):
            ext = pattern[1:]  # .ext
            if name.endswith(ext):
                return True
        # 정확한 파일명
        elif "/" not in pattern and "*" not in pattern:
            if name == pattern:
                return True
        # 경로 패턴
        elif pattern in rel_str:
            return True

    return False


def collect_all_files(root):
    tree_map = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            try:
                rel = str(fpath.relative_to(root))
                size = fpath.stat().st_size
                tree_map[rel] = size
            except (OSError, ValueError):
                pass
    return tree_map


# ── [신규] 예산(budget) 기반 파일 할당 ──
def allocate_budget(target_files, budget_bytes, config_files_set):
    """
    총 예산 내에서 우선순위가 높은 파일에 더 많은 공간을 할당.
    설정 파일은 예산에서 먼저 차감하고, 나머지를 코드 파일에 분배.
    """
    config_budget = 0
    code_files = []

    for rel, size, path, priority, depth in target_files:
        if path.name in config_files_set:
            config_budget += min(size, MAX_FILE_SIZE)
        else:
            code_files.append((rel, size, path, priority, depth))

    remaining = budget_bytes - config_budget
    if remaining < 0:
        remaining = budget_bytes // 2  # 설정 파일이 너무 크면 절반씩

    # 각 코드 파일에 할당할 수 있는 최대 줄 수 계산
    if code_files:
        per_file = max(remaining // len(code_files), 1024)  # 최소 1KB
    else:
        per_file = remaining

    return per_file


def export_project(output_name=None, root_path=None, compact=False, budget=None):
    root = Path(root_path) if root_path else Path.cwd()
    project_name = root.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_name:
        output_file = root / output_name
    else:
        output_file = root / f"backup_{timestamp}.txt"

    # .gitignore 패턴 로드
    gitignore_patterns = parse_gitignore(root)

    all_tree = collect_all_files(root)

    target_files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and should_include(path, root):
            rel_path = path.relative_to(root)
            # .gitignore 패턴 체크
            if matches_gitignore(rel_path, gitignore_patterns):
                if path.name not in ALWAYS_INCLUDE:
                    continue
            rel = str(rel_path)
            size = path.stat().st_size
            priority = get_priority(path)
            depth = len(Path(rel).parts)
            target_files.append((rel, size, path, priority, depth))

    if compact:
        compact_exclude_ext = {".md", ".txt", ".csv", ".html"}
        compact_exclude_names = {"client_secret.json", "service_account.json"}
        target_files = [
            (r, s, p, pr, d) for r, s, p, pr, d in target_files
            if p.name not in compact_exclude_names
            and (p.suffix.lower() not in compact_exclude_ext or p.name in CONFIG_FILES)
        ]

    target_files.sort(key=lambda x: (x[3], x[4], x[0]))

    # 예산 기반 라인 수 조정
    effective_budget = budget or MAX_TOTAL_SIZE
    per_file_budget = allocate_budget(target_files, effective_budget, CONFIG_FILES)
    adaptive_max_lines = max(per_file_budget // 40, 30)  # 줄당 ~40바이트 가정, 최소 30줄

    files_exported = []
    files_skipped = []
    total_size = 0

    with open(output_file, "w", encoding="utf-8") as out:
        out.write(f"# {project_name}  ({datetime.now().strftime('%Y-%m-%d')})\n")
        mode_str = "compact" if compact else "full"
        budget_str = f"{effective_budget//1024}KB"
        out.write(f"# 모드: {mode_str} | 예산: {budget_str} | 전체: {len(all_tree)} | 대상: {len(target_files)}\n")
        out.write("=" * 60 + "\n\n")

        # 디렉토리 트리 (포함 파일만 표시하여 크기 절약)
        included_tree = {rel: all_tree.get(rel, 0) for rel, *_ in target_files}
        out.write("## 프로젝트 구조\n")
        out.write("```\n")
        out.write(build_tree(root, included_tree))
        out.write("\n```\n\n")

        # 파일 목록 (별도 섹션 제거 → 트리에 통합하여 중복 절약)

        for rel, size, path, priority, _ in target_files:
            is_config = path.name in CONFIG_FILES

            if not is_config and total_size > effective_budget:
                files_skipped.append(f"{rel} (예산 초과)")
                continue

            if size > MAX_FILE_SIZE:
                # 큰 파일도 시그니처 추출 시도
                try:
                    content = path.read_text(encoding="utf-8")
                    ext = path.suffix.lower()
                    sig = None
                    if ext == ".py":
                        sig = extract_signatures_python(content)
                    elif ext in {".js", ".ts", ".jsx", ".tsx"}:
                        sig = extract_signatures_js(content)

                    if sig and len(sig.encode("utf-8")) < MAX_FILE_SIZE:
                        content = mask_sensitive(sig, path.name)
                        out.write(f"\n{'='*60}\n")
                        out.write(f"# {rel}  [시그니처만 — 원본 {size//1024}KB]\n")
                        out.write(f"{'='*60}\n")
                        out.write(content)
                        out.write("\n")
                        files_exported.append(rel)
                        total_size += len(content.encode("utf-8"))
                        continue
                except (UnicodeDecodeError, Exception):
                    pass

                files_skipped.append(f"{rel} ({size//1024}KB 초과)")
                continue

            try:
                content = path.read_text(encoding="utf-8")
                content = mask_sensitive(content, path.name)
                content = strip_noise(content)  # ← 노이즈 제거

                effective_lines = min(MAX_LINES_PER_FILE, adaptive_max_lines) if not is_config else MAX_LINES_PER_FILE
                content, truncated = truncate_content(content, effective_lines, is_config, filepath=path)

                out.write(f"\n{'='*60}\n")
                label = f"# {rel}"
                if is_config:
                    label += "  [설정]"
                if truncated:
                    label += "  [요약]"
                out.write(f"{label}\n")
                out.write(f"{'='*60}\n")
                out.write(content)
                out.write("\n")

                files_exported.append(rel)
                total_size += len(content.encode("utf-8"))

            except UnicodeDecodeError:
                files_skipped.append(f"{rel} (바이너리)")
            except Exception as e:
                files_skipped.append(f"{rel} ({e})")

        out.write(f"\n{'='*60}\n")
        out.write(f"# 요약\n")
        out.write(f"# 내보냄: {len(files_exported)} | 건너뜀: {len(files_skipped)} | 크기: {total_size:,}B\n")
        if files_skipped:
            out.write(f"# 건너뛴 파일:\n")
            for s in files_skipped:
                out.write(f"#   - {s}\n")
        out.write(f"{'='*60}\n")

    final_size = output_file.stat().st_size
    print(f"✓ 출력: {output_file.name} ({mode_str})")
    print(f"  파일: {len(files_exported)}개 내보냄, {len(files_skipped)}개 건너뜀")
    print(f"  크기: {final_size:,} bytes ({final_size/1024:.1f}KB)")
    if final_size > effective_budget:
        print(f"  ⚠ 예산({effective_budget//1024}KB) 초과!")
    if files_skipped:
        print(f"  건너뛴 파일:")
        for s in files_skipped[:10]:
            print(f"    - {s}")
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="프로젝트 컨텍스트 내보내기 v4")
    parser.add_argument("-o", "--output", help="출력 파일명")
    parser.add_argument("-p", "--path", help="프로젝트 경로")
    parser.add_argument("--full", action="store_true", help="전체 모드")
    parser.add_argument("--budget", type=int, default=100, help="목표 크기 (KB, 기본: 100)")
    parser.add_argument("--max-lines", type=int, default=300)
    parser.add_argument("--max-size", type=int, default=50)
    args = parser.parse_args()

    compact = not args.full
    budget_bytes = args.budget * 1024
    MAX_TOTAL_SIZE = budget_bytes

    if compact:
        MAX_LINES_PER_FILE = 80
        MAX_FILE_SIZE = 20 * 1024
    else:
        if args.max_lines:
            MAX_LINES_PER_FILE = args.max_lines
        if args.max_size:
            MAX_FILE_SIZE = args.max_size * 1024

    export_project(args.output, args.path, compact=compact, budget=budget_bytes)
