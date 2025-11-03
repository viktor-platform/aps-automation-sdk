import json
from typing import Literal, Any, Optional
from pydantic import BaseModel, Field, PrivateAttr
from .core import (
    get_signed_s3_upload,
    put_to_signed_url,
    complete_signed_s3_upload,
    build_oss_urn,
    get_signed_s3_download,
    dowload_from_signed_url,
    create_activity,
    create_activity_alias,
    upload_appbundle,
    create_appbundle_alias,
    register_appbundle,
    run_work_item,
    poll_workitem_status,
    run_public_work_item
)
from .utils import create_bucket
from .dsl import RegisterBundleResponse, UploadParameters
from aps_automation_sdk.acc import get_item_tip_version, find_tip_storage_id, create_storage, create_item_with_first_version, create_version_for_item, find_item_by_name

class ActivityParameter(BaseModel):
    name: str
    localName: str
    verb: Literal["get", "put", "post"]
    description: str
    zip: bool = Field(default=False)
    ondemand: bool = Field(default=False)
    required: bool = Field(default=False)

    # storage, optional for JSON params
    bucketKey: Optional[str] = None
    objectKey: Optional[str] = None

    # roles
    is_output: bool = False
    is_engine_input: bool = False

    def oss_keys(self) -> tuple[str, str]:
        if not self.bucketKey or not self.objectKey:
            raise ValueError(f"{self.name}: bucketKey and objectKey are required for OSS operations")
        return self.bucketKey, self.objectKey

    def ensure_bucket(self, token: str) -> None:
        try:
            create_bucket(bucketKey=self.bucketKey, token=token)
        except Exception:
            pass

    def upload_file_to_oss(self, file_path: str, token: str) -> None:
        bucketKey, objectKey = self.oss_keys()
        self.ensure_bucket(token)
        signed = get_signed_s3_upload(bucketKey=bucketKey, objectKey=objectKey, token=token)
        put_to_signed_url(signed_url=signed.urls[0], file_path=file_path)
        complete_signed_s3_upload(bucketKey=bucketKey, objectKey=objectKey, uploadKey=signed.uploadKey, token=token)

    def download_to(self, output_path: str, token: str) -> None:
        if not self.is_output:
            raise ValueError(f"{self.name}: download_to is only valid for output parameters")
        bucketKey, objectKey = self.oss_keys()
        signed = get_signed_s3_download(bucketKey=bucketKey, objectKey=objectKey, token=token)
        dowload_from_signed_url(signed_url=signed["url"], output_path=output_path)

    def generate_oss_urn(self) -> str:
        bucketKey, objectKey = self.oss_keys()
        return build_oss_urn(bucketKey=bucketKey, objectKey=objectKey)

    def to_api_param(self) -> dict[str, Any]:
        return {
            "localName": self.localName,
            "zip": self.zip,
            "ondemand": self.ondemand,
            "verb": self.verb,
            "description": self.description,
            "required": self.required,
        }


class ActivityInputParameter(ActivityParameter):
    is_output: bool = False

    def work_item_arg(self, token: str) -> dict[str, Any]:
        return {
            self.name: {
                "url": self.generate_oss_urn(),
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }


class ActivityOutputParameter(ActivityParameter):
    is_output: bool = True

    def work_item_arg(self, _token: str) -> dict[str, Any]:
        return {
            self.name: {
                "url": self.generate_oss_urn(),
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {_token}"},
            }
        }


class ActivityJsonParameter(ActivityParameter):
    content: dict | None = None

    def work_item_arg(self) -> dict[str, Any]:
        data_str = json.dumps(self.content, separators=(",", ":"))
        return {self.name: {"url": f"data:application/json,{data_str}"}}
    
    def set_content(self, data: dict) -> None:
        self.content = data


class Activity(BaseModel):
    id: str
    parameters: list[ActivityParameter]
    engine: Optional[str] = None
    appbundle_full_name: str
    description: str
    alias: str
    commandLine: Optional[list[str]] = None

    def param_map(self) -> dict[str, dict[str, Any]]:
        return {p.name: p.to_api_param() for p in self.parameters}

    @staticmethod
    def short_appbundle_id(appbundle_full_alias: str) -> str:
        right = appbundle_full_alias.split(".", 1)[-1]
        return right.split("+", 1)[0]

    def set_revit_command_line(self) -> None:
        revit_input = next((p for p in self.parameters if isinstance(p, ActivityInputParameter) and p.is_engine_input), None)
        if revit_input is None:
            raise ValueError("No Revit input parameter marked as engine input")
        appbundle_short_id = self.short_appbundle_id(self.appbundle_full_name)
        self.commandLine = [
            "$(engine.path)\\revitcoreconsole.exe "
            f'/i "$(args[{revit_input.name}].path)" '
            f'/al "$(appbundles[{appbundle_short_id}].path)"'
        ]

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "commandLine": self.commandLine,
            "parameters": self.param_map(),
            "engine": self.engine,
            "appbundles": [self.appbundle_full_name],
            "description": self.description,
        }

    def deploy(self, token: str) -> None:
        create_activity(token=token, payload=self.to_api_dict())
        create_activity_alias(activity_id=self.id, alias_id=self.alias, version=1, token=token)

class AppBundle(BaseModel):
    appBundleId: str
    engine: str
    alias: str
    zip_path: str
    description: str
    version: int = 0  # updated on deploy

    def register(self, token: str) -> RegisterBundleResponse:
        return register_appbundle(
            appBundleId=self.appBundleId,
            engine=self.engine,
            description=self.description,
            token=token,
        )

    def upload(self, uploadParameters: UploadParameters) -> int:
        return upload_appbundle(
            upload_parameters=uploadParameters,
            zip_path=self.zip_path,
        )

    def create_alias(self, token: str) -> dict:
        return create_appbundle_alias(
            app_id=self.appBundleId,
            alias_id=self.alias,
            version=self.version,
            token=token,
        )

    def deploy(self, token: str) -> int:
        reg = self.register(token)
        self.upload(reg.uploadParameters)
        self.version = int(reg.version)
        self.create_alias(token)
        return self.version

class WorkItem(BaseModel):
    parameters: list[ActivityParameter]
    activity_full_alias: str
    
    def build_arguments(self, token: str) -> dict[str, Any]:
        """Build work item arguments from all parameters."""
        payload = {}
        for param in self.parameters:
            if isinstance(param, ActivityJsonParameter):
                payload |= param.work_item_arg()
            else:
                payload |= param.work_item_arg(token)
        return payload
    
    def run(self, token: str) -> str:
        args = self.build_arguments(token)
        response = run_work_item(
            token=token,
            full_activity_alias=self.activity_full_alias,
            work_item_args=args
        )
        work_item_id = response.get("id")
        if not work_item_id:
            raise RuntimeError("No work item id returned from run_work_item")
        return work_item_id
    
    def poll(self, work_item_id: str, token: str, max_wait: int = 600, interval: int = 10) -> dict[str, Any]:
        return poll_workitem_status(work_item_id, token, max_wait=max_wait, interval=interval)
    
    def execute(self, token: str, max_wait: int = 600, interval: int = 10) -> dict[str, Any]:
        work_item_id = self.run(token)
        return self.poll(work_item_id, token, max_wait=max_wait, interval=interval)
    

class ActivityInputParameterAcc(ActivityInputParameter):
    linage_urn: str | None = None
    project_id: str | None = None
        
    def get_acc_storage_url(self, token: str) -> str:
        tip_payload = get_item_tip_version(
            project_id= self.project_id,
            item_lineage_urn= self.linage_urn,
            token=token
        )
        acc_storage_url = find_tip_storage_id(tip_payload)
        return acc_storage_url

    def work_item_arg_3lo(self, token_3lo: str) -> dict[str, Any]:
        acc_storage_url = self.get_acc_storage_url(token=token_3lo)
        return {
            self.name: {
                "url": acc_storage_url,
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {token_3lo}"},
            }
        }

class UploadActivityInputParameter(ActivityInputParameter):
    folder_id: str
    project_id: str
    file_name: str
    file_path: str

    def upload_and_create(self, token: str) -> tuple[str, str]:

        item_id = find_item_by_name(self.project_id, self.folder_id, self.file_name, token)
        # Always create fresh storage for the incoming bytes
        storage_id = create_storage(project_id=self.project_id, folder_urn=self.folder_id, file_name=self.file_name, token=token)
        bucket_key, object_key = storage_id.split("urn:adsk.objects:os.object:")[1].split("/", 1)
        signed = get_signed_s3_upload(bucketKey=bucket_key, objectKey=object_key, token=token)
        print("**"*20)
        print(f"{signed=}")
        put_to_signed_url(signed_url=signed.urls[0], file_path=self.file_path)
        complete_signed_s3_upload(bucketKey=bucket_key, objectKey=object_key, uploadKey=signed.uploadKey, token=token)

        if item_id:
            # Create a new version on the existing item
            _ = create_version_for_item(
                project_id=self.project_id,
                item_id=item_id,
                file_name=self.file_name,
                storage_id=storage_id,
                token=token,
            )
            lineage_urn = item_id
            acc_storage_url = storage_id
            return acc_storage_url, lineage_urn

        # First version on a brand new item
        resp = create_item_with_first_version(
            project_id=self.project_id,
            folder_urn=self.folder_id,
            file_name=self.file_name,
            storage_id=storage_id,
            token=token,
        )
        lineage_urn = resp["data"]["id"]
        acc_storage_url = storage_id
        return acc_storage_url, lineage_urn

    def work_item_arg_3lo(self, token_3lo: str) -> dict[str, Any]:
        acc_storage_url, lineage_urn = self.upload_and_create(token_3lo)
        return {
            self.name: {
                "url": acc_storage_url,
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {token_3lo}"},
            }
        }


class ActivityOutputParameterAcc(ActivityOutputParameter):
    folder_id: str
    project_id: str
    file_name: str
    _storage_id: Optional[str] = PrivateAttr(default=None)

    def work_item_arg_3lo(self, token_3lo: str) -> dict[str, Any]:
     storage_id = create_storage(project_id=self.project_id, folder_urn=self.folder_id, file_name=self.file_name, token=token_3lo)
     self._storage_id = storage_id
     return {
            self.name: {
                "url": self._storage_id,
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {token_3lo}"},
            }
        }
    
    def create_acc_item(self, token: str):
        if not self._storage_id:
           raise RuntimeError("No storage have being creaded")
           
        resp = create_item_with_first_version(
            project_id=self.project_id,
            folder_urn=self.folder_id,
            file_name=self.file_name,
            storage_id=self._storage_id,
            token=token
        )
        return resp

class WorkItemAcc(WorkItem):

    def build_arguments_3lo(self, token3lo: str) ->dict[str, Any]:
        payload: dict[str, Any] = {}
        for param in self.parameters:
            if isinstance(param, ActivityJsonParameter):
                payload |= param.work_item_arg()
            elif isinstance(param, (ActivityInputParameterAcc, ActivityOutputParameterAcc, UploadActivityInputParameter)):
                payload |= param.work_item_arg_3lo(token3lo)
            else:
                raise TypeError(
                    f"Parameter '{param.name}' must be ActivityInputParameterAcc or ActivityOutputParameterAcc for 3LO"
                )
        return payload

    def run_public_activity(self, token3lo: str, activity_signature: str):
        args = self.build_arguments_3lo(token3lo)
        response = run_public_work_item(
            token=token3lo,
            full_activity_alias=self.activity_full_alias,
            work_item_args=args,
            signature=activity_signature,
        )
        workitem_id = response.get("id")
        if not workitem_id:
            raise RuntimeError("No work item id returned from run_public_work_item")

        return workitem_id