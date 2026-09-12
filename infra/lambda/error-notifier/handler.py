from __future__ import annotations

import base64
import gzip
import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3

SNS = boto3.client("sns")
TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]
MAX_MESSAGE_BYTES = 240_000
SUMMARY_MESSAGE = "Fixture refresh completed with failures"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    payload = _decode_logs_payload(event)

    if payload.get("messageType") == "CONTROL_MESSAGE":
        return {"ok": True, "ignored": True, "eventCount": 0}

    log_events = payload.get("logEvents")
    if not isinstance(log_events, list) or not log_events:
        return {"ok": True, "ignored": True, "eventCount": 0}

    lines = _format_alert(payload, log_events)
    message = _truncate_utf8("\n".join(lines), MAX_MESSAGE_BYTES)

    SNS.publish(
        TopicArn=TOPIC_ARN,
        Subject="[Match Calendar] Fixture batch ERROR",
        Message=message,
    )

    return {"ok": True, "ignored": False, "eventCount": len(log_events)}


def _decode_logs_payload(event: dict[str, Any]) -> dict[str, Any]:
    awslogs = event.get("awslogs")
    if not isinstance(awslogs, dict):
        raise ValueError("awslogs payload is missing")

    encoded = awslogs.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("awslogs.data is missing")

    decoded = gzip.decompress(base64.b64decode(encoded))
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("decoded CloudWatch Logs payload must be an object")
    return payload


def _format_timestamp(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown-time"

    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value

    suffix = "\n\n[truncated]"
    suffix_bytes = suffix.encode("utf-8")
    truncated = encoded[: max_bytes - len(suffix_bytes)]

    while truncated:
        try:
            return truncated.decode("utf-8") + suffix
        except UnicodeDecodeError:
            truncated = truncated[:-1]

    return suffix


def _parse_json_object(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_failure_summary(raw_message: str) -> dict[str, Any] | None:
    parsed = _parse_json_object(raw_message)
    if parsed is None:
        return None

    if parsed.get("message") == SUMMARY_MESSAGE:
        return parsed

    nested_message = parsed.get("message")
    if not isinstance(nested_message, str):
        return None

    nested = _parse_json_object(nested_message)
    if nested is not None and nested.get("message") == SUMMARY_MESSAGE:
        return nested

    return None


def _format_failure(summary: dict[str, Any]) -> list[str]:
    competition = str(summary.get("competition", "?"))
    provider = summary.get("provider")
    provider_text = f" ({provider})" if provider else ""
    error_type = str(summary.get("errorType", "Error"))
    status = summary.get("statusCode")
    status_text = f" (HTTP {status})" if status is not None else ""
    error_message = str(summary.get("errorMessage", "")).strip()

    lines = [f"- {competition}{provider_text}", f"  {error_type}{status_text}"]
    if error_message:
        lines.append(f"  {error_message}")
    return lines


def _format_summary_alert(
    payload: dict[str, Any],
    timestamp: str,
    summary: dict[str, Any],
) -> list[str]:
    competitions = summary.get("failedCompetitions")
    if not isinstance(competitions, list):
        competitions = []

    failure_count = summary.get("failureCount", len(competitions))
    suffix = "competition" if failure_count == 1 else "competitions"
    lines = [
        "[FixtureFetcher] Fixture refresh failed",
        "",
        f"Cause: {summary.get('primaryCause', 'Unknown error')}",
        f"Failed: {failure_count} {suffix}",
    ]

    failures = summary.get("failures")
    if isinstance(failures, list) and failures:
        for failure in failures:
            if isinstance(failure, dict):
                lines.extend(_format_failure(failure))
    else:
        lines.extend(f"- {competition}" for competition in competitions)

    lines.extend(
        [
            "",
            f"Request ID: {summary.get('requestId') or '-'}",
            f"Time: {timestamp}",
            f"Provider: {summary.get('provider', '-')}",
            "",
            "Debug",
            f"logGroup: {payload.get('logGroup', '-')}",
            f"logStream: {payload.get('logStream', '-')}",
        ]
    )
    return lines


def _format_alert(payload: dict[str, Any], log_events: list[Any]) -> list[str]:
    summaries: list[tuple[str, dict[str, Any]]] = []
    raw_events: list[tuple[str, str]] = []

    for item in log_events:
        if not isinstance(item, dict):
            continue
        timestamp = _format_timestamp(item.get("timestamp"))
        raw_message = str(item.get("message", "")).rstrip()
        raw_events.append((timestamp, raw_message))

        summary = _extract_failure_summary(raw_message)
        if summary is not None:
            summaries.append((timestamp, summary))

    if len(summaries) == 1:
        timestamp, summary = summaries[0]
        return _format_summary_alert(payload, timestamp, summary)

    lines = [
        "FixtureFetcher emitted ERROR logs.",
        f"logGroup: {payload.get('logGroup', '-')}",
        f"logStream: {payload.get('logStream', '-')}",
        "",
    ]
    lines.extend(f"[{timestamp}] {message}" for timestamp, message in raw_events)
    return lines
