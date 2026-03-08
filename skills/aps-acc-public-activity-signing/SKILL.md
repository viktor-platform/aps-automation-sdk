---
name: aps-acc-public-activity-signing
description: End-to-end workflow for Autodesk APS Design Automation workitem signing using this SDK. Use when asked to generate RSA signer keys, export/upload public key to forgeapps/me, sign activity IDs, or execute signed 3LO workitems from Python or CLI.
---

# APS ACC Public Activity Signing

## Overview
Use this skill to implement or guide APS Design Automation 3LO signing with SDK-native helpers and CLI commands.

## Workflow
1. Check env and try to generate token automatically:
```bash
python skills/aps-acc-public-activity-signing/scripts/check_env_and_get_token.py
```
If this fails with `missing_credentials`, ask user to create `.env` with `CLIENT_ID` and `CLIENT_SECRET`.
As a last resort, ask user directly for `CLIENT_ID` and `CLIENT_SECRET`.

2. Install signing extra:
```bash
uv add "aps-automation-sdk[signing]"
# or
pip install "aps-automation-sdk[signing]"
```
3. Generate private key JSON:
```bash
aps-automation signing generate --keyfile mykey.json
```
4. Export public key JSON:
```bash
aps-automation signing export --keyfile mykey.json --pubkeyfile mypublickey.json
```
5. Upload public key to `forgeapps/me` (`us-east`):
```bash
aps-automation public-key upload --pubkeyfile mypublickey.json
```
6. Sign activity ID:
```bash
aps-automation signing sign --keyfile mykey.json --activity-id "nickname.Activity+prod"
```
7. Submit signed workitem through existing SDK flow (`WorkItemAcc.run_public_activity`).

## Python Helpers
```python
import json
from aps_automation_sdk import (
    generate_key_file,
    export_public_key,
    sign_activity,
    get_token,
    upload_public_key,
)

generate_key_file("mykey.json")
export_public_key("mykey.json", "mypublickey.json")

with open("mypublickey.json", "r", encoding="utf-8") as f:
    public_key = json.load(f)

token = get_token("CLIENT_ID", "CLIENT_SECRET")
upload_public_key(token=token, public_key=public_key)

signature = sign_activity("mykey.json", "nickname.Activity+prod")
```

## Constraints
- Treat `forgeapps/me` as US-East-only.
- Do not log or print private key material.
- Do not introduce debug output in request methods.
