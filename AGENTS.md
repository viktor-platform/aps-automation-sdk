# AGENTS.md

> Canonical instructions file for this repository.
> `CLAUDE.md` imports this file so Codex and Claude share one instruction source.

## Repository Assessment

### What this repo is
`aps-automation-sdk` is a Python 3.11+ SDK for Autodesk Platform Services (APS) focused on Design Automation (AutoCAD/Revit), object storage (OSS), ACC Data Management integration, and optional Model Derivative translation for viewing.

Repository clarification used in this guide: Design Automation base URL is treated as US-only (`https://developer.api.autodesk.com/da/us-east/v3`).

If you want to create or modify a method of this repository, always check the autodesk documentation. Refer to "Method-to-APS Documentation Matrix" section of this document.
---

## Repository Sections and Functionalities

## 1) Package Entry (`aps_automation_sdk/__init__.py`)
Purpose: Re-exports the public API for easy imports.

Relevant exports:
- Workflow classes: `Activity`, `AppBundle`, `WorkItem`, `WorkItemAcc`, parameter classes.
- Auth/admin helpers: `get_token`, `set_nickname`, `create_bucket`, `publish_appbundle_update`, etc.
- Model Derivative helpers: `translate_file_in_oss`, `get_translation_status`, etc.

---

## 2) HTTP Core for Design Automation + OSS (`aps_automation_sdk/core.py`)
Purpose: Low-level wrappers around APS REST endpoints.

Functional groups and key methods:
- Region/URL helpers:
  - `get_da_base_url(region="US")`
- OSS signed upload/download:
  - `get_signed_s3_upload(...)`
  - `put_to_signed_url(signed_url, file_path)`
  - `complete_signed_s3_upload(...)`
  - `get_signed_s3_download(...)`
  - `dowload_from_signed_url(...)`
  - `build_oss_urn(bucketKey, objectKey)`
- AppBundle/activity management:
  - `register_appbundle(...)`
  - `upload_appbundle(upload_parameters, zip_path)`
  - `create_appbundle_alias(...)`
  - `create_activity(payload=...)`
  - `create_activity_alias(...)`
- Work item lifecycle:
  - `run_work_item(...)`
  - `run_public_work_item(...)`
  - `get_workitem_status(...)`
  - `poll_workitem_status(...)`
  - `fetch_report_content(report_url)`

Use when:
- You want direct API control without higher-level classes.

---

## 3) Auth and Administrative Helpers (`aps_automation_sdk/utils.py`)
Purpose: OAuth token retrieval + common setup/maintenance operations.

Relevant methods:
- OAuth/token:
  - `get_token(client_id, client_secret)`
- Forge app identity:
  - `set_nickname(token, nickname)`
  - `get_nickname(token)`
- Bucket and cleanup:
  - `create_bucket(bucketKey, token, ...)`
  - `delete_appbundle(appbundleId, token)`
  - `delete_activity(activityId, token)`
- AppBundle updates without downtime:
  - `create_appbundle_version(...)`
  - `move_or_create_alias(...)`
  - `publish_appbundle_update(...)`

Use when:
- You need fast bootstrap/auth and lifecycle utilities.

---

## 4) Data Models (`aps_automation_sdk/dsl.py`)
Purpose: Pydantic models for response/request payload structure.

Relevant models:
- Upload form and appbundle responses:
  - `FormData`, `UploadParameters`, `RegisterBundleResponse`
- Signed URL payloads:
  - `GetSignedS3UrlsResponse`, `CompleteUploadRequest`, `GetDownloadS3Url`

Use when:
- You need typed validation for payloads returned by APS.

---

## 5) Object-Oriented Workflow Layer (`aps_automation_sdk/classes.py`)
Purpose: High-level abstractions for bundles, activities, parameters, and work items.

### Parameter classes
- `ActivityParameter`
  - Storage helpers: `oss_keys()`, `upload_file_to_oss(...)`, `download_to(...)`, `generate_oss_urn()`
- `ActivityInputParameter`
  - `work_item_arg(token)`
- `ActivityOutputParameter`
  - `work_item_arg(token)`
- `ActivityJsonParameter`
  - `set_content(data)`, `work_item_arg()`

### Deployment classes
- `AppBundle`
  - `register()`, `upload()`, `create_alias()`, `deploy()`
- `Activity`
  - `set_revit_command_line()`
  - `set_autocad_command_line()`
  - `to_api_dict()`
  - `deploy()`

### Execution classes
- `WorkItem`
  - `build_arguments()`, `run()`, `poll()`, `execute()`

Use when:
- You want a clean end-to-end flow with minimal direct REST payload handling.

---

## 6) ACC Data Management Integration (`aps_automation_sdk/acc.py` + ACC classes)
Purpose: Resolve ACC storage IDs, create storage, and create/update ACC versions/items.

Core ACC functions (`acc.py`):
- Resolve folder/item relationships:
  - `item_from_version(...)`, `parent_folder_from_item(...)`, `resolve_parent_folder(...)`
- Tip/storage retrieval:
  - `get_item_tip_version(...)`, `find_tip_storage_id(...)`
- Write pipeline:
  - `create_storage(...)`
  - `find_item_by_name(...)`
  - `create_version_for_item(...)`
  - `create_item_with_first_version(...)`

ACC-specific parameter/work item classes (`classes.py`):
- Inputs from ACC:
  - `ActivityInputParameterAcc` (`work_item_arg_3lo(...)`)
  - `UploadActivityInputParameter` (`upload_and_create(...)`, `work_item_arg_3lo(...)`)
- Outputs to ACC:
  - `ActivityOutputParameterAcc` (`work_item_arg_3lo(...)`, `create_acc_item(...)`, `get_lineage_urn()`)
- Orchestration:
  - `WorkItemAcc.build_arguments_3lo(...)`
  - `WorkItemAcc.execute_and_finalize(...)`

Use when:
- Your inputs/outputs are in Autodesk Construction Cloud and require 3LO token handling.

---

## 7) Model Derivative Helpers (`aps_automation_sdk/model_derivative.py`)
Purpose: Trigger and monitor translation for viewer-compatible derivatives.

Relevant methods:
- URN conversion:
  - `safe_base64_encode(text)`
  - `to_md_urn(wip_urn)`
- Manifest inspection:
  - `fetch_manifest(token, object_urn)`
  - `get_revit_version_from_manifest(manifest)`
  - `get_revit_version_from_oss_object(token, bucket_key, object_key)`
- Translation:
  - `start_svf_translation_job(token, object_urn)`
  - `get_translation_status(token, object_urn)`
  - `translate_file_in_oss(...)`
  - `get_translation_info(token, object_urn)`

Use when:
- You want to visualize outputs in APS Viewer (SVF/SVF2 pipeline).

---

## 8) Signing Public Activities for ACC/3LO (`aps_automation_sdk/signing.py` + `utils.py` + `WorkItemAcc`)
Purpose: Support signed Design Automation workitem execution in 3LO/ACC workflows.

RSA signing utilities for APS Design Automation public activities.

Provides RSA key generation in Autodesk-compatible JSON format, public key
export, and PKCS#1 v1.5 SHA-256 activity-ID signing. Cryptography dependencies
are loaded lazily so the SDK remains importable without the signing extra.

Install for signing support:
- `uv add "aps-automation-sdk[signing]"`
- `pip install "aps-automation-sdk[signing]"`

End-to-end signing flow:
1. Generate key files:
   - `generate_key_file("mykey.json")`
   - `export_public_key("mykey.json", "mypublickey.json")`
2. Get 2LO token from credentials:
   - `get_token(client_id, client_secret)`
3. Upload public key to `forgeapps/me` (US-East):
   - `upload_public_key(token, public_key_json)`
4. Sign activity id:
   - `sign_activity("mykey.json", "nickname.Activity+alias")`
5. Execute signed ACC public activity:
   - `WorkItemAcc.run_public_activity(token3lo, activity_signature)`

Important connection to ACC classes:
- `WorkItemAcc.run_public_activity(...)` is the method that submits signed workitems.
- The signature generated by `sign_activity(...)` is passed as `activity_signature` to that method.

CLI and skill available:
- CLI entrypoint: `aps-automation`
  - `aps-automation signing generate --keyfile ...`
  - `aps-automation signing export --keyfile ... --pubkeyfile ...`
  - `aps-automation signing sign --keyfile ... --activity-id ...`
  - `aps-automation public-key info`
  - `aps-automation public-key upload --pubkeyfile ... [--nickname ...]`
- Skill: `.agents/skills/aps-acc-public-activity-signing/SKILL.md`
- Notebook example: `examples/Common/05_workitem_signing.ipynb`

---

## Method-to-APS Documentation Matrix

### Link Key
- [OAuth Get Token](https://aps.autodesk.com/en/docs/oauth/v2/reference/http/gettoken-POST/)
- [DA Overview](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview/)
- [DA 3LO Token Usage](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/3-legged-oauth-token-usage/)
- [DA Forge App Me GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-GET/)
- [DA Forge App Me PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-PATCH/)
- [OSS Create Bucket](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-POST/)
- [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/)
- [OSS Signed S3 Upload POST (Complete)](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-POST/)
- [OSS Signed S3 Download GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3download-GET/)
- [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/)
- [DA AppBundle Versions POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-versions-POST/)
- [DA AppBundle Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-POST/)
- [DA AppBundle Alias PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-alias_id-PATCH/)
- [DA AppBundle DELETE](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-DELETE/)
- [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/)
- [DA Activity Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-id-aliases-POST/)
- [DA Activity DELETE](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-id-DELETE/)
- [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/)
- [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/)
- [ACC Version -> Item GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-version_id-item-GET/)
- [ACC Item -> Parent GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-parent-GET/)
- [ACC Item Tip GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-tip-GET/)
- [ACC Storage POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-storage-POST/)
- [ACC Folder Contents GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-folders-folder_id-contents-GET/)
- [ACC Versions POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-POST/)
- [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/)
- [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/)
- [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/)

### `core.py`
| Method | APS reference | Note |
|---|---|---|
| `get_da_base_url` | [DA Overview](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview/) | Helper exists in SDK, but this repo documentation standardizes on US endpoint usage. |
| `get_nickname` | [DA Forge App Me GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-GET/) | Reads current DA app nickname. |
| `get_signed_s3_upload` | [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/) | Gets upload URL + `uploadKey`. |
| `put_to_signed_url` | [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/) | Uploads bytes to signed URL returned by APS. |
| `complete_signed_s3_upload` | [OSS Signed S3 Upload POST (Complete)](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-POST/) | Finalizes multipart/signed upload. |
| `build_oss_urn` | [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/) | Local URN formatter used in DA work item args. |
| `register_appbundle` | [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/) | Registers a new appbundle definition/version. |
| `upload_appbundle` | [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/) | Uploads to `uploadParameters.endpointURL` returned by APS. |
| `create_appbundle_alias` | [DA AppBundle Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-POST/) | Creates alias for appbundle version. |
| `get_signed_s3_download` | [OSS Signed S3 Download GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3download-GET/) | Gets temporary download URL for OSS object. |
| `dowload_from_signed_url` | [OSS Signed S3 Download GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3download-GET/) | Downloads bytes from previously issued signed URL. |
| `create_activity_alias` | [DA Activity Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-id-aliases-POST/) | Creates alias for activity version. |
| `create_activity` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Creates DA activity definition. |
| `run_work_item` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Submits work item. |
| `run_public_work_item` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Submits signed/public work item with signature headers/body. |
| `get_workitem_status` | [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/) | Gets current execution status/report URL. |
| `poll_workitem_status` | [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/) | Polling loop around status endpoint. |
| `fetch_report_content` | [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/) | Uses `reportUrl` returned by status payload. |

### `utils.py`
| Method | APS reference | Note |
|---|---|---|
| `get_token` | [OAuth Get Token](https://aps.autodesk.com/en/docs/oauth/v2/reference/http/gettoken-POST/) | Client credentials token for 2LO workflows. |
| `set_nickname` | [DA Forge App Me PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-PATCH/) | Sets app nickname when allowed. |
| `get_nickname` | [DA Forge App Me GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-GET/) | Reads existing nickname/public key. |
| `get_forgeapp_profile` | [DA Forge App Me GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-GET/) | Reads full `forgeapps/me` profile payload. |
| `upload_public_key` | [DA Forge App Me PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-PATCH/) | Uploads/replaces public key for signature verification. |
| `create_bucket` | [OSS Create Bucket](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-POST/) | Creates OSS bucket for inputs/outputs. |
| `delete_appbundle` | [DA AppBundle DELETE](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-DELETE/) | Deletes appbundle. |
| `delete_activity` | [DA Activity DELETE](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-id-DELETE/) | Deletes activity. |
| `create_appbundle_version` | [DA AppBundle Versions POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-versions-POST/) | Creates new appbundle version and upload params. |
| `move_or_create_alias` | [DA AppBundle Alias PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-alias_id-PATCH/) and [DA AppBundle Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-POST/) | Patch existing alias or create if missing. |
| `publish_appbundle_update` | [DA AppBundle Versions POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-versions-POST/) and [DA AppBundle Alias PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-alias_id-PATCH/) | Composite flow: version + upload + alias move. |

### `signing.py`
| Method | APS reference | Note |
|---|---|---|
| `generate_key_file` | [DA 3LO Token Usage](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/3-legged-oauth-token-usage/) | Generates local RSA private/public key material in signer-compatible JSON format. |
| `export_public_key` | [DA Forge App Me PATCH](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/forgeapps-me-PATCH/) | Exports `Exponent` and `Modulus` JSON used for upload. |
| `sign_activity` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Signs full activity id for signed/public workitem submission. |

### `classes.py` (workflow layer)
| Method | APS reference | Note |
|---|---|---|
| `ActivityParameter.oss_keys` | [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/) | Local validation helper for OSS key pair. |
| `ActivityParameter.ensure_bucket` | [OSS Create Bucket](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-POST/) | Creates bucket on-demand before upload. |
| `ActivityParameter.upload_file_to_oss` | [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/) and [OSS Signed S3 Upload POST (Complete)](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-POST/) | Full signed upload flow. |
| `ActivityParameter.download_to` | [OSS Signed S3 Download GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3download-GET/) | Retrieves output object to local file. |
| `ActivityParameter.generate_oss_urn` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Builds argument URL as OSS URN. |
| `ActivityParameter.to_api_param` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Maps SDK parameter to activity schema. |
| `ActivityInputParameter.work_item_arg` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Input argument descriptor for work item. |
| `ActivityOutputParameter.work_item_arg` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Output argument descriptor for work item. |
| `ActivityJsonParameter.work_item_arg` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Inline `data:` JSON URL argument. |
| `ActivityJsonParameter.set_content` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Local payload setter for inline JSON argument. |
| `Activity.param_map` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Internal mapper for `parameters` payload. |
| `Activity.short_appbundle_id` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Helper for `commandLine` bundle token format. |
| `Activity.set_revit_command_line` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Sets Revit command line template. |
| `Activity.set_autocad_command_line` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Sets AutoCAD command line template. |
| `Activity.to_api_dict` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) | Builds activity payload body. |
| `Activity.deploy` | [DA Activities POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-POST/) and [DA Activity Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/activities-id-aliases-POST/) | Create activity + alias v1. |
| `AppBundle.register` | [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/) | Registers appbundle version. |
| `AppBundle.upload` | [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/) | Uploads binary via APS-provided form endpoint. |
| `AppBundle.create_alias` | [DA AppBundle Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-POST/) | Creates appbundle alias. |
| `AppBundle.deploy` | [DA AppBundles POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-POST/) and [DA AppBundle Aliases POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/appbundles-id-aliases-POST/) | Register + upload + alias flow. |
| `WorkItem.build_arguments` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Merges all parameter args into request body. |
| `WorkItem.run` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Submits work item and returns ID. |
| `WorkItem.poll` | [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/) | Polls work item state. |
| `WorkItem.execute` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) and [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/) | Run + poll convenience flow. |
| `ActivityInputParameterAcc.get_acc_storage_url` | [ACC Item Tip GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-tip-GET/) | Resolves latest storage ID from lineage. |
| `ActivityInputParameterAcc.work_item_arg_3lo` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | ACC storage URL as input argument. |
| `UploadActivityInputParameter.upload_and_create` | [ACC Storage POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-storage-POST/), [OSS Signed S3 Upload GET](https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-bucketKey-objects-objectName-signeds3upload-GET/), [ACC Versions POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-POST/), [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/) | Upload local file and ensure ACC item/version exists. |
| `UploadActivityInputParameter.work_item_arg_3lo` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Returns 3LO argument after upload/create. |
| `ActivityOutputParameterAcc.work_item_arg_3lo` | [ACC Storage POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-storage-POST/) | Creates target ACC storage and returns work item arg. |
| `ActivityOutputParameterAcc.create_acc_item` | [ACC Folder Contents GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-folders-folder_id-contents-GET/), [ACC Versions POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-POST/), [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/) | Finalizes storage into new version/item. |
| `ActivityOutputParameterAcc.get_lineage_urn` | [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/) | Returns lineage URN cached from finalize step. |
| `WorkItemAcc.build_arguments_3lo` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Builds request body for 3LO ACC scenario. |
| `WorkItemAcc.run_public_activity` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Submits signed/public activity work item. |
| `WorkItemAcc.execute_and_finalize` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/), [DA WorkItems GET](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-id-GET/), [ACC Versions POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-POST/), [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/) | End-to-end ACC pipeline. |

### `acc.py`
| Method | APS reference | Note |
|---|---|---|
| `bearer` | [DA Overview](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview/) | Local header helper, includes optional region header. |
| `item_from_version` | [ACC Version -> Item GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-version_id-item-GET/) | Resolves item from version URN. |
| `parent_folder_from_item` | [ACC Item -> Parent GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-parent-GET/) | Resolves folder from item. |
| `resolve_parent_folder` | [ACC Version -> Item GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-version_id-item-GET/) and [ACC Item -> Parent GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-parent-GET/) | Convenience chain. |
| `get_item_tip_version` | [ACC Item Tip GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-tip-GET/) | Reads current tip version payload. |
| `find_tip_storage_id` | [ACC Item Tip GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-item_id-tip-GET/) | Extracts storage object ID from tip payload. |
| `create_storage` | [ACC Storage POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-storage-POST/) | Creates upload target storage in ACC folder. |
| `to_data_url_json` | [DA WorkItems POST](https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST/) | Utility for inline JSON arguments. |
| `find_item_by_name` | [ACC Folder Contents GET](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-folders-folder_id-contents-GET/) | Finds existing item lineage by display name. |
| `create_version_for_item` | [ACC Versions POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-versions-POST/) | Adds version to existing ACC item. |
| `create_item_with_first_version` | [ACC Items POST](https://aps.autodesk.com/en/docs/data/v1/reference/http/projects-project_id-items-POST/) | Creates brand-new item + first version. |

### `model_derivative.py`
| Method | APS reference | Note |
|---|---|---|
| `safe_base64_encode` | [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/) | Helper for URN-safe encoding. |
| `to_md_urn` | [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/) | Converts OSS object URN to MD URN format. |
| `get_revit_version_from_manifest` | [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | Local parser for manifest payload. |
| `fetch_manifest` | [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | Fetches translation manifest. |
| `get_revit_version_from_oss_object` | [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/) and [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | Triggers translation, inspects manifest for RVT version. |
| `start_svf_translation_job` | [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/) | Starts SVF2 translation. |
| `get_translation_status` | [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | Checks translation state/progress. |
| `translate_file_in_oss` | [Model Derivative Job POST](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/job-POST/) and [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | End-to-end translation + polling flow. |
| `get_translation_info` | [Model Derivative Manifest GET](https://aps.autodesk.com/en/docs/model-derivative/v2/reference/http/designdata-urn-manifest-GET/) | Summarizes manifest metadata. |
