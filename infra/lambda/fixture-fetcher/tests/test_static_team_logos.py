from __future__ import annotations

from datetime import date

from laliga_v2 import select_canonical_fixtures
from team_logos import TEAM_LOGOS, get_static_team_logo


def _fixture(*, fixture_id: str, kickoff: str, time: str | None) -> dict:
    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "lg_laliga", "name": "La Liga", "season": 2026},
        "home": {"id": "tm_sevilla", "name": "Sevilla FC"},
        "away": {"id": "tm_valencia", "name": "Valencia CF"},
        "score": None,
        "round": "Matchday 5",
        "source": "owned",
    }


def test_static_logo_snapshot_covers_supported_leagues() -> None:
    assert set(TEAM_LOGOS) == {"epl", "laliga", "bundesliga", "ligue1", "j1"}
    assert len(TEAM_LOGOS["epl"]) == 20
    assert len(TEAM_LOGOS["laliga"]) == 20
    assert len(TEAM_LOGOS["bundesliga"]) == 18
    assert len(TEAM_LOGOS["ligue1"]) == 18
    assert len(TEAM_LOGOS["j1"]) == 20
    assert sum(len(teams) for teams in TEAM_LOGOS.values()) == 96


def test_static_logo_snapshot_has_expected_known_teams() -> None:
    assert get_static_team_logo("epl", "Brighton") == (
        "https://images.kickoffapi.com/images/logos/51.png?format=webp"
    )
    assert get_static_team_logo("laliga", "FC Barcelona") == (
        "https://images.kickoffapi.com/images/logos/529.png?format=webp"
    )
    assert get_static_team_logo("laliga", "Deportivo Alavés") == (
        "https://images.kickoffapi.com/images/logos/542.png?format=webp"
    )
    assert get_static_team_logo("bundesliga", "Bayern München") == (
        "https://images.kickoffapi.com/images/logos/157.png?format=webp"
    )
    assert get_static_team_logo("ligue1", "Paris Saint Germain") == (
        "https://images.kickoffapi.com/images/logos/85.png?format=webp"
    )
    assert get_static_team_logo("j1", "Kawasaki Frontale") == (
        "https://images.kickoffapi.com/images/logos/294.png?format=webp"
    )


def test_bundesliga_v2_team_name_aliases_resolve_static_logos() -> None:
    aliases = {
        "1. FC Union Berlin": 182,
        "TSG 1899 Hoffenheim": 167,
        "1. FSV Mainz 05": 164,
        "Bayer 04 Leverkusen": 168,
        "SV Werder Bremen": 162,
        "SV 07 Elversberg": 1660,
        "FC Bayern München": 157,
    }

    for team_name, logo_id in aliases.items():
        assert get_static_team_logo("bundesliga", team_name) == (
            f"https://images.kickoffapi.com/images/logos/{logo_id}.png?format=webp"
        )


def test_laliga_v2_uses_static_logo_when_provider_omits_it() -> None:
    canonical = _fixture(
        fixture_id="fx_canonical",
        kickoff="2026-09-11T19:00:00.000Z",
        time=None,
    )
    wall_clock = _fixture(
        fixture_id="fx_wall_clock",
        kickoff="2026-09-11T21:00:00.000Z",
        time="21:00",
    )

    selected = select_canonical_fixtures(
        [canonical, wall_clock],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert selected[0]["home"]["logo"] == (
        "https://images.kickoffapi.com/images/logos/536.png?format=webp"
    )
    assert selected[0]["away"]["logo"] == (
        "https://images.kickoffapi.com/images/logos/532.png?format=webp"
    )


def test_laliga_v2_provider_logo_still_wins_over_static_snapshot() -> None:
    canonical = _fixture(
        fixture_id="fx_canonical",
        kickoff="2026-09-11T19:00:00.000Z",
        time=None,
    )
    canonical["home"]["logo"] = "https://provider.example/sevilla.webp"
    wall_clock = _fixture(
        fixture_id="fx_wall_clock",
        kickoff="2026-09-11T21:00:00.000Z",
        time="21:00",
    )

    selected = select_canonical_fixtures(
        [canonical, wall_clock],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert selected[0]["home"]["logo"] == "https://provider.example/sevilla.webp"
