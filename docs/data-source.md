# Football data source

The fixture fetcher reads fixtures from KickoffAPI v1 and publishes the application-owned JSON document consumed by the frontend.

## Enabled competitions

- Premier League (`epl` / provider league `39`)
- La Liga (`laliga` / provider league `140`)

UEFA Champions League is intentionally kept out of the current production feed and will be enabled separately after the two domestic leagues are verified in production.

J1 League is intentionally excluded for now because KickoffAPI's current J1 catalog data is only available through the 2025 season and a `season=2026` fixture request returned no matches.

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

KickoffAPI v1 production responses use a `{ response, paging }` envelope. The fetcher requests each configured competition independently with the league ID, season, `from`, and `to` parameters and follows `paging.current` / `paging.total` when multiple pages are returned.

The provider receives `from` / `to`, but the Lambda also filters normalized fixtures against the configured date window in JST. This prevents out-of-window fixtures from being published if the provider returns a wider season result set.

KickoffAPI v1 is deprecated and is scheduled to sunset on 1 January 2027, so a v2 migration remains a future task. For the current MVP, v1 is kept because the Premier League fixture flow has already been verified in production and La Liga uses the same response contract.

## Publishing rule

The Lambda builds the complete document in memory first. Before `data/fixtures.json` is written to S3, the application-owned document is validated as schema version `1`.

Validation covers the document range and timestamps, configured competition IDs, fixture/team identifiers and names, duplicate fixture IDs, home/away consistency, supported statuses, non-negative scores, JST range membership, and fixture ordering. If fetching, normalization, or validation fails, S3 is not updated and the previous known-good object remains available to the frontend.

The frontend therefore consumes the S3 document as the validated read model and does not need to understand KickoffAPI's provider-specific response shape.

## Score policy

KickoffAPI score data is retained in the JSON even while a match is live. The frontend decides whether to display it. This lets the data layer remain faithful to the provider without showing stale in-progress scores to users.

## Credential

The KickoffAPI key is stored as an SSM SecureString at `/football-schedule/kickoff-api-key`. It is never exposed to the frontend.

## Tests

`pytest` covers configured competition mappings, status mapping, observed/documented v1 fixture shapes, UTC conversion, JST date-window filtering, score preservation, season selection, v1 pagination, API error handling, application document validation, and atomic multi-competition publishing.
