from __future__ import annotations

from datetime import date

import handler
import split_handler


def test_europa_league_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["uel"]})

    assert selected == (split_handler.UEL_COMPETITION,)
    assert selected[0] == handler.Competition("uel", 3, "UEFA Europa League", "Europe")
    assert split_handler.OBJECT_FILENAMES["uel"] == "europa-league.json"


def test_europa_league_uses_v1_fixture_fetcher(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_fetch_v1_competition_fixtures(**kwargs):
        calls.append(kwargs)
        return [{"fixture": {"id": 1}}]

    monkeypatch.setattr(handler, "_fetch_v1_competition_fixtures", fake_fetch_v1_competition_fixtures)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.UEL_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert fixtures == [{"fixture": {"id": 1}}]
    assert calls == [
        {
            "api_key": "secret",
            "competition": split_handler.UEL_COMPETITION,
            "season": 2026,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]


def test_europa_league_uses_provider_logo_when_static_logo_is_missing() -> None:
    raw = {
        "fixture": {
            "id": 1,
            "date": "2026-09-17T19:00:00Z",
            "status": {"short": "NS"},
        },
        "teams": {
            "home": {"id": 1, "name": "Roma", "logo": "https://provider.example/roma.png"},
            "away": {"id": 2, "name": "Aston Villa", "logo": "https://provider.example/villa.png"},
        },
        "goals": {"home": None, "away": None},
    }

    normalized = handler._normalize_fixture(raw, split_handler.UEL_COMPETITION)

    assert normalized["home"]["logo"] == "https://provider.example/roma.png"
    assert normalized["away"]["logo"] == "https://provider.example/villa.png"
