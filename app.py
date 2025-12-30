from flask import Flask, render_template, request, redirect, url_for, flash, g, session
import os
import sqlite3
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

def get_tournament_leaderboard(tournament_id):
    """Get player standings for a specific tournament"""
    db = get_db_connection()

    players = db.execute(
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
    """Landing page - shows active tournament or setup option"""
    from datetime import datetime
    db = get_db_connection()
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE status = "active" LIMIT 1'
    ).fetchone()

    if tournament:
        return redirect(url_for('active_tournament', tournament_id=tournament['id']))

    # Get current year
    current_year = datetime.now().year

    # Check if any tournaments exist
    has_tournaments = db.execute(
        'SELECT COUNT(*) as count FROM tournaments'
    ).fetchone()['count'] > 0

    # Get tournaments from current year
    tournaments = db.execute(
        '''SELECT * FROM tournaments
           WHERE strftime('%Y', created_at) = ?
           ORDER BY created_at DESC''',
        (str(current_year),)
    ).fetchall()

    return render_template('index.html',
                          has_tournaments=has_tournaments,
                          current_year=current_year,
                          tournaments=tournaments)

@app.route('/setup', methods=['GET', 'POST'])
def setup_tournament():
    """Setup new tournament and add players"""
    if request.method == 'POST':
        db = get_db_connection()

        # Check for current season
        current_season = get_current_season(db)
        if not current_season:
            flash('No active season. Please create or activate a season first.')
            return redirect(url_for('seasons_management'))

        tournament_name = request.form.get('tournament_name')
        num_courts = int(request.form.get('num_courts'))
        player_names = request.form.get('players').strip().split('\n')

        # Clean up player names
        player_names = [name.strip() for name in player_names if name.strip()]

        # Validate player count
        required_players = num_courts * 4
        if len(player_names) < required_players:
            flash(f'Need at least {required_players} players for {num_courts} courts. You provided {len(player_names)}.')
            return render_template('setup_tournament.html')

        # Create tournament with season_id
        cursor = db.execute(
            'INSERT INTO tournaments (name, num_courts, status, season_id) VALUES (?, ?, ?, ?)',
            (tournament_name, num_courts, 'setup', current_season['id'])
        )
        tournament_id = cursor.lastrowid

        # Add players to Phase 3 player_registry
        for name in player_names:
            # Split name into first and last (assume "First Last" format)
            parts = name.strip().split(' ', 1)
            first_name = parts[0] if len(parts) > 0 else ''
            last_name = parts[1] if len(parts) > 1 else ''

            try:
                db.execute(
                    'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                    (first_name, last_name)
                )
            except sqlite3.IntegrityError:
                flash(f'Player {name} already exists, skipping')

        db.commit()
        flash('Tournament created successfully!')
        return redirect(url_for('start_round', tournament_id=tournament_id))

    return render_template('setup_tournament.html')

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

    if request.method == 'POST':
        # Get all players from player_registry (Phase 3)
        players = db.execute('SELECT id FROM player_registry ORDER BY RANDOM()').fetchall()
        num_players = len(players)
        num_courts = tournament['num_courts']

        # Validate we have enough players (4 per court)
        required_players = num_courts * 4
        if num_players < required_players:
            flash(f'Need {required_players} players for {num_courts} courts. You have {num_players}.')
            return redirect(url_for('setup_tournament'))

        # Get or create current round
        last_round = db.execute(
            'SELECT * FROM rounds WHERE tournament_id = ? ORDER BY round_number DESC LIMIT 1',
            (tournament_id,)
        ).fetchone()

        round_number = 1 if not last_round else last_round['round_number'] + 1

        cursor = db.execute(
            'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
            (tournament_id, round_number)
        )
        round_id = cursor.lastrowid

        # Determine pairing strategy
        if round_number == 1:
            # Round 1: Seeded pairing (Phase 3 feature)
            from seeded_pairing import generate_seeded_round1_pairings

            # Get players with their seed points from player_seeding view
            # For Phase 3, we use player_registry + player_seeding
            # For backward compatibility with Phase 2, fall back to players table
            try:
                players_with_seeds = db.execute("""
                    SELECT
                        p.id,
                        COALESCE(ps.seed_points, 0) as seed_points
                    FROM player_registry p
                    LEFT JOIN player_seeding ps ON p.id = ps.id
                    ORDER BY seed_points DESC
                """).fetchall()
            except:
                # Fallback if player_seeding view doesn't exist
                players_with_seeds = db.execute("""
                    SELECT id, 0 as seed_points
                    FROM player_registry
                """).fetchall()

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

        # Update tournament status
        db.execute(
            'UPDATE tournaments SET status = "active" WHERE id = ?',
            (tournament_id,)
        )
        db.commit()

        flash(f"Round {round_number} created! Players, go to your courts to confirm teams.")
        return redirect(url_for('court_selection', tournament_id=tournament_id, round_id=round_id))

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

@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/courts')
def court_selection(tournament_id, round_id):
    """
    Display court selection screen for a round.

    Shows all courts for this round with algorithm-generated team pairings.
    Users can click "Go to Court N" to proceed to the pre-match confirmation
    screen where they can optionally shuffle teams before starting the match.

    Args:
        tournament_id (int): ID of the tournament
        round_id (int): ID of the round

    Returns:
        Rendered template (court_selection.html) with court grid, or
        redirect to index with flash message on error

    Redirects to index if:
        - Tournament not found
        - Round not found
        - Round doesn't belong to tournament
        - No matches found for round

    Template variables:
        tournament: Tournament database row
        round: Round database row
        matches: List of match dicts with enriched player data
    """
    db = get_db_connection()

    # Get tournament
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
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

    # Get all matches for this round
    matches = db.execute(
        'SELECT * FROM matches WHERE round_id = ? ORDER BY court_number',
        (round_id,)
    ).fetchall()

    # Check for empty matches
    if not matches:
        flash('No matches found for this round. Please contact the organizer.')
        return redirect(url_for('index'))

    # Add player details to each match
    matches_with_players = []
    for match in matches:
        match_dict = dict(match)
        match_dict['player1'] = get_player(match['player1_id'])
        match_dict['player2'] = get_player(match['player2_id'])
        match_dict['player3'] = get_player(match['player3_id'])
        match_dict['player4'] = get_player(match['player4_id'])
        matches_with_players.append(match_dict)

    # Check if all matches are completed
    all_completed = all(match['completed'] for match in matches)

    return render_template(
        'court_selection.html',
        tournament=tournament,
        round=round_obj,
        matches=matches_with_players,
        all_completed=all_completed
    )

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

    # Handle POST request (save shuffled teams)
    if request.method == 'POST':
        # Get match first
        match = db.execute(
            'SELECT * FROM matches WHERE round_id = ? AND court_number = ?',
            (round_id, court_number)
        ).fetchone()

        if not match:
            flash('Match not found')
            return redirect(url_for('court_selection', tournament_id=tournament_id, round_id=round_id))

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

    round_data = db.execute('SELECT * FROM rounds WHERE id = ?', (round_id,)).fetchone()

    if not round_data:
        flash('Round not found')
        return redirect(url_for('index'))

    # Get all matches with player names
    matches = db.execute(
        '''SELECT
            m.*,
            p1.name as player1_name,
            p2.name as player2_name,
            p3.name as player3_name,
            p4.name as player4_name
           FROM matches m
           JOIN players p1 ON m.player1_id = p1.id
           JOIN players p2 ON m.player2_id = p2.id
           JOIN players p3 ON m.player3_id = p3.id
           JOIN players p4 ON m.player4_id = p4.id
           WHERE m.round_id = ?
           ORDER BY m.court_number''',
        (round_id,)
    ).fetchall()

    # Check if all matches are completed
    all_completed = all(match['completed'] for match in matches)

    return render_template('active_round.html',
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
            flash('Score updated successfully!')
        else:
            # Record new scores (1 point for winners)
            for player_id in winner_ids:
                db.execute(
                    'INSERT INTO scores (player_id, match_id, points) VALUES (?, ?, ?)',
                    (player_id, match_id, 1)
                )
            flash('Score recorded successfully!')

        # Mark match as completed
        db.execute(
            'UPDATE matches SET completed = 1, winning_team = ? WHERE id = ?',
            (winning_team, match_id)
        )

        db.commit()

        return redirect(url_for('court_selection',
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

    flash('Tournament ended successfully!')
    return redirect(url_for('leaderboard', tournament_id=tournament_id))

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
    players = db.execute(
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
        GROUP BY pr.id, pr.first_name, pr.last_name
        HAVING total_matches > 0
        ORDER BY total_wins DESC, win_rate DESC, pr.last_name ASC
    """, (current_season['id'],)).fetchall()

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

    return render_template('season_leaderboard.html',
                          season_name=current_season['name'],
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
            GROUP BY pr.id, pr.first_name, pr.last_name
            HAVING total_matches > 0
            ORDER BY total_wins DESC, win_rate DESC, pr.last_name ASC
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
    """Clear all tournament and player data - complete reset"""
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

@app.route('/tournament/<int:tournament_id>/complete', methods=['POST'])
def complete_tournament(tournament_id):
    """Complete a tournament - calculate final stats and set status to completed"""
    conn = get_db()
    cursor = conn.cursor()

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
        for idx, player_row in enumerate(ranked_players):
            cursor.execute('''
                UPDATE tournament_players
                SET final_rank = ?
                WHERE tournament_id = ? AND player_id = ?
            ''', (current_rank, tournament_id, player_row['player_id']))
            current_rank += 1

        # Update tournament status to completed
        cursor.execute('''
            UPDATE tournaments
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tournament_id,))

        conn.commit()
        flash('Tournament completed successfully!', 'success')
        return redirect(url_for('tournament_results', tournament_id=tournament_id))

    except Exception as e:
        conn.rollback()
        flash(f'Error completing tournament: {e}', 'error')
        return redirect(url_for('active_tournament', tournament_id=tournament_id))
    finally:
        conn.close()

@app.route('/tournament/<int:tournament_id>/archive', methods=['POST'])
def archive_tournament(tournament_id):
    """Archive a completed tournament (read-only)"""
    db = get_db()

    tournament = db.execute(
        "SELECT status FROM tournaments WHERE id = ?",
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    if tournament['status'] != 'completed':
        flash("Can only archive completed tournaments")
        return redirect('/')

    db.execute("""
        UPDATE tournaments
        SET status = 'archived', archived_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (tournament_id,))
    db.commit()

    flash("Tournament archived")
    return redirect('/')

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
        ORDER BY pr.last_name, pr.first_name
    """).fetchall()

    return render_template('players_list.html', players=players)

# ============================================================
# SEASON MANAGEMENT ROUTES
# ============================================================

@app.route('/seasons')
def seasons_management():
    """Display season management admin page"""
    db = get_db()

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
    if current_season:
        current_tournament_count = db.execute(
            "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']
    else:
        current_tournament_count = 0

    return render_template('seasons_management.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          archived_seasons=archived_seasons)

@app.route('/seasons/end-current', methods=['POST'])
def end_current_season():
    """End the current season without creating a new one"""
    db = get_db()

    current_season = get_current_season(db)
    if not current_season:
        flash('No current season to end')
        return redirect(url_for('seasons_management'))

    from datetime import datetime
    db.execute(
        "UPDATE seasons SET is_current = 0, ended_at = ? WHERE id = ?",
        (datetime.now(), current_season['id'])
    )
    db.commit()

    flash(f"Season '{current_season['name']}' has been ended")
    return redirect(url_for('seasons_management'))

@app.route('/seasons/create', methods=['POST'])
def create_season():
    """Create a new season and make it current"""
    db = get_db()
    season_name = request.form.get('season_name', '').strip()

    # Validation
    if not season_name:
        flash('Season name is required')
        return redirect(url_for('seasons_management'))

    if len(season_name) > 100:
        flash('Season name must be 100 characters or less')
        return redirect(url_for('seasons_management'))

    # Check for duplicate
    existing = db.execute(
        "SELECT id FROM seasons WHERE name = ?", (season_name,)
    ).fetchone()

    if existing:
        flash('Season name already exists. Please choose a different name.')
        return redirect(url_for('seasons_management'))

    # Archive current season if exists
    db.execute("UPDATE seasons SET is_current = 0 WHERE is_current = 1")

    # Create new season
    db.execute(
        "INSERT INTO seasons (name, is_current) VALUES (?, 1)",
        (season_name,)
    )
    db.commit()

    flash(f"Season '{season_name}' created successfully!")
    return redirect(url_for('seasons_management'))

@app.route('/seasons/<int:season_id>/activate', methods=['POST'])
def activate_season(season_id):
    """Reactivate an archived season as the current season"""
    db = get_db()

    season = db.execute(
        "SELECT * FROM seasons WHERE id = ?", (season_id,)
    ).fetchone()

    if not season:
        flash('Season not found')
        return redirect(url_for('seasons_management'))

    set_current_season(db, season_id)

    flash(f"Season '{season['name']}' is now active")
    return redirect(url_for('seasons_management'))

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


@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page"""
    return render_template('admin_dashboard.html')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Logout and clear admin session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect('/admin/login')

# Run migration on startup if needed
with app.app_context():
    from migration import run_migration_if_needed
    result = run_migration_if_needed()
    if result == "migrated":
        print("✅ Data migration completed: Tournaments assigned to seasons")
    elif result == "already_migrated":
        print("✅ Data already migrated")
if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
