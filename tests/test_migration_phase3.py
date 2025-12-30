import sqlite3
from database import get_db


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


def test_migrate_creates_registry_entries():
    """Test that migration creates player_registry entries from legacy players"""
    from migration_phase3 import migrate_players_to_registry

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Cleanup
        cursor.execute("DELETE FROM players WHERE name LIKE 'Test Player%'")
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Test' AND last_name LIKE 'Player%'")
        conn.commit()

        # Setup: Create legacy players without registry_id
        cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Test Player One", 0))
        cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Test Player Two", 0))
        conn.commit()

        # Run migration
        migrated = migrate_players_to_registry(conn)

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

    finally:
        # Cleanup
        cursor.execute("DELETE FROM players WHERE name LIKE 'Test Player%'")
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Test' AND last_name LIKE 'Player%'")
        conn.commit()
        conn.close()
