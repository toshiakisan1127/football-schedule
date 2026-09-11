from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BERLIN = ZoneInfo("Europe/Berlin")
LOGGER = logging.getLogger(__name__)


class BundesligaV2SelectionError(RuntimeError):
    pass


def select_canonical_fixtures(
    raw_fixtures: list[dict[str, Any]], *, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    """Select one trustworthy KickoffAPI v2 record per Bundesliga match.

    KickoffAPI v2 can expose a canonical UTC record together with a sibling
    whose Berlin wall-clock time is stored as though it were UTC. Single-record
    groups are preserved. Duplicate groups are only collapsed when exactly one
    candidate is verified by that Berlin wall-clock relationship.
    """

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in raw_fixtures:
        groups[_group_key(raw)].append(raw)

    selected: list[dict[str, Any]] = []
    for key, candidates in groups.items():
        relevant = [
            candidate
            for candidate in candidates
            if _candidate_in_window(candidate, from_date=from_date, to_date=to_date)
        ]
        if not relevant:
            continue
        if len(relevant) == 1:
            selected.append(relevant[0])
            continue

        matches = [
            candidate
            for candidate in relevant
            if candidate.get("time") is None
            and _has_berlin_wall_clock_sibling(candidate, relevant)
        ]
        if len(matches) == 1:
            selected.append(matches[0])
            continue
        if len(matches) > 1:
            raise BundesligaV2SelectionError(
                "Could not select exactly one canonical Bundesliga v2 fixture "
                f"for home={key[0]!r} away={key[1]!r} round={key[2]!r}: "
                f"selected={len(matches)} candidates={_diagnostics(relevant)!r}"
            )

        LOGGER.warning(
            "Skipping unresolved Bundesliga v2 duplicate fixture: "
            "home=%r away=%r round=%r candidates=%r",
            key[0],
            key[1],
            key[2],
            _diagnostics(relevant),
        )

    return selected


def _group_key(raw: dict[str, Any]) -> tuple[str, str, str]:
    home = raw.get("home")
    away = raw.get("away")
    round_name = raw.get("round")
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture is missing teams: {raw!r}")
    home_name = home.get("name")
    away_name = away.get("name")
    if not isinstance(home_name, str) or not home_name:
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture has invalid home team: {raw!r}")
    if not isinstance(away_name, str) or not away_name:
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture has invalid away team: {raw!r}")
    if not isinstance(round_name, str) or not round_name:
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture has invalid round: {raw!r}")
    return home_name, away_name, round_name


def _candidate_in_window(
    candidate: dict[str, Any], *, from_date: date, to_date: date
) -> bool:
    kickoff = candidate.get("date")
    if not isinstance(kickoff, str):
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture has invalid date: {candidate!r}")
    fixture_date_jst = _parse_datetime(kickoff).astimezone(JST).date()
    return from_date <= fixture_date_jst <= to_date


def _has_berlin_wall_clock_sibling(
    candidate: dict[str, Any], candidates: list[dict[str, Any]]
) -> bool:
    kickoff = candidate.get("date")
    if not isinstance(kickoff, str):
        raise BundesligaV2SelectionError(f"Bundesliga v2 fixture has invalid date: {candidate!r}")

    berlin = _parse_datetime(kickoff).astimezone(BERLIN)
    expected_date = berlin.strftime("%Y-%m-%d")
    expected_time = berlin.strftime("%H:%M")

    for other in candidates:
        if other is candidate:
            continue
        if other.get("time") != expected_time:
            continue
        other_date = other.get("date")
        if not isinstance(other_date, str):
            continue
        other_utc = _parse_datetime(other_date).astimezone(timezone.utc)
        if other_utc.strftime("%Y-%m-%d") != expected_date:
            continue
        if other_utc.strftime("%H:%M") != expected_time:
            continue
        return True

    return False


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BundesligaV2SelectionError(f"Invalid Bundesliga v2 datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        raise BundesligaV2SelectionError(f"Bundesliga v2 datetime has no timezone: {value!r}")
    return parsed


def _diagnostics(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": candidate.get("id"),
            "date": candidate.get("date"),
            "time": candidate.get("time"),
        }
        for candidate in candidates
    ]
