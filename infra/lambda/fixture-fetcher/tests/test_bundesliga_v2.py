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
        "home": {"id": "tm_home", "name": home},
        "away": {"id": "tm_away", "name": away},
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


def test_round_wide_placeholder_batch_is_removed_before_window_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    matches = [
        ("Borussia Dortmund", "SV Werder Bremen"),
        ("FC Augsburg", "FC Bayern München"),
        ("1. FC Union Berlin", "SV 07 Elversberg"),
        ("1. FSV Mainz 05", "Bayer 04 Leverkusen"),
        ("TSG 1899 Hoffenheim", "Hamburger SV"),
        ("1. FC Köln", "Borussia Mönchengladbach"),
        ("RB Leipzig", "Eintracht Frankfurt"),
        ("SC Paderborn 07", "VfB Stuttgart"),
        ("SC Freiburg", "FC Schalke 04"),
    ]
    finalized_kickoffs = [
        "2026-10-09T18:30:00.000Z",
        "2026-10-10T13:30:00.000Z",
        "2026-10-10T13:30:00.000Z",
        "2026-10-10T13:30:00.000Z",
        "2026-10-10T13:30:00.000Z",
        "2026-10-11T13:30:00.000Z",
        "2026-10-10T16:30:00.000Z",
        "2026-10-10T13:30:00.000Z",
        "2026-10-11T15:30:00.000Z",
    ]

    raw = []
    for index, ((home, away), finalized_kickoff) in enumerate(
        zip(matches, finalized_kickoffs, strict=True)
    ):
        raw.extend(
            [
                fixture(
                    fixture_id=f"placeholder-{index}",
                    kickoff="2026-10-10T12:00:00.000Z",
                    time=None,
                    home=home,
                    away=away,
                    round_name="Matchday 5",
                ),
                fixture(
                    fixture_id=f"finalized-{index}",
                    kickoff=finalized_kickoff,
                    time=None,
                    home=home,
                    away=away,
                    round_name="Matchday 5",
                ),
            ]
        )

    with caplog.at_level("WARNING"):
        selected = select_canonical_fixtures(
            raw,
            from_date=date(2026, 10, 10),
            to_date=date(2026, 10, 11),
        )

    selected_ids = {item["id"] for item in selected}
    assert "placeholder-3" not in selected_ids
    assert "finalized-3" in selected_ids
    assert all(not fixture_id.startswith("placeholder-") for fixture_id in selected_ids)
    assert "finalized-8" not in selected_ids
    assert "Dropping Bundesliga v2 round-wide placeholder fixture batch" in caplog.text


def test_partial_round_duplicates_are_preserved() -> None:
    raw = [
        fixture(
            fixture_id="placeholder-a",
            kickoff="2026-10-10T12:00:00.000Z",
            time=None,
            home="A",
            away="B",
            round_name="Matchday 5",
        ),
        fixture(
            fixture_id="finalized-a",
            kickoff="2026-10-10T13:30:00.000Z",
            time=None,
            home="A",
            away="B",
            round_name="Matchday 5",
        ),
        fixture(
            fixture_id="placeholder-c",
            kickoff="2026-10-10T12:00:00.000Z",
            time=None,
            home="C",
            away="D",
            round_name="Matchday 5",
        ),
        fixture(
            fixture_id="finalized-c",
            kickoff="2026-10-10T13:30:00.000Z",
            time=None,
            home="C",
            away="D",
            round_name="Matchday 5",
        ),
        fixture(
            fixture_id="only-e",
            kickoff="2026-10-10T12:00:00.000Z",
            time=None,
            home="E",
            away="F",
            round_name="Matchday 5",
        ),
    ]

    selected = select_canonical_fixtures(
        raw,
        from_date=date(2026, 10, 10),
        to_date=date(2026, 10, 11),
    )

    assert {item["id"] for item in selected} == {item["id"] for item in raw}


def test_two_round_wide_duplicate_batches_are_preserved_as_ambiguous(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = []
    for index, (home, away) in enumerate([("A", "B"), ("C", "D"), ("E", "F")]):
        raw.extend(
            [
                fixture(
                    fixture_id=f"batch-a-{index}",
                    kickoff="2026-10-10T12:00:00.000Z",
                    time=None,
                    home=home,
                    away=away,
                    round_name="Matchday 5",
                ),
                fixture(
                    fixture_id=f"batch-b-{index}",
                    kickoff="2026-10-10T13:30:00.000Z",
                    time=None,
                    home=home,
                    away=away,
                    round_name="Matchday 5",
                ),
            ]
        )

    with caplog.at_level("WARNING"):
        selected = select_canonical_fixtures(
            raw,
            from_date=date(2026, 10, 10),
            to_date=date(2026, 10, 11),
        )

    assert {item["id"] for item in selected} == {item["id"] for item in raw}
    assert "Preserving ambiguous Bundesliga v2 round-wide duplicate batches" in caplog.text


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
