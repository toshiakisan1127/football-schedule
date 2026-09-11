from __future__ import annotations

from datetime import date

import handler
import split_handler


def test_ucl_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["ucl"]})

    assert selected == (split_handler.UCL_COMPETITION,)
    assert selected[0] == handler.Competition("ucl", 2, "UEFA Champions League", "Europe")
    assert split_handler.UCL_V2_LEAGUE_ID == "lg_4WmajCeHmdkK"
    assert split_handler.OBJECT_FILENAMES["ucl"] == "champions-league.json"


def test_ucl_uses_v2_range_fetcher(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_fetch_v2_fixture_pages(**kwargs):
        calls.append(kwargs)
        return [{"id": "ucl-first"}]

    monkeypatch.setattr(handler, "_fetch_v2_fixture_pages", fake_fetch_v2_fixture_pages)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.UCL_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert fixtures == [{"id": "ucl-first"}]
    assert calls == [
        {
            "api_key": "secret",
            "competition": split_handler.UCL_COMPETITION,
            "league_id": "lg_4WmajCeHmdkK",
            "season": 2026,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]
