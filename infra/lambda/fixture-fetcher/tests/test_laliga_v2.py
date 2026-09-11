from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from laliga_v2 import LaLigaV2SelectionError, select_canonical_fixtures

MADRID = ZoneInfo("Europe/Madrid")


def fixture(
    *,
    fixture_id: str,
    kickoff: str,
    time: str | None,
    home: str,
    away: str,
    round_name: str,
    home_id: str | None = "home-id",
    away_id: str | None = "away-id",
) -> dict:
    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "lg_laliga", "name": "La Liga", "season": 2026},
        "home": {"id": home_id, "name": home},
        "away": {"id": away_id, "name": away},
        "score": None,
        "round": round_name,
        "source": "owned",
    }


def wall_clock_sibling(
    *, fixture_id: str, kickoff: str, home: str, away: str, round_name: str
) -> dict:
    canonical = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    madrid = canonical.astimezone(MADRID)
    wall_clock_as_utc = madrid.replace(tzinfo=timezone.utc)
    return fixture(
        fixture_id=fixture_id,
        kickoff=wall_clock_as_utc.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        time=madrid.strftime("%H:%M"),
        home=home,
        away=away,
        round_name=round_name,
    )


VALIDATED_FIXTURES = [
    ("Sevilla FC", "Valencia CF", "Matchday 5", "2026-09-11T19:00:00.000Z"),
    ("Real Racing Club de Santander", "Deportivo Alavés", "Matchday 5", "2026-09-12T12:00:00.000Z"),
    ("CA Osasuna", "RCD Espanyol de Barcelona", "Matchday 5", "2026-09-12T14:15:00.000Z"),
    ("Athletic Club", "Elche CF", "Matchday 5", "2026-09-12T16:30:00.000Z"),
    ("Real Madrid CF", "Rayo Vallecano de Madrid", "Matchday 5", "2026-09-12T19:00:00.000Z"),
    ("RC Celta de Vigo", "Málaga CF", "Matchday 5", "2026-09-13T12:00:00.000Z"),
    ("Levante UD", "FC Barcelona", "Matchday 5", "2026-09-13T14:15:00.000Z"),
    ("Getafe CF", "RC Deportivo La Coruña", "Matchday 5", "2026-09-13T16:30:00.000Z"),
    ("Real Sociedad de Fútbol", "Club Atlético de Madrid", "Matchday 5", "2026-09-13T19:00:00.000Z"),
    ("Villarreal CF", "Real Betis Balompié", "Matchday 5", "2026-09-14T19:00:00.000Z"),
    ("Rayo Vallecano de Madrid", "RCD Espanyol de Barcelona", "Matchday 6", "2026-09-15T17:00:00.000Z"),
    ("Deportivo Alavés", "Valencia CF", "Matchday 6", "2026-09-15T18:00:00.000Z"),
    ("Elche CF", "Real Madrid CF", "Matchday 6", "2026-09-15T19:30:00.000Z"),
    ("RC Deportivo La Coruña", "Sevilla FC", "Matchday 6", "2026-09-16T17:00:00.000Z"),
    ("Club Atlético de Madrid", "CA Osasuna", "Matchday 6", "2026-09-16T17:00:00.000Z"),
    ("FC Barcelona", "Real Racing Club de Santander", "Matchday 6", "2026-09-16T19:30:00.000Z"),
    ("Levante UD", "Athletic Club", "Matchday 6", "2026-09-16T19:30:00.000Z"),
    ("Real Betis Balompié", "Getafe CF", "Matchday 6", "2026-09-17T17:00:00.000Z"),
    ("Málaga CF", "Villarreal CF", "Matchday 6", "2026-09-17T19:30:00.000Z"),
    ("RCD Espanyol de Barcelona", "Elche CF", "Matchday 7", "2026-09-18T19:00:00.000Z"),
    ("CA Osasuna", "Rayo Vallecano de Madrid", "Matchday 7", "2026-09-19T12:00:00.000Z"),
    ("Athletic Club", "Deportivo Alavés", "Matchday 7", "2026-09-19T14:15:00.000Z"),
    ("RC Celta de Vigo", "Real Racing Club de Santander", "Matchday 7", "2026-09-19T16:30:00.000Z"),
    ("Sevilla FC", "FC Barcelona", "Matchday 7", "2026-09-19T19:00:00.000Z"),
]


def test_selection_rule_reproduces_all_24_v1_verified_fixtures() -> None:
    raw: list[dict] = []
    expected_dates: set[str] = set()

    for index, (home, away, round_name, kickoff) in enumerate(VALIDATED_FIXTURES):
        expected_dates.add(kickoff)
        raw.append(
            fixture(
                fixture_id=f"canonical-{index}",
                kickoff=kickoff,
                time=None,
                home=home,
                away=away,
                round_name=round_name,
            )
        )
        raw.append(
            wall_clock_sibling(
                fixture_id=f"wall-clock-{index}",
                kickoff=kickoff,
                home=home,
                away=away,
                round_name=round_name,
            )
        )

        # Mirror the observed provider pattern where some matches also have a
        # noon placeholder on another date. It must not beat the verified pair.
        if index % 3 == 0:
            raw.append(
                fixture(
                    fixture_id=f"placeholder-{index}",
                    kickoff="2026-09-20T12:00:00.000Z",
                    time=None,
                    home=home,
                    away=away,
                    round_name=round_name,
                )
            )

    selected = select_canonical_fixtures(
        raw,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert len(selected) == 24
    assert {item["date"] for item in selected} == expected_dates
    assert all(item["time"] is None for item in selected)


def test_selection_ignores_unpaired_placeholder_when_verified_pair_exists() -> None:
    home = "Real Betis Balompié"
    away = "Getafe CF"
    round_name = "Matchday 6"
    canonical = fixture(
        fixture_id="canonical",
        kickoff="2026-09-17T17:00:00.000Z",
        time=None,
        home=home,
        away=away,
        round_name=round_name,
    )
    raw = [
        fixture(
            fixture_id="placeholder",
            kickoff="2026-09-16T12:00:00.000Z",
            time=None,
            home=home,
            away=away,
            round_name=round_name,
        ),
        canonical,
        wall_clock_sibling(
            fixture_id="wall-clock",
            kickoff=canonical["date"],
            home=home,
            away=away,
            round_name=round_name,
        ),
    ]

    selected = select_canonical_fixtures(
        raw,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert [item["id"] for item in selected] == ["canonical"]


def test_selection_fails_closed_when_relevant_group_has_no_verified_pair() -> None:
    raw = [
        fixture(
            fixture_id="placeholder",
            kickoff="2026-09-13T12:00:00.000Z",
            time=None,
            home="Sevilla FC",
            away="Valencia CF",
            round_name="Matchday 5",
        )
    ]

    with pytest.raises(LaLigaV2SelectionError, match="selected=0"):
        select_canonical_fixtures(
            raw,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 9, 20),
        )


def test_selection_fails_closed_when_two_verified_pairs_exist() -> None:
    home = "Sevilla FC"
    away = "Valencia CF"
    round_name = "Matchday 5"
    first = "2026-09-11T19:00:00.000Z"
    second = "2026-09-12T19:00:00.000Z"
    raw = [
        fixture(
            fixture_id="canonical-1",
            kickoff=first,
            time=None,
            home=home,
            away=away,
            round_name=round_name,
        ),
        wall_clock_sibling(
            fixture_id="wall-clock-1",
            kickoff=first,
            home=home,
            away=away,
            round_name=round_name,
        ),
        fixture(
            fixture_id="canonical-2",
            kickoff=second,
            time=None,
            home=home,
            away=away,
            round_name=round_name,
        ),
        wall_clock_sibling(
            fixture_id="wall-clock-2",
            kickoff=second,
            home=home,
            away=away,
            round_name=round_name,
        ),
    ]

    with pytest.raises(LaLigaV2SelectionError, match="selected=2"):
        select_canonical_fixtures(
            raw,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 9, 20),
        )


def test_selection_ignores_unresolved_groups_outside_publication_window() -> None:
    raw = [
        fixture(
            fixture_id="future-placeholder",
            kickoff="2026-12-01T12:00:00.000Z",
            time=None,
            home="Future Home",
            away="Future Away",
            round_name="Matchday 20",
        )
    ]

    assert (
        select_canonical_fixtures(
            raw,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )
        == []
    )


def test_selection_backfills_team_id_from_sibling() -> None:
    canonical = fixture(
        fixture_id="canonical",
        kickoff="2026-09-11T19:00:00.000Z",
        time=None,
        home="Sevilla FC",
        away="Valencia CF",
        round_name="Matchday 5",
        away_id=None,
    )
    sibling = wall_clock_sibling(
        fixture_id="wall-clock",
        kickoff=canonical["date"],
        home="Sevilla FC",
        away="Valencia CF",
        round_name="Matchday 5",
    )
    sibling["away"]["id"] = "tm_valencia"

    selected = select_canonical_fixtures(
        [canonical, sibling],
        from_date=date(2026, 9, 10),
        to_date=date(2026, 9, 20),
    )

    assert selected[0]["away"]["id"] == "tm_valencia"
