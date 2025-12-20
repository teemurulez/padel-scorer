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
            # Round 1: Random pairing (existing logic)
            player_list = list(players)
            random.shuffle(player_list)

            for court in range(num_courts):
                idx = court * 4
                if idx + 3 < num_players:
                    db.execute(
                        '''INSERT INTO matches
                           (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (round_id, court + 1,
                         player_list[idx]['id'],
                         player_list[idx + 1]['id'],
                         player_list[idx + 2]['id'],
                         player_list[idx + 3]['id'])
                    )
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

        return redirect(url_for('active_round', tournament_id=tournament_id, round_id=round_id))

    # Get current round if exists
    current_round = db.execute(
        '''SELECT * FROM rounds
           WHERE tournament_id = ? AND status = "in_progress"
           ORDER BY round_number DESC LIMIT 1''',
        (tournament_id,)
    ).fetchone()

    return render_template('start_round.html', tournament=tournament, current_round=current_round)

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

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
