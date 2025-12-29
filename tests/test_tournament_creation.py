import pytest
import os
from app import app
from database import get_db

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_tournament.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_tournament_assigned_to_current_season(client):
    """Test that new tournaments are assigned to current season"""
    with app.app_context():
        # Create current season
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    # Create tournament
    response = client.post('/setup', data={
        'tournament_name': 'Test Tournament',
        'num_courts': '3',
        'players': 'Player 1\nPlayer 2\nPlayer 3\nPlayer 4\nPlayer 5\nPlayer 6\nPlayer 7\nPlayer 8\nPlayer 9\nPlayer 10\nPlayer 11\nPlayer 12'
    }, follow_redirects=True)

    assert response.status_code == 200

    # Verify tournament has season_id
    with app.app_context():
        conn = get_db()
        tournament = conn.execute(
            "SELECT season_id FROM tournaments WHERE name = ?",
            ("Test Tournament",)
        ).fetchone()
        assert tournament is not None
        assert tournament[0] == season_id

def test_tournament_creation_blocked_without_season(client):
    """Test that tournament creation is blocked when no current season"""
    # No current season created
    response = client.post('/setup', data={
        'tournament_name': 'Test Tournament',
        'num_courts': '3',
        'players': 'Player 1\nPlayer 2\nPlayer 3\nPlayer 4\nPlayer 5\nPlayer 6\nPlayer 7\nPlayer 8\nPlayer 9\nPlayer 10\nPlayer 11\nPlayer 12'
    }, follow_redirects=True)

    assert b'No active season' in response.data

    # Verify no tournament created
    with app.app_context():
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
        assert count == 0
