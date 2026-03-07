#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

INCLUDE_SUFFIXES = {
    ".py", ".rst", ".toml", ".yaml", ".yml",
    ".json", ".ini", ".cfg", ".sh"
}

EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".idea", ".vscode"
}

EXCLUDE_FILES = {
    "AGENT.md",
    "improvement.md",
    "README.md",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

EXCLUDE_RELATIVE_PATHS = {
    "skills/full-llm-export/scripts/export_repo_context.py",
}

MAX_FILE_SIZE = 200_000  # bytes
ALLOWED_TOP_LEVEL_DIRS = {"aps_automation_sdk", "examples"}


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
        if not rel_parts or rel_parts[0] not in ALLOWED_TOP_LEVEL_DIRS:
            return True
    except ValueError:
        return True

    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    try:
        rel = path.relative_to(root).as_posix()
        if rel in EXCLUDE_RELATIVE_PATHS:
            return True
    except ValueError:
        pass
    if path.is_file():
        if path.suffix not in INCLUDE_SUFFIXES:
            return True
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                return True
        except OSError:
            return True
    return False


def iter_files(root: Path, output_file: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == output_file.resolve():
            continue
        if should_skip(path, root):
            continue
        files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(root)))


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def export_repo_context(root: Path, output_file: Path) -> None:
    files = iter_files(root, output_file)

    lines: list[str] = []
    lines.append("# Repository context export\n\n")

    for file_path in files:
        rel = file_path.relative_to(root)
        content = read_text_file(file_path).rstrip()

        lines.append("=" * 100 + "\n")
        lines.append(f"FILE: {rel.as_posix()}\n")
        lines.append("=" * 100 + "\n\n")
        lines.append(content)
        lines.append("\n\n")

    output_file.write_text("".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export repository context to llms-full.txt")
    parser.add_argument("--root", default=".", help="Repository root to scan (default: current directory)")
    parser.add_argument("--output", default="llms-full.txt", help="Output file name or absolute path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()

    output_arg = Path(args.output)
    output_file = output_arg if output_arg.is_absolute() else (root / output_arg)

    export_repo_context(root, output_file)
    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
