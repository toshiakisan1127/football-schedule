# Football data source

The MVP fetcher reads fixtures from API-Football and publishes the application-owned JSON document consumed by the frontend.

## MVP competitions

- Premier League (`epl`)
- J1 League (`j1`)

The MVP intentionally starts with these two competitions. Additional leagues and cups can be added after the fetch/publish path is proven stable.

## Publishing rule

The Lambda builds the complete document in memory first. `data/fixtures.json` is written to S3 only after every configured competition has been fetched and normalized successfully. If any competition fails, the previous S3 object is left untouched.

## Score policy

API-Football score data is retained in the JSON even while a match is live. The frontend decides whether to display it. This lets the data layer remain faithful to the provider without showing stale in-progress scores to users.

## Tests

`pytest` covers status mapping, UTC conversion, score preservation, season selection, API pagination, API error handling, and the atomic publish behavior.
