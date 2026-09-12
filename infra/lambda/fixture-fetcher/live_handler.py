from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from api_football import fetch_live_fixtures
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
LIVE_LEAGUE_IDS = tuple(LEAGUE_TO_COMPETITION)


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    del event, context

    bucket_name = legacy._required_env("DATA_BUCKET_NAME")
    object_prefix = os.getenv("FIXTURE_OBJECT_PREFIX", "data/fixtures").strip("/")
    parameter_name = legacy._required_env("API_FOOTBALL_KEY_PARAMETER_NAME")
    api_key = legacy._load_api_key(parameter_name)

    raw_fixtures = fetch_live_fixtures(
        api_key=api_key,
        league_ids=LIVE_LEAGUE_IDS,
    )
    document = _build_live_document(raw_fixtures)
    object_key = f"{object_prefix}/live.json" if object_prefix else "live.json"
    body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    legacy._s3_client().put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=60",
    )

    LOGGER.info(
        "Published live fixture document: bucket=%s key=%s fixtures=%d bytes=%d",
        bucket_name,
        object_key,
        len(document["fixtures"]),
        len(body),
    )

    return {
        "ok": True,
        "published": True,
        "objectKey": object_key,
        "fixtureCount": len(document["fixtures"]),
    }


def _build_live_document(raw_fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    fixtures = [_normalize_live_fixture(raw) for raw in raw_fixtures]
    fixtures.sort(key=lambda fixture: (fixture["competitionId"], fixture["id"]))

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "fixtures": fixtures,
    }


def _normalize_live_fixture(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        fixture = raw["fixture"]
        league = raw["league"]
        goals = raw["goals"]
        fixture_id = fixture["id"]
        league_id = int(league["id"])
        status = fixture["status"]
        home_score = goals["home"]
        away_score = goals["away"]
    except (KeyError, TypeError, ValueError) as exc:
        raise legacy.FixtureDataError(f"Malformed live fixture payload: {raw!r}") from exc

    competition_id = LEAGUE_TO_COMPETITION.get(league_id)
    if competition_id is None:
        raise legacy.FixtureDataError(f"Unexpected live fixture league ID: {league_id}")
    if not isinstance(status, dict):
        raise legacy.FixtureDataError(f"Malformed live fixture status: {status!r}")
    if not isinstance(home_score, int) or not isinstance(away_score, int):
        raise legacy.FixtureDataError(
            f"Malformed live fixture score for {fixture_id}: {goals!r}"
        )

    elapsed = status.get("elapsed")
    extra = status.get("extra")
    status_short = status.get("short")
    if not isinstance(elapsed, int):
        raise legacy.FixtureDataError(
            f"Live fixture {fixture_id} has invalid elapsed minute: {elapsed!r}"
        )
    if extra is not None and not isinstance(extra, int):
        raise legacy.FixtureDataError(
            f"Live fixture {fixture_id} has invalid extra minute: {extra!r}"
        )
    if not isinstance(status_short, str) or not status_short:
        raise legacy.FixtureDataError(
            f"Live fixture {fixture_id} has invalid short status: {status_short!r}"
        )

    raw_events = raw.get("events")
    events = (
        [_normalize_event(event) for event in raw_events if isinstance(event, dict)]
        if isinstance(raw_events, list)
        else []
    )
    events.sort(key=lambda event: (event["elapsed"], event["extra"] or 0))

    return {
        "id": str(fixture_id),
        "competitionId": competition_id,
        "statusShort": status_short,
        "elapsed": elapsed,
        "extra": extra,
        "score": {
            "home": home_score,
            "away": away_score,
        },
        "events": events,
    }


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    time = raw.get("time") if isinstance(raw.get("time"), dict) else {}
    team = raw.get("team") if isinstance(raw.get("team"), dict) else {}
    player = raw.get("player") if isinstance(raw.get("player"), dict) else {}
    assist = raw.get("assist") if isinstance(raw.get("assist"), dict) else {}

    elapsed = time.get("elapsed")
    extra = time.get("extra")
    if not isinstance(elapsed, int):
        raise legacy.FixtureDataError(f"Live event has invalid elapsed minute: {raw!r}")
    if extra is not None and not isinstance(extra, int):
        raise legacy.FixtureDataError(f"Live event has invalid extra minute: {raw!r}")

    raw_type = raw.get("type")
    event_type = _event_type(raw_type)

    return {
        "elapsed": elapsed,
        "extra": extra,
        "teamId": str(team["id"]) if team.get("id") not in (None, "") else None,
        "player": player.get("name") if isinstance(player.get("name"), str) else None,
        "assist": assist.get("name") if isinstance(assist.get("name"), str) else None,
        "type": event_type,
        "detail": raw.get("detail") if isinstance(raw.get("detail"), str) else None,
        "comments": raw.get("comments") if isinstance(raw.get("comments"), str) else None,
    }


def _event_type(raw_type: Any) -> str:
    if not isinstance(raw_type, str):
        return "other"

    normalized = raw_type.strip().lower()
    if normalized == "goal":
        return "goal"
    if normalized == "card":
        return "card"
    if normalized in {"subst", "substitution"}:
        return "substitution"
    return "other"
