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

API_BASE_URL = "https://api.kickoffapi.com"
JST = ZoneInfo("Asia/Tokyo")

SCHEDULED_STATUSES = {"tbd", "ns", "scheduled", "not started"}
LIVE_STATUSES = {"1h", "ht", "2h", "et", "bt", "p", "live"}
FINISHED_STATUSES = {"ft", "aet", "pen", "awd", "wo", "finished"}
POSTPONED_STATUSES = {"pst", "susp", "int", "postponed"}
CANCELLED_STATUSES = {"canc", "abd", "cancelled", "canceled"}


@dataclass(frozen=True)
class Competition:
    app_id: str
    api_league_id: str
    name: str
    country: str


COMPETITIONS = (
    Competition("epl", "en.1", "Premier League", "England"),
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
    lookahead_days = _non_negative_int_env("LOOKAHEAD_DAYS", 14)

    today_jst = datetime.now(JST).date()
    from_date = today_jst - timedelta(days=lookback_days)
    to_date = today_jst + timedelta(days=lookahead_days)
    season = _season_for(today_jst)

    LOGGER.info(
        "Starting fixture refresh: from=%s to=%s season=%d competitions=%d",
        from_date,
        to_date,
        season,
        len(COMPETITIONS),
    )

    api_key = _load_api_key(parameter_name)
    fixtures: list[dict[str, Any]] = []

    # Build the entire document first. S3 is only updated after every competition
    # has been fetched, normalized and filtered successfully.
    for competition in COMPETITIONS:
        raw_fixtures = _fetch_competition_fixtures(
            api_key=api_key,
            competition=competition,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
        normalized = [
            fixture
            for item in raw_fixtures
            if _fixture_in_window(
                fixture := _normalize_fixture(item, competition),
                from_date=from_date,
                to_date=to_date,
            )
        ]
        fixtures.extend(normalized)

        LOGGER.info(
            "Fetched competition: app_id=%s api_league_id=%s season=%d raw=%d kept=%d",
            competition.app_id,
            competition.api_league_id,
            season,
            len(raw_fixtures),
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
    season: int,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    cursor: str | None = None
    page = 1
    seen_cursors: set[str] = set()

    while True:
        params: dict[str, Any] = {
            "league": competition.api_league_id,
            "season": season,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        if cursor is not None:
            params["cursor"] = cursor
        elif page > 1:
            params["page"] = page

        payload = _get_api_json(
            "/api/v2/fixtures",
            api_key=api_key,
            params=params,
        )

        response_items = payload.get("data")
        if not isinstance(response_items, list):
            raise FixtureDataError(
                f"KickoffAPI response is missing a data list for {competition.app_id}"
            )
        fixtures.extend(response_items)

        meta = payload.get("meta")
        if isinstance(meta, dict):
            next_cursor = meta.get("nextCursor")
            if next_cursor not in (None, ""):
                next_cursor_value = str(next_cursor)
                if next_cursor_value in seen_cursors:
                    raise FixtureDataError(
                        f"KickoffAPI repeated cursor for {competition.app_id}: "
                        f"{next_cursor_value!r}"
                    )
                seen_cursors.add(next_cursor_value)
                cursor = next_cursor_value
                continue
            return fixtures

        # KickoffAPI's migration documentation describes page/totalPages at the
        # top level, while current production responses use meta.nextCursor.
        # Supporting both keeps the fetcher tolerant of either v2 envelope.
        try:
            current_page = int(payload.get("page", page))
            total_pages = int(payload.get("totalPages", current_page))
        except (TypeError, ValueError) as exc:
            raise FixtureDataError(
                f"Invalid KickoffAPI paging data for {competition.app_id}"
            ) from exc

        if current_page >= total_pages:
            return fixtures
        page = current_page + 1


def _get_api_json(
    path: str,
    *,
    api_key: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = _http.get(
        f"{API_BASE_URL}{path}",
        headers={"x-api-key": api_key},
        params=params,
        timeout=(3.05, 180),
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise FixtureDataError("KickoffAPI returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise FixtureDataError("KickoffAPI returned a non-object JSON payload")

    errors = payload.get("errors") or payload.get("error")
    if errors:
        raise FixtureDataError(f"KickoffAPI returned errors: {errors!r}")

    return payload


def _normalize_fixture(
    raw: dict[str, Any],
    competition: Competition,
) -> dict[str, Any]:
    try:
        fixture_id = raw["id"]
        kickoff = raw["date"]

        home = raw.get("home") or raw.get("homeTeam")
        away = raw.get("away") or raw.get("awayTeam")
        if not isinstance(home, dict) or not isinstance(away, dict):
            raise KeyError("home/away teams")

        home_id = home["id"]
        home_name = home["name"]
        away_id = away["id"]
        away_name = away["name"]

        raw_status = raw["status"]
        if isinstance(raw_status, dict):
            status_value = raw_status.get("short") or raw_status.get("long")
        else:
            status_value = raw_status
    except (KeyError, TypeError) as exc:
        raise FixtureDataError(
            f"Malformed fixture payload for {competition.app_id}: {raw!r}"
        ) from exc

    if not isinstance(kickoff, str):
        raise FixtureDataError(f"Invalid kickoff for fixture {fixture_id}: {kickoff!r}")
    if not isinstance(status_value, str):
        raise FixtureDataError(
            f"Invalid status for fixture {fixture_id}: {status_value!r}"
        )

    score_raw = raw.get("score")
    if isinstance(score_raw, dict):
        home_goals = score_raw.get("home")
        away_goals = score_raw.get("away")
    else:
        home_goals = raw.get("homeScore")
        away_goals = raw.get("awayScore")

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
        "status": _normalize_status(status_value),
        # Keep live scores in JSON; the frontend decides when they are safe to show.
        "score": score,
    }


def _normalize_status(status_value: str) -> str:
    normalized = status_value.strip().lower()
    if normalized in SCHEDULED_STATUSES:
        return "scheduled"
    if normalized in LIVE_STATUSES:
        return "live"
    if normalized in FINISHED_STATUSES:
        return "finished"
    if normalized in POSTPONED_STATUSES:
        return "postponed"
    if normalized in CANCELLED_STATUSES:
        return "cancelled"
    raise FixtureDataError(f"Unknown KickoffAPI fixture status: {status_value}")


def _fixture_in_window(
    fixture: dict[str, Any],
    *,
    from_date: date,
    to_date: date,
) -> bool:
    kickoff = fixture.get("kickoff")
    if not isinstance(kickoff, str):
        raise FixtureDataError(f"Normalized fixture has invalid kickoff: {kickoff!r}")

    fixture_date_jst = _parse_datetime(kickoff).astimezone(JST).date()
    return from_date <= fixture_date_jst <= to_date


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FixtureDataError(f"Invalid fixture datetime: {value!r}") from exc

    if parsed.tzinfo is None:
        raise FixtureDataError(f"Fixture datetime has no timezone: {value!r}")

    return parsed


def _utc_iso(value: str) -> str:
    return (
        _parse_datetime(value)
        .astimezone(timezone.utc)
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
