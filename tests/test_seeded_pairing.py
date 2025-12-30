import pytest
from seeded_pairing import generate_seeded_round1_pairings


def test_seeded_pairing_puts_top_players_on_court_1():
    """Test that highest seeded players are on Court 1"""
    # Mock database with 8 players having different seeds
    players_with_seeds = [
        {'id': 1, 'seed_points': 850},
        {'id': 2, 'seed_points': 820},
        {'id': 3, 'seed_points': 780},
        {'id': 4, 'seed_points': 750},
        {'id': 5, 'seed_points': 680},
        {'id': 6, 'seed_points': 650},
        {'id': 7, 'seed_points': 620},
        {'id': 8, 'seed_points': 580},
    ]

    pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=2)

    # Court 1 should have top 4 players (ids 1, 2, 3, 4)
    court1_players = set(pairings[0])
    assert court1_players == {1, 2, 3, 4}

    # Court 2 should have bottom 4 players (ids 5, 6, 7, 8)
    court2_players = set(pairings[1])
    assert court2_players == {5, 6, 7, 8}


def test_seeded_pairing_handles_new_players():
    """Test that new players (seed=0) go to lower courts"""
    players_with_seeds = [
        {'id': 1, 'seed_points': 850},
        {'id': 2, 'seed_points': 820},
        {'id': 3, 'seed_points': 0},  # New player
        {'id': 4, 'seed_points': 0},  # New player
        {'id': 5, 'seed_points': 750},
        {'id': 6, 'seed_points': 680},
        {'id': 7, 'seed_points': 0},  # New player
        {'id': 8, 'seed_points': 0},  # New player
    ]

    pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=2)

    # Court 1 should have experienced players (1, 2, 5, 6)
    court1_players = set(pairings[0])
    assert court1_players == {1, 2, 5, 6}

    # Court 2 should have new players (3, 4, 7, 8)
    court2_players = set(pairings[1])
    assert court2_players == {3, 4, 7, 8}


def test_seeded_pairing_balances_teams():
    """Test that team assignments are balanced (high/low seed pairs)"""
    players_with_seeds = [
        {'id': 1, 'seed_points': 850},  # Highest
        {'id': 2, 'seed_points': 820},
        {'id': 3, 'seed_points': 780},
        {'id': 4, 'seed_points': 750},  # Lowest on Court 1
    ]

    pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=1)

    # Team assignment should be: [p1, p3, p2, p4] for balance
    # Team 1 (p1, p3): highest + 3rd seed
    # Team 2 (p2, p4): 2nd + lowest seed
    assert pairings[0] == [1, 3, 2, 4]


def test_seeded_pairing_handles_partial_court():
    """Test that partial courts raise ValueError"""
    players_with_seeds = [
        {'id': 1, 'seed_points': 850},
        {'id': 2, 'seed_points': 820},
        {'id': 3, 'seed_points': 780},
        {'id': 4, 'seed_points': 750},
        {'id': 5, 'seed_points': 680},
        {'id': 6, 'seed_points': 650},
        # Only 6 players, not enough for 2 full courts
    ]

    # Should raise ValueError when not enough players
    with pytest.raises(ValueError, match="Not enough players for 2 courts"):
        generate_seeded_round1_pairings(players_with_seeds, num_courts=2)
