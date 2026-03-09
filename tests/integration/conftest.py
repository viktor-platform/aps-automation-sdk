import os
import tempfile
from pathlib import Path
from typing import Callable

import pytest

from aps_automation_sdk.core import (
    complete_signed_s3_upload,
    get_signed_s3_upload,
    put_to_signed_url,
)
from aps_automation_sdk.ssa import SsaConfig, get_ssa_3lo_token


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not set")
    return value


@pytest.fixture(scope="session")
def token3lo() -> str:
    return get_ssa_3lo_token(SsaConfig.from_env())


@pytest.fixture(scope="session")
def project_id() -> str:
    return _require_env("APS_TEST_PROJECT_ID")


@pytest.fixture(scope="session")
def folder_id() -> str:
    return _require_env("APS_TEST_FOLDER_ID")


@pytest.fixture(scope="session")
def source_version_urn() -> str:
    return _require_env("APS_TEST_SOURCE_VERSION_URN")


@pytest.fixture(scope="session")
def source_item_urn() -> str:
    return _require_env("APS_TEST_SOURCE_ITEM_URN")


@pytest.fixture(scope="session")
def upload_bytes_to_storage() -> Callable[[str, str, bytes], None]:
    def _upload(storage_id: str, token: str, content: bytes) -> None:
        prefix = "urn:adsk.objects:os.object:"
        if not storage_id.startswith(prefix):
            raise ValueError(f"Unexpected storage id format: {storage_id}")

        bucket_key, object_key = storage_id[len(prefix):].split("/", 1)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            signed = get_signed_s3_upload(
                bucketKey=bucket_key,
                objectKey=object_key,
                token=token,
            )
            put_to_signed_url(signed.urls[0], str(tmp_path))
            complete_signed_s3_upload(
                bucketKey=bucket_key,
                objectKey=object_key,
                uploadKey=signed.uploadKey,
                token=token,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    return _upload
