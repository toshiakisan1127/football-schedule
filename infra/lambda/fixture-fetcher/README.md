# Fixture fetcher Lambda

Python 3.13 Lambda that fetches Premier League and J1 League fixtures from API-Football, normalizes them, and atomically publishes `data/fixtures.json` to S3.

## Local tests

```bash
cd infra/lambda/fixture-fetcher
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No AWS credentials or API-Football key are required for the unit tests.
