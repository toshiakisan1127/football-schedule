# Fixture fetcher Lambda

Python 3.13 Lambda that fetches Premier League, UEFA Champions League, and LaLiga fixtures from KickoffAPI v2, normalizes them, filters the configured JST window, and atomically publishes `data/fixtures.json` to S3.

The API key is read from SSM SecureString parameter `/football-schedule/kickoff-api-key`.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or KickoffAPI key are required for the unit tests.
