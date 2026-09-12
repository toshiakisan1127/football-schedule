# Football data source

The fixture fetcher publishes application-owned, league-specific JSON documents consumed by the frontend. Provider handling is competition-specific so upstream quirks stay inside the Lambda/provider layer and the frontend only sees the shared schema.

## Enabled competitions

- Premier League (`epl` / API-Football v3 league `39`)
- La Liga (`laliga` / KickoffAPI v2 league `es.1`)
- Bundesliga (`bundesliga` / KickoffAPI v2 league `de.1`)
- Ligue 1 (`ligue1` / KickoffAPI v2 league `fr.1`)
- J1 League (`j1` / API-Football v3 league `98`)

Application competition IDs are stable app-owned slugs and do not depend on provider IDs.

## Provider handling

### Premier League

Premier League uses API-Football v3 league `39`. The fetcher requests one range with `league`, `season`, `from`, and `to`; the fixture response already contains the team IDs, names, status, score, round, and team logo URLs needed by the application.

Before migration, the 2026-09-13 through 2026-10-13 range was compared against the existing KickoffAPI v1 feed. All 23 fixtures matched on fixture ID, home/away team IDs, UTC kickoff, round, status, and total fixture count. The main differences were response shape and the logo URL host. This validation is also recorded in issue #142.

The migration removes the remaining Premier League dependency on KickoffAPI v1. No extra API call is made for logos.

### La Liga

La Liga uses KickoffAPI v2 with league `es.1`. The provider can expose multiple rows for the same home/away/Matchday combination, so the Lambda performs competition-specific canonical selection before normalization. See [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md) for the validated selection strategy.

### Bundesliga and Ligue 1

Bundesliga and Ligue 1 use KickoffAPI v2. Both keep provider-specific canonical selection in the Lambda so duplicate, placeholder, or wall-clock rows are resolved before data reaches the frontend.

API-Football was also evaluated for these leagues, but future fixtures differed from the existing validated KickoffAPI v2 schedules in the tested range, so they remain on KickoffAPI v2 for now.

### J1 League

J1 uses API-Football v3 because the current KickoffAPI feed does not provide the future 2026/27 J1 schedule needed by the app.

- endpoint: `GET https://v3.football.api-sports.io/fixtures`
- league: `98`
- current 2026/27 season identifier: `2027`
- authentication header: `x-apisports-key`
- fixture window: provider `from` / `to`, followed by the app's JST range validation
- request model: one range request; `/fixtures` does not accept `page`

API-Football identifies the autumn-spring J1 season by its ending year, so dates in the second half of 2026 map to `season=2027`.

The fixture response already includes team IDs, names, kickoff timestamps, status, scores, and team logo URLs. For API-Football competitions, provider-specific normalization prefers the API-Football team logo when present; if it is missing, the existing static logo mapping remains as fallback. No additional logo request is required.

Venue fields are intentionally not included in the application fixture schema. During source validation, some venue values were less reliable than the fixture date/team data, and venue display is not required for the current product.

The exact J1 curl commands, Free-plan restriction response, Pro response shape, kickoff-time spot checks, and the deployed `page` parameter failure are recorded in [`api-football-j1-validation.md`](api-football-j1-validation.md).

## Publication window

The Lambda publishes from the configured lookback through lookahead window, currently one day back through 30 days ahead.

Provider-side range behavior is not trusted as the final boundary. After provider-specific normalization, every fixture is filtered against the configured date window in JST before publishing.

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

If one competition fails fetching, provider-specific selection, normalization, or validation, its previous known-good S3 object remains untouched. Other competitions can still publish during the same Lambda invocation. Failures are then emitted as one aggregated ERROR summary with provider information.

The frontend therefore consumes validated application-owned JSON and does not need to understand KickoffAPI or API-Football response shapes.

## Score policy

Provider score data is retained in the JSON when available. The frontend decides whether to display it, including the existing result spoiler behavior.

## Credentials

Provider credentials are stored as SSM SecureStrings and are never exposed to the frontend.

- KickoffAPI: `/football-schedule/kickoff-api-key`
- API-Football Pro: `/football-schedule/api-football-pro-key`

The FixtureFetcher Lambda receives only the parameter names through environment variables and has IAM read permission for both parameters.

## Tests

`pytest` covers provider routing, status mapping, v1/v2/API-Football fixture shapes, UTC conversion, JST date-window filtering, score/logo preservation, season selection, provider request behavior, canonical-row selection, fail-closed behavior, API error handling, application document validation, manual single-competition refreshes, and partial-success multi-competition publishing.
