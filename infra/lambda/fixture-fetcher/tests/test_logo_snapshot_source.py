from team_logos import TEAM_LOGOS


def test_static_logo_snapshot_total_count() -> None:
    assert sum(len(teams) for teams in TEAM_LOGOS.values()) == 96
