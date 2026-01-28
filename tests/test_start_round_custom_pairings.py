import pytest
import os
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_start_round.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        # Setup test data
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

            # Create 8 players
            for i in range(1, 9):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                player_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (tournament_id, player_id))

            db.commit()

        yield client, tournament_id

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_start_round1_uses_custom_pairings_if_saved(client):
    """Test start_round uses saved custom pairings when available"""
    client_obj, tournament_id = client

    # Save custom pairings first
    from database import get_db
    with app.app_context():
        db = get_db()

        # Custom pairing: specific player order
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, 1, 1, 2, 3, 4))

        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, 2, 5, 6, 7, 8))

        db.commit()

    # Set admin session (required to start tournament in setup mode)
    with client_obj.session_transaction() as sess:
        sess['is_admin'] = True

    # Start Round 1
    response = client_obj.post(f'/tournament/{tournament_id}/start_round')

    assert response.status_code == 302  # Redirect

    # Verify matches created with custom pairings
    with app.app_context():
        db = get_db()
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = ? AND r.round_number = 1
            ORDER BY m.court_number
        """, (tournament_id,)).fetchall()

    assert len(matches) == 2
    assert matches[0]['player1_id'] == 1
    assert matches[0]['player2_id'] == 2
    assert matches[0]['player3_id'] == 3
    assert matches[0]['player4_id'] == 4

def test_start_round1_deletes_used_custom_pairings(client):
    """Test custom pairings are deleted after being used"""
    client_obj, tournament_id = client

    # Save custom pairings
    from database import get_db
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?)
        """, (tournament_id, 1, 1, 2, 3, 4, tournament_id, 2, 5, 6, 7, 8))
        db.commit()

    # Set admin session (required to start tournament in setup mode)
    with client_obj.session_transaction() as sess:
        sess['is_admin'] = True

    # Start Round 1
    client_obj.post(f'/tournament/{tournament_id}/start_round')

    # Verify custom pairings deleted
    with app.app_context():
        db = get_db()
        pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchall()

    assert len(pairings) == 0

def test_start_round1_uses_algorithm_if_no_custom_pairings(client):
    """Test fallback to seeding algorithm when no custom pairings"""
    client_obj, tournament_id = client

    # Set admin session (required to start tournament in setup mode)
    with client_obj.session_transaction() as sess:
        sess['is_admin'] = True

    # Start Round 1 without saving custom pairings
    response = client_obj.post(f'/tournament/{tournament_id}/start_round')

    assert response.status_code == 302  # Redirect

    # Verify matches created (with seeding algorithm)
    from database import get_db
    with app.app_context():
        db = get_db()
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = ? AND r.round_number = 1
        """, (tournament_id,)).fetchall()

    assert len(matches) == 2  # Should still create matches
