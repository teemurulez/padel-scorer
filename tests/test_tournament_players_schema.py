import sqlite3
import pytest


def test_tournament_players_table_exists():
    """Test that tournament_players junction table exists"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tournament_players'
    """)
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(tournament_players)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'tournament_id' in columns
    assert 'player_id' in columns
    assert 'final_rank' in columns
    assert 'total_points' in columns
    assert 'match_wins' in columns
    assert 'match_losses' in columns

    conn.close()


def test_tournament_players_foreign_keys():
    """Test that foreign keys are properly defined"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_key_list(tournament_players)")
    foreign_keys = cursor.fetchall()

    # Should have FK to tournaments and player_registry
    fk_tables = [fk[2] for fk in foreign_keys]
    assert 'tournaments' in fk_tables
    assert 'player_registry' in fk_tables

    conn.close()


def test_tournament_players_composite_primary_key():
    """Test that composite primary key prevents duplicate entries"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    tournament_id = None
    player_id = None
    season_id = None

    try:
        # Create test season, tournament, and player (include year for backward compatibility)
        cursor.execute("INSERT INTO seasons (name, year, is_current) VALUES (?, ?, ?)", ("Test Season PK", 2092, 0))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id)
            VALUES (?, ?, ?)
        """, ("Test Tournament", 2, season_id))
        tournament_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Test", "Player"))
        player_id = cursor.lastrowid

        conn.commit()

        # Insert first record
        cursor.execute("""
            INSERT INTO tournament_players (tournament_id, player_id, total_points)
            VALUES (?, ?, ?)
        """, (tournament_id, player_id, 100))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO tournament_players (tournament_id, player_id, total_points)
                VALUES (?, ?, ?)
            """, (tournament_id, player_id, 150))
            conn.commit()
    finally:
        # Cleanup (handle case where variables might not be set)
        if tournament_id:
            cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
            cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        if player_id:
            cursor.execute("DELETE FROM player_registry WHERE id = ?", (player_id,))
        if season_id:
            cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
