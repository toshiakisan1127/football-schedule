from __future__ import annotations

import json
from datetime import date

import pytest

import handler


def raw_fixture(
    *,
    fixture_id: int = 1001,
    kickoff: str = "2026-09-12T06:00:00.000Z",
    status: str = "NS",
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff,
            "status": {
                "long": "Not Started" if status == "NS" else "Match Finished",
                "short": status,
                "elapsed": None,
            },
        },
        "league": {
            "id": 39,
            "name": "Premier League",
            "season": 2026,
        },
        "teams": {
            "home": {"id": 40, "name": "Home FC"},
            "away": {"id": 33, "name": "Away FC"},
        },
        "goals": {
            "home": home_goals,
            "away": away_goals,
        },
    }


def raw_v2_fixture(
    *,
    fixture_id: str,
    kickoff: str,
    time: str | None,
    home_id: str | None = "tm_home",
    away_id: str | None = "tm_away",
) -> dict:
    return {
        "id": fixture_id,
        "date": kickoff,
        "time": time,
        "status": {"long": "Not Started", "short": "NS", "elapsed": None},
        "league": {"id": "lg_laliga", "name": "La Liga", "season": 2026},
        "home": {"id": home_id, "name": "Sevilla FC"},
        "away": {"id": away_id, "name": "Valencia CF"},
        "score": None,
        "round": "Matchday 5",
        "source": "owned",
    }


def competition() -> handler.Competition:
    return handler.COMPETITIONS[0]


def test_mvp_fetches_premier_league_and_laliga() -> None:
    assert [
        (item.app_id, item.api_league_id, item.name, item.country)
        for item in handler.COMPETITIONS
    ] == [
        ("epl", 39, "Premier League", "England"),
        ("laliga", 140, "La Liga", "Spain"),
    ]
    assert handler.LALIGA_V2_LEAGUE_ID == "es.1"


@pytest.mark.parametrize(
    ("api_status", "expected"),
    [
        ("NS", "scheduled"),
        ("scheduled", "scheduled"),
        ("1H", "live"),
        ("live", "live"),
        ("FT", "finished"),
        ("finished", "finished"),
        ("PST", "postponed"),
        ("postponed", "postponed"),
        ("CANC", "cancelled"),
        ("cancelled", "cancelled"),
    ],
)
def test_normalize_status(api_status: str, expected: str) -> None:
    assert handler._normalize_status(api_status) == expected


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(handler.FixtureDataError, match="Unknown KickoffAPI fixture status"):
        handler._normalize_status("SOMETHING_NEW")


def test_normalize_fixture_uses_documented_v1_shape() -> None:
    normalized = handler._normalize_fixture(raw_fixture(), competition())

    assert normalized == {
        "id": "1001",
        "competition": {
            "id": "epl",
            "name": "Premier League",
            "country": "England",
        },
        "home": {"id": "40", "name": "Home FC"},
        "away": {"id": "33", "name": "Away FC"},
        "kickoff": "2026-09-12T06:00:00Z",
        "status": "scheduled",
        "score": None,
    }


def test_normalize_fixture_accepts_flat_v1_docs_example() -> None:
    normalized = handler._normalize_fixture(
        {
            "id": 1035039,
            "date": "2026-09-12T15:00:00+09:00",
            "statusShort": "FT",
            "homeTeam": {"id": 40, "name": "Burnley", "goals": 0},
            "awayTeam": {"id": 50, "name": "Manchester City", "goals": 3},
        },
        competition(),
    )

    assert normalized["kickoff"] == "2026-09-12T06:00:00Z"
    assert normalized["status"] == "finished"
    assert normalized["score"] == {"home": 0, "away": 3}


def test_normalize_fixture_accepts_v2_score_shape() -> None:
    raw = raw_v2_fixture(
        fixture_id="fx_1",
        kickoff="2026-09-11T19:00:00Z",
        time=None,
    )
    raw["score"] = {"home": 2, "away": 1}

    normalized = handler._normalize_fixture(raw, handler.COMPETITIONS[1])

    assert normalized["kickoff"] == "2026-09-11T19:00:00Z"
    assert normalized["status"] == "scheduled"
    assert normalized["score"] == {"home": 2, "away": 1}


def test_live_score_is_preserved_in_json_data() -> None:
    normalized = handler._normalize_fixture(
        raw_fixture(status="2H", home_goals=2, away_goals=1),
        competition(),
    )

    assert normalized["status"] == "live"
    assert normalized["score"] == {"home": 2, "away": 1}


@pytest.mark.parametrize(
    ("kickoff", "expected"),
    [
        ("2026-09-09T14:59:59Z", False),
        ("2026-09-09T15:00:00Z", True),
        ("2026-10-11T14:59:59Z", True),
        ("2026-10-11T15:00:00Z", False),
    ],
)
def test_fixture_window_is_evaluated_in_jst(kickoff: str, expected: bool) -> None:
    fixture = {"kickoff": kickoff}
    assert (
        handler._fixture_in_window(
            fixture,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )
        is expected
    )


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


def test_fetch_competition_fixtures_uses_v1_range_and_paging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_get_api_json(path: str, *, api_key: str, params: dict) -> dict:
        calls.append({"path": path, "api_key": api_key, "params": params.copy()})
        page = params.get("page", 1)
        return {
            "response": [raw_fixture(fixture_id=page)],
            "results": 1,
            "paging": {"current": page, "total": 2},
        }

    monkeypatch.setattr(handler, "_get_api_json", fake_get_api_json)

    fixtures = handler._fetch_competition_fixtures(
        api_key="secret",
        competition=competition(),
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert [item["fixture"]["id"] for item in fixtures] == [1, 2]
    assert [call["path"] for call in calls] == [
        "/api/v1/fixtures",
        "/api/v1/fixtures",
    ]
    assert calls[0]["params"] == {
        "league": 39,
        "season": 2026,
        "from": "2026-09-10",
        "to": "2026-10-11",
    }
    assert calls[1]["params"]["page"] == 2


def test_fetch_competition_fixtures_uses_laliga_v2_cursor_paging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_get_api_json(path: str, *, api_key: str, params: dict) -> dict:
        calls.append({"path": path, "api_key": api_key, "params": params.copy()})
        if "cursor" not in params:
            return {
                "data": [
                    raw_v2_fixture(
                        fixture_id="fx_canonical",
                        kickoff="2026-09-11T19:00:00.000Z",
                        time=None,
                        away_id=None,
                    )
                ],
                "meta": {"count": 1, "cursor": 0, "nextCursor": "200"},
            }
        return {
            "data": [
                raw_v2_fixture(
                    fixture_id="fx_wall_clock",
                    kickoff="2026-09-11T21:00:00.000Z",
                    time="21:00",
                    away_id="tm_valencia",
                )
            ],
            "meta": {"count": 1, "cursor": 200, "nextCursor": None},
        }

    monkeypatch.setattr(handler, "_get_api_json", fake_get_api_json)

    fixtures = handler._fetch_competition_fixtures(
        api_key="secret",
        competition=handler.COMPETITIONS[1],
        season=2026,
        from_date=date(2026, 9, 10),
        to_date=date(2026, 10, 11),
    )

    assert len(fixtures) == 1
    assert fixtures[0]["id"] == "fx_canonical"
    assert fixtures[0]["away"]["id"] == "tm_valencia"
    assert [call["path"] for call in calls] == ["/api/v2/fixtures", "/api/v2/fixtures"]
    assert calls[0]["params"] == {"league": "es.1", "season": 2026}
    assert calls[1]["params"] == {"league": "es.1", "season": 2026, "cursor": "200"}


def test_fetch_competition_fixtures_rejects_missing_v1_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        handler,
        "_get_api_json",
        lambda *args, **kwargs: {"results": 0, "paging": {"current": 1, "total": 1}},
    )

    with pytest.raises(handler.FixtureDataError, match="missing a response list"):
        handler._fetch_competition_fixtures(
            api_key="secret",
            competition=competition(),
            season=2026,
            from_date=date(2026, 9, 10),
            to_date=date(2026, 10, 11),
        )


def test_api_uses_kickoff_header_and_rejects_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"error": "rate limit"}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(handler._http, "get", fake_get)

    with pytest.raises(handler.FixtureDataError, match="KickoffAPI returned errors"):
        handler._get_api_json("/api/v1/fixtures", api_key="secret", params={})

    assert captured["headers"] == {"x-api-key": "secret"}


def test_lambda_does_not_publish_when_a_competition_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv(
        "API_KEY_PARAMETER_NAME",
        "/football-schedule/kickoff-api-key",
    )
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")

    def fake_fetch(**kwargs) -> list[dict]:
        raise handler.FixtureDataError("Competition fetch failed")

    published: list[dict] = []
    monkeypatch.setattr(handler, "_fetch_competition_fixtures", fake_fetch)
    monkeypatch.setattr(handler, "_publish_document", lambda **kwargs: published.append(kwargs))

    with pytest.raises(handler.FixtureDataError, match="Competition fetch failed"):
        handler.lambda_handler({}, None)

    assert published == []


def test_lambda_publishes_once_after_all_competitions_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_BUCKET_NAME", "fixture-bucket")
    monkeypatch.setenv(
        "API_KEY_PARAMETER_NAME",
        "/football-schedule/kickoff-api-key",
    )
    monkeypatch.setattr(handler, "_load_api_key", lambda _: "secret")

    def fake_fetch(**kwargs) -> list[dict]:
        current_competition = kwargs["competition"]
        fixture_id = 1001 if current_competition.app_id == "epl" else 2001
        return [
            raw_fixture(
                fixture_id=fixture_id,
                kickoff="2026-09-12T06:00:00Z",
                status="FT",
                home_goals=2,
                away_goals=1,
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
    assert {fixture["competition"]["id"] for fixture in body["fixtures"]} == {
        "epl",
        "laliga",
    }
    assert all(fixture["score"] is not None for fixture in body["fixtures"])
    assert body["range"]["from"] <= body["range"]["to"]
