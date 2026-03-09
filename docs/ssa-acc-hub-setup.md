# SSA + ACC Hub Setup Guide

This guide sets up a Secure Service Account (SSA) robot user so the SDK can mint a real 3-legged token and run ACC + Design Automation integration tests without changing existing `WorkItemAcc` flows.

## 1) One-time SSA setup in APS

1. Create a **Server-to-Server** APS app and keep its `Client ID` and `Client Secret`.
2. In SSA Manager, create a **Service Account (robot)** and generate a key.
3. Save these values securely:
- `APS_SSA_SERVICE_ACCOUNT_ID` (Oxygen ID)
- `APS_SSA_KEY_ID`
- `APS_SSA_PRIVATE_KEY` (returned once at key creation)

Operational guidance:
- Treat robot/key setup as infrastructure.
- Do not create or rotate keys during test runs.
- Rotate keys in a controlled maintenance workflow and update secrets first.

## 2) Provision to ACC hub

1. Open ACC Account Admin and go to **Custom Integrations**.
2. Add your APS app `Client ID` as a custom integration.
3. Invite the robot email/user to the target ACC project.
4. Grant permissions at project and folder level for the test folder:
- Read item/version metadata
- Create storage
- Create items and versions
- Write outputs

Recommended: use a dedicated ACC test project and folder for live tests.

## 3) Configure environment

Set the following values in your CI secrets or `.env`:

```ini
CLIENT_ID_SSA=
CLIENT_SECRET_SSA=
APS_SSA_SERVICE_ACCOUNT_ID=
APS_SSA_KEY_ID=
APS_SSA_PRIVATE_KEY=
APS_SSA_SCOPE=code:all data:read data:write data:create data:search

APS_TEST_PROJECT_ID=
APS_TEST_FOLDER_ID=
APS_TEST_SOURCE_VERSION_URN=
APS_TEST_SOURCE_ITEM_URN=

APS_TEST_PUBLIC_ACTIVITY_ALIAS=
APS_TEST_PUBLIC_ACTIVITY_SIGNATURE=
APS_TEST_WORKITEM_CONFIG_JSON=
```

Notes:
- `CLIENT_ID_SSA` and `CLIENT_SECRET_SSA` must come from your **Server-to-Server** app.
- Legacy aliases `APS_SSA_CLIENT_ID` and `APS_SSA_CLIENT_SECRET` are also supported.
- `APS_SSA_PRIVATE_KEY` may be stored as a single line with escaped newlines (`\n`).
- `code:all` is required for Automation API endpoints.

## 4) Preflight checklist

Before running live tests:

- SSA robot user exists and is enabled.
- Key ID matches the active key used for signing JWT assertions.
- Robot has been invited to the ACC project.
- Folder permissions allow read/write/version operations.
- `APS_SSA_SCOPE` includes both data scopes and `code:all`.
- Test `source item/version` URNs belong to the same project.

## 5) Validate token minting

Mint a 3LO token from SSA env vars:

```bash
aps-automation ssa token
```

If token minting works, run integration tests:

```bash
pytest -m integration
```

Run e2e workitem test only when activity alias/signature are configured:

```bash
pytest -m e2e
```

## 6) Troubleshooting matrix

| Symptom | Likely cause | Fix |
|---|---|---|
| `401/400` on `/authentication/v2/token` | JWT claims invalid (`iss`, `sub`, `aud`, `exp`) | Verify `iss=CLIENT_ID_SSA`, `sub=APS_SSA_SERVICE_ACCOUNT_ID`, `aud=https://developer.api.autodesk.com/authentication/v2/token`, `exp<=300s` |
| `kid`/signature errors | Wrong key id or private key | Ensure `APS_SSA_KEY_ID` and `APS_SSA_PRIVATE_KEY` are from the same SSA key |
| `{"Authorization":["No public key can be found for this client."]}` | Public key was uploaded for a different APS app than the one behind the runtime 3LO token | Upload the signing public key to `forgeapps/me` for the same app used to mint the runtime token (`CLIENT_ID_SSA` / `APS_SSA_CLIENT_ID`). |
| ACC `403` | Robot lacks ACC membership or folder rights | Invite robot to project and grant folder permissions |
| ACC `404` for URNs | Wrong project/folder/item/version IDs | Re-check `APS_TEST_PROJECT_ID`, source URNs, and folder ID |
| DA workitem rejected for scope | Missing `code:all` | Add `code:all` to `APS_SSA_SCOPE` |
| E2E fails on signature | Wrong activity signature or alias | Re-sign full `nickname.Activity+alias` and verify alias matches deployed activity |

## 7) APS references

- SSA Getting Started (create/provision/token): https://aps.autodesk.com/en/docs/ssa/v1/tutorials/getting-started-with-ssa/
- SSA service-account management: https://aps.autodesk.com/en/docs/ssa/v1/tutorials/service-account-management/
- OAuth token endpoint: https://aps.autodesk.com/en/docs/oauth/v2/reference/http/gettoken-POST/
- Automation scope enforcement update (`code:all`): https://aps.autodesk.com/blog/design-automation-api-enforcing-oauth-scope-deadline-extension-march-31-2025
