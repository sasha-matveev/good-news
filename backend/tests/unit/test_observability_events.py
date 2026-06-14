from __future__ import annotations

import json

from app.core.observability import emit_event, record_analysis_failure, record_delivery_run


def _captured_events(capsys) -> list[dict]:
    out = capsys.readouterr().out.strip().splitlines()
    return [json.loads(line) for line in out if line.strip().startswith("{")]


def test_emit_event_writes_structured_json_line(capsys) -> None:
    emit_event("custom_event", severity="WARNING", foo="bar", count=3)

    events = _captured_events(capsys)
    assert events == [{"severity": "WARNING", "event": "custom_event", "foo": "bar", "count": 3}]


def test_record_analysis_failure_emits_event(capsys) -> None:
    record_analysis_failure(reason="write_failed")

    events = _captured_events(capsys)
    assert {"severity": "WARNING", "event": "analysis_failed", "reason": "write_failed"} in events


def test_record_delivery_run_marks_failed_as_warning(capsys) -> None:
    record_delivery_run(digest_type="daily", status="failed")
    record_delivery_run(digest_type="daily", status="sent")

    events = _captured_events(capsys)
    by_status = {e["status"]: e["severity"] for e in events if e["event"] == "delivery_run"}
    assert by_status == {"failed": "WARNING", "sent": "INFO"}
