# tests/test_court_movement.py
import pytest
from court_movement import get_previous_teammates, sort_players_by_court_position, assign_teams_with_separation, generate_next_round_pairings

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

def test_sort_players_by_court_position_winners_first():
    """Test that winners are sorted before losers within same court"""
    matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2  # Team 2 won
        }
    ]
    result = sort_players_by_court_position(matches)
    # Winners (3, 4) should come before losers (1, 2) for court 1
    assert result == [3, 4, 1, 2]

def test_sort_players_multi_court():
    """Test sorting across multiple courts maintains court order"""
    matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        },
        {
            'court_number': 2,
            'player1_id': 5,
            'player2_id': 6,
            'player3_id': 7,
            'player4_id': 8,
            'winning_team': 2
        }
    ]
    result = sort_players_by_court_position(matches)
    # Court 1 winners, Court 1 losers, Court 2 winners, Court 2 losers
    assert result == [1, 2, 3, 4, 7, 8, 5, 6]

def test_assign_teams_prevents_same_teammates():
    """Test that previous teammates are not paired together"""
    sorted_player_ids = [1, 2, 3, 4]  # 4 players for 1 court
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        }
    ]

    result = assign_teams_with_separation(
        sorted_player_ids=sorted_player_ids,
        previous_matches=previous_matches,
        num_courts=1
    )

    # Result should be list of court assignments
    # Each court has [p1, p2, p3, p4] where p1+p2 are NOT previous teammates
    assert len(result) == 1
    court = result[0]
    assert len(court) == 4

    # Player 1 and 2 were teammates, should NOT be together
    if court[0] == 1:
        assert court[1] != 2
    if court[0] == 2:
        assert court[1] != 1

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
