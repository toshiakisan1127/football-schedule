# Fixture fetcher Lambda

Python 3.13 Lambda that fetches football fixtures, normalizes provider-specific responses into the application fixture contract, validates each competition document, and publishes league-specific JSON to S3 only when the refresh is valid.

## Providers

- Premier League: KickoffAPI v1
- La Liga: KickoffAPI v2
- Bundesliga: KickoffAPI v2
- Ligue 1: KickoffAPI v2
- J1 League: API-Football v3 (`league=98`)

KickoffAPI v2 competitions can require competition-specific canonical selection because provider feeds may contain duplicate or placeholder rows. J1 is intentionally isolated behind the API-Football adapter so the provider can be changed independently from the frontend contract.

For the current autumn-spring J1 season, API-Football identifies 2026/27 as `season=2027`. The adapter derives the ending year from the fixture window, follows API-Football paging, and uses the team logo URLs already included in the fixture response. Venue data is not published into the application fixture schema.

See [`../../../docs/data-source.md`](../../../docs/data-source.md) for provider behavior and credential details.

## Runtime

- Runtime: Python 3.13
- Schedule: daily at 05:00 JST via EventBridge Scheduler
- Window: 1 day lookback / 30 days lookahead in JST
- Output: league-specific files under `data/fixtures/`
- KickoffAPI key: SSM SecureString `/football-schedule/kickoff-api-key`
- API-Football Pro key: SSM SecureString `/football-schedule/api-football-pro-key`

Team logos are preserved when the provider fixture response contains `logo`, `image`, or `crest`. Missing logos are omitted; the Lambda does not make an additional API request only to fetch a logo.

## Publish safety

Before S3 upload, each normalized document is validated against schema version 1. Validation includes fixture IDs, competition IDs, team consistency, kickoff timestamps and range, status values, scores, sort order, and optional team logo HTTP(S) URLs.

If provider fetch, provider-specific validation, normalization, or document validation fails, that competition is not uploaded, keeping the previous known-good S3 object available to the frontend. Other competition documents can still publish successfully during the same run; the invocation then emits one aggregated ERROR summary.

## Packaging

CDK bundling uses `package.sh` so runtime dependencies and the local provider/validation modules are packaged together. CI includes an import smoke test in addition to unit tests.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or provider API keys are required for the unit tests.
