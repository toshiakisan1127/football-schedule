from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from api_football import LIVE_LEAGUE_IDS, fetch_live_fixtures
import handler as legacy

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

LEAGUE_TO_COMPETITION = {
    39: "epl",
    140: "laliga",
    78: "bundesliga",
    61: "ligue1",
    98: "j1",
    2: "ucl",
    3: "uel",
    848: "uecl",
}
SUPPORTED_EVENT_TYPES = {
    "goal": "goal",
    "card": "card",
    "subst": "substitution",
}


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    del event, context

    bucket_name = legacy._required_env("DATA_BUCKET_NAME")
    object_key = os.getenv("LIVE_FIXTURE_OBJECT_KEY", "data/fixtures/live.json").strip("/")
    parameter_name = legacy._required_env("API_FOOTBALL_KEY_PARAMETER_NAME")
    api_key = legacy._load_api_key(parameter_name)

    try:
        raw_fixtures = fetch_live_fixtures(api_key=api_key, league_ids=LIVE_LEAGUE_IDS)
        document = _build_live_document(raw_fixtures)
        body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        legacy._s3_client().put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=body,
            ContentType="application/json; charset=utf-8",
            CacheControl="public, max-age=60",
        )
    except Exception:
        LOGGER.exception("Live fixture refresh failed")
        raise

    LOGGER.info(
        "Published live fixture snapshot: bucket=%s key=%s fixtures=%d bytes=%d",
        bucket_name,
        object_key,
        len(document["fixtures"]),
        len(body),
    )
    return {
        "ok": True,
        "objectKey": object_key,
        "fixtureCount": len(document["fixtures"]),
        "generatedAt": document["generatedAt"],
    }


def _build_live_document(raw_fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    fixtures = [_normalize_live_fixture(item) for item in raw_fixtures]
    fixtures.sort(key=lambda fixture: fixture["id"])
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "fixtures": fixtures,
    }


def _normalize_live_fixture(raw: dict[str, Any]) -> dict[str, Any]:
    fixture = _required_dict(raw, "fixture")
    league = _required_dict(raw, "league")
    goals = _required_dict(raw, "goals")
    status = _required_dict(fixture, "status")

    fixture_id = fixture.get("id")
    league_id = league.get("id")
    home_goals = goals.get("home")
    away_goals = goals.get("away")

    if fixture_id in (None, ""):
        raise legacy.FixtureDataError("Live fixture is missing fixture.id")
    if not isinstance(league_id, int) or league_id not in LEAGUE_TO_COMPETITION:
        raise legacy.FixtureDataError(f"Unsupported live fixture league: {league_id!r}")
    if not isinstance(home_goals, int) or not isinstance(away_goals, int):
        raise legacy.FixtureDataError(
            f"Live fixture {fixture_id} has invalid goals: {goals!r}"
        )

    elapsed = status.get("elapsed")
    extra = status.get("extra")
    short_status = status.get("short")
    if elapsed is not None and not isinstance(elapsed, int):
        raise legacy.FixtureDataError(f"Live fixture {fixture_id} has invalid elapsed time")
    if extra is not None and not isinstance(extra, int):
        raise legacy.FixtureDataError(f"Live fixture {fixture_id} has invalid extra time")
    if not isinstance(short_status, str) or not short_status:
        raise legacy.FixtureDataError(f"Live fixture {fixture_id} has invalid status")

    raw_events = raw.get("events")
    events = []
    if isinstance(raw_events, list):
        events = [
            normalized
            for raw_event in raw_events
            if isinstance(raw_event, dict)
            if (normalized := _normalize_event(raw_event)) is not None
        ]

    return {
        "id": str(fixture_id),
        "competitionId": LEAGUE_TO_COMPETITION[league_id],
        "period": short_status,
        "elapsed": elapsed,
        "extra": extra,
        "score": {"home": home_goals, "away": away_goals},
        "events": events,
    }


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    raw_type = raw.get("type")
    if not isinstance(raw_type, str):
        return None
    event_type = SUPPORTED_EVENT_TYPES.get(raw_type.strip().lower())
    if event_type is None:
        return None

    time = raw.get("time") if isinstance(raw.get("time"), dict) else {}
    team = raw.get("team") if isinstance(raw.get("team"), dict) else {}
    player = raw.get("player") if isinstance(raw.get("player"), dict) else {}
    assist = raw.get("assist") if isinstance(raw.get("assist"), dict) else {}

    elapsed = time.get("elapsed")
    extra = time.get("extra")
    if elapsed is not None and not isinstance(elapsed, int):
        elapsed = None
    if extra is not None and not isinstance(extra, int):
        extra = None

    return {
        "type": event_type,
        "detail": _optional_string(raw.get("detail")),
        "elapsed": elapsed,
        "extra": extra,
        "teamId": _optional_id(team.get("id")),
        "teamName": _optional_string(team.get("name")),
        "player": _optional_string(player.get("name")),
        "assist": _optional_string(assist.get("name")),
    }


def _required_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise legacy.FixtureDataError(f"Live fixture payload is missing {key}")
    return value


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_id(value: Any) -> str | None:
    return None if value in (None, "") else str(value)
