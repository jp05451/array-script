"""
Scan all Python files in the project for functions and classes, and update README.md.
"""

import argparse
import ast
import os


def scan_python_file(filepath: str) -> dict:
    """Scan a single Python file and return class/function info."""
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
                    methods.append({"name": item.name, "line": item.lineno})
            classes.append({"name": node.name, "methods": methods, "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno})

    return {"classes": classes, "functions": functions}


def scan_project(project_dir: str, exclude_dirs: set = None, exclude_files: set = None) -> list:
    """Scan the whole project directory and return analysis results for all Python files."""
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
    """Convert scan results to Markdown format."""
    total_functions = 0
    total_methods = 0
    total_classes = 0

    for r in results:
        total_functions += len(r["functions"])
        total_classes += len(r["classes"])
        for c in r["classes"]:
            total_methods += len(c["methods"])

    lines = []
    lines.append("## Project Function Scan Results")
    lines.append("")
    lines.append(f"> Scanned **{len(results)}** Python files, "
                 f"found **{total_classes}** classes, "
                 f"**{total_functions}** top-level functions, "
                 f"and **{total_methods}** methods "
                 f"(total **{total_functions + total_methods}** functions)")
    lines.append("")

    lines.append("| File | Classes | Top-level Functions | Methods | Total |")
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
                    lines.append(f"- `{m['name']}()` (line {m['line']})")
            else:
                lines.append("- _(no methods)_")
            lines.append("")

    return "\n".join(lines)


def update_readme(readme_path: str, section_md: str):
    """Update README.md by inserting or replacing the scan result block."""
    begin_marker = "<!-- FUNCTION_SCAN_BEGIN -->"
    end_marker = "<!-- FUNCTION_SCAN_END -->"

    block = f"{begin_marker}\n{section_md}\n{end_marker}"

    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    if begin_marker in content and end_marker in content:
        # Replace existing block
        start = content.index(begin_marker)
        end = content.index(end_marker) + len(end_marker)
        content = content[:start] + block + content[end:]
    else:
        # Append to the end of the file
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n" + block + "\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_args():
    parser = argparse.ArgumentParser(description="Scan all Python files for functions/classes and update README.md.")
    parser.add_argument(
        "--exclude-files", "-ef",
        nargs="*",
        default=[],
        metavar="FILE",
        help="File names to exclude, e.g., -ef RedisDB.py test_ssh.py",
    )
    parser.add_argument(
        "--exclude-dirs", "-ed",
        nargs="*",
        default=[],
        metavar="DIR",
        help="Additional directories to exclude (defaults already exclude .venv, .git, __pycache__, node_modules, .tox), e.g., -ed tests shell",
    )
    parser.add_argument(
        "--exclude-tests", "-et",
        action="store_true",
        help="Exclude all test_*.py files",
    )
    parser.add_argument(
        "--readme",
        default=None,
        metavar="PATH",
        help="Specify README.md path (default: README.md in project root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results only; do not write to README.md",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = args.readme or os.path.join(project_dir, "README.md")

    exclude_files = set(args.exclude_files)
    exclude_dirs = set(args.exclude_dirs)

    if args.exclude_tests:
        # Dynamically collect all test_*.py filenames
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

    # Print summary
    total = sum(
        len(r["functions"]) + sum(len(c["methods"]) for c in r["classes"])
        for r in results
    )
    print(f"Scan completed: {len(results)} files, {total} functions total")
    if args.exclude_files or args.exclude_tests:
        print(f"Excluded files: {', '.join(sorted(exclude_files))}")
    if args.exclude_dirs:
        print(f"Additional excluded directories: {', '.join(sorted(exclude_dirs))}")
    if not args.dry_run:
        print(f"Updated {readme_path}")


if __name__ == "__main__":
    main()
