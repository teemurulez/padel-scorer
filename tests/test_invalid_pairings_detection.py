import pytest
import os
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_invalid_pairings.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_start_round1_detects_invalid_pairings(client):
    """Test start_round detects and handles invalid saved pairings"""
    from database import get_db

    with app.app_context():
        db = get_db()

        # Create season
        db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create tournament
        db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                  ("Test Tournament", 2, season_id, "setup"))
        tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create players 1-8
        for i in range(1, 9):
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      (f"Player{i}", f"Last{i}"))
            player_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                      (tournament_id, player_id))

        # Save pairings with player IDs 1-8
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?)
        """, (tournament_id, 1, 1, 2, 3, 4, tournament_id, 2, 5, 6, 7, 8))

        # Now change players (remove player 8, add player 9)
        db.execute("DELETE FROM tournament_players WHERE tournament_id = ? AND player_id = ?",
                  (tournament_id, 8))
        db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                  ("Player9", "Last9"))
        player9_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                  (tournament_id, player9_id))

        db.commit()

    # Try to start Round 1
    response = client.post(f'/tournament/{tournament_id}/start_round')

    # Should succeed (fallback to algorithm since pairings invalid)
    assert response.status_code == 302

    # Verify invalid pairings were deleted
    with app.app_context():
        db = get_db()
        pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchall()

    assert len(pairings) == 0  # Invalid pairings deleted

    # Verify matches created (using algorithm fallback)
    with app.app_context():
        db = get_db()
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = ? AND r.round_number = 1
        """, (tournament_id,)).fetchall()

    assert len(matches) == 2  # Matches still created
