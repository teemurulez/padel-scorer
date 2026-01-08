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
    from app import get_db_connection
    db = get_db_connection()

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
            total_points INTEGER DEFAULT 0
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

    # Should redirect to active_tournament page
    assert response.status_code == 302

    # Verify status changed
    from app import get_db_connection
    with app.app_context():
        db = get_db_connection()
        tournament = db.execute(
            "SELECT status, completed_at FROM tournaments WHERE id = 1"
        ).fetchone()
        assert tournament['status'] == 'completed'
        assert tournament['completed_at'] is not None


def test_complete_tournament_calculates_final_ranks(client):
    """Test that completing tournament calculates final ranks based on total_points"""
    response = client.post('/tournament/1/complete')

    # Verify final_rank was set based on points (player 1 has 100 pts, player 2 has 80 pts)
    from app import get_db_connection
    with app.app_context():
        db = get_db_connection()

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

    from app import get_db_connection
    with app.app_context():
        db = get_db_connection()
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

    from app import get_db_connection
    with app.app_context():
        db = get_db_connection()
        tournament = db.execute(
            "SELECT status, archived_at FROM tournaments WHERE id = 1"
        ).fetchone()
        assert tournament['status'] == 'archived'
        assert tournament['archived_at'] is not None


def test_complete_tournament_not_found(client):
    """Test completing non-existent tournament returns error"""
    response = client.post('/tournament/999/complete')
    # Should redirect to index when tournament not found
    assert response.status_code == 302


def test_full_tournament_lifecycle(tmp_path):
    """Integration test - complete tournament lifecycle from setup to archived"""

    # Setup test client with temporary database
    import os
    db_path = tmp_path / "test_full_lifecycle.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    # Initialize database
    with app.app_context():
        from database import init_db
        init_db()

    client = app.test_client()

    tournament_id = None
    try:
        # Setup: Ensure there's an active season
        with app.app_context():
            from app import get_db_connection
            db = get_db_connection()
            db.execute("DELETE FROM seasons WHERE name = 'Test Season 9999'")
            db.execute(
                "INSERT INTO seasons (name, is_current) VALUES ('Test Season 9999', 1)"
            )
            db.commit()

        # PHASE 1: SETUP (status='setup')
        # Create tournament directly (no /setup route anymore)
        with app.app_context():
            db = get_db_connection()

            # Get season_id
            season = db.execute("SELECT id FROM seasons WHERE name = 'Test Season 9999'").fetchone()
            season_id = season['id']

            # Create tournament
            db.execute("""
                INSERT INTO tournaments (name, num_courts, season_id, status)
                VALUES (?, ?, ?, 'setup')
            """, ('Lifecycle Test Tournament', 2, season_id))
            tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Create 8 players and add to tournament
            for i in range(1, 9):
                db.execute("""
                    INSERT INTO player_registry (first_name, last_name)
                    VALUES (?, ?)
                """, (f'Player', f'{i}'))
                player_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

                db.execute("""
                    INSERT INTO tournament_players (tournament_id, player_id, total_points)
                    VALUES (?, ?, 0)
                """, (tournament_id, player_id))

            db.commit()

            # Verify tournament created with status='setup'
            tournament = db.execute(
                "SELECT id, status FROM tournaments WHERE id = ?",
                (tournament_id,)
            ).fetchone()
            assert tournament is not None
            assert tournament['status'] == 'setup'

        # PHASE 2: ACTIVE (status='active')
        # Start Round 1
        response = client.post(f'/tournament/{tournament_id}/start_round',
                             follow_redirects=True)
        assert response.status_code == 200

        # Verify status changed to 'active'
        with app.app_context():
            db = get_db_connection()
            result = db.execute(
                "SELECT status FROM tournaments WHERE id = ?", (tournament_id,)
            ).fetchone()
            assert result['status'] == 'active'

        # PHASE 3: COMPLETED (status='completed')
        # Complete tournament
        response = client.post(f'/tournament/{tournament_id}/complete',
                             follow_redirects=True)
        assert response.status_code == 200

        # Verify status changed to 'completed' and timestamp set
        with app.app_context():
            db = get_db_connection()
            result = db.execute(
                "SELECT status, completed_at FROM tournaments WHERE id = ?",
                (tournament_id,)
            ).fetchone()
            assert result['status'] == 'completed'
            assert result['completed_at'] is not None

            # Verify tournament_players data exists
            players_count = db.execute(
                '''
                SELECT COUNT(*) as count FROM tournament_players
                WHERE tournament_id = ?
                ''', (tournament_id,)
            ).fetchone()['count']
            assert players_count > 0

        # PHASE 4: ARCHIVED (status='archived')
        # Archive tournament
        response = client.post(f'/tournament/{tournament_id}/archive',
                             follow_redirects=True)
        assert response.status_code == 200

        # Verify status changed to 'archived' and timestamp set
        with app.app_context():
            db = get_db_connection()
            result = db.execute(
                "SELECT status, archived_at FROM tournaments WHERE id = ?",
                (tournament_id,)
            ).fetchone()
            assert result['status'] == 'archived'
            assert result['archived_at'] is not None

    finally:
        # Cleanup
        with app.app_context():
            db = get_db_connection()
            if tournament_id:
                db.execute("DELETE FROM tournament_players WHERE tournament_id = ?",
                         (tournament_id,))
                db.execute("DELETE FROM rounds WHERE tournament_id = ?",
                         (tournament_id,))
                db.execute("DELETE FROM tournaments WHERE id = ?",
                         (tournament_id,))
            db.execute("DELETE FROM seasons WHERE name = 'Test Season 9999'")
            db.commit()
