import json
from unittest.mock import Mock

import pytest
import requests

from aps_automation_sdk import WorkItem, WorkItemPollEvent
from aps_automation_sdk import core


class PollClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> PollClock:
    timer = PollClock()
    monkeypatch.setattr(core.time, "monotonic", timer.monotonic)
    monkeypatch.setattr(core.time, "sleep", timer.sleep)
    return timer


def status_response(payload: dict[str, object]) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(payload).encode()
    return response


def work_item() -> WorkItem:
    return WorkItem(parameters=[], activity_full_alias="app.RevitActivity+dev")


def test_public_poll_passes_queue_updates_and_clears_position_after_start(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock,
) -> None:
    payloads: list[dict[str, object]] = [
        {"id": "job-id", "status": "pending", "approximateQueuePosition": 5},
        {"id": "job-id", "status": "pending", "approximateQueuePosition": 2},
        {"id": "job-id", "status": "inprogress", "approximateQueuePosition": 2},
        {"id": "job-id", "status": "success", "reportUrl": "https://reports.example.test/job"},
    ]
    request = Mock(side_effect=[status_response(payload) for payload in payloads])
    submit = Mock(side_effect=AssertionError("Polling must not submit another job"))
    monkeypatch.setattr(core.requests, "get", request)
    monkeypatch.setattr(core.requests, "post", submit)
    events: list[WorkItemPollEvent] = []

    result = work_item().poll(
        work_item_id="job-id", token="test-token", interval=2,
        max_wait=60, on_event=events.append,
    )

    assert [event.approximate_queue_position for event in events] == [5, 2, None, None]
    assert [event.status for event in events] == ["pending", "pending", "inprogress", "success"]
    assert [event.elapsed_seconds for event in events] == [0, 2, 4, 6]
    assert [event.is_terminal for event in events] == [False, False, False, True]
    assert all(event.workitem_id == "job-id" and event.max_wait_seconds == 60 for event in events)
    assert events[-1].report_url == payloads[-1]["reportUrl"]
    assert result == payloads[-1]
    assert request.call_count == len(payloads)
    assert all(call.args[0] == f"{core.DA_BASE_URL}/workitems/job-id" for call in request.call_args_list)
    assert all(call.kwargs["headers"]["Authorization"] == "Bearer test-token" for call in request.call_args_list)
    submit.assert_not_called()


@pytest.mark.parametrize("position", [None, 0, -1, True, False, 5.0, 5.5, "5", [], {}])
def test_invalid_beta_position_does_not_break_polling(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock, position: object,
) -> None:
    payload: dict[str, object] = {"status": "pending", "approximateQueuePosition": position}
    monkeypatch.setattr(core.requests, "get", Mock(return_value=status_response(payload)))
    events: list[WorkItemPollEvent] = []

    result = work_item().poll("job-id", "test-token", max_wait=0, on_event=events.append)

    assert events[0].approximate_queue_position is None
    assert result == payload


@pytest.mark.parametrize("position", [1, 5, 2**63])
def test_pending_event_accepts_positive_integer_position(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock, position: int,
) -> None:
    payload: dict[str, object] = {"status": "pending", "approximateQueuePosition": position}
    monkeypatch.setattr(core.requests, "get", Mock(return_value=status_response(payload)))
    events: list[WorkItemPollEvent] = []

    work_item().poll("job-id", "test-token", max_wait=0, on_event=events.append)

    assert events[0].approximate_queue_position == position


@pytest.mark.parametrize("missing_position", [{}, {"approximateQueuePosition": None}])
def test_unavailable_pending_position_does_not_reuse_previous_value(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock,
    missing_position: dict[str, object],
) -> None:
    payloads: list[dict[str, object]] = [
        {"status": "pending", "approximateQueuePosition": 5},
        {"status": "pending", **missing_position},
        {"status": "success"},
    ]
    monkeypatch.setattr(core.requests, "get", Mock(side_effect=[status_response(p) for p in payloads]))
    events: list[WorkItemPollEvent] = []

    work_item().poll("job-id", "test-token", on_event=events.append)

    assert [event.approximate_queue_position for event in events] == [5, None, None]


@pytest.mark.parametrize("status", ["inprogress", "success", "failedInstructions", "cancelled"])
def test_nonpending_status_does_not_expose_queue_position(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock, status: str,
) -> None:
    payload: dict[str, object] = {"status": status, "approximateQueuePosition": 5}
    monkeypatch.setattr(core.requests, "get", Mock(return_value=status_response(payload)))
    events: list[WorkItemPollEvent] = []

    work_item().poll("job-id", "test-token", max_wait=0, on_event=events.append)

    assert events[0].approximate_queue_position is None


def test_existing_event_constructors_remain_valid() -> None:
    positional = WorkItemPollEvent("job-id", "pending", 0, 600, None, False)
    keyword = WorkItemPollEvent(
        workitem_id="job-id", status="pending", elapsed_seconds=0,
        max_wait_seconds=600, report_url=None, is_terminal=False,
    )
    assert positional == keyword
    assert positional.approximate_queue_position is None


def test_existing_callback_can_ignore_new_field(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock,
) -> None:
    payloads: list[dict[str, object]] = [
        {"status": "pending", "approximateQueuePosition": 5},
        {"status": "success", "reportUrl": "https://reports.example.test/job"},
    ]
    monkeypatch.setattr(core.requests, "get", Mock(side_effect=[status_response(p) for p in payloads]))
    messages: list[tuple[str, str, int, int, str | None, bool]] = []

    def existing_callback(event: WorkItemPollEvent) -> None:
        messages.append((event.workitem_id, event.status, event.elapsed_seconds,
                         event.max_wait_seconds, event.report_url, event.is_terminal))

    result = work_item().poll("job-id", "test-token", interval=2, on_event=existing_callback)

    assert messages == [
        ("job-id", "pending", 0, 600, None, False),
        ("job-id", "success", 2, 600, "https://reports.example.test/job", True),
    ]
    assert result == payloads[-1]


def test_poll_without_callback_preserves_raw_response(
    monkeypatch: pytest.MonkeyPatch, clock: PollClock,
) -> None:
    payload: dict[str, object] = {"status": "pending", "approximateQueuePosition": 5}
    request = Mock(return_value=status_response(payload))
    monkeypatch.setattr(core.requests, "get", request)

    assert work_item().poll("job-id", "test-token", max_wait=0) == payload
    assert request.call_count == 1
