from __future__ import annotations

import handler


def test_null_status_is_treated_as_scheduled() -> None:
    assert handler._normalize_status(None) == "scheduled"


def test_fixture_with_null_status_normalizes_as_scheduled() -> None:
    normalized = handler._normalize_fixture(
        {
            "id": "fx_null_status",
            "date": "2026-09-12T06:00:00Z",
            "status": None,
            "home": {"id": "tm_home", "name": "Home FC"},
            "away": {"id": "tm_away", "name": "Away FC"},
            "score": {"home": None, "away": None},
        },
        handler.COMPETITIONS[0],
    )

    assert normalized["status"] == "scheduled"
    assert normalized["score"] is None
