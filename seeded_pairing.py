"""
Seeded Round 1 Pairing Algorithm

Generates Round 1 pairings based on player seeding (recent performance).
Uses rolling pool randomization to mix players within similar skill tiers.

Algorithm:
- Players are sorted by seed score (high to low)
- Instead of strictly assigning top 4 to court 1, we use a "pool" approach
- Pool size is ~6 players (adjustable 4-8 based on total players)
- 4 players are randomly selected from the pool for each court
- Remaining players "overflow" to the next court's pool
- This creates variation while keeping similar skill levels together
"""

import random


def generate_seeded_round1_pairings(players_with_seeds, num_courts):
    """
    Generate Round 1 pairings based on player seeds with rolling pool randomization.

    Args:
        players_with_seeds: List of dicts with 'id' and 'seed_points'
        num_courts: Number of courts

    Returns:
        List of lists - court_assignments[court_idx] = [p1_id, p2_id, p3_id, p4_id]
    """
    # Sort players by seed (high to low)
    sorted_players = sorted(
        players_with_seeds,
        key=lambda p: p.get('seed_points', 0),
        reverse=True
    )

    players_per_court = 4
    total_players_needed = num_courts * players_per_court

    if len(sorted_players) < total_players_needed:
        raise ValueError(
            f"Not enough players for {num_courts} courts. "
            f"Need {total_players_needed} players, have {len(sorted_players)}."
        )

    # Calculate optimal overflow size (players that roll to next pool)
    # Target: pool of 6, so overflow of 2
    # Adjust based on total players to ensure even distribution
    total_players = len(sorted_players)
    base_overflow = 2  # Default: pool of 6, pick 4, leave 2

    # Adjust overflow if needed for edge cases
    # For small tournaments (2-3 courts), use smaller overflow
    if num_courts <= 2:
        base_overflow = 1
    elif num_courts >= 6:
        base_overflow = 2

    court_assignments = []
    overflow = []  # Players from previous pool not selected
    player_index = 0  # Current position in sorted_players

    for court_idx in range(num_courts):
        remaining_courts = num_courts - court_idx

        if remaining_courts == 1:
            # Last court - use all remaining players (overflow + remaining sorted)
            pool = overflow + sorted_players[player_index:]
        else:
            # Calculate how many new players to add to pool
            # Target pool size: 4 players + overflow buffer for randomization
            target_pool_size = players_per_court + base_overflow

            # Don't create a pool larger than 8 or smaller than 4
            target_pool_size = max(4, min(8, target_pool_size))

            # How many new players needed to reach target pool size
            new_players_needed = target_pool_size - len(overflow)

            # Calculate how many players we can take while ensuring future courts have enough
            # Key insight: overflow from this pool will help fill future pools
            # So we only need to leave (remaining_courts - 1) * 4 - base_overflow * (remaining_courts - 1)
            # Simplified: future courts need 4 each, but each will get ~base_overflow from previous
            players_available = len(sorted_players) - player_index

            # For remaining courts after this one, each needs 4 players
            # But they'll receive overflow from previous courts
            # So the minimum we must leave is: (remaining - 1) * (4 - base_overflow)
            # But we can't leave negative, so use max with 0
            min_players_for_remaining = max(0, (remaining_courts - 1) * (players_per_court - base_overflow))
            max_can_take = players_available - min_players_for_remaining

            # Take the minimum of what we need and what we can take
            new_players_to_take = max(0, min(new_players_needed, max_can_take))

            # Ensure pool has at least 4 players
            if len(overflow) + new_players_to_take < players_per_court:
                new_players_to_take = players_per_court - len(overflow)

            pool = overflow + sorted_players[player_index:player_index + new_players_to_take]
            player_index += new_players_to_take

        # Randomly select 4 players from the pool
        if len(pool) <= players_per_court:
            # Pool is exactly 4 (or less for edge cases), take all
            selected = pool
            overflow = []
        else:
            selected = random.sample(pool, players_per_court)
            overflow = [p for p in pool if p not in selected]

        # Sort selected players by seed for balanced team assignment
        selected_sorted = sorted(
            selected,
            key=lambda p: p.get('seed_points', 0),
            reverse=True
        )
        player_ids = [p['id'] for p in selected_sorted]

        # Assign teams (alternate to balance):
        # Team 1: highest seed + 3rd seed
        # Team 2: 2nd seed + 4th seed
        team_assignment = [
            player_ids[0],  # player1_id - Team 1, highest seed on court
            player_ids[2],  # player2_id - Team 1, 3rd seed on court
            player_ids[1],  # player3_id - Team 2, 2nd seed on court
            player_ids[3]   # player4_id - Team 2, lowest seed on court
        ]

        court_assignments.append(team_assignment)

    return court_assignments
