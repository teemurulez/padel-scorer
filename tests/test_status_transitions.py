import pytest
import os
from app import app
from database import get_db


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_status_transitions.db"
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


def test_new_tournament_has_setup_status(client):
    """Test that new tournament is created with status='setup'"""
    with app.app_context():
        # Create current season
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        conn.commit()

    # Create tournament via /setup route
    response = client.post('/setup', data={
        'tournament_name': 'Test Tournament',
        'num_courts': '1',
        'players': 'Player One\nPlayer Two\nPlayer Three\nPlayer Four'
    }, follow_redirects=False)

    # Should redirect to start_round
    assert response.status_code == 302

    # Verify tournament has status='setup'
    with app.app_context():
        conn = get_db()
        tournament = conn.execute(
            "SELECT status FROM tournaments WHERE name = ?",
            ("Test Tournament",)
        ).fetchone()
        assert tournament is not None
        assert tournament['status'] == 'setup', f"Expected status='setup', got '{tournament['status']}'"


def test_start_round1_sets_active_status(client):
    """Test that starting Round 1 sets status to 'active'"""
    with app.app_context():
        # Create season
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create tournament with status='setup'
        conn.execute("""
            INSERT INTO tournaments (name, num_courts, status, season_id)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 1, 'setup', season_id))
        tournament_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Add 4 players to player_registry
        for i in range(4):
            conn.execute("""
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            """, (f"Player{i}", f"Last{i}"))

        conn.commit()

    # Start Round 1 via POST to start_round
    response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=False)

    # Should redirect to court_selection
    assert response.status_code == 302

    # Verify status is now 'active'
    with app.app_context():
        conn = get_db()
        tournament = conn.execute(
            "SELECT status FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        assert tournament['status'] == 'active', f"Expected status='active' after Round 1, got '{tournament['status']}'"


def test_subsequent_rounds_keep_active_status(client):
    """Test that starting Round 2+ keeps status='active'"""
    with app.app_context():
        # Create season
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create tournament with status='active' (already past Round 1)
        conn.execute("""
            INSERT INTO tournaments (name, num_courts, status, season_id)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 1, 'active', season_id))
        tournament_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Add 4 players
        player_ids = []
        for i in range(4):
            conn.execute("""
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            """, (f"Player{i}", f"Last{i}"))
            player_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        # Create completed Round 1
        conn.execute("""
            INSERT INTO rounds (tournament_id, round_number, status)
            VALUES (?, ?, ?)
        """, (tournament_id, 1, 'completed'))
        round1_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, completed, winning_team)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (round1_id, 1, player_ids[0], player_ids[1], player_ids[2], player_ids[3], 1, 1))

        conn.commit()

    # Start Round 2 via POST
    response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=False)

    # Should redirect to court_selection
    assert response.status_code == 302

    # Verify status is still 'active' (unchanged)
    with app.app_context():
        conn = get_db()
        tournament = conn.execute(
            "SELECT status FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        assert tournament['status'] == 'active', f"Expected status='active' for Round 2+, got '{tournament['status']}'"
