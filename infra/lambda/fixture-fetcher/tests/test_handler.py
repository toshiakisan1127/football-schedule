from __future__ import annotations

import json
from datetime import date

import pytest

import handler


def raw_fixture(
    *,
    fixture_id: int = 1001,
    kickoff: str = "2026-09-12T15:00:00+09:00",
    status: str = "NS",
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff,
            "status": {"short": status},
        },
        "teams": {
            "home": {"id": 10, "name": "Home FC"},
            "away": {"id": 20, "name": "Away FC"},
        },
        "goals": {
            "home": home_goals,
            "away": away_goals,
        },
    }


def competition(app_id: str = "epl") -> handler.Competition:
    if app_id == "epl":
        return handler.Competition("epl", 39, "Premier League", "England")
    return handler.Competition("j1", 98, "J1 League", "Japan")


def test_mvp_has_only_premier_league_and_j1() -> None:
    assert [item.app_id for item in handler.COMPETITIONS] == ["epl", "j1"]


@pytest.mark.parametrize(
    ("api_status", "expected"),
    [
        ("NS", "scheduled"),
        ("1H", "live"),
        ("FT", "finished"),
        ("PST", "postponed"),
        ("CANC", "cancelled"),
    ],
)
def test_normalize_status(api_status: str, expected: str) -> None:
    assert handler._normalize_status(api_status) == expected


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(handler.FixtureDataError, match="Unknown API-Football fixture status"):
        handler._normalize_status("SOMETHING_NEW")


def test_normalize_fixture_converts_kickoff_to_utc() -> None:
    normalized = handler._normalize_fixture(raw_fixture(), competition())

    assert normalized == {
        "id": "1001",
        "competition": {
            "id": "epl",
            "name": "Premier League",
            "country": "England",
        },
        "home": {"id": "10", "name": "Home FC"},
        "away": {"id": "20", "name": "Away FC"},
        "kickoff": "2026-09-12T06:00:00Z",
        "status": "scheduled",
        "score": None,
    }


def test_live_score_is_preserved_in_json_data() -> None:
    normalized = handler._normalize_fixture(
        raw_fixture(status="2H", home_goals=2, away_goals=1),
        competition("j1"),
    )

    assert normalized["status"] == "live"
    assert normalized["score"] == {"home": 2, "away": 1}


def test_finished_score_is_preserved() -> None:
    normalized = handler._normalize_fixture(
        raw_fixture(status="FT", home_goals=3, away_goals=2),
        competition(),
    )

    assert normalized["status"] == "finished"
    assert normalized["score"] == {"home": 3, "away": 2}


@pytest.mark.parametrize(
    ("reference_date", "expected_season"),
    [
        (date(2026, 7, 1), 2026),
        (date(2026, 9, 11), 2026),
        (date(2027, 1, 15), 2026),
        (date(2027, 7, 1), 2027),
    ],
)
def test_season_uses_start_year(reference_date: date, expected_season: int) -> None:
    assert handler._season_for(reference_date) == expected_season


def test_fetch_competition_fixtures_follows_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_get_api_json(path: str, *, api_key: str, params: dict) -> dict:
        calls.append({"path": path, "api_key": api_key, "params": params.copy()})
        page = params["page"]
        return {
            "errors": [],
            "paging": {"current": page, "total": 2},
            "response": [raw_fixture(fixture_id=1000 + page)],
        }

    monkeypatch.setattr(handler, "_get_api_json", fake_get_api_json)

    fixtures = handler._fetch_competition_fixtures(
        api_key="secret",
        competition=competition(),
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert [item["fixture"]["id"] for item in fixtures] == [1001, 1002]
    assert [call["params"]["page"] for call in calls] == [1, 2]
    assert all(call["params"]["league"] == 39 for call in calls)
    assert all(call["params"]["season"] == 2026 for call in calls)
    assert all(call["params"]["timezone"] == "Asia/Tokyo" for call in calls)


def test_api_errors_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"errors": {"rateLimit": "Too many requests"}, "response": []}

    monkeypatch.setattr(handler._http, "get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(handler.FixtureDataError, match="API-Football returned errors"):
        handler._get_api_json("/fixtures", api_key="secret", params={})


def test_lambda_does_not_publish_when_one_competition_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv("API_KEY_PARAMETER_NAME", "/football-schedule/api-football-key")
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")

    def fake_fetch(*, competition: handler.Competition, **kwargs) -> list[dict]:
        if competition.app_id == "epl":
            return [raw_fixture()]
        raise handler.FixtureDataError("J1 fetch failed")

    published: list[dict] = []
    monkeypatch.setattr(handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    with pytest.raises(handler.FixtureDataError, match="J1 fetch failed"):
        handler.lambda_handler({}, None)

    assert published == []


def test_lambda_publishes_once_after_both_competitions_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv("API_KEY_PARAMETER_NAME", "/football-schedule/api-football-key")
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")

    def fake_fetch(*, competition: handler.Competition, **kwargs) -> list[dict]:
        status = "FT" if competition.app_id == "epl" else "1H"
        score = (2, 1) if competition.app_id == "epl" else (0, 0)
        fixture_id = 2001 if competition.app_id == "epl" else 2002
        return [
            raw_fixture(
                fixture_id=fixture_id,
                status=status,
                home_goals=score[0],
                away_goals=score[1],
            )
        ]

    published: list[dict] = []
    monkeypatch.setattr(handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    result = handler.lambda_handler({}, None)

    assert result["ok"] is True
    assert result["published"] is True
    assert result["fixtureCount"] == 2
    assert len(published) == 1

    body = json.loads(published[0]["body"].decode("utf-8"))
    assert {fixture["competition"]["id"] for fixture in body["fixtures"]} == {"epl", "j1"}
    assert body["fixtures"][0]["score"] is not None
    assert body["range"]["from"] <= body["range"]["to"]
