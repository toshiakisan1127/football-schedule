# Football data source

The MVP fetcher reads fixtures from KickoffAPI v2 and publishes the application-owned JSON document consumed by the frontend.

## MVP competitions

- Premier League (`epl` / provider league `en.1`)
- UEFA Champions League (`ucl` / provider league `lg_4WmajCeHmdkK`)
- LaLiga (`laliga` / provider league `es.1`)

J1 League is intentionally excluded for now because KickoffAPI's current J1 catalog data is only available through the 2025 season and a `season=2026` fixture request returned no matches.

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

KickoffAPI v2 production responses currently use a `{ data, meta }` envelope with cursor pagination via `meta.nextCursor`. The fetcher also accepts the page-based v2 envelope described in KickoffAPI's migration documentation.

The provider receives `from` / `to`, but the Lambda also filters normalized fixtures against the configured date window in JST. This prevents out-of-window fixtures from being published if the provider returns a wider season result set.

## Publishing rule

The Lambda builds the complete document in memory first. `data/fixtures.json` is written to S3 only after every configured competition has been fetched, normalized, and filtered successfully. If any competition fails, the previous S3 object is left untouched.

## Score policy

KickoffAPI score data is retained in the JSON even while a match is live. The frontend decides whether to display it. This lets the data layer remain faithful to the provider without showing stale in-progress scores to users.

## Credential

The KickoffAPI key is stored as an SSM SecureString at `/football-schedule/kickoff-api-key`. It is never exposed to the frontend.

## Tests

`pytest` covers status mapping, both observed and documented v2 fixture shapes, UTC conversion, JST date-window filtering, score preservation, season selection, cursor/page pagination, API error handling, and atomic publish behavior.
