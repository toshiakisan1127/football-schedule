from __future__ import annotations

from datetime import date

import handler
from laliga_v2 import select_canonical_fixtures


def _fixture(
    *,
    fixture_id: str,
    kickoff: str,
    time: str | None,
    home_logo: str | None = None,
    away_logo: str | None = None,
) -> dict:
    home = {"id": "tm_home", "name": "Villarreal CF"}
    away = {"id": "tm_away", "name": "Real Betis Balompié"}
    if home_logo is not None:
        home["logo"] = home_logo
    if away_logo is not None:
        away["logo"] = away_logo

    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "es.1", "name": "La Liga", "season": 2026},
        "home": home,
        "away": away,
        "score": None,
        "round": "Matchday 5",
        "source": "owned",
    }


def test_selection_backfills_team_logos_from_wall_clock_sibling() -> None:
    canonical = _fixture(
        fixture_id="canonical",
        kickoff="2026-09-14T19:00:00.000Z",
        time=None,
    )
    sibling = _fixture(
        fixture_id="wall-clock",
        kickoff="2026-09-14T21:00:00.000Z",
        time="21:00",
        home_logo="https://images.kickoffapi.com/images/logos/villarreal.png?format=webp",
        away_logo="https://images.kickoffapi.com/images/logos/betis.png?format=webp",
    )

    selected = select_canonical_fixtures(
        [canonical, sibling],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert len(selected) == 1
    assert selected[0]["id"] == "canonical"
    assert selected[0]["home"]["logo"].endswith("villarreal.png?format=webp")
    assert selected[0]["away"]["logo"].endswith("betis.png?format=webp")


def test_canonical_team_logo_is_not_overwritten_by_sibling() -> None:
    canonical = _fixture(
        fixture_id="canonical",
        kickoff="2026-09-14T19:00:00.000Z",
        time=None,
        home_logo="https://images.kickoffapi.com/canonical-villarreal.png",
    )
    sibling = _fixture(
        fixture_id="wall-clock",
        kickoff="2026-09-14T21:00:00.000Z",
        time="21:00",
        home_logo="https://images.kickoffapi.com/sibling-villarreal.png",
    )

    selected = select_canonical_fixtures(
        [canonical, sibling],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert selected[0]["home"]["logo"] == "https://images.kickoffapi.com/canonical-villarreal.png"


def test_backfilled_v2_logo_reaches_normalized_fixture() -> None:
    canonical = _fixture(
        fixture_id="canonical",
        kickoff="2026-09-14T19:00:00.000Z",
        time=None,
    )
    sibling = _fixture(
        fixture_id="wall-clock",
        kickoff="2026-09-14T21:00:00.000Z",
        time="21:00",
        home_logo="https://images.kickoffapi.com/images/logos/villarreal.png?format=webp",
        away_logo="https://images.kickoffapi.com/images/logos/betis.png?format=webp",
    )

    selected = select_canonical_fixtures(
        [canonical, sibling],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )[0]
    normalized = handler._normalize_fixture(selected, handler.COMPETITIONS[1])

    assert normalized["home"]["logo"].endswith("villarreal.png?format=webp")
    assert normalized["away"]["logo"].endswith("betis.png?format=webp")
