from __future__ import annotations

import json

import pytest

import handler
import split_handler


def raw_fixture(fixture_id: int) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": "2026-09-12T06:00:00Z",
            "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        },
        "teams": {
            "home": {"id": 40, "name": "Home FC"},
            "away": {"id": 33, "name": "Away FC"},
        },
        "goals": {"home": None, "away": None},
    }


def configure_lambda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv(
        "API_FOOTBALL_KEY_PARAMETER_NAME",
        "/football-schedule/api-football-pro-key",
    )
    monkeypatch.setattr(split_handler, "_load_api_football_key", lambda: "secret")


def test_lambda_does_not_publish_when_document_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_lambda(monkeypatch)
    monkeypatch.setattr(
        split_handler,
        "_fetch_competition_fixtures",
        lambda **kwargs: [raw_fixture(1001), raw_fixture(1001)],
    )
    published: list[dict] = []
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    with pytest.raises(handler.FixtureDataError, match="duplicate fixture id"):
        split_handler.lambda_handler({"competitions": ["epl"]}, None)

    assert published == []


def test_lambda_publishes_schema_version_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_lambda(monkeypatch)

    fixture_ids = {"epl": 1001, "laliga": 2001, "bundesliga": 3001}

    def fake_fetch(**kwargs) -> list[dict]:
        return [raw_fixture(fixture_ids[kwargs["competition"].app_id])]

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    published: list[dict] = []
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler(
        {"competitions": ["epl", "laliga", "bundesliga"]},
        None,
    )
    documents = [json.loads(item["body"].decode("utf-8")) for item in published]

    assert result["schemaVersion"] == 1
    assert len(published) == 3
    assert all(document["schemaVersion"] == 1 for document in documents)
