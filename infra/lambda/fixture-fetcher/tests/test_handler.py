from __future__ import annotations

from datetime import date

import pytest

import handler


def raw_fixture(
    *,
    fixture_id: int = 1001,
    kickoff: str = "2026-09-12T06:00:00.000Z",
    status: str | None = "NS",
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff,
            "status": None
            if status is None
            else {
                "long": "Not Started" if status == "NS" else "Match Finished",
                "short": status,
                "elapsed": None,
            },
        },
        "league": {
            "id": 39,
            "name": "Premier League",
            "season": 2026,
        },
        "teams": {
            "home": {"id": 40, "name": "Home FC"},
            "away": {"id": 33, "name": "Away FC"},
        },
        "goals": {
            "home": home_goals,
            "away": away_goals,
        },
    }


def competition() -> handler.Competition:
    return handler.COMPETITIONS[0]


def test_supported_competitions_and_api_football_ids() -> None:
    assert [
        (item.app_id, item.api_league_id, item.name, item.country)
        for item in handler.COMPETITIONS
    ] == [
        ("epl", 39, "Premier League", "England"),
        ("laliga", 140, "La Liga", "Spain"),
        ("bundesliga", 78, "Bundesliga", "Germany"),
    ]


@pytest.mark.parametrize(
    ("api_status", "expected"),
    [
        ("NS", "scheduled"),
        ("scheduled", "scheduled"),
        ("1H", "live"),
        ("live", "live"),
        ("FT", "finished"),
        ("finished", "finished"),
        ("PST", "postponed"),
        ("postponed", "postponed"),
        ("CANC", "cancelled"),
        ("cancelled", "cancelled"),
    ],
)
def test_normalize_status(api_status: str, expected: str) -> None:
    assert handler._normalize_status(api_status) == expected


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(handler.FixtureDataError, match="Unknown fixture status"):
        handler._normalize_status("SOMETHING_NEW")


def test_normalize_fixture_uses_api_football_shape() -> None:
    normalized = handler._normalize_fixture(raw_fixture(), competition())

    assert normalized == {
        "id": "1001",
        "competition": {
            "id": "epl",
            "name": "Premier League",
            "country": "England",
        },
        "home": {"id": "40", "name": "Home FC"},
        "away": {"id": "33", "name": "Away FC"},
        "kickoff": "2026-09-12T06:00:00Z",
        "status": "scheduled",
        "score": None,
    }


def test_live_score_is_preserved() -> None:
    normalized = handler._normalize_fixture(
        raw_fixture(status="2H", home_goals=2, away_goals=1),
        competition(),
    )

    assert normalized["status"] == "live"
    assert normalized["score"] == {"home": 2, "away": 1}


def test_flat_legacy_fixture_shape_is_rejected() -> None:
    with pytest.raises(handler.FixtureDataError, match="Malformed fixture payload"):
        handler._normalize_fixture(
            {
                "id": "legacy-fixture",
                "date": "2026-09-12T06:00:00Z",
                "status": "scheduled",
                "home": {"id": "home", "name": "Home FC"},
                "away": {"id": "away", "name": "Away FC"},
            },
            competition(),
        )


@pytest.mark.parametrize(
    ("kickoff", "expected"),
    [
        ("2026-09-09T14:59:59Z", False),
        ("2026-09-09T15:00:00Z", True),
        ("2026-10-11T14:59:59Z", True),
        ("2026-10-11T15:00:00Z", False),
    ],
)
def test_fixture_window_is_evaluated_in_jst(kickoff: str, expected: bool) -> None:
    fixture = {"kickoff": kickoff}
    assert (
        handler._fixture_in_window(
            fixture,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )
        is expected
    )


@pytest.mark.parametrize(
    ("reference_date", "expected_season"),
    [
        (date(2026, 7, 1), 2026),
        (date(2026, 9, 11), 2026),
        (date(2027, 1, 15), 2026),
        (date(2027, 7, 1), 2027),
    ],
)
def test_season_uses_start_year(reference_date: date, expected_season: int) -> None:
    assert handler._season_for(reference_date) == expected_season
