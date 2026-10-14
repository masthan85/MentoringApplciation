import json
import logging

from app.core.logging import JsonFormatter, bind_log_context, clear_log_context


def test_json_lines_include_context_and_extras() -> None:
    clear_log_context()
    bind_log_context(request_id="abc")
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello %s", ("there",), None)
    record.duration_ms = 12.5
    line = JsonFormatter("svc").format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello there"
    assert payload["level"] == "info"
    assert payload["service"] == "svc"
    assert payload["request_id"] == "abc"
    assert payload["duration_ms"] == 12.5
    clear_log_context()


def test_exceptions_are_serialised() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    payload = json.loads(JsonFormatter("svc").format(record))
    assert "ValueError: boom" in payload["exception"]
