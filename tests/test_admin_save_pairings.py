import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_save_pairings.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        # Setup admin session to bypass authentication
        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        # Setup test data
        from database import get_db
        with app.app_context():
            db = get_db()

            # Create season
            db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
            season_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Create tournament
            db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                      ("Test Tournament", 2, season_id, "setup"))
            tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Create 8 players
            for i in range(1, 9):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                player_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (tournament_id, player_id))

            db.commit()

        yield client, tournament_id

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_save_valid_custom_pairings(client):
    """Test POST /admin/tournaments/<id>/save-round1-pairings with valid data"""
    client_obj, tournament_id = client

    pairings_data = {
        'pairings': [
            {'court': 1, 'team1': [1, 2], 'team2': [3, 4]},
            {'court': 2, 'team1': [5, 6], 'team2': [7, 8]}
        ]
    }

    response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        data=json.dumps(pairings_data),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] == True

    # Verify saved to database
    from database import get_db
    with app.app_context():
        db = get_db()
        saved_pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ? ORDER BY court_number",
            (tournament_id,)
        ).fetchall()

    assert len(saved_pairings) == 2
    assert saved_pairings[0]['team1_player1_id'] == 1
    assert saved_pairings[0]['team1_player2_id'] == 2

def test_save_invalid_pairings_returns_400(client):
    """Test save fails with invalid pairings (duplicate player)"""
    client_obj, tournament_id = client

    pairings_data = {
        'pairings': [
            {'court': 1, 'team1': [1, 1], 'team2': [3, 4]},  # Player 1 twice
            {'court': 2, 'team1': [5, 6], 'team2': [7, 8]}
        ]
    }

    response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        data=json.dumps(pairings_data),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'errors' in data
    assert len(data['errors']) > 0

def test_save_pairings_replaces_existing(client):
    """Test saving new pairings replaces old ones"""
    client_obj, tournament_id = client

    # Save first set of pairings
    pairings_v1 = {
        'pairings': [
            {'court': 1, 'team1': [1, 2], 'team2': [3, 4]},
            {'court': 2, 'team1': [5, 6], 'team2': [7, 8]}
        ]
    }
    client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        data=json.dumps(pairings_v1),
        content_type='application/json'
    )

    # Save second set (swapped teams)
    pairings_v2 = {
        'pairings': [
            {'court': 1, 'team1': [1, 3], 'team2': [2, 4]},  # Changed
            {'court': 2, 'team1': [5, 6], 'team2': [7, 8]}
        ]
    }
    client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        data=json.dumps(pairings_v2),
        content_type='application/json'
    )

    # Verify only v2 exists (v1 replaced)
    from database import get_db
    with app.app_context():
        db = get_db()
        saved_pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ? ORDER BY court_number",
            (tournament_id,)
        ).fetchall()

    assert len(saved_pairings) == 2
    assert saved_pairings[0]['team1_player2_id'] == 3  # v2 value, not 2
