"""
掃描專案中所有 Python 檔案的 function 與 class，並更新 README.md。
"""

import argparse
import ast
import os


def scan_python_file(filepath: str) -> dict:
    """掃描單一 Python 檔案，回傳 class 與 function 資訊。"""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return {"classes": [], "functions": []}

    classes = []
    functions = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            classes.append({"name": node.name, "methods": methods, "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno})

    return {"classes": classes, "functions": functions}


def scan_project(project_dir: str, exclude_dirs: set = None, exclude_files: set = None) -> list:
    """掃描整個專案目錄，回傳所有 Python 檔案的分析結果。"""
    if exclude_dirs is None:
        exclude_dirs = set()
    if exclude_files is None:
        exclude_files = set()

    default_exclude_dirs = {".venv", ".git", "__pycache__", "node_modules", ".tox"}
    exclude_dirs = default_exclude_dirs | exclude_dirs

    results = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for filename in sorted(files):
            if not filename.endswith(".py") or filename == os.path.basename(__file__):
                continue
            if filename in exclude_files:
                continue
            filepath = os.path.join(root, filename)
            relpath = os.path.relpath(filepath, project_dir)
            info = scan_python_file(filepath)
            if info["classes"] or info["functions"]:
                results.append({"file": relpath, **info})

    return results


def generate_markdown(results: list) -> str:
    """將掃描結果轉為 Markdown 格式。"""
    total_functions = 0
    total_methods = 0
    total_classes = 0

    for r in results:
        total_functions += len(r["functions"])
        total_classes += len(r["classes"])
        for c in r["classes"]:
            total_methods += len(c["methods"])

    lines = []
    lines.append("## 專案函式掃描結果")
    lines.append("")
    lines.append(f"> 掃描到 **{len(results)}** 個 Python 檔案，"
                 f"共 **{total_classes}** 個 class、"
                 f"**{total_functions}** 個 top-level function、"
                 f"**{total_methods}** 個 method "
                 f"(總計 **{total_functions + total_methods}** 個 function)")
    lines.append("")

    lines.append("| 檔案 | Classes | Top-level Functions | Methods | 合計 |")
    lines.append("|------|---------|--------------------:|--------:|-----:|")
    for r in results:
        n_func = len(r["functions"])
        n_cls = len(r["classes"])
        n_methods = sum(len(c["methods"]) for c in r["classes"])
        lines.append(f"| `{r['file']}` | {n_cls} | {n_func} | {n_methods} | {n_func + n_methods} |")
    lines.append("")

    for r in results:
        lines.append(f"### `{r['file']}`")
        lines.append("")
        if r["functions"]:
            lines.append("**Top-level Functions:**")
            lines.append("")
            for fn in r["functions"]:
                lines.append(f"- `{fn['name']}()` (line {fn['line']})")
            lines.append("")
        for cls in r["classes"]:
            lines.append(f"**Class `{cls['name']}`** (line {cls['line']}):")
            lines.append("")
            if cls["methods"]:
                for m in cls["methods"]:
                    lines.append(f"- `{m}()`")
            else:
                lines.append("- _(no methods)_")
            lines.append("")

    return "\n".join(lines)


def update_readme(readme_path: str, section_md: str):
    """更新 README.md，在標記區塊中插入或替換掃描結果。"""
    begin_marker = "<!-- FUNCTION_SCAN_BEGIN -->"
    end_marker = "<!-- FUNCTION_SCAN_END -->"

    block = f"{begin_marker}\n{section_md}\n{end_marker}"

    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    if begin_marker in content and end_marker in content:
        # 替換現有區塊
        start = content.index(begin_marker)
        end = content.index(end_marker) + len(end_marker)
        content = content[:start] + block + content[end:]
    else:
        # 附加到檔案末尾
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n" + block + "\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_args():
    parser = argparse.ArgumentParser(description="掃描專案中所有 Python 檔案的 function 與 class，並更新 README.md。")
    parser.add_argument(
        "--exclude-files", "-ef",
        nargs="*",
        default=[],
        metavar="FILE",
        help="要排除的檔案名稱，例如：-ef RedisDB.py test_ssh.py",
    )
    parser.add_argument(
        "--exclude-dirs", "-ed",
        nargs="*",
        default=[],
        metavar="DIR",
        help="要額外排除的目錄名稱（預設已排除 .venv, .git, __pycache__, node_modules, .tox），例如：-ed tests shell",
    )
    parser.add_argument(
        "--exclude-tests", "-et",
        action="store_true",
        help="排除所有 test_*.py 測試檔案",
    )
    parser.add_argument(
        "--readme",
        default=None,
        metavar="PATH",
        help="指定 README.md 路徑（預設為專案根目錄下的 README.md）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只印出掃描結果，不寫入 README.md",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = args.readme or os.path.join(project_dir, "README.md")

    exclude_files = set(args.exclude_files)
    exclude_dirs = set(args.exclude_dirs)

    if args.exclude_tests:
        # 動態收集所有 test_*.py 檔案名稱
        for root, _, files in os.walk(project_dir):
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    exclude_files.add(f)

    results = scan_project(project_dir, exclude_dirs=exclude_dirs, exclude_files=exclude_files)
    section_md = generate_markdown(results)

    if args.dry_run:
        print(section_md)
    else:
        update_readme(readme_path, section_md)

    # 印出摘要
    total = sum(
        len(r["functions"]) + sum(len(c["methods"]) for c in r["classes"])
        for r in results
    )
    print(f"掃描完成：{len(results)} 個檔案，共 {total} 個 function")
    if args.exclude_files or args.exclude_tests:
        print(f"已排除檔案：{', '.join(sorted(exclude_files))}")
    if args.exclude_dirs:
        print(f"已額外排除目錄：{', '.join(sorted(exclude_dirs))}")
    if not args.dry_run:
        print(f"已更新 {readme_path}")


if __name__ == "__main__":
    main()
