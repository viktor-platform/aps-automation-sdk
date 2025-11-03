import requests
import time
import logging
import os
from typing import Annotated, Any
from dotenv import load_dotenv
from .dsl import RegisterBundleResponse, UploadParameters, GetSignedS3UrlsResponse, CompleteUploadRequest

load_dotenv()

APS_BASE_URL = "https://developer.api.autodesk.com"
OSS_V2_BASE_URL = f"{APS_BASE_URL}/oss/v2"
OSS_V4_BASE_URL = f"{APS_BASE_URL}/oss/v4"
MD_BASE_URL = f"{APS_BASE_URL}/modelderivative/v2" 
DA_BASE_URL = f"{APS_BASE_URL}/da/us-east/v3" 
AUTH_URL = f"{APS_BASE_URL}/authentication/v2/token"

def get_nickname(token: str) -> str:
    """
    Get the nickname (owner/qualifier) for the current APS account.
    This is the prefix used for AppBundles and Activities.
    Returns the nickname string directly.
    """
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

def get_signed_s3_upload(
        bucketKey: Annotated[str, "Unique Name you assign to a bucket, Possible values: -_.a-z0-9 (between 3-128 characters in length"],
        objectKey: Annotated[str, "URL-encoded object key to create signed URL for, basicallythenameofthefile"],
        token: Annotated[str, "2Lo Token"]
)->GetSignedS3UrlsResponse:
    """
    We need to check the encoded url part of this!
    """
    url = f"{OSS_V2_BASE_URL}/buckets/{bucketKey}/objects/{objectKey}/signeds3upload"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    response = r.json()
    return GetSignedS3UrlsResponse.model_validate(response)

def put_to_signed_url(signed_url: str, file_path: str) -> int:
    """
    Returns HTTP status code, 200 or 201 indicates success
    """
    with open(file_path, "rb") as f:
        r = requests.put(
            signed_url,
            data=f,
            headers={"Content-Type": "application/octet-stream"},
            timeout=120
        )
        r.raise_for_status()
        return r.status_code

def complete_signed_s3_upload(
        bucketKey: Annotated[str, "Unique Name of the bocket"],
        objectKey: Annotated[str, "URL-encoded object key to create signed URL for, basicallythenameofthefile"],
        uploadKey: Annotated[str, "UploadKey "],
        token: Annotated[str, "2Lo Token"]
    ) -> CompleteUploadRequest:
    url = f"{OSS_V2_BASE_URL}/buckets/{bucketKey}/objects/{objectKey}/signeds3upload"
    payload = {"uploadKey": uploadKey}
    header = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(url, headers=header, json=payload, timeout=30)
    r.raise_for_status()
    return CompleteUploadRequest.model_validate(r.json())

def build_oss_urn(
        bucketKey:Annotated[str, "Unique Name of the bucket"],
        objectKey: Annotated[str, "URL-encode object key"]
    ) -> str:
    return f"urn:adsk.objects:os.object:{bucketKey}/{objectKey}"


def register_appbundle(
        appBundleId: Annotated[str, "Name of AppBundle Only alphanumeric characters and _ (underscore) are allowed."],
        engine: Annotated[str, "Engine to be use in the Automation api e.g'Autodesk.Revit+2021'"],
        description: Annotated[str, "App bundle description"],
        token: Annotated[str, "2Lo Token"]
)->RegisterBundleResponse:
    url = f"{DA_BASE_URL}/appbundles" 
    payload = {"id": appBundleId, "engine": engine, "description":description}
    header = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(url,headers=header, json=payload)
    r.raise_for_status()
    return RegisterBundleResponse(**r.json())

def upload_appbundle(upload_parameters: UploadParameters, zip_path: str) -> Annotated[int, "Status Code e.g 200"]:
    with open(zip_path, "rb") as f:
        files = {**upload_parameters.formData.model_dump(by_alias=True, exclude_none=True), 'file': (os.path.basename(zip_path), f, "application/octet-stream")}
        r = requests.post(upload_parameters.endpointURL, files=files, timeout=60)
    r.raise_for_status()
    return r.status_code

def create_appbundle_alias(
    app_id: str, alias_id: str, version: int, token: str
) -> dict[str, Any]:
    """
    Create an alias for an AppBundle version.
    """
    url = f"{DA_BASE_URL}/appbundles/{app_id}/aliases"
    payload = {"version": version, "id": alias_id}
    header = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(
        url,
        headers=header,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def get_signed_s3_download(
        bucketKey: Annotated[str, "Unique name of the bucket"],
        objectKey: Annotated[str, "URL-encoded object key to create signed URL for, basicallythenameofthefile"],
        token: Annotated[str, "2Lo Token"]
) -> None:
    url = f"{OSS_V2_BASE_URL}/buckets/{bucketKey}/objects/{objectKey}/signeds3download"
    header = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.get(url=url, headers=header, timeout=30)
    r.raise_for_status()
    return r.json()

def dowload_from_signed_url(
        signed_url: Annotated[str, "Signed url from the previos"],
        output_path: Annotated[str, "Output path str"],
)-> int:
    """
    """
    r = requests.get(signed_url, timeout=120)
    r.raise_for_status()
    
    with open(output_path, "wb") as f:
        f.write(r.content)
    
    return r.status_code
        
def create_activity_alias(
    activity_id: str, alias_id: str, version: int, token: str
) -> dict[str, Any]:
    """
    Create an alias for an Activity version.
    """
    url = f"{DA_BASE_URL}/activities/{activity_id}/aliases"
    payload = {"version": version, "id": alias_id}
    r = requests.post(
        url,
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_activity(
    token: str,
    payload: dict
) -> dict:
    url = f"{DA_BASE_URL}/activities"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    
    if r.status_code != 200:
        print(f" Error found: {r.text=}")
    
    r.raise_for_status()
    return r.json()


def run_work_item(token: str, full_activity_alias: str, work_item_args: dict[str,Any]):
    url = f"{DA_BASE_URL}/workitems"
    payload = {
        "activityId": full_activity_alias,
        "arguments": work_item_args 
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    
    if r.status_code != 200:
        print(f" Error found: {r.text=}")
    
    r.raise_for_status()
    return r.json()

def run_public_work_item(token: str, full_activity_alias: str, work_item_args: dict[str,Any], signature: str):
    url = f"{DA_BASE_URL}/workitems"
    payload = {
        "activityId": full_activity_alias,
        "arguments": work_item_args,
        "signatures": {
            "activityId": signature,
            "workItem": signature
        }
    }
    import pprint
    pprint.pp(f"{payload=}")
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json","x-ads-workitem-signature": signature}, json=payload, timeout=30)
    
    if r.status_code != 200:
        print(f" Error found: {r.text=}")
    
    r.raise_for_status()
    return r.json()



def get_workitem_status(workitem_id: str, token: str) -> dict[str, Any]:
    """
    Get the current status and report URL for a WorkItem.
    """
    url = f"{DA_BASE_URL}/workitems/{workitem_id}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def poll_workitem_status(workitem_id: str, token: str, max_wait: int = 600, interval: int = 10) -> dict[str, Any]:
    
    elapsed = 0
    logging.info("Polling work item status, id=%s", workitem_id)

    last_status = ""
    status_resp = {}
    
    while elapsed < max_wait:
        status_resp = get_workitem_status(workitem_id, token)
        last_status = status_resp.get("status", "")
        report_url = status_resp.get('reportUrl')
        logging.info("[%3ds] status=%s report_url=%s", elapsed, last_status, report_url)
        if last_status in {"success", "failedUpload", "cancelled"}:
            report = status_resp.get("reportUrl")
            if report:
                logging.info("Report URL: %s", report)
            break
        time.sleep(interval)
        elapsed += interval
    
    return status_resp
    