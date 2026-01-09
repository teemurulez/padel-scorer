import sqlite3
import pytest


def test_tournaments_status_column_exists():
    """Test that tournaments table has status column"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(tournaments)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'status' in columns
    assert 'completed_at' in columns
    assert 'archived_at' in columns

    conn.close()


def test_tournament_status_default_value():
    """Test that new tournaments default to 'setup' status"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    tournament_id = None
    season_id = None

    try:
        # Create season (include year for backward compatibility)
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season Status", 2091, 0))
        season_id = cursor.lastrowid

        # Create tournament without specifying status
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id)
            VALUES (?, ?, ?)
        """, ("Test Tournament Status", 2, season_id))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Check default status
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'setup'
    finally:
        if tournament_id:
            cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        if season_id:
            cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_tournament_status_transitions():
    """Test that tournament status can transition through lifecycle"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    tournament_id = None
    season_id = None

    try:
        # Create season and tournament (include year for backward compatibility)
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season Trans", 2090, 0))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament Trans", 2, season_id, "setup"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Transition to active
        cursor.execute("UPDATE tournaments SET status = ? WHERE id = ?", ("active", tournament_id))
        conn.commit()

        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        assert cursor.fetchone()[0] == 'active'

        # Transition to completed
        cursor.execute("""
            UPDATE tournaments SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("completed", tournament_id))
        conn.commit()

        cursor.execute("SELECT status, completed_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'completed'
        assert row[1] is not None

        # Transition to archived
        cursor.execute("""
            UPDATE tournaments SET status = ?, archived_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("archived", tournament_id))
        conn.commit()

        cursor.execute("SELECT status, archived_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'archived'
        assert row[1] is not None
    finally:
        if tournament_id:
            cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        if season_id:
            cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
