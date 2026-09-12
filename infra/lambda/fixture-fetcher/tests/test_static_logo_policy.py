from __future__ import annotations

import handler


def _fixture(home: str, away: str, *, home_logo: str | None = None, away_logo: str | None = None) -> dict:
    home_team = {"id": "home-id", "name": home}
    away_team = {"id": "away-id", "name": away}
    if home_logo is not None:
        home_team["logo"] = home_logo
    if away_logo is not None:
        away_team["logo"] = away_logo
    return {
        "fixture": {
            "id": "fx-1",
            "date": "2026-09-12T13:30:00Z",
            "status": {"short": "NS"},
        },
        "teams": {
            "home": home_team,
            "away": away_team,
        },
        "goals": {"home": None, "away": None},
    }


def test_static_logo_wins_for_premier_league() -> None:
    fixture = _fixture(
        "Brighton",
        "Manchester United",
        home_logo="https://provider.example/brighton.png",
        away_logo="https://provider.example/man-utd.png",
    )

    normalized = handler._normalize_fixture(fixture, handler.COMPETITIONS[0])

    assert normalized["home"]["logo"] == "https://images.kickoffapi.com/images/logos/51.png?format=webp"
    assert normalized["away"]["logo"] == "https://images.kickoffapi.com/images/logos/33.png?format=webp"


def test_static_logo_wins_for_laliga() -> None:
    fixture = _fixture(
        "FC Barcelona",
        "Real Madrid CF",
        home_logo="https://provider.example/barcelona.png",
        away_logo="https://provider.example/real-madrid.png",
    )

    normalized = handler._normalize_fixture(fixture, handler.COMPETITIONS[1])

    assert normalized["home"]["logo"] == "https://images.kickoffapi.com/images/logos/529.png?format=webp"
    assert normalized["away"]["logo"] == "https://images.kickoffapi.com/images/logos/541.png?format=webp"


def test_static_logo_wins_for_bundesliga() -> None:
    fixture = _fixture(
        "Bayern München",
        "Borussia Dortmund",
        home_logo="https://provider.example/bayern.png",
        away_logo="https://provider.example/dortmund.png",
    )

    normalized = handler._normalize_fixture(fixture, handler.COMPETITIONS[2])

    assert normalized["home"]["logo"] == "https://images.kickoffapi.com/images/logos/157.png?format=webp"
    assert normalized["away"]["logo"] == "https://images.kickoffapi.com/images/logos/165.png?format=webp"


def test_provider_logo_is_fallback_when_static_mapping_is_missing() -> None:
    fixture = _fixture(
        "Unknown FC",
        "Another FC",
        home_logo="https://provider.example/unknown.png",
    )

    normalized = handler._normalize_fixture(fixture, handler.COMPETITIONS[0])

    assert normalized["home"]["logo"] == "https://provider.example/unknown.png"
    assert "logo" not in normalized["away"]
