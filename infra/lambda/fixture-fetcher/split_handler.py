from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

from api_football import fetch_j1_fixtures, fetch_premier_league_fixtures
import handler as legacy
from ligue1_v2 import (
    Ligue1V2SelectionError,
    select_canonical_fixtures as select_ligue1_canonical_fixtures,
)
from validation import SCHEMA_VERSION, FixtureDocumentValidationError, validate_fixture_document

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

LIGUE1_COMPETITION = legacy.Competition("ligue1", 61, "Ligue 1", "France")
J1_COMPETITION = legacy.Competition("j1", 98, "J1 League", "Japan")
COMPETITIONS = (*legacy.COMPETITIONS, LIGUE1_COMPETITION, J1_COMPETITION)
LIGUE1_V2_LEAGUE_ID = "fr.1"
API_FOOTBALL_COMPETITION_IDS = {"epl", "j1"}

OBJECT_FILENAMES = {
    "epl": "premier-league.json",
    "laliga": "laliga.json",
    "bundesliga": "bundesliga.json",
    "ligue1": "ligue1.json",
    "j1": "j1.json",
}


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    bucket_name = legacy._required_env("DATA_BUCKET_NAME")
    object_prefix = os.getenv("FIXTURE_OBJECT_PREFIX", "data/fixtures").strip("/")
    lookback_days = legacy._non_negative_int_env("LOOKBACK_DAYS", 1)
    lookahead_days = legacy._non_negative_int_env("LOOKAHEAD_DAYS", 14)
    competitions = _selected_competitions(event)

    today_jst = datetime.now(legacy.JST).date()
    from_date = today_jst - timedelta(days=lookback_days)
    to_date = today_jst + timedelta(days=lookahead_days)
    season = legacy._season_for(today_jst)

    LOGGER.info(
        "Starting split fixture refresh: from=%s to=%s season=%d competitions=%s",
        from_date,
        to_date,
        season,
        ",".join(competition.app_id for competition in competitions),
    )

    kickoff_api_key = _load_kickoff_api_key(competitions)
    api_football_api_key = _load_api_football_key(competitions)
    published: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for competition in competitions:
        provider = _provider_name(competition)
        api_key = (
            api_football_api_key
            if competition.app_id in API_FOOTBALL_COMPETITION_IDS
            else kickoff_api_key
        )
        if api_key is None:
            raise legacy.FixtureDataError(f"No API key loaded for provider {provider}")

        try:
            document = _build_competition_document(
                api_key=api_key,
                competition=competition,
                season=season,
                from_date=from_date,
                to_date=to_date,
            )
            object_key = _object_key(object_prefix, competition.app_id)
            body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            legacy._publish_document(bucket_name=bucket_name, object_key=object_key, body=body)
            published.append(
                {
                    "competition": competition.app_id,
                    "objectKey": object_key,
                    "fixtureCount": len(document["fixtures"]),
                }
            )
            LOGGER.info(
                "Published competition fixture document: app_id=%s provider=%s bucket=%s key=%s fixtures=%d bytes=%d",
                competition.app_id,
                provider,
                bucket_name,
                object_key,
                len(document["fixtures"]),
                len(body),
            )
        except Exception as exc:
            LOGGER.warning(
                "Competition refresh failed: app_id=%s provider=%s error_type=%s error=%s",
                competition.app_id,
                provider,
                type(exc).__name__,
                exc,
            )
            failures.append(_failure_detail(competition.app_id, provider, exc))

    if failures:
        alert = {
            "level": "ERROR",
            "message": "Fixture refresh completed with failures",
            "requestId": getattr(context, "aws_request_id", None),
            "provider": _summary_provider(failures),
            "failureCount": len(failures),
            "failedCompetitions": [failure["competition"] for failure in failures],
            "primaryCause": _primary_cause(failures),
            "failures": failures,
        }
        LOGGER.error(json.dumps(alert, ensure_ascii=False, separators=(",", ":")))
        summary = ", ".join(
            f"{failure['competition']}: {failure['errorMessage']}" for failure in failures
        )
        raise legacy.FixtureDataError(f"One or more competition refreshes failed: {summary}")

    return {
        "ok": True,
        "published": True,
        "schemaVersion": SCHEMA_VERSION,
        "range": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "fixtureCount": sum(item["fixtureCount"] for item in published),
        "competitions": published,
    }


def _selected_competitions(event: dict[str, Any] | None) -> tuple[legacy.Competition, ...]:
    if not isinstance(event, dict) or "competitions" not in event:
        return COMPETITIONS

    raw = event.get("competitions")
    if not isinstance(raw, list) or not raw:
        raise legacy.FixtureDataError("competitions must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise legacy.FixtureDataError("competitions must contain non-empty competition IDs")

    configured = {competition.app_id: competition for competition in COMPETITIONS}
    selected: list[legacy.Competition] = []
    seen: set[str] = set()

    for raw_id in raw:
        competition_id = raw_id.strip()
        if competition_id in seen:
            continue
        competition = configured.get(competition_id)
        if competition is None:
            raise legacy.FixtureDataError(f"Unknown competition ID: {competition_id}")
        seen.add(competition_id)
        selected.append(competition)

    return tuple(selected)


def _load_kickoff_api_key(competitions: tuple[legacy.Competition, ...]) -> str | None:
    if not any(
        competition.app_id not in API_FOOTBALL_COMPETITION_IDS
        for competition in competitions
    ):
        return None
    parameter_name = legacy._required_env("API_KEY_PARAMETER_NAME")
    return legacy._load_api_key(parameter_name)


def _load_api_football_key(competitions: tuple[legacy.Competition, ...]) -> str | None:
    if not any(
        competition.app_id in API_FOOTBALL_COMPETITION_IDS
        for competition in competitions
    ):
        return None
    parameter_name = legacy._required_env("API_FOOTBALL_KEY_PARAMETER_NAME")
    return legacy._load_api_key(parameter_name)


def _provider_name(competition: legacy.Competition) -> str:
    return (
        "API-Football"
        if competition.app_id in API_FOOTBALL_COMPETITION_IDS
        else "KickoffAPI"
    )


def _fetch_competition_fixtures(
    *,
    api_key: str,
    competition: legacy.Competition,
    season: int,
    from_date: Any,
    to_date: Any,
) -> list[dict[str, Any]]:
    if competition.app_id == "epl":
        fixtures = fetch_premier_league_fixtures(
            api_key=api_key,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
        LOGGER.info(
            "Fetched API-Football Premier League fixtures: season=%d fetched=%d",
            season,
            len(fixtures),
        )
        return fixtures

    if competition.app_id == "j1":
        fixtures = fetch_j1_fixtures(
            api_key=api_key,
            from_date=from_date,
            to_date=to_date,
        )
        LOGGER.info(
            "Fetched API-Football J1 fixtures: fetched=%d",
            len(fixtures),
        )
        return fixtures

    if competition.app_id == "ligue1":
        fixtures = legacy._fetch_v2_fixture_pages(
            api_key=api_key,
            competition=competition,
            league_id=LIGUE1_V2_LEAGUE_ID,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )
        try:
            selected = select_ligue1_canonical_fixtures(
                fixtures,
                from_date=from_date,
                to_date=to_date,
            )
        except Ligue1V2SelectionError as exc:
            raise legacy.FixtureDataError(
                f"Ligue 1 v2 canonical fixture selection failed: {exc}"
            ) from exc
        LOGGER.info(
            "Selected canonical Ligue 1 v2 fixtures: season=%d fetched=%d selected=%d",
            season,
            len(fixtures),
            len(selected),
        )
        return selected

    return legacy._fetch_competition_fixtures(
        api_key=api_key,
        competition=competition,
        season=season,
        from_date=from_date,
        to_date=to_date,
    )


def _normalize_provider_fixture(
    item: dict[str, Any],
    competition: legacy.Competition,
    *,
    team_ids: dict[str, str],
) -> dict[str, Any]:
    fixture = legacy._normalize_fixture(item, competition, team_ids=team_ids)
    if competition.app_id not in API_FOOTBALL_COMPETITION_IDS:
        return fixture

    raw_home, raw_away = legacy._raw_teams(item)
    for side, raw_team in (("home", raw_home), ("away", raw_away)):
        if not isinstance(raw_team, dict):
            continue
        provider_logo = legacy._normalize_team_logo(raw_team)
        if provider_logo is not None:
            fixture[side]["logo"] = provider_logo

    return fixture


def _build_competition_document(
    *,
    api_key: str,
    competition: legacy.Competition,
    season: int,
    from_date: Any,
    to_date: Any,
) -> dict[str, Any]:
    raw_fixtures = _fetch_competition_fixtures(
        api_key=api_key,
        competition=competition,
        season=season,
        from_date=from_date,
        to_date=to_date,
    )
    team_ids = legacy._collect_team_ids(raw_fixtures)
    fixtures = [
        fixture
        for item in raw_fixtures
        if legacy._fixture_in_window(
            fixture := _normalize_provider_fixture(item, competition, team_ids=team_ids),
            from_date=from_date,
            to_date=to_date,
        )
    ]
    fixtures.sort(key=lambda fixture: (fixture["kickoff"], fixture["id"]))

    document = {
        "schemaVersion": SCHEMA_VERSION,
        "competition": {
            "id": competition.app_id,
            "name": competition.name,
            "country": competition.country,
        },
        "generatedAt": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "range": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "fixtures": fixtures,
    }
    _validate_competition_document(document, competition)
    return document


def _validate_competition_document(
    document: dict[str, Any], competition: legacy.Competition
) -> None:
    root_competition = document.get("competition")
    expected = {
        "id": competition.app_id,
        "name": competition.name,
        "country": competition.country,
    }
    if root_competition != expected:
        raise legacy.FixtureDataError(
            f"Competition document metadata is invalid for {competition.app_id}"
        )

    try:
        validate_fixture_document(document, competition_ids={competition.app_id})
    except FixtureDocumentValidationError as exc:
        raise legacy.FixtureDataError(
            f"Fixture document validation failed for {competition.app_id}: {exc}"
        ) from exc


def _object_key(prefix: str, competition_id: str) -> str:
    filename = OBJECT_FILENAMES.get(competition_id)
    if filename is None:
        raise legacy.FixtureDataError(f"No fixture object filename configured: {competition_id}")
    return f"{prefix}/{filename}" if prefix else filename


def _failure_detail(competition_id: str, provider: str, exc: Exception) -> dict[str, Any]:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return {
        "competition": competition_id,
        "provider": provider,
        "errorType": type(exc).__name__,
        "errorMessage": str(exc),
        "statusCode": status_code,
        "stackTrace": traceback.format_exception(type(exc), exc, exc.__traceback__),
    }


def _summary_provider(failures: list[dict[str, Any]]) -> str:
    providers = {str(failure.get("provider", "Unknown")) for failure in failures}
    return next(iter(providers)) if len(providers) == 1 else "mixed"


def _primary_cause(failures: list[dict[str, Any]]) -> str:
    status_codes = {failure.get("statusCode") for failure in failures}
    provider = _summary_provider(failures)
    provider_label = provider if provider != "mixed" else "Provider"
    if status_codes == {429}:
        return f"{provider_label} rate limit exceeded (HTTP 429)"
    if len(status_codes) == 1:
        status_code = next(iter(status_codes))
        if status_code is not None:
            return f"{provider_label} request failed (HTTP {status_code})"

    error_types = {str(failure.get("errorType", "UnknownError")) for failure in failures}
    if len(error_types) == 1:
        return next(iter(error_types))
    return "Multiple errors"
