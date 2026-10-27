import os
from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_test_env() -> None:
    """Load the local test file. Keep CI and process variables unchanged."""
    if not os.getenv("CI"):
        load_dotenv(REPOSITORY_ROOT / ".env", override=False)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
