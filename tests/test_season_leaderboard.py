import pytest
import os
from app import app
from database import get_db

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_season_leaderboard.db"
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

def test_season_leaderboard_filters_by_current_season(client):
    """Test that season leaderboard shows only current season tournaments"""
    with app.app_context():
        conn = get_db()

        # Create two seasons
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Old Season", 0))
        old_season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Current Season", 1))
        current_season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create tournaments in different seasons
        conn.execute("INSERT INTO tournaments (name, num_courts, season_id) VALUES (?, ?, ?)",
                    ("Old Tournament", 3, old_season_id))
        conn.execute("INSERT INTO tournaments (name, num_courts, season_id) VALUES (?, ?, ?)",
                    ("Current Tournament", 3, current_season_id))
        conn.commit()

    response = client.get('/leaderboard/season')

    # Should show current season name
    assert b'Current Season' in response.data
    # Should show current tournament
    assert b'Current Tournament' in response.data
    # Should NOT show old tournament
    assert b'Old Tournament' not in response.data

def test_season_leaderboard_shows_message_without_current_season(client):
    """Test message when no current season exists"""
    response = client.get('/leaderboard/season')
    assert b'No current season' in response.data
