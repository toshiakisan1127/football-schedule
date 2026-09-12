# Football data source

The fixture fetcher publishes application-owned, league-specific JSON documents consumed by the frontend. Provider handling stays inside the Lambda/provider layer so the frontend only sees the shared schema.

## Enabled competitions

All currently enabled competitions use API-Football v3:

- Premier League (`epl` / league `39`)
- La Liga (`laliga` / league `140`)
- Bundesliga (`bundesliga` / league `78`)
- Ligue 1 (`ligue1` / league `61`)
- J1 League (`j1` / league `98`)

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

European competitions use `GET /fixtures` with `league`, `season`, `from`, and `to`. The fixture response already contains the team IDs, names, kickoff timestamps, status, scores, round information, and team logo URLs required by the application. No additional logo request is made.

Before consolidating onto API-Football, the current feeds were compared against the existing KickoffAPI feeds:

- Premier League: 23/23 fixtures matched in the validation range
- La Liga: 24/24 fixtures inside the adopted 21-day window matched the existing canonical KickoffAPI feed
- Bundesliga: 11/11 fixtures in the validation window matched
- Ligue 1: 12/12 fixtures in the validation window matched

La Liga also showed why the app does not currently publish 30 days ahead: a later round still contained generic placeholder kickoff times in API-Football after the official schedule had been announced. The MVP therefore uses a 21-day lookahead. The window can be extended later after re-validating each league against official schedule information.

The previous KickoffAPI v2 canonical-selection investigation is kept as historical validation documentation in [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md), but KickoffAPI is no longer required by the deployed fixture fetcher.

### J1 League

J1 also uses API-Football v3:

- endpoint: `GET https://v3.football.api-sports.io/fixtures`
- league: `98`
- current 2026/27 season identifier: `2027`
- authentication header: `x-apisports-key`
- fixture window: provider `from` / `to`, followed by the app's JST range validation
- request model: one range request; `/fixtures` does not accept `page`

API-Football identifies the autumn-spring J1 season by its ending year, so dates in the second half of 2026 map to `season=2027`.

Venue fields are intentionally not included in the application fixture schema. During source validation, some venue values were less reliable than the fixture date/team data, and venue display is not required for the current product.

The exact J1 curl commands, Free-plan restriction response, Pro response shape, kickoff-time spot checks, and the deployed `page` parameter failure are recorded in [`api-football-j1-validation.md`](api-football-j1-validation.md).

## Publication window

The Lambda currently publishes from one day back through 21 days ahead in JST.

Provider-side range behavior is not trusted as the final boundary. After normalization, every fixture is filtered against the configured date window in JST before publishing.

The 21-day limit is a data-quality policy rather than a provider limitation. To extend the range later, fetch the proposed range for each league and compare fixture cards and UTC kickoff times against official league information before changing `LOOKAHEAD_DAYS`.

## Publishing rule

Each competition is built and validated independently before its league-specific S3 object is replaced.

Current outputs include:

```text
data/fixtures/premier-league.json
data/fixtures/laliga.json
data/fixtures/bundesliga.json
data/fixtures/ligue1.json
data/fixtures/j1.json
```

Validation covers document metadata and range, fixture/team identifiers and names, duplicate fixture IDs, home/away consistency, supported statuses, non-negative scores, kickoff timestamps, JST range membership, sorting, and optional team logo HTTP(S) URLs.

If one competition fails fetching, normalization, or validation, its previous known-good S3 object remains untouched. Other competitions can still publish during the same Lambda invocation. Failures are then emitted as one aggregated ERROR summary with provider information.

The frontend therefore consumes validated application-owned JSON and does not need to understand API-Football response shapes.

## Score policy

Provider score data is retained in the JSON when available. The frontend decides whether to display it, including the existing result spoiler behavior.

## Credentials

The API-Football Pro credential is stored as an SSM SecureString and is never exposed to the frontend.

- API-Football Pro: `/football-schedule/api-football-pro-key`

The FixtureFetcher Lambda receives only the parameter name through an environment variable and has IAM read permission for that parameter.

## Tests

`pytest` covers API-Football request behavior, league routing, status mapping, UTC conversion, JST date-window filtering, score/logo preservation, J1 season selection, API error handling, application document validation, manual single-competition refreshes, and partial-success multi-competition publishing.
