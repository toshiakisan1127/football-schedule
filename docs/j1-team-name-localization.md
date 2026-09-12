# J1 team-name localization

J1 team names are localized in the frontend with a static API-Football team ID to Japanese display-name mapping.

- The API response and normalized fixture IDs remain unchanged.
- Only the frontend display name is localized.
- Unknown team IDs fall back to the provider-supplied name so promotions, relegations, or provider changes do not break rendering.
- The same mapping is applied to live-event team names when a matching team ID is available.

The current mapping lives in `app/data/j1TeamNames.ts`.
