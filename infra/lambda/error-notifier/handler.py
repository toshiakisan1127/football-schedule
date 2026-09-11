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


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    payload = _decode_logs_payload(event)

    if payload.get("messageType") == "CONTROL_MESSAGE":
        return {"ok": True, "ignored": True, "eventCount": 0}

    log_events = payload.get("logEvents")
    if not isinstance(log_events, list) or not log_events:
        return {"ok": True, "ignored": True, "eventCount": 0}

    lines = [
        "FixtureFetcher emitted ERROR logs.",
        f"logGroup: {payload.get('logGroup', '-')}",
        f"logStream: {payload.get('logStream', '-')}",
        "",
    ]

    for item in log_events:
        if not isinstance(item, dict):
            continue
        timestamp = _format_timestamp(item.get("timestamp"))
        message = str(item.get("message", "")).rstrip()
        lines.append(f"[{timestamp}] {message}")

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
