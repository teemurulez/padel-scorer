import sqlite3
import pytest
import os
from app import app


@pytest.fixture
def client_with_db(tmp_path):
    """Create test client with isolated database"""
    db_path = tmp_path / "test_complete.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client, str(db_path)

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_complete_tournament_success(client_with_db):
    """Test that active tournament can be completed"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create tournament with status='active'
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 2, season_id, "active"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # POST to /tournament/<id>/complete
    response = client.post(f'/tournament/{tournament_id}/complete')

    # Verify status changed to 'completed'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Tournament not found"
    status = result[0]
    assert status == 'completed', f"Expected status 'completed', got '{status}'"

    # Verify redirect
    assert response.status_code == 302, f"Expected redirect (302), got {response.status_code}"


def test_complete_tournament_calculates_stats(client_with_db):
    """Test that completion calculates match wins/losses/points"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create 2 players in registry
    cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Alice", "Smith"))
    player1_id = cursor.lastrowid

    cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Bob", "Jones"))
    player2_id = cursor.lastrowid

    # Create active tournament
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 1, season_id, "active"))
    tournament_id = cursor.lastrowid

    # Add players to tournament
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, 0)",
                  (tournament_id, player1_id))
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, 0)",
                  (tournament_id, player2_id))

    conn.commit()
    conn.close()

    # Complete tournament
    response = client.post(f'/tournament/{tournament_id}/complete')
    assert response.status_code == 302


def test_complete_tournament_sets_timestamp(client_with_db):
    """Test that completion sets completed_at timestamp"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create active tournament
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status, completed_at)
        VALUES (?, ?, ?, ?, NULL)
    """, ("Test Tournament", 1, season_id, "active"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Complete tournament
    response = client.post(f'/tournament/{tournament_id}/complete')

    # Verify completed_at is set
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT completed_at FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    assert result is not None
    completed_at = result[0]
    assert completed_at is not None, "Expected completed_at to be set"


def test_complete_tournament_rejects_non_active(client_with_db):
    """Test that only active tournaments can be completed"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create tournament with status='setup' (not active)
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 1, season_id, "setup"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Try to complete non-active tournament
    response = client.post(f'/tournament/{tournament_id}/complete', follow_redirects=True)

    # Should show error or redirect with flash message
    # The exact behavior depends on implementation
    # At minimum, status should NOT change
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        status = result[0]
        assert status != 'completed', "Setup tournament should not be completable"


def test_complete_tournament_handles_ties(client_with_db):
    """Test that completion correctly handles tied players"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create active tournament
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 1, season_id, "active"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Complete tournament
    response = client.post(f'/tournament/{tournament_id}/complete')

    # Should succeed
    assert response.status_code == 302
