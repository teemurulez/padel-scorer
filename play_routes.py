"""
Play Blueprint — score entry and active tournament routes.

Contains the tournament-critical score entry flow:
- Active tournament/round views
- Team confirmation with drag-and-drop shuffle
- Score entry and result correction
- SSE live updates
- Round generation (start_round)
- Pairings text API
"""

import json
import os
import queue
import sqlite3

from flask import (
    Blueprint, Response, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from court_movement import generate_next_round_pairings
from helpers import (
    get_court_labels, get_db_connection, get_player,
    get_result_correction_scenario, validate_saved_pairings_still_valid,
)

play_bp = Blueprint('play', __name__)

# Module-level reference to the SSE broadcaster, set by init_play_routes()
_sse_broadcaster = None


def init_play_routes(sse_broadcaster):
    """Initialize the play blueprint with app-level dependencies."""
    global _sse_broadcaster
    _sse_broadcaster = sse_broadcaster


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_match_player_names(match_dict):
    """Add player name strings to a match dict (mutates in place)."""
    for i in range(1, 5):
        player = get_player(match_dict[f'player{i}_id'])
        match_dict[f'player{i}_name'] = f"{player['first_name']} {player['last_name']}"


def _check_tournament_playable(tournament):
    """Check tournament exists and is not completed/archived.

    Returns an error redirect response, or None if OK.
    """
    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))
    if tournament['status'] == 'completed':
        flash('Turnaus on päättynyt.')
        return redirect(url_for('index'))
    if tournament['status'] == 'archived':
        flash('Cannot modify archived tournament.')
        return redirect(url_for('index'))
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@play_bp.route('/tournament/<int:tournament_id>')
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
        return redirect(url_for('.start_round', tournament_id=tournament_id))

    return redirect(url_for('.active_round',
                           tournament_id=tournament_id,
                           round_id=current_round['id']))


@play_bp.route('/tournament/<int:tournament_id>/round/<int:round_id>')
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

    # Get all matches
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
        _load_match_player_names(match_dict)
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


@play_bp.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm', methods=['GET', 'POST'])
def confirm_match_teams(tournament_id, round_id, court_number):
    """
    Show pre-match confirmation screen with drag-and-drop team shuffling (GET).
    Save final team configuration and proceed to score entry (POST).
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
            return redirect(url_for('.active_round', tournament_id=tournament_id, round_id=round_id))

        # Get submitted team configuration
        try:
            new_team1_p1 = int(request.form['team1_player1'])
            new_team1_p2 = int(request.form['team1_player2'])
            new_team2_p1 = int(request.form['team2_player1'])
            new_team2_p2 = int(request.form['team2_player2'])
        except (KeyError, ValueError):
            flash("Invalid form submission.")
            return redirect(url_for('.confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 1: Exactly 4 unique players
        submitted_players = [new_team1_p1, new_team1_p2, new_team2_p1, new_team2_p2]
        if len(set(submitted_players)) != 4:
            flash("Invalid team configuration: All 4 players must be unique.")
            return redirect(url_for('.confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 2: Players must be from original match
        original_players = {match['player1_id'], match['player2_id'], match['player3_id'], match['player4_id']}
        if set(submitted_players) != original_players:
            flash("Invalid team configuration: Players must be from the original match.")
            return redirect(url_for('.confirm_match_teams',
                                    tournament_id=tournament_id,
                                    round_id=round_id,
                                    court_number=court_number))

        # Validation 3: Teams must have exactly 2 players each
        if len({new_team1_p1, new_team1_p2}) != 2 or len({new_team2_p1, new_team2_p2}) != 2:
            flash("Each team must have exactly 2 different players.")
            return redirect(url_for('.confirm_match_teams',
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
        return redirect(url_for('.score_entry', match_id=match['id']))

    # Handle GET request (show confirmation screen)
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    error = _check_tournament_playable(tournament)
    if error:
        return error

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
            return redirect(url_for('.active_round', tournament_id=tournament_id, round_id=round_id))
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


@play_bp.route('/api/tournament/<int:tournament_id>/pairings-text')
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


@play_bp.route('/tournament/<int:tournament_id>/start_round', methods=['GET', 'POST'])
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
                return redirect(url_for('.active_round', tournament_id=tournament_id, round_id=last_round['id']))

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
        return redirect(url_for('.active_round', tournament_id=tournament_id, round_id=round_id))

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


@play_bp.route('/match/<int:match_id>/score', methods=['GET', 'POST'])
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
            return redirect(url_for('.active_round',
                                   tournament_id=match['tournament_id'],
                                   round_id=match['round_id']))

    # Get player details using helper function (Phase 3 compatible)
    match = dict(match)
    _load_match_player_names(match)

    if request.method == 'POST':
        winning_team = int(request.form.get('winning_team', 0))

        # Validate winning_team value
        if winning_team not in (1, 2):
            flash('Virheellinen tulosvalinta.')
            return redirect(url_for('.score_entry', match_id=match_id))

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
        _sse_broadcaster.broadcast(match['round_id'], 'score_updated', {
            'match_id': match_id,
            'court_number': match['court_number'],
            'winning_team': winning_team
        })

        return redirect(url_for('.active_round',
                               tournament_id=match['tournament_id'],
                               round_id=match['round_id']))

    return render_template('score_entry.html', match=match, is_editing=is_editing)


@play_bp.route('/sse/round/<int:round_id>')
def sse_round_stream(round_id):
    """Server-Sent Events stream for live round updates."""
    # Disable SSE on hosts that don't support long-polling (e.g., PythonAnywhere with 1 worker)
    if os.environ.get('DISABLE_SSE'):
        return jsonify({'error': 'SSE disabled', 'message': 'Use polling instead'}), 503

    def event_stream():
        q = _sse_broadcaster.subscribe(round_id)
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
            _sse_broadcaster.unsubscribe(round_id, q)

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


@play_bp.route('/tournament/<int:tournament_id>/round/<int:round_id>/matches-partial')
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
        _load_match_player_names(match_dict)
        matches.append(match_dict)

    all_completed = all(match['completed'] for match in matches)

    return render_template('_matches_partial.html',
                          tournament_id=tournament_id,
                          round_data=round_data,
                          matches=matches,
                          all_completed=all_completed)
