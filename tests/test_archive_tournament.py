import sqlite3
import pytest


def test_archive_tournament_success():
    """Test that completed tournament can be archived"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
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

        # POST to /tournament/<id>/archive
        from app import app
        client = app.test_client()

        response = client.post(f'/tournament/{tournament_id}/archive')

        # Verify status changed to 'archived'
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'archived', f"Expected status 'archived', got '{status}'"

        # Verify redirect to index
        assert response.status_code == 302, f"Expected redirect (302), got {response.status_code}"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_archive_tournament_sets_timestamp():
    """Test that archived_at timestamp is set"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
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

        # Archive it
        from app import app
        client = app.test_client()
        response = client.post(f'/tournament/{tournament_id}/archive')

        # Verify archived_at IS NOT NULL
        cursor.execute("SELECT archived_at FROM tournaments WHERE id = ?", (tournament_id,))
        archived_at = cursor.fetchone()[0]
        assert archived_at is not None, "Expected archived_at to be set"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_archive_tournament_rejects_non_completed():
    """Test that only completed tournaments can be archived"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
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

        # Try to archive it
        from app import app
        client = app.test_client()

        response = client.post(f'/tournament/{tournament_id}/archive', follow_redirects=True)

        # Verify error flash message
        assert b'Cannot archive tournament' in response.data or b'Can only archive' in response.data, \
            "Expected error message about tournament status"

        # Verify status still 'active'
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'active', f"Expected status to remain 'active', got '{status}'"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
