import sqlite3
import os
from database import get_db

def migrate_tournaments_to_seasons(conn):
    """
    Migrate existing tournaments to season-based system.

    Creates seasons from distinct years in tournaments table,
    assigns tournaments to corresponding seasons,
    marks most recent season as current.

    Returns:
        str: "migrated" if migration ran, "already_migrated" if skipped
    """
    cursor = conn.cursor()

    # Check if migration needed (any tournament without season_id)
    result = cursor.execute(
        "SELECT COUNT(*) FROM tournaments WHERE season_id IS NULL"
    ).fetchone()

    if result[0] == 0:
        return "already_migrated"

    # Step 1: Create seasons from existing years
    years = cursor.execute("""
        SELECT DISTINCT strftime('%Y', created_at) as year
        FROM tournaments
        WHERE season_id IS NULL
        ORDER BY year
    """).fetchall()

    for year_row in years:
        year = year_row[0]
        cursor.execute(
            "INSERT INTO seasons (name, is_current, created_at) VALUES (?, ?, ?)",
            (f"Season {year}", 0, f"{year}-01-01 00:00:00")
        )

    # Step 2: Assign tournaments to seasons based on year
    cursor.execute("""
        UPDATE tournaments
        SET season_id = (
            SELECT s.id FROM seasons s
            WHERE s.name = 'Season ' || strftime('%Y', tournaments.created_at)
        )
        WHERE season_id IS NULL
    """)

    # Step 3: Mark most recent season as current
    cursor.execute(
        "UPDATE seasons SET is_current = 1 WHERE id = (SELECT MAX(id) FROM seasons)"
    )

    conn.commit()
    return "migrated"

def run_migration_if_needed():
    """Run migration automatically on app startup if needed"""
    conn = get_db()
    result = migrate_tournaments_to_seasons(conn)
    conn.close()
    return result

def migrate_add_round1_preview_pairings():
    """Add round1_preview_pairings table for manual Round 1 editing"""
    conn = get_db()
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='round1_preview_pairings'
    """)

    if cursor.fetchone():
        print("✅ round1_preview_pairings table already exists")
        conn.close()
        return "table_exists"

    # Read and execute migration SQL
    migration_path = os.path.join(os.path.dirname(__file__), 'migrations', 'add_round1_preview_pairings.sql')
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        cursor.executescript(migration_sql)
        conn.commit()
        print("✅ Created round1_preview_pairings table")
        result = "success"
    except FileNotFoundError as e:
        print(f"❌ Migration file not found: {migration_path}")
        conn.close()
        raise
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.close()
        raise
    finally:
        conn.close()

    return result

def migrate_seasons_schema():
    """Add name and ended_at columns to seasons table if missing"""
    conn = get_db()
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(seasons)")
    columns = [row[1] for row in cursor.fetchall()]

    changes_made = False

    if 'name' not in columns:
        print("Adding 'name' column to seasons table...")
        cursor.execute('ALTER TABLE seasons ADD COLUMN name TEXT')
        # Populate name from year for existing rows
        cursor.execute("UPDATE seasons SET name = 'Season ' || year WHERE name IS NULL")
        changes_made = True

    if 'ended_at' not in columns:
        print("Adding 'ended_at' column to seasons table...")
        cursor.execute('ALTER TABLE seasons ADD COLUMN ended_at TIMESTAMP NULL')
        changes_made = True

    if changes_made:
        conn.commit()
        print("✅ Seasons schema updated")
        result = "migrated"
    else:
        result = "already_migrated"

    conn.close()
    return result


if __name__ == "__main__":
    migrate_add_round1_preview_pairings()
