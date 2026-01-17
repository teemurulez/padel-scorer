import pytest
import os
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_history_log.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
            db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                      ("Test Tournament", 1, 1, "setup"))

            for i in range(1, 5):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (1, i))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_adding_player_logs_history(client):
    """Test that adding a player creates history entry"""
    # Edit with one new player (replacing one)
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nNewPlayer New"

    response = client.post('/admin/tournaments/1/edit',
                          data={
                              'tournament_name': 'Test Tournament',
                              'num_courts': 1,
                              'players': new_players
                          },
                          follow_redirects=True)

    assert response.status_code == 200

    from database import get_db
    with app.app_context():
        db = get_db()
        history = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = 1 AND change_type = 'player_added'"
        ).fetchall()

        assert len(history) >= 1
        # Check that NewPlayer was logged as added
        added_names = [h['change_data'] for h in history]
        assert 'NewPlayer New' in added_names

def test_removing_player_logs_history(client):
    """Test that removing a player creates history entry"""
    # Edit with a different player replacing Player4
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nDifferent Person"

    response = client.post('/admin/tournaments/1/edit',
                          data={
                              'tournament_name': 'Test Tournament',
                              'num_courts': 1,
                              'players': new_players
                          },
                          follow_redirects=True)

    assert response.status_code == 200

    from database import get_db
    with app.app_context():
        db = get_db()
        history = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = 1 AND change_type = 'player_removed'"
        ).fetchall()

        assert len(history) >= 1
        # Check that Player4 was logged as removed
        removed_names = [h['change_data'] for h in history]
        assert 'Player4 Last4' in removed_names
