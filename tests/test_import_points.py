import pytest
import json
from app import app
from database import get_db


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_import.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)


def setup_admin_and_season(client):
    """Helper to set up admin user and current season"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db = get_db()
        # Create admin
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        # Create season
        db.execute(
            "INSERT INTO seasons (name, is_current) VALUES ('Test Season', 1)"
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})


def test_import_points_requires_login(client):
    """Test that import points requires admin login"""
    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': []}),
        content_type='application/json'
    )
    assert response.status_code == 302
    assert '/admin/login' in response.location


def test_import_points_requires_active_season(client):
    """Test that import points requires an active season"""
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    client.post('/admin/login', data={'password': 'testpass123'})

    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [{'firstName': 'Test', 'lastName': 'Player', 'wins': 5}]}),
        content_type='application/json'
    )
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'aktiivista kautta' in data['error']


def test_import_points_creates_new_player(client):
    """Test that import creates new players in registry"""
    setup_admin_and_season(client)

    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Matti', 'lastName': 'Meikäläinen', 'wins': 5}
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['imported'] == 1
    assert data['created'] == 1

    # Verify player was created
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT * FROM player_registry WHERE first_name = 'Matti' AND last_name = 'Meikäläinen'"
        ).fetchone()
        assert player is not None

        # Verify points adjustment was created
        adj = db.execute(
            "SELECT adjustment FROM player_points_adjustment WHERE player_id = ?",
            (player['id'],)
        ).fetchone()
        assert adj is not None
        assert adj['adjustment'] == 5


def test_import_points_adds_to_existing_player(client):
    """Test that import adds points to existing player"""
    setup_admin_and_season(client)

    # Create existing player
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO player_registry (first_name, last_name) VALUES ('Maija', 'Virtanen')"
        )
        db.commit()

    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Maija', 'lastName': 'Virtanen', 'wins': 3}
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['imported'] == 1
    assert data['created'] == 0  # No new player created

    # Verify points were added
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT id FROM player_registry WHERE first_name = 'Maija' AND last_name = 'Virtanen'"
        ).fetchone()
        adj = db.execute(
            "SELECT adjustment FROM player_points_adjustment WHERE player_id = ?",
            (player['id'],)
        ).fetchone()
        assert adj['adjustment'] == 3


def test_import_points_accumulates(client):
    """Test that multiple imports accumulate points"""
    setup_admin_and_season(client)

    # First import
    client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Test', 'lastName': 'Player', 'wins': 5}
        ]}),
        content_type='application/json'
    )

    # Second import for same player
    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Test', 'lastName': 'Player', 'wins': 3}
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['success'] is True

    # Verify points accumulated (5 + 3 = 8)
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT id FROM player_registry WHERE first_name = 'Test'"
        ).fetchone()
        adj = db.execute(
            "SELECT adjustment FROM player_points_adjustment WHERE player_id = ?",
            (player['id'],)
        ).fetchone()
        assert adj['adjustment'] == 8


def test_import_points_case_insensitive_match(client):
    """Test that player matching is case insensitive"""
    setup_admin_and_season(client)

    # Create player with specific case
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO player_registry (first_name, last_name) VALUES ('PEKKA', 'POUTA')"
        )
        db.commit()

    # Import with different case
    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Pekka', 'lastName': 'Pouta', 'wins': 4}
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['created'] == 0  # Should match existing, not create new


def test_import_points_skips_invalid_entries(client):
    """Test that import skips entries with missing data or negative wins"""
    setup_admin_and_season(client)

    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Valid', 'lastName': 'Player', 'wins': 5},
            {'firstName': '', 'lastName': 'NoFirst', 'wins': 3},
            {'firstName': 'NoLast', 'lastName': '', 'wins': 3},
            {'firstName': 'Zero', 'lastName': 'Wins', 'wins': 0},
            {'firstName': 'Negative', 'lastName': 'Wins', 'wins': -1},
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['imported'] == 2  # Valid and Zero wins entries


def test_import_points_multiple_players(client):
    """Test importing multiple players at once"""
    setup_admin_and_season(client)

    response = client.post('/admin/players/import-points',
        data=json.dumps({'players': [
            {'firstName': 'Player', 'lastName': 'One', 'wins': 10},
            {'firstName': 'Player', 'lastName': 'Two', 'wins': 8},
            {'firstName': 'Player', 'lastName': 'Three', 'wins': 6},
        ]}),
        content_type='application/json'
    )

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['imported'] == 3
    assert data['created'] == 3
