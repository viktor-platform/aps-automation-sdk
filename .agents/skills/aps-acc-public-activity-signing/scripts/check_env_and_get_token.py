#!/usr/bin/env python3
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from aps_automation_sdk import get_token


def main() -> int:
    load_dotenv(override=False)

    client_id = os.getenv("CLIENT_ID", "").strip()
    client_secret = os.getenv("CLIENT_SECRET", "").strip()

    missing: list[str] = []
    if not client_id:
        missing.append("CLIENT_ID")
    if not client_secret:
        missing.append("CLIENT_SECRET")

    if missing:
        env_path = Path.cwd() / ".env"
        payload = {
            "ok": False,
            "reason": "missing_credentials",
            "missing": missing,
            "message": f"Missing {', '.join(missing)} in .env or environment.",
            "next_step": f"Create {env_path} with CLIENT_ID and CLIENT_SECRET.",
        }
        print(json.dumps(payload, indent=2))
        return 1

    try:
        token = get_token(client_id=client_id, client_secret=client_secret)
    except Exception as exc:
        payload = {
            "ok": False,
            "reason": "token_request_failed",
            "message": str(exc),
            "next_step": "Verify CLIENT_ID/CLIENT_SECRET values and APS app permissions.",
        }
        print(json.dumps(payload, indent=2))
        return 2

    payload = {
        "ok": True,
        "token": token,
        "message": "Token generated successfully from env/.env credentials.",
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
