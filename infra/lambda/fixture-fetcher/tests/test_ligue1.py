from __future__ import annotations

from datetime import date

import handler
import split_handler


def test_ligue1_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["ligue1"]})

    assert selected == (split_handler.LIGUE1_COMPETITION,)
    assert selected[0] == handler.Competition("ligue1", 61, "Ligue 1", "France")
    assert split_handler.OBJECT_FILENAMES["ligue1"] == "ligue1.json"
    assert split_handler._provider_name(selected[0]) == "API-Football"


def test_ligue1_uses_api_football_range_fetcher(monkeypatch) -> None:
    fetch_calls: list[dict] = []
    raw = [{"fixture": {"id": "fr-first"}}]

    def fake_fetch(**kwargs):
        fetch_calls.append(kwargs)
        return raw

    monkeypatch.setattr(split_handler, "fetch_fixtures", fake_fetch)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.LIGUE1_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 13),
        to_date=date(2026, 10, 4),
    )

    assert fixtures == raw
    assert fetch_calls == [
        {
            "api_key": "secret",
            "league_id": 61,
            "season": 2026,
            "from_date": date(2026, 9, 13),
            "to_date": date(2026, 10, 4),
            "competition_label": "Ligue 1",
        }
    ]


def test_scheduler_default_includes_ligue1() -> None:
    assert [competition.app_id for competition in split_handler._selected_competitions({})] == [
        "epl",
        "laliga",
        "bundesliga",
        "ligue1",
        "j1",
    ]
