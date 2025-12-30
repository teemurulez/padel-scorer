import sqlite3
import pytest


def test_tournament_results_displays_standings():
    """Test that results page displays final standings correctly"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create completed tournament
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "completed"))
        tournament_id = cursor.lastrowid

        # Create players
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("John", "Doe"))
        player1_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Jane", "Smith"))
        player2_id = cursor.lastrowid

        # Create tournament_players entries with standings data
        cursor.execute("""
            INSERT INTO tournament_players
            (tournament_id, player_id, final_rank, total_points, match_wins, match_losses)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, player1_id, 1, 100, 5, 1))

        cursor.execute("""
            INSERT INTO tournament_players
            (tournament_id, player_id, final_rank, total_points, match_wins, match_losses)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, player2_id, 2, 80, 4, 2))

        conn.commit()

        # GET /tournament/<id>/results
        from app import app
        client = app.test_client()

        response = client.get(f'/tournament/{tournament_id}/results')

        # Verify response is successful
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify standings table shows ranks, names, points, wins, losses
        assert b'John Doe' in response.data, "Expected player John Doe in response"
        assert b'Jane Smith' in response.data, "Expected player Jane Smith in response"
        assert b'100' in response.data, "Expected points 100 in response"
        assert b'80' in response.data, "Expected points 80 in response"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM player_registry WHERE id IN (?, ?)", (player1_id, player2_id))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_tournament_results_shows_archive_button():
    """Test that Archive button appears for completed tournaments"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create completed tournament
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "completed"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # GET /tournament/<id>/results
        from app import app
        client = app.test_client()

        response = client.get(f'/tournament/{tournament_id}/results')

        # Verify "Archive Tournament" button is present
        assert b'Archive Tournament' in response.data, "Expected Archive Tournament button for completed tournament"

        # Now change status to archived
        cursor.execute("UPDATE tournaments SET status = ? WHERE id = ?", ("archived", tournament_id))
        conn.commit()

        # GET /tournament/<id>/results again
        response = client.get(f'/tournament/{tournament_id}/results')

        # Verify "Archive Tournament" button is NOT present
        assert b'Archive Tournament' not in response.data, "Archive Tournament button should not appear for archived tournament"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_tournament_results_404_for_nonexistent():
    """Test that nonexistent tournament shows error"""
    from app import app
    client = app.test_client()

    # GET /tournament/99999/results (without following redirects to capture flash)
    response = client.get('/tournament/99999/results')

    # Verify redirect to index
    assert response.status_code == 302, f"Expected redirect (302), got {response.status_code}"
    assert '/'.encode() in response.data or response.location == '/', \
        "Expected redirect to index page"
