import pytest
import os
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_history_schema.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_tournament_edit_history_table_exists(client):
    """Test that tournament_edit_history table exists with correct schema"""
    from database import get_db
    with app.app_context():
        db = get_db()

        # Check table exists
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tournament_edit_history'"
        ).fetchone()
        assert result is not None

        # Check columns
        columns = db.execute("PRAGMA table_info(tournament_edit_history)").fetchall()
        column_names = [col[1] for col in columns]

        assert 'id' in column_names
        assert 'tournament_id' in column_names
        assert 'changed_at' in column_names
        assert 'change_type' in column_names
        assert 'change_data' in column_names

def test_can_insert_edit_history(client):
    """Test that we can insert edit history records"""
    from database import get_db
    import json

    with app.app_context():
        db = get_db()

        # Create season and tournament first
        db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
        db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                  ("Test Tournament", 2, 1, "setup"))

        # Insert history record
        change_data = json.dumps({"player_name": "Matti Virtanen", "action": "added"})
        db.execute(
            """INSERT INTO tournament_edit_history
               (tournament_id, change_type, change_data)
               VALUES (?, ?, ?)""",
            (1, 'player_added', change_data)
        )
        db.commit()

        # Verify insertion
        result = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = ?"
        , (1,)).fetchone()

        assert result is not None
        assert result['change_type'] == 'player_added'
