from __future__ import annotations

import json
from datetime import datetime

import live_handler


def _live_fixture() -> dict:
    return {
        "fixture": {
            "id": 1575165,
            "status": {"short": "2H", "elapsed": 76, "extra": None},
        },
        "league": {"id": 78, "name": "Bundesliga"},
        "goals": {"home": 1, "away": 1},
        "events": [
            {
                "time": {"elapsed": 11, "extra": None},
                "team": {"id": 192, "name": "1. FC Köln"},
                "player": {"id": 25380, "name": "Linton Maina"},
                "assist": {"id": 21587, "name": "Ellyes Skhiri"},
                "type": "Goal",
                "detail": "Normal Goal",
            },
            {
                "time": {"elapsed": 64, "extra": None},
                "team": {"id": 192, "name": "1. FC Köln"},
                "player": {"id": 93016, "name": "Thijs Dallinga"},
                "assist": {"id": 37439, "name": "Ragnar Ache"},
                "type": "subst",
                "detail": "Substitution 1",
            },
            {
                "time": {"elapsed": 72, "extra": None},
                "team": {"id": 162, "name": "Werder Bremen"},
                "player": {"id": 8673, "name": "Olivier Deman"},
                "assist": {"id": None, "name": None},
                "type": "Card",
                "detail": "Yellow Card",
            },
        ],
    }


def test_build_live_document_normalizes_score_status_and_events() -> None:
    document = live_handler._build_live_document([_live_fixture()])

    assert document["schemaVersion"] == 1
    generated_at = datetime.fromisoformat(document["generatedAt"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(document["expiresAt"].replace("Z", "+00:00"))
    assert (expires_at - generated_at).total_seconds() == 10 * 60
    assert len(document["fixtures"]) == 1
    fixture = document["fixtures"][0]
    assert fixture == {
        "id": "1575165",
        "competitionId": "bundesliga",
        "period": "2H",
        "elapsed": 76,
        "extra": None,
        "score": {"home": 1, "away": 1},
        "events": [
            {
                "type": "goal",
                "detail": "Normal Goal",
                "elapsed": 11,
                "extra": None,
                "teamId": "192",
                "teamName": "1. FC Köln",
                "player": "Linton Maina",
                "assist": "Ellyes Skhiri",
            },
            {
                "type": "substitution",
                "detail": "Substitution 1",
                "elapsed": 64,
                "extra": None,
                "teamId": "192",
                "teamName": "1. FC Köln",
                "player": "Thijs Dallinga",
                "assist": "Ragnar Ache",
            },
            {
                "type": "card",
                "detail": "Yellow Card",
                "elapsed": 72,
                "extra": None,
                "teamId": "162",
                "teamName": "Werder Bremen",
                "player": "Olivier Deman",
                "assist": None,
            },
        ],
    }


def test_normalize_event_preserves_goal_detail_and_var_events() -> None:
    missed_penalty = live_handler._normalize_event(
        {
            "time": {"elapsed": 25, "extra": None},
            "team": {"id": 192, "name": "1. FC Köln"},
            "player": {"id": 1, "name": "Penalty Taker"},
            "assist": {"id": None, "name": None},
            "type": "Goal",
            "detail": "Missed Penalty",
        }
    )
    var_event = live_handler._normalize_event(
        {
            "time": {"elapsed": 31, "extra": None},
            "team": {"id": 192, "name": "1. FC Köln"},
            "player": {"id": 1, "name": "Penalty Taker"},
            "assist": {"id": None, "name": None},
            "type": "Var",
            "detail": "Goal cancelled",
        }
    )

    assert missed_penalty is not None
    assert missed_penalty["type"] == "goal"
    assert missed_penalty["detail"] == "Missed Penalty"
    assert var_event is not None
    assert var_event["type"] == "var"
    assert var_event["detail"] == "Goal cancelled"


def test_lambda_handler_publishes_complete_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixtures-bucket")
    monkeypatch.setenv("API_FOOTBALL_KEY_PARAMETER_NAME", "/football/key")

    monkeypatch.setattr(live_handler.legacy, "_load_api_key", lambda parameter_name: "secret")
    monkeypatch.setattr(live_handler, "fetch_live_fixtures", lambda **kwargs: [_live_fixture()])

    puts: list[dict] = []

    class S3:
        def put_object(self, **kwargs) -> None:
            puts.append(kwargs)

    monkeypatch.setattr(live_handler.legacy, "_s3_client", lambda: S3())

    result = live_handler.lambda_handler({}, None)

    assert result["ok"] is True
    assert result["fixtureCount"] == 1
    assert result["objectKey"] == "data/fixtures/live.json"
    assert result["expiresAt"]
    assert len(puts) == 1
    assert puts[0]["Bucket"] == "fixtures-bucket"
    assert puts[0]["Key"] == "data/fixtures/live.json"
    assert puts[0]["CacheControl"] == "public, max-age=60"
    body = json.loads(puts[0]["Body"].decode("utf-8"))
    assert body["fixtures"][0]["id"] == "1575165"
    assert body["expiresAt"] == result["expiresAt"]


def test_successful_empty_live_response_replaces_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixtures-bucket")
    monkeypatch.setenv("API_FOOTBALL_KEY_PARAMETER_NAME", "/football/key")
    monkeypatch.setattr(live_handler.legacy, "_load_api_key", lambda parameter_name: "secret")
    monkeypatch.setattr(live_handler, "fetch_live_fixtures", lambda **kwargs: [])

    puts: list[dict] = []

    class S3:
        def put_object(self, **kwargs) -> None:
            puts.append(kwargs)

    monkeypatch.setattr(live_handler.legacy, "_s3_client", lambda: S3())

    live_handler.lambda_handler({}, None)

    body = json.loads(puts[0]["Body"].decode("utf-8"))
    assert body["fixtures"] == []
    assert body["expiresAt"]
