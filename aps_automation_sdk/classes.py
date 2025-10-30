import json
from typing import Literal, Any, Dict, List, Optional
from pydantic import BaseModel, Field
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
    poll_workitem_status
)
from .utils import create_bucket
from .dsl import RegisterBundleResponse, UploadParameters

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

    def to_api_param(self) -> Dict[str, Any]:
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

    def work_item_arg(self, token: str) -> Dict[str, Any]:
        return {
            self.name: {
                "url": self.generate_oss_urn(),
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }


class ActivityOutputParameter(ActivityParameter):
    is_output: bool = True

    def work_item_arg(self, _token: str) -> Dict[str, Any]:
        return {
            self.name: {
                "url": self.generate_oss_urn(),
                "verb": self.verb,
                "headers": {"Authorization": f"Bearer {_token}"},
            }
        }


class ActivityJsonParameter(ActivityParameter):
    content: dict | None = None

    def work_item_arg(self) -> Dict[str, Any]:
        data_str = json.dumps(self.content, separators=(",", ":"))
        return {self.name: {"url": f"data:application/json, {data_str}"}}
    
    def set_content(self, data: dict) -> None:
        self.content = data


class Activity(BaseModel):
    id: str
    parameters: List[ActivityParameter]
    engine: Optional[str] = None
    appbundle_full_name: str
    description: str
    alias: str
    commandLine: Optional[List[str]] = None

    def param_map(self) -> Dict[str, Dict[str, Any]]:
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

    def to_api_dict(self) -> Dict[str, Any]:
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
    
    def build_arguments(self, token: str) -> Dict[str, Any]:
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
    
    def poll(self, work_item_id: str, token: str, max_wait: int = 600, interval: int = 10) -> Dict[str, Any]:
        return poll_workitem_status(work_item_id, token, max_wait=max_wait, interval=interval)
    
    def execute(self, token: str, max_wait: int = 600, interval: int = 10) -> Dict[str, Any]:
        work_item_id = self.run(token)
        return self.poll(work_item_id, token, max_wait=max_wait, interval=interval)
                