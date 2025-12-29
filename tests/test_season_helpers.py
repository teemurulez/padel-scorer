from database import get_db
from app import get_current_season, set_current_season

def test_get_current_season_returns_current():
    """Test getting the current active season"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Season 1", "Season 2"))
    conn.commit()

    # Setup: Create seasons
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Season 1", 0))
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Season 2", 1))
    conn.commit()

    # Test
    current = get_current_season(conn)
    assert current is not None
    assert current['name'] == "Season 2"
    assert current['is_current'] == 1

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Season 1", "Season 2"))
    conn.commit()
    conn.close()

def test_get_current_season_returns_none_when_no_current():
    """Test that None is returned when no season is current"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Season 1",))
    conn.commit()

    # Setup: Create only archived seasons
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Season 1", 0))
    conn.commit()

    # Test
    current = get_current_season(conn)
    assert current is None

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Season 1",))
    conn.commit()
    conn.close()

def test_set_current_season_archives_previous():
    """Test that setting a season as current archives others"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Season 1", "Season 2"))
    conn.commit()

    # Setup: Create two seasons, one current
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Season 1", 1))
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Season 2", 0))
    season2_id = cursor.lastrowid
    conn.commit()

    # Test: Set season 2 as current
    set_current_season(conn, season2_id)

    # Verify: Season 1 is now archived
    s1 = cursor.execute("SELECT is_current FROM seasons WHERE name = ?", ("Season 1",)).fetchone()
    assert s1[0] == 0

    # Verify: Season 2 is now current
    s2 = cursor.execute("SELECT is_current FROM seasons WHERE name = ?", ("Season 2",)).fetchone()
    assert s2[0] == 1

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name IN (?, ?)", ("Season 1", "Season 2"))
    conn.commit()
    conn.close()

def test_set_current_season_clears_ended_at():
    """Test that reactivating a season clears ended_at"""
    conn = get_db()
    cursor = conn.cursor()

    # Clean up any existing test data
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Season 1",))
    conn.commit()

    # Setup: Create archived season with ended_at
    cursor.execute(
        "INSERT INTO seasons (name, is_current, ended_at) VALUES (?, ?, ?)",
        ("Season 1", 0, "2024-12-31 23:59:59")
    )
    season_id = cursor.lastrowid
    conn.commit()

    # Test: Reactivate season
    set_current_season(conn, season_id)

    # Verify: ended_at is NULL
    season = cursor.execute("SELECT ended_at FROM seasons WHERE id = ?", (season_id,)).fetchone()
    assert season[0] is None

    # Clean up
    cursor.execute("DELETE FROM seasons WHERE name = ?", ("Season 1",))
    conn.commit()
    conn.close()
