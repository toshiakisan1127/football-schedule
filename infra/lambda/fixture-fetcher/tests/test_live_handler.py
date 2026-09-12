from __future__ import annotations

import json

import live_handler


def _live_fixture() -> dict:
    return {
        "fixture": {
            "id": 1570373,
            "status": {
                "short": "2H",
                "elapsed": 78,
                "extra": None,
            },
        },
        "league": {
            "id": 140,
            "name": "La Liga",
        },
        "goals": {
            "home": 0,
            "away": 1,
        },
        "events": [
            {
                "time": {"elapsed": 50, "extra": None},
                "team": {"id": 797, "name": "Elche"},
                "player": {"id": 311334, "name": "Facundo Buonanotte"},
                "assist": {"id": None, "name": None},
                "type": "Goal",
                "detail": "Penalty",
                "comments": None,
            },
            {
                "time": {"elapsed": 56, "extra": None},
                "team": {"id": 797, "name": "Elche"},
                "player": {"id": 311345, "name": "Federico Redondo Solari"},
                "assist": {"id": None, "name": None},
                "type": "Card",
                "detail": "Yellow Card",
                "comments": "Foul",
            },
            {
                "time": {"elapsed": 65, "extra": None},
                "team": {"id": 531, "name": "Athletic Club"},
                "player": {"id": 182181, "name": "Jesus Areso"},
                "assist": {"id": 344838, "name": "Johaneko Louis-Jean"},
                "type": "subst",
                "detail": "Substitution 1",
                "comments": None,
            },
        ],
    }


def test_build_live_document_normalizes_score_status_and_events() -> None:
    document = live_handler._build_live_document([_live_fixture()])

    assert document["schemaVersion"] == 1
    assert document["generatedAt"].endswith("Z")
    assert document["fixtures"] == [
        {
            "id": "1570373",
            "competitionId": "laliga",
            "statusShort": "2H",
            "elapsed": 78,
            "extra": None,
            "score": {"home": 0, "away": 1},
            "events": [
                {
                    "elapsed": 50,
                    "extra": None,
                    "teamId": "797",
                    "player": "Facundo Buonanotte",
                    "assist": None,
                    "type": "goal",
                    "detail": "Penalty",
                    "comments": None,
                },
                {
                    "elapsed": 56,
                    "extra": None,
                    "teamId": "797",
                    "player": "Federico Redondo Solari",
                    "assist": None,
                    "type": "card",
                    "detail": "Yellow Card",
                    "comments": "Foul",
                },
                {
                    "elapsed": 65,
                    "extra": None,
                    "teamId": "531",
                    "player": "Jesus Areso",
                    "assist": "Johaneko Louis-Jean",
                    "type": "substitution",
                    "detail": "Substitution 1",
                    "comments": None,
                },
            ],
        }
    ]


def test_lambda_handler_fetches_all_leagues_once_and_publishes_live_json(monkeypatch) -> None:
    calls: list[tuple[int, ...]] = []
    puts: list[dict] = []

    class S3:
        def put_object(self, **kwargs) -> None:
            puts.append(kwargs)

    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv("API_FOOTBALL_KEY_PARAMETER_NAME", "/api/key")
    monkeypatch.setattr(live_handler.legacy, "_load_api_key", lambda _name: "secret")
    monkeypatch.setattr(live_handler.legacy, "_s3_client", lambda: S3())

    def fake_fetch_live_fixtures(*, api_key, league_ids):
        assert api_key == "secret"
        calls.append(tuple(league_ids))
        return [_live_fixture()]

    monkeypatch.setattr(live_handler, "fetch_live_fixtures", fake_fetch_live_fixtures)

    result = live_handler.lambda_handler(None, None)

    assert calls == [live_handler.LIVE_LEAGUE_IDS]
    assert result["fixtureCount"] == 1
    assert result["objectKey"] == "data/fixtures/live.json"
    assert len(puts) == 1
    assert puts[0]["Bucket"] == "fixture-bucket"
    assert puts[0]["Key"] == "data/fixtures/live.json"
    assert puts[0]["CacheControl"] == "public, max-age=60"

    body = json.loads(puts[0]["Body"].decode("utf-8"))
    assert body["fixtures"][0]["id"] == "1570373"
