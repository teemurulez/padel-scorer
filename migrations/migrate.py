#!/usr/bin/env python3
"""
Phase 3 Database Migration Script

Migrates Phase 2 database to Phase 3 schema:
- Creates new tables (seasons, player_registry, tournament_players)
- Adds columns to existing tables (tournaments, players)
- Migrates existing data to new structure
- Creates backup before migration
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def get_db_path():
    """Get database path"""
    db_path = Path('instance/padel.db')
    if not db_path.exists():
        db_path = Path('../instance/padel.db')
    if not db_path.exists():
        raise FileNotFoundError("Cannot find instance/padel.db")
    return str(db_path)


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def create_backup(db_path):
    """Create a backup of the database before migration"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def run_migration(db_path):
    """Execute the Phase 3 database migration"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        print("\n=== Phase 3 Database Migration ===\n")

        # Step 1: Read and execute SQL migration file
        print("Step 1: Creating new tables...")
        sql_file = Path(__file__).parent / '001_add_phase3_tables.sql'
        with open(sql_file, 'r') as f:
            sql_script = f.read()
        cursor.executescript(sql_script)
        print("✓ New tables created (seasons, player_registry, tournament_players)")

        # Step 2: Add columns to tournaments table
        print("\nStep 2: Modifying tournaments table...")
        columns_to_add = [
            ('season_id', 'INTEGER'),
            ('month', 'INTEGER'),
            ('status', 'TEXT DEFAULT "setup"')
        ]

        for col_name, col_type in columns_to_add:
            if not column_exists(cursor, 'tournaments', col_name):
                # Note: tournaments already has 'status' column, so we skip it
                if col_name == 'status':
                    print(f"  - Column 'status' already exists, skipping")
                    continue
                cursor.execute(f"ALTER TABLE tournaments ADD COLUMN {col_name} {col_type}")
                cursor.execute(
                    "INSERT OR IGNORE INTO _migration_tracking (table_name, column_name) VALUES (?, ?)",
                    ('tournaments', col_name)
                )
                print(f"  ✓ Added column: {col_name}")
            else:
                print(f"  - Column '{col_name}' already exists, skipping")

        # Step 3: Add registry_id to players table
        print("\nStep 3: Modifying players table...")
        if not column_exists(cursor, 'players', 'registry_id'):
            cursor.execute("ALTER TABLE players ADD COLUMN registry_id INTEGER REFERENCES player_registry(id)")
            cursor.execute(
                "INSERT OR IGNORE INTO _migration_tracking (table_name, column_name) VALUES (?, ?)",
                ('players', 'registry_id')
            )
            print("  ✓ Added column: registry_id")
        else:
            print("  - Column 'registry_id' already exists, skipping")

        # Step 4: Create current season
        print("\nStep 4: Creating current season...")
        current_year = datetime.now().year
        cursor.execute("SELECT id FROM seasons WHERE year = ?", (current_year,))
        season = cursor.fetchone()

        if not season:
            cursor.execute(
                "INSERT INTO seasons (year, status, total_tournaments) VALUES (?, 'active', 10)",
                (current_year,)
            )
            season_id = cursor.lastrowid
            print(f"  ✓ Created season {current_year} (ID: {season_id})")
        else:
            season_id = season[0]
            print(f"  - Season {current_year} already exists (ID: {season_id})")

        # Step 5: Migrate player names to player_registry
        print("\nStep 5: Migrating player data to registry...")
        cursor.execute("SELECT id, name FROM players")
        players = cursor.fetchall()

        player_mapping = {}  # old_player_id -> registry_id

        for player in players:
            player_id = player['id']
            name = player['name'].strip()

            # Parse name into first_name and last_name
            name_parts = name.split(maxsplit=1)
            if len(name_parts) == 2:
                first_name = name_parts[0]
                last_name = name_parts[1]
            else:
                first_name = ""
                last_name = name_parts[0]

            # Insert into player_registry (or get existing)
            cursor.execute(
                "INSERT OR IGNORE INTO player_registry (first_name, last_name) VALUES (?, ?)",
                (first_name, last_name)
            )
            cursor.execute(
                "SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?",
                (first_name, last_name)
            )
            registry_id = cursor.fetchone()[0]
            player_mapping[player_id] = registry_id

            # Update player record with registry_id
            cursor.execute(
                "UPDATE players SET registry_id = ? WHERE id = ?",
                (registry_id, player_id)
            )

        print(f"  ✓ Migrated {len(players)} players to registry")

        # Step 6: Link tournaments to current season
        print("\nStep 6: Linking tournaments to season...")
        cursor.execute("SELECT id FROM tournaments WHERE season_id IS NULL")
        tournaments = cursor.fetchall()

        for tournament in tournaments:
            tournament_id = tournament['id']
            cursor.execute(
                "UPDATE tournaments SET season_id = ? WHERE id = ?",
                (season_id, tournament_id)
            )

        if tournaments:
            print(f"  ✓ Linked {len(tournaments)} tournaments to season {current_year}")
        else:
            print("  - All tournaments already linked to a season")

        # Step 7: Calculate match wins/losses for tournament_players
        print("\nStep 7: Calculating match statistics...")
        cursor.execute("SELECT id FROM tournaments")
        all_tournaments = cursor.fetchall()

        total_stats_created = 0
        for tournament in all_tournaments:
            tournament_id = tournament['id']

            # Get all players who participated in this tournament
            cursor.execute("""
                SELECT DISTINCT p.id, p.registry_id
                FROM players p
                JOIN matches m ON (
                    p.id = m.player1_id OR
                    p.id = m.player2_id OR
                    p.id = m.player3_id OR
                    p.id = m.player4_id
                )
                JOIN rounds r ON m.round_id = r.id
                WHERE r.tournament_id = ?
            """, (tournament_id,))

            tournament_participants = cursor.fetchall()

            for participant in tournament_participants:
                player_id = participant['id']
                registry_id = participant['registry_id']

                if not registry_id:
                    continue  # Skip if registry_id not set

                # Calculate wins
                cursor.execute("""
                    SELECT COUNT(*) as wins
                    FROM matches m
                    JOIN rounds r ON m.round_id = r.id
                    WHERE r.tournament_id = ?
                    AND m.completed = 1
                    AND (
                        (m.winning_team = 1 AND (m.player1_id = ? OR m.player2_id = ?))
                        OR
                        (m.winning_team = 2 AND (m.player3_id = ? OR m.player4_id = ?))
                    )
                """, (tournament_id, player_id, player_id, player_id, player_id))
                wins = cursor.fetchone()[0]

                # Calculate losses
                cursor.execute("""
                    SELECT COUNT(*) as losses
                    FROM matches m
                    JOIN rounds r ON m.round_id = r.id
                    WHERE r.tournament_id = ?
                    AND m.completed = 1
                    AND (
                        (m.winning_team = 2 AND (m.player1_id = ? OR m.player2_id = ?))
                        OR
                        (m.winning_team = 1 AND (m.player3_id = ? OR m.player4_id = ?))
                    )
                """, (tournament_id, player_id, player_id, player_id, player_id))
                losses = cursor.fetchone()[0]

                # Get total points for this player in this tournament
                cursor.execute("""
                    SELECT COALESCE(SUM(s.points), 0) as total_points
                    FROM scores s
                    JOIN matches m ON s.match_id = m.id
                    JOIN rounds r ON m.round_id = r.id
                    WHERE r.tournament_id = ?
                    AND s.player_id = ?
                """, (tournament_id, player_id))
                total_points = cursor.fetchone()[0]

                # Insert or update tournament_players record
                cursor.execute("""
                    INSERT OR REPLACE INTO tournament_players
                    (tournament_id, player_id, total_points, match_wins, match_losses)
                    VALUES (?, ?, ?, ?, ?)
                """, (tournament_id, registry_id, total_points, wins, losses))

                total_stats_created += 1

        print(f"  ✓ Created {total_stats_created} tournament participation records")

        # Commit all changes
        conn.commit()

        # Step 8: Display migration summary
        print("\n=== Migration Summary ===")
        cursor.execute("SELECT COUNT(*) FROM seasons")
        seasons_count = cursor.fetchone()[0]
        print(f"Seasons: {seasons_count}")

        cursor.execute("SELECT COUNT(*) FROM player_registry")
        registry_count = cursor.fetchone()[0]
        print(f"Player Registry: {registry_count}")

        cursor.execute("SELECT COUNT(*) FROM tournament_players")
        tp_count = cursor.fetchone()[0]
        print(f"Tournament Players: {tp_count}")

        cursor.execute("SELECT COUNT(*) FROM tournaments WHERE season_id IS NOT NULL")
        linked_tournaments = cursor.fetchone()[0]
        print(f"Tournaments linked to seasons: {linked_tournaments}")

        print("\n✓ Migration completed successfully!\n")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        print("Database rolled back to previous state.")
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    try:
        db_path = get_db_path()
        print(f"Database: {db_path}")

        # Create backup
        backup_path = create_backup(db_path)

        # Run migration
        run_migration(db_path)

        print(f"Note: Backup saved at {backup_path}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
