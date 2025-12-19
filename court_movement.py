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
