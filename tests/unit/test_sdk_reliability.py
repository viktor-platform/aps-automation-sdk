import json
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import aps_automation_sdk as sdk
from aps_automation_sdk import classes, core, ssa

ROOT = Path(__file__).resolve().parents[2]


def response(payload, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = 'https://developer.api.autodesk.com/test'
    result._content = json.dumps(payload).encode()
    return result


def test_base_import_does_not_require_ssa_or_signing_packages(tmp_path):
    script = '''
import importlib.abc, sys
class BlockExtras(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'jwt', 'cryptography'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, BlockExtras())
import aps_automation_sdk as sdk
assert sdk.Activity is not None
config = sdk.SsaConfig('client', 'secret', 'account', 'key', 'private', 'data:read')
try:
    sdk.build_ssa_jwt(config)
except RuntimeError as exc:
    assert 'aps-automation-sdk[ssa]' in str(exc)
else:
    raise AssertionError('SSA must report its missing extra')
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_jwt_still_signs_with_ssa_extra(tmp_path):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    config = sdk.SsaConfig('client', 'secret', 'account', 'key-id', pem, 'data:read code:all')
    assertion = sdk.build_ssa_jwt(config)
    claims = jwt.decode(assertion, key.public_key(), algorithms=['RS256'], audience=ssa.AUTH_TOKEN_URL)
    assert claims['iss'] == 'client'
    assert claims['sub'] == 'account'
    assert claims['scope'] == ['data:read', 'code:all']
    assert jwt.get_unverified_header(assertion)['kid'] == 'key-id'


@pytest.mark.parametrize('operation', ['upload', 'complete', 'download'])
def test_oss_object_key_is_encoded_as_one_path_segment(monkeypatch, operation):
    key = 'folder/á #%?.rvt'
    payload = {'uploadKey': 'upload', 'urls': ['https://storage.test/input'],
               'bucketKey': 'bucket', 'objectId': 'object', 'objectKey': key,
               'size': 1, 'contentType': 'application/octet-stream', 'location': 'location',
               'url': 'https://storage.test/output'}
    request = Mock(return_value=response(payload))
    monkeypatch.setattr(core.requests, 'get', request)
    monkeypatch.setattr(core.requests, 'post', request)
    if operation == 'upload':
        core.get_signed_s3_upload('bucket', key, 'test-token')
    elif operation == 'complete':
        core.complete_signed_s3_upload('bucket', key, 'upload', 'test-token')
    else:
        core.get_signed_s3_download('bucket', key, 'test-token')
    url = request.call_args.args[0] if request.call_args.args else request.call_args.kwargs['url']
    assert '/objects/folder%2F%C3%A1%20%23%25%3F.rvt/signeds3' in url
    assert core.build_oss_urn('bucket', key) == f'urn:adsk.objects:os.object:bucket/{key}'


def parameter():
    return sdk.ActivityInputParameter(name='input', localName='input.rvt', verb='get',
                                      description='Input', bucketKey='bucket', objectKey='input.rvt')


@pytest.mark.parametrize('status', [401, 403, 500])
def test_bucket_errors_propagate(monkeypatch, status):
    error = requests.HTTPError(response=response({}, status))
    monkeypatch.setattr(classes, 'create_bucket', Mock(side_effect=error))
    with pytest.raises(requests.HTTPError):
        parameter().ensure_bucket('test-token')


def test_existing_bucket_conflict_is_allowed(monkeypatch):
    monkeypatch.setattr(classes, 'create_bucket', Mock(side_effect=requests.HTTPError(response=response({}, 409))))
    parameter().ensure_bucket('test-token')


def test_bucket_transport_error_propagates(monkeypatch):
    monkeypatch.setattr(classes, 'create_bucket', Mock(side_effect=requests.Timeout('test timeout')))
    with pytest.raises(requests.Timeout):
        parameter().ensure_bucket('test-token')


def test_bundle_registration_has_http_timeout(monkeypatch):
    request = Mock(return_value=response({}))
    monkeypatch.setattr(core.requests, 'post', request)
    monkeypatch.setattr(core, 'RegisterBundleResponse', lambda **kwargs: kwargs)
    core.register_appbundle('TestBundle', 'Autodesk.Revit+2024', 'Test', 'test-token')
    assert request.call_args.kwargs['timeout'] == 30


@pytest.mark.parametrize('status', [200, 400])
def test_workitem_submission_does_not_print_tokens_or_response(monkeypatch, capsys, status):
    token = 'test-sensitive-token'
    request = Mock(return_value=response({'id': 'workitem', 'echo': token}, status))
    monkeypatch.setattr(core.requests, 'post', request)
    args = {'input': {'url': 'test-input', 'headers': {'Authorization': f'Bearer {token}'}}}
    if status == 200:
        assert core.run_public_work_item(token, 'app.Activity+dev', args, 'signature')['id'] == 'workitem'
    else:
        with pytest.raises(requests.HTTPError):
            core.run_public_work_item(token, 'app.Activity+dev', args, 'signature')
    assert not capsys.readouterr().out
    assert request.call_args.kwargs['json']['arguments'] == args


def test_acc_upload_does_not_print_signed_urls(monkeypatch, capsys):
    value = sdk.UploadActivityInputParameter(name='input', localName='input.dwg', verb='get',
        description='Input', project_id='project', folder_id='folder', file_name='input.dwg', file_path='input.dwg')
    monkeypatch.setattr(classes, 'find_item_by_name', lambda *args: 'item')
    monkeypatch.setattr(classes, 'create_storage', lambda **kwargs: 'urn:adsk.objects:os.object:bucket/key')
    signed = core.GetSignedS3UrlsResponse(uploadKey='test-upload-key', urls=['https://storage.test/?signature=secret'])
    monkeypatch.setattr(classes, 'get_signed_s3_upload', lambda **kwargs: signed)
    for name in ('put_to_signed_url', 'complete_signed_s3_upload', 'create_version_for_item'):
        monkeypatch.setattr(classes, name, lambda **kwargs: None)
    assert value.upload_and_create('test-token')[1] == 'item'
    assert not capsys.readouterr().out


def test_invalid_token_response_does_not_echo_token():
    with pytest.raises(RuntimeError) as exc:
        ssa.parse_token_response({'token_type': 'unexpected', 'access_token': 'test-sensitive-token'})
    assert 'test-sensitive-token' not in str(exc.value)


class Timer:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.mark.parametrize('payload', [{'status': 'pending'}, {}])
def test_poll_budget_includes_http_time_and_limits_last_sleep(monkeypatch, payload):
    timer = Timer()
    calls = []
    events = []
    def get_status(*args, timeout):
        calls.append(timeout)
        timer.now += 3
        return payload
    monkeypatch.setattr(core.time, 'monotonic', timer.monotonic)
    monkeypatch.setattr(core.time, 'sleep', timer.sleep)
    monkeypatch.setattr(core, 'get_workitem_status', get_status)
    assert core.poll_workitem_status('item', 'token', max_wait=5, interval=10, on_event=events.append) == payload
    assert calls == [5]
    assert timer.sleeps == [2]
    assert events[0].elapsed_seconds == 3
    assert not events[0].is_terminal


def test_poll_callback_time_consumes_budget(monkeypatch):
    timer = Timer()
    request = Mock(return_value={'status': 'pending'})
    monkeypatch.setattr(core.time, 'monotonic', timer.monotonic)
    monkeypatch.setattr(core.time, 'sleep', timer.sleep)
    monkeypatch.setattr(core, 'get_workitem_status', request)
    def callback(event):
        timer.now += 6
    core.poll_workitem_status('item', 'token', max_wait=5, on_event=callback)
    assert request.call_count == 1
    assert not timer.sleeps


@pytest.mark.parametrize('status', ['success', 'cancelled', 'failedUploadOptional'])
def test_terminal_status_stops_polling(monkeypatch, caplog, status):
    timer = Timer()
    request = Mock(return_value={'status': status, 'reportUrl': 'https://storage.test/?signature=secret'})
    monkeypatch.setattr(core.time, 'monotonic', timer.monotonic)
    monkeypatch.setattr(core.time, 'sleep', timer.sleep)
    monkeypatch.setattr(core, 'get_workitem_status', request)
    events = []
    with caplog.at_level('INFO'):
        result = core.poll_workitem_status('item', 'token', on_event=events.append)
    assert result['status'] == status
    assert events[0].is_terminal
    assert events[0].report_url == result['reportUrl']
    assert 'signature=secret' not in caplog.text
    assert request.call_count == 1
    assert not timer.sleeps


def test_zero_wait_makes_one_request(monkeypatch):
    request = Mock(return_value={'status': 'pending'})
    monkeypatch.setattr(core, 'get_workitem_status', request)
    core.poll_workitem_status('item', 'token', max_wait=0)
    assert request.call_count == 1
    assert request.call_args.kwargs['timeout'] == 30


@pytest.mark.parametrize('kwargs', [{'max_wait': -1}, {'interval': 0}, {'interval': -1},
                                   {'max_wait': float('inf')}, {'interval': float('nan')}])
def test_invalid_poll_options_fail_before_http(monkeypatch, kwargs):
    request = Mock()
    monkeypatch.setattr(core, 'get_workitem_status', request)
    with pytest.raises(ValueError):
        core.poll_workitem_status('item', 'token', **kwargs)
    request.assert_not_called()


def test_package_version_matches_project_metadata():
    metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert sdk.__version__ == metadata['project']['version']
