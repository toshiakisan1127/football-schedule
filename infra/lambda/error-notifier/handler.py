from __future__ import annotations

import base64
import gzip
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

SNS = boto3.client("sns")
DYNAMODB = boto3.client("dynamodb")
TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]
STATE_TABLE_NAME = os.getenv("ALERT_STATE_TABLE_NAME", "")
COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "21600"))
STATE_TTL_SECONDS = int(os.getenv("ALERT_STATE_TTL_SECONDS", "86400"))
MAX_MESSAGE_BYTES = 240_000
SUMMARY_MESSAGE = "Fixture refresh completed with failures"
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
VOLATILE_FINGERPRINT_KEYS = {
    "timestamp",
    "requestId",
    "request_id",
    "awsRequestId",
    "stackTrace",
    "logStream",
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    payload = _decode_logs_payload(event)

    if payload.get("messageType") == "CONTROL_MESSAGE":
        return {"ok": True, "ignored": True, "eventCount": 0}

    log_events = payload.get("logEvents")
    if not isinstance(log_events, list) or not log_events:
        return {"ok": True, "ignored": True, "eventCount": 0}

    fingerprint = _build_alert_fingerprint(payload, log_events)
    now_epoch = int(time.time())
    if not _claim_notification(fingerprint, now_epoch):
        LOGGER.info("Suppressed repeated error alert: fingerprint=%s", fingerprint)
        return {
            "ok": True,
            "ignored": True,
            "suppressed": True,
            "eventCount": len(log_events),
            "fingerprint": fingerprint,
        }

    lines = _format_alert(payload, log_events)
    message = _truncate_utf8("\n".join(lines), MAX_MESSAGE_BYTES)

    try:
        SNS.publish(
            TopicArn=TOPIC_ARN,
            Subject="[Match Calendar] Fixture batch ERROR",
            Message=message,
        )
    except Exception:
        _release_notification_claim(fingerprint, now_epoch)
        raise

    return {
        "ok": True,
        "ignored": False,
        "suppressed": False,
        "eventCount": len(log_events),
        "fingerprint": fingerprint,
    }


def _claim_notification(fingerprint: str, now_epoch: int) -> bool:
    if not STATE_TABLE_NAME:
        LOGGER.error("ALERT_STATE_TABLE_NAME is not configured; sending alert without throttling")
        return True

    cutoff = now_epoch - COOLDOWN_SECONDS
    expires_at = now_epoch + STATE_TTL_SECONDS
    try:
        DYNAMODB.update_item(
            TableName=STATE_TABLE_NAME,
            Key={"fingerprint": {"S": fingerprint}},
            UpdateExpression="SET lastNotifiedAt = :now, expiresAt = :expiresAt",
            ConditionExpression=(
                "attribute_not_exists(fingerprint) OR lastNotifiedAt <= :cutoff"
            ),
            ExpressionAttributeValues={
                ":now": {"N": str(now_epoch)},
                ":cutoff": {"N": str(cutoff)},
                ":expiresAt": {"N": str(expires_at)},
            },
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        LOGGER.exception("Failed to update alert throttle state; sending alert fail-open")
        return True
    except Exception:
        LOGGER.exception("Failed to update alert throttle state; sending alert fail-open")
        return True


def _release_notification_claim(fingerprint: str, now_epoch: int) -> None:
    if not STATE_TABLE_NAME:
        return
    try:
        DYNAMODB.delete_item(
            TableName=STATE_TABLE_NAME,
            Key={"fingerprint": {"S": fingerprint}},
            ConditionExpression="lastNotifiedAt = :now",
            ExpressionAttributeValues={":now": {"N": str(now_epoch)}},
        )
    except Exception:
        LOGGER.exception("Failed to release alert throttle claim after SNS publish failure")


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


def _normalize_fingerprint_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_fingerprint_value(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_FINGERPRINT_KEYS
        }
    if isinstance(value, list):
        return [_normalize_fingerprint_value(item) for item in value]
    if isinstance(value, str):
        nested = _parse_json_object(value)
        if nested is not None:
            return _normalize_fingerprint_value(nested)
        return value.strip()
    return value


def _event_fingerprint_identity(item: Any) -> Any:
    if not isinstance(item, dict):
        return str(item)

    raw_message = str(item.get("message", "")).strip()
    summary = _extract_failure_summary(raw_message)
    if summary is not None:
        return _normalize_fingerprint_value(summary)

    parsed = _parse_json_object(raw_message)
    if parsed is not None:
        return _normalize_fingerprint_value(parsed)
    return raw_message


def _build_alert_fingerprint(payload: dict[str, Any], log_events: list[Any]) -> str:
    identity = {
        "logGroup": payload.get("logGroup", "-"),
        "events": [_event_fingerprint_identity(item) for item in log_events],
    }
    serialized = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
