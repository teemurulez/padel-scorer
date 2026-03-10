"""
Shared helpers used across blueprints.

Extracted from app.py to avoid circular imports and enable reuse.
"""

import json
import sqlite3
from functools import wraps

from flask import flash, g, jsonify, redirect, request, session
from database import get_db, init_db


# Database initialization flag - lazy init on first request for faster startup
_db_initialized = False


def get_db_connection():
    """Get database connection, stored in Flask's g object"""
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True
        print("Database initialized successfully!")
    if 'db' not in g:
        g.db = get_db()
    return g.db


def get_player(player_id):
    """
    Helper to get player with backward compatibility.
    Tries Phase 3 player_registry first, falls back to Phase 2 players table.
    """
    db = get_db_connection()

    # Try Phase 3 registry first
    result = db.execute(
        'SELECT id, first_name, last_name FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        return dict(result)

    # Fallback to Phase 2 players table
    result = db.execute(
        'SELECT id, name FROM players WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        # Split name into first/last (best effort)
        parts = result['name'].split(' ', 1)
        return {
            'id': result['id'],
            'first_name': parts[0] if len(parts) > 0 else 'Unknown',
            'last_name': parts[1] if len(parts) > 1 else ''
        }

    # Player not found - return placeholder
    return {
        'id': player_id,
        'first_name': '[Deleted',
        'last_name': f'Player {player_id}]'
    }


def get_result_correction_scenario(match_id, db):
    """
    Determine if a match result can be safely edited.

    Returns dict with:
        - scenario: 1 (safe to edit) or 2 (next round exists)
        - can_edit: boolean (True for scenario 1, False for scenario 2 unless admin)
        - next_round_id: ID of next round if scenario 2
        - message: Warning text for user (Finnish)
    """
    # Get match and round info
    match = db.execute(
        '''SELECT m.*, r.tournament_id, r.round_number
           FROM matches m
           JOIN rounds r ON m.round_id = r.id
           WHERE m.id = ?''',
        (match_id,)
    ).fetchone()

    if not match:
        return {'scenario': None, 'can_edit': False, 'message': 'Ottelua ei löydy'}

    # Check if next round exists
    next_round = db.execute(
        '''SELECT id, round_number FROM rounds
           WHERE tournament_id = ? AND round_number = ?''',
        (match['tournament_id'], match['round_number'] + 1)
    ).fetchone()

    if next_round:
        # Scenario 2: Next round exists
        return {
            'scenario': 2,
            'can_edit': False,
            'next_round_id': next_round['id'],
            'current_round_id': match['round_id'],
            'tournament_id': match['tournament_id'],
            'message': 'Seuraava kierros on jo alkanut. Tuloksen muuttaminen vaatii kierroksen uudelleenlaskemisen.'
        }
    else:
        # Scenario 1: Safe to edit
        return {
            'scenario': 1,
            'can_edit': True,
            'next_round_id': None,
            'current_round_id': match['round_id'],
            'tournament_id': match['tournament_id'],
            'message': None
        }


def get_court_labels(tournament):
    """Get court labels for a tournament.

    Returns list of court numbers from court_labels JSON, or generates
    sequential [1, 2, ..., num_courts] if not set.
    """
    court_labels_json = tournament['court_labels'] if 'court_labels' in tournament.keys() else None
    if court_labels_json:
        return json.loads(court_labels_json)
    return list(range(1, tournament['num_courts'] + 1))


def validate_round1_pairings(tournament_id, pairings, db):
    """
    Validate custom Round 1 pairings before saving.

    Args:
        tournament_id: ID of tournament
        pairings: List of dicts with court, team1, team2
        db: Database connection

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Get valid player IDs for this tournament
    tournament_players = db.execute(
        'SELECT player_id FROM tournament_players WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()
    valid_player_ids = {p['player_id'] for p in tournament_players}

    if not valid_player_ids:
        errors.append("Tournament has no players assigned")
        return errors

    all_players = []

    for court in pairings:
        court_players = court['team1'] + court['team2']

        # Validate all players exist in tournament
        for pid in court_players:
            if pid not in valid_player_ids:
                errors.append(f"Player {pid} not in tournament")

        # Validate no duplicates within court
        if len(court_players) != len(set(court_players)):
            errors.append(f"Duplicate players in Court {court['court']}")

        # Validate each team has exactly 2 players
        if len(court['team1']) != 2:
            errors.append(f"Court {court['court']} team1 must have 2 players (has {len(court['team1'])})")
        if len(court['team2']) != 2:
            errors.append(f"Court {court['court']} team2 must have 2 players (has {len(court['team2'])})")

        all_players.extend(court_players)

    # Validate no duplicates across courts
    if len(all_players) != len(set(all_players)):
        errors.append("Player assigned to multiple courts")

    # Validate all tournament players are assigned
    if set(all_players) != valid_player_ids:
        missing = valid_player_ids - set(all_players)
        errors.append(f"Not all players assigned. Missing player IDs: {missing}")

    return errors


def validate_saved_pairings_still_valid(tournament_id, db):
    """
    Check if saved Round 1 pairings match current tournament players.
    Deletes invalid pairings if mismatch detected.

    Args:
        tournament_id: ID of tournament
        db: Database connection

    Returns:
        True if pairings valid, False if invalid (and deleted)
    """
    try:
        saved_pairings = db.execute(
            'SELECT * FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        # Table doesn't exist (old schema) - skip validation
        return True

    if not saved_pairings:
        return True  # No saved pairings, nothing to validate

    # Extract all player IDs from saved pairings
    pairing_player_ids = set()
    for p in saved_pairings:
        pairing_player_ids.update([
            p['team1_player1_id'],
            p['team1_player2_id'],
            p['team2_player1_id'],
            p['team2_player2_id']
        ])

    # Get current tournament players
    current_players = db.execute(
        'SELECT player_id FROM tournament_players WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()
    current_player_ids = {p['player_id'] for p in current_players}

    # If mismatch, delete invalid pairings
    if pairing_player_ids != current_player_ids:
        db.execute(
            'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        )
        db.commit()
        return False  # Invalid pairings deleted

    return True  # Pairings valid


def block_in_demo_mode(f):
    """Decorator to block write operations in demo mode.

    Returns a friendly message instead of executing the function.
    Works with both AJAX (JSON) and form submissions (redirect with flash).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('demo_mode'):
            # Check if this is an AJAX request
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'demo': True,
                    'message': 'Demo-tila: toimintoa ei suoritettu'
                }), 200
            else:
                flash('👾 Demo-tila: toimintoa ei suoritettu')
                # Redirect back to referrer or admin page
                return redirect(request.referrer or '/admin')
        return f(*args, **kwargs)
    return decorated_function
