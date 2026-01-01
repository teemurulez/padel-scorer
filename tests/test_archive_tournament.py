import sqlite3
import pytest
import os
from app import app


@pytest.fixture
def client_with_db(tmp_path):
    """Create test client with isolated database"""
    db_path = tmp_path / "test_archive.db"
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


def test_archive_tournament_success(client_with_db):
    """Test that completed tournament can be archived"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create tournament with status='completed'
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 2, season_id, "completed"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # POST to /tournament/<id>/archive
    response = client.post(f'/tournament/{tournament_id}/archive')

    # Verify status changed to 'archived'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Tournament not found"
    status = result[0]
    assert status == 'archived', f"Expected status 'archived', got '{status}'"

    # Verify redirect to index
    assert response.status_code == 302, f"Expected redirect (302), got {response.status_code}"


def test_archive_tournament_sets_timestamp(client_with_db):
    """Test that archived_at timestamp is set"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create season
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
    season_id = cursor.lastrowid

    # Create completed tournament
    cursor.execute("""
        INSERT INTO tournaments (name, num_courts, season_id, status)
        VALUES (?, ?, ?, ?)
    """, ("Test Tournament", 2, season_id, "completed"))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Archive it
    response = client.post(f'/tournament/{tournament_id}/archive')

    # Verify archived_at IS NOT NULL
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT archived_at FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Tournament not found"
    archived_at = result[0]
    assert archived_at is not None, "Expected archived_at to be set"


def test_archive_tournament_rejects_non_completed(client_with_db):
    """Test that only completed tournaments can be archived"""
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

    # Try to archive it
    response = client.post(f'/tournament/{tournament_id}/archive', follow_redirects=True)

    # Verify error flash message
    assert b'Cannot archive tournament' in response.data or b'Can only archive' in response.data, \
        "Expected error message about tournament status"

    # Verify status still 'active'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        status = result[0]
        assert status == 'active', f"Expected status to remain 'active', got '{status}'"
