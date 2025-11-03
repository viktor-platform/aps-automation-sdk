import requests
from typing import Annotated, Literal, Any
from aps_automation_sdk.core import upload_appbundle
from aps_automation_sdk.dsl import RegisterBundleResponse

APS_BASE_URL = "https://developer.api.autodesk.com"
OSS_V2_BASE_URL = f"{APS_BASE_URL}/oss/v2"
DA_BASE_URL = f"{APS_BASE_URL}/da/us-east/v3" 
AUTH_URL = f"{APS_BASE_URL}/authentication/v2/token"

SCOPES = "data:read data:write data:create bucket:create bucket:read code:all"

def get_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        AUTH_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": SCOPES,
        },
        timeout=15,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return token

def set_nickname(token: str, nickname: str) -> str:
    """
    Try to set the nickname.
    Returns the nickname that actually applies.
    """
    url = f"{DA_BASE_URL}/forgeapps/me"
    r = requests.patch(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"nickname": nickname},
        timeout=30,
    )

    if r.status_code == 200:
        return nickname

    if r.status_code == 409:
        # App already has resources, nickname is locked, keep the current one
        return get_nickname(token)

    # Often 400 means the nickname is already taken
    try:
        details = r.json()
    except Exception:
        details = r.text
    raise RuntimeError(f"Could not set nickname, status {r.status_code}, details {details}")

def get_nickname(token: str) -> str:
    url = f"{DA_BASE_URL}/forgeapps/me"
    r = requests.get(
        url,
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    # The API returns a JSON object with nickname and publicKey
    # Example response: {"nickname": "viktortest", "publicKey": {...}}
    response_data = r.json()
    return response_data.get("nickname", response_data)

def create_bucket(
    bucketKey: Annotated[str, "Unique Name you assign to a bucket, Possible values: -_.a-z0-9 (between 3-128 characters in length"],
    token: Annotated[str, "2Lo token"],
    policy_key: Literal["transient", "temporary", "persistent"]= "transient",
    access: None | Literal["full", "read"] = "full",
    region: Literal["US", "EMEA", "AUS", "CAN", "DEU", "IND", "JPN", "GBN"] = "US",
) -> dict[str, Any]:
    """
    Create a bucket in OSS v2.
    https://aps.autodesk.com/en/docs/data/v2/reference/http/buckets-POST/
    """
    url = f"{OSS_V2_BASE_URL}/buckets"
    payload = {"bucketKey": bucketKey, "access": access, "policyKey": policy_key}
    headers = {
        "Authorization":f"Bearer {token}",
        "Content-Type": "application/json",
        "x-ads-region": region,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def delete_appbundle(appbundleId:str, token: str) -> int:
    url = f"{DA_BASE_URL}/appbundles/{appbundleId}"
    header = {"Authorization": f"Bearer {token}"}
    r = requests.delete(url=url, headers=header)
    r.raise_for_status() 
    return r.status_code

def delete_activity(activityId: str, token: str) -> int:
    url = f"{DA_BASE_URL}/activities/{activityId}"
    header = {"Authorization": f"Bearer {token}"}
    r = requests.delete(url=url, headers=header)
    r.raise_for_status()
    return r.status_code

# App bundle utils
def create_appbundle_version(app_id: str, engine: str, description: str, token: str) -> RegisterBundleResponse:
    """
    POST /appbundles/{id}/versions
    Returns JSON with 'version' and 'uploadParameters' for S3.
    """
    url = f"{DA_BASE_URL}/appbundles/{app_id}/versions"
    payload = {"id": None, "engine": engine, "description": description}
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=60)
    r.raise_for_status()
    return RegisterBundleResponse.model_validate(r.json())


def move_or_create_alias(app_id: str, alias_id: str, version: int, token: str) -> dict[str, Any]:
    """
    PATCH alias to the new version. If the alias does not exist, create it.
    """
    url = f"{DA_BASE_URL}/appbundles/{app_id}/aliases/{alias_id}"
    r = requests.patch(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"version": version}, timeout=30)
    if r.status_code == 404:
        create_url = f"{DA_BASE_URL}/appbundles/{app_id}/aliases"
        r = requests.post(create_url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"id": alias_id, "version": version}, timeout=30)
    r.raise_for_status()
    return r.json()

def publish_appbundle_update(appbundle_id: str, engine: str, alias_id: str, zip_path: str, token: str, description: str = "Automated update") -> dict[str, Any]:
    """
    Update the running Activity without breaking users:
    1) Create a new AppBundle version
    2) Upload the new .bundle.zip to S3
    3) Move (or create) the alias to the new version

    Returns:
        {
            "appbundle_id": ...,
            "new_version": <int>,
            "alias": ...,
            "alias_version": <int>,
            "s3_status": <int>
        }
    """
    # Step 1: create new version and get S3 upload info
    version_resp: RegisterBundleResponse = create_appbundle_version(appbundle_id, engine, description, token)
    version_no = version_resp.version

    # Step 2: upload the bundle
    s3_status = upload_appbundle(upload_parameters=version_resp.uploadParameters,zip_path=zip_path)

    # Step 3: move alias to the new version
    alias_resp = move_or_create_alias(appbundle_id, alias_id, version_no, token)

    return {
        "appbundle_id": appbundle_id,
        "new_version": version_no,
        "alias": alias_id,
        "alias_version": alias_resp.get("version", version_no),
        "s3_status": s3_status,
    }