from __future__ import annotations

TEAM_LOGOS: dict[str, dict[str, str]] = {
    "epl": {
        "Arsenal": "https://images.kickoffapi.com/images/logos/42.png?format=webp",
        "Aston Villa": "https://images.kickoffapi.com/images/logos/66.png?format=webp",
        "Bournemouth": "https://images.kickoffapi.com/images/logos/35.png?format=webp",
        "Brentford": "https://images.kickoffapi.com/images/logos/55.png?format=webp",
        "Brighton": "https://images.kickoffapi.com/images/logos/51.png?format=webp",
        "Chelsea": "https://images.kickoffapi.com/images/logos/49.png?format=webp",
        "Coventry": "https://images.kickoffapi.com/images/logos/1346.png?format=webp",
        "Crystal Palace": "https://images.kickoffapi.com/images/logos/52.png?format=webp",
        "Everton": "https://images.kickoffapi.com/images/logos/45.png?format=webp",
        "Fulham": "https://images.kickoffapi.com/images/logos/36.png?format=webp",
        "Hull City": "https://images.kickoffapi.com/images/logos/64.png?format=webp",
        "Ipswich": "https://images.kickoffapi.com/images/logos/57.png?format=webp",
        "Leeds": "https://images.kickoffapi.com/images/logos/63.png?format=webp",
        "Liverpool": "https://images.kickoffapi.com/images/logos/40.png?format=webp",
        "Manchester City": "https://images.kickoffapi.com/images/logos/50.png?format=webp",
        "Manchester United": "https://images.kickoffapi.com/images/logos/33.png?format=webp",
        "Newcastle": "https://images.kickoffapi.com/images/logos/34.png?format=webp",
        "Nottingham Forest": "https://images.kickoffapi.com/images/logos/65.png?format=webp",
        "Sunderland": "https://images.kickoffapi.com/images/logos/746.png?format=webp",
        "Tottenham": "https://images.kickoffapi.com/images/logos/47.png?format=webp",
    },
    "laliga": {
        "Athletic Club": "https://images.kickoffapi.com/images/logos/531.png?format=webp",
        "CA Osasuna": "https://images.kickoffapi.com/images/logos/727.png?format=webp",
        "Club Atlético de Madrid": "https://images.kickoffapi.com/images/logos/530.png?format=webp",
        "Deportivo Alavés": "https://images.kickoffapi.com/images/logos/542.png?format=webp",
        "Elche CF": "https://images.kickoffapi.com/images/logos/797.png?format=webp",
        "FC Barcelona": "https://images.kickoffapi.com/images/logos/529.png?format=webp",
        "Getafe CF": "https://images.kickoffapi.com/images/logos/546.png?format=webp",
        "Levante UD": "https://images.kickoffapi.com/images/logos/539.png?format=webp",
        "Málaga CF": "https://images.kickoffapi.com/images/logos/535.png?format=webp",
        "RC Celta de Vigo": "https://images.kickoffapi.com/images/logos/538.png?format=webp",
        "RC Deportivo La Coruña": "https://images.kickoffapi.com/images/logos/544.png?format=webp",
        "RCD Espanyol de Barcelona": "https://images.kickoffapi.com/images/logos/540.png?format=webp",
        "Rayo Vallecano de Madrid": "https://images.kickoffapi.com/images/logos/728.png?format=webp",
        "Real Betis Balompié": "https://images.kickoffapi.com/images/logos/543.png?format=webp",
        "Real Madrid CF": "https://images.kickoffapi.com/images/logos/541.png?format=webp",
        "Real Racing Club de Santander": "https://images.kickoffapi.com/images/logos/4665.png?format=webp",
        "Real Sociedad de Fútbol": "https://images.kickoffapi.com/images/logos/548.png?format=webp",
        "Sevilla FC": "https://images.kickoffapi.com/images/logos/536.png?format=webp",
        "Valencia CF": "https://images.kickoffapi.com/images/logos/532.png?format=webp",
        "Villarreal CF": "https://images.kickoffapi.com/images/logos/533.png?format=webp",
    },
}


def get_static_team_logo(competition_id: str, team_name: str) -> str | None:
    return TEAM_LOGOS.get(competition_id, {}).get(team_name)
