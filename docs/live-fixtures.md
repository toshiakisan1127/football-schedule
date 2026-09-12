# LIVE fixture updates

Match Calendar refreshes live match state independently from the daily fixture documents.

## Refresh model

- Source: API-Football `GET /fixtures?live=39-140-78-61-98-2-3-848&timezone=Asia/Tokyo`
- Lambda schedule: every 5 minutes
- API requests: one request per refresh for all supported competitions
- Output: `data/fixtures/live.json`
- Snapshot lifetime: `expiresAt` is set to 10 minutes after `generatedAt`
- Frontend polling: every 5 minutes while there are no fresh live matches, every 1 minute while a fresh snapshot contains live matches
- Background tabs: polling stops while the page is hidden and refreshes immediately when the page becomes visible again
- Display: `LIVE`, elapsed time and current score in the existing status area
- Details: selecting a live match expands goal, card and substitution events

## Snapshot contract

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-09-13T03:40:00Z",
  "expiresAt": "2026-09-13T03:50:00Z",
  "fixtures": [
    {
      "id": "1575165",
      "competitionId": "bundesliga",
      "period": "2H",
      "elapsed": 76,
      "extra": null,
      "score": { "home": 1, "away": 1 },
      "events": []
    }
  ]
}
```

A successful API response with no live matches still overwrites the object with `fixtures: []`, which clears stale LIVE state normally.

If the live Lambda keeps failing, the last S3 object may remain, but the frontend stops using it when `expiresAt` is reached. The daily fixture data remains available as the fallback.

## Request-volume policy

The adaptive frontend polling keeps CloudFront request volume low when no supported match is live while increasing freshness during live matches.

The five-minute Lambda schedule is intentionally conservative for the initial release. With API-Football Pro's 7,500-request daily quota, the backend schedule can later be changed to one minute without changing the data model.

## Failure notifications

`LiveFixtureFetcher` writes structured logs to its dedicated CloudWatch Log Group. Only `level = ERROR` logs are forwarded by a Subscription Filter to `BatchErrorNotifier`.

Repeated identical alerts are throttled using DynamoDB: first occurrence is immediate, the same fingerprint is suppressed for six hours, and materially different failures can still notify immediately.

See [`error-alerting.md`](error-alerting.md) for the DynamoDB table, fingerprint definition, cooldown, TTL, and fail-open behavior.

## Related docs

- [`architecture.md`](architecture.md)
- [`error-alerting.md`](error-alerting.md)
- [`data-source.md`](data-source.md)
