import pytest
import sqlite3
from app import app


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_tournament_lifecycle.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    with app.test_client() as client:
        with app.app_context():
            init_test_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def init_test_db():
    """Initialize test database with Phase 3 schema"""
    from database import get_db
    db = get_db()

    # Drop existing tables to ensure clean slate
    db.executescript("""
        DROP TABLE IF EXISTS scores;
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS tournament_players;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS player_registry;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS seasons;
    """)
    db.commit()

    # Create Phase 2 + Phase 3 schema for testing (hybrid for redirect compatibility)
    db.executescript("""
        CREATE TABLE seasons (
            id INTEGER PRIMARY KEY,
            year INTEGER,
            status TEXT
        );

        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT,
            num_courts INTEGER,
            season_id INTEGER,
            status TEXT DEFAULT 'setup',
            completed_at TIMESTAMP,
            archived_at TIMESTAMP
        );

        CREATE TABLE tournament_players (
            tournament_id INTEGER,
            player_id INTEGER,
            final_rank INTEGER,
            total_points INTEGER,
            match_wins INTEGER,
            match_losses INTEGER,
            PRIMARY KEY (tournament_id, player_id)
        );

        -- Phase 2 tables for redirect compatibility
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            total_points INTEGER DEFAULT 0,
            tournament_id INTEGER
        );

        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER,
            round_number INTEGER,
            status TEXT DEFAULT 'in_progress'
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            round_id INTEGER,
            court_number INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            player3_id INTEGER,
            player4_id INTEGER,
            winning_team INTEGER,
            completed INTEGER DEFAULT 0
        );

        CREATE TABLE scores (
            id INTEGER PRIMARY KEY,
            match_id INTEGER,
            player_id INTEGER,
            points INTEGER DEFAULT 0
        );

        -- Insert test data
        INSERT OR REPLACE INTO seasons (id, year, status) VALUES (1, 2025, 'active');
        INSERT OR REPLACE INTO player_registry (id, first_name, last_name)
        VALUES (1, 'Test', 'Player'), (2, 'Another', 'Player');
        INSERT OR REPLACE INTO tournaments (id, name, num_courts, season_id, status)
        VALUES (1, 'Test Tournament', 2, 1, 'active');
        INSERT OR REPLACE INTO tournament_players (tournament_id, player_id, total_points, match_wins, match_losses)
        VALUES (1, 1, 100, 5, 2), (1, 2, 80, 4, 3);
    """)
    db.commit()


def test_complete_tournament_marks_status_completed(client):
    """Test that completing tournament changes status to completed"""
    response = client.post('/tournament/1/complete')

    # Should redirect
    assert response.status_code in [200, 302]

    # Verify status changed
    from database import get_db
    with app.app_context():
        db = get_db()
        tournament = db.execute(
            "SELECT status, completed_at FROM tournaments WHERE id = 1"
        ).fetchone()
        assert tournament['status'] == 'completed'
        assert tournament['completed_at'] is not None


def test_complete_tournament_calculates_final_ranks(client):
    """Test that completing tournament calculates final ranks based on total_points"""
    response = client.post('/tournament/1/complete')

    # Verify final_rank was set based on points (player 1 has 100 pts, player 2 has 80 pts)
    from database import get_db
    with app.app_context():
        db = get_db()

        # Player 1 should be rank 1 (higher points)
        player1 = db.execute(
            "SELECT final_rank FROM tournament_players WHERE tournament_id = 1 AND player_id = 1"
        ).fetchone()
        assert player1['final_rank'] == 1

        # Player 2 should be rank 2 (lower points)
        player2 = db.execute(
            "SELECT final_rank FROM tournament_players WHERE tournament_id = 1 AND player_id = 2"
        ).fetchone()
        assert player2['final_rank'] == 2


def test_archive_tournament_requires_completed_status(client):
    """Test that only completed tournaments can be archived"""
    # Try to archive an active tournament (should fail)
    response = client.post('/tournament/1/archive', follow_redirects=True)

    from database import get_db
    with app.app_context():
        db = get_db()
        tournament = db.execute(
            "SELECT status FROM tournaments WHERE id = 1"
        ).fetchone()
        # Should still be active (not archived)
        assert tournament['status'] == 'active'


def test_archive_tournament_after_completion(client):
    """Test that completed tournaments can be archived"""
    # First complete the tournament
    client.post('/tournament/1/complete')

    # Then archive it
    response = client.post('/tournament/1/archive')

    from database import get_db
    with app.app_context():
        db = get_db()
        tournament = db.execute(
            "SELECT status, archived_at FROM tournaments WHERE id = 1"
        ).fetchone()
        assert tournament['status'] == 'archived'
        assert tournament['archived_at'] is not None


def test_complete_tournament_not_found(client):
    """Test completing non-existent tournament returns error"""
    response = client.post('/tournament/999/complete')
    assert response.status_code in [302, 404]  # Redirect or not found
