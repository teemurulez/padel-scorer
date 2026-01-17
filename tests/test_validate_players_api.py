import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_validate_api.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        # Setup admin session
        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        # Add some players to registry
        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Matti", "Virtanen"))
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Anna", "Korhonen"))
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Matti", "Meikäläinen"))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_validate_players_endpoint_exists(client):
    """Test that validate-players endpoint exists"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Virtanen'},
                          content_type='application/json')
    assert response.status_code == 200

def test_validate_players_exact_match(client):
    """Test validation returns exact match for known player"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Virtanen'},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'exact'
    assert data['results'][0]['player_id'] == 1

def test_validate_players_fuzzy_match(client):
    """Test validation suggests correction for typo"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Meikalainen'},  # Missing ä
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'similar'
    assert data['results'][0]['suggestion'] == 'Matti Meikäläinen'

def test_validate_players_new_player(client):
    """Test validation detects new player"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Liisa Nieminen'},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'new'

def test_validate_players_multiple(client):
    """Test validation with multiple players"""
    players = "Matti Virtanen\nMatti Meikalainen\nLiisa Uusi"
    response = client.post('/admin/validate-players',
                          json={'players': players},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 3
    assert data['summary']['exact'] == 1
    assert data['summary']['similar'] == 1
    assert data['summary']['new'] == 1
