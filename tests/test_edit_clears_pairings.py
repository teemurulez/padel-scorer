import pytest
import os
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_edit_clears.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        # Setup admin session to bypass authentication
        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

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

            # Save preview pairings
            db.execute("""
                INSERT INTO round1_preview_pairings
                (tournament_id, court_number, team1_player1_id, team1_player2_id,
                 team2_player1_id, team2_player2_id)
                VALUES (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?)
            """, (tournament_id, 1, 1, 2, 3, 4, tournament_id, 2, 5, 6, 7, 8))

            db.commit()

        yield client, tournament_id

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_edit_players_updates_pairings_by_position(client):
    """Test editing player list updates pairings by position mapping (preserves structure)"""
    client_obj, tournament_id = client

    # Verify pairings exist before edit
    from database import get_db
    with app.app_context():
        db = get_db()
        pairings_before = db.execute(
            "SELECT COUNT(*) as count FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchone()['count']

    assert pairings_before == 2

    # Edit tournament with different player list (same count = 8)
    # This simulates changing some player names
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nPlayer4 Last4\nPlayer9 New9\nPlayer10 New10\nPlayer11 New11\nPlayer12 New12"

    response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/edit',
        data={
            'tournament_name': 'Test Tournament',
            'num_courts': 2,
            'players': new_players
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # Pairings are preserved (updated with new player IDs by position mapping)
    with app.app_context():
        db = get_db()
        pairings_after = db.execute(
            "SELECT COUNT(*) as count FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchone()['count']

    # Same count - pairings preserved with ID mapping
    assert pairings_after == 2

def test_edit_num_courts_clears_saved_pairings(client):
    """Test changing number of courts clears saved pairings"""
    client_obj, tournament_id = client

    # Verify pairings exist
    from database import get_db
    with app.app_context():
        db = get_db()
        pairings_before = db.execute(
            "SELECT COUNT(*) as count FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchone()['count']

    assert pairings_before == 2

    # Edit tournament with different court count (2 → 1)
    # Need only 4 players for 1 court
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nPlayer4 Last4"

    response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/edit',
        data={
            'tournament_name': 'Test Tournament',
            'num_courts': 1,  # Changed from 2
            'players': new_players
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # Verify pairings cleared
    with app.app_context():
        db = get_db()
        pairings_after = db.execute(
            "SELECT COUNT(*) as count FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchone()['count']

    assert pairings_after == 0

def test_edit_tournament_name_does_not_clear_pairings(client):
    """Test changing only tournament name preserves pairings"""
    client_obj, tournament_id = client

    # Get current player list
    from database import get_db
    with app.app_context():
        db = get_db()
        players = db.execute("""
            SELECT pr.first_name, pr.last_name
            FROM player_registry pr
            JOIN tournament_players tp ON pr.id = tp.player_id
            WHERE tp.tournament_id = ?
            ORDER BY pr.id
        """, (tournament_id,)).fetchall()

    player_list = '\n'.join([f"{p['first_name']} {p['last_name']}" for p in players])

    # Edit only tournament name (same courts, same players)
    response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/edit',
        data={
            'tournament_name': 'New Tournament Name',  # Changed
            'num_courts': 2,  # Same
            'players': player_list  # Same
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # Verify pairings preserved
    with app.app_context():
        db = get_db()
        pairings_after = db.execute(
            "SELECT COUNT(*) as count FROM round1_preview_pairings WHERE tournament_id = ?",
            (tournament_id,)
        ).fetchone()['count']

    assert pairings_after == 2  # Still exists
