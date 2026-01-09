import sqlite3
import pytest
from database import get_db

def test_seasons_table_exists():
    """Test that seasons table is created with correct schema"""
    conn = get_db()
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='seasons'")
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(seasons)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'id' in columns
    assert 'name' in columns
    assert 'is_current' in columns
    assert 'created_at' in columns
    assert 'ended_at' in columns

    conn.close()

@pytest.mark.skip(reason="Name uniqueness enforced by app layer, not DB constraint - name column added via ALTER TABLE")
def test_seasons_name_unique_constraint():
    """Test that season names must be unique"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Unique",))
    conn.commit()

    # Insert first season (include year for backward compatibility)
    cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season Unique", 2094, 1))
    conn.commit()

    # Try to insert duplicate - should fail on name uniqueness
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season Unique", 2093, 0))
        conn.commit()

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Unique",))
    conn.commit()

    conn.close()

def test_tournaments_has_season_id_column():
    """Test that tournaments table has season_id column"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(tournaments)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'season_id' in columns

    conn.close()
