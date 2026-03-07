# Contributing to APS Automation SDK

## Installation

### Prerequisites

1. **Install uv** (fast Python package manager):
   ```powershell
   pip install uv
   ```
   
   For other installation methods, see: https://docs.astral.sh/uv/getting-started/installation/

2. **Clone or download this repository**

### Install the SDK

From the project root directory:

```powershell
# Install the package in editable mode
uv venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
uv pip install -e .
```

**Note:** When running the Jupyter notebook in VS Code for the first time, you may be prompted to install the `ipykernel` package. Click "Install" or run:

```powershell
uv add ipykernel
```

## Configuration

Create a `.env` file in the project root with your APS credentials:

```ini
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```

Get your credentials from the [APS Developer Portal](https://aps.autodesk.com/).

## AI-Assisted Development

You can use AI agents to speed up development, but they must always use repository context and APS documentation context.

### Mandatory context files

- `AGENTS.md` (canonical instruction source for this repo)
- `CLAUDE.md` (imports `AGENTS.md`)
- `AGENTS.md` → [`## Method-to-APS Documentation Matrix`](AGENTS.md#method-to-aps-documentation-matrix)

Before changing code, make sure the agent reads these files and follows the links/references they contain (especially APS method references in `AGENTS.md`).

### APS documentation requirement

If a method is added or modified, verify it against Autodesk APS docs before finalizing changes.
Use `AGENTS.md` → [`## Method-to-APS Documentation Matrix`](AGENTS.md#method-to-aps-documentation-matrix) as the required mapping source.

### Refresh repository context for agents

If you add or modify methods, regenerate `llms-full.txt` so external agents always have fresh context.

Run:

```bash
python skills/full-llm-export/scripts/export_repo_context.py --root . --output llms-full.txt
```

Or invoke the local skill:

- `$full-llm-export`

## Road Map

- Improve type hints and docstrings
- Add ACC examples
- Add unit tests
- Code style and governance will be added in further version
