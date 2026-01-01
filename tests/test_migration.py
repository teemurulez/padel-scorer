import sqlite3
import pytest
import os
from migration import migrate_tournaments_to_seasons
from app import app

@pytest.fixture
def test_db(tmp_path):
    """Create isolated test database"""
    db_path = tmp_path / "test_migration.db"
    conn = sqlite3.connect(str(db_path))

    # Create Phase 3 schema
    conn.executescript("""
        CREATE TABLE seasons (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            is_current BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            num_courts INTEGER NOT NULL,
            status TEXT DEFAULT 'setup',
            season_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (season_id) REFERENCES seasons(id)
        );
    """)
    conn.commit()

    yield conn

    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_migrate_creates_seasons_from_years(test_db):
    """Test that migration creates season for each year"""
    cursor = test_db.cursor()

    # Setup: Create tournaments in different years
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2024-1", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2024-2", 3, "2024-06-20 14:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2025-1", 3, "2025-01-10 09:00:00"))
    test_db.commit()

    # Run migration
    migrate_tournaments_to_seasons(test_db)

    # Verify seasons created
    seasons = cursor.execute("SELECT name FROM seasons ORDER BY name").fetchall()
    assert len(seasons) == 2
    assert seasons[0][0] == "Season 2024"
    assert seasons[1][0] == "Season 2025"

def test_migrate_assigns_tournaments_to_seasons(test_db):
    """Test that tournaments are assigned to correct seasons"""
    cursor = test_db.cursor()

    # Setup
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2024", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2025", 3, "2025-01-10 09:00:00"))
    test_db.commit()

    # Run migration
    migrate_tournaments_to_seasons(test_db)

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

def test_migrate_marks_latest_season_as_current(test_db):
    """Test that most recent season is marked as current"""
    cursor = test_db.cursor()

    # Setup
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2024", 3, "2024-01-15 10:00:00"))
    cursor.execute("INSERT INTO tournaments (name, num_courts, created_at, season_id) VALUES (?, ?, ?, NULL)",
                  ("Tournament 2025", 3, "2025-01-10 09:00:00"))
    test_db.commit()

    # Run migration
    migrate_tournaments_to_seasons(test_db)

    # Verify only 2025 is current
    current = cursor.execute("SELECT name FROM seasons WHERE is_current = 1").fetchone()
    assert current[0] == "Season 2025"

    # Verify 2024 is not current
    not_current = cursor.execute("SELECT name FROM seasons WHERE is_current = 0").fetchone()
    assert not_current[0] == "Season 2024"

def test_migrate_skips_if_already_migrated(test_db):
    """Test that migration doesn't run if tournaments already have season_id"""
    cursor = test_db.cursor()

    # Setup: Create season and assign tournament
    cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Existing Season", 1))
    season_id = cursor.lastrowid
    cursor.execute("INSERT INTO tournaments (name, num_courts, season_id) VALUES (?, ?, ?)",
                  ("Tournament", 3, season_id))
    test_db.commit()

    # Run migration
    result = migrate_tournaments_to_seasons(test_db)

    # Verify migration was skipped
    assert result == "already_migrated"

    # Verify no new seasons created
    seasons = cursor.execute("SELECT COUNT(*) FROM seasons").fetchone()
    assert seasons[0] == 1
