# Fixture fetcher Lambda

Python 3.13 Lambda that fetches football fixtures, normalizes provider responses into the application fixture contract, validates each competition document, and publishes league-specific JSON to S3 only when the refresh is valid.

## Provider

All enabled competitions use API-Football v3:

- Premier League: `league=39`
- La Liga: `league=140`
- Bundesliga: `league=78`
- Ligue 1: `league=61`
- J1 League: `league=98`

European competitions use the shared `fetch_fixtures` path. J1 uses the same API-Football endpoint with season handling isolated because API-Football identifies the autumn-spring 2026/27 season as `season=2027`.

The fixture response already contains the team IDs, names, kickoff timestamps, status, scores, and team logo URLs needed by the application. Venue data is not published into the application fixture schema.

See [`../../../docs/data-source.md`](../../../docs/data-source.md) for provider behavior, migration validation, and credential details.

## Runtime

- Runtime: Python 3.13
- Schedule: daily at 05:00 JST via EventBridge Scheduler
- Window: 1 day lookback / 21 days lookahead in JST
- Output: league-specific files under `data/fixtures/`
- API-Football Pro key: SSM SecureString `/football-schedule/api-football-pro-key`

Team logos are preserved from the API-Football fixture response when available. Missing logos may use the existing static mapping fallback; the Lambda does not make an additional API request only to fetch a logo.

## Publish safety

Before S3 upload, each normalized document is validated against schema version 1. Validation includes fixture IDs, competition IDs, team consistency, kickoff timestamps and range, status values, scores, sort order, and optional team logo HTTP(S) URLs.

If provider fetch, normalization, or document validation fails, that competition is not uploaded, keeping the previous known-good S3 object available to the frontend. Other competition documents can still publish successfully during the same run; the invocation then emits one aggregated ERROR summary.

## Packaging

CDK bundling uses `package.sh` so runtime dependencies and the local provider/validation modules are packaged together. CI includes an import smoke test in addition to unit tests.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or provider API keys are required for the unit tests.
