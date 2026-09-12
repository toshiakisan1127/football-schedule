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
    monkeypatch.setenv(
        "API_FOOTBALL_KEY_PARAMETER_NAME",
        "/football-schedule/api-football-pro-key",
    )
    monkeypatch.setenv("LOOKBACK_DAYS", "1")
    monkeypatch.setenv("LOOKAHEAD_DAYS", "21")
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")


def test_manual_single_competition_only_fetches_and_publishes_that_competition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    fetched: list[dict] = []
    published: list[dict] = []

    def fake_fetch(**kwargs) -> list[dict]:
        fetched.append(kwargs)
        return [raw_fixture(3001)]

    monkeypatch.setattr(split_handler, "fetch_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler({"competitions": ["bundesliga"]}, None)

    assert len(fetched) == 1
    assert fetched[0]["league_id"] == 78
    assert fetched[0]["competition_label"] == "Bundesliga"
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


@pytest.mark.parametrize(
    ("competition_id", "league_id", "competition_label"),
    [
        ("epl", 39, "Premier League"),
        ("laliga", 140, "La Liga"),
        ("bundesliga", 78, "Bundesliga"),
        ("ligue1", 61, "Ligue 1"),
        ("ucl", 2, "UEFA Champions League"),
        ("uel", 3, "UEFA Europa League"),
        ("uecl", 848, "UEFA Conference League"),
    ],
)
def test_european_competitions_use_api_football_league_ids(
    monkeypatch: pytest.MonkeyPatch,
    competition_id: str,
    league_id: int,
    competition_label: str,
) -> None:
    calls: list[dict] = []

    def fake_fetch(**kwargs) -> list[dict]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr(split_handler, "fetch_fixtures", fake_fetch)
    competition = next(
        competition
        for competition in split_handler.COMPETITIONS
        if competition.app_id == competition_id
    )

    fixtures = split_handler._fetch_competition_fixtures(
        api_key="secret",
        competition=competition,
        season=2026,
        from_date=handler.date(2026, 9, 13),
        to_date=handler.date(2026, 10, 4),
    )

    assert fixtures == []
    assert len(calls) == 1
    assert calls[0]["league_id"] == league_id
    assert calls[0]["competition_label"] == competition_label
    assert calls[0]["season"] == 2026


@pytest.mark.parametrize(
    ("competition_id", "expected_span_days"),
    [
        ("laliga", 22),
        ("j1", 22),
        ("ucl", 36),
        ("uel", 36),
        ("uecl", 36),
    ],
)
def test_competition_type_controls_fixture_window(
    monkeypatch: pytest.MonkeyPatch,
    competition_id: str,
    expected_span_days: int,
) -> None:
    setup_env(monkeypatch)
    calls: list[dict] = []

    def fake_fetch(**kwargs) -> list[dict]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: None)

    split_handler.lambda_handler({"competitions": [competition_id]}, None)

    assert len(calls) == 1
    assert (calls[0]["to_date"] - calls[0]["from_date"]).days == expected_span_days


def test_manual_j1_only_uses_api_football_and_publishes_j1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    fetched: list[dict] = []
    published: list[dict] = []

    def fake_fetch_j1(**kwargs) -> list[dict]:
        fetched.append(kwargs)
        return [
            {
                "fixture": {
                    "id": 1556067,
                    "date": "2026-09-13T09:30:00+00:00",
                    "status": {"long": "Not Started", "short": "NS"},
                },
                "teams": {
                    "home": {
                        "id": 287,
                        "name": "Urawa",
                        "logo": "https://media.api-sports.io/football/teams/287.png",
                    },
                    "away": {
                        "id": 310,
                        "name": "Fagiano Okayama",
                        "logo": "https://media.api-sports.io/football/teams/310.png",
                    },
                },
                "goals": {"home": None, "away": None},
            }
        ]

    monkeypatch.setattr(split_handler, "fetch_j1_fixtures", fake_fetch_j1)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler({"competitions": ["j1"]}, None)

    assert len(fetched) == 1
    assert fetched[0]["api_key"] == "secret"
    assert len(published) == 1
    assert published[0]["object_key"] == "data/fixtures/j1.json"
    document = json.loads(published[0]["body"].decode("utf-8"))
    assert document["competition"] == {
        "id": "j1",
        "name": "J1 League",
        "country": "Japan",
    }
    assert document["fixtures"][0]["home"]["logo"] == (
        "https://media.api-sports.io/football/teams/287.png"
    )
    assert document["fixtures"][0]["away"]["logo"] == (
        "https://media.api-sports.io/football/teams/310.png"
    )
    assert document["fixtures"][0]["kickoff"] == "2026-09-13T09:30:00Z"
    assert result["competitions"][0]["competition"] == "j1"


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

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)

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
        "j1": 5001,
        "ucl": 6001,
        "uel": 7001,
        "uecl": 8001,
    }

    def fake_fetch(**kwargs) -> list[dict]:
        competition = kwargs["competition"]
        fetched.append(competition.app_id)
        return [raw_fixture(fixture_ids[competition.app_id])]

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = split_handler.lambda_handler({"source": "aws.scheduler"}, None)

    assert fetched == ["epl", "laliga", "bundesliga", "ligue1", "j1", "ucl", "uel", "uecl"]
    assert [item["object_key"] for item in published] == [
        "data/fixtures/premier-league.json",
        "data/fixtures/laliga.json",
        "data/fixtures/bundesliga.json",
        "data/fixtures/ligue1.json",
        "data/fixtures/j1.json",
        "data/fixtures/champions-league.json",
        "data/fixtures/europa-league.json",
        "data/fixtures/conference-league.json",
    ]
    assert result["fixtureCount"] == 8


def test_one_competition_failure_does_not_block_other_competition_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_env(monkeypatch)
    published: list[dict] = []
    fixture_ids = {
        "epl": 1001,
        "bundesliga": 3001,
        "ligue1": 4001,
        "j1": 5001,
        "ucl": 6001,
        "uel": 7001,
        "uecl": 8001,
    }

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
        "data/fixtures/j1.json",
        "data/fixtures/champions-league.json",
        "data/fixtures/europa-league.json",
        "data/fixtures/conference-league.json",
    ]


def test_failure_summary_emits_one_error_log(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    setup_env(monkeypatch)

    class Response:
        status_code = 429

    class RateLimitError(Exception):
        response = Response()

    def fake_fetch(**kwargs) -> list[dict]:
        raise RateLimitError("429 Too Many Requests")

    monkeypatch.setattr(split_handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: None)

    class Context:
        aws_request_id = "request-123"

    with caplog.at_level("ERROR"):
        with pytest.raises(handler.FixtureDataError):
            split_handler.lambda_handler({}, Context())

    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    payload = json.loads(error_records[0].message)
    assert payload["failureCount"] == 8
    assert payload["failedCompetitions"] == [
        "epl",
        "laliga",
        "bundesliga",
        "ligue1",
        "j1",
        "ucl",
        "uel",
        "uecl",
    ]
    assert payload["provider"] == "API-Football"
    assert payload["primaryCause"] == "API-Football rate limit exceeded (HTTP 429)"
    assert payload["requestId"] == "request-123"
