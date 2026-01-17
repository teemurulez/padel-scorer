import pytest
import os
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_edit_page.db"
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

        # Create test data
        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
            db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                      ("Test Tournament", 2, 1, "setup"))

            # Add 8 players
            for i in range(1, 9):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (1, i))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_edit_page_exists(client):
    """Test that edit page route exists"""
    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 200

def test_edit_page_shows_tournament_name(client):
    """Test that edit page shows tournament name"""
    response = client.get('/admin/tournaments/1/edit')
    assert b'Test Tournament' in response.data

def test_edit_page_shows_players(client):
    """Test that edit page shows player list"""
    response = client.get('/admin/tournaments/1/edit')
    assert b'Player1 Last1' in response.data

def test_edit_page_requires_admin(client):
    """Test that edit page requires admin login"""
    # Clear admin session
    with client.session_transaction() as sess:
        sess.clear()

    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 302  # Redirect to login

def test_edit_page_404_for_nonexistent(client):
    """Test that edit page returns 404 for nonexistent tournament"""
    response = client.get('/admin/tournaments/999/edit')
    assert response.status_code == 404

def test_edit_page_404_for_non_setup(client):
    """Test that edit page returns 404 for non-setup tournament"""
    from database import get_db
    with app.app_context():
        db = get_db()
        db.execute("UPDATE tournaments SET status = 'active' WHERE id = 1")
        db.commit()

    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 404
