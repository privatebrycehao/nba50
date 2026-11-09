def get_home_away_competitors(event):
    competitions = event.get('competitions', [])
    if not competitions:
        return None, None
    competitors = competitions[0].get('competitors', [])
    home = next((team for team in competitors if team.get('homeAway') == 'home'), None)
    away = next((team for team in competitors if team.get('homeAway') == 'away'), None)
    return home, away
