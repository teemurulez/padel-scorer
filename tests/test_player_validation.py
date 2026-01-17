import pytest
from player_validation import validate_player_names, find_similar_player

def test_find_similar_player_exact_match():
    """Exact match returns the player"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
        {'id': 2, 'first_name': 'Anna', 'last_name': 'Korhonen'},
    ]
    result = find_similar_player('Matti Virtanen', registry)
    assert result['status'] == 'exact'
    assert result['player_id'] == 1

def test_find_similar_player_fuzzy_match():
    """Similar name suggests correction"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Meikäläinen'},
    ]
    result = find_similar_player('Matti Meikalainen', registry)  # Missing ä
    assert result['status'] == 'similar'
    assert result['suggestion'] == 'Matti Meikäläinen'
    assert result['player_id'] == 1

def test_find_similar_player_no_match():
    """New player detected"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
    ]
    result = find_similar_player('Liisa Nieminen', registry)
    assert result['status'] == 'new'
    assert result['player_id'] is None

def test_validate_player_names_mixed():
    """Validate list with mix of exact, similar, and new"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
        {'id': 2, 'first_name': 'Anna', 'last_name': 'Korhonen'},
    ]
    names = ['Matti Virtanen', 'Matti Virtanen', 'Anna Korhonnen', 'Liisa Uusi']

    results = validate_player_names(names, registry)

    assert len(results) == 4
    assert results[0]['status'] == 'exact'
    assert results[1]['status'] == 'duplicate'  # Duplicate of first
    assert results[2]['status'] == 'similar'  # Typo
    assert results[3]['status'] == 'new'

def test_validate_player_names_empty_lines_ignored():
    """Empty lines in input are filtered out"""
    registry = []
    names = ['Matti Virtanen', '', '  ', 'Anna Korhonen']

    results = validate_player_names(names, registry)

    assert len(results) == 2
