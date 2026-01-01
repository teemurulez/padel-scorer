import sqlite3
import pytest
import os


@pytest.fixture
def test_db(tmp_path):
    """Create isolated test database with player tables"""
    db_path = tmp_path / "test_migration_phase3.db"
    conn = sqlite3.connect(str(db_path))

    # Create schema
    conn.executescript("""
        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            UNIQUE(first_name, last_name)
        );

        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            total_points INTEGER DEFAULT 0,
            registry_id INTEGER,
            FOREIGN KEY (registry_id) REFERENCES player_registry(id)
        );
    """)
    conn.commit()

    yield conn

    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_parse_player_name_standard_format():
    """Test parsing standard 'FirstName LastName' format"""
    from migration_phase3 import parse_player_name

    first, last = parse_player_name("John Doe")
    assert first == "John"
    assert last == "Doe"


def test_parse_player_name_multiple_words():
    """Test parsing names with multiple words in last name"""
    from migration_phase3 import parse_player_name

    first, last = parse_player_name("Juan Carlos De La Rosa")
    assert first == "Juan"
    assert last == "Carlos De La Rosa"


def test_parse_player_name_single_word():
    """Test parsing single-word names (edge case)"""
    from migration_phase3 import parse_player_name

    first, last = parse_player_name("Madonna")
    assert first == "Madonna"
    assert last == "Player"


def test_migrate_creates_registry_entries(test_db):
    """Test that migration creates player_registry entries from legacy players"""
    from migration_phase3 import migrate_players_to_registry

    cursor = test_db.cursor()

    # Setup: Create legacy players without registry_id
    cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Test Player One", 0))
    cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Test Player Two", 0))
    test_db.commit()

    # Run migration
    migrated = migrate_players_to_registry(test_db)

    # Verify registry entries created
    cursor.execute("SELECT COUNT(*) FROM player_registry WHERE first_name = 'Test' AND last_name LIKE 'Player%'")
    registry_count = cursor.fetchone()[0]
    assert registry_count == 2

    # Verify legacy players are linked
    cursor.execute("SELECT COUNT(*) FROM players WHERE name LIKE 'Test Player%' AND registry_id IS NOT NULL")
    linked_count = cursor.fetchone()[0]
    assert linked_count == 2

    # Verify return count
    assert migrated == 2


def test_migrate_handles_duplicates(test_db):
    """Test that migration is idempotent and handles already-migrated players"""
    from migration_phase3 import migrate_players_to_registry

    cursor = test_db.cursor()

    # Setup: Create legacy player
    cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Idempotent Test", 10))
    player_id = cursor.lastrowid
    test_db.commit()

    # Run migration first time
    migrated1 = migrate_players_to_registry(test_db)
    assert migrated1 == 1

    # Verify player is migrated
    cursor.execute("SELECT registry_id FROM players WHERE id = ?", (player_id,))
    registry_id_first = cursor.fetchone()[0]
    assert registry_id_first is not None

    # Run migration second time (should be idempotent)
    migrated2 = migrate_players_to_registry(test_db)
    assert migrated2 == 0  # No additional migrations

    # Verify registry_id unchanged
    cursor.execute("SELECT registry_id FROM players WHERE id = ?", (player_id,))
    registry_id_second = cursor.fetchone()[0]
    assert registry_id_second == registry_id_first

    # Verify still only one registry entry
    cursor.execute("SELECT COUNT(*) FROM player_registry WHERE first_name = 'Idempotent' AND last_name = 'Test'")
    registry_count = cursor.fetchone()[0]
    assert registry_count == 1


def test_parse_player_name_long_names():
    """Test that very long names are truncated to 100 chars"""
    from migration_phase3 import parse_player_name

    long_first = "A" * 150
    long_last = "B" * 150
    full_name = f"{long_first} {long_last}"

    first, last = parse_player_name(full_name)

    assert len(first) <= 100
    assert len(last) <= 100
    assert first == "A" * 100
    assert last == "B" * 100


def test_parse_player_name_empty():
    """Test that empty/whitespace names get defaults"""
    from migration_phase3 import parse_player_name

    assert parse_player_name("") == ("Unknown", "Player")
    assert parse_player_name("   ") == ("Unknown", "Player")
