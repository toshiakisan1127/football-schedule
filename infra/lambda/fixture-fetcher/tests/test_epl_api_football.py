from __future__ import annotations

from datetime import date

import split_handler


def _raw_epl_fixture() -> dict:
    return {
        "fixture": {
            "id": 1557409,
            "date": "2026-09-19T14:00:00+00:00",
            "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        },
        "league": {
            "id": 39,
            "name": "Premier League",
            "season": 2026,
            "round": "Regular Season - 5",
        },
        "teams": {
            "home": {
                "id": 51,
                "name": "Brighton",
                "logo": "https://media.api-sports.io/football/teams/51.png",
            },
            "away": {
                "id": 42,
                "name": "Arsenal",
                "logo": "https://media.api-sports.io/football/teams/42.png",
            },
        },
        "goals": {"home": None, "away": None},
        "score": {
            "halftime": {"home": None, "away": None},
            "fulltime": {"home": None, "away": None},
            "extratime": {"home": None, "away": None},
            "penalty": {"home": None, "away": None},
        },
    }


def test_epl_routes_to_api_football(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_fetch(**kwargs) -> list[dict]:
        calls.append(kwargs)
        return [_raw_epl_fixture()]

    monkeypatch.setattr(split_handler, "fetch_fixtures", fake_fetch)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="pro-secret",
        competition=split_handler.legacy.Competition("epl", 39, "Premier League", "England"),
        season=2026,
        from_date=date(2026, 9, 13),
        to_date=date(2026, 10, 4),
    )

    assert len(fixtures) == 1
    assert calls == [
        {
            "api_key": "pro-secret",
            "league_id": 39,
            "season": 2026,
            "from_date": date(2026, 9, 13),
            "to_date": date(2026, 10, 4),
            "competition_label": "Premier League",
        }
    ]
    assert split_handler._provider_name(
        split_handler.legacy.Competition("epl", 39, "Premier League", "England")
    ) == "API-Football"


def test_epl_normalization_prefers_api_football_fixture_logos() -> None:
    competition = split_handler.legacy.Competition("epl", 39, "Premier League", "England")
    fixture = split_handler._normalize_provider_fixture(
        _raw_epl_fixture(),
        competition,
        team_ids={"Brighton": "51", "Arsenal": "42"},
    )

    assert fixture["id"] == "1557409"
    assert fixture["kickoff"] == "2026-09-19T14:00:00Z"
    assert fixture["home"]["logo"] == "https://media.api-sports.io/football/teams/51.png"
    assert fixture["away"]["logo"] == "https://media.api-sports.io/football/teams/42.png"
