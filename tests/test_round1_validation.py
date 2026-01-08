import pytest
import sqlite3
import os
from app import app, validate_round1_pairings

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_round1_validation.db"
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

            # Create players
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

def test_validate_pairings_valid(client):
    """Test validation passes for valid pairings"""
    _, tournament_id = client

    pairings = [
        {"court": 1, "team1": [1, 2], "team2": [3, 4]},
        {"court": 2, "team1": [5, 6], "team2": [7, 8]}
    ]

    from database import get_db
    with app.app_context():
        db = get_db()
        errors = validate_round1_pairings(tournament_id, pairings, db)

    assert errors == []

def test_validate_pairings_duplicate_within_court(client):
    """Test validation fails for duplicate player within court"""
    _, tournament_id = client

    pairings = [
        {"court": 1, "team1": [1, 1], "team2": [3, 4]},  # Player 1 twice
        {"court": 2, "team1": [5, 6], "team2": [7, 8]}
    ]

    from database import get_db
    with app.app_context():
        db = get_db()
        errors = validate_round1_pairings(tournament_id, pairings, db)

    assert len(errors) > 0
    assert any("Duplicate players" in err for err in errors)

def test_validate_pairings_duplicate_across_courts(client):
    """Test validation fails for player assigned to multiple courts"""
    _, tournament_id = client

    pairings = [
        {"court": 1, "team1": [1, 2], "team2": [3, 4]},
        {"court": 2, "team1": [1, 6], "team2": [7, 8]}  # Player 1 again
    ]

    from database import get_db
    with app.app_context():
        db = get_db()
        errors = validate_round1_pairings(tournament_id, pairings, db)

    assert len(errors) > 0
    assert any("multiple courts" in err for err in errors)

def test_validate_pairings_invalid_player_id(client):
    """Test validation fails for player not in tournament"""
    _, tournament_id = client

    pairings = [
        {"court": 1, "team1": [1, 2], "team2": [3, 4]},
        {"court": 2, "team1": [5, 999], "team2": [7, 8]}  # Player 999 doesn't exist
    ]

    from database import get_db
    with app.app_context():
        db = get_db()
        errors = validate_round1_pairings(tournament_id, pairings, db)

    assert len(errors) > 0
    assert any("not in tournament" in err for err in errors)

def test_validate_pairings_missing_players(client):
    """Test validation fails when not all tournament players assigned"""
    _, tournament_id = client

    pairings = [
        {"court": 1, "team1": [1, 2], "team2": [3, 4]}
        # Missing court 2 (players 5, 6, 7, 8)
    ]

    from database import get_db
    with app.app_context():
        db = get_db()
        errors = validate_round1_pairings(tournament_id, pairings, db)

    assert len(errors) > 0
    assert any("Not all players assigned" in err for err in errors)
