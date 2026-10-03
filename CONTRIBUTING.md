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

For development and integration test variables you can also use `.env.sample.dev` as a template.

## Test

Run the unit tests without APS credentials:

```bash
uv sync --locked --group dev
uv run pytest -m "not integration" -q
```

The live connection test gets an SSA token and reads ACC tip storage:

```bash
uv run pytest -m "integration and not e2e" -v
```

Local tests load `.env` from the repository root. Existing process variables take priority.
The SDK does not load `.env` on import. In a notebook or script, call `load_dotenv()` before you read local credentials.

Use these variables for the connection test:

- `CLIENT_ID_SSA` and `CLIENT_SECRET_SSA`, or the `APS_SSA_CLIENT_ID` and `APS_SSA_CLIENT_SECRET` aliases
- `APS_SSA_SERVICE_ACCOUNT_ID`
- `APS_SSA_KEY_ID`
- `APS_SSA_PRIVATE_KEY`
- `APS_TEST_PROJECT_ID`
- `APS_TEST_SOURCE_ITEM_URN`

`APS_SSA_SCOPE` is optional. The SDK uses its default scopes if the variable is absent.
For SSA setup, read [SSA + ACC Hub Setup](docs/ssa-acc-hub-setup.md).

CI uses GitHub secrets. It does not load a local `.env` file. Unit tests run on all PRs.
Live ACC tests do not run on PRs. ACC access is not available to the current SSA test account.
For a manual connection check, select **Run workflow** and enable **Check the SSA and ACC connection**.
A manual run reports missing secret names and fails if required secrets are absent.

The full AutoCAD test creates an appbundle, an activity, a workitem, and an ACC output item.
It reads the app nickname and checks its public key. It does not replace either value.
It deletes its DA resources after the test, unless `APS_TEST_KEEP_DA_RESOURCES=true`.
The ACC output item remains in the test folder.

Run this test only in a test project:

```bash
uv run pytest -m e2e -v
```

It also needs `APS_TEST_FOLDER_ID` and `APS_TEST_SIGNING_KEY_JSON`.
The JSON must contain the private signing key that matches the app's public key.
This key is separate from the SSA JWT private key. See `.env.sample.dev`.
For CI, add the JSON as a GitHub secret. Select **Run workflow** and enable **Run the full AutoCAD test**.
The manual run fails if required secrets are absent.

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
python .agents/skills/full-llm-export/scripts/export_repo_context.py --root . --output llms-full.txt
```

Or invoke the local skill:

- `$full-llm-export`

## Road Map

- Improve type hints and docstrings
- Add ACC examples
- Add unit tests
- Code style and governance will be added in further version
