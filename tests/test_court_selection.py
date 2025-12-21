"""
Tests for court selection route.
"""
import pytest
import os
from app import app


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_court_selection.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    with app.test_client() as client:
        with app.app_context():
            init_test_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def init_test_db():
    """Initialize test database with full schema"""
    from database import get_db
    db = get_db()

    # Create full schema for testing (Phase 2 + Phase 3)
    db.executescript("""
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS player_registry;

        -- Phase 2 tables
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            num_courts INTEGER NOT NULL,
            status TEXT DEFAULT 'setup',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            archived_at TIMESTAMP
        );

        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            status TEXT DEFAULT 'setup',
            FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            court_number INTEGER NOT NULL,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            player3_id INTEGER NOT NULL,
            player4_id INTEGER NOT NULL,
            winning_team INTEGER,
            completed BOOLEAN DEFAULT 0,
            teams_shuffled BOOLEAN DEFAULT 0,
            original_player1_id INTEGER,
            original_player2_id INTEGER,
            original_player3_id INTEGER,
            original_player4_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (round_id) REFERENCES rounds (id)
        );

        -- Phase 3 tables
        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        );

        -- Test data
        INSERT INTO player_registry (first_name, last_name) VALUES ('John', 'Doe');
        INSERT INTO player_registry (first_name, last_name) VALUES ('Jane', 'Smith');
        INSERT INTO player_registry (first_name, last_name) VALUES ('Bob', 'Johnson');
        INSERT INTO player_registry (first_name, last_name) VALUES ('Alice', 'Williams');
    """)
    db.commit()


def test_court_selection_displays_all_courts(client):
    """Test that court selection shows all courts for a round."""
    # Use app context to insert test data
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test Tournament', 4, 'active')")
        tournament_id = cursor.lastrowid

        # Create round
        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, 1, 'setup')", (tournament_id,))
        round_id = cursor.lastrowid

        # Create matches
        db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))

        db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 2, 2, 3, 4, 1)
        """, (round_id,))

        db.commit()

    # Request court selection page
    response = client.get(f'/tournament/{tournament_id}/round/{round_id}/courts', follow_redirects=True)

    assert response.status_code == 200
    assert b'Court 1' in response.data
    assert b'Court 2' in response.data
    assert b'John Doe' in response.data
    assert b'Jane Smith' in response.data


def test_court_selection_tournament_not_found(client):
    """Test that invalid tournament ID redirects to index."""
    response = client.get('/tournament/9999/round/1/courts')

    # Should redirect (302) when tournament not found
    assert response.status_code == 302
    assert response.location == '/'


def test_court_selection_round_not_found(client):
    """Test that invalid round ID redirects to index."""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test Tournament', 4, 'active')")
        tournament_id = cursor.lastrowid
        db.commit()

    # Request with invalid round
    response = client.get(f'/tournament/{tournament_id}/round/9999/courts', follow_redirects=True)

    assert response.status_code == 200
    assert b'Round not found' in response.data


def test_court_selection_round_wrong_tournament(client):
    """Test that round from different tournament is rejected."""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create two tournaments
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Tournament 1', 4, 'active')")
        tournament1_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Tournament 2', 4, 'active')")
        tournament2_id = cursor.lastrowid

        # Create round for tournament 1
        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, 1, 'setup')", (tournament1_id,))
        round_id = cursor.lastrowid
        db.commit()

    # Try to access round from tournament 2
    response = client.get(f'/tournament/{tournament2_id}/round/{round_id}/courts', follow_redirects=True)

    assert response.status_code == 200
    assert b'Round not found in this tournament' in response.data


def test_court_selection_empty_matches(client):
    """Test that round with no matches shows appropriate message."""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament and round, but no matches
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test Tournament', 4, 'active')")
        tournament_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, 1, 'setup')", (tournament_id,))
        round_id = cursor.lastrowid
        db.commit()

    # Request court selection
    response = client.get(f'/tournament/{tournament_id}/round/{round_id}/courts', follow_redirects=True)

    assert response.status_code == 200
    assert b'No matches found' in response.data


def test_court_selection_player_names_display(client):
    """Test that player names are correctly displayed."""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test Tournament', 4, 'active')")
        tournament_id = cursor.lastrowid

        # Create round
        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, 1, 'setup')", (tournament_id,))
        round_id = cursor.lastrowid

        # Create match
        db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))
        db.commit()

    # Request court selection
    response = client.get(f'/tournament/{tournament_id}/round/{round_id}/courts')

    assert response.status_code == 200
    # Check all 4 players displayed
    assert b'John Doe' in response.data
    assert b'Jane Smith' in response.data
    assert b'Bob Johnson' in response.data
    assert b'Alice Williams' in response.data
    # Check Team labels
    assert b'Team 1:' in response.data
    assert b'Team 2:' in response.data
