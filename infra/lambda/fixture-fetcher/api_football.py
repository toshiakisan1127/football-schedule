from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

LOGGER = logging.getLogger()
API_BASE_URL = "https://v3.football.api-sports.io"
J1_LEAGUE_ID = 98

_http = requests.Session()
_http.headers.update({"User-Agent": "football-schedule-fixture-fetcher/1.0"})


class ApiFootballError(RuntimeError):
    pass


def j1_season_for(reference_date: date) -> int:
    """API-Football identifies the current autumn-spring J1 season by its ending year."""
    return reference_date.year + 1 if reference_date.month >= 7 else reference_date.year


def fetch_j1_fixtures(
    *,
    api_key: str,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    page = 1
    season = j1_season_for(from_date)

    while True:
        payload = _get_json(
            "/fixtures",
            api_key=api_key,
            params={
                "league": J1_LEAGUE_ID,
                "season": season,
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "page": page,
            },
        )
        response_items = payload.get("response")
        if not isinstance(response_items, list):
            raise ApiFootballError("API-Football response is missing a response list for J1")
        fixtures.extend(response_items)

        paging = payload.get("paging")
        if not isinstance(paging, dict):
            raise ApiFootballError("API-Football response is missing paging data for J1")
        try:
            current_page = int(paging.get("current", page))
            total_pages = int(paging.get("total", current_page))
        except (TypeError, ValueError) as exc:
            raise ApiFootballError("API-Football returned invalid paging data for J1") from exc

        LOGGER.info(
            "Raw API-Football J1 fixtures: season=%d page=%d count=%d total_pages=%d",
            season,
            current_page,
            len(response_items),
            total_pages,
        )
        if current_page >= total_pages:
            return fixtures
        page = current_page + 1


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
