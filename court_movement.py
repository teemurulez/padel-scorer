# court_movement.py
def get_previous_teammates(player_id, previous_matches):
    """
    Get set of player IDs who were teammates with player_id in previous matches.

    Args:
        player_id: The player to check
        previous_matches: List of match dicts from previous round

    Returns:
        Set of player IDs who were teammates
    """
    teammates = set()

    for match in previous_matches:
        # Check if player was in this match
        player_ids = [
            match['player1_id'],
            match['player2_id'],
            match['player3_id'],
            match['player4_id']
        ]

        if player_id not in player_ids:
            continue

        # Find which team they were on
        if player_id in [match['player1_id'], match['player2_id']]:
            # Team 1
            teammates.add(match['player1_id'])
            teammates.add(match['player2_id'])
        else:
            # Team 2
            teammates.add(match['player3_id'])
            teammates.add(match['player4_id'])

    # Remove the player themselves
    teammates.discard(player_id)

    return teammates

def sort_players_by_court_position(matches):
    """
    Sort players by their position in court hierarchy.
    Winners move up, losers move down.

    Args:
        matches: List of completed match dicts with court_number and winning_team

    Returns:
        List of player IDs in order: Court 1 winners, Court 1 losers,
        Court 2 winners, Court 2 losers, etc.
    """
    # Sort matches by court number
    sorted_matches = sorted(matches, key=lambda m: m['court_number'])

    result = []

    for match in sorted_matches:
        if match['winning_team'] == 1:
            # Team 1 won
            winners = [match['player1_id'], match['player2_id']]
            losers = [match['player3_id'], match['player4_id']]
        else:
            # Team 2 won
            winners = [match['player3_id'], match['player4_id']]
            losers = [match['player1_id'], match['player2_id']]

        # Winners first, then losers
        result.extend(winners)
        result.extend(losers)

    return result

def assign_teams_with_separation(sorted_player_ids, previous_matches, num_courts):
    """
    Assign players to courts and teams, avoiding previous teammates.

    Args:
        sorted_player_ids: Players in court hierarchy order (winners->losers)
        previous_matches: Previous round matches for teammate history
        num_courts: Number of courts to fill

    Returns:
        List of court assignments, each court is [p1, p2, p3, p4]
        where p1+p2 are team 1, p3+p4 are team 2
    """
    courts = []
    players_per_court = 4

    for court_idx in range(num_courts):
        start_idx = court_idx * players_per_court
        end_idx = start_idx + players_per_court

        if end_idx > len(sorted_player_ids):
            break  # Not enough players for this court

        court_players = sorted_player_ids[start_idx:end_idx]

        # Try to assign teams avoiding previous teammates
        # Strategy: Take players in order but swap if needed
        p1, p2, p3, p4 = court_players

        # Check if p1 and p2 were previous teammates
        p1_teammates = get_previous_teammates(p1, previous_matches)

        if p2 in p1_teammates:
            # Swap p2 with p3 to separate teammates
            p2, p3 = p3, p2

        courts.append([p1, p2, p3, p4])

    return courts
