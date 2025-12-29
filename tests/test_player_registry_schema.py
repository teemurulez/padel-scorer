import sqlite3
import pytest


def test_player_registry_table_exists():
    """Test that player_registry table exists with correct columns"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='player_registry'
    """)
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(player_registry)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'id' in columns
    assert 'first_name' in columns
    assert 'last_name' in columns
    assert 'created_at' in columns

    conn.close()


def test_player_registry_unique_constraint():
    """Test that duplicate first_name + last_name is prevented"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Insert first player
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("TestFirst", "TestLast"))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            """, ("TestFirst", "TestLast"))
            conn.commit()
    finally:
        # Cleanup
        cursor.execute("""
            DELETE FROM player_registry
            WHERE first_name = 'TestFirst' AND last_name = 'TestLast'
        """)
        conn.commit()
        conn.close()


def test_player_registry_indexes_exist():
    """Test that indexes are created for performance"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='player_registry'
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    # Should have index on name columns
    assert any('player_registry' in idx.lower() for idx in indexes)

    conn.close()
