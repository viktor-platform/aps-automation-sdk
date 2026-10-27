import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

from aps_automation_sdk.ssa import DEFAULT_SSA_SCOPES, SsaConfig
from tests.integration import config
from tests.integration import test_ssa_only_autocad_list_layers_e2e as e2e


def set_ssa_env(monkeypatch):
    for name in ('CLIENT_ID_SSA', 'CLIENT_SECRET_SSA', 'APS_CLIENT_ID', 'APS_CLIENT_SECRET',
                 'CLIENT_ID', 'CLIENT_SECRET', 'APS_SSA_SCOPE'):
        monkeypatch.delenv(name, raising=False)
    values = {
        'APS_SSA_CLIENT_ID': 'test-client',
        'APS_SSA_CLIENT_SECRET': 'test-secret',
        'APS_SSA_SERVICE_ACCOUNT_ID': 'test-account',
        'APS_SSA_KEY_ID': 'test-key',
        'APS_SSA_PRIVATE_KEY': 'test-private-key',
        'APS_TEST_PROJECT_ID': 'test-project',
        'APS_TEST_FOLDER_ID': 'test-folder',
        'APS_TEST_SOURCE_ITEM_URN': 'test-item',
        'APS_TEST_SIGNING_KEY_JSON': json.dumps({name: 'test' for name in
                                               ('D', 'Exponent', 'InverseQ', 'Modulus', 'P', 'Q')}),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_local_env_uses_repository_root_and_preserves_process_values(tmp_path, monkeypatch):
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.setattr(config, 'REPOSITORY_ROOT', tmp_path)
    (tmp_path / '.env').write_text('APS_TEST_FOLDER_ID=file-folder\nAPS_TEST_PROJECT_ID=file-project\n')
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.delenv('APS_TEST_FOLDER_ID', raising=False)
    monkeypatch.setenv('APS_TEST_PROJECT_ID', 'process-project')
    config.load_test_env()
    assert os.environ['APS_TEST_FOLDER_ID'] == 'file-folder'
    assert os.environ['APS_TEST_PROJECT_ID'] == 'process-project'


def test_ci_does_not_load_local_env(tmp_path, monkeypatch):
    monkeypatch.setenv('CI', 'true')
    monkeypatch.setattr(config, 'REPOSITORY_ROOT', tmp_path)
    (tmp_path / '.env').write_text('APS_TEST_FOLDER_ID=file-folder\n')
    monkeypatch.delenv('APS_TEST_FOLDER_ID', raising=False)
    config.load_test_env()
    assert 'APS_TEST_FOLDER_ID' not in os.environ


def test_sdk_import_does_not_load_env(tmp_path):
    sentinel = 'APS_IMPORT_ENV_SENTINEL'
    (tmp_path / '.env').write_text(f'{sentinel}=unexpected\n')
    env = dict(os.environ, PYTHONPATH=str(config.REPOSITORY_ROOT))
    env.pop(sentinel, None)
    result = subprocess.run(
        [sys.executable, '-c', f'import aps_automation_sdk, os; assert {sentinel!r} not in os.environ'],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_dotenv_template_parses_private_key():
    values = dotenv_values(config.REPOSITORY_ROOT / '.env.sample.dev')
    assert values['APS_SSA_PRIVATE_KEY'] == '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'


def test_ssa_config_accepts_canonical_names_and_default_scope(monkeypatch):
    set_ssa_env(monkeypatch)
    monkeypatch.setenv('CLIENT_ID_SSA', 'canonical-client')
    monkeypatch.setenv('CLIENT_SECRET_SSA', 'canonical-secret')
    result = SsaConfig.from_env()
    assert result.client_id == 'canonical-client'
    assert result.client_secret == 'canonical-secret'
    assert result.scope == DEFAULT_SSA_SCOPES


@pytest.mark.parametrize('keep', ['false', 'true'])
@pytest.mark.parametrize('failure_at', ['token', 'profile'])
def test_e2e_failure_propagates_during_cleanup(tmp_path, monkeypatch, keep, failure_at):
    set_ssa_env(monkeypatch)
    monkeypatch.setattr(e2e, 'load_test_env', lambda: None)
    monkeypatch.setenv('APS_TEST_KEEP_DA_RESOURCES', keep)
    calls = []

    def fail(*args):
        raise RuntimeError('test operation failed')

    monkeypatch.setattr(e2e, 'get_token', fail if failure_at == 'token' else lambda *args: 'test-token')
    monkeypatch.setattr(e2e, 'get_forgeapp_profile', fail)
    monkeypatch.setattr(e2e, 'delete_activity', lambda *args: calls.append('activity'))
    monkeypatch.setattr(e2e, 'delete_appbundle', lambda *args: calls.append('bundle'))
    with pytest.raises(RuntimeError, match='test operation failed'):
        e2e.test_ssa_only_autocad_list_layers_end_to_end(tmp_path)
    assert calls == (['activity', 'bundle'] if failure_at == 'profile' and keep == 'false' else [])


def test_e2e_rejects_wrong_signing_key_before_deployment(tmp_path, monkeypatch):
    set_ssa_env(monkeypatch)
    monkeypatch.setattr(e2e, 'load_test_env', lambda: None)
    monkeypatch.setattr(e2e, 'get_token', lambda *args: 'test-token')
    monkeypatch.setattr(e2e, 'get_forgeapp_profile', lambda *args: {
        'nickname': 'testapp', 'publicKey': {'Exponent': 'other', 'Modulus': 'other'},
    })
    monkeypatch.setenv('APS_TEST_KEEP_DA_RESOURCES', 'true')
    with pytest.raises(AssertionError, match='signing key must match'):
        e2e.test_ssa_only_autocad_list_layers_end_to_end(tmp_path)
