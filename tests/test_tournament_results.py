import sqlite3
import pytest
import os
from app import app


@pytest.fixture
def client_with_db(tmp_path):
    """Create test client with isolated database"""
    db_path = tmp_path / "test_results.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client, str(db_path)

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_tournament_results_displays_standings(client_with_db):
    """Test that results page displays final standings correctly"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
    conn.close()

    # GET /tournament/<id>/results
    response = client.get(f'/tournament/{tournament_id}/results')

    # Verify response is successful
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Verify standings table shows ranks, names, points, wins, losses
    assert b'John Doe' in response.data, "Expected player John Doe in response"
    assert b'Jane Smith' in response.data, "Expected player Jane Smith in response"
    assert b'100' in response.data, "Expected points 100 in response"
    assert b'80' in response.data, "Expected points 80 in response"


def test_tournament_results_shows_archive_button(client_with_db):
    """Test that results page shows Archive Tournament button for completed tournaments"""
    client, db_path = client_with_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
    conn.close()

    # GET /tournament/<id>/results
    response = client.get(f'/tournament/{tournament_id}/results')

    # Verify Archive Tournament button is present (Finnish: "Arkistoi turnaus")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert 'Arkistoi turnaus'.encode('utf-8') in response.data, "Expected Archive Tournament button (Finnish) for completed tournament"


def test_tournament_results_404_for_nonexistent(client_with_db):
    """Test that results page redirects for non-existent tournament"""
    client, db_path = client_with_db

    # GET /tournament/999999/results (non-existent)
    response = client.get('/tournament/999999/results', follow_redirects=False)

    # Verify redirect (app redirects with flash message instead of 404)
    assert response.status_code == 302, f"Expected redirect for non-existent tournament, got {response.status_code}"
