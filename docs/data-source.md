# Football data source

The fixture fetcher publishes the application-owned JSON document consumed by the frontend. Provider handling is competition-specific because the currently observed KickoffAPI v1 and v2 behavior differs by league.

## Enabled competitions

- Premier League (`epl` / KickoffAPI v1 league `39`)
- La Liga (`laliga` / KickoffAPI v2 league `es.1`)

UEFA Champions League is intentionally kept out of the current production feed and will be enabled separately after the two domestic leagues are verified in production.

J1 League is intentionally excluded for now because KickoffAPI's current J1 catalog data is only available through the 2025 season and a `season=2026` fixture request returned no matches.

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

### Premier League

Premier League stays on KickoffAPI v1. The fetcher requests league `39` with season, `from`, and `to`, and follows `paging.current` / `paging.total` when multiple pages are returned.

v1 is deprecated and is scheduled to sunset on 1 January 2027, so this is a temporary compatibility choice while the v2 feed is not yet reliable enough to replace it safely.

### La Liga

La Liga uses KickoffAPI v2 with league `es.1` because the v1 feed did not expose the full one-month future window. In the 2026-09-11 validation, a v1 request through 2026-10-11 returned only 29 rows and stopped at 2026-09-20.

The v2 feed contains the later fixtures but also exposes multiple rows for the same home/away/Matchday combination. The Lambda therefore:

1. fetches v2 pages by following `meta.nextCursor`,
2. groups rows by home team, away team, and Matchday,
3. selects the canonical UTC record only when it has the verified `Europe/Madrid` wall-clock sibling pattern,
4. fails closed if a relevant group resolves to zero or multiple canonical rows,
5. normalizes the selected rows into the app-owned schema,
6. applies the JST publication-window filter.

The selection rule was cross-checked against all 24 v1 fixtures available in the validation window and selected the exact v1 kickoff for 24/24 fixtures with zero wrong or ambiguous selections. See [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md) for the observations, rejected heuristics, validation output, and regression strategy.

## Publication window

The Lambda publishes from the configured lookback through lookahead window, currently one day back through 30 days ahead.

Provider-side range behavior is not trusted as the final boundary. Premier League v1 receives `from` / `to`; La Liga v2 is fetched using cursor pagination because its observed response ignored the requested date range. In both cases the Lambda filters normalized fixtures against the configured date window in JST before publishing.

## Publishing rule

The Lambda builds the complete document in memory first. Before `data/fixtures.json` is written to S3, the application-owned document is validated as schema version `1`.

Validation covers the document range and timestamps, configured competition IDs, fixture/team identifiers and names, duplicate fixture IDs, home/away consistency, supported statuses, non-negative scores, JST range membership, and fixture ordering. If fetching, provider-specific canonical selection, normalization, or validation fails, S3 is not updated and the previous known-good object remains available to the frontend.

The frontend therefore consumes the S3 document as the validated read model and does not need to understand KickoffAPI's provider version or response shape.

## Score policy

KickoffAPI score data is retained in the JSON even while a match is live. The frontend decides whether to display it. This lets the data layer remain faithful to the provider without showing stale in-progress scores to users.

## Credential

The KickoffAPI key is stored as an SSM SecureString at `/football-schedule/kickoff-api-key`. It is never exposed to the frontend.

## Tests

`pytest` covers configured competition mappings, status mapping, v1 and v2 fixture shapes, UTC conversion, JST date-window filtering, score preservation, season selection, v1 page pagination, v2 cursor pagination, La Liga canonical-row selection, fail-closed behavior, API error handling, application document validation, and atomic multi-competition publishing.
