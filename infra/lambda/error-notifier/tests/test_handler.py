from __future__ import annotations

import base64
import gzip
import json
import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault(
    "ALERT_TOPIC_ARN",
    "arn:aws:sns:ap-northeast-1:123456789012:fixture-errors",
)

import handler


class FakeSns:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, **kwargs) -> None:
        self.published.append(kwargs)


class FakeDynamoDb:
    def __init__(self) -> None:
        self.last_notified: dict[str, int] = {}

    def update_item(self, **kwargs) -> None:
        fingerprint = kwargs["Key"]["fingerprint"]["S"]
        values = kwargs["ExpressionAttributeValues"]
        now = int(values[":now"]["N"])
        cutoff = int(values[":cutoff"]["N"])
        previous = self.last_notified.get(fingerprint)
        if previous is not None and previous > cutoff:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "suppressed"}},
                "UpdateItem",
            )
        self.last_notified[fingerprint] = now

    def delete_item(self, **kwargs) -> None:
        fingerprint = kwargs["Key"]["fingerprint"]["S"]
        self.last_notified.pop(fingerprint, None)


def _logs_event(message: str, *, log_group: str = "group", timestamp: int = 0) -> dict:
    payload = {
        "messageType": "DATA_MESSAGE",
        "logGroup": log_group,
        "logStream": "stream",
        "logEvents": [{"timestamp": timestamp, "message": message}],
    }
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode("utf-8"))).decode("ascii")
    return {"awslogs": {"data": encoded}}


def _configure_throttle(monkeypatch, dynamodb=None, sns=None) -> tuple[object, FakeSns]:
    dynamodb = dynamodb or FakeDynamoDb()
    sns = sns or FakeSns()
    monkeypatch.setattr(handler, "DYNAMODB", dynamodb)
    monkeypatch.setattr(handler, "SNS", sns)
    monkeypatch.setattr(handler, "STATE_TABLE_NAME", "alert-state")
    monkeypatch.setattr(handler, "COOLDOWN_SECONDS", 6 * 60 * 60)
    monkeypatch.setattr(handler, "STATE_TTL_SECONDS", 24 * 60 * 60)
    return dynamodb, sns


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


def test_fingerprint_ignores_request_id_timestamp_and_stack_trace() -> None:
    payload = {"logGroup": "live-group", "logStream": "stream-a"}
    first = {
        "timestamp": 1,
        "message": json.dumps(
            {
                "timestamp": "2026-09-13T01:00:00Z",
                "level": "ERROR",
                "message": "Live fixture refresh failed",
                "requestId": "request-a",
                "errorType": "ApiFootballError",
                "errorMessage": "provider unavailable",
                "stackTrace": ["first stack"],
            }
        ),
    }
    second = {
        "timestamp": 2,
        "message": json.dumps(
            {
                "timestamp": "2026-09-13T01:05:00Z",
                "level": "ERROR",
                "message": "Live fixture refresh failed",
                "requestId": "request-b",
                "errorType": "ApiFootballError",
                "errorMessage": "provider unavailable",
                "stackTrace": ["different stack"],
            }
        ),
    }

    assert handler._build_alert_fingerprint(payload, [first]) == handler._build_alert_fingerprint(
        {**payload, "logStream": "stream-b"},
        [second],
    )


def test_repeated_alert_is_suppressed_during_six_hour_cooldown(monkeypatch) -> None:
    _, sns = _configure_throttle(monkeypatch)
    now = 1_000_000
    monkeypatch.setattr(handler.time, "time", lambda: now)
    event = _logs_event("same failure", log_group="live-group")

    first = handler.lambda_handler(event, None)
    now += 5 * 60
    second = handler.lambda_handler(event, None)

    assert first["suppressed"] is False
    assert second["suppressed"] is True
    assert len(sns.published) == 1


def test_same_alert_is_sent_again_after_cooldown(monkeypatch) -> None:
    _, sns = _configure_throttle(monkeypatch)
    now = 2_000_000
    monkeypatch.setattr(handler.time, "time", lambda: now)
    event = _logs_event("same failure", log_group="live-group")

    handler.lambda_handler(event, None)
    now += 6 * 60 * 60
    result = handler.lambda_handler(event, None)

    assert result["suppressed"] is False
    assert len(sns.published) == 2


def test_distinct_error_is_sent_immediately(monkeypatch) -> None:
    _, sns = _configure_throttle(monkeypatch)
    now = 3_000_000
    monkeypatch.setattr(handler.time, "time", lambda: now)

    handler.lambda_handler(_logs_event("provider timeout", log_group="live-group"), None)
    handler.lambda_handler(_logs_event("invalid payload", log_group="live-group"), None)

    assert len(sns.published) == 2


def test_state_store_failure_fails_open_and_sends_alert(monkeypatch) -> None:
    class BrokenDynamoDb:
        def update_item(self, **kwargs) -> None:
            raise RuntimeError("dynamodb unavailable")

    _, sns = _configure_throttle(monkeypatch, dynamodb=BrokenDynamoDb())
    monkeypatch.setattr(handler.time, "time", lambda: 4_000_000)

    result = handler.lambda_handler(_logs_event("provider timeout"), None)

    assert result["suppressed"] is False
    assert len(sns.published) == 1
