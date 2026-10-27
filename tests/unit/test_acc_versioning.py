from unittest.mock import Mock

import pytest
import requests

from aps_automation_sdk import ActivityOutputParameterAcc, acc, classes
from .test_sdk_reliability import response


@pytest.mark.parametrize('next_link', [{'href': '?page%5Bnumber%5D=2'}, '?page%5Bnumber%5D=2'])
def test_item_lookup_follows_next_page_and_encodes_folder(monkeypatch, next_link):
    request = Mock(side_effect=[
        response({'data': [{'type': 'folders', 'id': 'folder', 'attributes': {'displayName': 'output.rvt'}}],
                  'links': {'next': next_link}}),
        response({'data': [{'type': 'items', 'id': 'existing-item', 'attributes': {'displayName': 'output.rvt'}}]}),
    ])
    monkeypatch.setattr(acc.requests, 'get', request)
    assert acc.find_item_by_name('project', 'urn:folder/#?', 'output.rvt', 'token') == 'existing-item'
    assert '/folders/urn%3Afolder%2F%23%3F/contents' in request.call_args_list[0].args[0]
    assert request.call_args_list[1].args[0].endswith('?page%5Bnumber%5D=2')
    assert request.call_args_list[1].kwargs['headers'] == {'Authorization': 'Bearer token'}


def test_item_lookup_returns_none_after_last_page(monkeypatch):
    request = Mock(side_effect=[response({'data': [], 'links': {'next': {'href': '?page=2'}}}),
                                response({'data': [], 'links': {'next': None}})])
    monkeypatch.setattr(acc.requests, 'get', request)
    assert acc.find_item_by_name('project', 'folder', 'missing.rvt', 'token') is None
    assert request.call_count == 2


def test_item_lookup_stops_when_match_exists(monkeypatch):
    request = Mock(return_value=response({'data': [{'type': 'items', 'id': 'item',
                                                   'attributes': {'displayName': 'output.rvt'}}],
                                          'links': {'next': '?page=2'}}))
    monkeypatch.setattr(acc.requests, 'get', request)
    assert acc.find_item_by_name('project', 'folder', 'output.rvt', 'token') == 'item'
    assert request.call_count == 1


def test_pagination_does_not_forward_token_to_other_host(monkeypatch):
    request = Mock(return_value=response({'data': [], 'links': {'next': {'href': 'https://other.test/page'}}}))
    monkeypatch.setattr(acc.requests, 'get', request)
    with pytest.raises(RuntimeError, match='APS API origin'):
        acc.find_item_by_name('project', 'folder', 'output.rvt', 'token')
    assert request.call_count == 1


def test_pagination_cycle_fails_without_another_request(monkeypatch):
    request = Mock(return_value=response({'data': [], 'links': {'next': {'href': '?page=1'}}}))
    monkeypatch.setattr(acc.requests, 'get', request)
    with pytest.raises(RuntimeError, match='repeated a page'):
        acc.find_item_by_name('project', 'folder', 'output.rvt', 'token')
    assert request.call_count == 2


def test_page_http_error_propagates(monkeypatch):
    request = Mock(side_effect=[response({'data': [], 'links': {'next': '?page=2'}}), response({}, 403)])
    monkeypatch.setattr(acc.requests, 'get', request)
    with pytest.raises(requests.HTTPError):
        acc.find_item_by_name('project', 'folder', 'output.rvt', 'token')


def output():
    value = ActivityOutputParameterAcc(name='result', localName='output.rvt', verb='put',
        description='Output', project_id='project', folder_id='folder', file_name='output.rvt')
    value._storage_id = 'urn:adsk.objects:os.object:bucket/new-output'
    return value


def test_output_adds_version_to_existing_item(monkeypatch):
    monkeypatch.setattr(classes, 'find_item_by_name', lambda *args: 'existing-item')
    create_item = Mock()
    create_version = Mock(return_value={'data': {'type': 'versions', 'id': 'version-id'}})
    monkeypatch.setattr(classes, 'create_item_with_first_version', create_item)
    monkeypatch.setattr(classes, 'create_version_for_item', create_version)
    value = output()
    result = value.create_acc_item('token')
    assert result['data']['type'] == 'versions'
    assert value.get_lineage_urn() == 'existing-item'
    assert create_version.call_args.kwargs['item_id'] == 'existing-item'
    assert create_version.call_args.kwargs['storage_id'] == value._storage_id
    create_item.assert_not_called()


def test_output_creates_new_item_when_name_is_absent(monkeypatch):
    monkeypatch.setattr(classes, 'find_item_by_name', lambda *args: None)
    create_item = Mock(return_value={'data': {'type': 'items', 'id': 'new-item'}})
    create_version = Mock()
    monkeypatch.setattr(classes, 'create_item_with_first_version', create_item)
    monkeypatch.setattr(classes, 'create_version_for_item', create_version)
    value = output()
    assert value.create_acc_item('token')['data']['type'] == 'items'
    assert value.get_lineage_urn() == 'new-item'
    assert create_item.call_args.kwargs['storage_id'] == value._storage_id
    create_version.assert_not_called()


def test_output_handles_concurrent_item_creation(monkeypatch):
    monkeypatch.setattr(classes, 'find_item_by_name', Mock(side_effect=[None, 'other-writer-item']))
    create_item = Mock(side_effect=requests.HTTPError(response=response({}, 409)))
    create_version = Mock(return_value={'data': {'type': 'versions', 'id': 'version'}})
    monkeypatch.setattr(classes, 'create_item_with_first_version', create_item)
    monkeypatch.setattr(classes, 'create_version_for_item', create_version)
    value = output()
    value.create_acc_item('token')
    assert value.get_lineage_urn() == 'other-writer-item'
    assert create_item.call_count == 1
    assert create_version.call_args.kwargs['item_id'] == 'other-writer-item'


@pytest.mark.parametrize('status', [403, 409, 500])
def test_output_preserves_create_error_when_no_item_is_found(monkeypatch, status):
    monkeypatch.setattr(classes, 'find_item_by_name', lambda *args: None)
    error = requests.HTTPError(response=response({}, status))
    monkeypatch.setattr(classes, 'create_item_with_first_version', Mock(side_effect=error))
    create_version = Mock()
    monkeypatch.setattr(classes, 'create_version_for_item', create_version)
    value = output()
    with pytest.raises(requests.HTTPError) as caught:
        value.create_acc_item('token')
    assert caught.value is error
    create_version.assert_not_called()
    with pytest.raises(RuntimeError, match='No ACC item lineage'):
        value.get_lineage_urn()


def test_output_requires_storage_before_finalize(monkeypatch):
    value = output()
    value._storage_id = None
    lookup = Mock()
    monkeypatch.setattr(classes, 'find_item_by_name', lookup)
    with pytest.raises(RuntimeError, match='Create output storage'):
        value.create_acc_item('token')
    lookup.assert_not_called()


def test_new_output_storage_clears_previous_lineage(monkeypatch):
    value = output()
    value._item_lineage_urn = 'old-item'
    monkeypatch.setattr(classes, 'create_storage', lambda **kwargs: 'new-storage')
    assert value.work_item_arg_3lo('token')['result']['url'] == 'new-storage'
    with pytest.raises(RuntimeError, match='No ACC item lineage'):
        value.get_lineage_urn()


@pytest.mark.parametrize('temporary_id', [1, 2, 7])
def test_compound_item_request_has_matching_tip_and_included_ids(monkeypatch, temporary_id):
    request = Mock(return_value=response({'data': {'type': 'items', 'id': 'item'}}))
    monkeypatch.setattr(acc.requests, 'post', request)
    acc.create_item_with_first_version('project', 'folder', 'output.rvt', 'storage', 'token', version=temporary_id)
    payload = request.call_args.kwargs['json']
    tip_id = payload['data']['relationships']['tip']['data']['id']
    assert tip_id == payload['included'][0]['id'] == str(temporary_id)
    assert payload['included'][0]['relationships']['storage']['data']['id'] == 'storage'
