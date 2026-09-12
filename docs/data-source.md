# Football data source

The fixture fetcher publishes application-owned, competition-specific JSON documents consumed by the frontend. Provider handling stays inside the Lambda/provider layer so the frontend only sees the shared schema.

## Enabled competitions

All currently enabled competitions use API-Football v3:

- Premier League (`epl` / league `39`)
- La Liga (`laliga` / league `140`)
- Bundesliga (`bundesliga` / league `78`)
- Ligue 1 (`ligue1` / league `61`)
- J1 League (`j1` / league `98`)
- UEFA Champions League (`ucl` / league `2`)
- UEFA Europa League (`uel` / league `3`)
- UEFA Conference League (`uecl` / league `848`)

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

European competitions use `GET /fixtures` with `league`, `season`, `from`, and `to`. The fixture response already contains the team IDs, names, kickoff timestamps, status, scores, round information, and team logo URLs required by the application. No additional logo request is made.

Before consolidating onto API-Football, the current feeds were compared against the existing KickoffAPI feeds:

- Premier League: 23/23 fixtures matched in the validation range
- La Liga: 24/24 fixtures inside the adopted 21-day window matched the existing canonical KickoffAPI feed
- Bundesliga: 11/11 fixtures in the validation window matched
- Ligue 1: 12/12 fixtures in the validation window matched

La Liga also showed why the app does not currently publish 30 days ahead for European domestic leagues: a later round still contained generic placeholder kickoff times in API-Football after the official schedule had been announced. European domestic leagues therefore use a 21-day lookahead.

The previous KickoffAPI v2 canonical-selection investigation is kept as historical validation documentation in [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md), but KickoffAPI is no longer required by the deployed fixture fetcher.

### UEFA club competitions

The 2026/27 UEFA club competitions were validated directly against API-Football future fixtures:

- Champions League: `league=2`, `season=2026`
- Europa League: `league=3`, `season=2026`
- Conference League: `league=848`, `season=2026`

Future league-stage fixtures are returned with `status.short = NS` and the same fixture/team/logo structure used by domestic competitions.

UEFA competitions use a 35-day lookahead. League-phase matchdays can be more than three weeks apart, so the 21-day European domestic window can otherwise make a valid competition appear empty between matchdays.

### J1 League

J1 also uses API-Football v3:

- endpoint: `GET https://v3.football.api-sports.io/fixtures`
- league: `98`
- current 2026/27 season identifier: `2027`
- authentication header: `x-apisports-key`
- request model: one range request; `/fixtures` does not accept `page`
- publication lookahead: 100 days

API-Football identifies the autumn-spring J1 season by its ending year, so dates in the second half of 2026 map to `season=2027`.

J1 uses a longer 100-day lookahead because the 2027 schedule is available sufficiently far ahead and this app benefits from calendar-style visibility. The final publication boundary is still enforced by the app after normalization.

Venue fields are intentionally not included in the application fixture schema. During source validation, some venue values were less reliable than the fixture date/team data, and venue display is not required for the current product.

The exact J1 curl commands, Free-plan restriction response, Pro response shape, kickoff-time spot checks, and the deployed `page` parameter failure are recorded in [`api-football-j1-validation.md`](api-football-j1-validation.md).

## Publication window

The daily Lambda publishes from one day back through:

- 21 days ahead for Premier League / La Liga / Bundesliga / Ligue 1
- 35 days ahead for UEFA Champions League / Europa League / Conference League
- 100 days ahead for J1 League

Provider-side range behavior is not trusted as the final boundary. After normalization, every fixture is filtered against its competition-specific JST date window before publishing.

Lookahead lengths are product/data-quality policy, not a single provider limitation. Extend them only after checking the target competition's future cards and UTC kickoff quality.

## Publishing rule

Each competition is built and validated independently before its competition-specific S3 object is replaced.

Current daily outputs:

```text
data/fixtures/premier-league.json
data/fixtures/laliga.json
data/fixtures/bundesliga.json
data/fixtures/ligue1.json
data/fixtures/j1.json
data/fixtures/champions-league.json
data/fixtures/europa-league.json
data/fixtures/conference-league.json
```

LIVE state is published separately to:

```text
data/fixtures/live.json
```

The LIVE object is not a competition document. It is an all-competition snapshot keyed by fixture ID and contains `generatedAt`, `expiresAt`, current scores, elapsed time, and supported match events. See [`live-fixtures.md`](live-fixtures.md).

Validation covers document metadata and range, fixture/team identifiers and names, duplicate fixture IDs, home/away consistency, supported statuses, non-negative scores, kickoff timestamps, JST range membership, sorting, and optional team logo HTTP(S) URLs.

If one competition fails fetching, normalization, or validation, its previous known-good S3 object remains untouched. Other competitions can still publish during the same Lambda invocation. Failures are emitted as one aggregated ERROR summary with provider information.

The frontend therefore consumes validated application-owned JSON and does not need to understand API-Football response shapes.

## LIVE source

The LIVE Lambda uses one API-Football request for all enabled competition IDs:

```text
GET /fixtures?live=39-140-78-61-98-2-3-848&timezone=Asia/Tokyo
```

It runs every five minutes. One batched request per execution means 288 provider requests/day for LIVE refreshes.

## Score policy

Provider score data is retained in the JSON when available. The frontend decides whether to display it, including the existing result spoiler behavior.

For active matches, the frontend overlays the fresh `live.json` snapshot on top of the daily fixture document by fixture ID.

## Credentials

The API-Football Pro credential is stored as an SSM SecureString and is never exposed to the frontend.

- API-Football Pro: `/football-schedule/api-football-pro-key`

Fixture Lambdas receive only the parameter name through an environment variable and have IAM read permission for that parameter.

## Failure notifications

Daily and LIVE fetchers both write structured logs to CloudWatch Logs. `level = ERROR` events are sent through Subscription Filters to the shared `BatchErrorNotifier` Lambda.

Repeated identical errors are throttled for six hours using a DynamoDB alert-state table. Details are in [`error-alerting.md`](error-alerting.md).

## Tests

`pytest` covers API-Football request behavior, league routing, competition-specific lookahead windows, status mapping, UTC conversion, JST date-window filtering, score/logo preservation, J1 season selection, API error handling, application document validation, manual single-competition refreshes, partial-success multi-competition publishing, LIVE batching, LIVE normalization, and empty-snapshot publishing.
