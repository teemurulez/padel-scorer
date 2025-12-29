import sqlite3
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
