from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
VALID_STATUSES = {"scheduled", "live", "finished", "postponed", "cancelled"}
JST = ZoneInfo("Asia/Tokyo")


class FixtureDocumentValidationError(RuntimeError):
    pass


def validate_fixture_document(
    document: dict[str, Any],
    *,
    competition_ids: set[str],
) -> None:
    if not isinstance(document, dict):
        raise FixtureDocumentValidationError("document must be an object")

    if document.get("schemaVersion") != SCHEMA_VERSION:
        raise FixtureDocumentValidationError(
            f"schemaVersion must be {SCHEMA_VERSION}"
        )

    generated_at = _required_string(document, "generatedAt", "document")
    generated_at_dt = _parse_datetime(generated_at, "generatedAt")
    if generated_at_dt.utcoffset() is None or not generated_at.endswith("Z"):
        raise FixtureDocumentValidationError("generatedAt must be a UTC ISO-8601 timestamp")

    range_value = document.get("range")
    if not isinstance(range_value, dict):
        raise FixtureDocumentValidationError("range must be an object")

    from_date = _parse_date(_required_string(range_value, "from", "range"), "range.from")
    to_date = _parse_date(_required_string(range_value, "to", "range"), "range.to")
    if from_date > to_date:
        raise FixtureDocumentValidationError("range.from must not be after range.to")

    fixtures = document.get("fixtures")
    if not isinstance(fixtures, list):
        raise FixtureDocumentValidationError("fixtures must be an array")

    fixture_ids: set[str] = set()
    team_names_by_id: dict[str, str] = {}
    competition_metadata: dict[str, tuple[str, str]] = {}
    sort_keys: list[tuple[str, str]] = []

    for index, fixture in enumerate(fixtures):
        path = f"fixtures[{index}]"
        if not isinstance(fixture, dict):
            raise FixtureDocumentValidationError(f"{path} must be an object")

        fixture_id = _required_string(fixture, "id", path)
        if fixture_id in fixture_ids:
            raise FixtureDocumentValidationError(f"duplicate fixture id: {fixture_id}")
        fixture_ids.add(fixture_id)

        competition = fixture.get("competition")
        if not isinstance(competition, dict):
            raise FixtureDocumentValidationError(f"{path}.competition must be an object")
        competition_id = _required_string(competition, "id", f"{path}.competition")
        competition_name = _required_string(competition, "name", f"{path}.competition")
        competition_country = _required_string(competition, "country", f"{path}.competition")
        if competition_id not in competition_ids:
            raise FixtureDocumentValidationError(
                f"{path}.competition.id is not configured: {competition_id}"
            )
        metadata = (competition_name, competition_country)
        previous_metadata = competition_metadata.setdefault(competition_id, metadata)
        if previous_metadata != metadata:
            raise FixtureDocumentValidationError(
                f"competition metadata changed within document: {competition_id}"
            )

        home_id, home_name = _validate_team(fixture.get("home"), f"{path}.home")
        away_id, away_name = _validate_team(fixture.get("away"), f"{path}.away")
        if home_id == away_id or home_name == away_name:
            raise FixtureDocumentValidationError(
                f"{path} has the same home and away team"
            )

        _remember_team(team_names_by_id, home_id, home_name, f"{path}.home")
        _remember_team(team_names_by_id, away_id, away_name, f"{path}.away")

        kickoff = _required_string(fixture, "kickoff", path)
        kickoff_dt = _parse_datetime(kickoff, f"{path}.kickoff")
        if kickoff_dt.utcoffset() is None or not kickoff.endswith("Z"):
            raise FixtureDocumentValidationError(
                f"{path}.kickoff must be a UTC ISO-8601 timestamp"
            )
        kickoff_date_jst = kickoff_dt.astimezone(JST).date()
        if not from_date <= kickoff_date_jst <= to_date:
            raise FixtureDocumentValidationError(
                f"{path}.kickoff is outside the document range"
            )

        status = _required_string(fixture, "status", path)
        if status not in VALID_STATUSES:
            raise FixtureDocumentValidationError(
                f"{path}.status is invalid: {status}"
            )

        _validate_score(fixture.get("score"), f"{path}.score")
        sort_keys.append((kickoff, fixture_id))

    if sort_keys != sorted(sort_keys):
        raise FixtureDocumentValidationError("fixtures must be sorted by kickoff and id")


def _required_string(value: dict[str, Any], key: str, path: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise FixtureDocumentValidationError(f"{path}.{key} must be a non-empty string")
    return item


def _parse_date(value: str, path: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FixtureDocumentValidationError(f"{path} must be an ISO date") from exc


def _parse_datetime(value: str, path: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FixtureDocumentValidationError(
            f"{path} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise FixtureDocumentValidationError(f"{path} must include a timezone")
    return parsed


def _validate_team(value: Any, path: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise FixtureDocumentValidationError(f"{path} must be an object")
    return (
        _required_string(value, "id", path),
        _required_string(value, "name", path),
    )


def _remember_team(
    team_names_by_id: dict[str, str],
    team_id: str,
    team_name: str,
    path: str,
) -> None:
    previous_name = team_names_by_id.setdefault(team_id, team_name)
    if previous_name != team_name:
        raise FixtureDocumentValidationError(
            f"{path}.id maps to multiple team names: {team_id}"
        )


def _validate_score(value: Any, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise FixtureDocumentValidationError(f"{path} must be null or an object")
    if set(value) != {"home", "away"}:
        raise FixtureDocumentValidationError(
            f"{path} must contain exactly home and away"
        )
    for side in ("home", "away"):
        score = value[side]
        if isinstance(score, bool) or not isinstance(score, int) or score < 0:
            raise FixtureDocumentValidationError(
                f"{path}.{side} must be a non-negative integer"
            )
