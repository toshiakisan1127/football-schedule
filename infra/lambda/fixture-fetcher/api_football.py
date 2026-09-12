from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable

import requests

LOGGER = logging.getLogger()
API_BASE_URL = "https://v3.football.api-sports.io"
PREMIER_LEAGUE_ID = 39
J1_LEAGUE_ID = 98

_http = requests.Session()
_http.headers.update({"User-Agent": "football-schedule-fixture-fetcher/1.0"})


class ApiFootballError(RuntimeError):
    pass


def j1_season_for(reference_date: date) -> int:
    """API-Football identifies the current autumn-spring J1 season by its ending year."""
    return reference_date.year + 1 if reference_date.month >= 7 else reference_date.year


def fetch_fixtures(
    *,
    api_key: str,
    league_id: int,
    season: int,
    from_date: date,
    to_date: date,
    competition_label: str,
) -> list[dict[str, Any]]:
    payload = _get_json(
        "/fixtures",
        api_key=api_key,
        params={
            "league": league_id,
            "season": season,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
    )
    response_items = payload.get("response")
    if not isinstance(response_items, list):
        raise ApiFootballError(
            f"API-Football response is missing a response list for {competition_label}"
        )

    LOGGER.info(
        "Raw API-Football fixtures: competition=%s league=%d season=%d count=%d",
        competition_label,
        league_id,
        season,
        len(response_items),
    )
    return response_items


def fetch_live_fixtures(
    *,
    api_key: str,
    league_ids: Iterable[int],
) -> list[dict[str, Any]]:
    normalized_ids = tuple(dict.fromkeys(int(league_id) for league_id in league_ids))
    if not normalized_ids:
        raise ApiFootballError("At least one league ID is required for live fixtures")

    payload = _get_json(
        "/fixtures",
        api_key=api_key,
        params={
            "live": "-".join(str(league_id) for league_id in normalized_ids),
            "timezone": "Asia/Tokyo",
        },
    )
    response_items = payload.get("response")
    if not isinstance(response_items, list):
        raise ApiFootballError(
            "API-Football live response is missing a response list"
        )

    LOGGER.info(
        "Raw API-Football live fixtures: leagues=%s count=%d",
        "-".join(str(league_id) for league_id in normalized_ids),
        len(response_items),
    )
    return response_items


def fetch_premier_league_fixtures(
    *,
    api_key: str,
    season: int,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    return fetch_fixtures(
        api_key=api_key,
        league_id=PREMIER_LEAGUE_ID,
        season=season,
        from_date=from_date,
        to_date=to_date,
        competition_label="Premier League",
    )


def fetch_j1_fixtures(
    *,
    api_key: str,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    return fetch_fixtures(
        api_key=api_key,
        league_id=J1_LEAGUE_ID,
        season=j1_season_for(from_date),
        from_date=from_date,
        to_date=to_date,
        competition_label="J1",
    )


def _get_json(path: str, *, api_key: str, params: dict[str, Any]) -> dict[str, Any]:
    response = _http.get(
        f"{API_BASE_URL}{path}",
        headers={"x-apisports-key": api_key},
        params=params,
        timeout=(3.05, 30),
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise ApiFootballError("API-Football returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ApiFootballError("API-Football returned a non-object JSON payload")
    errors = payload.get("errors")
    if errors:
        raise ApiFootballError(f"API-Football returned errors: {errors!r}")
    return payload
