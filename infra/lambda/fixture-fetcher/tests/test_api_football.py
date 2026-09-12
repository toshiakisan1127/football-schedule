from __future__ import annotations

from datetime import date

import api_football


def test_j1_season_uses_ending_year_for_autumn_spring_season() -> None:
    assert api_football.j1_season_for(date(2026, 9, 12)) == 2027
    assert api_football.j1_season_for(date(2027, 2, 1)) == 2027


def test_fetch_j1_fixtures_uses_api_football_key_and_paging(monkeypatch) -> None:
    requests: list[dict] = []

    class Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    payloads = [
        {
            "errors": {},
            "paging": {"current": 1, "total": 2},
            "response": [{"fixture": {"id": 1}}],
        },
        {
            "errors": {},
            "paging": {"current": 2, "total": 2},
            "response": [{"fixture": {"id": 2}}],
        },
    ]

    def fake_get(url, *, headers, params, timeout):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
        )
        return Response(payloads[len(requests) - 1])

    monkeypatch.setattr(api_football._http, "get", fake_get)

    fixtures = api_football.fetch_j1_fixtures(
        api_key="pro-secret",
        from_date=date(2026, 9, 12),
        to_date=date(2026, 10, 12),
    )

    assert [fixture["fixture"]["id"] for fixture in fixtures] == [1, 2]
    assert len(requests) == 2
    assert requests[0]["url"] == "https://v3.football.api-sports.io/fixtures"
    assert requests[0]["headers"] == {"x-apisports-key": "pro-secret"}
    assert requests[0]["params"] == {
        "league": 98,
        "season": 2027,
        "from": "2026-09-12",
        "to": "2026-10-12",
        "page": 1,
    }
    assert requests[1]["params"]["page"] == 2


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
