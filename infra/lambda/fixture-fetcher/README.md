# Fixture fetcher Lambda

Python 3.13 Lambda that fetches Premier League fixtures from KickoffAPI v1 and La Liga fixtures from KickoffAPI v2, normalizes them, filters the configured JST window, and atomically publishes `data/fixtures.json` to S3.

La Liga v2 is cursor-paginated and contains duplicate candidate rows. The fetcher selects a canonical UTC row only when it matches the validated `Europe/Madrid` wall-clock sibling pattern. Ambiguous or unresolved relevant groups fail closed so the previous known-good S3 object remains untouched.

See [`../../../docs/data-source.md`](../../../docs/data-source.md) and [`../../../docs/kickoffapi-laliga-v2-validation.md`](../../../docs/kickoffapi-laliga-v2-validation.md) for provider behavior and validation details.

The API key is read from SSM SecureString parameter `/football-schedule/kickoff-api-key`.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or KickoffAPI key are required for the unit tests.
