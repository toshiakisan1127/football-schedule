from __future__ import annotations

import json
import logging
from datetime import date

import handler


def _fixture(*, fixture_id: str, home_id: str | None, home_name: str, away_id: str | None, away_name: str) -> dict:
    return {
        "id": fixture_id,
        "date": "2026-09-12T15:00:00Z",
        "status": None,
        "home": {"id": home_id, "name": home_name},
        "away": {"id": away_id, "name": away_name},
        "score": {"home": None, "away": None},
    }


def test_missing_team_id_reuses_provider_id_from_same_response() -> None:
    fixtures = [
        _fixture(
            fixture_id="fx_missing",
            home_id=None,
            home_name="Aston Villa FC",
            away_id="tm_forest",
            away_name="Nottingham Forest FC",
        ),
        _fixture(
            fixture_id="fx_complete",
            home_id="tm_villa",
            home_name="Aston Villa FC",
            away_id="tm_other",
            away_name="Other FC",
        ),
    ]

    team_ids = handler._collect_team_ids(fixtures)
    normalized = handler._normalize_fixture(fixtures[0], handler.COMPETITIONS[0], team_ids=team_ids)

    assert normalized["home"]["id"] == "tm_villa"
    assert normalized["home"]["id"] != "None"


def test_missing_team_id_uses_deterministic_fallback() -> None:
    fixture = _fixture(
        fixture_id="fx_missing",
        home_id=None,
        home_name="Unknown FC",
        away_id="tm_other",
        away_name="Other FC",
    )

    first = handler._normalize_fixture(fixture, handler.COMPETITIONS[0], team_ids={})
    second = handler._normalize_fixture(fixture, handler.COMPETITIONS[0], team_ids={})

    assert first["home"]["id"] == second["home"]["id"]
    assert first["home"]["id"].startswith("team-name-")
    assert first["home"]["id"] != "None"


def test_fetch_logs_compact_raw_fixture_diagnostics(monkeypatch, caplog) -> None:
    raw = _fixture(
        fixture_id="fx_raw",
        home_id=None,
        home_name="Aston Villa FC",
        away_id="tm_forest",
        away_name="Nottingham Forest FC",
    )

    monkeypatch.setattr(
        handler,
        "_get_api_json",
        lambda *args, **kwargs: {
            "data": [raw],
            "meta": {"count": 1, "cursor": 0, "nextCursor": None},
        },
    )

    with caplog.at_level(logging.INFO, logger=handler.LOGGER.name):
        handler._fetch_competition_fixtures(
            api_key="secret",
            competition=handler.COMPETITIONS[0],
            season=2026,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 9, 25),
        )

    record = next(record for record in caplog.records if record.message.startswith("Raw KickoffAPI fixtures:"))
    payload = json.loads(record.message.split("items=", 1)[1])

    assert payload == [
        {
            "id": "fx_raw",
            "date": "2026-09-12T15:00:00Z",
            "status": None,
            "home": {"id": None, "name": "Aston Villa FC"},
            "away": {"id": "tm_forest", "name": "Nottingham Forest FC"},
        }
    ]
    assert "secret" not in record.message
