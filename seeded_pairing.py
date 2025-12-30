"""
Seeded Round 1 Pairing Algorithm

Generates Round 1 pairings based on player seeding (recent performance).
Top players start on Court 1, bottom players on last court.
"""


def generate_seeded_round1_pairings(players_with_seeds, num_courts):
    """
    Generate Round 1 pairings based on player seeds.

    Args:
        players_with_seeds: List of dicts with 'id' and 'seed_points'
        num_courts: Number of courts

    Returns:
        List of lists - court_assignments[court_idx] = [p1_id, p2_id, p3_id, p4_id]
    """
    # Sort players by seed (high to low)
    # Use seed_points if available, else 0
    sorted_players = sorted(
        players_with_seeds,
        key=lambda p: p.get('seed_points', 0),
        reverse=True
    )

    players_per_court = 4

    # Validate we have enough players for the requested courts
    total_players_needed = num_courts * players_per_court
    if len(sorted_players) < total_players_needed:
        raise ValueError(
            f"Not enough players for {num_courts} courts. "
            f"Need {total_players_needed} players, have {len(sorted_players)}."
        )

    court_assignments = []

    for court_idx in range(num_courts):
        start = court_idx * players_per_court
        end = start + players_per_court

        # Get 4 players for this court (sorted by seed)
        court_players = sorted_players[start:end]
        player_ids = [p['id'] for p in court_players]

        # Assign teams (alternate to balance):
        # Team 1: P1 (highest) + P3
        # Team 2: P2 + P4 (lowest on this court)
        # Returns: [p1, p3, p2, p4] (matches database order: player1_id, player2_id, player3_id, player4_id)
        team_assignment = [
            player_ids[0],  # player1_id - Team 1, highest seed on court
            player_ids[2],  # player2_id - Team 1, 3rd seed on court
            player_ids[1],  # player3_id - Team 2, 2nd seed on court
            player_ids[3]   # player4_id - Team 2, lowest seed on court
        ]

        court_assignments.append(team_assignment)

    return court_assignments
