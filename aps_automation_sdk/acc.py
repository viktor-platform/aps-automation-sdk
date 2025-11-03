import requests
import urllib.parse
import json
from typing import Any

APS_BASE_URL = "https://developer.api.autodesk.com"
PROJECTS_V1 = f"{APS_BASE_URL}/project/v1"
DATA_V1 = f"{APS_BASE_URL}/data/v1"
DATA_V2 = f"{APS_BASE_URL}/data/v2"
DA_V3 = f"{APS_BASE_URL}/da/us-east/v3"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def item_from_version(project_id: str, version_urn: str, token: str) -> str:
    """Get item ID from version URN."""
    if "?version=" not in version_urn:
        raise RuntimeError("version URN must include '?version=N'")
    url = f"{DATA_V1}/projects/{project_id}/versions/{urllib.parse.quote(version_urn, safe='')}/item"
    r = requests.get(url, headers=bearer(token), timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})
    if data.get("type") != "items" or "id" not in data:
        raise RuntimeError(
            f"Unexpected payload for versions->item, {json.dumps(r.json())[:400]}"
        )
    return data["id"]


def parent_folder_from_item(project_id: str, item_id: str, token: str) -> str:
    """Get parent folder ID from item ID."""
    url = f"{DATA_V1}/projects/{project_id}/items/{urllib.parse.quote(item_id, safe='')}/parent"
    r = requests.get(url, headers=bearer(token), timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})
    if data.get("type") != "folders" or "id" not in data:
        raise RuntimeError(
            f"Unexpected payload for item->parent, {json.dumps(r.json())[:400]}"
        )
    return data["id"]


def resolve_parent_folder(project_id: str, any_urn: str, token: str) -> str:
    """Resolve parent folder ID from any version URN."""
    item_id = item_from_version(project_id, any_urn, token)
    folder_id = parent_folder_from_item(project_id, item_id, token)
    return folder_id


def get_item_tip_version(
    project_id: str, item_lineage_urn: str, token: str
) -> dict[str, Any]:
    url = f"{DATA_V1}/projects/{project_id}/items/{urllib.parse.quote(item_lineage_urn, safe=':')}/tip"
    r = requests.get(url, headers=bearer(token), timeout=30)
    r.raise_for_status()
    return r.json()


def find_tip_storage_id(tip_payload: dict[str, Any]) -> str:
    """
    Return the storage objectId for the tip version.
    """
    nodes = [tip_payload.get("data", {})] + tip_payload.get("included", [])
    for node in nodes:
        rel = node.get("relationships", {})
        st = rel.get("storage") or {}
        data_rel = st.get("data") or {}
        sid = data_rel.get("id")
        if sid:
            return sid
    raise RuntimeError("No storage id found in tip payload")


def create_storage(project_id: str, folder_urn: str, file_name: str, token: str) -> str:
    """POST /data/v1/projects/{project_id}/storage, returns storage objectId"""
    url = f"{DATA_V1}/projects/{project_id}/storage"
    payload = {
        "jsonapi": {"version": "1.0"},
        "data": {
            "type": "objects",
            "attributes": {"name": file_name},
            "relationships": {
                "target": {"data": {"type": "folders", "id": folder_urn}}
            },
        },
    }
    r = requests.post(
        url,
        headers={**bearer(token), "Content-Type": "application/vnd.api+json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    storage_id = r.json().get("data", {}).get("id")
    if not storage_id:
        raise RuntimeError("Storage creation returned no id")
    return storage_id


def to_data_url_json(obj: dict) -> str:
    """Convert a dict to a minified JSON data URL for inline payload."""
    return "data:application/json," + urllib.parse.quote(
        json.dumps(obj, separators=(",", ":"))
    )


def find_item_by_name(
    project_id: str, folder_urn: str, file_name: str, token: str
) -> str | None:
    url = f"{DATA_V1}/projects/{project_id}/folders/{folder_urn}/contents"
    r = requests.get(url, headers=bearer(token), timeout=30)
    r.raise_for_status()
    for entry in r.json().get("data", []):
        if (
            entry.get("type") == "items"
            and entry.get("attributes", {}).get("displayName") == file_name
        ):
            return entry.get("id")
    return None


def create_version_for_item(
    project_id: str, item_id: str, file_name: str, storage_id: str, token: str
) -> dict[str, Any]:
    url = f"{DATA_V1}/projects/{project_id}/versions"
    payload = {
        "jsonapi": {"version": "1.0"},
        "data": {
            "type": "versions",
            "attributes": {
                "name": file_name,
                "extension": {
                    "type": "versions:autodesk.bim360:File",
                    "version": "1.0",
                },
            },
            "relationships": {
                "item": {"data": {"type": "items", "id": item_id}},
                "storage": {"data": {"type": "objects", "id": storage_id}},
            },
        },
    }
    r = requests.post(
        url,
        headers={**bearer(token), "Content-Type": "application/vnd.api+json"},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def create_item_with_first_version(
    project_id: str,
    folder_urn: str,
    file_name: str,
    storage_id: str,
    token: str,
    version: int = 1,
) -> dict[str, Any]:
    """
    POST /data/v1/projects/{project_id}/items to create a new Item and first Version
    referencing the storage we prepared and Automation wrote to.
    """
    url = f"{DATA_V1}/projects/{project_id}/items"
    payload = {
        "jsonapi": {"version": "1.0"},
        "data": {
            "type": "items",
            "attributes": {
                "displayName": file_name,
                "extension": {"type": "items:autodesk.bim360:File", "version": "1.0"},
            },
            "relationships": {
                "tip": {"data": {"type": "versions", "id": str(version)}},
                "parent": {"data": {"type": "folders", "id": folder_urn}},
            },
        },
        "included": [
            {
                "type": "versions",
                "id": "1",
                "attributes": {
                    "name": file_name,
                    "extension": {
                        "type": "versions:autodesk.bim360:File",
                        "version": "1.0",
                    },
                },
                "relationships": {
                    "storage": {"data": {"type": "objects", "id": storage_id}}
                },
            }
        ],
    }
    r = requests.post(
        url,
        headers={**bearer(token), "Content-Type": "application/vnd.api+json"},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()