import json
from typing import cast
from unittest.mock import Mock

import pytest
import requests

from aps_automation_sdk import AutomationEngine, EngineQueueStats, get_engine_queue_stats
from aps_automation_sdk import core


def json_response(payload: dict[str, object], status: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = f"{core.DA_BASE_URL}/health/Revit/stats"
    response._content = json.dumps(payload).encode()
    return response


@pytest.mark.parametrize("engine", ["AutoCAD", "Revit", "Inventor", "Fusion", "3dsMax"])
def test_public_helper_reads_shared_engine_queue(
    monkeypatch: pytest.MonkeyPatch, engine: AutomationEngine,
) -> None:
    payload: dict[str, object] = {
        "p50QueueTimeMs": 106.72,
        "p95QueueTimeMs": 372.19,
        "futureMetric": 10,
    }
    request = Mock(return_value=json_response(payload))
    monkeypatch.setattr(core.requests, "get", request)

    stats: EngineQueueStats = get_engine_queue_stats(engine=engine, token="test-token")

    assert stats == payload
    assert stats["p50QueueTimeMs"] == 106.72
    assert stats["p95QueueTimeMs"] == 372.19
    request.assert_called_once_with(
        f"{core.DA_BASE_URL}/health/{engine}/stats",
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        timeout=30,
    )


def test_no_recent_data_preserves_aps_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    payload: dict[str, object] = {"p50QueueTimeMs": -1.0, "p95QueueTimeMs": -1.0}
    request = Mock(return_value=json_response(payload))
    monkeypatch.setattr(core.requests, "get", request)

    assert get_engine_queue_stats("Revit", "test-token") == payload
    request.assert_called_once()


@pytest.mark.parametrize(
    "engine", ["", "revit", "Autodesk.Revit+2026", "Revit/../AutoCAD", None, 1, [], {}],
)
def test_invalid_engine_fails_before_request(
    monkeypatch: pytest.MonkeyPatch, engine: object,
) -> None:
    request = Mock(side_effect=AssertionError("Invalid engines must not reach APS"))
    monkeypatch.setattr(core.requests, "get", request)

    with pytest.raises(ValueError, match="engine must be one of:"):
        get_engine_queue_stats(cast(AutomationEngine, engine), "test-token")

    request.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 503])
def test_http_failure_is_not_returned_as_queue_data(
    monkeypatch: pytest.MonkeyPatch, status: int,
) -> None:
    response = json_response({"error": "APS request failed"}, status)
    request = Mock(return_value=response)
    monkeypatch.setattr(core.requests, "get", request)

    with pytest.raises(requests.HTTPError) as error:
        get_engine_queue_stats("AutoCAD", "test-token")

    assert error.value.response is response
    request.assert_called_once()


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), requests.ConnectionError("offline")])
def test_transport_failure_reaches_caller(
    monkeypatch: pytest.MonkeyPatch, error: requests.RequestException,
) -> None:
    request = Mock(side_effect=error)
    monkeypatch.setattr(core.requests, "get", request)

    with pytest.raises(type(error)) as raised:
        get_engine_queue_stats("Revit", "test-token")

    assert raised.value is error
    request.assert_called_once()


def test_caller_can_set_http_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = Mock(return_value=json_response({"p50QueueTimeMs": 0.0, "p95QueueTimeMs": 0.0}))
    monkeypatch.setattr(core.requests, "get", request)

    assert get_engine_queue_stats("Revit", "test-token", timeout=12.5) == {
        "p50QueueTimeMs": 0.0, "p95QueueTimeMs": 0.0,
    }
    assert request.call_args.kwargs["timeout"] == 12.5
