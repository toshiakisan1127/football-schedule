# Fixture fetcher Lambda

Python 3.13 Lambda that fetches football fixtures, normalizes provider-specific responses into the application fixture contract, validates the complete document, and publishes `data/fixtures.json` to S3 only when the refresh is fully valid.

## Providers

- Premier League: KickoffAPI v1
- La Liga: KickoffAPI v2

La Liga v2 is cursor-paginated and can contain duplicate candidate rows. The fetcher selects a canonical UTC row only when it matches the validated `Europe/Madrid` wall-clock sibling pattern. Ambiguous or unresolved relevant groups fail closed so the previous known-good S3 object remains untouched.

See [`../../../docs/data-source.md`](../../../docs/data-source.md) and [`../../../docs/kickoffapi-laliga-v2-validation.md`](../../../docs/kickoffapi-laliga-v2-validation.md) for provider behavior and validation details.

## Runtime

- Runtime: Python 3.13
- Schedule: every 6 hours via EventBridge Scheduler
- Window: 1 day lookback / 30 days lookahead in JST
- Output: `data/fixtures.json`
- API key: SSM SecureString `/football-schedule/kickoff-api-key`

Team logos are preserved when the provider fixture response contains `logo`, `image`, or `crest`. Missing logos are omitted; the Lambda does not make an additional API request only to fetch a logo.

## Publish safety

Before S3 upload, the normalized document is validated against schema version 1. Validation includes fixture IDs, competition IDs, team consistency, kickoff timestamps and range, status values, scores, sort order, and optional team logo HTTP(S) URLs.

If provider fetch, provider-specific validation, normalization, or document validation fails, the Lambda raises an error before `put_object`, keeping the previous known-good object available to the frontend.

## Packaging

CDK bundling uses `package.sh` so runtime dependencies and the local validation module are packaged together. CI includes an import smoke test in addition to unit tests.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or KickoffAPI key are required for the unit tests.
