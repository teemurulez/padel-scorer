# tests/test_court_movement.py
import random
import pytest
from court_movement import get_previous_teammates, best_team_arrangement, generate_next_round_pairings

def test_get_previous_teammates_empty_round():
    """Test that empty round history returns empty set"""
    previous_matches = []
    result = get_previous_teammates(player_id=1, previous_matches=previous_matches)
    assert result == set()

def test_get_previous_teammates_identifies_team1_partner():
    """Test identifying teammate from team 1"""
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        }
    ]
    result = get_previous_teammates(player_id=1, previous_matches=previous_matches)
    assert result == {2}

def test_get_previous_teammates_identifies_team2_partner():
    """Test identifying teammate from team 2"""
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2
        }
    ]
    result = get_previous_teammates(player_id=3, previous_matches=previous_matches)
    assert result == {4}

def _make_match(court_number, p1, p2, p3, p4, winning_team):
    """Helper to create a match dict."""
    return {
        'id': court_number,
        'court_number': court_number,
        'player1_id': p1,
        'player2_id': p2,
        'player3_id': p3,
        'player4_id': p4,
        'winning_team': winning_team,
        'completed': 1,
    }


def test_best_team_arrangement_avoids_previous_teammates():
    """Test that best_team_arrangement picks arrangement with zero conflicts."""
    # Players 1+2 were teammates, 3+4 were teammates
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        }
    ]
    result = best_team_arrangement([1, 2, 3, 4], previous_matches)
    # Team 1 (result[0], result[1]) should NOT be previous teammates
    # Team 2 (result[2], result[3]) should NOT be previous teammates
    team1 = {result[0], result[1]}
    team2 = {result[2], result[3]}
    assert {1, 2} != team1, "Previous teammates 1+2 should not be on same team"
    assert {3, 4} != team2, "Previous teammates 3+4 should not be on same team"
    assert team1 | team2 == {1, 2, 3, 4}


def test_best_team_arrangement_no_conflicts_keeps_original():
    """With no previous matches, the original arrangement is preserved."""
    result = best_team_arrangement([1, 2, 3, 4], [])
    assert result == [1, 2, 3, 4]


def test_teammate_separation_across_all_courts():
    """Verify teammate separation works across all courts, not just first pair."""
    # Set up so court 2 would have players 3,4 (prev teammates) + 9,10 (prev teammates)
    previous_matches = [
        _make_match(1, 1, 2, 3, 4, winning_team=1),      # 1+2 win, 3+4 lose
        _make_match(2, 5, 6, 7, 8, winning_team=1),       # 5+6 win, 7+8 lose
        _make_match(3, 9, 10, 11, 12, winning_team=1),    # 9+10 win, 11+12 lose
    ]
    result = generate_next_round_pairings(previous_matches, num_courts=3)
    # Court 2 gets: C1 losers (3,4) + C3 winners (9,10)
    # 3+4 were teammates, 9+10 were teammates — both pairs should be separated
    court2 = result[1]
    assert set(court2) == {3, 4, 9, 10}
    team1 = {court2[0], court2[1]}
    team2 = {court2[2], court2[3]}
    assert {3, 4} != team1 and {3, 4} != team2, "Previous teammates 3+4 should be separated"
    assert {9, 10} != team1 and {9, 10} != team2, "Previous teammates 9+10 should be separated"


def test_generate_next_round_pairings_moves_winners_up():
    """Test that winners from court 2 move to court 1"""
    previous_matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2  # 3, 4 won
        },
        {
            'court_number': 2,
            'player1_id': 5,
            'player2_id': 6,
            'player3_id': 7,
            'player4_id': 8,
            'winning_team': 1  # 5, 6 won
        }
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=2)

    # Court 1 should have winners from both courts
    # Court 2 should have losers from both courts
    court1 = result[0]
    court2 = result[1]

    # Winners: 3, 4, 5, 6 should be on court 1
    assert set(court1) == {3, 4, 5, 6}
    # Losers: 1, 2, 7, 8 should be on court 2
    assert set(court2) == {1, 2, 7, 8}


def test_movement_3_courts_winners_move_up_one():
    """With 3 courts, winners move up exactly 1 court, losers down 1."""
    previous_matches = [
        _make_match(1, 1, 2, 3, 4, winning_team=1),      # C1: 1,2 win
        _make_match(2, 5, 6, 7, 8, winning_team=1),      # C2: 5,6 win
        _make_match(3, 9, 10, 11, 12, winning_team=1),   # C3: 9,10 win
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=3)

    # Court 1: C1 winners (stay) + C2 winners (up 1)
    assert set(result[0]) == {1, 2, 5, 6}
    # Court 2: C1 losers (down 1) + C3 winners (up 1)
    assert set(result[1]) == {3, 4, 9, 10}
    # Court 3: C2 losers (down 1) + C3 losers (stay)
    assert set(result[2]) == {7, 8, 11, 12}


def test_movement_4_courts_winners_move_up_one():
    """With 4 courts, court 4 winner should go to court 3, not court 2."""
    previous_matches = [
        _make_match(1, 1, 2, 3, 4, winning_team=1),      # C1: 1,2 win
        _make_match(2, 5, 6, 7, 8, winning_team=1),      # C2: 5,6 win
        _make_match(3, 9, 10, 11, 12, winning_team=1),   # C3: 9,10 win
        _make_match(4, 13, 14, 15, 16, winning_team=1),  # C4: 13,14 win
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=4)

    # Court 1: C1 winners (stay) + C2 winners (up 1)
    assert set(result[0]) == {1, 2, 5, 6}
    # Court 2: C1 losers (down 1) + C3 winners (up 1)
    assert set(result[1]) == {3, 4, 9, 10}
    # Court 3: C2 losers (down 1) + C4 winners (up 1)
    assert set(result[2]) == {7, 8, 13, 14}
    # Court 4: C3 losers (down 1) + C4 losers (stay)
    assert set(result[3]) == {11, 12, 15, 16}


def test_movement_6_courts_court4_winner_goes_to_court3():
    """Regression test for reported bug: court 4 winner went to court 2 instead of 3."""
    previous_matches = [
        _make_match(1, 1, 2, 3, 4, winning_team=1),
        _make_match(2, 5, 6, 7, 8, winning_team=1),
        _make_match(3, 9, 10, 11, 12, winning_team=1),
        _make_match(4, 13, 14, 15, 16, winning_team=1),
        _make_match(5, 17, 18, 19, 20, winning_team=1),
        _make_match(6, 21, 22, 23, 24, winning_team=1),
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=6)

    # Court 1: C1 winners (stay) + C2 winners (up 1)
    assert set(result[0]) == {1, 2, 5, 6}
    # Court 2: C1 losers (down 1) + C3 winners (up 1)
    assert set(result[1]) == {3, 4, 9, 10}
    # Court 3: C2 losers (down 1) + C4 winners (up 1) — the reported bug
    assert set(result[2]) == {7, 8, 13, 14}
    # Court 4: C3 losers (down 1) + C5 winners (up 1)
    assert set(result[3]) == {11, 12, 17, 18}
    # Court 5: C4 losers (down 1) + C6 winners (up 1)
    assert set(result[4]) == {15, 16, 21, 22}
    # Court 6: C5 losers (down 1) + C6 losers (stay)
    assert set(result[5]) == {19, 20, 23, 24}


def test_movement_mixed_winners_across_courts():
    """Test with different teams winning on different courts."""
    previous_matches = [
        _make_match(1, 1, 2, 3, 4, winning_team=2),      # C1: 3,4 win
        _make_match(2, 5, 6, 7, 8, winning_team=1),      # C2: 5,6 win
        _make_match(3, 9, 10, 11, 12, winning_team=2),   # C3: 11,12 win
        _make_match(4, 13, 14, 15, 16, winning_team=1),  # C4: 13,14 win
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=4)

    # Court 1: C1 winners {3,4} + C2 winners {5,6}
    assert set(result[0]) == {3, 4, 5, 6}
    # Court 2: C1 losers {1,2} + C3 winners {11,12}
    assert set(result[1]) == {1, 2, 11, 12}
    # Court 3: C2 losers {7,8} + C4 winners {13,14}
    assert set(result[2]) == {7, 8, 13, 14}
    # Court 4: C3 losers {9,10} + C4 losers {15,16}
    assert set(result[3]) == {9, 10, 15, 16}


def test_generate_pairings_handles_incomplete_matches():
    """Test that algorithm handles incomplete previous round gracefully"""
    previous_matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': None,  # Not completed
            'completed': 0
        }
    ]

    # Should raise error or handle gracefully
    with pytest.raises(ValueError, match="incomplete matches"):
        generate_next_round_pairings(previous_matches, num_courts=1)


@pytest.mark.parametrize("num_courts", [3, 4, 5, 6, 8])
def test_movement_rules_hold_for_n_courts(num_courts):
    """Every winner moves up exactly 1 court (or stays at court 1).
    Every loser moves down exactly 1 court (or stays at last court)."""
    num_players = num_courts * 4
    # All team 1 wins for predictable validation
    matches = [
        _make_match(c + 1, c*4+1, c*4+2, c*4+3, c*4+4, winning_team=1)
        for c in range(num_courts)
    ]

    result = generate_next_round_pairings(matches, num_courts=num_courts)

    assert len(result) == num_courts

    all_assigned = set()
    for court in result:
        assert len(court) == 4
        all_assigned.update(court)

    # All players assigned exactly once
    assert len(all_assigned) == num_players
    assert all_assigned == set(range(1, num_players + 1))

    # Court 1: winners from court 1 (stay) + winners from court 2 (up 1)
    assert set(result[0]) == {1, 2, 5, 6}

    # Last court: losers from court N-1 (down 1) + losers from court N (stay)
    last = num_courts - 1
    last_c = num_courts
    prev_c = num_courts - 1
    expected_last = {prev_c*4-1, prev_c*4, last_c*4-1, last_c*4}
    assert set(result[last]) == expected_last

    # Middle courts: losers from above + winners from below
    for k in range(1, num_courts - 1):
        above = k - 1  # 0-indexed court above
        below = k + 1  # 0-indexed court below
        expected = {
            above*4+3, above*4+4,       # losers from court above
            below*4+1, below*4+2        # winners from court below
        }
        assert set(result[k]) == expected, f"Court {k+1} mismatch"


def test_multi_round_stability_6_courts_7_rounds():
    """Simulate 7 rounds with 6 courts. Every round must satisfy movement rules."""
    num_courts = 6
    num_players = num_courts * 4  # 24
    random.seed(42)

    # Round 1: arbitrary initial placement
    player_ids = list(range(1, num_players + 1))
    current_matches = []
    for c in range(num_courts):
        p = player_ids[c*4:(c+1)*4]
        winning_team = random.choice([1, 2])
        current_matches.append(_make_match(c + 1, p[0], p[1], p[2], p[3], winning_team=winning_team))

    for round_num in range(2, 8):  # Rounds 2-7
        result = generate_next_round_pairings(current_matches, num_courts=num_courts)

        assert len(result) == num_courts, f"Round {round_num}: expected {num_courts} courts"

        # All players assigned exactly once
        all_players = set()
        for court in result:
            assert len(court) == 4, f"Round {round_num}: court has {len(court)} players"
            all_players.update(court)
        assert len(all_players) == num_players, f"Round {round_num}: {len(all_players)} players instead of {num_players}"
        assert all_players == set(range(1, num_players + 1)), f"Round {round_num}: wrong player set"

        # Verify movement rules: check each player moved correctly
        # Build lookup: player -> court in previous round, and win/loss status
        prev_court = {}
        prev_won = {}
        for match in current_matches:
            court_num = match['court_number']
            if match['winning_team'] == 1:
                winners = {match['player1_id'], match['player2_id']}
                losers = {match['player3_id'], match['player4_id']}
            else:
                winners = {match['player3_id'], match['player4_id']}
                losers = {match['player1_id'], match['player2_id']}
            for pid in winners:
                prev_court[pid] = court_num
                prev_won[pid] = True
            for pid in losers:
                prev_court[pid] = court_num
                prev_won[pid] = False

        for court_idx, court_players in enumerate(result):
            new_court = court_idx + 1
            for pid in court_players:
                old_court = prev_court[pid]
                won = prev_won[pid]
                if won:
                    if old_court == 1:
                        assert new_court == 1, f"Round {round_num}: player {pid} won on court 1 but moved to court {new_court}"
                    else:
                        assert new_court == old_court - 1, f"Round {round_num}: player {pid} won on court {old_court} but moved to court {new_court} (expected {old_court - 1})"
                else:
                    if old_court == num_courts:
                        assert new_court == num_courts, f"Round {round_num}: player {pid} lost on court {num_courts} but moved to court {new_court}"
                    else:
                        assert new_court == old_court + 1, f"Round {round_num}: player {pid} lost on court {old_court} but moved to court {new_court} (expected {old_court + 1})"

        # Prepare matches for next round with random winners
        current_matches = []
        for c_idx, court in enumerate(result):
            winning_team = random.choice([1, 2])
            current_matches.append(_make_match(c_idx + 1, court[0], court[1], court[2], court[3], winning_team=winning_team))
