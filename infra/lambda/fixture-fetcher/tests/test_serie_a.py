from __future__ import annotations

from datetime import date

import handler
import split_handler


def test_serie_a_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["seriea"]})

    assert selected == (split_handler.SERIE_A_COMPETITION,)
    assert selected[0] == handler.Competition("seriea", 135, "Serie A", "Italy")
    assert split_handler.SERIE_A_V2_LEAGUE_ID == "it.1"
    assert split_handler.OBJECT_FILENAMES["seriea"] == "serie-a.json"


def test_serie_a_uses_v2_range_fetcher(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_fetch_v2_fixture_pages(**kwargs):
        calls.append(kwargs)
        return [{"id": "it-first"}]

    monkeypatch.setattr(handler, "_fetch_v2_fixture_pages", fake_fetch_v2_fixture_pages)

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.SERIE_A_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert fixtures == [{"id": "it-first"}]
    assert calls == [
        {
            "api_key": "secret",
            "competition": split_handler.SERIE_A_COMPETITION,
            "league_id": "it.1",
            "season": 2026,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]


def test_serie_a_uses_provider_logo_when_static_logo_is_missing() -> None:
    raw = {
        "id": "it-fixture",
        "date": "2026-09-20T18:45:00Z",
        "status": {"short": "NS"},
        "home": {"id": "tm_inter", "name": "Inter", "logo": "https://provider.example/inter.png"},
        "away": {"id": "tm_milan", "name": "AC Milan", "logo": "https://provider.example/milan.png"},
        "score": None,
    }

    normalized = handler._normalize_fixture(raw, split_handler.SERIE_A_COMPETITION)

    assert normalized["home"]["logo"] == "https://provider.example/inter.png"
    assert normalized["away"]["logo"] == "https://provider.example/milan.png"
