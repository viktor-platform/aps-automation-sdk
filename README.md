# APS Automation SDK [Draft/Preliminary Version]

A Python SDK that wraps the Autodesk Platform Services (APS) Design Automation API, making it faster and easier to automate Revit and AutoCAD workflows in the cloud. 

## SDK vs REST API Comparison

The following comparison clearly shows how the `aps_automation_sdk` simplifies workflows compared to using the REST API directly. For complete examples, refer to the [examples folder](./examples/).

<table>
<tr>
<td><b>SDK</b></td>
<td><b>REST API</b></td>
</tr>
<tr>
<td valign="top">

```python
# 1. Define input parameter
input_revit = ActivityInputParameter(
    name="rvtFile",
    localName="input.rvt",
    verb="get",
    description="Input Revit File",
    required=True,
    is_engine_input=True,
    bucketKey="yourBucketKey",
    objectKey="input.rvt",
)

# 2. Define output parameter
output_file = ActivityOutputParameter(
    name="result",
    localName="result.rvt",
    verb="put",
    description="Results",
    zip=False,
    bucketKey="yourBucketKey",
    objectKey="result.rvt",
    required=True,
)

# 3. Create activity
activity = Activity(
    id=activity_name,
    parameters=[input_revit, output_file],
    engine="Autodesk.Revit+2024",
    appbundle_full_name=appbundle_full_alias,
    description="Delete walls from Revit file Updated.",
    alias=alias,
)

# 4. Deploy activity
activity.set_revit_command_line()
activity.deploy(token=token)

# 5. Upload input file
input_rvt_path = Path.cwd() / "files" / "DeleteWalls.rvt"
input_revit.upload_file_to_oss(file_path=str(input_rvt_path), token=token)

# 6. Create work item
work_item = WorkItem(
    parameters=[input_revit, output_file],
    activity_full_alias=activity_full_alias
)

# 7. Execute and monitor work item
status_resp = work_item.execute(token=token, max_wait=600, interval=10)
```

</td>
<td valign="top">

```bash
# 1. Create activity
curl -X POST  'https://developer.api.autodesk.com/da/us-east/v3/activities'  -H 'Content-Type: application/json'  -H 'Authorization: Bearer <YOUR_ACCESS_TOKEN>'  -d '{
            "id": "DeleteWallsActivity",
            "commandLine": [ "$(engine.path)\\\\revitcoreconsole.exe /i \"$(args[rvtFile].path)\" /al \"$(appbundles[DeleteWallsApp].path)\"" ],
            "parameters": {
              "rvtFile": {
                "zip": false,
                "ondemand": false,
                "verb": "get",
                "description": "Input Revit model",
                "required": true,
                "localName": "$(rvtFile)"
              },
              "result": {
                "zip": false,
                "ondemand": false,
                "verb": "put",
                "description": "Results",
                "required": true,
                "localName": "result.rvt"
              }
            },
            "engine": "Autodesk.Revit+2024",
            "appbundles": [ "<YOUR_NICKNAME>.DeleteWallsApp+test" ],
            "description": "Deletes walls from Revit file."
    }'

# 2. Create activity alias
curl -X POST  'https://developer.api.autodesk.com/da/us-east/v3/activities/DeleteWallsActivity/aliases'  -H 'Content-Type: application/json'  -H 'Authorization: Bearer <YOUR_ACCESS_TOKEN>'  -d '{
      "version": 1,
      "id": "test"
    }'

# 3. Create bucket
curl -X POST \
    'https://developer.api.autodesk.com/oss/v2/buckets' \
    -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
    -H 'Content-Type: application/json' \
    -H 'x-ads-region: US' \
        -d '{
            "bucketKey": "<YOUR_BUCKET_KEY>",
            "access": "full",
            "policyKey": "transient"
        }'

# 4. Get signed upload URL
curl -X GET  "https://developer.api.autodesk.com/oss/v2/buckets/<YOUR_BUCKET_KEY>/objects/YOUR_OBJECT_KEY/signeds3upload"
     -H "Authorization: Bearer nFRJxzCD8OOUr7hzBwbr06D76zAT"

# 5. Upload file to S3
curl -X PUT  "<SIGNED_UPLOAD_URL>"
     -H --data-binary '@<PATH_TO_FILE_TO_UPLOAD>/deleteWalls.rvt'

# 6. Complete upload
curl -X POST  "https://developer.api.autodesk.com/oss/v2/buckets/<YOUR_BUCKET_KEY>/objects/<OBJECT_KEY_4_INPUT_FILE>/signeds3upload"  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"  -d '{
            "uploadKey": "<YOUR_UPLOAD_KEY>"
        }'

# 7. Create and execute work item
curl -X POST  'https://developer.api.autodesk.com/da/us-east/v3/workitems'  -H 'Content-Type: application/json'  -H 'Authorization: Bearer <YOUR_ACCESS_TOKEN>'  -d '{
        "activityId": "<YOUR_APP_NICKNAME>.DeleteWallsActivity+test",
        "arguments": {
          "rvtFile": {
            "url": "urn:adsk.objects:os.object:<YOUR_BUCKET_KEY>/<OBJECT_KEY_4_INPUT_FILE>",
              "verb": "get",
              "headers": {
                  "Authorization": "Bearer <YOUR_ACCESS_TOKEN>"
              }
          },
          "result": {
            "url": "urn:adsk.objects:os.object:<YOUR_BUCKET_KEY>/<RESULT_FILE_OBJECT_KEY>",
                              "verb": "put",
              "headers": {
                  "Authorization": "Bearer <YOUR_ACCESS_TOKEN>"
              }
          }
        }
      }'

# 8. Monitor work item status
curl -X GET  'https://developer.api.autodesk.com/da/us-east/v3/workitems/YOUR_WORKITEM_ID'  -H 'Content-Type: application/json'  -H 'Authorization: Bearer <YOUR_ACCESS_TOKEN>'

```


</td>
</tr>
</table>


## Installation

### Prerequisites

1. **Install uv** (fast Python package manager):
   ```powershell
   pip install uv
   ```
   
   For other installation methods, see: https://docs.astral.sh/uv/getting-started/installation/

2. **Clone or download this repository**

### Install the SDK

From the project root directory:

```powershell
# Install the package in editable mode
uv pip install -e .
```

**Note:** When running the Jupyter notebook in VS Code for the first time, you may be prompted to install the `ipykernel` package. Click "Install" or run:

```powershell
uv add ipykernel
```

## Configuration

Create a `.env` file in the project root with your APS credentials:

```ini
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```

Get your credentials from the [APS Developer Portal](https://aps.autodesk.com/).

## Road Map

- Improve type hints and docstrings
- Add ACC examples
- Add unit tests
- Add pre-commits and governance
- Migrate to Viktor