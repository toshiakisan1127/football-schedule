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


def setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv("API_KEY_PARAMETER_NAME", "/football-schedule/kickoff-api-key")
    monkeypatch.setenv("LOOKBACK_DAYS", "1")
    monkeypatch.setenv("LOOKAHEAD_DAYS", "30")
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")


def test_manual_single_competition_only_fetches_and_publishes_that_competition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    fetched: list[str] = []
    published: list[dict] = []

    def fake_fetch(**kwargs) -> list[dict]:
        competition = kwargs["competition"]
        fetched.append(competition.app_id)
        return [raw_fixture(3001)]

    monkeypatch.setattr(handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler({"competitions": ["bundesliga"]}, None)

    assert fetched == ["bundesliga"]
    assert len(published) == 1
    assert published[0]["object_key"] == "data/fixtures/bundesliga.json"
    document = json.loads(published[0]["body"].decode("utf-8"))
    assert document["competition"] == {
        "id": "bundesliga",
        "name": "Bundesliga",
        "country": "Germany",
    }
    assert {fixture["competition"]["id"] for fixture in document["fixtures"]} == {
        "bundesliga"
    }
    assert result["competitions"][0]["competition"] == "bundesliga"


def test_competition_ids_are_deduplicated(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = split_handler._selected_competitions(
        {"competitions": ["laliga", "laliga", "bundesliga"]}
    )
    assert [competition.app_id for competition in selected] == ["laliga", "bundesliga"]


def test_unknown_competition_fails_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    called = False

    def fake_fetch(**kwargs) -> list[dict]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(handler, "_fetch_competition_fixtures", fake_fetch)

    with pytest.raises(handler.FixtureDataError, match="Unknown competition ID"):
        split_handler.lambda_handler({"competitions": ["serie-a"]}, None)

    assert called is False


def test_empty_competition_array_is_rejected() -> None:
    with pytest.raises(handler.FixtureDataError, match="non-empty array"):
        split_handler._selected_competitions({"competitions": []})


def test_scheduler_style_event_refreshes_all_competitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    fetched: list[str] = []
    published: list[dict] = []
    fixture_ids = {
        "epl": 1001,
        "laliga": 2001,
        "bundesliga": 3001,
        "ligue1": 4001,
        "uecl": 5001,
    }

    def fake_fetch(**kwargs) -> list[dict]:
        competition = kwargs["competition"]
        fetched.append(competition.app_id)
        return [raw_fixture(fixture_ids[competition.app_id])]

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler({"source": "aws.scheduler"}, None)

    assert fetched == ["epl", "laliga", "bundesliga", "ligue1", "uecl"]
    assert [item["object_key"] for item in published] == [
        "data/fixtures/premier-league.json",
        "data/fixtures/laliga.json",
        "data/fixtures/bundesliga.json",
        "data/fixtures/ligue1.json",
        "data/fixtures/conference-league.json",
    ]
    assert result["fixtureCount"] == 5


def test_one_competition_failure_does_not_block_other_competition_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    published: list[dict] = []
    fixture_ids = {"epl": 1001, "bundesliga": 3001, "ligue1": 4001, "uecl": 5001}

    def fake_fetch(**kwargs) -> list[dict]:
        competition = kwargs["competition"]
        if competition.app_id == "laliga":
            raise handler.FixtureDataError("provider failed")
        return [raw_fixture(fixture_ids[competition.app_id])]

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    with pytest.raises(handler.FixtureDataError, match="laliga: provider failed"):
        split_handler.lambda_handler({}, None)

    assert [item["object_key"] for item in published] == [
        "data/fixtures/premier-league.json",
        "data/fixtures/bundesliga.json",
        "data/fixtures/ligue1.json",
        "data/fixtures/conference-league.json",
    ]
