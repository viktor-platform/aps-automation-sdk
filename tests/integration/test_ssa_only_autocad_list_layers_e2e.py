import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

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
    get_forgeapp_profile,
    get_token,
    sign_activity,
)
from aps_automation_sdk.core import get_workitem_status
from aps_automation_sdk.ssa import SsaConfig, get_ssa_3lo_token
from aps_automation_sdk.signing import load_private_key_data
from .config import load_test_env, require_env



def is_terminal_status(status: str) -> bool:
    normalized = status.strip().lower()
    return normalized == "success" or normalized == "cancelled" or normalized.startswith("failed")


@pytest.mark.integration
@pytest.mark.e2e
def test_ssa_only_autocad_list_layers_end_to_end(tmp_path: Path) -> None:
    """
    End-to-end live test using only SSA app credentials:
    1) Check the existing signing key against the SSA app profile
    2) Deploy AutoCAD appbundle/activity with SSA app 2LO token
    3) Sign activity id
    4) Mint SSA-backed 3LO token
    5) Run public WorkItemAcc with ACC input/output
    6) Finalize output item in ACC
    """
    load_test_env()

    bundle_zip = (Path(__file__).resolve().parents[1] / "fixtures" / "autocad_list_layers" / "ListLayers.zip")
    if not bundle_zip.exists():
        raise RuntimeError(f"Missing test fixture bundle: {bundle_zip}")

    project_id = require_env("APS_TEST_PROJECT_ID")
    folder_id = require_env("APS_TEST_FOLDER_ID")
    source_item_urn = require_env("APS_TEST_SOURCE_ITEM_URN")

    config = SsaConfig.from_env()
    signing_key_json = require_env("APS_TEST_SIGNING_KEY_JSON")

    suffix = uuid.uuid4().hex[:8]
    app_bundle_id = f"it_listlayers_{suffix}"
    activity_id = f"it_listlayers_activity_{suffix}"
    alias = "dev"
    output_name = f"it-layers-{suffix}.txt"

    token2lo = ""

    try:
        print("Getting 2LO token from SSA app credentials", flush=True)
        token2lo = get_token(config.client_id, config.client_secret)
        profile = get_forgeapp_profile(token2lo)
        nickname = profile.get("nickname")
        assert isinstance(nickname, str) and nickname, "Set the app nickname before this test."

        private_key_path = tmp_path / "signing_key.json"
        private_key_path.write_text(signing_key_json, encoding="utf-8")
        private_key_path.chmod(0o600)
        key_data = load_private_key_data(str(private_key_path))
        public_key = {name: key_data[name] for name in ("Exponent", "Modulus")}
        assert profile.get("publicKey") == public_key, "The signing key must match the app public key."

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
        token3lo = get_ssa_3lo_token(config)

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
        keep_resources = os.getenv("APS_TEST_KEEP_DA_RESOURCES", "false").strip().lower() in {"1", "true", "yes"}
        if not keep_resources and token2lo:
            print("cleanup: deleting activity/appbundle", flush=True)
            try:
                delete_activity(activity_id, token2lo)
            except Exception as exc:  # pragma: no cover - best effort cleanup
                print(f"cleanup warning (activity): {exc}", flush=True)

            try:
                delete_appbundle(app_bundle_id, token2lo)
            except Exception as exc:  # pragma: no cover - best effort cleanup
                print(f"cleanup warning (appbundle): {exc}", flush=True)
