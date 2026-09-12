from __future__ import annotations

from datetime import date

import handler
import split_handler
from ligue1_v2 import _get_static_ligue1_logo, select_canonical_fixtures


def _fixture(
    *,
    fixture_id: str,
    kickoff: str,
    time: str | None,
    home: str = "RC Strasbourg Alsace",
    away: str = "AS Monaco FC",
    round_name: str = "Matchday 4",
) -> dict:
    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "lg_ligue1", "name": "Ligue 1", "season": 2026},
        "home": {"id": "tm_home", "name": home},
        "away": {"id": "tm_away", "name": away},
        "score": None,
        "round": round_name,
        "group": None,
        "notes": None,
        "source": "owned",
    }


def test_ligue1_is_supported_by_split_fixture_pipeline() -> None:
    selected = split_handler._selected_competitions({"competitions": ["ligue1"]})

    assert selected == (split_handler.LIGUE1_COMPETITION,)
    assert selected[0] == handler.Competition("ligue1", 61, "Ligue 1", "France")
    assert split_handler.LIGUE1_V2_LEAGUE_ID == "fr.1"
    assert split_handler.OBJECT_FILENAMES["ligue1"] == "ligue1.json"


def test_ligue1_uses_v2_range_fetcher_and_canonical_selector(monkeypatch) -> None:
    fetch_calls: list[dict] = []
    selection_calls: list[dict] = []
    raw = [{"id": "fr-first"}]

    def fake_fetch_v2_fixture_pages(**kwargs):
        fetch_calls.append(kwargs)
        return raw

    def fake_select_canonical_fixtures(fixtures, **kwargs):
        selection_calls.append({"fixtures": fixtures, **kwargs})
        return raw

    monkeypatch.setattr(handler, "_fetch_v2_fixture_pages", fake_fetch_v2_fixture_pages)
    monkeypatch.setattr(
        split_handler,
        "select_ligue1_canonical_fixtures",
        fake_select_canonical_fixtures,
    )

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=split_handler.LIGUE1_COMPETITION,
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert fixtures == raw
    assert fetch_calls == [
        {
            "api_key": "secret",
            "competition": split_handler.LIGUE1_COMPETITION,
            "league_id": "fr.1",
            "season": 2026,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]
    assert selection_calls == [
        {
            "fixtures": raw,
            "from_date": date(2026, 9, 10),
            "to_date": date(2026, 10, 11),
        }
    ]


def test_ligue1_selects_canonical_summer_time_fixture() -> None:
    canonical = _fixture(
        fixture_id="fx_canonical",
        kickoff="2026-09-12T15:15:00.000Z",
        time=None,
    )
    wall_clock = _fixture(
        fixture_id="fx_wall_clock",
        kickoff="2026-09-12T17:15:00.000Z",
        time="17:15",
    )
    stale_placeholder = _fixture(
        fixture_id="fx_placeholder",
        kickoff="2026-09-13T12:00:00.000Z",
        time=None,
    )

    selected = select_canonical_fixtures(
        [canonical, wall_clock, stale_placeholder],
        from_date=date(2026, 9, 11),
        to_date=date(2026, 9, 20),
    )

    assert [fixture["id"] for fixture in selected] == ["fx_canonical"]
    assert selected[0]["date"] == "2026-09-12T15:15:00.000Z"


def test_ligue1_selects_canonical_after_dst_switch() -> None:
    canonical = _fixture(
        fixture_id="fx_canonical",
        kickoff="2026-10-25T19:45:00.000Z",
        time=None,
        home="Paris Saint-Germain FC",
        away="Olympique Lyonnais",
        round_name="Matchday 8",
    )
    wall_clock = _fixture(
        fixture_id="fx_wall_clock",
        kickoff="2026-10-25T20:45:00.000Z",
        time="20:45",
        home="Paris Saint-Germain FC",
        away="Olympique Lyonnais",
        round_name="Matchday 8",
    )

    selected = select_canonical_fixtures(
        [canonical, wall_clock],
        from_date=date(2026, 10, 24),
        to_date=date(2026, 10, 26),
    )

    assert [fixture["id"] for fixture in selected] == ["fx_canonical"]


def test_ligue1_canonical_fixture_backfills_static_logos() -> None:
    canonical = _fixture(
        fixture_id="fx_canonical",
        kickoff="2026-09-12T15:15:00.000Z",
        time=None,
    )
    wall_clock = _fixture(
        fixture_id="fx_wall_clock",
        kickoff="2026-09-12T17:15:00.000Z",
        time="17:15",
    )

    selected = select_canonical_fixtures(
        [canonical, wall_clock],
        from_date=date(2026, 9, 11),
        to_date=date(2026, 9, 20),
    )

    assert selected[0]["home"]["logo"] == (
        "https://images.kickoffapi.com/images/logos/95.png?format=webp"
    )
    assert selected[0]["away"]["logo"] == (
        "https://images.kickoffapi.com/images/logos/91.png?format=webp"
    )


def test_ligue1_v2_team_names_resolve_all_static_logos() -> None:
    v2_team_names = [
        "Angers SCO",
        "AJ Auxerre",
        "ES Troyes AC",
        "Le Havre AC",
        "Le Mans FC",
        "Racing Club de Lens",
        "Lille OSC",
        "FC Lorient",
        "Olympique Lyonnais",
        "Olympique de Marseille",
        "AS Monaco FC",
        "OGC Nice",
        "Paris FC",
        "Paris Saint-Germain FC",
        "Stade Rennais FC 1901",
        "Stade Brestois 29",
        "RC Strasbourg Alsace",
        "Toulouse FC",
    ]

    assert all(_get_static_ligue1_logo(team_name) is not None for team_name in v2_team_names)
    assert _get_static_ligue1_logo("Paris Saint-Germain FC") == (
        "https://images.kickoffapi.com/images/logos/85.png?format=webp"
    )


def test_scheduler_default_includes_ligue1() -> None:
    assert [competition.app_id for competition in split_handler._selected_competitions({})] == [
        "epl",
        "laliga",
        "bundesliga",
        "ligue1",
    ]
