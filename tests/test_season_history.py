import pytest
import os
from app import app
from database import get_db

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_season_history.db"
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

def test_season_history_shows_archived_seasons(client):
    """Test that history page shows archived seasons"""
    with app.app_context():
        conn = get_db()

        # Create archived seasons
        conn.execute("INSERT INTO seasons (name, is_current, ended_at) VALUES (?, ?, ?)",
                    ("Winter 2024", 0, "2024-12-31"))
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)",
                    ("Spring 2025", 1))
        conn.commit()

    response = client.get('/leaderboard/history')

    # Should show archived season
    assert b'Winter 2024' in response.data
    # Should NOT show current season
    assert b'Spring 2025' not in response.data

def test_season_history_uses_season_names_not_years(client):
    """Test that custom season names are displayed"""
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current, ended_at) VALUES (?, ?, ?)",
                    ("Fall Championship 2024", 0, "2024-11-30"))
        conn.commit()

    response = client.get('/leaderboard/history')
    assert b'Fall Championship 2024' in response.data
