"""
프로젝트 기술문서 자동 생성 에이전트
사용법:
  python scripts/doc_agent.py                  # 전체 스캔 → TECHNICAL.md 갱신
  python scripts/doc_agent.py --pipeline car    # 특정 파이프라인만
  python scripts/doc_agent.py --shared          # shared 모듈만
  python scripts/doc_agent.py --config          # config 분석만
  python scripts/doc_agent.py --summary         # 1페이지 요약만
"""
import os
import re
import ast
import argparse
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "themes",
               "public", "static", "assets", ".wrangler", ".aider.tags.cache.v4"}
IGNORE_FILES = {".pyc", ".bak", ".db", ".pickle", ".json", ".yaml", ".toml",
                ".sh", ".txt", ".md", ".html", ".css", ".js", ".svg", ".webp"}


def scan_py_files(target_dir):
    """디렉터리 내 .py 파일 목록 반환"""
    py_files = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                py_files.append(os.path.join(root, f))
    return sorted(py_files)


def extract_module_info(filepath):
    """Python 파일에서 docstring, 클래스, 함수, 상수, import 추출"""
    info = {
        "path": str(Path(filepath).relative_to(PROJECT_ROOT)),
        "docstring": "",
        "classes": [],
        "functions": [],
        "constants": [],
        "imports": [],
        "lines": 0,
    }
    try:
        source = open(filepath, "r", encoding="utf-8").read()
        info["lines"] = len(source.splitlines())
        tree = ast.parse(source)
    except Exception as e:
        info["error"] = str(e)
        return info

    # 모듈 docstring
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, (ast.Constant,))):
        val = tree.body[0].value
        info["docstring"] = info["docstring"].strip().split("\n")[0][:200]

    for node in ast.walk(tree):
        # 클래스
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            cls_doc = ""
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, (ast.Constant,))):
                val = node.body[0].value
            info["classes"].append({
                "name": node.name,
                "methods": methods,
                "docstring": cls_doc,
            })
        # 최상위 함수
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "col_offset") and node.col_offset == 0:
                func_doc = ""
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, (ast.Constant,))):
                    val = node.body[0].value
                args = []
                for arg in node.args.args:
                    if arg.arg != "self":
                        args.append(arg.arg)
                info["functions"].append({
                    "name": node.name,
                    "args": args,
                    "docstring": func_doc,
                })

    # 상수 (대문자 변수)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    info["constants"].append(target.id)

    # import
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                info["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                info["imports"].append(node.module)

    return info


def analyze_pipeline(pipeline_dir):
    """파이프라인 디렉터리 분석"""
    name = os.path.basename(pipeline_dir)
    py_files = scan_py_files(pipeline_dir)
    modules = [extract_module_info(f) for f in py_files]
    return {"name": name, "modules": modules}


def analyze_config():
    """config 디렉터리 분석 (YAML/TOML 키 구조)"""
    config_dir = PROJECT_ROOT / "config"
    result = {}
    for f in sorted(config_dir.glob("*")):
        if f.suffix in (".yaml", ".yml"):
            try:
                import yaml
                with open(f, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict):
                    result[f.name] = list(data.keys())[:20]
                elif isinstance(data, list):
                    result[f.name] = f"list[{len(data)}]"
            except Exception:
                result[f.name] = "parse error"
        elif f.suffix == ".toml":
            result[f.name] = "toml file"
        elif f.suffix == ".json":
            result[f.name] = "json file (credentials)"
    return result


def analyze_scheduler():
    """scheduler.py 분석 — 스케줄 정보 추출"""
    sched_path = PROJECT_ROOT / "scheduler.py"
    if not sched_path.exists():
        return None
    source = open(sched_path, "r", encoding="utf-8").read()
    schedules = re.findall(r'schedule\..*?\.do\(([^)]+)\)', source)
    cron_like = re.findall(r'(every.*?day.*?at.*?|interval.*?|cron.*?)\n', source, re.IGNORECASE)
    return {
        "jobs": schedules[:20],
        "patterns": cron_like[:10],
        "lines": len(source.splitlines()),
    }


def generate_markdown(pipelines, shared_modules, config_info, scheduler_info, summary_only=False):
    """분석 결과를 TECHNICAL.md 형식으로 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 프로젝트 기술문서",
        f"",
        f"> 자동 생성: {now} by `scripts/doc_agent.py`",
        f"",
    ]

    # 요약
    total_files = sum(len(p["modules"]) for p in pipelines) + len(shared_modules)
    total_lines = sum(m["lines"] for p in pipelines for m in p["modules"])
    total_lines += sum(m["lines"] for m in shared_modules)
    active_pipelines = [p["name"] for p in pipelines if any(m["lines"] > 10 for m in p["modules"])]

    lines += [
        "## 프로젝트 요약",
        "",
        f"| 항목 | 값 |",
        f"|---|---|",
        f"| Python 파일 수 | {total_files} |",
        f"| 총 코드 라인 수 | {total_lines:,} |",
        f"| 활성 파이프라인 | {', '.join(active_pipelines)} |",
        f"| shared 모듈 수 | {len(shared_modules)} |",
        "",
    ]

    if summary_only:
        return "\n".join(lines)

    # 파이프라인 상세
    lines += ["## 파이프라인", ""]
    for p in pipelines:
        if not any(m["lines"] > 10 for m in p["modules"]):
            continue
        lines.append(f"### {p['name']}")
        lines.append("")
        for m in p["modules"]:
            if m.get("error"):
                lines.append(f"- `{m['path']}` — parse error")
                continue
            if m["lines"] < 5:
                continue
            doc = f" — {m['docstring']}" if m["docstring"] else ""
            lines.append(f"**`{m['path']}`** ({m['lines']}줄){doc}")
            lines.append("")
            if m["classes"]:
                for cls in m["classes"]:
                    cls_doc = f": {cls['docstring']}" if cls["docstring"] else ""
                    lines.append(f"- class `{cls['name']}`{cls_doc}")
                    if cls["methods"]:
                        lines.append(f"  - methods: {', '.join(cls['methods'][:10])}")
            if m["functions"]:
                for fn in m["functions"]:
                    if fn["name"].startswith("_") and fn["name"] != "__init__":
                        continue
                    fn_doc = f" — {fn['docstring']}" if fn["docstring"] else ""
                    args_str = f"({', '.join(fn['args'][:5])})" if fn["args"] else "()"
                    lines.append(f"- `{fn['name']}{args_str}`{fn_doc}")
            if m["constants"]:
                lines.append(f"- 상수: {', '.join(m['constants'][:10])}")
            lines.append("")

    # shared 모듈
    lines += ["## shared 모듈", ""]
    for m in shared_modules:
        if m["lines"] < 5:
            continue
        doc = f" — {m['docstring']}" if m["docstring"] else ""
        lines.append(f"**`{m['path']}`** ({m['lines']}줄){doc}")
        lines.append("")
        if m["classes"]:
            for cls in m["classes"]:
                cls_doc = f": {cls['docstring']}" if cls["docstring"] else ""
                lines.append(f"- class `{cls['name']}`{cls_doc}")
                if cls["methods"]:
                    lines.append(f"  - methods: {', '.join(cls['methods'][:10])}")
        if m["functions"]:
            for fn in m["functions"]:
                if fn["name"].startswith("_"):
                    continue
                fn_doc = f" — {fn['docstring']}" if fn["docstring"] else ""
                args_str = f"({', '.join(fn['args'][:5])})" if fn["args"] else "()"
                lines.append(f"- `{fn['name']}{args_str}`{fn_doc}")
        if m["constants"]:
            lines.append(f"- 상수: {', '.join(m['constants'][:10])}")
        lines.append("")

    # config
    if config_info:
        lines += ["## config 파일", ""]
        for fname, keys in config_info.items():
            if isinstance(keys, list):
                lines.append(f"- `{fname}`: {', '.join(str(k) for k in keys)}")
            else:
                lines.append(f"- `{fname}`: {keys}")
        lines.append("")

    # scheduler
    if scheduler_info:
        lines += ["## 스케줄러", ""]
        lines.append(f"- `scheduler.py` ({scheduler_info['lines']}줄)")
        if scheduler_info["jobs"]:
            lines.append(f"- 등록된 작업: {len(scheduler_info['jobs'])}개")
            for j in scheduler_info["jobs"][:10]:
                lines.append(f"  - {j.strip()}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="프로젝트 기술문서 자동 생성")
    parser.add_argument("--pipeline", help="특정 파이프라인만 분석")
    parser.add_argument("--shared", action="store_true", help="shared 모듈만 분석")
    parser.add_argument("--config", action="store_true", help="config 분석만")
    parser.add_argument("--summary", action="store_true", help="요약만 출력")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "TECHNICAL.md"), help="출력 파일 경로")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력 (Claude 컨텍스트용)")
    args = parser.parse_args()

    pipelines_dir = PROJECT_ROOT / "pipelines"
    shared_dir = PROJECT_ROOT / "shared"

    # 파이프라인 분석
    pipelines = []
    if args.pipeline:
        target = pipelines_dir / args.pipeline
        if target.exists():
            pipelines.append(analyze_pipeline(str(target)))
        else:
            print(f"Pipeline not found: {args.pipeline}")
            return
    elif not args.shared and not args.config:
        for d in sorted(pipelines_dir.iterdir()):
            if d.is_dir() and d.name not in IGNORE_DIRS:
                pipelines.append(analyze_pipeline(str(d)))

    # shared 분석
    shared_modules = []
    if not args.config:
        for f in scan_py_files(str(shared_dir)):
            shared_modules.append(extract_module_info(f))

    # config 분석
    config_info = analyze_config() if not args.shared else {}

    # scheduler 분석
    scheduler_info = analyze_scheduler()

    if args.json:
        result = {
            "generated_at": datetime.now().isoformat(),
            "pipelines": pipelines,
            "shared": shared_modules,
            "config": config_info,
            "scheduler": scheduler_info,
        }
        json_path = args.output.replace(".md", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"JSON saved: {json_path}")
        return

    md = generate_markdown(pipelines, shared_modules, config_info, scheduler_info, args.summary)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Generated: {args.output}")
    print(f"  Pipelines: {len(pipelines)}")
    print(f"  Shared modules: {len(shared_modules)}")


if __name__ == "__main__":
    main()
