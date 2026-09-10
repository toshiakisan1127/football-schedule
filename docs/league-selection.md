# League selection

The schedule opens with all competitions visible. League chips are a persisted display preference rather than a one-off filter.

- With no saved selection, all competitions are shown.
- Selecting a league starts a custom selection and shows only that league.
- Additional leagues can be selected at the same time.
- Removing the final selected league returns to all competitions.
- Choosing `全リーグ` resets the custom selection.
- The selected competition IDs are stored in `localStorage` under `football-schedule-competitions`.

This avoids assuming which leagues a user follows while still supporting a Premier League + J1 League view with two taps.