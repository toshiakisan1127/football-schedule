# LIVE fixture updates

Match Calendar refreshes live match state independently from the daily fixture documents.

- Source: API-Football `GET /fixtures?live=39-140-78-61-98-2-3-848&timezone=Asia/Tokyo`
- Lambda schedule: every 5 minutes
- API requests: one request per refresh for all supported competitions
- Output: `data/fixtures/live.json`
- Snapshot lifetime: `expiresAt` is set to 10 minutes after `generatedAt`
- Frontend polling: every 5 minutes while there are no fresh live matches, every 1 minute while a fresh snapshot contains live matches
- Background tabs: polling stops while the page is hidden and refreshes immediately when the page becomes visible again
- Display: `LIVE`, elapsed time and current score in the existing status area
- Details: selecting a live match expands goal, card and substitution events

If the live Lambda keeps failing, the last S3 object may remain, but the frontend stops using it when `expiresAt` is reached. The daily fixture data remains available as the fallback.

The adaptive frontend polling keeps CloudFront request volume low when no supported match is live while increasing freshness during live matches. The five-minute Lambda schedule is intentionally conservative for the initial release. With API-Football Pro's 7,500-request daily quota, the Lambda schedule can later be changed to one minute without changing the data model.
