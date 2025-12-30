import sqlite3
from database import get_db


def parse_player_name(full_name):
    """Parse 'FirstName LastName' into components, enforcing length limits"""
    MAX_NAME_LENGTH = 100

    parts = full_name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0][:MAX_NAME_LENGTH]
        last_name = ' '.join(parts[1:])[:MAX_NAME_LENGTH]
    else:
        first_name = parts[0][:MAX_NAME_LENGTH] if parts else 'Unknown'
        last_name = 'Player'
    return first_name, last_name


def migrate_players_to_registry(conn):
    """Migrate legacy players to player_registry"""
    cursor = conn.cursor()

    try:
        # Get all unique player names from legacy players table
        cursor.execute("SELECT DISTINCT name FROM players WHERE registry_id IS NULL")
        legacy_players = cursor.fetchall()

        migrated_count = 0
        for (full_name,) in legacy_players:
            try:
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
            except Exception as player_error:
                print(f"Error migrating player '{full_name}': {player_error}")
                raise

        conn.commit()
        return migrated_count
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise


def run_migration_if_needed():
    """Run Phase 3 migration if needed (idempotent)"""
    conn = get_db()
    try:
        cursor = conn.cursor()

        # Check if migration needed
        cursor.execute("SELECT COUNT(*) FROM players WHERE registry_id IS NULL")
        unmigrated_count = cursor.fetchone()[0]

        if unmigrated_count > 0:
            migrated = migrate_players_to_registry(conn)
            print(f"Migrated {migrated} player records to registry")
            return migrated
        else:
            print("No migration needed - all players already linked to registry")
            return 0
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration_if_needed()
