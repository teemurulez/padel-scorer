import pytest
from seeded_pairing import generate_seeded_round1_pairings


def test_seeded_pairing_uses_rolling_pool_randomization():
    """Test that court assignments use rolling pool randomization within skill tiers"""
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

    court1_players = set(pairings[0])
    court2_players = set(pairings[1])

    # All players should be assigned exactly once
    assert len(court1_players) == 4
    assert len(court2_players) == 4
    assert court1_players.isdisjoint(court2_players)
    assert court1_players | court2_players == {1, 2, 3, 4, 5, 6, 7, 8}

    # Court 1 players should come from top pool (players 1-5 for 2 courts)
    # At least 3 of the top 4 should be on court 1 (pool is top 5, pick 4)
    top_4_on_court1 = len(court1_players & {1, 2, 3, 4})
    assert top_4_on_court1 >= 3, f"Expected at least 3 of top 4 on court 1, got {top_4_on_court1}"

    # Court 1 should not have the bottom 3 players
    assert court1_players.isdisjoint({6, 7, 8}) or len(court1_players & {6, 7, 8}) <= 1


def test_seeded_pairing_handles_new_players():
    """Test that new players (seed=0) end up on lower courts"""
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

    court1_players = set(pairings[0])
    court2_players = set(pairings[1])

    # Experienced players (1, 2, 5, 6) should mostly be on court 1
    # At least 3 of them should be on court 1
    experienced = {1, 2, 5, 6}
    experienced_on_court1 = len(court1_players & experienced)
    assert experienced_on_court1 >= 3, f"Expected at least 3 experienced players on court 1"

    # New players (3, 4, 7, 8) should mostly be on court 2
    new_players = {3, 4, 7, 8}
    new_on_court2 = len(court2_players & new_players)
    assert new_on_court2 >= 3, f"Expected at least 3 new players on court 2"


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


def test_seeded_pairing_6_courts_all_players_assigned():
    """Test seeded pairing with 24 players for 6 courts (base_overflow=2 branch)."""
    players_with_seeds = [
        {'id': i, 'seed_points': 1000 - i * 30}
        for i in range(1, 25)
    ]

    pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=6)

    assert len(pairings) == 6

    all_assigned = set()
    for court in pairings:
        assert len(court) == 4
        court_set = set(court)
        assert len(court_set) == 4, f"Duplicate player on court: {court}"
        assert court_set.isdisjoint(all_assigned), f"Player assigned to multiple courts"
        all_assigned.update(court_set)

    assert all_assigned == set(range(1, 25))


def test_seeded_pairing_6_courts_skill_tiers_respected():
    """Top seeds should end up on higher courts, bottom seeds on lower courts."""
    players_with_seeds = [
        {'id': i, 'seed_points': 1000 - i * 30}
        for i in range(1, 25)
    ]

    # Run multiple times to account for randomization
    # Pool size is 6 (4 + base_overflow=2) so P(>=3 of top 4 selected) ~ 60%
    # Use enough trials and a conservative threshold for statistical reliability
    top_4_on_court1_count = 0
    bottom_4_on_last_court_count = 0
    trials = 100

    for _ in range(trials):
        pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=6)
        court1_players = set(pairings[0])
        court6_players = set(pairings[5])

        # At least 3 of top 4 should be on court 1
        if len(court1_players & {1, 2, 3, 4}) >= 3:
            top_4_on_court1_count += 1
        # At least 3 of bottom 4 should be on court 6
        if len(court6_players & {21, 22, 23, 24}) >= 3:
            bottom_4_on_last_court_count += 1

    # With pool-based randomization (pool=6, pick=4), the probability of
    # getting >=3 of top/bottom 4 on the expected court is ~60% per trial.
    # With 100 trials, expect ~60 successes; threshold of 40% is very safe.
    assert top_4_on_court1_count >= trials * 0.4, f"Top seeds on court 1 only {top_4_on_court1_count}/{trials} times"
    assert bottom_4_on_last_court_count >= trials * 0.4, f"Bottom seeds on court 6 only {bottom_4_on_last_court_count}/{trials} times"