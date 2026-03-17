import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from aps_automation_sdk import (
    Activity,
    ActivityInputParameter,
    ActivityInputParameterAcc,
    ActivityOutputParameter,
    ActivityOutputParameterAcc,
    AppBundle,
    WorkItemAcc,
    delete_activity,
    delete_appbundle,
    export_public_key,
    get_forgeapp_profile,
    generate_key_file,
    get_token,
    set_nickname,
    sign_activity,
    upload_public_key,
)
from aps_automation_sdk.core import get_workitem_status
from aps_automation_sdk.ssa import SsaConfig, get_ssa_3lo_token


def clean(value: str) -> str:
    return value.strip().strip('"').strip("'")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return clean(value)


def is_terminal_status(status: str) -> bool:
    normalized = status.strip().lower()
    return normalized == "success" or normalized == "cancelled" or normalized.startswith("failed")


@pytest.mark.integration
@pytest.mark.e2e
def test_ssa_only_autocad_list_layers_end_to_end(tmp_path: Path) -> None:
    """
    End-to-end live test using only SSA app credentials:
    1) Generate signing keys + upload public key to SSA app profile
    2) Deploy AutoCAD appbundle/activity with SSA app 2LO token
    3) Sign activity id
    4) Mint SSA-backed 3LO token
    5) Run public WorkItemAcc with ACC input/output
    6) Finalize output item in ACC
    """
    load_dotenv(override=False)

    bundle_zip = (Path(__file__).resolve().parents[1] / "fixtures" / "autocad_list_layers" / "ListLayers.zip")
    if not bundle_zip.exists():
        raise RuntimeError(f"Missing test fixture bundle: {bundle_zip}")

    project_id = require_env("APS_TEST_PROJECT_ID")
    folder_id = require_env("APS_TEST_FOLDER_ID")
    source_item_urn = require_env("APS_TEST_SOURCE_ITEM_URN")

    # Single app credentials for both deploy/public-key upload and runtime token minting
    client_id_ssa = require_env("APS_SSA_CLIENT_ID")
    client_secret_ssa = require_env("APS_SSA_CLIENT_SECRET")
    service_account_id = require_env("APS_SSA_SERVICE_ACCOUNT_ID")
    key_id = require_env("APS_SSA_KEY_ID")
    private_key = require_env("APS_SSA_PRIVATE_KEY").replace("\\n", "\n")
    ssa_scope = require_env("APS_SSA_SCOPE")

    suffix = uuid.uuid4().hex[:8]
    app_bundle_id = f"it_listlayers_{suffix}"
    activity_id = f"it_listlayers_activity_{suffix}"
    alias = "dev"
    output_name = f"it-layers-{suffix}.txt"
    # APS nickname constraints: <=20 chars, [a-zA-Z0-9_]
    requested_nickname = "myUniqueNick_123_SSA"

    token2lo = ""

    try:
        print("Getting 2LO token from SSA app credentials", flush=True)
        token2lo = get_token(client_id_ssa, client_secret_ssa)
        nickname = set_nickname(token2lo, requested_nickname)
        print(f"Using nickname: {nickname}", flush=True)
        assert nickname == requested_nickname, (
            f"Expected nickname '{requested_nickname}', got '{nickname}'. "
            "Clear existing DA resources or use a different app so nickname can be set."
        )

        print("Generating signing key pair", flush=True)
        private_key_path = tmp_path / "signing_key.json"
        public_key_path = tmp_path / "signing_public.json"
        generate_key_file(str(private_key_path))
        export_public_key(str(private_key_path), str(public_key_path))

        print("Uploading public key to forgeapps/me for SSA app", flush=True)
        with public_key_path.open("r", encoding="utf-8") as f:
            public_key: dict[str, Any] = json.load(f)
        upload_response = upload_public_key(token2lo, public_key)
        print("Verifying uploaded public key on forgeapps/me", flush=True)
        profile = upload_response if isinstance(upload_response, dict) else get_forgeapp_profile(token2lo)
        profile_public_key = profile.get("publicKey") if isinstance(profile, dict) else None
        assert isinstance(profile_public_key, dict), f"Missing publicKey in forgeapps/me response: {profile}"
        assert profile_public_key.get("Exponent") == public_key.get("Exponent"), "Uploaded public key Exponent mismatch"
        assert profile_public_key.get("Modulus") == public_key.get("Modulus"), "Uploaded public key Modulus mismatch"

        print("Deploying AutoCAD appbundle", flush=True)
        bundle = AppBundle(
            appBundleId=app_bundle_id,
            engine="Autodesk.AutoCAD+24_3",
            alias=alias,
            zip_path=str(bundle_zip),
            description="Integration e2e (SSA-only): AutoCAD list layers",
        )
        bundle.deploy(token2lo)
        appbundle_full_alias = f"{nickname}.{app_bundle_id}+{alias}"

        print("Creating and deploying activity", flush=True)
        input_dwg = ActivityInputParameter(
            name="InputDwg",
            localName="Input.dwg",
            verb="get",
            description="Input drawing file",
            required=True,
            is_engine_input=True,
        )
        output_file = ActivityOutputParameter(
            name="result",
            localName="layers.txt",
            verb="put",
            description="Layer list text output",
        )
        activity = Activity(
            id=activity_id,
            parameters=[input_dwg, output_file],
            engine="Autodesk.AutoCAD+24_3",
            appbundle_full_name=appbundle_full_alias,
            description="E2E test activity: List layers from DWG in ACC (SSA-only creds)",
            alias=alias,
            script='(command "LISTLAYERS")\n',
        )
        activity.set_autocad_command_line()
        activity.deploy(token2lo)
        activity_full_alias = f"{nickname}.{activity_id}+{alias}"

        print("Signing activity id", flush=True)
        activity_signature = sign_activity(str(private_key_path), activity_full_alias)

        print("Minting SSA 3LO token", flush=True)
        token3lo = get_ssa_3lo_token(
            SsaConfig(
                client_id=client_id_ssa,
                client_secret=client_secret_ssa,
                service_account_id=service_account_id,
                key_id=key_id,
                private_key=private_key,
                scope=ssa_scope,
            )
        )
        print(f"token3lo prefix: {token3lo[:20]}...", flush=True)

        print("Building ACC input/output arguments", flush=True)
        input_acc = ActivityInputParameterAcc(
            name="InputDwg",
            localName="input.dwg",
            verb="get",
            description="Input DWG from ACC",
            required=True,
            is_engine_input=True,
            project_id=project_id,
            linage_urn=source_item_urn,
        )
        output_acc = ActivityOutputParameterAcc(
            name="result",
            localName="layers.txt",
            verb="put",
            description="Layer list output",
            folder_id=folder_id,
            project_id=project_id,
            file_name=output_name,
        )

        workitem = WorkItemAcc(
            parameters=[input_acc, output_acc],
            activity_full_alias=activity_full_alias,
        )

        print("Submitting public workitem", flush=True)
        workitem_id = workitem.run_public_activity(
            token3lo=token3lo,
            activity_signature=activity_signature,
        )
        print(f"workitem_id: {workitem_id}", flush=True)

        print("Polling workitem status", flush=True)
        deadline = time.time() + 1200
        status_payload: dict[str, Any] = {}
        while time.time() < deadline:
            status_payload = get_workitem_status(workitem_id, token3lo)
            status = str(status_payload.get("status", ""))
            print(f"workitem status: {status}", flush=True)
            if is_terminal_status(status):
                break
            time.sleep(10)

        assert status_payload.get("status") == "success", status_payload

        print("Finalizing output in ACC", flush=True)
        created_item = output_acc.create_acc_item(token3lo)
        assert created_item["data"]["type"] == "items"
        print(f"created ACC item lineage: {created_item['data']['id']}", flush=True)
        assert output_acc.get_lineage_urn() == created_item["data"]["id"]

        downloaded_output = tmp_path / output_name
        print(f"Downloading ACC output to {downloaded_output}", flush=True)
        output_acc.download_to(str(downloaded_output), token3lo)
        assert downloaded_output.exists()
        assert downloaded_output.read_text(encoding="utf-8").strip()

        print("E2E flow completed successfully", flush=True)

    finally:
        keep_resources = clean(os.getenv("APS_TEST_KEEP_DA_RESOURCES", "false")).lower() in {"1", "true", "yes"}
        if keep_resources or not token2lo:
            return

        print("cleanup: deleting activity/appbundle", flush=True)
        try:
            delete_activity(activity_id, token2lo)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            print(f"cleanup warning (activity): {exc}", flush=True)

        try:
            delete_appbundle(app_bundle_id, token2lo)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            print(f"cleanup warning (appbundle): {exc}", flush=True)
