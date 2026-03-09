from __future__ import annotations

import os

from dotenv import load_dotenv
import pytest

from aps_automation_sdk.acc import find_tip_storage_id, get_item_tip_version
from aps_automation_sdk.ssa import SsaConfig, get_ssa_3lo_token


def clean(value: str) -> str:
    return value.strip().strip('"').strip("'")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return clean(value)


@pytest.mark.integration
def test_ssa_connection() -> None:
    """Live check: mint SSA token and resolve ACC tip/storage."""
    load_dotenv(override=False)

    project_id = require_env("APS_TEST_PROJECT_ID")
    source_item_urn = require_env("APS_TEST_SOURCE_ITEM_URN")

    token3lo = get_ssa_3lo_token(SsaConfig.from_env())
    tip = get_item_tip_version(
        project_id=project_id,
        item_lineage_urn=source_item_urn,
        token=token3lo,
    )
    storage_id = find_tip_storage_id(tip)

    assert tip["data"]["type"] == "versions"
    assert tip["data"]["id"]
    assert storage_id.startswith("urn:adsk.objects:os.object:")
