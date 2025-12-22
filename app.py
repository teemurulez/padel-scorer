from flask import Flask, render_template, request, redirect, url_for, flash, g
import os
import random
import sqlite3
from config import Config
from database import get_db, init_db
from court_movement import generate_next_round_pairings

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
def close_db(error):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

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

# Routes

@app.route('/')
def index():
    """Landing page - shows active tournament or setup option"""
    db = get_db_connection()
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE status = "active" LIMIT 1'
    ).fetchone()

    if tournament:
        return redirect(url_for('active_tournament', tournament_id=tournament['id']))

    return render_template('index.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup_tournament():
    """Setup new tournament and add players"""
    if request.method == 'POST':
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

        db = get_db_connection()

        # Create tournament
        cursor = db.execute(
            'INSERT INTO tournaments (name, num_courts, status) VALUES (?, ?, ?)',
            (tournament_name, num_courts, 'setup')
        )
        tournament_id = cursor.lastrowid

        # Add players
        for name in player_names:
            try:
                db.execute('INSERT INTO players (name) VALUES (?)', (name,))
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
        # Get all players
        players = db.execute('SELECT * FROM players ORDER BY RANDOM()').fetchall()
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
                    FROM players p
                    LEFT JOIN player_seeding ps ON p.id = ps.player_id
                    WHERE p.tournament_id = ?
                    ORDER BY seed_points DESC
                """, (tournament_id,)).fetchall()
            except:
                # Fallback if player_seeding view doesn't exist (Phase 2)
                players_with_seeds = db.execute("""
                    SELECT id, 0 as seed_points
                    FROM players
                    WHERE tournament_id = ?
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

    return render_template('start_round.html', tournament=tournament, current_round=current_round)

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

    return render_template(
        'court_selection.html',
        tournament=tournament,
        round=round_obj,
        matches=matches_with_players
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

        # Redirect to active tournament (score entry screen)
        return redirect(url_for('active_tournament', tournament_id=tournament_id))

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
        '''SELECT
            m.*,
            r.tournament_id,
            p1.name as player1_name,
            p2.name as player2_name,
            p3.name as player3_name,
            p4.name as player4_name
           FROM matches m
           JOIN rounds r ON m.round_id = r.id
           JOIN players p1 ON m.player1_id = p1.id
           JOIN players p2 ON m.player2_id = p2.id
           JOIN players p3 ON m.player3_id = p3.id
           JOIN players p4 ON m.player4_id = p4.id
           WHERE m.id = ?''',
        (match_id,)
    ).fetchone()

    if not match:
        flash('Match not found')
        return redirect(url_for('index'))

    if match['completed']:
        flash('This match has already been scored')
        return redirect(url_for('active_round',
                               tournament_id=match['tournament_id'],
                               round_id=match['round_id']))

    if request.method == 'POST':
        winning_team = int(request.form.get('winning_team'))

        # Determine winners
        if winning_team == 1:
            winner_ids = [match['player1_id'], match['player2_id']]
        else:
            winner_ids = [match['player3_id'], match['player4_id']]

        # Record scores (1 point for winners)
        for player_id in winner_ids:
            db.execute(
                'INSERT INTO scores (player_id, match_id, points) VALUES (?, ?, ?)',
                (player_id, match_id, 1)
            )
            # Update player's total points
            db.execute(
                'UPDATE players SET total_points = total_points + 1 WHERE id = ?',
                (player_id,)
            )

        # Mark match as completed
        db.execute(
            'UPDATE matches SET completed = 1, winning_team = ? WHERE id = ?',
            (winning_team, match_id)
        )

        db.commit()
        flash('Score recorded successfully!')

        return redirect(url_for('active_round',
                               tournament_id=match['tournament_id'],
                               round_id=match['round_id']))

    return render_template('score_entry.html', match=match)

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

    # Get all players with their match statistics
    players = db.execute(
        '''SELECT
            p.id,
            p.name,
            p.total_points,
            COUNT(DISTINCT s.match_id) as matches_played,
            ROUND(CAST(p.total_points AS FLOAT) /
                  NULLIF(COUNT(DISTINCT s.match_id), 0) * 100, 1) as win_rate
           FROM players p
           LEFT JOIN scores s ON p.id = s.player_id
           LEFT JOIN matches m ON s.match_id = m.id
           LEFT JOIN rounds r ON m.round_id = r.id
           WHERE r.tournament_id = ?
           GROUP BY p.id, p.name, p.total_points
           ORDER BY p.total_points DESC, p.name ASC''',
        (tournament_id,)
    ).fetchall()

    return render_template('leaderboard.html',
                          tournament=tournament,
                          players=players)

@app.route('/tournament/<int:tournament_id>/complete', methods=['POST'])
def complete_tournament(tournament_id):
    """Complete a tournament and calculate final rankings"""
    db = get_db()

    tournament = db.execute(
        "SELECT * FROM tournaments WHERE id = ?",
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    # Calculate final rankings based on total_points
    players_ranked = db.execute("""
        SELECT
            tp.player_id,
            tp.total_points,
            pr.first_name,
            pr.last_name
        FROM tournament_players tp
        JOIN player_registry pr ON tp.player_id = pr.id
        WHERE tp.tournament_id = ?
        ORDER BY tp.total_points DESC, pr.last_name ASC
    """, (tournament_id,)).fetchall()

    # Update final_rank for each player
    for rank, player in enumerate(players_ranked, start=1):
        db.execute("""
            UPDATE tournament_players
            SET final_rank = ?
            WHERE tournament_id = ? AND player_id = ?
        """, (rank, tournament_id, player['player_id']))

    # Update tournament status
    db.execute("""
        UPDATE tournaments
        SET status = 'completed', completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (tournament_id,))

    db.commit()

    winner = players_ranked[0] if players_ranked else None
    if winner:
        flash(f"Tournament completed! Winner: {winner['first_name']} {winner['last_name']}")
    else:
        flash("Tournament completed!")

    return redirect('/')

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
    cursor = db.execute(
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

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
