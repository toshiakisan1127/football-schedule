from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import requests

from laliga_v2 import LaLigaV2SelectionError, select_canonical_fixtures
from team_logos import get_static_team_logo
from validation import SCHEMA_VERSION, FixtureDocumentValidationError, validate_fixture_document

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
API_BASE_URL = "https://api.kickoffapi.com"
JST = ZoneInfo("Asia/Tokyo")
V2_LEAGUE_IDS = {
    "laliga": "es.1",
    "bundesliga": "de.1",
}

SCHEDULED_STATUSES = {"tbd", "ns", "scheduled", "not started"}
LIVE_STATUSES = {"1h", "ht", "2h", "et", "bt", "p", "live"}
FINISHED_STATUSES = {"ft", "aet", "pen", "awd", "wo", "finished"}
POSTPONED_STATUSES = {"pst", "susp", "int", "postponed"}
CANCELLED_STATUSES = {"canc", "abd", "cancelled", "canceled"}
TEAM_LOGO_KEYS = ("logo", "image", "crest")


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
        "Starting fixture refresh: providers=mixed from=%s to=%s season=%d competitions=%d",
        from_date, to_date, season, len(COMPETITIONS),
    )
    api_key = _load_api_key(parameter_name)
    fixtures: list[dict[str, Any]] = []

    for competition in COMPETITIONS:
        raw_fixtures = _fetch_competition_fixtures(
            api_key=api_key,
            competition=competition,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
        team_ids = _collect_team_ids(raw_fixtures)
        normalized = [
            fixture
            for item in raw_fixtures
            if _fixture_in_window(
                fixture := _normalize_fixture(item, competition, team_ids=team_ids),
                from_date=from_date,
                to_date=to_date,
            )
        ]
        fixtures.extend(normalized)
        provider_league_id = V2_LEAGUE_IDS.get(competition.app_id)
        provider = "v2" if provider_league_id is not None else "v1"
        LOGGER.info(
            "Fetched competition: provider=%s app_id=%s api_league_id=%s season=%d raw=%d kept=%d",
            provider,
            competition.app_id,
            provider_league_id or competition.api_league_id,
            season,
            len(raw_fixtures),
            len(normalized),
        )

    fixtures.sort(key=lambda fixture: (fixture["kickoff"], fixture["id"]))
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "range": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "fixtures": fixtures,
    }
    _validate_document(document)

    body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _publish_document(bucket_name=bucket_name, object_key=object_key, body=body)
    LOGGER.info(
        "Published fixture document: bucket=%s key=%s fixtures=%d bytes=%d schema_version=%d",
        bucket_name, object_key, len(fixtures), len(body), SCHEMA_VERSION,
    )
    return {
        "ok": True,
        "published": True,
        "fixtureCount": len(fixtures),
        "schemaVersion": SCHEMA_VERSION,
        "range": document["range"],
    }


def _validate_document(document: dict[str, Any]) -> None:
    try:
        validate_fixture_document(
            document,
            competition_ids={competition.app_id for competition in COMPETITIONS},
        )
    except FixtureDocumentValidationError as exc:
        LOGGER.error("Fixture document validation failed: %s", exc)
        raise FixtureDataError(f"Fixture document validation failed: {exc}") from exc
    LOGGER.info(
        "Validated fixture document: schema_version=%d fixtures=%d",
        document["schemaVersion"], len(document["fixtures"]),
    )


def _fetch_competition_fixtures(
    *, api_key: str, competition: Competition, season: int, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    if competition.app_id == "laliga":
        return _fetch_laliga_v2_competition_fixtures(
            api_key=api_key,
            competition=competition,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
    if competition.app_id == "bundesliga":
        return _fetch_v2_fixture_pages(
            api_key=api_key,
            competition=competition,
            league_id=V2_LEAGUE_IDS[competition.app_id],
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
    return _fetch_v1_competition_fixtures(
        api_key=api_key,
        competition=competition,
        season=season,
        from_date=from_date,
        to_date=to_date,
    )


def _fetch_v1_competition_fixtures(
    *, api_key: str, competition: Competition, season: int, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    page = 1
    while True:
        params: dict[str, Any] = {
            "league": competition.api_league_id,
            "season": season,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        if page > 1:
            params["page"] = page
        payload = _get_api_json("/api/v1/fixtures", api_key=api_key, params=params)
        response_items = payload.get("response")
        if not isinstance(response_items, list):
            raise FixtureDataError(
                f"KickoffAPI v1 response is missing a response list for {competition.app_id}"
            )
        diagnostics = [_raw_fixture_diagnostic(item) for item in response_items]
        LOGGER.info(
            "Raw KickoffAPI v1 fixtures: app_id=%s page=%d items=%s",
            competition.app_id,
            page,
            json.dumps(diagnostics, ensure_ascii=False, separators=(",", ":")),
        )
        fixtures.extend(response_items)
        paging = payload.get("paging")
        if not isinstance(paging, dict):
            return fixtures
        try:
            current_page = int(paging.get("current", page))
            total_pages = int(paging.get("total", current_page))
        except (TypeError, ValueError) as exc:
            raise FixtureDataError(
                f"Invalid KickoffAPI v1 paging data for {competition.app_id}"
            ) from exc
        if current_page >= total_pages:
            return fixtures
        page = current_page + 1


def _fetch_v2_fixture_pages(
    *,
    api_key: str,
    competition: Competition,
    league_id: str,
    season: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    while True:
        params: dict[str, Any] = {
            "league": league_id,
            "season": season,
        }
        if from_date is not None:
            params["from"] = from_date.isoformat()
        if to_date is not None:
            params["to"] = to_date.isoformat()
        if cursor is not None:
            params["cursor"] = cursor

        payload = _get_api_json("/api/v2/fixtures", api_key=api_key, params=params)
        data = payload.get("data")
        if not isinstance(data, list):
            raise FixtureDataError(
                f"KickoffAPI v2 response is missing a data list for {competition.app_id}"
            )
        fixtures.extend(data)

        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise FixtureDataError(f"KickoffAPI v2 response is missing meta for {competition.app_id}")
        next_cursor = meta.get("nextCursor")
        LOGGER.info(
            "Raw KickoffAPI v2 fixtures: app_id=%s cursor=%s count=%d next_cursor=%s",
            competition.app_id,
            cursor,
            len(data),
            next_cursor,
        )
        if next_cursor in (None, ""):
            return fixtures

        next_cursor_string = str(next_cursor)
        if next_cursor_string in seen_cursors:
            raise FixtureDataError(
                f"KickoffAPI v2 cursor repeated for {competition.app_id}: {next_cursor_string}"
            )
        seen_cursors.add(next_cursor_string)
        cursor = next_cursor_string


def _fetch_laliga_v2_competition_fixtures(
    *, api_key: str, competition: Competition, season: int, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    fixtures = _fetch_v2_fixture_pages(
        api_key=api_key,
        competition=competition,
        league_id=V2_LEAGUE_IDS[competition.app_id],
        season=season,
    )

    try:
        selected = select_canonical_fixtures(
            fixtures,
            from_date=from_date,
            to_date=to_date,
        )
    except LaLigaV2SelectionError as exc:
        raise FixtureDataError(f"La Liga v2 canonical fixture selection failed: {exc}") from exc

    LOGGER.info(
        "Selected canonical La Liga v2 fixtures: season=%d fetched=%d selected=%d",
        season,
        len(fixtures),
        len(selected),
    )
    return selected


def _raw_fixture_diagnostic(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"type": type(raw).__name__}
    fixture = raw.get("fixture")
    if isinstance(fixture, dict):
        fixture_id = fixture.get("id")
        kickoff = fixture.get("date")
        status = fixture.get("status")
    else:
        fixture_id = raw.get("id")
        kickoff = raw.get("date")
        status = raw.get("status") or raw.get("statusShort")
    home, away = _raw_teams(raw)
    return {
        "id": fixture_id,
        "date": kickoff,
        "status": status,
        "home": _raw_team_diagnostic(home),
        "away": _raw_team_diagnostic(away),
    }


def _raw_team_diagnostic(team: Any) -> Any:
    if not isinstance(team, dict):
        return team
    return {"id": team.get("id"), "name": team.get("name")}


def _raw_teams(raw: dict[str, Any]) -> tuple[Any, Any]:
    teams = raw.get("teams")
    if isinstance(teams, dict):
        return teams.get("home"), teams.get("away")
    return raw.get("homeTeam") or raw.get("home"), raw.get("awayTeam") or raw.get("away")


def _get_api_json(path: str, *, api_key: str, params: dict[str, Any]) -> dict[str, Any]:
    response = _http.get(
        f"{API_BASE_URL}{path}",
        headers={"x-api-key": api_key},
        params=params,
        timeout=(3.05, 30),
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
    for key in TEAM_LOGO_KEYS:
        value = team.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalized_team(
    raw_team: dict[str, Any], *, team_name: str, team_id: str, competition_id: str
) -> dict[str, str]:
    team = {"id": team_id, "name": team_name}
    logo = get_static_team_logo(competition_id, team_name) if competition_id == "bundesliga" else None
    if logo is None:
        logo = _normalize_team_logo(raw_team)
    if logo is not None:
        team["logo"] = logo
    return team


def _normalize_fixture(
    raw: dict[str, Any], competition: Competition, *, team_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    try:
        fixture = raw.get("fixture")
        if isinstance(fixture, dict):
            fixture_id = fixture["id"]
            kickoff = fixture["date"]
            raw_status = fixture.get("status")
        else:
            fixture_id = raw["id"]
            kickoff = raw["date"]
            raw_status = raw.get("status") or raw.get("statusShort")
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
    provider_score = raw.get("score")
    if isinstance(goals, dict):
        home_goals, away_goals = goals.get("home"), goals.get("away")
    elif isinstance(provider_score, dict):
        home_goals, away_goals = provider_score.get("home"), provider_score.get("away")
    else:
        home_goals, away_goals = raw.get("homeScore"), raw.get("awayScore")
        if home_goals is None:
            home_goals = home.get("goals")
        if away_goals is None:
            away_goals = away.get("goals")
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
    raise FixtureDataError(f"Unknown KickoffAPI fixture status: {status_value}")


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
    return _parse_datetime(value).astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
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
