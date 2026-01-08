import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_preserve.db"
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

def test_preview_preserves_saved_custom_pairings(client):
    """
    Test that preview-round1 endpoint loads existing saved pairings
    instead of regenerating them.

    This tests the workflow:
    1. User generates initial preview
    2. User customizes pairings and saves them
    3. User clicks Preview Round 1 again (or Edit -> Preview Round 1)
    4. Saved custom pairings should be returned, not regenerated
    """
    client_obj, tournament_id = client

    # Step 1: Generate initial preview
    response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert response.status_code == 200
    initial_data = json.loads(response.data)
    initial_pairings = initial_data['pairings']

    # Step 2: Customize the pairings (swap two players)
    # Deep copy to avoid modifying initial_pairings
    custom_pairings = json.loads(json.dumps(initial_pairings))
    # Swap team1 players on court 1
    custom_pairings[0]['team1'][0], custom_pairings[0]['team1'][1] = \
        custom_pairings[0]['team1'][1], custom_pairings[0]['team1'][0]

    # Step 3: Save custom pairings
    save_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        json={'pairings': custom_pairings},
        content_type='application/json'
    )
    assert save_response.status_code == 200

    # Step 4: Call preview again (simulating user clicking "Edit -> Preview Round 1")
    preview_again_response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert preview_again_response.status_code == 200
    preview_again_data = json.loads(preview_again_response.data)
    returned_pairings = preview_again_data['pairings']

    # ASSERTION: The returned pairings should match our custom pairings, not initial
    assert returned_pairings == custom_pairings, \
        "Preview should return saved custom pairings, not regenerate from scratch"

    # Additional verification: Ensure they differ from initial (proving customization was preserved)
    assert returned_pairings[0]['team1'] != initial_pairings[0]['team1'], \
        "Custom pairings should differ from initial generated pairings"

def test_preview_with_force_regenerates_pairings(client):
    """
    Test that preview-round1 with force=true regenerates pairings
    even when saved custom pairings exist.

    This tests the Reset button workflow.
    """
    client_obj, tournament_id = client

    # Step 1: Generate initial preview
    response = client_obj.post(f'/admin/tournaments/{tournament_id}/preview-round1')
    assert response.status_code == 200
    initial_data = json.loads(response.data)
    initial_pairings = initial_data['pairings']

    # Step 2: Customize and save pairings
    custom_pairings = json.loads(json.dumps(initial_pairings))
    custom_pairings[0]['team1'][0], custom_pairings[0]['team1'][1] = \
        custom_pairings[0]['team1'][1], custom_pairings[0]['team1'][0]

    save_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/save-round1-pairings',
        json={'pairings': custom_pairings},
        content_type='application/json'
    )
    assert save_response.status_code == 200

    # Step 3: Call preview with force=true (Reset button)
    reset_response = client_obj.post(
        f'/admin/tournaments/{tournament_id}/preview-round1',
        json={'force': True},
        content_type='application/json'
    )
    assert reset_response.status_code == 200
    reset_data = json.loads(reset_response.data)
    reset_pairings = reset_data['pairings']

    # ASSERTION: Reset should regenerate, matching initial algorithm output
    # Since seeding is deterministic, reset should match initial
    assert reset_pairings[0]['team1'] == initial_pairings[0]['team1'], \
        "Reset with force=true should regenerate to match initial algorithm output"

    # Verify it doesn't match the custom pairings
    assert reset_pairings[0]['team1'] != custom_pairings[0]['team1'], \
        "Reset should not preserve custom pairings"
