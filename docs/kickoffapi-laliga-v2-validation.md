# KickoffAPI La Liga v2 validation

Validated on 2026-09-11 for the 2026 La Liga season.

## Why this validation exists

The application publishes roughly one month of fixtures. KickoffAPI v1 and v2 behaved differently for La Liga:

- v1 (`league=140`) returned clean fixture rows, but a request for 2026-09-11 through 2026-10-11 returned only 29 fixtures and stopped at 2026-09-20.
- v2 (`league=es.1`) contained fixtures through 2026-10-11, but returned multiple records for the same home/away/Matchday combination.
- v2 also ignored the requested `from` / `to` window in the observed response and returned a wider season result set, so the application must continue to enforce its own publication window.

The goal of this validation was to determine whether one canonical v2 row could be selected without guessing a kickoff time.

## Observed v2 duplicate pattern

For example, Sevilla FC vs Valencia CF, Matchday 5, appeared as:

```text
2026-09-11T19:00:00.000Z  time=null
2026-09-11T21:00:00.000Z  time="21:00"
2026-09-13T12:00:00.000Z  time=null
```

The v1 fixture date was `2026-09-11T19:00:00.000Z`.

The first v2 row is the correct UTC kickoff. Converting it to `Europe/Madrid` gives 21:00. A sibling v2 row stores that Madrid wall-clock value as `2026-09-11T21:00:00.000Z` and also exposes `time="21:00"`.

The additional `2026-09-13T12:00:00.000Z` row behaved like a placeholder and did not have a matching same-date Madrid wall-clock sibling.

This pattern was also observed across the other compared fixtures. A fixed two-hour adjustment is intentionally not used because Madrid changes between CET and CEST.

## Rules considered and rejected

### Earliest record

Rejected. The v1-correct row was the earliest candidate for 15 of 18 initially matched groups, but not for fixtures such as Villarreal vs Real Betis where an earlier noon placeholder existed.

### `time == null`

Rejected by itself. Both canonical UTC rows and placeholder rows can have `time=null`.

### Provider ID / round / status / source

Rejected. Duplicate candidates had different fixture IDs but the same Matchday, `NS` status, and `source=owned`, so these fields did not identify the correct row.

## Canonical selection rule

Group v2 rows by:

```text
home team name + away team name + Matchday
```

Within each group:

1. Consider rows where `time == null` as canonical UTC candidates.
2. Convert the candidate `date` from UTC to `Europe/Madrid`.
3. Derive the Madrid local calendar date and `HH:MM`.
4. Require a sibling row in the same group whose:
   - `time` equals that Madrid `HH:MM`, and
   - UTC-labelled `date` contains that same Madrid local calendar date and `HH:MM`.
5. Exactly one candidate must satisfy the rule.
6. If zero or multiple candidates satisfy it for a group in the publication window, fail closed and do not replace the existing known-good S3 document.

The final normalized fixture still passes through the existing JST publication-window filter.

## Cross-check against v1

The rule was compared against all 24 v1 fixtures available from 2026-09-11 through 2026-09-19/20, covering Matchdays 5, 6, and 7.

Final result:

```text
total                   : 24
candidate_found         : 24
exact_found             : 24
rule_selected_one       : 24
rule_selected_exact     : 24
rule_selected_wrong     : 0
rule_ambiguous          : 0
rule_none               : 0
```

The initial version of the rule matched 22/24 uniquely. The two ambiguous cases were caused by allowing a wall-clock sibling from a different calendar date. Requiring the sibling date to match the candidate's Madrid-local calendar date resolved both cases and produced 24/24 exact matches.

## Provider strategy adopted

- Premier League: KickoffAPI v1 (`league=39`), including provider-side `from` / `to` plus application-side JST filtering.
- La Liga: KickoffAPI v2 (`league=es.1`), cursor pagination across the returned season data, canonical-row selection using the rule above, then application-side JST filtering.
- The frontend continues to consume only the application-owned validated `data/fixtures.json` format and does not know which provider version supplied a competition.

## Regression coverage

Unit tests preserve the 24 verified fixture kickoffs and assert that the canonical selection rule reproduces all 24. Separate tests cover:

- an unpaired placeholder not winning over a verified UTC/Madrid pair,
- zero canonical candidates failing closed,
- multiple canonical candidates failing closed,
- unresolved groups outside the current publication window being ignored,
- team IDs being backfilled from sibling rows when the canonical row has a null team ID,
- v2 cursor pagination.

## Revalidation trigger

Re-run this comparison before changing the selection rule, when KickoffAPI changes the v2 fixture contract, or if production starts failing canonical selection. The safest fallback is to keep the previous known-good S3 document rather than publish a guessed kickoff time.
