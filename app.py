"""
Padel Paroni - Tournament Management Application

A Flask web application for managing padel/tennis tournaments with:
- Season and tournament management
- Player registry and statistics
- Round-robin court assignments with smart pairing algorithm
- Real-time scoring and leaderboards
- Admin dashboard with authentication

Main features:
- Public views: Leaderboards, player profiles, live scoring
- Admin views: Tournament setup, player management, data export/restore

Security:
- CSRF protection on all POST requests
- Rate limiting on sensitive endpoints
- Password hashing (pbkdf2:sha256)
- Session timeout after 30 minutes

For deployment instructions, see docs/PYTHONANYWHERE_DEPLOYMENT.md
"""

from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify, abort, Response
import csv
import io
import secrets
import base64
import queue
import threading
import time
from functools import wraps
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


def generate_court_labels(num_courts, start_from=1, skip_courts=None):
    """Generate list of court numbers.

    Args:
        num_courts: Number of courts needed
        start_from: Starting court number (default 1)
        skip_courts: List of court numbers to skip

    Returns:
        List of court numbers, e.g., [1, 2, 3, 4, 5, 6, 8, 9]
    """
    skip_courts = skip_courts or []
    courts = []
    current = start_from
    while len(courts) < num_courts:
        if current not in skip_courts:
            courts.append(current)
        current += 1
    return courts


def get_court_labels(tournament):
    """Get court labels for a tournament.

    Returns list of court numbers from court_labels JSON, or generates
    sequential [1, 2, ..., num_courts] if not set.
    """
    court_labels_json = tournament['court_labels'] if 'court_labels' in tournament.keys() else None
    if court_labels_json:
        return json.loads(court_labels_json)
    return list(range(1, tournament['num_courts'] + 1))

def get_setup_tournaments(db, season_id):
    """Get tournaments in 'setup' status for a season"""
    return db.execute(
        "SELECT id, name FROM tournaments WHERE season_id = ? AND status = 'setup'",
        (season_id,)
    ).fetchall()

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

# SSE (Server-Sent Events) broadcaster for live updates
class SSEBroadcaster:
    """Simple in-memory event broadcaster for SSE connections."""

    def __init__(self):
        self.listeners = {}  # round_id -> list of queues
        self.lock = threading.Lock()

    def subscribe(self, round_id):
        """Subscribe to events for a specific round. Returns a queue."""
        q = queue.Queue(maxsize=10)
        with self.lock:
            if round_id not in self.listeners:
                self.listeners[round_id] = []
            self.listeners[round_id].append(q)
        return q

    def unsubscribe(self, round_id, q):
        """Unsubscribe from events."""
        with self.lock:
            if round_id in self.listeners:
                try:
                    self.listeners[round_id].remove(q)
                except ValueError:
                    pass
                if not self.listeners[round_id]:
                    del self.listeners[round_id]

    def broadcast(self, round_id, event_type, data):
        """Broadcast an event to all listeners for a round."""
        message = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        with self.lock:
            if round_id in self.listeners:
                for q in self.listeners[round_id]:
                    try:
                        q.put_nowait(message)
                    except queue.Full:
                        pass  # Drop if queue is full

sse_broadcaster = SSEBroadcaster()

# Ensure database directory exists
db_dir = os.path.dirname(app.config['DATABASE'])
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# Database initialization flag - lazy init on first request for faster startup
_db_initialized = False

# Database connection helper
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

@app.teardown_appcontext
def close_db(_):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.before_request
def log_request_start():
    """Log request timing"""
    import time
    g.request_start_time = time.time()
    print(f"[REQ START] {request.method} {request.path}")

@app.after_request
def log_request_end(response):
    """Log request duration"""
    import time
    if hasattr(g, 'request_start_time'):
        duration = time.time() - g.request_start_time
        print(f"[REQ END] {request.method} {request.path} - {duration:.3f}s - {response.status_code}")
    return response

@app.before_request
def check_admin_session():
    """Check admin authentication and session timeout before each request"""
    # Only check for admin routes (except login and setup)
    if request.path.startswith('/admin') and request.path not in ['/admin/login', '/admin/setup']:
        # Check if logged in
        if not session.get('logged_in_as_admin'):
            return redirect('/admin/login')

        # Verify admin still exists in database (handles wiped database case)
        # Skip in testing mode where sessions are mocked without real admin users
        if not app.config.get('TESTING'):
            db = get_db_connection()
            admin_exists = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
            if not admin_exists:
                session.clear()
                return redirect('/admin/setup')

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


@app.before_request
def generate_csp_nonce():
    """Generate a unique nonce for Content-Security-Policy on each request"""
    g.csp_nonce = base64.b64encode(secrets.token_bytes(16)).decode('utf-8')


@app.after_request
def add_security_headers(response):
    """Add Content-Security-Policy and other security headers"""
    # Only add CSP to HTML responses
    if response.content_type and 'text/html' in response.content_type:
        nonce = getattr(g, 'csp_nonce', '')
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"form-action 'self'; "
            f"frame-ancestors 'none'"
        )
        response.headers['Content-Security-Policy'] = csp
    return response


@app.context_processor
def inject_csp_nonce():
    """Make csp_nonce available in all templates"""
    return {'csp_nonce': getattr(g, 'csp_nonce', '')}


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

@app.route('/health')
def health_check():
    """Simple health check - no database access"""
    return {'status': 'ok', 'db': 'not checked'}


@app.route('/health/db')
def health_check_db():
    """Health check with database access"""
    import time
    start = time.time()
    db = get_db_connection()
    db.execute('SELECT 1').fetchone()
    db_time = time.time() - start
    return {'status': 'ok', 'db_response_ms': round(db_time * 1000, 2)}


@app.route('/')
def index():
    """Home page - consistent landing page for all users"""
    db = get_db_connection()

    # Query active tournaments with round and player info
    active_tournaments = db.execute(
        '''SELECT t.*,
                  (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                  (SELECT MAX(round_number) FROM rounds WHERE tournament_id = t.id) as current_round
           FROM tournaments t
           WHERE t.status = 'active'
           ORDER BY t.created_at DESC'''
    ).fetchall()

    # Query setup tournaments with player count
    setup_tournaments = db.execute(
        '''SELECT t.*,
                  (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
           FROM tournaments t
           WHERE t.status = 'setup'
           ORDER BY t.created_at DESC'''
    ).fetchall()

    current_season = get_current_season(db)

    # Get season info for display
    season_info = None
    if current_season:
        # Count actual tournaments
        actual_tournament_count = db.execute(
            "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']

        # Get max imported tournaments (when no actual tournaments exist)
        imported_tournament_count = db.execute(
            "SELECT COALESCE(MAX(tournaments_adjustment), 0) as count FROM player_points_adjustment WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']

        # Use actual count if exists, otherwise use imported count
        tournament_count = actual_tournament_count if actual_tournament_count > 0 else imported_tournament_count

        season_name = current_season['name'] if 'name' in current_season.keys() else f"Season {current_season['year']}"

        season_info = {
            'name': season_name,
            'tournament_count': tournament_count
        }

    return render_template('home.html',
                         active_tournaments=active_tournaments,
                         setup_tournaments=setup_tournaments,
                         season=season_info)

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

    # Prevent non-admin users from starting tournament in setup mode
    if tournament['status'] == 'setup' and not session.get('logged_in_as_admin'):
        flash('Vain ylläpitäjä voi aloittaa turnauksen')
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
        court_labels = get_court_labels(tournament)

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

                # Create matches from seeded assignments using court labels
                for court_idx, player_ids in enumerate(court_assignments):
                    court_label = court_labels[court_idx] if court_idx < len(court_labels) else court_idx + 1
                    db.execute(
                        '''INSERT INTO matches
                           (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (round_id, court_label, *player_ids)
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

            # Create matches from assignments using court labels
            for court_idx, players_on_court in enumerate(court_assignments):
                court_label = court_labels[court_idx] if court_idx < len(court_labels) else court_idx + 1
                db.execute(
                    '''INSERT INTO matches
                       (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (round_id, court_label, *players_on_court)
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

    # Check if match already completed - allow editing in scenario 1 (no next round)
    if match['completed']:
        correction_scenario = get_result_correction_scenario(match['id'], db)
        if correction_scenario['scenario'] == 2 and not session.get('logged_in_as_admin'):
            flash(correction_scenario['message'])
            return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))
        # Scenario 1 or admin: allow editing teams

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

@app.route('/api/tournament/<int:tournament_id>/pairings-text')
def api_tournament_pairings_text(tournament_id):
    """Return current round pairings as copyable text"""
    db = get_db_connection()

    tournament = db.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404

    # Get the latest round
    current_round = db.execute(
        'SELECT * FROM rounds WHERE tournament_id = ? ORDER BY round_number DESC LIMIT 1',
        (tournament_id,)
    ).fetchone()
    if not current_round:
        return jsonify({'error': 'No rounds found'}), 404

    matches = db.execute('''
        SELECT m.court_number,
               p1.first_name || ' ' || p1.last_name as player1_name,
               p2.first_name || ' ' || p2.last_name as player2_name,
               p3.first_name || ' ' || p3.last_name as player3_name,
               p4.first_name || ' ' || p4.last_name as player4_name
        FROM matches m
        JOIN player_registry p1 ON m.player1_id = p1.id
        JOIN player_registry p2 ON m.player2_id = p2.id
        JOIN player_registry p3 ON m.player3_id = p3.id
        JOIN player_registry p4 ON m.player4_id = p4.id
        WHERE m.round_id = ?
        ORDER BY m.court_number
    ''', (current_round['id'],)).fetchall()

    lines = []
    for m in matches:
        lines.append(f"Kenttä {m['court_number']}: {m['player1_name']} & {m['player2_name']} vs {m['player3_name']} & {m['player4_name']}")

    return jsonify({
        'text': '\n'.join(lines),
        'round_number': current_round['round_number'],
        'tournament_name': tournament['name']
    })

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

    # Check if user is admin
    is_admin = session.get('logged_in_as_admin', False)

    # Get all rounds for this tournament (for admin navigation)
    all_rounds = []
    if is_admin:
        all_rounds = db.execute(
            'SELECT id, round_number FROM rounds WHERE tournament_id = ? ORDER BY round_number',
            (tournament_id,)
        ).fetchall()

    # Check if previous round was edited after this round started (needs recalculation)
    needs_recalculation = False
    if is_admin and round_data['round_number'] > 1:
        # Get the most recent result correction for previous round (after this round was created)
        last_correction = db.execute(
            '''SELECT MAX(changed_at) as last_changed FROM tournament_edit_history
               WHERE tournament_id = ?
               AND change_type = 'result_corrected'
               AND changed_at > ?
               AND json_extract(change_data, '$.round_id') = (
                   SELECT id FROM rounds WHERE tournament_id = ? AND round_number = ?
               )''',
            (tournament_id, round_data['created_at'], tournament_id, round_data['round_number'] - 1)
        ).fetchone()

        if last_correction and last_correction['last_changed']:
            # Check if this round was recalculated after the last correction
            last_recalc = db.execute(
                '''SELECT MAX(changed_at) as last_changed FROM tournament_edit_history
                   WHERE tournament_id = ?
                   AND change_type = 'round_recalculated'
                   AND json_extract(change_data, '$.round_id') = ?''',
                (tournament_id, round_id)
            ).fetchone()

            if last_recalc and last_recalc['last_changed']:
                # Needs recalculation only if correction is newer than last recalc
                needs_recalculation = last_correction['last_changed'] > last_recalc['last_changed']
            else:
                # No recalculation done yet, so needs it
                needs_recalculation = True

    return render_template('active_round.html',
                          tournament_id=tournament_id,
                          tournament=tournament,
                          round_data=round_data,
                          matches=matches,
                          all_completed=all_completed,
                          is_admin=is_admin,
                          all_rounds=all_rounds,
                          needs_recalculation=needs_recalculation)


@app.route('/sse/round/<int:round_id>')
def sse_round_stream(round_id):
    """Server-Sent Events stream for live round updates."""
    # Disable SSE on hosts that don't support long-polling (e.g., PythonAnywhere with 1 worker)
    if os.environ.get('DISABLE_SSE'):
        return jsonify({'error': 'SSE disabled', 'message': 'Use polling instead'}), 503

    def event_stream():
        q = sse_broadcaster.subscribe(round_id)
        try:
            # Send initial connection confirmation
            yield f"data: {json.dumps({'type': 'connected', 'round_id': round_id})}\n\n"

            while True:
                try:
                    # Wait for events with timeout (for keepalive)
                    message = q.get(timeout=30)
                    yield f"data: {json.dumps(message)}\n\n"
                except queue.Empty:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            sse_broadcaster.unsubscribe(round_id, q)

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/matches-partial')
def active_round_matches_partial(tournament_id, round_id):
    """Return just the matches section HTML for AJAX refresh."""
    db = get_db_connection()

    round_data = db.execute('SELECT * FROM rounds WHERE id = ?', (round_id,)).fetchone()
    if not round_data:
        return '', 404

    # Get all matches with player names
    matches_raw = db.execute(
        '''SELECT m.*
           FROM matches m
           WHERE m.round_id = ?
           ORDER BY m.court_number''',
        (round_id,)
    ).fetchall()

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

    all_completed = all(match['completed'] for match in matches)

    return render_template('_matches_partial.html',
                          tournament_id=tournament_id,
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

    # Check if editing completed match - detect scenario
    is_editing = match['completed']
    correction_scenario = None
    if is_editing:
        correction_scenario = get_result_correction_scenario(match_id, db)
        # Scenario 2: Block regular users if next round has started
        if correction_scenario['scenario'] == 2 and not session.get('logged_in_as_admin'):
            flash(correction_scenario['message'])
            return redirect(url_for('active_round',
                                   tournament_id=match['tournament_id'],
                                   round_id=match['round_id']))

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

        # Determine winners (only winners get points in current scoring system)
        if winning_team == 1:
            winner_ids = [match['player1_id'], match['player2_id']]
        else:
            winner_ids = [match['player3_id'], match['player4_id']]

        if match['completed']:
            # Update existing scores
            old_winning_team = match['winning_team']

            # Log the correction to audit history
            db.execute(
                '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
                   VALUES (?, ?, ?)''',
                (match['tournament_id'], 'result_corrected', json.dumps({
                    'match_id': match_id,
                    'court_number': match['court_number'],
                    'round_id': match['round_id'],
                    'old_winning_team': old_winning_team,
                    'new_winning_team': winning_team
                }))
            )

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

        # Broadcast score update for live refresh
        sse_broadcaster.broadcast(match['round_id'], 'score_updated', {
            'match_id': match_id,
            'court_number': match['court_number'],
            'winning_team': winning_team
        })

        return redirect(url_for('active_round',
                               tournament_id=match['tournament_id'],
                               round_id=match['round_id']))

    return render_template('score_entry.html', match=match, is_editing=is_editing)

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
    # Includes players with only imported points (no tournament matches)
    season_stats_raw = db.execute("""
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
            COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0) as total_matches,
            COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0) as total_tournaments,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0), 0) * 100,
                1
            ) as win_rate,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) as total_points
        FROM player_registry pr
        LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
        LEFT JOIN matches m ON (pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id) AND m.completed = 1)
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id AND t.season_id = ?
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE adj.adjustment IS NOT NULL OR adj.tournaments_adjustment IS NOT NULL OR t.id IS NOT NULL
        GROUP BY pr.id, pr.first_name, pr.last_name
        HAVING total_points > 0 OR total_tournaments > 0
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

    # Count actual tournaments, or use imported tournament count if none exist
    actual_tournament_count = len(tournaments)
    if actual_tournament_count > 0:
        tournament_count = actual_tournament_count
    else:
        # Get max imported tournaments
        imported_count = db.execute(
            "SELECT COALESCE(MAX(tournaments_adjustment), 0) as count FROM player_points_adjustment WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']
        tournament_count = imported_count

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

@app.route('/admin/empty-database', methods=['POST'])
@block_in_demo_mode
def admin_empty_database():
    """Clear all tournament and player data - complete reset (admin only)"""
    if not session.get('logged_in_as_admin'):
        flash('Vain ylläpitäjä voi tyhjentää datan')
        return redirect(url_for('admin_login'))

    db = get_db_connection()

    # Delete in correct order (foreign key constraints)
    tables = [
        'scores', 'matches', 'rounds', 'round1_preview_pairings',
        'tournament_edit_history', 'player_points_adjustment',
        'player_seeding', 'tournament_players', 'tournaments',
        'player_registry', 'seasons'
    ]
    for table in tables:
        try:
            db.execute(f'DELETE FROM {table}')
        except Exception:
            pass  # Table might not exist

    # Reset auto-increment counters
    db.execute('DELETE FROM sqlite_sequence')

    db.commit()

    flash('Tietokanta tyhjennetty onnistuneesti.')
    return redirect(url_for('admin_dashboard'))

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
            COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0) as total_matches,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0), 0) * 100,
                1
            ) as win_rate,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) as total_points,
            COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0) as tournaments_played
        FROM player_registry pr
        LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
        LEFT JOIN matches m ON (
            pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id)
            AND m.completed = 1
        )
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id AND t.season_id = ?
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE pr.id = ?
          AND (adj.adjustment IS NOT NULL OR adj.tournaments_adjustment IS NOT NULL OR t.id IS NOT NULL)
        GROUP BY pr.id, pr.first_name, pr.last_name
    """, (current_season['id'], current_season['id'], player_id)).fetchone()

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
                COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) as total_points,
                ROUND(
                    CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                    NULLIF(COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0), 0) * 100,
                    1
                ) as win_rate
            FROM player_registry pr
            LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
            LEFT JOIN matches m ON (
                pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id)
                AND m.completed = 1
            )
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id AND t.season_id = ?
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
            WHERE adj.adjustment IS NOT NULL OR adj.tournaments_adjustment IS NOT NULL OR t.id IS NOT NULL
            GROUP BY pr.id
            HAVING total_points > 0 OR COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0) > 0
            ORDER BY total_points DESC, win_rate DESC
        """, (current_season['id'], current_season['id'])).fetchall()

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

    # Calculate additional stats
    best_partner = None
    longest_streak = 0
    best_tournament = None
    worst_tournament = None

    if season_stats and season_stats['total_wins'] > 0:
        # 1. Best partner - find who they won most matches with
        partner_wins = db.execute("""
            SELECT
                CASE
                    WHEN m.player1_id = ? THEN m.player2_id
                    WHEN m.player2_id = ? THEN m.player1_id
                    WHEN m.player3_id = ? THEN m.player4_id
                    WHEN m.player4_id = ? THEN m.player3_id
                END as partner_id,
                COUNT(*) as wins_together
            FROM matches m
            JOIN rounds r ON m.round_id = r.id
            JOIN tournaments t ON r.tournament_id = t.id
            WHERE t.season_id = ?
              AND m.completed = 1
              AND (
                  (m.winning_team = 1 AND (m.player1_id = ? OR m.player2_id = ?))
                  OR
                  (m.winning_team = 2 AND (m.player3_id = ? OR m.player4_id = ?))
              )
            GROUP BY partner_id
            ORDER BY wins_together DESC
            LIMIT 1
        """, (player_id, player_id, player_id, player_id, current_season['id'],
              player_id, player_id, player_id, player_id)).fetchone()

        if partner_wins and partner_wins['partner_id']:
            partner = db.execute(
                'SELECT first_name, last_name FROM player_registry WHERE id = ?',
                (partner_wins['partner_id'],)
            ).fetchone()
            if partner:
                best_partner = {
                    'name': f"{partner['first_name']} {partner['last_name']}",
                    'wins': partner_wins['wins_together']
                }

        # 2. Longest win streak - consecutive wins
        all_matches = db.execute("""
            SELECT
                m.id,
                m.winning_team,
                CASE
                    WHEN m.player1_id = ? OR m.player2_id = ? THEN 1
                    ELSE 2
                END as player_team
            FROM matches m
            JOIN rounds r ON m.round_id = r.id
            JOIN tournaments t ON r.tournament_id = t.id
            WHERE t.season_id = ?
              AND m.completed = 1
              AND (m.player1_id = ? OR m.player2_id = ? OR m.player3_id = ? OR m.player4_id = ?)
            ORDER BY t.created_at, r.round_number, m.id
        """, (player_id, player_id, current_season['id'],
              player_id, player_id, player_id, player_id)).fetchall()

        current_streak = 0
        for match in all_matches:
            if match['winning_team'] == match['player_team']:
                current_streak += 1
                if current_streak > longest_streak:
                    longest_streak = current_streak
            else:
                current_streak = 0

        # 3. Best tournament - most wins in a single tournament
        tournament_wins = db.execute("""
            SELECT
                t.id,
                t.name,
                COUNT(*) as wins
            FROM matches m
            JOIN rounds r ON m.round_id = r.id
            JOIN tournaments t ON r.tournament_id = t.id
            WHERE t.season_id = ?
              AND m.completed = 1
              AND (
                  (m.winning_team = 1 AND (m.player1_id = ? OR m.player2_id = ?))
                  OR
                  (m.winning_team = 2 AND (m.player3_id = ? OR m.player4_id = ?))
              )
            GROUP BY t.id
            ORDER BY wins DESC
        """, (current_season['id'], player_id, player_id, player_id, player_id)).fetchall()

        if tournament_wins:
            best = tournament_wins[0]
            best_tournament = {'name': best['name'], 'wins': best['wins']}

            # 4. Worst tournament - only if more than 1 tournament played
            if len(tournament_wins) > 1:
                worst = tournament_wins[-1]
                worst_tournament = {'name': worst['name'], 'wins': worst['wins']}

    # Additional stats (even if no wins, some of these can still be calculated)
    nemesis = None
    easiest_opponent = None
    current_form = []
    comeback_rate = None
    first_round_winrate = None
    later_rounds_winrate = None
    most_common_partner = None
    most_common_opponent = None
    court_stats = []
    progress_data = []

    if season_stats and season_stats['total_matches'] > 0:
        # Get all matches for this player in current season with details
        all_player_matches = db.execute("""
            SELECT
                m.id,
                m.winning_team,
                m.court_number,
                m.player1_id, m.player2_id, m.player3_id, m.player4_id,
                r.round_number,
                t.id as tournament_id,
                t.name as tournament_name,
                CASE
                    WHEN m.player1_id = ? OR m.player2_id = ? THEN 1
                    ELSE 2
                END as player_team
            FROM matches m
            JOIN rounds r ON m.round_id = r.id
            JOIN tournaments t ON r.tournament_id = t.id
            WHERE t.season_id = ?
              AND m.completed = 1
              AND (m.player1_id = ? OR m.player2_id = ? OR m.player3_id = ? OR m.player4_id = ?)
            ORDER BY t.created_at, r.round_number, m.id
        """, (player_id, player_id, current_season['id'],
              player_id, player_id, player_id, player_id)).fetchall()

        # 5. Current form - last 10 matches
        for match in all_player_matches[-10:]:
            won = match['winning_team'] == match['player_team']
            current_form.append('✓' if won else '✗')

        # 6. Comeback rate - win after a loss
        comebacks = 0
        comeback_opportunities = 0
        prev_won = None
        for match in all_player_matches:
            won = match['winning_team'] == match['player_team']
            if prev_won is False:  # Previous was a loss
                comeback_opportunities += 1
                if won:
                    comebacks += 1
            prev_won = won
        if comeback_opportunities > 0:
            comeback_rate = round(comebacks / comeback_opportunities * 100)

        # 7. First round vs later rounds win rate
        first_round_wins = 0
        first_round_total = 0
        later_round_wins = 0
        later_round_total = 0
        for match in all_player_matches:
            won = match['winning_team'] == match['player_team']
            if match['round_number'] == 1:
                first_round_total += 1
                if won:
                    first_round_wins += 1
            else:
                later_round_total += 1
                if won:
                    later_round_wins += 1
        if first_round_total > 0:
            first_round_winrate = round(first_round_wins / first_round_total * 100)
        if later_round_total > 0:
            later_rounds_winrate = round(later_round_wins / later_round_total * 100)

        # 8. Most common partner
        partner_counts = {}
        for match in all_player_matches:
            if match['player_team'] == 1:
                partner_id = match['player2_id'] if match['player1_id'] == player_id else match['player1_id']
            else:
                partner_id = match['player4_id'] if match['player3_id'] == player_id else match['player3_id']
            partner_counts[partner_id] = partner_counts.get(partner_id, 0) + 1

        if partner_counts:
            most_common_partner_id = max(partner_counts, key=partner_counts.get)
            partner = db.execute(
                'SELECT first_name, last_name FROM player_registry WHERE id = ?',
                (most_common_partner_id,)
            ).fetchone()
            if partner:
                most_common_partner = {
                    'name': f"{partner['first_name']} {partner['last_name']}",
                    'matches': partner_counts[most_common_partner_id]
                }

        # 9. Most common opponent & opponent stats (nemesis/easiest)
        opponent_stats = {}  # opponent_id -> {'wins': 0, 'losses': 0, 'total': 0}
        for match in all_player_matches:
            won = match['winning_team'] == match['player_team']
            if match['player_team'] == 1:
                opponents = [match['player3_id'], match['player4_id']]
            else:
                opponents = [match['player1_id'], match['player2_id']]
            for opp_id in opponents:
                if opp_id not in opponent_stats:
                    opponent_stats[opp_id] = {'wins': 0, 'losses': 0, 'total': 0}
                opponent_stats[opp_id]['total'] += 1
                if won:
                    opponent_stats[opp_id]['wins'] += 1
                else:
                    opponent_stats[opp_id]['losses'] += 1

        if opponent_stats:
            # Most common opponent
            most_common_opp_id = max(opponent_stats, key=lambda x: opponent_stats[x]['total'])
            opp = db.execute(
                'SELECT first_name, last_name FROM player_registry WHERE id = ?',
                (most_common_opp_id,)
            ).fetchone()
            if opp:
                most_common_opponent = {
                    'name': f"{opp['first_name']} {opp['last_name']}",
                    'matches': opponent_stats[most_common_opp_id]['total']
                }

            # Nemesis - most losses against (min 1 match)
            nemesis_candidates = [(k, v) for k, v in opponent_stats.items() if v['losses'] >= 1]
            if nemesis_candidates:
                nemesis_id = max(nemesis_candidates, key=lambda x: x[1]['losses'])[0]
                nem = db.execute(
                    'SELECT first_name, last_name FROM player_registry WHERE id = ?',
                    (nemesis_id,)
                ).fetchone()
                if nem:
                    nemesis = {
                        'name': f"{nem['first_name']} {nem['last_name']}",
                        'losses': opponent_stats[nemesis_id]['losses']
                    }

            # Easiest opponent - most wins against (min 2 matches)
            easy_candidates = [(k, v) for k, v in opponent_stats.items() if v['wins'] >= 2]
            if easy_candidates:
                easy_id = max(easy_candidates, key=lambda x: x[1]['wins'])[0]
                easy = db.execute(
                    'SELECT first_name, last_name FROM player_registry WHERE id = ?',
                    (easy_id,)
                ).fetchone()
                if easy:
                    easiest_opponent = {
                        'name': f"{easy['first_name']} {easy['last_name']}",
                        'wins': opponent_stats[easy_id]['wins']
                    }

        # 10. Win rate per court
        court_data = {}
        for match in all_player_matches:
            court = match['court_number']
            won = match['winning_team'] == match['player_team']
            if court not in court_data:
                court_data[court] = {'wins': 0, 'total': 0}
            court_data[court]['total'] += 1
            if won:
                court_data[court]['wins'] += 1

        for court in sorted(court_data.keys()):
            data = court_data[court]
            winrate = round(data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            court_stats.append({
                'court': court,
                'winrate': winrate,
                'matches': data['total'],
                'wins': data['wins'],
                'losses': data['total'] - data['wins']
            })

        # 11. Progress data - wins per tournament for graph
        tournament_progress = {}
        for match in all_player_matches:
            t_id = match['tournament_id']
            t_name = match['tournament_name']
            won = match['winning_team'] == match['player_team']
            if t_id not in tournament_progress:
                tournament_progress[t_id] = {'name': t_name, 'wins': 0}
            if won:
                tournament_progress[t_id]['wins'] += 1

        # Get tournaments in order
        tournaments_ordered = db.execute("""
            SELECT id, name FROM tournaments
            WHERE season_id = ? AND status = 'completed'
            ORDER BY created_at
        """, (current_season['id'],)).fetchall()

        for t in tournaments_ordered:
            if t['id'] in tournament_progress:
                progress_data.append({
                    'name': t['name'],
                    'wins': tournament_progress[t['id']]['wins']
                })

    return render_template(
        'player_profile.html',
        player=player,
        season_stats=season_stats,
        season_name=season_name,
        current_year=current_year,
        rank=rank,
        wins_per_tournament=wins_per_tournament,
        best_partner=best_partner,
        longest_streak=longest_streak,
        best_tournament=best_tournament,
        worst_tournament=worst_tournament,
        nemesis=nemesis,
        easiest_opponent=easiest_opponent,
        current_form=current_form,
        comeback_rate=comeback_rate,
        first_round_winrate=first_round_winrate,
        later_rounds_winrate=later_rounds_winrate,
        most_common_partner=most_common_partner,
        most_common_opponent=most_common_opponent,
        court_stats=court_stats,
        progress_data=progress_data
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

    db = get_db_connection()

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
    db = get_db_connection()
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
    db = get_db_connection()

    # Check if admin already exists
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if admin:
        return redirect('/admin/login')

    # In production, require ADMIN_SETUP_TOKEN to prevent unauthorized admin creation
    setup_token = app.config.get('ADMIN_SETUP_TOKEN')
    is_production = not (
        os.environ.get('FLASK_ENV') == 'development' or
        os.environ.get('FLASK_DEBUG') == '1' or
        os.environ.get('TESTING') == '1'
    )

    if is_production and not setup_token:
        flash('Admin setup disabled. Set ADMIN_SETUP_TOKEN environment variable.')
        return render_template('admin_setup.html', setup_disabled=True)

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Verify setup token in production
        if is_production:
            provided_token = request.form.get('setup_token', '').strip()
            if provided_token != setup_token:
                flash('Virheellinen asennusavain', 'error')
                return render_template('admin_setup.html', require_token=True)

        # Validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return render_template('admin_setup.html', require_token=is_production)

        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('admin_setup.html', require_token=is_production)

        # Create admin user
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (password_hash,)
        )
        db.commit()

        flash('Admin account created successfully! Please log in.')
        return redirect('/admin/login')

    return render_template('admin_setup.html', require_token=is_production)


@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])  # Brute force protection
def admin_login():
    """Admin login page"""
    db = get_db_connection()

    # Check if admin exists, redirect to setup if not
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if not admin:
        return redirect('/admin/setup')

    if request.method == 'POST':
        password = request.form.get('password', '')

        # Get admin password hash
        admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()

        if admin and check_password_hash(admin['password_hash'], password):
            # Set session for full admin access
            session['logged_in_as_admin'] = True
            session['demo_mode'] = False
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            return redirect('/admin')
        elif app.config.get('DEMO_PASSWORD') and password == app.config['DEMO_PASSWORD']:
            # Demo mode: read-only admin access
            session['logged_in_as_admin'] = True
            session['demo_mode'] = True
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            return redirect('/admin')
        else:
            flash('Invalid password')
            return render_template('admin_login.html')

    return render_template('admin_login.html')


# NOTE: Forgot-password feature removed for security reasons.
# If you forget the admin password, reset it via server command:
#   python -c "from werkzeug.security import generate_password_hash; from database import get_db; db = get_db(); db.execute('UPDATE admin_users SET password_hash = ?', (generate_password_hash('newpassword'),)); db.commit(); print('Password reset to: newpassword')"


@app.route('/admin/seasons/end-current', methods=['POST'])
@block_in_demo_mode
def admin_end_current_season():
    """End the current season without creating a new one (ADMIN)"""
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        flash('No current season to end')
        return redirect('/admin')

    # Check for setup tournaments that would be orphaned
    setup_tournaments = get_setup_tournaments(db, current_season['id'])
    if setup_tournaments:
        names = ', '.join([t['name'] for t in setup_tournaments])
        flash(f'Kautta ei voi päättää: turnaukset valmistelussa: {names}. Poista tai käynnistä ne ensin.')
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
@block_in_demo_mode
def admin_create_season():
    """Create a new season and make it current (ADMIN)"""
    db = get_db_connection()
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

    # Check for setup tournaments in current season that would be orphaned
    current_season = get_current_season(db)
    if current_season:
        setup_tournaments = get_setup_tournaments(db, current_season['id'])
        if setup_tournaments:
            names = ', '.join([t['name'] for t in setup_tournaments])
            flash(f'Uutta kautta ei voi luoda: turnaukset valmistelussa: {names}. Poista tai käynnistä ne ensin.')
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
@block_in_demo_mode
def admin_activate_season(season_id):
    """Reactivate an archived season as the current season (ADMIN)"""
    db = get_db_connection()

    season = db.execute(
        "SELECT * FROM seasons WHERE id = ?", (season_id,)
    ).fetchone()

    if not season:
        flash('Season not found')
        return redirect('/admin')

    # Check for setup tournaments in current season that would be orphaned
    current_season = get_current_season(db)
    if current_season and current_season['id'] != season_id:
        setup_tournaments = get_setup_tournaments(db, current_season['id'])
        if setup_tournaments:
            names = ', '.join([t['name'] for t in setup_tournaments])
            flash(f'Kautta ei voi vaihtaa: turnaukset valmistelussa: {names}. Poista tai käynnistä ne ensin.')
            return redirect('/admin')

    set_current_season(db, season_id)

    # Handle both old schema (year) and new schema (name)
    season_name = season['name'] if 'name' in season.keys() else f"Season {season['year']}"
    flash(f"Season '{season_name}' is now active")
    return redirect('/admin')


@app.route('/admin/generate-test-data', methods=['POST'])
@block_in_demo_mode
def admin_generate_test_data():
    """Generate test data (admin only) - for testing/demo purposes."""
    if not session.get('logged_in_as_admin'):
        flash('Vain ylläpitäjä voi suorittaa tämän toiminnon')
        return redirect('/admin/login')

    db = get_db_connection()

    # Clear existing tournament data but keep players
    db.execute('DELETE FROM scores')
    db.execute('DELETE FROM matches')
    db.execute('DELETE FROM rounds')
    db.execute('DELETE FROM tournament_players')
    db.execute('DELETE FROM round1_preview_pairings')
    db.execute('DELETE FROM tournaments')
    db.execute('DELETE FROM player_points_adjustment')
    db.execute('DELETE FROM seasons')
    db.commit()

    # Create season
    db.execute("INSERT INTO seasons (name, is_current) VALUES ('Kevat 2026', 1)")
    season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Get existing players
    players = db.execute('SELECT id FROM player_registry ORDER BY id').fetchall()
    player_ids = [p['id'] for p in players]

    if len(player_ids) < 8:
        flash(f'Tarvitaan vähintään 8 pelaajaa. Löytyi vain {len(player_ids)}.')
        return redirect('/admin')

    import random

    # Assign random skill levels
    skill_map = {}
    for i, pid in enumerate(player_ids):
        base_skill = 0.3 + (0.5 * (len(player_ids) - i) / len(player_ids))
        skill_map[pid] = base_skill + random.uniform(-0.1, 0.1)

    def create_test_tournament(name, t_player_ids, num_courts, num_rounds, status='completed'):
        db.execute(
            "INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
            (name, num_courts, season_id, status)
        )
        tid = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        for pid in t_player_ids:
            db.execute(
                "INSERT INTO tournament_players (tournament_id, player_id, total_points, match_wins, match_losses) VALUES (?, ?, 0, 0, 0)",
                (tid, pid)
            )

        player_stats = {pid: {'wins': 0, 'losses': 0} for pid in t_player_ids}

        for round_num in range(1, num_rounds + 1):
            round_status = 'completed' if status == 'completed' else ('in_progress' if round_num == 1 else 'pending')
            db.execute("INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, ?, ?)",
                      (tid, round_num, round_status))
            round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            shuffled = t_player_ids.copy()
            random.shuffle(shuffled)

            for court in range(1, num_courts + 1):
                base_idx = (court - 1) * 4
                if base_idx + 3 >= len(shuffled):
                    match_players = [shuffled[i % len(shuffled)] for i in range(base_idx, base_idx + 4)]
                else:
                    match_players = shuffled[base_idx:base_idx + 4]

                p1, p2, p3, p4 = match_players
                team1_skill = skill_map.get(p1, 0.5) + skill_map.get(p2, 0.5)
                team2_skill = skill_map.get(p3, 0.5) + skill_map.get(p4, 0.5)
                team1_score = team1_skill + random.uniform(-0.3, 0.3)
                team2_score = team2_skill + random.uniform(-0.3, 0.3)
                winning_team = 1 if team1_score > team2_score else 2

                completed = 1 if status == 'completed' else 0
                db.execute(
                    "INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (round_id, court, p1, p2, p3, p4, winning_team if completed else None, completed)
                )
                match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

                if completed:
                    winners = [p1, p2] if winning_team == 1 else [p3, p4]
                    losers = [p3, p4] if winning_team == 1 else [p1, p2]
                    for pid in winners:
                        db.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, 1)", (match_id, pid))
                        player_stats[pid]['wins'] += 1
                    for pid in losers:
                        db.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, 0)", (match_id, pid))
                        player_stats[pid]['losses'] += 1

            if status != 'completed':
                break  # Only create round 1 for active tournaments

        for pid, stats in player_stats.items():
            db.execute(
                "UPDATE tournament_players SET total_points = ?, match_wins = ?, match_losses = ? WHERE tournament_id = ? AND player_id = ?",
                (stats['wins'], stats['wins'], stats['losses'], tid, pid)
            )

        return tid

    num_players = len(player_ids)

    # Tournament 1: Large
    t1_count = min(num_players, 16)
    t1_courts = max(2, t1_count // 4)
    create_test_tournament("Tammikuun Mestaruus", player_ids[:t1_count], t1_courts, 6)

    # Tournament 2: Medium
    t2_players = [player_ids[i] for i in range(0, num_players, 2)][:min(num_players, 12)]
    if len(t2_players) < 8:
        t2_players = player_ids[:8]
    create_test_tournament("Helmikuun Haaste", t2_players, max(2, len(t2_players) // 4), 5)

    # Tournament 3: Small
    create_test_tournament("Mestarin Cup", player_ids[:8], 2, 7)

    # Tournament 4: Active
    t4_count = min(num_players, 12)
    t4_players = player_ids[2:2+t4_count] if num_players > 10 else player_ids[:t4_count]
    create_test_tournament("Marraskuu 2", t4_players, max(2, t4_count // 4), 1, status='active')

    db.commit()

    flash(f'Testidata luotu: 1 kausi, {num_players} pelaajaa, 4 turnausta')
    return redirect('/admin')


@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page with season management"""
    db = get_db_connection()

    # Check if we should keep a tournament edit form open
    edit_tournament_id = request.args.get('edit', type=int)

    # Get current season
    current_season = get_current_season(db)

    # Get archived seasons with tournament counts
    archived_seasons_raw = db.execute("""
        SELECT
            s.*,
            COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON s.id = t.season_id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.ended_at DESC, s.created_at DESC
    """).fetchall()

    # Build archived seasons list with tournaments included
    archived_seasons = []
    for season in archived_seasons_raw:
        season_dict = dict(season)
        season_dict['tournaments'] = db.execute('''
            SELECT id, name, status, created_at
            FROM tournaments
            WHERE season_id = ?
            ORDER BY created_at DESC
        ''', (season['id'],)).fetchall()
        archived_seasons.append(season_dict)

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

        # Fetch players with season wins for Players tab
        # Counts wins, tournaments, matches, calculates averages, and includes point adjustments
        # Includes players who have adjustments even if they haven't played matches
        # Includes players registered in setup tournaments (no matches yet)
        players = db.execute('''
            SELECT
                pr.id,
                pr.first_name,
                pr.last_name,
                COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as wins,
                COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0) as tournaments_played,
                COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0) as matches_played,
                ROUND(CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                      NULLIF(COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0), 0), 2) as wins_per_tournament,
                ROUND(CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                      NULLIF(COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0), 0), 2) as win_rate,
                COALESCE(adj.adjustment, 0) as adjustment,
                COALESCE(adj.tournaments_adjustment, 0) as tournaments_adjustment,
                COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) as total_points
            FROM player_registry pr
            LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
            LEFT JOIN matches m ON (pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id) AND m.completed = 1)
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id AND t.season_id = ?
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
            LEFT JOIN tournament_players tp ON pr.id = tp.player_id
            LEFT JOIN tournaments setup_t ON tp.tournament_id = setup_t.id AND setup_t.season_id = ?
            WHERE adj.adjustment IS NOT NULL OR adj.tournaments_adjustment IS NOT NULL OR t.id IS NOT NULL OR setup_t.id IS NOT NULL
            GROUP BY pr.id, pr.first_name, pr.last_name
            ORDER BY total_points DESC, wins DESC, win_rate DESC, pr.last_name ASC
        ''', (current_season['id'], current_season['id'], current_season['id'])).fetchall()

    # Get database statistics for Data tab
    db_stats = {
        'seasons': db.execute('SELECT COUNT(*) as count FROM seasons').fetchone()['count'],
        'tournaments': db.execute('SELECT COUNT(*) as count FROM tournaments').fetchone()['count'],
        'players': db.execute('SELECT COUNT(*) as count FROM player_registry').fetchone()['count'],
        'matches': db.execute('SELECT COUNT(*) as count FROM matches').fetchone()['count']
    }

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          current_season_tournaments=current_season_tournaments,
                          players=players,
                          archived_seasons=archived_seasons,
                          active_tab='seasons',
                          edit_tournament_id=edit_tournament_id,
                          db_stats=db_stats,
                          demo_mode=session.get('demo_mode', False))


@app.route('/admin/export/season-standings.csv')
def admin_export_season_standings():
    """Export current season standings as CSV for Google Sheets"""
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta vietäväksi')
        return redirect(url_for('admin_dashboard'))

    # Get players with season wins (same query as admin_dashboard)
    players = db.execute('''
        SELECT
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as wins,
            COUNT(DISTINCT t.id) as tournaments_played,
            COUNT(DISTINCT m.id) as matches_played,
            ROUND(CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                  NULLIF(COUNT(DISTINCT t.id), 0), 2) as wins_per_tournament,
            ROUND(CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                  NULLIF(COUNT(DISTINCT m.id), 0), 2) as win_rate
        FROM player_registry pr
        LEFT JOIN matches m ON (pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id))
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE t.season_id = ? AND m.completed = 1
        GROUP BY pr.id, pr.first_name, pr.last_name
        HAVING tournaments_played > 0
        ORDER BY wins DESC, win_rate DESC, pr.last_name ASC
    ''', (current_season['id'],)).fetchall()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Sija', 'Pelaaja', 'Voitot', 'Turnauksia', 'V/T', 'Otteluita', 'V/O'])

    # Data rows with ranking
    for rank, player in enumerate(players, 1):
        full_name = f"{player['first_name']} {player['last_name']}"
        writer.writerow([
            rank,
            full_name,
            player['wins'],
            player['tournaments_played'],
            f"{player['wins_per_tournament'] or 0:.2f}",
            player['matches_played'],
            f"{player['win_rate'] or 0:.2f}"
        ])

    # Prepare response
    output.seek(0)
    filename = f"{current_season['name'].replace(' ', '_')}_standings.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/export/database.json')
def admin_export_database_json():
    """Export entire database as JSON backup"""
    db = get_db_connection()

    # Define tables to export (excluding admin_users for security)
    tables = [
        'seasons',
        'tournaments',
        'rounds',
        'matches',
        'scores',
        'players',
        'player_registry',
        'player_seeding',
        'tournament_players',
        'tournament_edit_history',
        'round1_preview_pairings',
        'player_points_adjustment'
    ]

    export_data = {
        'export_date': datetime.now().isoformat(),
        'version': '1.0',
        'tables': {}
    }

    for table in tables:
        try:
            rows = db.execute(f'SELECT * FROM {table}').fetchall()
            # Convert sqlite3.Row objects to dicts
            export_data['tables'][table] = [dict(row) for row in rows]
        except Exception:
            # Table might not exist, skip it
            export_data['tables'][table] = []

    # Create JSON response
    json_output = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
    filename = f"padel_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        json_output,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/restore/database', methods=['POST'])
@block_in_demo_mode
def admin_restore_database():
    """Restore database from JSON backup"""
    db = get_db_connection()

    # Check if file was uploaded
    if 'backup_file' not in request.files:
        flash('Valitse JSON-tiedosto')
        return redirect('/admin')

    file = request.files['backup_file']
    if file.filename == '':
        flash('Valitse JSON-tiedosto')
        return redirect('/admin')

    # Parse JSON
    try:
        data = json.load(file)
    except json.JSONDecodeError:
        flash('Virheellinen JSON-tiedosto')
        return redirect('/admin')

    # Validate structure
    if 'tables' not in data:
        flash('Varmuuskopio on puutteellinen: "tables" puuttuu')
        return redirect('/admin')

    required_tables = ['seasons', 'tournaments', 'player_registry']
    for table in required_tables:
        if table not in data['tables']:
            flash(f'Varmuuskopio on puutteellinen: puuttuu {table}')
            return redirect('/admin')

    # Tables in deletion order (children first to respect foreign keys)
    delete_order = [
        'player_points_adjustment',
        'round1_preview_pairings',
        'tournament_edit_history',
        'scores',
        'matches',
        'rounds',
        'tournament_players',
        'player_seeding',
        'players',
        'tournaments',
        'seasons',
        'player_registry'
    ]

    # Tables in insertion order (parents first)
    insert_order = [
        'seasons',
        'player_registry',
        'tournaments',
        'players',
        'player_seeding',
        'tournament_players',
        'rounds',
        'matches',
        'scores',
        'tournament_edit_history',
        'round1_preview_pairings',
        'player_points_adjustment'
    ]

    try:
        # Delete all data
        for table in delete_order:
            try:
                db.execute(f'DELETE FROM {table}')
            except Exception:
                pass  # Table might not exist

        # Insert new data
        stats = {'seasons': 0, 'tournaments': 0, 'players': 0}
        for table in insert_order:
            if table in data['tables'] and data['tables'][table]:
                rows = data['tables'][table]
                if rows:
                    # Get column names from first row
                    columns = list(rows[0].keys())
                    placeholders = ', '.join(['?' for _ in columns])
                    columns_str = ', '.join(columns)

                    for row in rows:
                        values = [row.get(col) for col in columns]
                        try:
                            db.execute(
                                f'INSERT INTO {table} ({columns_str}) VALUES ({placeholders})',
                                values
                            )
                        except Exception as e:
                            # Log but continue - some rows might fail due to constraints
                            print(f"Error inserting into {table}: {e}")

                    # Track stats
                    if table == 'seasons':
                        stats['seasons'] = len(rows)
                    elif table == 'tournaments':
                        stats['tournaments'] = len(rows)
                    elif table == 'player_registry':
                        stats['players'] = len(rows)

        db.commit()
        flash(f"Tietokanta palautettu onnistuneesti. Palautettu: {stats['seasons']} kautta, {stats['tournaments']} turnausta, {stats['players']} pelaajaa.")

    except Exception as e:
        db.rollback()
        flash(f'Palautus epäonnistui: {str(e)}')

    return redirect('/admin')


@app.route('/admin/players')
def admin_players():
    """Admin players tab - view and edit player season points"""
    db = get_db_connection()

    # Get current season
    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta')
        return redirect('/admin')

    # Get all players with their season stats (points, matches, tournaments)
    # Combines auto-calculated values from completed matches with manual adjustments
    players = db.execute('''
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as wins,
            COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as total_points,
            COALESCE(adj.adjustment, 0) as adjustment,
            COALESCE(auto.auto_tournaments, 0) + COALESCE(adj.tournaments_adjustment, 0) as tournaments_played,
            COALESCE(auto.auto_matches, 0) + COALESCE(adj.matches_adjustment, 0) as matches_played,
            CASE
                WHEN (COALESCE(auto.auto_tournaments, 0) + COALESCE(adj.tournaments_adjustment, 0)) > 0
                THEN ROUND(
                    CAST(COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                    (COALESCE(auto.auto_tournaments, 0) + COALESCE(adj.tournaments_adjustment, 0)),
                    2
                )
                ELSE 0
            END as wins_per_tournament,
            CASE
                WHEN (COALESCE(auto.auto_matches, 0) + COALESCE(adj.matches_adjustment, 0)) > 0
                THEN ROUND(
                    CAST(COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                    (COALESCE(auto.auto_matches, 0) + COALESCE(adj.matches_adjustment, 0)),
                    2
                )
                ELSE 0
            END as win_rate
        FROM player_registry pr
        LEFT JOIN (
            SELECT
                pr2.id as player_id,
                COALESCE(SUM(s.points), 0) as auto_points,
                COUNT(DISTINCT m.id) as auto_matches,
                COUNT(DISTINCT t.id) as auto_tournaments
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

    # Get tournament count and list for current season
    current_tournament_count = db.execute(
        "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
        (current_season['id'],)
    ).fetchone()['count']

    current_season_tournaments = db.execute(
        "SELECT * FROM tournaments WHERE season_id = ? ORDER BY created_at DESC",
        (current_season['id'],)
    ).fetchall()

    # Get database statistics for Data tab
    db_stats = {
        'seasons': db.execute('SELECT COUNT(*) as count FROM seasons').fetchone()['count'],
        'tournaments': db.execute('SELECT COUNT(*) as count FROM tournaments').fetchone()['count'],
        'players': db.execute('SELECT COUNT(*) as count FROM player_registry').fetchone()['count'],
        'matches': db.execute('SELECT COUNT(*) as count FROM matches').fetchone()['count']
    }

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          current_season_tournaments=current_season_tournaments,
                          players=players,
                          archived_seasons=archived_seasons,
                          db_stats=db_stats,
                          active_tab='players')


@app.route('/admin/players/<int:player_id>/edit', methods=['POST'])
@block_in_demo_mode
def admin_edit_player_points(player_id):
    """Edit player season points (admin only)"""
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        flash('Ei aktiivista kautta')
        return redirect('/admin')

    try:
        new_total = int(request.form.get('new_total_points', 0))
    except ValueError:
        flash('Virheellinen pistemäärä')
        return redirect('/admin')

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

    return redirect(f'/admin?tab=players&edit_player={player_id}')


@app.route('/admin/players/import-points', methods=['POST'])
@block_in_demo_mode
def admin_import_player_points():
    """Bulk import player points from external tournament (admin only)"""
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        return jsonify({'success': False, 'error': 'Ei aktiivista kautta'}), 400

    data = request.get_json()
    if not data or 'players' not in data:
        return jsonify({'success': False, 'error': 'No players provided'}), 400

    players = data['players']
    imported_count = 0
    created_count = 0

    for player_data in players:
        first_name = player_data.get('firstName', '').strip()
        last_name = player_data.get('lastName', '').strip()
        wins = player_data.get('wins', 0)
        tournaments = player_data.get('tournaments', 0)
        matches = player_data.get('matches', 0)

        if not first_name or not last_name or wins < 0 or tournaments < 0 or matches < 0:
            continue

        # Check if player exists in registry
        existing = db.execute('''
            SELECT id FROM player_registry
            WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)
        ''', (first_name, last_name)).fetchone()

        if existing:
            player_id = existing['id']
        else:
            # Create new player in registry
            cursor = db.execute('''
                INSERT INTO player_registry (first_name, last_name, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (first_name, last_name))
            player_id = cursor.lastrowid
            created_count += 1

        # Get current adjustments (if any)
        current_adj = db.execute('''
            SELECT adjustment, tournaments_adjustment, matches_adjustment FROM player_points_adjustment
            WHERE player_id = ? AND season_id = ?
        ''', (player_id, current_season['id'])).fetchone()

        current_adjustment = current_adj['adjustment'] if current_adj else 0
        current_tournaments = current_adj['tournaments_adjustment'] if current_adj else 0
        current_matches = current_adj['matches_adjustment'] if current_adj else 0
        new_adjustment = current_adjustment + wins
        new_tournaments = current_tournaments + tournaments
        new_matches = current_matches + matches

        # Insert or update adjustment (add to existing)
        db.execute('''
            INSERT INTO player_points_adjustment (player_id, season_id, adjustment, tournaments_adjustment, matches_adjustment, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(player_id, season_id)
            DO UPDATE SET adjustment = ?, tournaments_adjustment = ?, matches_adjustment = ?, updated_at = CURRENT_TIMESTAMP
        ''', (player_id, current_season['id'], new_adjustment, new_tournaments, new_matches, new_adjustment, new_tournaments, new_matches))

        imported_count += 1

    db.commit()

    return jsonify({
        'success': True,
        'imported': imported_count,
        'created': created_count
    })


@app.route('/admin/players/fix-matches', methods=['POST'])
@block_in_demo_mode
def admin_fix_matches_adjustment():
    """Fix matches_adjustment for existing players (admin only)

    Used when historical data was imported without the matches column.
    Sets matches_adjustment to the provided value for all players who have
    wins but no matches recorded.
    """
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        return jsonify({'success': False, 'error': 'Ei aktiivista kautta'}), 400

    data = request.get_json()
    if not data or 'matches_per_player' not in data:
        return jsonify({'success': False, 'error': 'No matches_per_player provided'}), 400

    matches_per_player = int(data['matches_per_player'])
    if matches_per_player < 1:
        return jsonify({'success': False, 'error': 'matches_per_player must be at least 1'}), 400

    # Update all adjustments that have wins/tournaments but no matches
    cursor = db.execute('''
        UPDATE player_points_adjustment
        SET matches_adjustment = ?, updated_at = CURRENT_TIMESTAMP
        WHERE season_id = ?
          AND matches_adjustment = 0
          AND (adjustment > 0 OR tournaments_adjustment > 0)
    ''', (matches_per_player, current_season['id']))

    updated_count = cursor.rowcount
    db.commit()

    return jsonify({
        'success': True,
        'updated': updated_count,
        'matches_per_player': matches_per_player
    })


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
@block_in_demo_mode
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

    # Parse court numbering options
    try:
        start_from = int(request.form.get('court_start_from', 1))
    except (ValueError, TypeError):
        start_from = 1

    skip_courts_raw = request.form.get('court_skip', '').strip()
    skip_courts = []
    if skip_courts_raw:
        try:
            skip_courts = [int(x.strip()) for x in skip_courts_raw.split(',') if x.strip()]
        except ValueError:
            flash('Ohitettavat kentät tulee antaa pilkulla erotettuna (esim. "7" tai "3, 7").')
            return redirect('/admin')

    # Generate court labels
    court_labels = generate_court_labels(num_courts, start_from, skip_courts)

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
        'INSERT INTO tournaments (name, num_courts, status, season_id, court_labels) VALUES (?, ?, ?, ?, ?)',
        (tournament_name, num_courts, 'setup', current_season['id'], json.dumps(court_labels))
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
@block_in_demo_mode
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

    # Get season leaderboard rankings for badge display
    season_id = tournament['season_id']
    all_standings = db.execute("""
        SELECT
            pr.id,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) as total_points,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) + COALESCE(adj.adjustment, 0) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0), 0) * 100,
                1
            ) as win_rate
        FROM player_registry pr
        LEFT JOIN player_points_adjustment adj ON (pr.id = adj.player_id AND adj.season_id = ?)
        LEFT JOIN matches m ON (
            pr.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id)
            AND m.completed = 1
        )
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id AND t.season_id = ?
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE adj.adjustment IS NOT NULL OR adj.tournaments_adjustment IS NOT NULL OR t.id IS NOT NULL
        GROUP BY pr.id
        HAVING total_points > 0 OR COUNT(DISTINCT t.id) + COALESCE(adj.tournaments_adjustment, 0) > 0
        ORDER BY total_points DESC, win_rate DESC
    """, (season_id, season_id)).fetchall()

    # Build season rank lookup with tie handling
    season_rank_lookup = {}
    current_rank = 1
    for idx, row in enumerate(all_standings):
        if idx > 0:
            prev = all_standings[idx - 1]
            if row['total_points'] != prev['total_points'] or row['win_rate'] != prev['win_rate']:
                current_rank = idx + 1
        season_rank_lookup[row['id']] = {
            'season_rank': current_rank,
            'total_points': row['total_points'],
            'win_rate': row['win_rate']
        }

    # Get players registered for this tournament
    players = db.execute('''
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COALESCE(ps.seed_score, 0) as seed_score,
            COALESCE(ps.total_wins, 0) as total_wins,
            COALESCE(ps.total_matches, 0) as total_matches,
            COALESCE(ps.recent_tournaments, 0) as recent_tournaments
        FROM player_registry pr
        JOIN tournament_players tp ON pr.id = tp.player_id
        LEFT JOIN player_seeding ps ON pr.id = ps.player_id
        WHERE tp.tournament_id = ?
        ORDER BY ps.seed_score DESC NULLS LAST, pr.first_name, pr.last_name
    ''', (tournament_id,)).fetchall()

    # Attach season rank to players and create lookup for template
    players_with_rank = []
    player_seed_lookup = {}  # id -> {seed_score, seed_rank}
    for player in players:
        player_dict = dict(player)
        rank_info = season_rank_lookup.get(player['id'])
        player_dict['seed_rank'] = rank_info['season_rank'] if rank_info else None
        players_with_rank.append(player_dict)
        player_seed_lookup[player['id']] = {
            'seed_score': player['seed_score'],
            'seed_rank': rank_info['season_rank'] if rank_info else None,
            'total_wins': player['total_wins'],
            'total_matches': player['total_matches']
        }
    players = players_with_rank

    # Get pairings with player names and seed info
    pairings_raw = db.execute('''
        SELECT p.*,
               p1.first_name || ' ' || p1.last_name as team1_player1_name,
               p2.first_name || ' ' || p2.last_name as team1_player2_name,
               p3.first_name || ' ' || p3.last_name as team2_player1_name,
               p4.first_name || ' ' || p4.last_name as team2_player2_name,
               COALESCE(ps1.seed_score, 0) as team1_player1_seed,
               COALESCE(ps2.seed_score, 0) as team1_player2_seed,
               COALESCE(ps3.seed_score, 0) as team2_player1_seed,
               COALESCE(ps4.seed_score, 0) as team2_player2_seed
        FROM round1_preview_pairings p
        LEFT JOIN player_registry p1 ON p.team1_player1_id = p1.id
        LEFT JOIN player_registry p2 ON p.team1_player2_id = p2.id
        LEFT JOIN player_registry p3 ON p.team2_player1_id = p3.id
        LEFT JOIN player_registry p4 ON p.team2_player2_id = p4.id
        LEFT JOIN player_seeding ps1 ON p.team1_player1_id = ps1.player_id
        LEFT JOIN player_seeding ps2 ON p.team1_player2_id = ps2.player_id
        LEFT JOIN player_seeding ps3 ON p.team2_player1_id = ps3.player_id
        LEFT JOIN player_seeding ps4 ON p.team2_player2_id = ps4.player_id
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
                          edit_history=edit_history,
                          player_seed_lookup=player_seed_lookup,
                          demo_mode=session.get('demo_mode', False))


@app.route('/admin/tournaments/<int:tournament_id>/edit', methods=['POST'])
@block_in_demo_mode
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
@block_in_demo_mode
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


@app.route('/admin/tournament/<int:tournament_id>/round/<int:round_id>/recalculate', methods=['POST'])
@block_in_demo_mode
def admin_recalculate_round(tournament_id, round_id):
    """
    Recalculate round pairings based on previous round results (ADMIN only).
    Used when previous round result was corrected after this round started.
    """
    if not session.get('logged_in_as_admin'):
        flash('Vain ylläpitäjä voi laskea kierroksen uudelleen.')
        return redirect(url_for('index'))

    db = get_db_connection()

    # Get round info
    round_data = db.execute(
        'SELECT * FROM rounds WHERE id = ? AND tournament_id = ?',
        (round_id, tournament_id)
    ).fetchone()

    if not round_data:
        flash('Kierrosta ei löydy.')
        return redirect(url_for('admin_dashboard'))

    # Can't recalculate round 1 (no previous round)
    if round_data['round_number'] == 1:
        flash('Ensimmäistä kierrosta ei voi laskea uudelleen.')
        return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))

    # Check that all matches in this round are incomplete (not started)
    matches = db.execute(
        'SELECT * FROM matches WHERE round_id = ?',
        (round_id,)
    ).fetchall()

    # Get previous round matches
    previous_round = db.execute(
        'SELECT * FROM rounds WHERE tournament_id = ? AND round_number = ?',
        (tournament_id, round_data['round_number'] - 1)
    ).fetchone()

    if not previous_round:
        flash('Edellistä kierrosta ei löydy.')
        return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))

    previous_matches = db.execute(
        'SELECT * FROM matches WHERE round_id = ?',
        (previous_round['id'],)
    ).fetchall()

    # Convert to list of dicts
    previous_matches = [dict(m) for m in previous_matches]

    # Get number of courts
    tournament = db.execute(
        'SELECT num_courts FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()
    num_courts = tournament['num_courts']

    try:
        # Generate new pairings
        new_pairings = generate_next_round_pairings(previous_matches, num_courts)

        # Delete current round matches (and their scores just in case)
        for match in matches:
            db.execute('DELETE FROM scores WHERE match_id = ?', (match['id'],))
        db.execute('DELETE FROM matches WHERE round_id = ?', (round_id,))

        # Create new matches
        for court_idx, players in enumerate(new_pairings):
            db.execute(
                '''INSERT INTO matches
                   (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (round_id, court_idx + 1, players[0], players[1], players[2], players[3])
            )

        # Log the recalculation
        db.execute(
            '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
               VALUES (?, ?, ?)''',
            (tournament_id, 'round_recalculated', json.dumps({
                'round_id': round_id,
                'round_number': round_data['round_number'],
                'reason': 'Previous round result corrected'
            }))
        )

        db.commit()
        flash(f'Kierros {round_data["round_number"]} laskettu uudelleen edellisen kierroksen tulosten perusteella.')

    except ValueError as e:
        db.rollback()
        flash(f'Virhe kierroksen laskemisessa: {str(e)}')

    return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Logout and clear admin session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect('/admin/login')

# Run migrations on startup if needed (skip with SKIP_MIGRATIONS=1 for faster startup)
if not os.environ.get('SKIP_MIGRATIONS'):
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
        db = get_db_connection()
        # Check if matches table exists (fresh database may not have it yet)
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        if cursor.fetchone():
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
                tournaments_adjustment INTEGER DEFAULT 0,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE CASCADE,
                FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
                UNIQUE(player_id, season_id)
            )
        ''')

        # Migration: add adjustment columns if missing (for existing databases)
        cursor = db.execute("PRAGMA table_info(player_points_adjustment)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'tournaments_adjustment' not in columns:
            db.execute("ALTER TABLE player_points_adjustment ADD COLUMN tournaments_adjustment INTEGER DEFAULT 0")
        if 'matches_adjustment' not in columns:
            db.execute("ALTER TABLE player_points_adjustment ADD COLUMN matches_adjustment INTEGER DEFAULT 0")

        # Update player_seeding view to use wins/matches ratio from last 6 tournaments + adjustments
        db.execute("DROP VIEW IF EXISTS player_seeding")
        db.execute('''
            CREATE VIEW IF NOT EXISTS player_seeding AS
            WITH recent_tournaments AS (
                SELECT
                    tp.player_id,
                    tp.tournament_id,
                    tp.match_wins,
                    tp.match_losses,
                    ROW_NUMBER() OVER (
                        PARTITION BY tp.player_id
                        ORDER BY t.completed_at DESC
                    ) as tournament_rank
                FROM tournament_players tp
                JOIN tournaments t ON tp.tournament_id = t.id
                WHERE t.status IN ('completed', 'archived')
            ),
            player_adjustments AS (
                SELECT
                    player_id,
                    COALESCE(adjustment, 0) as wins_adj,
                    COALESCE(matches_adjustment, 0) as matches_adj
                FROM player_points_adjustment adj
                JOIN seasons s ON adj.season_id = s.id AND s.is_current = 1
            )
            SELECT
                pr.id as player_id,
                pr.first_name,
                pr.last_name,
                COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) as total_wins,
                COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0) as total_matches,
                COUNT(rt.tournament_id) as recent_tournaments,
                CASE
                    WHEN (COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0)) > 0
                    THEN ROUND(
                        CAST(COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) AS FLOAT) /
                        (COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0)),
                        3
                    )
                    ELSE 0
                END as seed_score,
                COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) as seed_points
            FROM player_registry pr
            LEFT JOIN recent_tournaments rt ON pr.id = rt.player_id AND rt.tournament_rank <= 6
            LEFT JOIN player_adjustments pa ON pr.id = pa.player_id
            GROUP BY pr.id, pr.first_name, pr.last_name, pa.wins_adj, pa.matches_adj
            ORDER BY seed_score DESC, total_wins DESC, last_name ASC, first_name ASC
        ''')
        print("✅ Player seeding view updated")

        db.commit()
else:
    print("⏭️ Skipping migrations (SKIP_MIGRATIONS=1)")

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
