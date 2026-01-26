# tests/test_result_correction.py
"""Tests for the match result correction feature"""
import pytest
import json
from app import app, get_result_correction_scenario
from database import get_db


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_result_correction.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def admin_client(client):
    """Create test client with admin logged in"""
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    with client.session_transaction() as sess:
        sess['logged_in_as_admin'] = True

    return client


def create_tournament_with_rounds(db, num_rounds=1):
    """Helper to create a tournament with completed rounds"""
    # Create season
    db.execute("INSERT INTO seasons (name, is_current) VALUES ('Test Season', 1)")

    # Create tournament
    db.execute(
        "INSERT INTO tournaments (name, num_courts, status, season_id) VALUES ('Test Tournament', 2, 'active', 1)"
    )
    tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Create 8 players in registry
    for i in range(1, 9):
        db.execute(
            "INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
            (f'Player{i}', f'Last{i}')
        )

    # Add players to tournament
    for i in range(1, 9):
        db.execute(
            "INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
            (tournament_id, i)
        )

    round_ids = []
    for round_num in range(1, num_rounds + 1):
        # Create round
        db.execute(
            "INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, ?, 'in_progress')",
            (tournament_id, round_num)
        )
        round_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        round_ids.append(round_id)

        # Create matches for this round
        db.execute(
            '''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
               VALUES (?, 1, 1, 2, 3, 4, 1, 1)''',
            (round_id,)
        )
        db.execute(
            '''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
               VALUES (?, 2, 5, 6, 7, 8, 2, 1)''',
            (round_id,)
        )

    db.commit()
    return tournament_id, round_ids


class TestGetResultCorrectionScenario:
    """Tests for get_result_correction_scenario helper function"""

    def test_scenario1_no_next_round(self, client):
        """Test scenario 1: Safe to edit when no next round exists"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)

            # Get first match
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

            result = get_result_correction_scenario(match['id'], db)

            assert result['scenario'] == 1
            assert result['can_edit'] is True
            assert result['next_round_id'] is None
            assert result['message'] is None

    def test_scenario2_next_round_exists(self, client):
        """Test scenario 2: Blocked when next round exists"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)

            # Get match from round 1
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

            result = get_result_correction_scenario(match['id'], db)

            assert result['scenario'] == 2
            assert result['can_edit'] is False
            assert result['next_round_id'] == round_ids[1]
            assert 'Seuraava kierros' in result['message']

    def test_nonexistent_match(self, client):
        """Test handling of nonexistent match"""
        with app.app_context():
            db = get_db()
            result = get_result_correction_scenario(99999, db)

            assert result['scenario'] is None
            assert result['can_edit'] is False


class TestScoreEntryScenarioBlocking:
    """Tests for score_entry route scenario blocking"""

    def test_regular_user_blocked_scenario2(self, client):
        """Test that regular users are blocked when next round exists"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

        # Try to access score entry for round 1 match (scenario 2)
        response = client.get(f'/match/{match["id"]}/score')

        # Should redirect back to active_round
        assert response.status_code == 302

    def test_regular_user_allowed_scenario1(self, client):
        """Test that regular users can edit when no next round"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

        # Try to access score entry for round 1 match (scenario 1)
        response = client.get(f'/match/{match["id"]}/score')

        # Should be allowed
        assert response.status_code == 200

    def test_admin_allowed_scenario2(self, admin_client):
        """Test that admin can access score entry in scenario 2"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

        # Try to access score entry for round 1 match as admin
        response = admin_client.get(f'/match/{match["id"]}/score')

        # Admin should be allowed
        assert response.status_code == 200

    def test_info_banner_shown_when_editing(self, client):
        """Test that info banner shows current winner when editing"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)
            match = db.execute("SELECT id FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()

        response = client.get(f'/match/{match["id"]}/score')

        assert response.status_code == 200
        assert 'Nykyinen voittaja'.encode('utf-8') in response.data


class TestAdminRecalculateRound:
    """Tests for admin recalculate round route"""

    def test_recalculate_requires_admin(self, client):
        """Test that recalculate route requires admin"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)

        response = client.post(f'/admin/tournament/{tournament_id}/round/{round_ids[1]}/recalculate')

        # Should redirect to index (not logged in)
        assert response.status_code == 302

    def test_recalculate_round1_blocked(self, admin_client):
        """Test that round 1 cannot be recalculated"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)

            # Make round 1 matches incomplete for the test
            db.execute("UPDATE matches SET completed = 0, winning_team = NULL WHERE round_id = ?", (round_ids[0],))
            db.commit()

        response = admin_client.post(f'/admin/tournament/{tournament_id}/round/{round_ids[0]}/recalculate')

        # Should redirect with error flash
        assert response.status_code == 302

    def test_recalculate_with_completed_matches_blocked(self, admin_client):
        """Test that recalculate is blocked if round has completed matches"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            # Round 2 matches are already completed

        response = admin_client.post(f'/admin/tournament/{tournament_id}/round/{round_ids[1]}/recalculate')

        # Should redirect with error
        assert response.status_code == 302

    def test_recalculate_success(self, admin_client):
        """Test successful round recalculation"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)

            # Make round 2 matches incomplete
            db.execute("UPDATE matches SET completed = 0, winning_team = NULL WHERE round_id = ?", (round_ids[1],))
            db.commit()

            # Get original round 2 matches
            original_matches = db.execute(
                "SELECT * FROM matches WHERE round_id = ?", (round_ids[1],)
            ).fetchall()
            original_player_sets = [
                {m['player1_id'], m['player2_id'], m['player3_id'], m['player4_id']}
                for m in original_matches
            ]

        response = admin_client.post(f'/admin/tournament/{tournament_id}/round/{round_ids[1]}/recalculate')

        assert response.status_code == 302

        with app.app_context():
            db = get_db()
            # Verify new matches exist
            new_matches = db.execute(
                "SELECT * FROM matches WHERE round_id = ?", (round_ids[1],)
            ).fetchall()

            assert len(new_matches) == 2  # Still 2 courts

            # Verify audit log entry
            history = db.execute(
                "SELECT * FROM tournament_edit_history WHERE tournament_id = ? AND change_type = 'round_recalculated'",
                (tournament_id,)
            ).fetchone()

            assert history is not None
            change_data = json.loads(history['change_data'])
            assert change_data['round_number'] == 2


class TestResultCorrectionAuditLogging:
    """Tests for audit logging when correcting results"""

    def test_result_correction_logged(self, client):
        """Test that correcting a result creates audit log entry"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)
            match = db.execute("SELECT * FROM matches WHERE round_id = ?", (round_ids[0],)).fetchone()
            match_id = match['id']
            old_winner = match['winning_team']

        # Change the result
        new_winner = 2 if old_winner == 1 else 1
        response = client.post(f'/match/{match_id}/score', data={
            'winning_team': new_winner,
            'version': 1
        })

        assert response.status_code == 302

        with app.app_context():
            db = get_db()
            # Check audit log
            history = db.execute(
                "SELECT * FROM tournament_edit_history WHERE tournament_id = ? AND change_type = 'result_corrected'",
                (tournament_id,)
            ).fetchone()

            assert history is not None
            change_data = json.loads(history['change_data'])
            assert change_data['match_id'] == match_id
            assert change_data['old_winning_team'] == old_winner
            assert change_data['new_winning_team'] == new_winner


class TestActiveRoundRecalculateButton:
    """Tests for recalculate button visibility in active_round template"""

    def test_recalculate_button_hidden_for_regular_user(self, client):
        """Test that recalculate button is not shown to regular users"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            # Make round 2 incomplete
            db.execute("UPDATE matches SET completed = 0, winning_team = NULL WHERE round_id = ?", (round_ids[1],))
            db.commit()

        response = client.get(f'/tournament/{tournament_id}/round/{round_ids[1]}')

        assert response.status_code == 200
        assert 'Laske kierros uudelleen'.encode('utf-8') not in response.data

    def test_recalculate_button_shown_for_admin(self, admin_client):
        """Test that recalculate button is shown to admin when previous round was edited"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            # Make round 2 incomplete
            db.execute("UPDATE matches SET completed = 0, winning_team = NULL WHERE round_id = ?", (round_ids[1],))
            # Backdate round 2's created_at so the correction appears to be after it
            db.execute("UPDATE rounds SET created_at = datetime('now', '-1 hour') WHERE id = ?", (round_ids[1],))
            # Add a result correction for round 1 (after round 2 was created)
            db.execute(
                '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
                   VALUES (?, 'result_corrected', ?)''',
                (tournament_id, json.dumps({'round_id': round_ids[0], 'old_winning_team': 1, 'new_winning_team': 2}))
            )
            db.commit()

        response = admin_client.get(f'/tournament/{tournament_id}/round/{round_ids[1]}')

        assert response.status_code == 200
        assert 'Laske kierros uudelleen'.encode('utf-8') in response.data

    def test_recalculate_button_hidden_for_round1(self, admin_client):
        """Test that recalculate button is not shown for round 1"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=1)
            # Make round 1 incomplete
            db.execute("UPDATE matches SET completed = 0, winning_team = NULL WHERE round_id = ?", (round_ids[0],))
            db.commit()

        response = admin_client.get(f'/tournament/{tournament_id}/round/{round_ids[0]}')

        assert response.status_code == 200
        assert 'Laske kierros uudelleen'.encode('utf-8') not in response.data

    def test_recalculate_button_hidden_when_matches_completed(self, admin_client):
        """Test that recalculate button is hidden when matches are completed"""
        with app.app_context():
            db = get_db()
            tournament_id, round_ids = create_tournament_with_rounds(db, num_rounds=2)
            # Round 2 matches are already completed

        response = admin_client.get(f'/tournament/{tournament_id}/round/{round_ids[1]}')

        assert response.status_code == 200
        assert 'Laske kierros uudelleen'.encode('utf-8') not in response.data
