import sqlite3
from database import get_db


def parse_player_name(full_name):
    """Parse 'FirstName LastName' into components"""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = ' '.join(parts[1:])
    else:
        first_name = parts[0] if parts else 'Unknown'
        last_name = 'Player'
    return first_name, last_name


def migrate_players_to_registry(conn):
    """Migrate legacy players to player_registry"""
    cursor = conn.cursor()

    # Get all unique player names from legacy players table
    cursor.execute("SELECT DISTINCT name FROM players WHERE registry_id IS NULL")
    legacy_players = cursor.fetchall()

    migrated_count = 0
    for (full_name,) in legacy_players:
        first_name, last_name = parse_player_name(full_name)

        # Insert or get existing registry entry
        cursor.execute('''
            INSERT OR IGNORE INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        ''', (first_name, last_name))

        # Get the registry_id
        cursor.execute('''
            SELECT id FROM player_registry
            WHERE first_name = ? AND last_name = ?
        ''', (first_name, last_name))
        registry_id = cursor.fetchone()[0]

        # Update all legacy players with this name
        cursor.execute('''
            UPDATE players
            SET registry_id = ?
            WHERE name = ? AND registry_id IS NULL
        ''', (registry_id, full_name))

        migrated_count += cursor.rowcount

    conn.commit()
    return migrated_count
