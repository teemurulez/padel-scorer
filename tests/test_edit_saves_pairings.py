import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_edit_pairings.db"
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

            db.commit()

        yield client, tournament_id

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_edit_tournament_saves_round1_pairings(client):
    """
    Test that editing a tournament with round1_pairings field
    saves the pairings to the database.

    This tests the new consolidated save workflow where the
    "Save Changes" button saves both tournament details and pairings.
    """
    client_obj, tournament_id = client

    # Step 1: Generate initial preview to get pairings structure
    preview_response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert preview_response.status_code == 200
    preview_data = json.loads(preview_response.data)
    initial_pairings = preview_data['pairings']

    # Step 2: Customize the pairings (swap two players on court 1)
    custom_pairings = json.loads(json.dumps(initial_pairings))
    custom_pairings[0]['team1'][0], custom_pairings[0]['team1'][1] = \
        custom_pairings[0]['team1'][1], custom_pairings[0]['team1'][0]

    # Step 3: Submit edit form with pairings data
    from database import get_db
    with app.app_context():
        db = get_db()
        players = db.execute(
            '''SELECT pr.first_name, pr.last_name
               FROM tournament_players tp
               JOIN player_registry pr ON tp.player_id = pr.id
               WHERE tp.tournament_id = ?
               ORDER BY pr.first_name, pr.last_name''',
            (tournament_id,)
        ).fetchall()
        player_names = [f"{p['first_name']} {p['last_name']}" for p in players]

    edit_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/edit',
        data={
            'tournament_name': 'Test Tournament Updated',
            'num_courts': '2',
            'players': '\n'.join(player_names),
            'round1_pairings': json.dumps(custom_pairings)
        },
        follow_redirects=False
    )

    assert edit_response.status_code == 302  # Redirect after successful save

    # Step 4: Verify pairings were saved to database
    from database import get_db
    with app.app_context():
        db = get_db()
        saved_pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ? ORDER BY court_number",
            (tournament_id,)
        ).fetchall()

    assert len(saved_pairings) == 2  # 2 courts

    # Verify the customization was saved
    court1 = saved_pairings[0]
    assert court1['team1_player1_id'] == custom_pairings[0]['team1'][0]
    assert court1['team1_player2_id'] == custom_pairings[0]['team1'][1]
    assert court1['team2_player1_id'] == custom_pairings[0]['team2'][0]
    assert court1['team2_player2_id'] == custom_pairings[0]['team2'][1]

    # Verify it differs from initial (proving customization)
    assert court1['team1_player1_id'] != initial_pairings[0]['team1'][0] or \
           court1['team1_player2_id'] != initial_pairings[0]['team1'][1]

def test_edit_tournament_without_pairings_keeps_existing(client):
    """
    Test that editing a tournament without pairings data
    preserves existing pairings.
    """
    client_obj, tournament_id = client

    # Step 1: Create and save initial pairings
    preview_response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert preview_response.status_code == 200
    preview_data = json.loads(preview_response.data)
    initial_pairings = preview_data['pairings']

    # Save via the save-round1-pairings endpoint
    save_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        json={'pairings': initial_pairings},
        content_type='application/json'
    )
    assert save_response.status_code == 200

    # Step 2: Edit tournament name without touching pairings
    from database import get_db
    with app.app_context():
        db = get_db()
        players = db.execute(
            '''SELECT pr.first_name, pr.last_name
               FROM tournament_players tp
               JOIN player_registry pr ON tp.player_id = pr.id
               WHERE tp.tournament_id = ?
               ORDER BY pr.first_name, pr.last_name''',
            (tournament_id,)
        ).fetchall()
        player_names = [f"{p['first_name']} {p['last_name']}" for p in players]

    edit_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/edit',
        data={
            'tournament_name': 'Test Tournament Renamed',
            'num_courts': '2',
            'players': '\n'.join(player_names),
            'round1_pairings': ''  # Empty, should preserve existing
        },
        follow_redirects=False
    )

    assert edit_response.status_code == 302

    # Step 3: Verify pairings still exist
    from database import get_db
    with app.app_context():
        db = get_db()
        saved_pairings = db.execute(
            "SELECT * FROM round1_preview_pairings WHERE tournament_id = ? ORDER BY court_number",
            (tournament_id,)
        ).fetchall()

    assert len(saved_pairings) == 2  # Pairings should still be there
