from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import requests

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

API_BASE_URL = "https://v3.football.api-sports.io"
JST = ZoneInfo("Asia/Tokyo")

SCHEDULED_STATUSES = {"TBD", "NS"}
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}
FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}
POSTPONED_STATUSES = {"PST", "SUSP", "INT"}
CANCELLED_STATUSES = {"CANC", "ABD"}


@dataclass(frozen=True)
class Competition:
    app_id: str
    api_league_id: int
    name: str
    country: str


COMPETITIONS = (
    Competition("epl", 39, "Premier League", "England"),
    Competition("j1", 98, "J1 League", "Japan"),
)

_http = requests.Session()
_http.headers.update({"User-Agent": "football-schedule-fixture-fetcher/1.0"})


class FixtureDataError(RuntimeError):
    pass


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    bucket_name = _required_env("DATA_BUCKET_NAME")
    parameter_name = _required_env("API_KEY_PARAMETER_NAME")
    object_key = os.getenv("FIXTURE_OBJECT_KEY", "data/fixtures.json")
    lookback_days = _non_negative_int_env("LOOKBACK_DAYS", 1)
    lookahead_days = _non_negative_int_env("LOOKAHEAD_DAYS", 30)

    today_jst = datetime.now(JST).date()
    from_date = today_jst - timedelta(days=lookback_days)
    to_date = today_jst + timedelta(days=lookahead_days)

    LOGGER.info(
        "Starting fixture refresh: from=%s to=%s competitions=%d",
        from_date,
        to_date,
        len(COMPETITIONS),
    )

    api_key = _load_api_key(parameter_name)
    fixtures: list[dict[str, Any]] = []

    # Build the entire document first. S3 is only updated after every competition
    # has been fetched and normalized successfully.
    for competition in COMPETITIONS:
        raw_fixtures = _fetch_competition_fixtures(
            api_key=api_key,
            competition=competition,
            from_date=from_date,
            to_date=to_date,
        )
        normalized = [_normalize_fixture(item, competition) for item in raw_fixtures]
        fixtures.extend(normalized)

        LOGGER.info(
            "Fetched competition: app_id=%s api_league_id=%d season=%d fixtures=%d",
            competition.app_id,
            competition.api_league_id,
            _season_for(today_jst),
            len(normalized),
        )

    fixtures.sort(key=lambda fixture: (fixture["kickoff"], fixture["id"]))

    document = {
        "generatedAt": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "range": {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
        "fixtures": fixtures,
    }

    body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _publish_document(bucket_name=bucket_name, object_key=object_key, body=body)

    LOGGER.info(
        "Published fixture document: bucket=%s key=%s fixtures=%d bytes=%d",
        bucket_name,
        object_key,
        len(fixtures),
        len(body),
    )

    return {
        "ok": True,
        "published": True,
        "fixtureCount": len(fixtures),
        "range": document["range"],
    }


def _fetch_competition_fixtures(
    *,
    api_key: str,
    competition: Competition,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    season = _season_for(from_date)
    page = 1
    fixtures: list[dict[str, Any]] = []

    while True:
        payload = _get_api_json(
            "/fixtures",
            api_key=api_key,
            params={
                "league": competition.api_league_id,
                "season": season,
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "timezone": "Asia/Tokyo",
                "page": page,
            },
        )

        response_items = payload.get("response")
        if not isinstance(response_items, list):
            raise FixtureDataError(
                f"API response is missing a response list for {competition.app_id}"
            )
        fixtures.extend(response_items)

        paging = payload.get("paging") or {}
        try:
            current_page = int(paging.get("current", page))
            total_pages = int(paging.get("total", 1))
        except (TypeError, ValueError) as exc:
            raise FixtureDataError(
                f"Invalid paging data for {competition.app_id}: {paging!r}"
            ) from exc

        if current_page >= total_pages:
            break
        page = current_page + 1

    return fixtures


def _get_api_json(
    path: str,
    *,
    api_key: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = _http.get(
        f"{API_BASE_URL}{path}",
        headers={"x-apisports-key": api_key},
        params=params,
        timeout=(3.05, 10),
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise FixtureDataError("API-Football returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise FixtureDataError("API-Football returned a non-object JSON payload")

    errors = payload.get("errors")
    if errors:
        raise FixtureDataError(f"API-Football returned errors: {errors!r}")

    return payload


def _normalize_fixture(
    raw: dict[str, Any],
    competition: Competition,
) -> dict[str, Any]:
    try:
        fixture = raw["fixture"]
        teams = raw["teams"]
        home = teams["home"]
        away = teams["away"]

        fixture_id = fixture["id"]
        kickoff = fixture["date"]
        status_short = fixture["status"]["short"]
        home_id = home["id"]
        home_name = home["name"]
        away_id = away["id"]
        away_name = away["name"]
    except (KeyError, TypeError) as exc:
        raise FixtureDataError(
            f"Malformed fixture payload for {competition.app_id}: {raw!r}"
        ) from exc

    if not isinstance(kickoff, str):
        raise FixtureDataError(f"Invalid kickoff for fixture {fixture_id}: {kickoff!r}")
    if not isinstance(status_short, str):
        raise FixtureDataError(
            f"Invalid status for fixture {fixture_id}: {status_short!r}"
        )

    goals = raw.get("goals") or {}
    home_goals = goals.get("home") if isinstance(goals, dict) else None
    away_goals = goals.get("away") if isinstance(goals, dict) else None

    score = None
    if isinstance(home_goals, int) and isinstance(away_goals, int):
        score = {"home": home_goals, "away": away_goals}

    return {
        "id": str(fixture_id),
        "competition": {
            "id": competition.app_id,
            "name": competition.name,
            "country": competition.country,
        },
        "home": {
            "id": str(home_id),
            "name": str(home_name),
        },
        "away": {
            "id": str(away_id),
            "name": str(away_name),
        },
        "kickoff": _utc_iso(kickoff),
        "status": _normalize_status(status_short),
        # Keep live scores in JSON; the frontend decides when they are safe to show.
        "score": score,
    }


def _normalize_status(status_short: str) -> str:
    if status_short in SCHEDULED_STATUSES:
        return "scheduled"
    if status_short in LIVE_STATUSES:
        return "live"
    if status_short in FINISHED_STATUSES:
        return "finished"
    if status_short in POSTPONED_STATUSES:
        return "postponed"
    if status_short in CANCELLED_STATUSES:
        return "cancelled"
    raise FixtureDataError(f"Unknown API-Football fixture status: {status_short}")


def _utc_iso(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FixtureDataError(f"Invalid fixture datetime: {value!r}") from exc

    if parsed.tzinfo is None:
        raise FixtureDataError(f"Fixture datetime has no timezone: {value!r}")

    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _season_for(reference_date: date) -> int:
    return reference_date.year if reference_date.month >= 7 else reference_date.year - 1


def _load_api_key(parameter_name: str) -> str:
    response = _ssm_client().get_parameter(Name=parameter_name, WithDecryption=True)
    value = response.get("Parameter", {}).get("Value")
    if not isinstance(value, str) or not value.strip():
        raise FixtureDataError(f"SSM parameter {parameter_name!r} has no value")
    return value.strip()


def _publish_document(*, bucket_name: str, object_key: str, body: bytes) -> None:
    _s3_client().put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=300",
    )


def _ssm_client() -> Any:
    return boto3.client("ssm")


def _s3_client() -> Any:
    return boto3.client("s3")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 0:
        raise RuntimeError(f"{name} must be non-negative")
    return value
