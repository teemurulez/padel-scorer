import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_preview.db"
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

def test_preview_round1_generates_pairings(client):
    """Test POST /admin/tournaments/<id>/preview-round1 generates pairings"""
    client_obj, tournament_id = client

    response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'pairings' in data
    assert 'players' in data
    assert len(data['pairings']) == 2  # 2 courts

    # Verify each pairing has correct structure
    for pairing in data['pairings']:
        assert 'court' in pairing
        assert 'team1' in pairing
        assert 'team2' in pairing
        assert len(pairing['team1']) == 2
        assert len(pairing['team2']) == 2

def test_preview_round1_saves_to_database(client):
    """Test preview pairings are saved to database"""
    client_obj, tournament_id = client

    response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert response.status_code == 200

    # Verify database entries
    from database import get_db
    with app.app_context():
        db = get_db()
        pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ? ORDER BY court_number",
            (tournament_id,)
        ).fetchall()

    assert len(pairings) == 2  # 2 courts
    assert pairings[0]['court_number'] == 1
    assert pairings[1]['court_number'] == 2

def test_preview_round1_non_setup_tournament_returns_404(client):
    """Test preview fails for non-setup tournament"""
    client_obj, tournament_id = client

    # Change tournament status to active
    from database import get_db
    with app.app_context():
        db = get_db()
        db.execute("UPDATE tournaments SET status = 'active' WHERE id = ?", (tournament_id,))
        db.commit()

    response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')

    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data

def test_preview_round1_clears_existing_pairings(client):
    """Test generating preview clears previous preview"""
    client_obj, tournament_id = client

    # Generate preview twice
    client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')

    # Verify only one set of pairings exists (not duplicated)
    from database import get_db
    with app.app_context():
        db = get_db()
        pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchall()

    assert len(pairings) == 2  # Still just 2 courts, not 4
