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

## Road Map

- Improve type hints and docstrings
- Add ACC examples
- Add unit tests
- Code style and governance will be added in further version
