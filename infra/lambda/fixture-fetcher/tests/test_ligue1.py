from __future__ import annotations

from datetime import date

import handler
import split_handler


def test_ligue1_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["ligue1"]})

    assert selected == (split_handler.LIGUE1_COMPETITION,)
    assert selected[0] == handler.Competition("ligue1", 61, "Ligue 1", "France")
    assert split_handler.LIGUE1_V2_LEAGUE_ID == "fr.1"
    assert split_handler.OBJECT_FILENAMES["ligue1"] == "ligue1.json"


def test_ligue1_uses_v2_range_fetcher(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_fetch_v2_fixture_pages(**kwargs):
        calls.append(kwargs)
        return [{"id": "fr-first"}]

    monkeypatch.setattr(handler, "_fetch_v2_fixture_pages", fake_fetch_v2_fixture_pages)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.LIGUE1_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert fixtures == [{"id": "fr-first"}]
    assert calls == [
        {
            "api_key": "secret",
            "competition": split_handler.LIGUE1_COMPETITION,
            "league_id": "fr.1",
            "season": 2026,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]


def test_scheduler_default_includes_ligue1() -> None:
    assert [competition.app_id for competition in split_handler._selected_competitions({})] == [
        "epl",
        "laliga",
        "bundesliga",
        "ligue1",
    ]
