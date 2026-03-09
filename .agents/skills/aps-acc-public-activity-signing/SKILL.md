---
name: aps-acc-public-activity-signing
description: Power skill for APS Design Automation public activity signing with full CLI + Python workflows, nickname/public-key setup, and signed ACC workitem execution guidance.
---

# APS ACC Public Activity Signing

## Purpose
Use this skill when users need a complete, reliable path to run **signed public activities** in APS Design Automation, including ACC-integrated execution.

## Core Capabilities
- Validate credential readiness from `.env` / environment.
- Generate Autodesk-compatible RSA private key JSON.
- Export APS uploadable public key JSON.
- **Register (set/change) the APS app nickname** and upload the public key to `forgeapps/me` via a single `PATCH` call (US-East DA endpoint).
- Sign activity IDs (`nickname.Activity+alias`) using RSA PKCS#1 v1.5 SHA-256.
- Connect signing outputs to ACC orchestration (`WorkItemAcc.run_public_activity`).
- Provide equivalent **CLI** and **Python notebook** paths.
- Provide cleanup guidance (delete test bundle/activity and local keys).

## CLI Operations Included
Yes. This skill explicitly supports these CLI operations:
- `aps-automation signing generate`
- `aps-automation signing export`
- `aps-automation signing sign`
- `aps-automation public-key info`
- `aps-automation public-key upload`

The skill uses these commands as the default operational path when users ask for CLI-first execution.

## Credential Resolution Contract
1. Prefer `.env` in repo root via `load_dotenv(override=False)`.
2. If missing, use shell environment (`CLIENT_ID`, `CLIENT_SECRET`).
3. If still missing, ask user for credentials or ask them to create `.env`.

## Agent Key Decision Protocol
Before generating any keys, **always ask the user**:

> "Do you already have a private key file (`mykey.json` or similar), or should I generate a new one?"

- If the user has existing keys → skip `signing generate` and `signing export`; ask for the paths to `--keyfile` and `--pubkeyfile`.
- If no keys exist → proceed with generation, then immediately remind the user to protect the private key file (see Key Safety Rules).

## Standard Preflight
Run this first to confirm credentials can mint a token:
```bash
python .agents/skills/aps-acc-public-activity-signing/scripts/check_env_and_get_token.py
```

## Installation
```bash
uv add "aps-automation-sdk[signing]"
# or
pip install "aps-automation-sdk[signing]"
```

## Workflow A: CLI End-to-End
1. Generate private key:
```bash
aps-automation signing generate --keyfile mykey.json
```
2. Export public key:
```bash
aps-automation signing export --keyfile mykey.json --pubkeyfile mypublickey.json
```
3. **Register** your APS app nickname and upload the public key in one step (recommended):
```bash
aps-automation public-key upload --pubkeyfile mypublickey.json --nickname <nickname>
```
> `--nickname` sends `PATCH /forgeapps/me` to **set/change the nickname** on your APS app, then uploads the public key in the same request. Without `--nickname`, only the key is uploaded and the nickname stays unchanged.
4. Sign activity ID:
```bash
aps-automation signing sign --keyfile mykey.json --activity-id "<nickname>.<activity_alias>+<tag>"
```
5. Submit signed workitem with existing SDK flow (`WorkItemAcc.run_public_activity`).

## Prompt Library (What Users Can Ask)
Use these prompts directly with the agent:

1. `Use $aps-acc-public-activity-signing and run the full CLI flow from my .env.`
2. `Use $aps-acc-public-activity-signing to generate keys and export the public key only.`
3. `Use $aps-acc-public-activity-signing to upload my public key with nickname <nickname>.`
4. `Use $aps-acc-public-activity-signing to sign activity <nickname>.<activity_alias>+<tag>.`
5. `Use $aps-acc-public-activity-signing and verify forgeapps/me profile before and after key upload.`
6. `Use $aps-acc-public-activity-signing and show CLI + Python parity for signing the same activity id.`
7. `Use $aps-acc-public-activity-signing and troubleshoot why public-key upload fails in my environment.`
8. `Use $aps-acc-public-activity-signing and validate if my nickname format is APS-compliant.`
9. `Use $aps-acc-public-activity-signing and wire the generated signature into WorkItemAcc.run_public_activity.`
10. `Use $aps-acc-public-activity-signing and clean local key files after signing.`

## Workflow B: Python / Notebook End-to-End
```python
import json
from aps_automation_sdk import (
    generate_key_file,
    export_public_key,
    sign_activity,
    get_token,
    set_nickname,
    upload_public_key,
)

generate_key_file("mykey.json")
export_public_key("mykey.json", "mypublickey.json")

with open("mypublickey.json", "r", encoding="utf-8") as f:
    public_key = json.load(f)

token = get_token("CLIENT_ID", "CLIENT_SECRET")
nickname = set_nickname(token, "<nickname>")  # nickname-first flow
upload_public_key(token=token, public_key=public_key)

signature = sign_activity("mykey.json", f"{nickname}.<activity_alias>+<tag>")
```

## Workflow C: ACC Signed Submission Link
Use signing output directly with ACC classes:
- Build `WorkItemAcc` arguments as usual.
- Use signed activity execution call:
  - `WorkItemAcc.run_public_activity(token3lo=..., activity_signature=...)`
- Keep signed request deterministic (`x-ads-workitem-signature` + `signatures` fields).

## Recommended Operational Order
1. Set nickname first (or nickname + public key in same `PATCH /forgeapps/me`).
2. Create AppBundle.
3. Create Activity.
4. Sign activity ID.
5. Submit signed workitem.

## Troubleshooting Playbook
- `missing_credentials`: create `.env` with `CLIENT_ID`, `CLIENT_SECRET`.
- `nickname invalid`: enforce APS regex (letters, numbers, underscore, <= 20 chars).
- `JSONDecodeError` on key upload: handle empty/non-JSON PATCH response and fetch profile after PATCH.
- `409 nickname`: app already has DA data; use existing nickname or clean DA data first.
- `signature rejected`: confirm signed string exactly matches executed activity alias.

## Key Safety Rules
- **Never commit private key JSON** to version control.
- **Never print private key fields** in logs or notebook output.
- Prefer environment-scoped keys (dev/staging/prod separated).
- After generating keys, always recommend the user either:
  1. Add the key directory/files to `.gitignore`, **or**
  2. Move them to a safe location outside the repo and note the path.

Recommended `.gitignore` entries:
```
keys/
*.json  # if keys live at repo root
mykey*.json
```

## Constraints
- Treat `forgeapps/me` as **US-East-only** for this package.
- Do not add debug `print/pprint` side effects in SDK request helpers.
