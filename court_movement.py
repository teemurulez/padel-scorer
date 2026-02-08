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

def generate_next_round_pairings(previous_matches, num_courts):
    """
    Generate court and team assignments for next round based on results.

    King of the Court rules:
    - Winners move up in court order (lower court number = higher)
    - Losers move down in court order
    - Previous teammates are separated when possible

    Args:
        previous_matches: List of completed match dicts from previous round
        num_courts: Number of courts available

    Returns:
        List of court assignments [court1, court2, ...] where each court
        is [player1_id, player2_id, player3_id, player4_id]
    """
    # Validate all matches are completed
    for match in previous_matches:
        # Check if match has a winner - winning_team must be set
        if match.get('winning_team') is None:
            raise ValueError(
                f"Cannot generate pairings: Match {match.get('id')} has incomplete matches"
            )
        # If completed field exists, it must be truthy
        if 'completed' in match and not match['completed']:
            raise ValueError(
                f"Cannot generate pairings: Match {match.get('id')} has incomplete matches"
            )

    # Step 1: Separate winners and losers per court
    sorted_matches = sorted(previous_matches, key=lambda m: m['court_number'])

    court_winners = []  # court_winners[i] = [w1, w2] from court i
    court_losers = []   # court_losers[i] = [l1, l2] from court i

    for match in sorted_matches:
        if match['winning_team'] == 1:
            winners = [match['player1_id'], match['player2_id']]
            losers = [match['player3_id'], match['player4_id']]
        else:
            winners = [match['player3_id'], match['player4_id']]
            losers = [match['player1_id'], match['player2_id']]

        court_winners.append(winners)
        court_losers.append(losers)

    n = len(court_winners)

    # Step 2: Interleave - winners move up 1 court, losers move down 1 court
    # Court 1: court 1 winners (stay) + court 2 winners (up 1)
    # Court K: court K-1 losers (down 1) + court K+1 winners (up 1)
    # Court N: court N-1 losers (down 1) + court N losers (stay)
    final_courts = []

    for court_idx in range(n):
        if court_idx == 0:
            # Top court: winners from court 1 stay + winners from court 2 move up
            court_players = court_winners[0] + court_winners[1] if n > 1 else court_winners[0]
        elif court_idx == n - 1:
            # Bottom court: losers from court N-1 move down + losers from court N stay
            court_players = court_losers[court_idx - 1] + court_losers[court_idx]
        else:
            # Middle courts: losers from above (down 1) + winners from below (up 1)
            court_players = court_losers[court_idx - 1] + court_winners[court_idx + 1]

        if len(court_players) < 4:
            break

        p1, p2, p3, p4 = court_players

        # Step 3: Separate previous teammates within each court
        p1_teammates = get_previous_teammates(p1, previous_matches)

        if p2 in p1_teammates:
            p2, p3 = p3, p2

        final_courts.append([p1, p2, p3, p4])

    return final_courts
