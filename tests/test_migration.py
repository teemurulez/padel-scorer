import sqlite3
from database import get_db
from migration import migrate_tournaments_to_seasons

def test_migrate_creates_seasons_from_years():
    """Test that migration creates season for each year"""
    conn = get_db()
    cursor = conn.cursor()

    # Cleanup: Remove any existing test data
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    # Setup: Create tournaments in different years
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2024-1", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2024-2", 3, "2024-06-20 14:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2025-1", 3, "2025-01-10 09:00:00"))
    conn.commit()

    # Run migration
    migrate_tournaments_to_seasons(conn)

    # Verify seasons created
    seasons = cursor.execute("SELECT name FROM seasons ORDER BY name").fetchall()
    assert len(seasons) == 2
    assert seasons[0][0] == "Season 2024"
    assert seasons[1][0] == "Season 2025"

    # Cleanup
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    conn.close()

def test_migrate_assigns_tournaments_to_seasons():
    """Test that tournaments are assigned to correct seasons"""
    conn = get_db()
    cursor = conn.cursor()

    # Cleanup: Remove any existing test data
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    # Setup
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2024", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2025", 3, "2025-01-10 09:00:00"))
    conn.commit()

    # Run migration
    migrate_tournaments_to_seasons(conn)

    # Verify assignments
    t2024 = cursor.execute(
        "SELECT t.name, s.name FROM tournaments t JOIN seasons s ON t.season_id = s.id WHERE t.name = ?",
        ("Tournament 2024",)
    ).fetchone()
    assert t2024[1] == "Season 2024"

    t2025 = cursor.execute(
        "SELECT t.name, s.name FROM tournaments t JOIN seasons s ON t.season_id = s.id WHERE t.name = ?",
        ("Tournament 2025",)
    ).fetchone()
    assert t2025[1] == "Season 2025"

    # Cleanup
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    conn.close()

def test_migrate_marks_latest_season_as_current():
    """Test that most recent season is marked as current"""
    conn = get_db()
    cursor = conn.cursor()

    # Cleanup: Remove any existing test data
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    # Setup
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2024", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at) VALUES (?, ?, ?)",
                  ("Tournament 2025", 3, "2025-01-10 09:00:00"))
    conn.commit()

    # Run migration
    migrate_tournaments_to_seasons(conn)

    # Verify only 2025 is current
    current = cursor.execute("SELECT name FROM seasons WHERE is_current = 1").fetchone()
    assert current[0] == "Season 2025"

    # Verify 2024 is not current
    not_current = cursor.execute("SELECT name FROM seasons WHERE is_current = 0").fetchone()
    assert not_current[0] == "Season 2024"

    # Cleanup
    cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Tournament 202%'")
    cursor.execute("DELETE FROM seasons WHERE name LIKE 'Season 202%'")
    conn.commit()

    conn.close()

def test_migrate_skips_if_already_migrated():
    """Test that migration doesn't run if tournaments already have season_id"""
    conn = get_db()
    cursor = conn.cursor()

    # Cleanup: Remove any existing test data
    cursor.execute("DELETE FROM tournaments WHERE name = 'Tournament'")
    cursor.execute("DELETE FROM seasons WHERE name = 'Existing Season'")
    conn.commit()

    # Setup: Create season and assign tournament
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Existing Season", 1))
    season_id = cursor.lastrowid
    cursor.execute("INSERT INTO tournaments (name, num_courts, season_id) VALUES (?, ?, ?)",
                  ("Tournament", 3, season_id))
    conn.commit()

    # Run migration
    result = migrate_tournaments_to_seasons(conn)

    # Verify migration was skipped
    assert result == "already_migrated"

    # Verify no new seasons created
    seasons = cursor.execute("SELECT COUNT(*) FROM seasons").fetchone()
    assert seasons[0] == 1

    # Cleanup
    cursor.execute("DELETE FROM tournaments WHERE name = 'Tournament'")
    cursor.execute("DELETE FROM seasons WHERE name = 'Existing Season'")
    conn.commit()

    conn.close()
