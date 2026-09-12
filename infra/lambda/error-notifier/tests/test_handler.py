from __future__ import annotations

import json
import os
from datetime import datetime, timezone

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault(
    "ALERT_TOPIC_ARN",
    "arn:aws:sns:ap-northeast-1:123456789012:fixture-errors",
)

import handler


def test_format_alert_unwraps_structured_logger_message() -> None:
    summary = {
        "level": "ERROR",
        "message": "Fixture refresh completed with failures",
        "requestId": "cb4dbcef-962f-4028-b3e6-cf47354cf6b2",
        "provider": "API-Football",
        "failureCount": 1,
        "failedCompetitions": ["j1"],
        "primaryCause": "ApiFootballError",
        "failures": [
            {
                "competition": "j1",
                "provider": "API-Football",
                "errorType": "ApiFootballError",
                "errorMessage": (
                    "API-Football returned errors: "
                    "{'page': 'The Page field do not exist.'}"
                ),
                "statusCode": None,
            }
        ],
    }
    structured_log = {
        "timestamp": "2026-09-12T15:54:46Z",
        "level": "ERROR",
        "message": json.dumps(summary),
        "logger": "root",
        "requestId": "cb4dbcef-962f-4028-b3e6-cf47354cf6b2",
    }
    event_timestamp = int(
        datetime(2026, 9, 12, 15, 54, 46, tzinfo=timezone.utc).timestamp() * 1000
    )
    payload = {
        "logGroup": "FootballScheduleDataStack-FixtureFetcherLogGroup",
        "logStream": "2026/09/12/FixtureFetcher[$LATEST]abc",
    }

    lines = handler._format_alert(
        payload,
        [{"timestamp": event_timestamp, "message": json.dumps(structured_log)}],
    )
    message = "\n".join(lines)

    assert message.startswith("[FixtureFetcher] Fixture refresh failed")
    assert "Cause: ApiFootballError" in message
    assert "Failed: 1 competition" in message
    assert "- j1 (API-Football)" in message
    assert "  ApiFootballError" in message
    assert "The Page field do not exist." in message
    assert "Request ID: cb4dbcef-962f-4028-b3e6-cf47354cf6b2" in message
    assert "Time: 2026-09-12T15:54:46+00:00" in message
    assert "\nDebug\nlogGroup:" in message
    assert "FixtureFetcher emitted ERROR logs." not in message
    assert '"stackTrace"' not in message


def test_extract_failure_summary_keeps_direct_summary_compatibility() -> None:
    summary = {
        "message": "Fixture refresh completed with failures",
        "failureCount": 1,
    }

    assert handler._extract_failure_summary(json.dumps(summary)) == summary


def test_format_alert_falls_back_for_unknown_error_log() -> None:
    payload = {"logGroup": "group", "logStream": "stream"}

    lines = handler._format_alert(
        payload,
        [{"timestamp": 0, "message": "plain unknown error"}],
    )

    assert lines[0] == "FixtureFetcher emitted ERROR logs."
    assert lines[-1].endswith("plain unknown error")
