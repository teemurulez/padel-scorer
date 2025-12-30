import sqlite3
import pytest


def test_complete_tournament_success():
    """Test that active tournament can be completed"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create tournament with status='active'
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "active"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # POST to /tournament/<id>/complete
        from app import app
        client = app.test_client()

        response = client.post(f'/tournament/{tournament_id}/complete')

        # Verify status changed to 'completed'
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'completed', f"Expected status 'completed', got '{status}'"

        # Verify redirect (should redirect to tournament_results which doesn't exist yet)
        # For now, we expect either redirect to tournament_results or a 404
        assert response.status_code in [302, 404], f"Expected redirect (302) or not found (404), got {response.status_code}"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_complete_tournament_calculates_stats():
    """Test that completion calculates match wins/losses/points"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create 2 players in registry
        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Alice", "Smith"))
        player1_id = cursor.lastrowid

        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Bob", "Jones"))
        player2_id = cursor.lastrowid

        # Create tournament with status='active'
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 1, season_id, "active"))
        tournament_id = cursor.lastrowid

        # Create round
        cursor.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)", (tournament_id, 1))
        round_id = cursor.lastrowid

        # Create 2 matches: Player 1 (team 1) wins both, Player 2 (team 2) loses both
        # Match 1: Team 1 (player1 + player1) vs Team 2 (player2 + player2) - Team 1 wins
        cursor.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (round_id, 1, player1_id, player1_id, player2_id, player2_id, 1, 1))

        # Match 2: Team 1 (player1 + player1) vs Team 2 (player2 + player2) - Team 1 wins
        cursor.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (round_id, 2, player1_id, player1_id, player2_id, player2_id, 1, 1))

        conn.commit()

        # Complete tournament
        from app import app
        client = app.test_client()
        response = client.post(f'/tournament/{tournament_id}/complete')

        # Query tournament_players table
        cursor.execute("""
            SELECT player_id, match_wins, match_losses, total_points
            FROM tournament_players
            WHERE tournament_id = ?
            ORDER BY player_id
        """, (tournament_id,))
        results = cursor.fetchall()

        # Verify: player 1 has match_wins=2, player 2 has match_wins=0
        player1_stats = [r for r in results if r[0] == player1_id][0]
        player2_stats = [r for r in results if r[0] == player2_id][0]

        assert player1_stats[1] == 2, f"Expected player 1 to have 2 wins, got {player1_stats[1]}"
        assert player1_stats[2] == 0, f"Expected player 1 to have 0 losses, got {player1_stats[2]}"
        assert player1_stats[3] == 2, f"Expected player 1 to have 2 points, got {player1_stats[3]}"

        assert player2_stats[1] == 0, f"Expected player 2 to have 0 wins, got {player2_stats[1]}"
        assert player2_stats[2] == 2, f"Expected player 2 to have 2 losses, got {player2_stats[2]}"
        assert player2_stats[3] == 0, f"Expected player 2 to have 0 points, got {player2_stats[3]}"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM matches WHERE round_id = ?", (round_id,))
        cursor.execute("DELETE FROM rounds WHERE id = ?", (round_id,))
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM player_registry WHERE id IN (?, ?)", (player1_id, player2_id))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_complete_tournament_sets_timestamp():
    """Test that completed_at timestamp is set"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create active tournament
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "active"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Complete it
        from app import app
        client = app.test_client()
        response = client.post(f'/tournament/{tournament_id}/complete')

        # Verify completed_at IS NOT NULL
        cursor.execute("SELECT completed_at FROM tournaments WHERE id = ?", (tournament_id,))
        completed_at = cursor.fetchone()[0]
        assert completed_at is not None, "Expected completed_at to be set"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_complete_tournament_rejects_non_active():
    """Test that only active tournaments can be completed"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create tournament with status='setup'
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "setup"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Try to complete it
        from app import app
        client = app.test_client()

        response = client.post(f'/tournament/{tournament_id}/complete', follow_redirects=True)

        # Verify error flash message (should be in response data)
        assert b'Cannot complete tournament' in response.data or b'status' in response.data, \
            "Expected error message about tournament status"

        # Verify status still 'setup'
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'setup', f"Expected status to remain 'setup', got '{status}'"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
