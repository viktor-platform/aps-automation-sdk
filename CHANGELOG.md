# Changelog

## 0.2.0rc1 — 2026-10-27

This is a release candidate for testing before the stable 0.2.0 release.

Install this candidate explicitly:

```bash
python -m pip install --upgrade "aps-automation-sdk==0.2.0rc1"
```

### Added

- Add `WorkItemPollEvent.approximate_queue_position` to polling callbacks. APS supplies an approximate position while the workitem is pending.
- Use `None` when queue position is unavailable or invalid. Clear the position when processing starts. APS marks this field as Beta.
- Add unit tests for queue updates, existing callbacks, ACC versioning, SDK imports, and test configuration.

### Fixed

- Create a new ACC version when an output file already exists. Search all folder pages and handle concurrent item creation.
- Include HTTP and callback time in polling limits and elapsed time. Reject invalid wait options.
- Apply a 30-second HTTP timeout to appbundle registration.
- Raise bucket setup errors except HTTP 409, which means the bucket name already exists.
- Load PyJWT only when SSA features are used. Base SDK imports no longer require the SSA extra.
- Remove tokens, signed storage URLs, and raw response output from SDK logs.
- Preserve live test failures during cleanup. Run live ACC tests only on a manual request.

### Changes for existing apps

- Load a local `.env` file in the application before reading credentials. Importing the SDK no longer loads it automatically:

  ```python
  from dotenv import load_dotenv

  load_dotenv()
  ```

- `ActivityOutputParameterAcc.create_acc_item()` returns an item response for a new file and a version response for an existing file. Use `get_lineage_urn()` to get the item ID in either case.
- Existing polling event constructors and callbacks remain valid. Code that serializes the complete event must accept the added queue-position field.
- A registration request can now raise `requests.Timeout`. Bucket setup can now raise errors that were previously ignored.

### Validation

- 76 unit tests pass locally and in GitHub CI.
- Live ACC tests require a manual run and access to the test project.
