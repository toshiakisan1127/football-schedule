from team_logos import get_static_team_logo


def test_mainz_uses_api_sports_logo_asset() -> None:
    assert get_static_team_logo("bundesliga", "1. FSV Mainz 05") == (
        "https://media.api-sports.io/football/teams/164.png"
    )


def test_frankfurt_uses_api_sports_logo_asset() -> None:
    assert get_static_team_logo("bundesliga", "Eintracht Frankfurt") == (
        "https://media.api-sports.io/football/teams/169.png"
    )
