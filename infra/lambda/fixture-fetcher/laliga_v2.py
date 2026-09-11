from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from team_logos import get_static_team_logo

JST = ZoneInfo("Asia/Tokyo")
MADRID = ZoneInfo("Europe/Madrid")
LOGGER = logging.getLogger(__name__)
TEAM_ASSET_KEYS = ("logo", "image", "crest")


class LaLigaV2SelectionError(RuntimeError):
    pass


def select_canonical_fixtures(
    raw_fixtures: list[dict[str, Any]], *, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    """Select one trustworthy KickoffAPI v2 record per La Liga match.

    KickoffAPI v2 currently exposes multiple records for the same La Liga
    home/away/Matchday combination. The record whose ``time`` is null is the
    canonical UTC candidate when there is a sibling record that stores the
    Europe/Madrid wall-clock date/time as if it were UTC and exposes that
    wall-clock value in ``time``.

    Only groups that overlap the requested JST publication window are
    considered. A group with no verified canonical candidate is skipped so a
    provider-side partial update does not block publication of every other
    trustworthy fixture. A group with multiple verified candidates still fails
    closed because choosing between two independently verified times would be
    unsafe.
    """

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in raw_fixtures:
        groups[_group_key(raw)].append(raw)

    selected: list[dict[str, Any]] = []
    for key, candidates in groups.items():
        if not _group_overlaps_window(candidates, from_date=from_date, to_date=to_date):
            continue

        matches = [
            candidate
            for candidate in candidates
            if candidate.get("time") is None
            and _has_madrid_wall_clock_sibling(candidate, candidates)
        ]
        if len(matches) == 0:
            LOGGER.warning(
                "Skipping unresolved La Liga v2 fixture: home=%r away=%r round=%r candidates=%r",
                key[0],
                key[1],
                key[2],
                _diagnostics(candidates),
            )
            continue
        if len(matches) > 1:
            raise LaLigaV2SelectionError(
                "Could not select exactly one canonical La Liga v2 fixture "
                f"for home={key[0]!r} away={key[1]!r} round={key[2]!r}: "
                f"selected={len(matches)} candidates={_diagnostics(candidates)!r}"
            )

        selected.append(_backfill_team_metadata(matches[0], candidates))

    return selected


def _group_key(raw: dict[str, Any]) -> tuple[str, str, str]:
    home = raw.get("home")
    away = raw.get("away")
    round_name = raw.get("round")
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise LaLigaV2SelectionError(f"La Liga v2 fixture is missing teams: {raw!r}")
    home_name = home.get("name")
    away_name = away.get("name")
    if not isinstance(home_name, str) or not home_name:
        raise LaLigaV2SelectionError(f"La Liga v2 fixture has invalid home team: {raw!r}")
    if not isinstance(away_name, str) or not away_name:
        raise LaLigaV2SelectionError(f"La Liga v2 fixture has invalid away team: {raw!r}")
    if not isinstance(round_name, str) or not round_name:
        raise LaLigaV2SelectionError(f"La Liga v2 fixture has invalid round: {raw!r}")
    return home_name, away_name, round_name


def _group_overlaps_window(
    candidates: list[dict[str, Any]], *, from_date: date, to_date: date
) -> bool:
    for candidate in candidates:
        kickoff = candidate.get("date")
        if not isinstance(kickoff, str):
            raise LaLigaV2SelectionError(f"La Liga v2 fixture has invalid date: {candidate!r}")
        fixture_date_jst = _parse_datetime(kickoff).astimezone(JST).date()
        if from_date <= fixture_date_jst <= to_date:
            return True
    return False


def _has_madrid_wall_clock_sibling(
    candidate: dict[str, Any], candidates: list[dict[str, Any]]
) -> bool:
    kickoff = candidate.get("date")
    if not isinstance(kickoff, str):
        raise LaLigaV2SelectionError(f"La Liga v2 fixture has invalid date: {candidate!r}")

    madrid = _parse_datetime(kickoff).astimezone(MADRID)
    expected_date = madrid.strftime("%Y-%m-%d")
    expected_time = madrid.strftime("%H:%M")

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


def _backfill_team_metadata(
    selected: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Preserve team metadata, then use the static v1 logo snapshot as fallback."""

    result = dict(selected)
    for side in ("home", "away"):
        selected_team = selected.get(side)
        if not isinstance(selected_team, dict):
            continue

        team = dict(selected_team)
        matching_siblings = [
            sibling_team
            for candidate in candidates
            if isinstance((sibling_team := candidate.get(side)), dict)
            and sibling_team.get("name") == team.get("name")
        ]

        if team.get("id") in (None, ""):
            for sibling_team in matching_siblings:
                if sibling_team.get("id") not in (None, ""):
                    team["id"] = sibling_team["id"]
                    break

        if not _has_team_asset(team):
            for sibling_team in matching_siblings:
                copied = False
                for key in TEAM_ASSET_KEYS:
                    value = sibling_team.get(key)
                    if isinstance(value, str) and value.strip():
                        team[key] = value.strip()
                        copied = True
                        break
                if copied:
                    break

        if not _has_team_asset(team):
            team_name = team.get("name")
            if isinstance(team_name, str):
                static_logo = get_static_team_logo("laliga", team_name)
                if static_logo is not None:
                    team["logo"] = static_logo

        result[side] = team
    return result


def _has_team_asset(team: dict[str, Any]) -> bool:
    return any(
        isinstance(team.get(key), str) and team[key].strip()
        for key in TEAM_ASSET_KEYS
    )


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LaLigaV2SelectionError(f"Invalid La Liga v2 datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        raise LaLigaV2SelectionError(f"La Liga v2 datetime has no timezone: {value!r}")
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