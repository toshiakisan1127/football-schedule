from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3

from team_logos import get_static_team_logo

JST = ZoneInfo("Asia/Tokyo")

SCHEDULED_STATUSES = {"tbd", "ns", "scheduled", "not started"}
LIVE_STATUSES = {"1h", "ht", "2h", "et", "bt", "p", "live"}
FINISHED_STATUSES = {"ft", "aet", "pen", "awd", "wo", "finished"}
POSTPONED_STATUSES = {"pst", "susp", "int", "postponed"}
CANCELLED_STATUSES = {"canc", "abd", "cancelled", "canceled"}


@dataclass(frozen=True)
class Competition:
    app_id: str
    api_league_id: int
    name: str
    country: str


COMPETITIONS = (
    Competition("epl", 39, "Premier League", "England"),
    Competition("laliga", 140, "La Liga", "Spain"),
    Competition("bundesliga", 78, "Bundesliga", "Germany"),
)


class FixtureDataError(RuntimeError):
    pass


def _raw_teams(raw: dict[str, Any]) -> tuple[Any, Any]:
    teams = raw.get("teams")
    if not isinstance(teams, dict):
        return None, None
    return teams.get("home"), teams.get("away")


def _collect_team_ids(raw_fixtures: list[dict[str, Any]]) -> dict[str, str]:
    team_ids: dict[str, str] = {}
    for raw in raw_fixtures:
        if not isinstance(raw, dict):
            continue
        for team in _raw_teams(raw):
            if not isinstance(team, dict):
                continue
            name = team.get("name")
            team_id = team.get("id")
            if isinstance(name, str) and name and team_id not in (None, ""):
                team_ids.setdefault(name, str(team_id))
    return team_ids


def _normalize_team_id(raw_id: Any, team_name: str, team_ids: dict[str, str] | None) -> str:
    if raw_id not in (None, ""):
        return str(raw_id)
    if team_ids is not None and team_ids.get(team_name):
        return team_ids[team_name]
    digest = hashlib.sha256(team_name.encode("utf-8")).hexdigest()[:16]
    return f"team-name-{digest}"


def _normalize_team_logo(team: dict[str, Any]) -> str | None:
    value = team.get("logo")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalized_team(
    raw_team: dict[str, Any], *, team_name: str, team_id: str, competition_id: str
) -> dict[str, str]:
    team = {"id": team_id, "name": team_name}
    logo = get_static_team_logo(competition_id, team_name)
    if logo is None:
        logo = _normalize_team_logo(raw_team)
    if logo is not None:
        team["logo"] = logo
    return team


def _normalize_fixture(
    raw: dict[str, Any], competition: Competition, *, team_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    try:
        fixture = raw["fixture"]
        if not isinstance(fixture, dict):
            raise TypeError("fixture")
        fixture_id = fixture["id"]
        kickoff = fixture["date"]
        raw_status = fixture.get("status")
        home, away = _raw_teams(raw)
        if not isinstance(home, dict) or not isinstance(away, dict):
            raise KeyError("home/away teams")
        home_name = home["name"]
        away_name = away["name"]
        if not isinstance(home_name, str) or not isinstance(away_name, str):
            raise TypeError("team name")
        home_id = _normalize_team_id(home.get("id"), home_name, team_ids)
        away_id = _normalize_team_id(away.get("id"), away_name, team_ids)
        status_value = (
            raw_status.get("short") or raw_status.get("long")
            if isinstance(raw_status, dict)
            else raw_status
        )
    except (KeyError, TypeError) as exc:
        raise FixtureDataError(
            f"Malformed fixture payload for {competition.app_id}: {raw!r}"
        ) from exc

    if not isinstance(kickoff, str):
        raise FixtureDataError(f"Invalid kickoff for fixture {fixture_id}: {kickoff!r}")
    if status_value is not None and not isinstance(status_value, str):
        raise FixtureDataError(f"Invalid status for fixture {fixture_id}: {status_value!r}")

    goals = raw.get("goals")
    if isinstance(goals, dict):
        home_goals, away_goals = goals.get("home"), goals.get("away")
    else:
        home_goals, away_goals = None, None
    score = (
        {"home": home_goals, "away": away_goals}
        if isinstance(home_goals, int) and isinstance(away_goals, int)
        else None
    )

    return {
        "id": str(fixture_id),
        "competition": {
            "id": competition.app_id,
            "name": competition.name,
            "country": competition.country,
        },
        "home": _normalized_team(
            home,
            team_name=home_name,
            team_id=home_id,
            competition_id=competition.app_id,
        ),
        "away": _normalized_team(
            away,
            team_name=away_name,
            team_id=away_id,
            competition_id=competition.app_id,
        ),
        "kickoff": _utc_iso(kickoff),
        "status": _normalize_status(status_value),
        "score": score,
    }


def _normalize_status(status_value: str | None) -> str:
    if status_value is None:
        return "scheduled"
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
    raise FixtureDataError(f"Unknown fixture status: {status_value}")


def _fixture_in_window(fixture: dict[str, Any], *, from_date: date, to_date: date) -> bool:
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
