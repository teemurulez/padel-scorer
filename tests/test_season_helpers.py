from database import get_db
from app import get_current_season, set_current_season

def test_get_current_season_returns_current():
    """Test getting the current active season"""
    conn = get_db()
    cursor = conn.cursor()

    # Save current state of is_current flags
    cursor.execute("SELECT id FROM seasons WHERE is_current = 1")
    original_current_ids = [row[0] for row in cursor.fetchall()]

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Test Season 1", "Test Season 2"))
    # Clear all current flags for test isolation
    cursor.execute("UPDATE seasons SET is_current = 0")
    conn.commit()

    try:
        # Setup: Create seasons (include year for backward compatibility with old schema)
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season 1", 2099, 0))
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season 2", 2100, 1))
        conn.commit()

        # Test
        current = get_current_season(conn)
        assert current is not None
        assert current['name'] == "Test Season 2"
        assert current['is_current'] == 1
    finally:
        # Clean up and restore original state
        cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Test Season 1", "Test Season 2"))
        for season_id in original_current_ids:
            cursor.execute("UPDATE seasons SET is_current = 1 WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()

def test_get_current_season_returns_none_when_no_current():
    """Test that None is returned when no season is current"""
    conn = get_db()
    cursor = conn.cursor()

    # Save current state of is_current flags
    cursor.execute("SELECT id FROM seasons WHERE is_current = 1")
    original_current_ids = [row[0] for row in cursor.fetchall()]

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Archived",))
    # Clear all current flags for test isolation
    cursor.execute("UPDATE seasons SET is_current = 0")
    conn.commit()

    try:
        # Setup: Create only archived seasons (include year for backward compatibility)
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season Archived", 2098, 0))
        conn.commit()

        # Test
        current = get_current_season(conn)
        assert current is None
    finally:
        # Clean up and restore original state
        cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Archived",))
        for season_id in original_current_ids:
            cursor.execute("UPDATE seasons SET is_current = 1 WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()

def test_set_current_season_archives_previous():
    """Test that setting a season as current archives others"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Test Season A", "Test Season B"))
    conn.commit()

    # Setup: Create two seasons, one current (include year for backward compatibility)
    cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season A", 2097, 1))
    cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season B", 2096, 0))
    season2_id = cursor.lastrowid
    conn.commit()

    # Test: Set season 2 as current
    set_current_season(conn, season2_id)

    # Verify: Season A is now archived
    s1 = cursor.execute("SELECT is_current FROM seasons WHERE name = ?", ("Test Season A",)).fetchone()
    assert s1[0] == 0

    # Verify: Season B is now current
    s2 = cursor.execute("SELECT is_current FROM seasons WHERE name = ?", ("Test Season B",)).fetchone()
    assert s2[0] == 1

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Test Season A", "Test Season B"))
    conn.commit()
    conn.close()

def test_set_current_season_clears_ended_at():
    """Test that reactivating a season clears ended_at"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Ended",))
    conn.commit()

    # Setup: Create archived season with ended_at (include year for backward compatibility)
    cursor.execute(
        "INSERT INTO seasons (name, year, is_current, ended_at) VALUES (?, ?, ?, ?)",
        ("Test Season Ended", 2095, 0, "2024-12-31 23:59:59")
    )
    season_id = cursor.lastrowid
    conn.commit()

    # Test: Reactivate season
    set_current_season(conn, season_id)

    # Verify: ended_at is NULL
    season = cursor.execute("SELECT ended_at FROM seasons WHERE id = ?", (season_id,)).fetchone()
    assert season[0] is None

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Test Season Ended",))
    conn.commit()
    conn.close()
