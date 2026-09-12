# API-Football J1 validation

This document records the investigation that led to using API-Football for J1 League fixtures. The goal is to keep the provider decision reproducible and to preserve the actual request patterns and observed responses.

Validation date: 2026-09-12 JST.

## 1. Discover J1 League and available seasons

The API does not allow `country` and `search` together, and `search` requires at least three characters. The initial request using both parameters failed with:

```json
{
  "get": "leagues",
  "parameters": {
    "country": "Japan",
    "search": "J1"
  },
  "errors": {
    "country": "The Country field cannot be used with the Search field.",
    "search": "The Search field must be at least 3 characters in length."
  },
  "results": 0,
  "paging": {
    "current": 1,
    "total": 1
  },
  "response": []
}
```

The working discovery request was therefore limited to Japan and filtered locally with `jq`:

```bash
curl -sS -G \
  -H "x-apisports-key: $API_FOOTBALL_KEY" \
  --data-urlencode "country=Japan" \
  "https://v3.football.api-sports.io/leagues" \
  | jq '.response[] | select(
      (.league.name | ascii_downcase | contains("j1"))
      or (.league.name | ascii_downcase | contains("j league"))
    )'
```

Observed J1 mapping:

- API-Football league ID: `98`
- Current API-Football season: `2027`
- Season range: `2026-08-07` through `2027-06-06`
- `current: true`
- fixture coverage is enabled

The API represents the 2026/27 J1 season as `season=2027`.

## 2. Free plan restriction

The fixture request itself was valid, but the Free plan could not access the current J1 season:

```bash
curl -sS -G \
  -H "x-apisports-key: $API_FOOTBALL_KEY" \
  --data-urlencode "league=98" \
  --data-urlencode "season=2027" \
  --data-urlencode "from=2026-09-13" \
  --data-urlencode "to=2026-10-12" \
  "https://v3.football.api-sports.io/fixtures" \
  | jq '.'
```

Observed Free-plan response:

```json
{
  "get": "fixtures",
  "parameters": {
    "league": "98",
    "season": "2027",
    "from": "2026-09-13",
    "to": "2026-10-12"
  },
  "errors": {
    "plan": "Free plans do not have access to this season, try from 2022 to 2024."
  },
  "results": 0,
  "paging": {
    "current": 1,
    "total": 1
  },
  "response": []
}
```

Conclusion: competition metadata is visible on Free, but current-season fixture data is plan-restricted.

## 3. Pro plan validation

After upgrading to Pro, the same request succeeded and returned 22 future J1 fixtures for the requested window.

The response shape includes the data needed by the application without additional logo requests:

```json
{
  "fixture": {
    "id": 1556067,
    "date": "2026-09-13T09:30:00+00:00",
    "timestamp": 1789291800,
    "venue": {
      "id": null,
      "name": "Saitama Stadium",
      "city": "Saitama"
    },
    "status": {
      "long": "Not Started",
      "short": "NS"
    }
  },
  "league": {
    "id": 98,
    "name": "J1 League",
    "country": "Japan",
    "logo": "https://media.api-sports.io/football/leagues/98.png",
    "flag": "https://media.api-sports.io/flags/jp.svg",
    "season": 2027,
    "round": "Regular Season - 7"
  },
  "teams": {
    "home": {
      "id": 287,
      "name": "Urawa",
      "logo": "https://media.api-sports.io/football/teams/287.png",
      "winner": null
    },
    "away": {
      "id": 310,
      "name": "Fagiano Okayama",
      "logo": "https://media.api-sports.io/football/teams/310.png",
      "winner": null
    }
  },
  "goals": {
    "home": null,
    "away": null
  }
}
```

Useful fields for the current product:

- `fixture.id`
- `fixture.date`
- `fixture.status`
- `teams.home.id`, `name`, `logo`
- `teams.away.id`, `name`, `logo`
- `goals.home`, `goals.away`
- `league.round` for potential future use

The fixture response already carries team-logo URLs, so J1 does not require a second API call just to resolve logos.

## 4. Kickoff-time spot checks

Several fixtures that had been problematic with alternative sources were spot-checked against the API-Football Pro response:

| Fixture | API-Football UTC | JST | Expected |
| --- | --- | --- | --- |
| Kawasaki Frontale vs Kashima Antlers | 2026-09-19 09:00 UTC | 2026-09-19 18:00 JST | 18:00 JST |
| Kyoto Sanga vs Machida Zelvia | 2026-10-10 10:00 UTC | 2026-10-10 19:00 JST | 19:00 JST |
| Kashima Antlers vs Gamba Osaka | 2026-10-09 10:00 UTC | 2026-10-09 19:00 JST | 19:00 JST |

These spot checks matched the expected kickoff times and dates.

## 5. Data-quality caveat

Venue data is not currently consumed by the application. During validation, at least one venue value looked inconsistent with the fixture, so the production integration intentionally relies on fixture date/status, teams, logos, and scores only.

If venue display is added later, venue data must be validated independently before exposing it to users.

## 6. Implementation decision

For the initial J1 rollout:

- Provider: API-Football v3
- League: `98`
- 2026/27 season: `2027`
- Credential: SSM SecureString `/football-schedule/api-football-pro-key`
- Output: normalized app-owned schema in `data/fixtures/j1.json`
- Refresh cadence: same daily batch as the other competitions
- Fixture request: one `from` / `to` request without `page`
- Existing European competitions remain on KickoffAPI for this PR

The provider code is kept isolated so other competitions can be migrated to API-Football later without changing the frontend contract.

## 7. First deployed request failure: unsupported `page`

On 2026-09-13 JST, the first manual J1-only Lambda test failed before publishing. The provider returned an API error indicating that the `page` field does not exist for the fixtures endpoint.

The deployed adapter had assumed generic API pagination and sent `page=1`, even though the successful validation curl had not used that parameter. This was a regression introduced by the adapter, not an API key or plan problem.

Correction:

- remove `page` from `/fixtures` parameters,
- remove the paging loop for J1,
- fetch the configured date range once,
- keep the response `paging` object informational only,
- add a regression test asserting that the J1 request contains only `league`, `season`, `from`, and `to`.

This incident is why the J1 adapter intentionally does not share generic pagination behavior with other provider endpoints.
