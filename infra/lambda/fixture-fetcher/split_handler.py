from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import handler as legacy
from validation import SCHEMA_VERSION, FixtureDocumentValidationError, validate_fixture_document

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

LIGUE1_COMPETITION = legacy.Competition("ligue1", 61, "Ligue 1", "France")
UEL_COMPETITION = legacy.Competition("uel", 3, "UEFA Europa League", "Europe")
COMPETITIONS = (*legacy.COMPETITIONS, LIGUE1_COMPETITION, UEL_COMPETITION)
LIGUE1_V2_LEAGUE_ID = "fr.1"

OBJECT_FILENAMES = {
    "epl": "premier-league.json",
    "laliga": "laliga.json",
    "bundesliga": "bundesliga.json",
    "ligue1": "ligue1.json",
    "uel": "europa-league.json",
}


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    bucket_name = legacy._required_env("DATA_BUCKET_NAME")
    parameter_name = legacy._required_env("API_KEY_PARAMETER_NAME")
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

    api_key = legacy._load_api_key(parameter_name)
    published: list[dict[str, Any]] = []
    failures: list[tuple[str, Exception]] = []

    for competition in competitions:
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
                "Published competition fixture document: app_id=%s bucket=%s key=%s fixtures=%d bytes=%d",
                competition.app_id,
                bucket_name,
                object_key,
                len(document["fixtures"]),
                len(body),
            )
        except Exception as exc:
            LOGGER.exception("Competition refresh failed: app_id=%s", competition.app_id)
            failures.append((competition.app_id, exc))

    if failures:
        summary = ", ".join(f"{competition_id}: {error}" for competition_id, error in failures)
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


def _fetch_competition_fixtures(
    *,
    api_key: str,
    competition: legacy.Competition,
    season: int,
    from_date: Any,
    to_date: Any,
) -> list[dict[str, Any]]:
    if competition.app_id == "ligue1":
        return legacy._fetch_v2_fixture_pages(
            api_key=api_key,
            competition=competition,
            league_id=LIGUE1_V2_LEAGUE_ID,
            season=season,
            from_date=from_date,
            to_date=to_date,
        )

    return legacy._fetch_competition_fixtures(
        api_key=api_key,
        competition=competition,
        season=season,
        from_date=from_date,
        to_date=to_date,
    )


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
            fixture := legacy._normalize_fixture(item, competition, team_ids=team_ids),
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
