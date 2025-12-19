# tests/test_court_movement.py
import pytest
from court_movement import get_previous_teammates, sort_players_by_court_position

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
