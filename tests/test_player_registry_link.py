import sqlite3
import pytest


def test_players_table_has_registry_id():
    """Test that players table has registry_id foreign key"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'registry_id' in columns

    conn.close()


def test_players_registry_id_foreign_key():
    """Test that registry_id references player_registry"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_key_list(players)")
    foreign_keys = cursor.fetchall()

    # Find FK to player_registry
    registry_fks = [fk for fk in foreign_keys if fk[2] == 'player_registry']
    assert len(registry_fks) > 0

    conn.close()


def test_players_can_link_to_registry():
    """Test that players can be linked to registry entries"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create registry player
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Test", "LinkPlayer"))
        registry_id = cursor.lastrowid
        conn.commit()

        # Create old-style player linked to registry
        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Test LinkPlayer", 100, registry_id))
        player_id = cursor.lastrowid
        conn.commit()

        # Verify link
        cursor.execute("""
            SELECT p.name, pr.first_name, pr.last_name
            FROM players p
            JOIN player_registry pr ON p.registry_id = pr.id
            WHERE p.id = ?
        """, (player_id,))

        row = cursor.fetchone()
        assert row[0] == "Test LinkPlayer"
        assert row[1] == "Test"
        assert row[2] == "LinkPlayer"
    finally:
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
        cursor.execute("DELETE FROM player_registry WHERE id = ?", (registry_id,))
        conn.commit()
        conn.close()
