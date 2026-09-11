from __future__ import annotations

from datetime import date

import pytest

from bundesliga_v2 import BundesligaV2SelectionError, select_canonical_fixtures


def fixture(
    *,
    fixture_id: str,
    kickoff: str,
    time: str | None,
    home: str = "1. FC Union Berlin",
    away: str = "FC Schalke 04",
    round_name: str = "Matchday 3",
) -> dict:
    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "de.1", "name": "Bundesliga", "season": 2026},
        "home": {"id": "tm_union", "name": home},
        "away": {"id": "tm_schalke", "name": away},
        "score": None,
        "round": round_name,
        "source": "owned",
    }


def test_selects_union_schalke_1830z_as_canonical_kickoff() -> None:
    selected = select_canonical_fixtures(
        [
            fixture(
                fixture_id="canonical",
                kickoff="2026-09-11T18:30:00.000Z",
                time=None,
            ),
            fixture(
                fixture_id="berlin-wall-clock",
                kickoff="2026-09-11T20:30:00.000Z",
                time="20:30",
            ),
        ],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert [item["id"] for item in selected] == ["canonical"]
    assert selected[0]["date"] == "2026-09-11T18:30:00.000Z"


def test_single_fixture_is_preserved_without_requiring_a_sibling() -> None:
    single = fixture(
        fixture_id="single",
        kickoff="2026-09-12T13:30:00.000Z",
        time=None,
        home="SC Freiburg",
        away="Borussia Mönchengladbach",
    )

    selected = select_canonical_fixtures(
        [single],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert selected == [single]


def test_unresolved_duplicate_group_is_preserved(caplog: pytest.LogCaptureFixture) -> None:
    raw = [
        fixture(fixture_id="a", kickoff="2026-09-11T18:30:00.000Z", time=None),
        fixture(fixture_id="b", kickoff="2026-09-11T19:30:00.000Z", time=None),
    ]

    with caplog.at_level("WARNING"):
        selected = select_canonical_fixtures(
            raw,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )

    assert selected == raw
    assert "Preserving unresolved Bundesliga v2 duplicate fixture" in caplog.text


def test_multiple_verified_candidates_fail_closed() -> None:
    raw = [
        fixture(fixture_id="canonical-1", kickoff="2026-09-11T18:30:00.000Z", time=None),
        fixture(fixture_id="wall-1", kickoff="2026-09-11T20:30:00.000Z", time="20:30"),
        fixture(fixture_id="canonical-2", kickoff="2026-09-12T18:30:00.000Z", time=None),
        fixture(fixture_id="wall-2", kickoff="2026-09-12T20:30:00.000Z", time="20:30"),
    ]

    with pytest.raises(BundesligaV2SelectionError, match="selected=2"):
        select_canonical_fixtures(
            raw,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )
