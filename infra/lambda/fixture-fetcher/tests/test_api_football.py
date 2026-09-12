from __future__ import annotations

from datetime import date

import api_football


def test_j1_season_uses_ending_year_for_autumn_spring_season() -> None:
    assert api_football.j1_season_for(date(2026, 9, 12)) == 2027
    assert api_football.j1_season_for(date(2027, 2, 1)) == 2027


def test_fetch_premier_league_fixtures_uses_league_39_and_requested_season(monkeypatch) -> None:
    requests: list[dict] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "errors": [],
                "paging": {"current": 1, "total": 1},
                "response": [{"fixture": {"id": 1557409}}],
            }

    def fake_get(url, *, headers, params, timeout):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
        )
        return Response()

    monkeypatch.setattr(api_football._http, "get", fake_get)

    fixtures = api_football.fetch_premier_league_fixtures(
        api_key="pro-secret",
        season=2026,
        from_date=date(2026, 9, 13),
        to_date=date(2026, 10, 13),
    )

    assert [fixture["fixture"]["id"] for fixture in fixtures] == [1557409]
    assert len(requests) == 1
    assert requests[0]["url"] == "https://v3.football.api-sports.io/fixtures"
    assert requests[0]["headers"] == {"x-apisports-key": "pro-secret"}
    assert requests[0]["params"] == {
        "league": 39,
        "season": 2026,
        "from": "2026-09-13",
        "to": "2026-10-13",
    }


def test_fetch_live_fixtures_batches_all_supported_leagues(monkeypatch) -> None:
    requests: list[dict] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "errors": [],
                "paging": {"current": 1, "total": 1},
                "response": [{"fixture": {"id": 1557406}}],
            }

    def fake_get(url, *, headers, params, timeout):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
        )
        return Response()

    monkeypatch.setattr(api_football._http, "get", fake_get)

    fixtures = api_football.fetch_live_fixtures(api_key="pro-secret")

    assert [fixture["fixture"]["id"] for fixture in fixtures] == [1557406]
    assert len(requests) == 1
    assert requests[0]["url"] == "https://v3.football.api-sports.io/fixtures"
    assert requests[0]["headers"] == {"x-apisports-key": "pro-secret"}
    assert requests[0]["params"] == {
        "live": "39-140-78-61-98-2-3-848",
        "timezone": "Asia/Tokyo",
    }


def test_fetch_j1_fixtures_uses_api_football_key_and_range_without_page(monkeypatch) -> None:
    requests: list[dict] = []

    class Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    payload = {
        "errors": {},
        "paging": {"current": 1, "total": 2},
        "response": [
            {"fixture": {"id": 1}},
            {"fixture": {"id": 2}},
        ],
    }

    def fake_get(url, *, headers, params, timeout):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
        )
        return Response(payload)

    monkeypatch.setattr(api_football._http, "get", fake_get)

    fixtures = api_football.fetch_j1_fixtures(
        api_key="pro-secret",
        from_date=date(2026, 9, 12),
        to_date=date(2026, 10, 12),
    )

    assert [fixture["fixture"]["id"] for fixture in fixtures] == [1, 2]
    assert len(requests) == 1
    assert requests[0]["url"] == "https://v3.football.api-sports.io/fixtures"
    assert requests[0]["headers"] == {"x-apisports-key": "pro-secret"}
    assert requests[0]["params"] == {
        "league": 98,
        "season": 2027,
        "from": "2026-09-12",
        "to": "2026-10-12",
    }


def test_fetch_j1_fixtures_rejects_api_errors(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "errors": {"plan": "season unavailable"},
                "paging": {"current": 1, "total": 1},
                "response": [],
            }

    monkeypatch.setattr(api_football._http, "get", lambda *args, **kwargs: Response())

    try:
        api_football.fetch_j1_fixtures(
            api_key="pro-secret",
            from_date=date(2026, 9, 12),
            to_date=date(2026, 10, 12),
        )
    except api_football.ApiFootballError as exc:
        assert "season unavailable" in str(exc)
    else:
        raise AssertionError("expected ApiFootballError")
