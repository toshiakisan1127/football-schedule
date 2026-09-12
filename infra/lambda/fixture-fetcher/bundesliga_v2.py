from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BERLIN = ZoneInfo("Europe/Berlin")
LOGGER = logging.getLogger(__name__)

_MIN_ROUND_PLACEHOLDER_MATCHES = 3


class BundesligaV2SelectionError(RuntimeError):
    pass


def select_canonical_fixtures(
    raw_fixtures: list[dict[str, Any]], *, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    """Select one trustworthy KickoffAPI v2 record per Bundesliga match.

    KickoffAPI v2 can expose a canonical UTC record together with a sibling
    whose Berlin wall-clock time is stored as though it were UTC. Those known
    duplicate pairs are collapsed first.

    The provider can also keep a round-wide provisional schedule after adding
    finalized kickoffs as new fixture records. That placeholder batch is only
    removed when every match in the observed round has exactly two records and
    exactly one timestamp contains one record for every match in that round.
    Ambiguous provider shapes are preserved rather than guessed.
    """

    relevant_fixtures = [
        raw
        for raw in raw_fixtures
        if _candidate_in_window(raw, from_date=from_date, to_date=to_date)
    ]

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in relevant_fixtures:
        groups[_group_key(raw)].append(raw)

    selected: list[dict[str, Any]] = []
    for key, relevant in groups.items():
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
            "Preserving unresolved Bundesliga v2 duplicate fixture: "
            "home=%r away=%r round=%r candidates=%r",
            key[0],
            key[1],
            key[2],
            _diagnostics(relevant),
        )
        selected.extend(relevant)

    return _drop_round_wide_placeholders(selected)


def _drop_round_wide_placeholders(
    fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fixtures_by_round: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fixture in fixtures:
        fixtures_by_round[_group_key(fixture)[2]].append(fixture)

    placeholder_object_ids: set[int] = set()

    for round_name, round_fixtures in fixtures_by_round.items():
        fixtures_by_match: dict[
            tuple[str, str, str], list[dict[str, Any]]
        ] = defaultdict(list)
        for fixture in round_fixtures:
            fixtures_by_match[_group_key(fixture)].append(fixture)

        match_count = len(fixtures_by_match)
        if match_count < _MIN_ROUND_PLACEHOLDER_MATCHES:
            continue
        if any(len(candidates) != 2 for candidates in fixtures_by_match.values()):
            continue

        fixtures_by_kickoff: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for fixture in round_fixtures:
            kickoff = fixture.get("date")
            if not isinstance(kickoff, str):
                raise BundesligaV2SelectionError(
                    f"Bundesliga v2 fixture has invalid date: {fixture!r}"
                )
            kickoff_utc = _parse_datetime(kickoff).astimezone(timezone.utc)
            fixtures_by_kickoff[kickoff_utc].append(fixture)

        all_match_keys = set(fixtures_by_match)
        candidates: list[tuple[datetime, list[dict[str, Any]]]] = []
        for kickoff, batch in fixtures_by_kickoff.items():
            if len(batch) != match_count:
                continue
            if not all(item.get("time") is None for item in batch):
                continue

            batch_match_keys = [_group_key(item) for item in batch]
            if len(set(batch_match_keys)) != match_count:
                continue
            if set(batch_match_keys) != all_match_keys:
                continue

            candidates.append((kickoff, batch))

        if len(candidates) == 1:
            kickoff, batch = candidates[0]
            LOGGER.warning(
                "Dropping Bundesliga v2 round-wide placeholder fixture batch: "
                "round=%r kickoff=%s matches=%d fixture_ids=%r",
                round_name,
                kickoff.isoformat(),
                len(batch),
                [item.get("id") for item in batch],
            )
            placeholder_object_ids.update(id(item) for item in batch)
        elif len(candidates) > 1:
            LOGGER.warning(
                "Preserving ambiguous Bundesliga v2 round-wide duplicate batches: "
                "round=%r candidates=%r",
                round_name,
                [
                    {
                        "kickoff": kickoff.isoformat(),
                        "fixture_ids": [item.get("id") for item in batch],
                    }
                    for kickoff, batch in candidates
                ],
            )

    return [fixture for fixture in fixtures if id(fixture) not in placeholder_object_ids]


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
