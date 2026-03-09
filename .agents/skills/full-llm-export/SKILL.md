---
name: full-llm-export
description: Export repository context into a single plain-text snapshot file for downstream LLM/agent ingestion. Use when asked to generate, refresh, or rebuild `llms-full.txt` (or equivalent repo context dumps), especially before handing codebases to external agents that do not have direct repository context.
---

# Full LLM Export

## Overview
Generate `llms-full.txt` from repository source files with deterministic include/exclude rules and size limits.

## Run Workflow
1. Run the exporter script from the target repository root.
2. Verify that `llms-full.txt` exists and has current content.
3. Re-run after meaningful repository changes.

### Default command
```bash
python .agents/skills/full-llm-export/scripts/export_repo_context.py
```

### Custom root/output
```bash
python .agents/skills/full-llm-export/scripts/export_repo_context.py \
  --root /path/to/repo \
  --output llms-full.txt
```

## Script Behavior
- Include file suffixes:
  `.py`, `.md`, `.rst`, `.toml`, `.yaml`, `.yml`, `.json`, `.txt`, `.ini`, `.cfg`, `.sh`
- Exclude directories:
  `.git`, `.hg`, `.svn`, `.venv`, `venv`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `node_modules`, `dist`, `build`, `.idea`, `.vscode`
- Exclude lock files:
  `poetry.lock`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`
- Skip files larger than `200_000` bytes.
- Write one concatenated export file with per-file separators and relative paths.

## Output Contract
- Default output file: `llms-full.txt` in the selected root.
- Header includes:
  - export title
  - root path
  - number of included files
- Each file block includes:
  - `FILE: <relative/path>`
  - raw text content (best-effort decoding: utf-8, utf-8-sig, latin-1)

## Notes
- Prefer running from repository root to avoid accidentally exporting the wrong tree.
- Re-run after major code/docs changes so external agents get fresh context.
