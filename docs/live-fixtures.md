# LIVE fixture updates

Match Calendar refreshes live match state independently from the daily fixture documents.

- Source: API-Football `GET /fixtures?live=39-140-78-61-98-2-3-848&timezone=Asia/Tokyo`
- Schedule: every 5 minutes
- API requests: one request per refresh for all supported competitions
- Output: `data/fixtures/live.json`
- Frontend: polls the published snapshot every minute, ignores snapshots older than 15 minutes, and merges matches by fixture ID
- Display: `LIVE`, elapsed time and current score in the existing status area
- Details: selecting a live match expands goal, card and substitution events

The five-minute schedule is intentionally conservative for the initial release. With API-Football Pro's 7,500-request daily quota, it can later be changed to one minute without changing the data model.
