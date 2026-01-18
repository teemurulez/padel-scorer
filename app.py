from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify, abort, Response
import csv
import io
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sqlite3
import json
from datetime import datetime, timedelta
from config import Config
from database import get_db, init_db
from court_movement import generate_next_round_pairings
from werkzeug.security import generate_password_hash, check_password_hash

# Season Management Helpers
def get_current_season(db):
    """Get the current active season, or None if no active season"""
    return db.execute(
        "SELECT * FROM seasons WHERE is_current = 1"
    ).fetchone()

def set_current_season(db, season_id):
    """Set a season as current, archiving any other current season"""
    # Archive all current seasons
    db.execute("UPDATE seasons SET is_current = 0 WHERE is_current = 1")

    # Set specified season as current and clear ended_at
    db.execute(
        "UPDATE seasons SET is_current = 1, ended_at = NULL WHERE id = ?",
        (season_id,)
    )
    db.commit()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiter (uses in-memory storage by default)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Ensure instance folder exists
os.makedirs('instance', exist_ok=True)

# Initialize database on first run
if not os.path.exists(app.config['DATABASE']):
    init_db()

# Database connection helper
def get_db_connection():
    """Get database connection, stored in Flask's g object"""
    if 'db' not in g:
        g.db = get_db()
    return g.db

@app.teardown_appcontext
def close_db(_error):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.before_request
def check_admin_session():
    """Check admin authentication and session timeout before each request"""
    # Only check for admin routes (except login and setup)
    if request.path.startswith('/admin') and request.path not in ['/admin/login', '/admin/setup']:
        # Check if logged in
        if not session.get('logged_in_as_admin'):
            return redirect('/admin/login')

        # Check 30-minute timeout
        last_activity_str = session.get('last_activity')
        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str)
            if datetime.now() - last_activity > timedelta(minutes=30):
                session.clear()
                flash('Session expired. Please log in again.')
                return redirect('/admin/login')

        # Update last activity
        session['last_activity'] = datetime.now().isoformat()

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

def format_round1_pairings_for_frontend(tournament_id, db):
    """
    Format Round 1 preview pairings for frontend consumption.

    Args:
        tournament_id: ID of tournament
        db: Database connection

    Returns:
        dict with 'pairings' and 'players' keys
    """
    # Get preview pairings from database
    pairings_raw = db.execute("""
        SELECT * FROM round1_preview_pairings
        WHERE tournament_id = ?
        ORDER BY court_number
    """, (tournament_id,)).fetchall()

    # Get all player details for this tournament
    players_raw = db.execute("""
        SELECT pr.id, pr.first_name, pr.last_name
        FROM player_registry pr
        JOIN tournament_players tp ON pr.id = tp.player_id
        WHERE tp.tournament_id = ?
    """, (tournament_id,)).fetchall()

    # Format pairings
    pairings = []
    for p in pairings_raw:
        pairings.append({
            'court': p['court_number'],
            'team1': [p['team1_player1_id'], p['team1_player2_id']],
            'team2': [p['team2_player1_id'], p['team2_player2_id']]
        })

    # Format players
    players = {}
    for p in players_raw:
        players[str(p['id'])] = {
            'first_name': p['first_name'],
            'last_name': p['last_name']
        }

    return {
        'pairings': pairings,
        'players': players
    }

def get_tournament_leaderboard(tournament_id):
    """Get player standings for a specific tournament"""
    db = get_db_connection()

    players_raw = db.execute(
        '''SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as wins,
            COUNT(DISTINCT m.id) as matches_played,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate
           FROM player_registry pr
           LEFT JOIN matches m ON (
               pr.id = m.player1_id OR
               pr.id = m.player2_id OR
               pr.id = m.player3_id OR
               pr.id = m.player4_id
           )
           LEFT JOIN rounds r ON m.round_id = r.id
           LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
           WHERE r.tournament_id = ? AND m.completed = 1
           GROUP BY pr.id, pr.first_name, pr.last_name
           HAVING matches_played > 0
           ORDER BY wins DESC, win_rate DESC, pr.last_name ASC''',
        (tournament_id,)
    ).fetchall()

    # Calculate ranks with proper tie handling
    players = []
    current_rank = 1
    for idx, player in enumerate(players_raw):
        # Update rank if this player's stats differ from previous
        if idx > 0:
            prev = players_raw[idx - 1]
            if player['wins'] != prev['wins'] or player['win_rate'] != prev['win_rate']:
                current_rank = idx + 1  # Account for gap

        # Convert row to dict and add rank
        player_dict = dict(player)
        player_dict['rank'] = current_rank
        players.append(player_dict)

    # Get tournament metadata
    tournament_info = db.execute(
        '''SELECT
            COUNT(DISTINCT r.id) as total_rounds
           FROM rounds r
           WHERE r.tournament_id = ?''',
        (tournament_id,)
    ).fetchone()

    return {
        'players': players,
        'rounds': tournament_info['total_rounds']
    }

# Routes

@app.route('/')
def index():
    """Home page - smart entry point for scorekeepers/players"""
    db = get_db()

    # Query active tournaments
    active_tournaments = db.execute(
        '''SELECT * FROM tournaments
           WHERE status = 'active'
           ORDER BY created_at DESC'''
    ).fetchall()

    # Query setup tournaments
    setup_tournaments = db.execute(
        '''SELECT * FROM tournaments
           WHERE status = 'setup'
           ORDER BY created_at DESC'''
    ).fetchall()

    active_count = len(active_tournaments)
    setup_count = len(setup_tournaments)
    total_count = active_count + setup_count

    # Case 1: Exactly 1 active tournament and no setup - auto-redirect
    if active_count == 1 and setup_count == 0:
        tournament_id = active_tournaments[0]['id']
        return redirect(url_for('active_tournament', tournament_id=tournament_id))

    # Case 2: Multiple tournaments (active or setup) - show selection
    elif total_count > 0:
        current_season = get_current_season(db)
        # Combine active and setup tournaments
        all_tournaments = list(active_tournaments) + list(setup_tournaments)
        return render_template('tournament_selection.html',
                             tournaments=all_tournaments,
                             season=current_season)

    # Case 3: No tournaments at all - show message
    else:
        current_season = get_current_season(db)

        # Get tournament count for season info
        season_info = None
        if current_season:
            tournament_count = db.execute(
                "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
                (current_season['id'],)
            ).fetchone()['count']

            # Handle both old schema (year) and new schema (name)
            season_name = current_season['name'] if 'name' in current_season.keys() else f"Season {current_season['year']}"

            season_info = {
                'name': season_name,
                'tournament_count': tournament_count
            }

        return render_template('no_active_tournament.html', season=season_info)

@app.route('/tournament/<int:tournament_id>/start_round', methods=['GET', 'POST'])
def start_round(tournament_id):
    """Generate a new round with randomized pairs"""
    db = get_db_connection()
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?', (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    if tournament['status'] == 'completed':
        flash('Turnaus on päättynyt')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Get players for this tournament only (Phase 3)
        players = db.execute(
            '''SELECT pr.id
               FROM player_registry pr
               JOIN tournament_players tp ON pr.id = tp.player_id
               WHERE tp.tournament_id = ?
               ORDER BY RANDOM()''',
            (tournament_id,)
        ).fetchall()
        num_players = len(players)
        num_courts = tournament['num_courts']

        # Validate we have enough players (4 per court)
        required_players = num_courts * 4
        if num_players < required_players:
            flash(f'Need {required_players} players for {num_courts} courts. You have {num_players}.')
            return redirect(url_for('index'))

        # Get or create current round
        last_round = db.execute(
            'SELECT * FROM rounds WHERE tournament_id = ? ORDER BY round_number DESC LIMIT 1',
            (tournament_id,)
        ).fetchone()

        # If there's a previous round (round 2+), ensure it's complete before starting new round
        if last_round:
            incomplete_matches = db.execute(
                '''SELECT COUNT(*) as count FROM matches
                   WHERE round_id = ? AND completed = 0''',
                (last_round['id'],)
            ).fetchone()

            if incomplete_matches['count'] > 0:
                flash(f'Cannot start new round: Round {last_round["round_number"]} has incomplete matches. Please complete all matches first.')
                return redirect(url_for('active_round', tournament_id=tournament_id, round_id=last_round['id']))

        round_number = 1 if not last_round else last_round['round_number'] + 1

        cursor = db.execute(
            'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
            (tournament_id, round_number)
        )
        round_id = cursor.lastrowid

        # Determine pairing strategy
        if round_number == 1:
            # Round 1: Validate and check for saved custom pairings
            pairings_valid = validate_saved_pairings_still_valid(tournament_id, db)

            if pairings_valid:
                try:
                    saved_pairings = db.execute("""
                        SELECT * FROM round1_preview_pairings
                        WHERE tournament_id = ?
                        ORDER BY court_number
                    """, (tournament_id,)).fetchall()
                except sqlite3.OperationalError:
                    # Table doesn't exist (old schema)
                    saved_pairings = []
            else:
                saved_pairings = []
                flash('⚠️ Saved Round 1 pairings were invalid - using seeded pairings', 'warning')

            if saved_pairings:
                # Use saved custom pairings
                for pairing in saved_pairings:
                    db.execute('''
                        INSERT INTO matches
                        (round_id, court_number, player1_id, player2_id,
                         player3_id, player4_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        round_id,
                        pairing['court_number'],
                        pairing['team1_player1_id'],
                        pairing['team1_player2_id'],
                        pairing['team2_player1_id'],
                        pairing['team2_player2_id']
                    ))

                # Delete used pairings
                db.execute(
                    'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
                    (tournament_id,)
                )

                flash('Round 1 started with your custom pairings!')
            else:
                # Use seeding algorithm (existing code)
                from seeded_pairing import generate_seeded_round1_pairings

                # Get players with their seed points from player_seeding view
                # Only include players registered for this tournament
                try:
                    players_with_seeds = db.execute("""
                        SELECT
                            p.id,
                            COALESCE(ps.seed_points, 0) as seed_points
                        FROM player_registry p
                        JOIN tournament_players tp ON p.id = tp.player_id
                        LEFT JOIN player_seeding ps ON p.id = ps.player_id
                        WHERE tp.tournament_id = ?
                        ORDER BY seed_points DESC
                    """, (tournament_id,)).fetchall()
                except (sqlite3.OperationalError, AttributeError):
                    # Fallback if player_seeding view doesn't exist
                    players_with_seeds = db.execute("""
                        SELECT p.id, 0 as seed_points
                        FROM player_registry p
                        JOIN tournament_players tp ON p.id = tp.player_id
                        WHERE tp.tournament_id = ?
                    """, (tournament_id,)).fetchall()

                players_with_seeds = [dict(p) for p in players_with_seeds]
                court_assignments = generate_seeded_round1_pairings(players_with_seeds, num_courts)

                # Create matches from seeded assignments
                for court_num, player_ids in enumerate(court_assignments, start=1):
                    db.execute(
                        '''INSERT INTO matches
                           (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (round_id, court_num, *player_ids)
                    )

                flash('Round 1 started with seeded pairings (based on recent performance)')
        else:
            # Round 2+: Movement-based pairing
            previous_matches = db.execute(
                '''SELECT m.* FROM matches m
                   JOIN rounds r ON m.round_id = r.id
                   WHERE r.tournament_id = ?
                   AND r.round_number = ?
                   AND m.completed = 1''',
                (tournament_id, round_number - 1)
            ).fetchall()

            # Convert to list of dicts
            previous_matches = [dict(m) for m in previous_matches]

            # Generate new pairings
            court_assignments = generate_next_round_pairings(previous_matches, num_courts)

            # Create matches from assignments
            for court_num, players_on_court in enumerate(court_assignments, start=1):
                db.execute(
                    '''INSERT INTO matches
                       (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (round_id, court_num, *players_on_court)
                )

            # Add feedback message
            flash(f'Round {round_number} started! Winners moved up, losers moved down.')

        db.commit()

        # Update tournament status to 'active' when starting Round 1
        if round_number == 1:
            db.execute(
                'UPDATE tournaments SET status = "active" WHERE id = ?',
                (tournament_id,)
            )
            db.commit()

        flash(f"Kierros {round_number} luotu!")
        return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))

    # Get current round if exists
    current_round = db.execute(
        '''SELECT * FROM rounds
           WHERE tournament_id = ? AND status = "in_progress"
           ORDER BY round_number DESC LIMIT 1''',
        (tournament_id,)
    ).fetchone()

    # Check if there's any completed match data for leaderboard
    completed_matches = db.execute(
        '''SELECT COUNT(*) as count FROM matches m
           JOIN rounds r ON m.round_id = r.id
           WHERE r.tournament_id = ? AND m.completed = 1''',
        (tournament_id,)
    ).fetchone()
    has_leaderboard_data = completed_matches['count'] > 0

    return render_template('start_round.html',
                         tournament=tournament,
                         current_round=current_round,
                         has_leaderboard_data=has_leaderboard_data)

@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm', methods=['GET', 'POST'])
def confirm_match_teams(tournament_id, round_id, court_number):
    """
    Show pre-match confirmation screen with drag-and-drop team shuffling (GET).
    Save final team configuration and proceed to score entry (POST).

    GET: Displays the 4 players assigned to this court, allowing users to
    optionally shuffle teams via drag-and-drop before starting the match.

    POST: Validates and saves the final team configuration (potentially shuffled),
    then redirects to score entry.

    Args:
        tournament_id (int): ID of the tournament
        round_id (int): ID of the round
        court_number (int): Court number for this match

    Returns:
        GET: Rendered template (confirm_match.html) with team boxes
        POST: Redirect to active_tournament (score entry) on success,
              redirect back to confirm screen with error on validation failure

    Redirects if:
        - Tournament not found
        - Tournament is archived
        - Round not found
        - Match not found
        - Match already completed
        - Scores already entered (prevents mid-match shuffle)
    """
    db = get_db_connection()

    # Check if tournament is completed
    tournament = db.execute('SELECT status FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
    if tournament and tournament['status'] == 'completed':
        flash('Turnaus on päättynyt')
        return redirect(url_for('index'))

    # Handle POST request (save shuffled teams)
    if request.method == 'POST':
        # Get match first
        match = db.execute(
            'SELECT * FROM matches WHERE round_id = ? AND court_number = ?',
            (round_id, court_number)
        ).fetchone()

        if not match:
            flash('Ottelua ei löytynyt')
            return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))

        # Get submitted team configuration
        try:
            new_team1_p1 = int(request.form['team1_player1'])
            new_team1_p2 = int(request.form['team1_player2'])
            new_team2_p1 = int(request.form['team2_player1'])
            new_team2_p2 = int(request.form['team2_player2'])
        except (KeyError, ValueError):
            flash("Invalid form submission.")
            return redirect(url_for('confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 1: Exactly 4 unique players
        submitted_players = [new_team1_p1, new_team1_p2, new_team2_p1, new_team2_p2]
        if len(set(submitted_players)) != 4:
            flash("Invalid team configuration: All 4 players must be unique.")
            return redirect(url_for('confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 2: Players must be from original match
        original_players = {match['player1_id'], match['player2_id'], match['player3_id'], match['player4_id']}
        if set(submitted_players) != original_players:
            flash("Invalid team configuration: Players must be from the original match.")
            return redirect(url_for('confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 3: Teams must have exactly 2 players each
        if len({new_team1_p1, new_team1_p2}) != 2 or len({new_team2_p1, new_team2_p2}) != 2:
            flash("Each team must have exactly 2 different players.")
            return redirect(url_for('confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Check if teams were shuffled
        original_team1 = {match['player1_id'], match['player2_id']}
        new_team1 = {new_team1_p1, new_team1_p2}
        teams_changed = original_team1 != new_team1

        if teams_changed:
            # Store original pairing before overwriting
            db.execute('''
                UPDATE matches
                SET original_player1_id = ?,
                    original_player2_id = ?,
                    original_player3_id = ?,
                    original_player4_id = ?,
                    teams_shuffled = 1,
                    player1_id = ?,
                    player2_id = ?,
                    player3_id = ?,
                    player4_id = ?
                WHERE id = ?
            ''', (
                match['player1_id'], match['player2_id'], match['player3_id'], match['player4_id'],
                new_team1_p1, new_team1_p2, new_team2_p1, new_team2_p2,
                match['id']
            ))
            db.commit()

        # Redirect to score entry screen for this match
        return redirect(url_for('score_entry', match_id=match['id']))

    # Handle GET request (show confirmation screen)
    # Get tournament
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Check if tournament is archived
    if tournament['status'] == 'archived':
        flash("Cannot modify archived tournament.")
        return redirect(url_for('index'))

    # Get round
    round_obj = db.execute(
        'SELECT * FROM rounds WHERE id = ?',
        (round_id,)
    ).fetchone()

    if not round_obj:
        flash('Round not found')
        return redirect(url_for('index'))

    # Validate round belongs to tournament
    if round_obj['tournament_id'] != tournament_id:
        flash('Round not found in this tournament')
        return redirect(url_for('index'))

    # Get match
    match = db.execute(
        'SELECT * FROM matches WHERE round_id = ? AND court_number = ?',
        (round_id, court_number)
    ).fetchone()

    if not match:
        flash('Match not found')
        return redirect(url_for('index'))

    # Check if match already completed
    if match['completed']:
        flash("This match has already been completed.")
        return redirect(url_for('leaderboard', tournament_id=tournament_id))

    # Check if scores already entered (prevent shuffle after scoring starts)
    existing_scores = db.execute(
        'SELECT COUNT(*) as count FROM scores WHERE match_id = ?',
        (match['id'],)
    ).fetchone()

    if existing_scores['count'] > 0:
        flash("Match already in progress. Team shuffling not available.")
        # Redirect to active tournament scoring
        return redirect(url_for('active_tournament', tournament_id=tournament_id))

    # Get player details
    players = {
        'team1': [
            get_player(match['player1_id']),
            get_player(match['player2_id'])
        ],
        'team2': [
            get_player(match['player3_id']),
            get_player(match['player4_id'])
        ]
    }

    return render_template(
        'confirm_match.html',
        tournament=tournament,
        round=round_obj,
        court_number=court_number,
        match=match,
        players=players
    )

@app.route('/tournament/<int:tournament_id>')
def active_tournament(tournament_id):
    """Show active round for tournament"""
    db = get_db_connection()

    # Get current round
    current_round = db.execute(
        '''SELECT * FROM rounds
           WHERE tournament_id = ? AND status = "in_progress"
           ORDER BY round_number DESC LIMIT 1''',
        (tournament_id,)
    ).fetchone()

    if not current_round:
        return redirect(url_for('start_round', tournament_id=tournament_id))

    return redirect(url_for('active_round',
                           tournament_id=tournament_id,
                           round_id=current_round['id']))

@app.route('/tournament/<int:tournament_id>/round/<int:round_id>')
def active_round(tournament_id, round_id):
    """Display all matches in current round"""
    db = get_db_connection()

    tournament = db.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
    round_data = db.execute('SELECT * FROM rounds WHERE id = ?', (round_id,)).fetchone()

    if not round_data:
        flash('Round not found')
        return redirect(url_for('index'))

    if tournament and tournament['status'] == 'completed':
        flash('Turnaus on päättynyt')
        return redirect(url_for('index'))

    # Get all matches (without player names - we'll add them below)
    matches_raw = db.execute(
        '''SELECT m.*
           FROM matches m
           WHERE m.round_id = ?
           ORDER BY m.court_number''',
        (round_id,)
    ).fetchall()

    # Add player names using helper function (Phase 3 compatible)
    matches = []
    for match in matches_raw:
        match_dict = dict(match)
        player1 = get_player(match_dict['player1_id'])
        player2 = get_player(match_dict['player2_id'])
        player3 = get_player(match_dict['player3_id'])
        player4 = get_player(match_dict['player4_id'])
        match_dict['player1_name'] = f"{player1['first_name']} {player1['last_name']}"
        match_dict['player2_name'] = f"{player2['first_name']} {player2['last_name']}"
        match_dict['player3_name'] = f"{player3['first_name']} {player3['last_name']}"
        match_dict['player4_name'] = f"{player4['first_name']} {player4['last_name']}"
        matches.append(match_dict)

    # Check if all matches are completed
    all_completed = all(match['completed'] for match in matches)

    return render_template('active_round.html',
                          tournament_id=tournament_id,
                          tournament=tournament,
                          round_data=round_data,
                          matches=matches,
                          all_completed=all_completed)

@app.route('/match/<int:match_id>/score', methods=['GET', 'POST'])
def score_entry(match_id):
    """Simple form for winners to enter their win"""
    db = get_db_connection()

    match = db.execute(
        '''SELECT m.*, r.tournament_id
           FROM matches m
           JOIN rounds r ON m.round_id = r.id
           WHERE m.id = ?''',
        (match_id,)
    ).fetchone()

    if not match:
        flash('Match not found')
        return redirect(url_for('index'))

    # Check if tournament is completed
    tournament = db.execute('SELECT status FROM tournaments WHERE id = ?', (match['tournament_id'],)).fetchone()
    if tournament and tournament['status'] == 'completed':
        flash('Turnaus on päättynyt')
        return redirect(url_for('index'))

    # Get player details using helper function (Phase 3 compatible)
    match = dict(match)
    player1 = get_player(match['player1_id'])
    player2 = get_player(match['player2_id'])
    player3 = get_player(match['player3_id'])
    player4 = get_player(match['player4_id'])
    match['player1_name'] = f"{player1['first_name']} {player1['last_name']}"
    match['player2_name'] = f"{player2['first_name']} {player2['last_name']}"
    match['player3_name'] = f"{player3['first_name']} {player3['last_name']}"
    match['player4_name'] = f"{player4['first_name']} {player4['last_name']}"

    if request.method == 'POST':
        winning_team = int(request.form.get('winning_team'))
        submitted_version = int(request.form.get('version', 0))

        # Check for concurrent modification (optimistic locking)
        current_match = db.execute(
            'SELECT version FROM matches WHERE id = ?', (match_id,)
        ).fetchone()
        current_version = current_match['version'] if current_match and current_match['version'] else 1

        if submitted_version != current_version:
            # Return 409 Conflict for AJAX requests
            return jsonify({'error': 'version_conflict', 'message': 'Joku muu on muokannut tätä ottelua.'}), 409

        # Determine winners
        if winning_team == 1:
            winner_ids = [match['player1_id'], match['player2_id']]
            loser_ids = [match['player3_id'], match['player4_id']]
        else:
            winner_ids = [match['player3_id'], match['player4_id']]
            loser_ids = [match['player1_id'], match['player2_id']]

        if match['completed']:
            # Update existing scores
            # Delete old scores and insert new ones
            db.execute('DELETE FROM scores WHERE match_id = ?', (match_id,))
            for player_id in winner_ids:
                db.execute(
                    'INSERT INTO scores (player_id, match_id, points) VALUES (?, ?, ?)',
                    (player_id, match_id, 1)
                )
            flash('Tulos päivitetty!')
        else:
            # Record new scores (1 point for winners)
            for player_id in winner_ids:
                db.execute(
                    'INSERT INTO scores (player_id, match_id, points) VALUES (?, ?, ?)',
                    (player_id, match_id, 1)
                )
            flash('Tulos tallennettu!')

        # Mark match as completed and increment version
        db.execute(
            'UPDATE matches SET completed = 1, winning_team = ?, version = ? WHERE id = ?',
            (winning_team, current_version + 1, match_id)
        )

        db.commit()

        return redirect(url_for('active_round',
                               tournament_id=match['tournament_id'],
                               round_id=match['round_id']))

    return render_template('score_entry.html', match=match)

@app.route('/tournament/<int:tournament_id>/end', methods=['POST'])
def end_tournament(tournament_id):
    """End tournament and mark as completed"""
    db = get_db_connection()

    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Update status to completed
    db.execute(
        'UPDATE tournaments SET status = ? WHERE id = ?',
        ('completed', tournament_id)
    )
    db.commit()

    flash('Turnaus päättyi!')
    return redirect(url_for('admin_dashboard'))

@app.route('/tournament/<int:tournament_id>/leaderboard')
def leaderboard(tournament_id):
    """Show current standings"""
    db = get_db_connection()

    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?', (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Get tournament metadata (total rounds)
    tournament_stats = db.execute(
        '''SELECT
            COUNT(DISTINCT r.id) as total_rounds
           FROM rounds r
           WHERE r.tournament_id = ?''',
        (tournament_id,)
    ).fetchone()

    # Get all players with their match statistics (Phase 3)
    players_raw = db.execute(
        '''SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as wins,
            COUNT(DISTINCT m.id) as matches_played,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate
           FROM player_registry pr
           LEFT JOIN matches m ON (
               pr.id = m.player1_id OR
               pr.id = m.player2_id OR
               pr.id = m.player3_id OR
               pr.id = m.player4_id
           )
           LEFT JOIN rounds r ON m.round_id = r.id
           LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
           WHERE r.tournament_id = ? AND m.completed = 1
           GROUP BY pr.id, pr.first_name, pr.last_name
           ORDER BY wins DESC, win_rate DESC, pr.last_name ASC''',
        (tournament_id,)
    ).fetchall()

    # Calculate ranks with proper tie handling
    players = []
    current_rank = 1
    for idx, player in enumerate(players_raw):
        # Update rank if this player's stats differ from previous
        if idx > 0:
            prev = players_raw[idx - 1]
            if player['wins'] != prev['wins'] or player['win_rate'] != prev['win_rate']:
                current_rank = idx + 1  # Account for gap

        # Convert row to dict and add rank
        player_dict = dict(player)
        player_dict['rank'] = current_rank
        players.append(player_dict)

    return render_template('leaderboard.html',
                          tournament=tournament,
                          tournament_stats=tournament_stats,
                          players=players)

@app.route('/leaderboard/season')
def season_leaderboard():
    """Display season leaderboard for current season"""
    db = get_db_connection()

    # Get current season
    current_season = get_current_season(db)
    if not current_season:
        return render_template('season_leaderboard.html',
                             season_name='No Current Season',
                             no_season=True,
                             tournaments=[],
                             leaderboard=[],
                             tournament_count=0,
                             has_previous_seasons=False)

    # Get tournaments from current season only
    tournaments = db.execute("""
        SELECT * FROM tournaments
        WHERE season_id = ?
        ORDER BY created_at DESC
    """, (current_season['id'],)).fetchall()

    # Get leaderboard (existing logic, but filter by current season)
    # Sort by total_points first, then win_rate for tiebreaker
    # Includes admin adjustments from player_points_adjustment table
    season_stats_raw = db.execute("""
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
            COUNT(DISTINCT m.id) as total_matches,
            COUNT(DISTINCT t.id) as total_tournaments,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate,
            COALESCE(SUM(s.points), 0) + COALESCE(adj.adjustment, 0) as total_points
        FROM player_registry pr
        LEFT JOIN matches m ON (
            pr.id = m.player1_id OR
            pr.id = m.player2_id OR
            pr.id = m.player3_id OR
            pr.id = m.player4_id
        )
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
        WHERE t.season_id = ?
          AND m.completed = 1
        GROUP BY pr.id, pr.first_name, pr.last_name
        HAVING total_matches > 0
        ORDER BY total_points DESC, win_rate DESC, pr.last_name ASC
    """, (current_season['id'], current_season['id'])).fetchall()

    # Calculate ranks with proper tie handling
    season_stats = []
    current_rank = 1
    for idx, player in enumerate(season_stats_raw):
        # Update rank if this player's stats differ from previous
        if idx > 0:
            prev = season_stats_raw[idx - 1]
            if player['total_points'] != prev['total_points'] or player['win_rate'] != prev['win_rate']:
                current_rank = idx + 1  # Account for gap

        # Convert row to dict and add rank
        player_dict = dict(player)
        player_dict['rank'] = current_rank
        season_stats.append(player_dict)

    # For each tournament, get its leaderboard
    tournaments_with_stats = []
    for tournament in tournaments:
        tournament_stats = get_tournament_leaderboard(tournament['id'])
        tournaments_with_stats.append({
            'tournament': tournament,
            'stats': tournament_stats
        })

    tournament_count = len(tournaments)

    # Check if there are any previous seasons (archived seasons)
    has_previous_seasons = db.execute(
        "SELECT COUNT(*) as count FROM seasons WHERE is_current = 0"
    ).fetchone()['count'] > 0

    # Handle both old schema (year) and new schema (name)
    season_name = current_season['name'] if 'name' in current_season.keys() else f"Season {current_season['year']}"

    return render_template('season_leaderboard.html',
                          season_name=season_name,
                          no_season=False,
                          season_stats=season_stats,
                          tournaments=tournaments_with_stats,
                          tournament_count=tournament_count,
                          has_previous_seasons=has_previous_seasons)

@app.route('/leaderboard/history')
def season_history():
    """Display historical season data for archived seasons"""
    db = get_db_connection()

    # Get all archived seasons (not current)
    archived_seasons = db.execute("""
        SELECT * FROM seasons
        WHERE is_current = 0
        ORDER BY ended_at DESC, created_at DESC
    """).fetchall()

    # For each season, get tournaments and leaderboard
    seasons_data = []
    for season in archived_seasons:
        tournaments = db.execute("""
            SELECT * FROM tournaments
            WHERE season_id = ?
            ORDER BY created_at ASC
        """, (season['id'],)).fetchall()

        season_stats = db.execute("""
            SELECT
                pr.id,
                pr.first_name,
                pr.last_name,
                COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
                COUNT(DISTINCT m.id) as total_matches,
                ROUND(
                    CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                    NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                    1
                ) as win_rate,
                COALESCE(SUM(s.points), 0) as total_points
            FROM player_registry pr
            LEFT JOIN matches m ON (
                pr.id = m.player1_id OR
                pr.id = m.player2_id OR
                pr.id = m.player3_id OR
                pr.id = m.player4_id
            )
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
            WHERE t.season_id = ?
              AND m.completed = 1
            GROUP BY pr.id, pr.first_name, pr.last_name
            HAVING total_matches > 0
            ORDER BY total_points DESC, win_rate DESC, pr.last_name ASC
        """, (season['id'],)).fetchall()

        # For each tournament, get its leaderboard
        tournaments_with_stats = []
        for tournament in tournaments:
            tournament_stats = get_tournament_leaderboard(tournament['id'])
            tournaments_with_stats.append({
                'tournament': tournament,
                'stats': tournament_stats
            })

        seasons_data.append({
            'season': season,
            'season_stats': season_stats,
            'tournaments': tournaments_with_stats,
            'tournament_count': len(tournaments)
        })

    return render_template('season_history.html',
                         seasons_data=seasons_data,
                         has_previous_seasons=len(archived_seasons) > 0)

@app.route('/leaderboard/clear-all', methods=['POST'])
def clear_all_data():
    """Clear all tournament and player data - complete reset (admin only)"""
    # Require admin authentication
    if not session.get('logged_in_as_admin'):
        flash('Vain ylläpitäjä voi tyhjentää datan')
        return redirect(url_for('admin_login'))

    db = get_db_connection()

    # Delete in correct order (foreign key constraints)
    db.execute('DELETE FROM scores')
    db.execute('DELETE FROM matches')
    db.execute('DELETE FROM rounds')
    db.execute('DELETE FROM tournaments')
    db.execute('DELETE FROM player_registry')

    # Reset auto-increment counters
    db.execute('''DELETE FROM sqlite_sequence
                  WHERE name IN ('tournaments', 'rounds', 'matches', 'scores', 'player_registry')''')

    db.commit()

    flash('All data cleared successfully! Starting fresh season.')
    return redirect(url_for('index'))

@app.route('/player/<int:player_id>/profile')
def player_profile(player_id):
    """Display player profile with current season statistics"""
    db = get_db_connection()

    # Get player from registry
    player = db.execute(
        'SELECT * FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if not player:
        flash('Player not found')
        return redirect(url_for('index'))

    # Get current season
    current_season = get_current_season(db)
    if not current_season:
        # No current season - show player with no data
        return render_template(
            'player_profile.html',
            player=player,
            season_stats=None,
            season_name='No Current Season',
            rank=None
        )

    current_year = datetime.now().year

    # Get season stats for this player
    # Using same query logic as season_leaderboard route
    season_stats = db.execute("""
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
            COUNT(DISTINCT m.id) as total_matches,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate,
            SUM(s.points) as total_points,
            COUNT(DISTINCT t.id) as tournaments_played
        FROM player_registry pr
        LEFT JOIN matches m ON (
            pr.id = m.player1_id OR
            pr.id = m.player2_id OR
            pr.id = m.player3_id OR
            pr.id = m.player4_id
        )
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE pr.id = ?
          AND t.season_id = ?
          AND m.completed = 1
        GROUP BY pr.id, pr.first_name, pr.last_name
    """, (player_id, current_season['id'])).fetchone()

    # Calculate wins per tournament
    wins_per_tournament = None
    if season_stats and season_stats['total_wins'] and season_stats['tournaments_played']:
        wins_per_tournament = round(
            season_stats['total_wins'] / season_stats['tournaments_played'], 2
        )

    # Calculate rank with proper handling of ties and gaps
    # Rules: 1) Sort by total_points DESC, then win_rate DESC
    #        2) If both points and win_rate equal, players share rank
    #        3) Next rank after tied players accounts for gap (e.g., 3 at rank 1 → next is rank 4)
    rank = None
    if season_stats and season_stats['total_points'] > 0:
        all_standings = db.execute("""
            SELECT
                pr.id,
                COALESCE(SUM(s.points), 0) as total_points,
                ROUND(
                    CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                    NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                    1
                ) as win_rate
            FROM player_registry pr
            LEFT JOIN matches m ON (
                pr.id = m.player1_id OR
                pr.id = m.player2_id OR
                pr.id = m.player3_id OR
                pr.id = m.player4_id
            )
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
            WHERE t.season_id = ?
              AND m.completed = 1
            GROUP BY pr.id
            HAVING COALESCE(SUM(s.points), 0) > 0
            ORDER BY total_points DESC, win_rate DESC
        """, (current_season['id'],)).fetchall()

        # Calculate rank with proper tie handling
        current_rank = 1
        for idx, row in enumerate(all_standings):
            # Update rank if this player's stats differ from previous
            if idx > 0:
                prev = all_standings[idx - 1]
                if row['total_points'] != prev['total_points'] or row['win_rate'] != prev['win_rate']:
                    current_rank = idx + 1  # Account for gap

            if row['id'] == player_id:
                rank = current_rank
                break

    # Handle both old schema (year) and new schema (name)
    season_name = current_season['name'] if 'name' in current_season.keys() else f"Season {current_season['year']}"

    return render_template(
        'player_profile.html',
        player=player,
        season_stats=season_stats,
        season_name=season_name,
        current_year=current_year,
        rank=rank,
        wins_per_tournament=wins_per_tournament
    )

@app.route('/tournament/<int:tournament_id>/complete', methods=['POST'])
def complete_tournament(tournament_id):
    """Complete a tournament - calculate final stats and set status to completed"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Verify tournament exists and is active
        cursor.execute('''
            SELECT status FROM tournaments WHERE id = ?
        ''', (tournament_id,))
        result = cursor.fetchone()

        if not result:
            flash('Tournament not found', 'error')
            return redirect(url_for('index'))

        if result['status'] != 'active':
            flash(f'Cannot complete tournament with status: {result["status"]}', 'error')
            return redirect(url_for('active_tournament', tournament_id=tournament_id))

        # Calculate final statistics for each player
        # Get all players who participated in this tournament
        cursor.execute('''
            SELECT DISTINCT pr.id as registry_id
            FROM player_registry pr
            JOIN matches m ON (pr.id = m.player1_id OR pr.id = m.player2_id
                              OR pr.id = m.player3_id OR pr.id = m.player4_id)
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = ?
        ''', (tournament_id,))
        tournament_players_list = cursor.fetchall()

        for player in tournament_players_list:
            registry_id = player['registry_id']

            # Count wins and losses
            cursor.execute('''
                SELECT
                    COUNT(*) as total_matches,
                    SUM(CASE
                        WHEN (m.player1_id = ? OR m.player2_id = ?) AND m.winning_team = 1 THEN 1
                        WHEN (m.player3_id = ? OR m.player4_id = ?) AND m.winning_team = 2 THEN 1
                        ELSE 0
                    END) as wins
                FROM matches m
                JOIN rounds r ON m.round_id = r.id
                WHERE r.tournament_id = ?
                  AND (m.player1_id = ? OR m.player2_id = ?
                       OR m.player3_id = ? OR m.player4_id = ?)
                  AND m.winning_team IS NOT NULL
            ''', (registry_id, registry_id, registry_id, registry_id, tournament_id,
                  registry_id, registry_id, registry_id, registry_id))

            stats = cursor.fetchone()
            match_wins = stats['wins'] or 0
            total_matches = stats['total_matches'] or 0
            match_losses = total_matches - match_wins
            total_points = match_wins  # Simple scoring: 1 point per win

            # Insert or update tournament_players record
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tournament_id, player_id)
                DO UPDATE SET
                    total_points = excluded.total_points,
                    match_wins = excluded.match_wins,
                    match_losses = excluded.match_losses
            ''', (tournament_id, registry_id, total_points, match_wins, match_losses))

        # Calculate rankings based on total_points (wins)
        cursor.execute('''
            SELECT player_id, total_points
            FROM tournament_players
            WHERE tournament_id = ?
            ORDER BY total_points DESC, player_id ASC
        ''', (tournament_id,))

        ranked_players = cursor.fetchall()
        current_rank = 1
        previous_points = None

        for idx, player_row in enumerate(ranked_players):
            # If points changed from previous player, update rank
            if previous_points is not None and player_row['total_points'] != previous_points:
                current_rank = idx + 1

            cursor.execute('''
                UPDATE tournament_players
                SET final_rank = ?
                WHERE tournament_id = ? AND player_id = ?
            ''', (current_rank, tournament_id, player_row['player_id']))

            previous_points = player_row['total_points']

        # Update tournament status to completed
        cursor.execute('''
            UPDATE tournaments
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tournament_id,))

        db.commit()
        flash('Tournament completed successfully!', 'success')
        return redirect(url_for('active_tournament', tournament_id=tournament_id))

    except Exception as e:
        db.rollback()
        flash(f'Error completing tournament: {e}', 'error')
        return redirect(url_for('active_tournament', tournament_id=tournament_id))
    finally:
        db.close()

@app.route('/tournament/<int:tournament_id>/archive', methods=['POST'])
def archive_tournament(tournament_id):
    """Archive a completed tournament - set status to archived"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Verify tournament exists and is completed
        cursor.execute('''
            SELECT status FROM tournaments WHERE id = ?
        ''', (tournament_id,))
        result = cursor.fetchone()

        if not result:
            flash('Tournament not found', 'error')
            return redirect(url_for('index'))

        if result['status'] != 'completed':
            flash(f'Cannot archive tournament with status: {result["status"]}', 'error')
            return redirect(url_for('active_tournament', tournament_id=tournament_id))

        # Update tournament status to archived
        cursor.execute('''
            UPDATE tournaments
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tournament_id,))

        db.commit()
        flash('Tournament archived successfully!', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        db.rollback()
        flash(f'Error archiving tournament: {e}', 'error')
        return redirect(url_for('active_tournament', tournament_id=tournament_id))
    finally:
        db.close()

@app.route('/tournament/<int:tournament_id>/results')
def tournament_results(tournament_id):
    """Display tournament results and final standings"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get tournament info
        cursor.execute('''
            SELECT * FROM tournaments WHERE id = ?
        ''', (tournament_id,))
        tournament = cursor.fetchone()

        if not tournament:
            flash('Tournament not found', 'error')
            return redirect(url_for('index'))

        # Get final standings from tournament_players
        cursor.execute('''
            SELECT
                tp.final_rank,
                pr.first_name,
                pr.last_name,
                tp.total_points,
                tp.match_wins,
                tp.match_losses
            FROM tournament_players tp
            JOIN player_registry pr ON tp.player_id = pr.id
            WHERE tp.tournament_id = ?
            ORDER BY tp.final_rank ASC NULLS LAST, tp.total_points DESC
        ''', (tournament_id,))
        standings = cursor.fetchall()

        return render_template('tournament_results.html',
                             tournament=tournament,
                             standings=standings)
    finally:
        db.close()

@app.route('/player/create', methods=['POST'])
def create_player():
    """Create a new player in the registry"""
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not first_name or not last_name:
        flash("First name and last name are required")
        return redirect(request.referrer or '/')

    db = get_db()

    # Check for duplicate
    existing = db.execute(
        "SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?",
        (first_name, last_name)
    ).fetchone()

    if existing:
        flash(f"⚠️ {first_name} {last_name} already exists in registry")
        return redirect('/players')

    # Create new player
    db.execute(
        "INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
        (first_name, last_name)
    )
    db.commit()

    flash(f"✅ Added {first_name} {last_name} to player registry")
    return redirect('/players')


@app.route('/players')
def players_list():
    """Show all players in registry"""
    db = get_db()
    players = db.execute("""
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            ps.seed_points,
            ps.recent_tournaments
        FROM player_registry pr
        LEFT JOIN player_seeding ps ON pr.id = ps.player_id
        ORDER BY ps.seed_points DESC, pr.last_name ASC, pr.first_name ASC
    """).fetchall()

    return render_template('players_list.html', players=players)

# ============================================================
# SEASON MANAGEMENT ROUTES
# ============================================================

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    """First-run admin setup page"""
    db = get_db()

    # Check if admin already exists
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if admin:
        return redirect('/admin/login')

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return render_template('admin_setup.html')

        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('admin_setup.html')

        # Create admin user
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (password_hash,)
        )
        db.commit()

        flash('Admin account created successfully! Please log in.')
        return redirect('/admin/login')

    return render_template('admin_setup.html')


@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])  # Brute force protection
def admin_login():
    """Admin login page"""
    db = get_db()

    # Check if admin exists, redirect to setup if not
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if not admin:
        return redirect('/admin/setup')

    if request.method == 'POST':
        password = request.form.get('password', '')

        # Get admin password hash
        admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()

        if admin and check_password_hash(admin['password_hash'], password):
            # Set session
            session['logged_in_as_admin'] = True
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            return redirect('/admin')
        else:
            flash('Invalid password')
            return render_template('admin_login.html')

    return render_template('admin_login.html')


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per hour", methods=["POST"])  # Prevent password reset abuse
def admin_forgot_password():
    """Handle forgot password - generate temp password and email it"""
    import secrets
    import string
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if request.method == 'POST':
        db = get_db()

        # Check if admin exists
        admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
        if not admin:
            flash('No admin account found. Please complete setup first.')
            return redirect('/admin/setup')

        # Generate random 12-character temporary password
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        # Hash and update password in database
        password_hash = generate_password_hash(temp_password, method='pbkdf2:sha256')
        db.execute(
            'UPDATE admin_users SET password_hash = ? WHERE id = ?',
            (password_hash, admin['id'])
        )
        db.commit()

        # Send email with temporary password
        try:
            recipient_email = "teemu.sevon@gmail.com"

            msg = MIMEMultipart()
            msg['From'] = "Tennis Scorer Admin"
            msg['To'] = recipient_email
            msg['Subject'] = "Tennis Scorer - Admin Password Reset"

            body = f"""
Hello,

Your admin password has been reset.

Your new temporary password is: {temp_password}

Please log in with this password and consider changing it to something memorable.

Best regards,
Tennis Scorer System
            """

            msg.attach(MIMEText(body, 'plain'))

            # Note: For production, you'd configure SMTP settings
            # For now, we'll just show success without actually sending
            # To enable email, configure environment variables for SMTP

            flash('Temporary password has been generated. Check your email at teemu.sevon@gmail.com')
            flash(f'For testing: Your temporary password is: {temp_password}', 'success')
            return redirect('/admin/login')

        except Exception as e:
            flash(f'Error sending email: {str(e)}')
            flash(f'Your temporary password is: {temp_password}', 'success')
            return redirect('/admin/login')

    return render_template('admin_forgot_password.html')


@app.route('/admin/seasons/end-current', methods=['POST'])
def admin_end_current_season():
    """End the current season without creating a new one (ADMIN)"""
    db = get_db()

    current_season = get_current_season(db)
    if not current_season:
        flash('No current season to end')
        return redirect('/admin')

    from datetime import datetime
    db.execute(
        "UPDATE seasons SET is_current = 0, ended_at = ? WHERE id = ?",
        (datetime.now(), current_season['id'])
    )
    db.commit()

    # Handle both old schema (year) and new schema (name)
    season_name = current_season['name'] if 'name' in current_season.keys() else f"Season {current_season['year']}"
    flash(f"Season '{season_name}' has been ended")
    return redirect('/admin')


@app.route('/admin/seasons/create', methods=['POST'])
def admin_create_season():
    """Create a new season and make it current (ADMIN)"""
    db = get_db()
    season_name = request.form.get('season_name', '').strip()

    # Validation
    if not season_name:
        flash('Season name is required')
        return redirect('/admin')

    if len(season_name) > 100:
        flash('Season name must be 100 characters or less')
        return redirect('/admin')

    # Check for duplicate
    existing = db.execute(
        "SELECT id FROM seasons WHERE name = ?", (season_name,)
    ).fetchone()

    if existing:
        flash('Season name already exists. Please choose a different name.')
        return redirect('/admin')

    # Archive current season if exists
    db.execute("UPDATE seasons SET is_current = 0 WHERE is_current = 1")

    # Create new season
    db.execute(
        "INSERT INTO seasons (name, is_current) VALUES (?, 1)",
        (season_name,)
    )
    db.commit()

    flash(f"Season '{season_name}' created successfully!")
    return redirect('/admin')


@app.route('/admin/seasons/<int:season_id>/activate', methods=['POST'])
def admin_activate_season(season_id):
    """Reactivate an archived season as the current season (ADMIN)"""
    db = get_db()

    season = db.execute(
        "SELECT * FROM seasons WHERE id = ?", (season_id,)
    ).fetchone()

    if not season:
        flash('Season not found')
        return redirect('/admin')

    set_current_season(db, season_id)

    # Handle both old schema (year) and new schema (name)
    season_name = season['name'] if 'name' in season.keys() else f"Season {season['year']}"
    flash(f"Season '{season_name}' is now active")
    return redirect('/admin')


@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page with season management"""
    db = get_db()

    # Check if we should keep a tournament edit form open
    edit_tournament_id = request.args.get('edit', type=int)

    # Get current season
    current_season = get_current_season(db)

    # Get archived seasons with tournament counts
    archived_seasons = db.execute("""
        SELECT
            s.*,
            COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON s.id = t.season_id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.ended_at DESC, s.created_at DESC
    """).fetchall()

    # Get tournament count for current season
    current_tournament_count = 0
    current_season_tournaments = []
    players = []
    if current_season:
        current_tournament_count = db.execute(
            "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']

        # Fetch tournaments for current season
        current_season_tournaments = db.execute(
            "SELECT * FROM tournaments WHERE season_id = ? ORDER BY created_at DESC",
            (current_season['id'],)
        ).fetchall()

        # Fetch players with season points for Players tab
        # Uses same query logic as season_leaderboard (scores table)
        players = db.execute('''
            SELECT
                pr.id,
                pr.first_name,
                pr.last_name,
                COALESCE(auto.auto_points, 0) as auto_points,
                COALESCE(adj.adjustment, 0) as adjustment,
                COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as total_points
            FROM player_registry pr
            LEFT JOIN (
                SELECT pr2.id as player_id, COALESCE(SUM(s.points), 0) as auto_points
                FROM player_registry pr2
                LEFT JOIN matches m ON (pr2.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id))
                LEFT JOIN rounds r ON m.round_id = r.id
                LEFT JOIN tournaments t ON r.tournament_id = t.id
                LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr2.id)
                WHERE t.season_id = ? AND m.completed = 1
                GROUP BY pr2.id
            ) auto ON pr.id = auto.player_id
            LEFT JOIN player_points_adjustment adj
                ON pr.id = adj.player_id AND adj.season_id = ?
            WHERE auto.auto_points > 0 OR adj.adjustment IS NOT NULL
            ORDER BY total_points DESC, pr.last_name ASC
        ''', (current_season['id'], current_season['id'])).fetchall()

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          current_season_tournaments=current_season_tournaments,
                          players=players,
                          archived_seasons=archived_seasons,
                          active_tab='seasons',
                          edit_tournament_id=edit_tournament_id)


@app.route('/admin/export/season-standings.csv')
def admin_export_season_standings():
    """Export current season standings as CSV for Google Sheets"""
    db = get_db()

    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta vietäväksi')
        return redirect(url_for('admin_dashboard'))

    # Get players with season points (same query as admin_dashboard)
    players = db.execute('''
        SELECT
            pr.first_name,
            pr.last_name,
            COALESCE(auto.auto_points, 0) as auto_points,
            COALESCE(adj.adjustment, 0) as adjustment,
            COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as total_points
        FROM player_registry pr
        LEFT JOIN (
            SELECT pr2.id as player_id, COALESCE(SUM(s.points), 0) as auto_points
            FROM player_registry pr2
            LEFT JOIN matches m ON (pr2.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id))
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr2.id)
            WHERE t.season_id = ? AND m.completed = 1
            GROUP BY pr2.id
        ) auto ON pr.id = auto.player_id
        LEFT JOIN player_points_adjustment adj
            ON pr.id = adj.player_id AND adj.season_id = ?
        WHERE auto.auto_points > 0 OR adj.adjustment IS NOT NULL
        ORDER BY total_points DESC, pr.last_name ASC
    ''', (current_season['id'], current_season['id'])).fetchall()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Sija', 'Pelaaja', 'Pisteet', 'Korjaus'])

    # Data rows with ranking
    for rank, player in enumerate(players, 1):
        full_name = f"{player['first_name']} {player['last_name']}"
        writer.writerow([
            rank,
            full_name,
            player['total_points'],
            player['adjustment'] if player['adjustment'] != 0 else ''
        ])

    # Prepare response
    output.seek(0)
    filename = f"{current_season['name'].replace(' ', '_')}_standings.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/players')
def admin_players():
    """Admin players tab - view and edit player season points"""
    db = get_db()

    # Get current season
    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta')
        return redirect('/admin')

    # Get all players with their season points (auto + adjustment)
    # Uses same query logic as season_leaderboard (scores table)
    players = db.execute('''
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COALESCE(auto.auto_points, 0) as auto_points,
            COALESCE(adj.adjustment, 0) as adjustment,
            COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as total_points
        FROM player_registry pr
        LEFT JOIN (
            SELECT pr2.id as player_id, COALESCE(SUM(s.points), 0) as auto_points
            FROM player_registry pr2
            LEFT JOIN matches m ON (pr2.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id))
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr2.id)
            WHERE t.season_id = ? AND m.completed = 1
            GROUP BY pr2.id
        ) auto ON pr.id = auto.player_id
        LEFT JOIN player_points_adjustment adj
            ON pr.id = adj.player_id AND adj.season_id = ?
        WHERE auto.auto_points > 0 OR adj.adjustment IS NOT NULL
        ORDER BY total_points DESC, pr.last_name ASC
    ''', (current_season['id'], current_season['id'])).fetchall()

    # Get archived seasons for sidebar
    archived_seasons = db.execute("""
        SELECT s.*, COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON s.id = t.season_id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.ended_at DESC
    """).fetchall()

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          players=players,
                          archived_seasons=archived_seasons,
                          active_tab='players')


@app.route('/admin/players/<int:player_id>/edit', methods=['POST'])
def admin_edit_player_points(player_id):
    """Edit player season points (admin only)"""
    db = get_db()

    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta')
        return redirect('/admin')

    try:
        new_total = int(request.form.get('new_total_points', 0))
    except ValueError:
        flash('Virheellinen pistemäärä')
        return redirect('/admin/players')

    # Get player's current auto points (from scores table, same as season_leaderboard)
    auto_result = db.execute('''
        SELECT COALESCE(SUM(s.points), 0) as auto_points
        FROM matches m
        JOIN rounds r ON m.round_id = r.id
        JOIN tournaments t ON r.tournament_id = t.id
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = ?)
        WHERE (? IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id))
          AND t.season_id = ?
          AND m.completed = 1
    ''', (player_id, player_id, current_season['id'])).fetchone()

    auto_points = auto_result['auto_points'] if auto_result else 0
    adjustment = new_total - auto_points

    # Insert or update adjustment
    db.execute('''
        INSERT INTO player_points_adjustment (player_id, season_id, adjustment, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(player_id, season_id)
        DO UPDATE SET adjustment = ?, updated_at = CURRENT_TIMESTAMP
    ''', (player_id, current_season['id'], adjustment, adjustment))

    db.commit()

    # Get player name for flash message
    player = db.execute('SELECT first_name, last_name FROM player_registry WHERE id = ?', (player_id,)).fetchone()
    flash(f'Pisteet päivitetty: {player["first_name"]} {player["last_name"]} = {new_total}')

    return redirect('/admin/players')


@app.route('/admin/validate-players', methods=['POST'])
def admin_validate_players():
    """Validate player names against registry (AJAX endpoint)"""
    from player_validation import validate_player_names

    data = request.get_json()
    if not data or 'players' not in data:
        return jsonify({'error': 'No players provided'}), 400

    players_text = data['players']
    player_names = [line.strip() for line in players_text.split('\n') if line.strip()]

    # Get all players from registry
    db = get_db_connection()
    registry = db.execute(
        'SELECT id, first_name, last_name FROM player_registry ORDER BY first_name, last_name'
    ).fetchall()

    # Convert to list of dicts for validation
    registry_list = [dict(p) for p in registry]

    # Validate
    results = validate_player_names(player_names, registry_list)

    # Build summary
    summary = {
        'exact': sum(1 for r in results if r['status'] == 'exact'),
        'similar': sum(1 for r in results if r['status'] == 'similar'),
        'new': sum(1 for r in results if r['status'] == 'new'),
        'duplicate': sum(1 for r in results if r['status'] == 'duplicate'),
        'total': len(results)
    }

    return jsonify({
        'results': results,
        'summary': summary
    })


@app.route('/admin/tournaments/create', methods=['POST'])
def admin_create_tournament():
    """Create new tournament from admin dashboard (ADMIN)"""
    db = get_db_connection()

    # Check for current season
    current_season = get_current_season(db)
    if not current_season:
        flash('No active season. Please create or activate a season first.')
        return redirect('/admin')

    # Validate form inputs
    tournament_name = request.form.get('tournament_name', '').strip()
    if not tournament_name:
        flash('Tournament name is required.')
        return redirect('/admin')

    try:
        num_courts = int(request.form.get('num_courts'))
    except (ValueError, TypeError):
        flash('Invalid number of courts.')
        return redirect('/admin')

    player_names_raw = request.form.get('players', '')
    if not player_names_raw:
        flash('Player names are required.')
        return redirect('/admin')

    player_names = player_names_raw.strip().split('\n')

    # Clean up player names
    player_names = [name.strip() for name in player_names if name.strip()]

    # Validate player count (admin route requires exact count for proper pairing)
    required_players = num_courts * 4
    if len(player_names) != required_players:
        flash(f'Need exactly {required_players} players for {num_courts} courts. You entered {len(player_names)} players.')
        return redirect('/admin')

    # Create tournament
    cursor = db.execute(
        'INSERT INTO tournaments (name, num_courts, status, season_id) VALUES (?, ?, ?, ?)',
        (tournament_name, num_courts, 'setup', current_season['id'])
    )
    tournament_id = cursor.lastrowid

    # Add players to Phase 3 player_registry and link to tournament
    for name in player_names:
        parts = name.strip().split(' ', 1)
        first_name = parts[0] if len(parts) > 0 else ''
        last_name = parts[1] if len(parts) > 1 else ''

        # Check if player already exists
        existing_player = db.execute(
            'SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?',
            (first_name, last_name)
        ).fetchone()

        if existing_player:
            player_id = existing_player['id']
        else:
            cursor = db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (first_name, last_name)
            )
            player_id = cursor.lastrowid

        # Link player to tournament
        try:
            db.execute(
                'INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)',
                (tournament_id, player_id)
            )
        except sqlite3.IntegrityError:
            # Player already linked to this tournament
            pass

    db.commit()

    flash(f'Tournament "{tournament_name}" created successfully!')

    # Redirect back to admin dashboard
    return redirect('/admin')


@app.route('/admin/tournaments/<int:tournament_id>/preview-round1', methods=['POST'])
def admin_preview_round1(tournament_id):
    """Generate or load Round 1 preview (ADMIN)"""
    db = get_db_connection()

    # Validate tournament exists and is in setup status
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ? AND status = ?',
        (tournament_id, 'setup')
    ).fetchone()

    if not tournament:
        return jsonify({'error': 'Tournament not found or not in setup status'}), 404

    # Check if we should force regeneration (for Reset button)
    force_regenerate = False
    if request.is_json and request.json:
        force_regenerate = request.json.get('force', False)

    # Check if saved pairings already exist
    existing_pairings = None
    if not force_regenerate:
        existing_pairings = db.execute(
            'SELECT * FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        ).fetchall()

    # If pairings exist and we're not forcing regeneration, return them
    if existing_pairings and not force_regenerate:
        return jsonify(format_round1_pairings_for_frontend(tournament_id, db))

    # Otherwise, generate new pairings
    # Get players with seeding points
    players_with_seeds = db.execute("""
        SELECT p.id, COALESCE(ps.seed_points, 0) as seed_points
        FROM player_registry p
        JOIN tournament_players tp ON p.id = tp.player_id
        LEFT JOIN player_seeding ps ON p.id = ps.player_id
        WHERE tp.tournament_id = ?
        ORDER BY seed_points DESC
    """, (tournament_id,)).fetchall()

    if not players_with_seeds:
        return jsonify({'error': 'No players in tournament'}), 400

    # Generate seeded pairings using existing algorithm
    from seeded_pairing import generate_seeded_round1_pairings
    players_with_seeds = [dict(p) for p in players_with_seeds]
    court_assignments = generate_seeded_round1_pairings(
        players_with_seeds,
        tournament['num_courts']
    )

    # Clear existing preview pairings for this tournament
    db.execute(
        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    )

    # Save new pairings to preview table
    for court_num, player_ids in enumerate(court_assignments, start=1):
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, court_num, *player_ids))

    db.commit()

    # Return formatted data for frontend
    return jsonify(format_round1_pairings_for_frontend(tournament_id, db))


@app.route('/admin/tournaments/<int:tournament_id>/save-round1-pairings', methods=['POST'])
def admin_save_round1_pairings(tournament_id):
    """Save custom Round 1 pairings (ADMIN)"""
    db = get_db_connection()

    # Get pairings from request
    pairings = request.json.get('pairings', [])

    if not pairings:
        return {'errors': ['No pairings provided']}, 400

    # Validate pairings
    errors = validate_round1_pairings(tournament_id, pairings, db)
    if errors:
        return {'errors': errors}, 400

    # Clear existing pairings for this tournament
    db.execute(
        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    )

    # Save new pairings
    for court in pairings:
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tournament_id,
            court['court'],
            court['team1'][0],
            court['team1'][1],
            court['team2'][0],
            court['team2'][1]
        ))

    db.commit()

    return {'success': True}


@app.route('/admin/tournaments/<int:tournament_id>/players')
def admin_get_tournament_players(tournament_id):
    """Get players for a tournament (ADMIN - API endpoint)"""
    db = get_db_connection()

    # Get player names for this tournament
    players = db.execute(
        '''SELECT pr.first_name, pr.last_name
           FROM tournament_players tp
           JOIN player_registry pr ON tp.player_id = pr.id
           WHERE tp.tournament_id = ?
           ORDER BY pr.first_name, pr.last_name''',
        (tournament_id,)
    ).fetchall()

    # Format as "First Last" strings
    player_names = [f"{p['first_name']} {p['last_name']}" for p in players]

    return {'players': player_names}


@app.route('/admin/tournaments/<int:tournament_id>/edit', methods=['GET'])
def admin_tournament_edit_page(tournament_id):
    """Full-screen tournament edit page (ADMIN)"""
    db = get_db_connection()

    # Get tournament (must be in setup mode)
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ? AND status = ?',
        (tournament_id, 'setup')
    ).fetchone()

    if not tournament:
        abort(404)

    # Get players
    players = db.execute('''
        SELECT pr.id, pr.first_name, pr.last_name
        FROM player_registry pr
        JOIN tournament_players tp ON pr.id = tp.player_id
        WHERE tp.tournament_id = ?
        ORDER BY pr.first_name, pr.last_name
    ''', (tournament_id,)).fetchall()

    # Get pairings with player names
    pairings_raw = db.execute('''
        SELECT p.*,
               p1.first_name || ' ' || p1.last_name as team1_player1_name,
               p2.first_name || ' ' || p2.last_name as team1_player2_name,
               p3.first_name || ' ' || p3.last_name as team2_player1_name,
               p4.first_name || ' ' || p4.last_name as team2_player2_name
        FROM round1_preview_pairings p
        LEFT JOIN player_registry p1 ON p.team1_player1_id = p1.id
        LEFT JOIN player_registry p2 ON p.team1_player2_id = p2.id
        LEFT JOIN player_registry p3 ON p.team2_player1_id = p3.id
        LEFT JOIN player_registry p4 ON p.team2_player2_id = p4.id
        WHERE p.tournament_id = ?
        ORDER BY p.court_number
    ''', (tournament_id,)).fetchall()

    pairings = [dict(p) for p in pairings_raw] if pairings_raw else []

    # Find unassigned players (in tournament but not in pairings)
    assigned_player_ids = set()
    for p in pairings:
        assigned_player_ids.add(p['team1_player1_id'])
        assigned_player_ids.add(p['team1_player2_id'])
        assigned_player_ids.add(p['team2_player1_id'])
        assigned_player_ids.add(p['team2_player2_id'])
    assigned_player_ids.discard(None)

    unassigned_players = [p for p in players if p['id'] not in assigned_player_ids]

    # Check if tournament can start (all slots filled, no unassigned)
    has_empty_slots = any(
        p['team1_player1_id'] is None or p['team1_player2_id'] is None or
        p['team2_player1_id'] is None or p['team2_player2_id'] is None
        for p in pairings
    )
    can_start = pairings and not has_empty_slots and not unassigned_players

    # Get edit history
    edit_history = db.execute('''
        SELECT * FROM tournament_edit_history
        WHERE tournament_id = ?
        ORDER BY changed_at DESC
        LIMIT 20
    ''', (tournament_id,)).fetchall()

    return render_template('admin_tournament_edit.html',
                          tournament=tournament,
                          players=players,
                          pairings=pairings,
                          unassigned_players=unassigned_players,
                          can_start=can_start,
                          edit_history=edit_history)


@app.route('/admin/tournaments/<int:tournament_id>/edit', methods=['POST'])
def admin_edit_tournament(tournament_id):
    """Edit tournament in setup mode (ADMIN)"""
    db = get_db_connection()

    # Verify tournament exists and is in setup mode
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ? AND status = ?',
        (tournament_id, 'setup')
    ).fetchone()

    if not tournament:
        flash('Tournament not found or cannot be edited (not in setup mode).')
        return redirect('/admin')

    # Get form data
    tournament_name = request.form.get('tournament_name', '').strip()
    if not tournament_name:
        flash('Tournament name is required.')
        return redirect('/admin')

    try:
        num_courts = int(request.form.get('num_courts'))
    except (ValueError, TypeError):
        flash('Invalid number of courts.')
        return redirect('/admin')

    player_names_raw = request.form.get('players', '')
    if not player_names_raw:
        flash('Player names are required.')
        return redirect('/admin')

    player_names = player_names_raw.strip().split('\n')
    player_names = [name.strip() for name in player_names if name.strip()]

    # Validate player count
    required_players = num_courts * 4
    if len(player_names) != required_players:
        flash(f'Need exactly {required_players} players for {num_courts} courts. You entered {len(player_names)} players.')
        return redirect('/admin')

    # Get current state for comparison
    current_tournament = db.execute(
        'SELECT num_courts FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    # Get current players in alphabetical order (same as shown in edit textarea)
    current_players_ordered = db.execute(
        '''SELECT tp.player_id, pr.first_name, pr.last_name
           FROM tournament_players tp
           JOIN player_registry pr ON tp.player_id = pr.id
           WHERE tp.tournament_id = ?
           ORDER BY pr.first_name, pr.last_name''',
        (tournament_id,)
    ).fetchall()
    current_player_ids = {p['player_id'] for p in current_players_ordered}

    # Parse new player list to get player IDs (in form order)
    new_player_ids_ordered = []
    for name in player_names:
        parts = name.strip().split(' ', 1)
        first_name = parts[0] if len(parts) > 0 else ''
        last_name = parts[1] if len(parts) > 1 else ''

        player = db.execute(
            'SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?',
            (first_name, last_name)
        ).fetchone()

        if player:
            new_player_ids_ordered.append(player['id'])
        else:
            new_player_ids_ordered.append(None)  # Will be created later

    new_player_ids = set(pid for pid in new_player_ids_ordered if pid is not None)

    # Check if player list or court count changed
    players_changed = current_player_ids != new_player_ids
    courts_changed = current_tournament['num_courts'] != num_courts
    count_changed = len(player_names) != len(current_players_ordered)

    # Build player ID mapping (old -> new) for pairings update
    player_id_mapping = {}

    if courts_changed or count_changed:
        # Court count or player count changed - clear pairings
        db.execute(
            'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        )
        if courts_changed:
            flash('⚠️ Number of courts changed - Round 1 pairings have been reset', 'warning')
        elif count_changed:
            flash('⚠️ Player count changed - Round 1 pairings have been reset', 'warning')
    elif players_changed:
        # Same count but different players - map old IDs to new IDs by position
        # This preserves the user's manual pairing arrangements
        for i, old_player in enumerate(current_players_ordered):
            if i < len(new_player_ids_ordered):
                old_id = old_player['player_id']
                new_id = new_player_ids_ordered[i]
                if new_id is not None and old_id != new_id:
                    player_id_mapping[old_id] = new_id

    # Update tournament
    db.execute(
        'UPDATE tournaments SET name = ?, num_courts = ? WHERE id = ?',
        (tournament_name, num_courts, tournament_id)
    )

    # Remove existing player assignments
    db.execute('DELETE FROM tournament_players WHERE tournament_id = ?', (tournament_id,))

    # Add updated player list and track the actual IDs (in form order)
    final_player_ids_ordered = []
    for name in player_names:
        parts = name.strip().split(' ', 1)
        first_name = parts[0] if len(parts) > 0 else ''
        last_name = parts[1] if len(parts) > 1 else ''

        # Check if player exists in registry
        existing_player = db.execute(
            'SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?',
            (first_name, last_name)
        ).fetchone()

        if existing_player:
            player_id = existing_player['id']
        else:
            cursor = db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (first_name, last_name)
            )
            player_id = cursor.lastrowid

        final_player_ids_ordered.append(player_id)

        # Link player to tournament
        try:
            db.execute(
                'INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)',
                (tournament_id, player_id)
            )
        except sqlite3.IntegrityError:
            pass  # Player already linked

    # Build final player ID mapping now that all players exist
    # Map old IDs to new IDs by position (for name changes)
    if players_changed and not (courts_changed or count_changed):
        for i, old_player in enumerate(current_players_ordered):
            if i < len(final_player_ids_ordered):
                old_id = old_player['player_id']
                new_id = final_player_ids_ordered[i]
                if old_id != new_id:
                    player_id_mapping[old_id] = new_id

    # Update existing pairings if we have a player ID mapping (name changes)
    if player_id_mapping:
        # Get existing pairings
        existing_pairings = db.execute(
            'SELECT * FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        ).fetchall()

        for pairing in existing_pairings:
            updates = {}
            for col in ['team1_player1_id', 'team1_player2_id', 'team2_player1_id', 'team2_player2_id']:
                old_id = pairing[col]
                if old_id in player_id_mapping:
                    updates[col] = player_id_mapping[old_id]

            if updates:
                set_clause = ', '.join(f'{col} = ?' for col in updates.keys())
                values = list(updates.values()) + [pairing['id']]
                db.execute(
                    f'UPDATE round1_preview_pairings SET {set_clause} WHERE id = ?',
                    values
                )

    # Save Round 1 pairings if provided (skip if we already did ID mapping - form has old IDs)
    round1_pairings_json = request.form.get('round1_pairings', '').strip()
    if round1_pairings_json and not player_id_mapping:
        try:
            pairings = json.loads(round1_pairings_json)
            if pairings:
                # Validate pairings
                errors = validate_round1_pairings(tournament_id, pairings, db)
                if not errors:
                    # Clear existing pairings
                    db.execute(
                        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
                        (tournament_id,)
                    )

                    # Save new pairings
                    for court in pairings:
                        db.execute("""
                            INSERT INTO round1_preview_pairings
                            (tournament_id, court_number, team1_player1_id, team1_player2_id,
                             team2_player1_id, team2_player2_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            tournament_id,
                            court['court'],
                            court['team1'][0],
                            court['team1'][1],
                            court['team2'][0],
                            court['team2'][1]
                        ))
                else:
                    flash(f'⚠️ Round 1 pairings validation failed: {", ".join(errors)}', 'warning')
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            flash(f'⚠️ Invalid Round 1 pairings data: {str(e)}', 'warning')

    # Log player changes to history
    new_player_ids_set = set(final_player_ids_ordered)
    added_players = new_player_ids_set - current_player_ids
    removed_players = current_player_ids - new_player_ids_set

    # Log additions
    for player_id in added_players:
        player = db.execute(
            'SELECT first_name, last_name FROM player_registry WHERE id = ?',
            (player_id,)
        ).fetchone()
        if player:
            db.execute(
                '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
                   VALUES (?, ?, ?)''',
                (tournament_id, 'player_added', f"{player['first_name']} {player['last_name']}")
            )

    # Log removals
    for player_id in removed_players:
        player = db.execute(
            'SELECT first_name, last_name FROM player_registry WHERE id = ?',
            (player_id,)
        ).fetchone()
        if player:
            db.execute(
                '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
                   VALUES (?, ?, ?)''',
                (tournament_id, 'player_removed', f"{player['first_name']} {player['last_name']}")
            )

    db.commit()

    flash(f'Tournament "{tournament_name}" updated successfully!')
    return redirect(url_for('admin_tournament_edit_page', tournament_id=tournament_id))


@app.route('/admin/tournaments/<int:tournament_id>/delete', methods=['POST'])
def admin_delete_tournament(tournament_id):
    """Delete a tournament and all associated data (ADMIN)"""
    db = get_db_connection()

    # Get tournament name for flash message
    tournament = db.execute(
        'SELECT name FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found.')
        return redirect('/admin')

    tournament_name = tournament['name']

    try:
        # Delete in correct order due to foreign key constraints
        # 1. Delete scores (references matches)
        db.execute(
            '''DELETE FROM scores WHERE match_id IN
               (SELECT m.id FROM matches m
                JOIN rounds r ON m.round_id = r.id
                WHERE r.tournament_id = ?)''',
            (tournament_id,)
        )

        # 2. Delete matches (references rounds)
        db.execute(
            '''DELETE FROM matches WHERE round_id IN
               (SELECT id FROM rounds WHERE tournament_id = ?)''',
            (tournament_id,)
        )

        # 3. Delete rounds (references tournaments)
        db.execute(
            'DELETE FROM rounds WHERE tournament_id = ?',
            (tournament_id,)
        )

        # 4. Delete tournament player associations
        db.execute(
            'DELETE FROM tournament_players WHERE tournament_id = ?',
            (tournament_id,)
        )

        # 5. Finally delete the tournament
        db.execute(
            'DELETE FROM tournaments WHERE id = ?',
            (tournament_id,)
        )

        db.commit()

        flash(f'Tournament "{tournament_name}" and all associated data deleted successfully.')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting tournament: {str(e)}')

    return redirect('/admin')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Logout and clear admin session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect('/admin/login')

@app.route('/test/selection')
def test_selection():
    tournaments = [
        {'id': 1, 'name': 'Tournament A', 'status': 'active', 'created_at': '2025-12-31'},
        {'id': 2, 'name': 'Tournament B', 'status': 'setup', 'created_at': '2025-12-31'}
    ]
    return render_template('tournament_selection.html', tournaments=tournaments)

@app.route('/test/noactive')
def test_noactive():
    season = {'name': 'Winter 2025', 'tournament_count': 5}
    return render_template('no_active_tournament.html', season=season)

# Run migrations on startup if needed
with app.app_context():
    from migration import run_migration_if_needed, migrate_seasons_schema
    result = run_migration_if_needed()
    if result == "migrated":
        print("✅ Data migration completed: Tournaments assigned to seasons")
    elif result == "already_migrated":
        print("✅ Data already migrated")

    # Ensure seasons table has name and ended_at columns
    schema_result = migrate_seasons_schema()
    if schema_result == "migrated":
        print("✅ Seasons schema migration completed")

    # Add version column to matches table for concurrency control
    db = get_db()
    cursor = db.execute("PRAGMA table_info(matches)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'version' not in columns:
        db.execute("ALTER TABLE matches ADD COLUMN version INTEGER DEFAULT 1")
        db.commit()
        print("✅ Matches version column added")

    # Create player_points_adjustment table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS player_points_adjustment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            adjustment INTEGER DEFAULT 0,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE CASCADE,
            FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
            UNIQUE(player_id, season_id)
        )
    ''')
    db.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
