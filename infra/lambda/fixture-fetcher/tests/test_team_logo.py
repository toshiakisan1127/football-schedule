from __future__ import annotations

import pytest

import handler
import validation


def test_v1_fixture_preserves_team_logos() -> None:
    raw = {
        "fixture": {
            "id": 1001,
            "date": "2026-09-12T06:00:00Z",
            "status": {"short": "NS"},
        },
        "teams": {
            "home": {
                "id": 40,
                "name": "Home FC",
                "logo": "https://cdn.example.com/home.webp",
            },
            "away": {
                "id": 33,
                "name": "Away FC",
                "logo": "https://cdn.example.com/away.webp",
            },
        },
        "goals": {"home": None, "away": None},
    }

    normalized = handler._normalize_fixture(raw, handler.COMPETITIONS[0])

    assert normalized["home"]["logo"] == "https://cdn.example.com/home.webp"
    assert normalized["away"]["logo"] == "https://cdn.example.com/away.webp"


def test_v2_fixture_preserves_team_logos() -> None:
    raw = {
        "id": "fx_1",
        "date": "2026-09-12T06:00:00Z",
        "status": "scheduled",
        "homeTeam": {
            "id": "tm_home",
            "name": "Home FC",
            "logo": "https://cdn.example.com/home-v2.webp",
        },
        "awayTeam": {
            "id": "tm_away",
            "name": "Away FC",
            "logo": "https://cdn.example.com/away-v2.webp",
        },
        "homeScore": None,
        "awayScore": None,
    }

    normalized = handler._normalize_fixture(raw, handler.COMPETITIONS[1])

    assert normalized["home"]["logo"] == "https://cdn.example.com/home-v2.webp"
    assert normalized["away"]["logo"] == "https://cdn.example.com/away-v2.webp"


def test_image_and_crest_are_supported_without_extra_api_calls() -> None:
    assert handler._normalize_team_logo({"image": "https://cdn.example.com/image.webp"}) == (
        "https://cdn.example.com/image.webp"
    )
    assert handler._normalize_team_logo({"crest": "https://cdn.example.com/crest.webp"}) == (
        "https://cdn.example.com/crest.webp"
    )


def test_missing_or_blank_logo_is_omitted() -> None:
    raw = {
        "fixture": {
            "id": 1001,
            "date": "2026-09-12T06:00:00Z",
            "status": {"short": "NS"},
        },
        "teams": {
            "home": {"id": 40, "name": "Home FC", "logo": "  "},
            "away": {"id": 33, "name": "Away FC"},
        },
        "goals": {"home": None, "away": None},
    }

    normalized = handler._normalize_fixture(raw, handler.COMPETITIONS[0])

    assert "logo" not in normalized["home"]
    assert "logo" not in normalized["away"]


def test_fixture_document_rejects_non_http_logo_url() -> None:
    document = {
        "schemaVersion": 1,
        "generatedAt": "2026-09-11T02:00:00Z",
        "range": {"from": "2026-09-10", "to": "2026-09-25"},
        "fixtures": [
            {
                "id": "1001",
                "competition": {
                    "id": "epl",
                    "name": "Premier League",
                    "country": "England",
                },
                "home": {
                    "id": "40",
                    "name": "Home FC",
                    "logo": "javascript:alert(1)",
                },
                "away": {"id": "33", "name": "Away FC"},
                "kickoff": "2026-09-12T06:00:00Z",
                "status": "scheduled",
                "score": None,
            }
        ],
    }

    with pytest.raises(validation.FixtureDocumentValidationError, match="HTTP\\(S\\) URL"):
        validation.validate_fixture_document(document, competition_ids={"epl", "laliga"})
