from __future__ import annotations

import handler


def _fixture(
    *,
    fixture_id: int,
    home_id: int | None,
    home_name: str,
    away_id: int | None,
    away_name: str,
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": "2026-09-12T15:00:00Z",
            "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        },
        "teams": {
            "home": {"id": home_id, "name": home_name},
            "away": {"id": away_id, "name": away_name},
        },
        "goals": {"home": None, "away": None},
    }


def test_missing_team_id_reuses_provider_id_from_same_response() -> None:
    fixtures = [
        _fixture(
            fixture_id=1,
            home_id=None,
            home_name="Aston Villa FC",
            away_id=50,
            away_name="Nottingham Forest FC",
        ),
        _fixture(
            fixture_id=2,
            home_id=66,
            home_name="Aston Villa FC",
            away_id=77,
            away_name="Other FC",
        ),
    ]

    team_ids = handler._collect_team_ids(fixtures)
    normalized = handler._normalize_fixture(
        fixtures[0],
        handler.COMPETITIONS[0],
        team_ids=team_ids,
    )

    assert normalized["home"]["id"] == "66"
    assert normalized["home"]["id"] != "None"


def test_missing_team_id_uses_deterministic_fallback() -> None:
    fixture = _fixture(
        fixture_id=1,
        home_id=None,
        home_name="Unknown FC",
        away_id=77,
        away_name="Other FC",
    )

    first = handler._normalize_fixture(fixture, handler.COMPETITIONS[0], team_ids={})
    second = handler._normalize_fixture(fixture, handler.COMPETITIONS[0], team_ids={})

    assert first["home"]["id"] == second["home"]["id"]
    assert first["home"]["id"].startswith("team-name-")
    assert first["home"]["id"] != "None"
