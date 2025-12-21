"""
Tests for team shuffling POST route validation.
"""
import pytest
import os
from app import app


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_team_shuffling.db"
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

    # Create full schema
    db.executescript("""
        DROP TABLE IF EXISTS scores;
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS player_registry;

        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            num_courts INTEGER NOT NULL,
            status TEXT DEFAULT 'setup',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        CREATE TABLE scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        );

        -- Test data
        INSERT INTO players (name) VALUES ('Player 1'), ('Player 2'), ('Player 3'), ('Player 4'), ('Player 5');
        INSERT INTO player_registry (first_name, last_name) VALUES
            ('John', 'Doe'), ('Jane', 'Smith'), ('Bob', 'Johnson'), ('Alice', 'Williams'), ('Charlie', 'Brown');
    """)
    db.commit()


def test_validation_rejects_duplicate_players(client):
    """Ensure exactly 4 unique players in submission"""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament, round, match
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
        tournament_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (?, 1)", (tournament_id,))
        round_id = cursor.lastrowid

        db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))
        db.commit()

    # Submit with duplicate player
    response = client.post(
        f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '1',  # Duplicate!
            'team2_player1': '3',
            'team2_player2': '4'
        },
        follow_redirects=True
    )

    assert b'All 4 players must be unique' in response.data


def test_validation_rejects_foreign_players(client):
    """Ensure submitted players are from original match"""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament, round, match with players 1,2,3,4
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
        tournament_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (?, 1)", (tournament_id,))
        round_id = cursor.lastrowid

        db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))
        db.commit()

    # Submit with player 5 (not in original match)
    response = client.post(
        f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '2',
            'team2_player1': '3',
            'team2_player2': '5'  # Not in original!
        },
        follow_redirects=True
    )

    assert b'Players must be from the original match' in response.data


def test_successful_team_shuffle_saves_original(client):
    """Test that successful shuffle saves original player IDs"""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament, round, match
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
        tournament_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (?, 1)", (tournament_id,))
        round_id = cursor.lastrowid

        cursor = db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))
        match_id = cursor.lastrowid
        db.commit()

    # Submit shuffled teams: (1,2 vs 3,4) -> (1,3 vs 2,4)
    response = client.post(
        f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '3',  # Swapped from team2
            'team2_player1': '2',  # Swapped from team1
            'team2_player2': '4'
        },
        follow_redirects=False
    )

    # Should redirect to active tournament
    assert response.status_code == 302
    assert f'/tournament/{tournament_id}' in response.location

    # Verify database updated correctly
    with app.app_context():
        from database import get_db
        db = get_db()
        match = db.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()

        # Check teams_shuffled flag
        assert match['teams_shuffled'] == 1

        # Check original players stored
        assert match['original_player1_id'] == 1
        assert match['original_player2_id'] == 2
        assert match['original_player3_id'] == 3
        assert match['original_player4_id'] == 4

        # Check new team configuration
        assert match['player1_id'] == 1
        assert match['player2_id'] == 3
        assert match['player3_id'] == 2
        assert match['player4_id'] == 4


def test_no_shuffle_does_not_set_flag(client):
    """Test that confirming without shuffle doesn't set teams_shuffled flag"""
    with app.app_context():
        from database import get_db
        db = get_db()

        # Create tournament, round, match
        cursor = db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
        tournament_id = cursor.lastrowid

        cursor = db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (?, 1)", (tournament_id,))
        round_id = cursor.lastrowid

        cursor = db.execute("""
            INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
            VALUES (?, 1, 1, 2, 3, 4)
        """, (round_id,))
        match_id = cursor.lastrowid
        db.commit()

    # Submit same teams (no shuffle)
    response = client.post(
        f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '2',
            'team2_player1': '3',
            'team2_player2': '4'
        },
        follow_redirects=False
    )

    assert response.status_code == 302

    # Verify teams_shuffled is still 0
    with app.app_context():
        from database import get_db
        db = get_db()
        match = db.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()

        assert match['teams_shuffled'] == 0
        assert match['original_player1_id'] is None
