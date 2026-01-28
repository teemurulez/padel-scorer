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
    assert 'Ei aktiivista kautta'.encode('utf-8') in response.data  # Finnish: "No current season"

def test_season_leaderboard_includes_players_with_only_imported_points(client):
    """Test that players with only imported points (no tournament matches) appear in standings"""
    with app.app_context():
        conn = get_db()

        # Create a season
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create a player with NO tournament match history
        conn.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                    ("Imported", "Player"))
        player_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Add imported points via adjustment (simulating bulk import from external tournament)
        conn.execute("""
            INSERT INTO player_points_adjustment (player_id, season_id, adjustment, tournaments_adjustment)
            VALUES (?, ?, ?, ?)
        """, (player_id, season_id, 5, 2))  # 5 wins from 2 external tournaments

        conn.commit()

    response = client.get('/leaderboard/season')
    assert response.status_code == 200

    # Player with imported points should appear in the leaderboard
    assert b'Imported' in response.data
    assert b'Player' in response.data
