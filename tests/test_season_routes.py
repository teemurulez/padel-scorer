import pytest
import os
from app import app
from database import get_db

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_seasons.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_seasons_page_loads(client):
    """Test that /seasons page loads successfully"""
    response = client.get('/seasons')
    assert response.status_code == 200
    assert b'Season Management' in response.data

def test_seasons_page_shows_current_season(client):
    """Test that current season is displayed"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Winter 2025", 1))
        conn.commit()

    response = client.get('/seasons')
    assert b'Winter 2025' in response.data
    assert b'Current Season' in response.data

def test_seasons_page_shows_no_season_message(client):
    """Test message when no current season exists"""
    response = client.get('/seasons')
    assert b'No Active Season' in response.data

def test_seasons_page_shows_archived_seasons(client):
    """Test that archived seasons are listed"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO seasons (name, is_current, ended_at) VALUES (?, ?, ?)",
                      ("Season 2024", 0, "2024-12-31"))
        conn.commit()

    response = client.get('/seasons')
    assert b'Season 2024' in response.data
    assert b'Archived Seasons' in response.data

def test_end_current_season(client):
    """Test ending the current season"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Winter 2025", 1))
        season_id = cursor.lastrowid
        conn.commit()

    response = client.post('/seasons/end-current', follow_redirects=True)
    assert response.status_code == 200
    assert b'ended' in response.data

    # Verify season is no longer current
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        season = cursor.execute("SELECT is_current, ended_at FROM seasons WHERE id = ?", (season_id,)).fetchone()
        assert season[0] == 0  # is_current = 0
        assert season[1] is not None  # ended_at is set

def test_end_current_season_when_none_exists(client):
    """Test ending current season when none exists"""
    response = client.post('/seasons/end-current', follow_redirects=True)
    assert response.status_code == 200
    assert b'No current season' in response.data

def test_create_season(client):
    """Test creating a new season"""
    response = client.post('/seasons/create', data={'season_name': 'Spring 2025'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'created successfully' in response.data

    with app.app_context():
        conn = get_db()
        season = conn.execute("SELECT * FROM seasons WHERE name = ?", ("Spring 2025",)).fetchone()
        assert season is not None
        assert season['is_current'] == 1

def test_create_season_validates_required_name(client):
    """Test that season name is required"""
    response = client.post('/seasons/create', data={'season_name': ''}, follow_redirects=True)
    assert b'required' in response.data

def test_create_season_validates_unique_name(client):
    """Test that season names must be unique"""
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Spring 2025", 0))
        conn.commit()

    response = client.post('/seasons/create', data={'season_name': 'Spring 2025'}, follow_redirects=True)
    assert b'already exists' in response.data

def test_create_season_validates_max_length(client):
    """Test that season name has max length"""
    long_name = 'A' * 101
    response = client.post('/seasons/create', data={'season_name': long_name}, follow_redirects=True)
    assert b'100 characters' in response.data

def test_create_season_archives_current_season(client):
    """Test that creating new season archives the current one"""
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Old Season", 1))
        old_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    client.post('/seasons/create', data={'season_name': 'New Season'}, follow_redirects=True)

    with app.app_context():
        conn = get_db()
        old_season = conn.execute("SELECT is_current FROM seasons WHERE id = ?", (old_id,)).fetchone()
        assert old_season[0] == 0

def test_activate_archived_season(client):
    """Test reactivating an archived season"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO seasons (name, is_current, ended_at) VALUES (?, ?, ?)",
                      ("Old Season", 0, "2024-12-31"))
        season_id = cursor.lastrowid
        conn.commit()

    response = client.post(f'/seasons/{season_id}/activate', follow_redirects=True)
    assert response.status_code == 200
    assert b'is now active' in response.data

    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        season = cursor.execute("SELECT is_current, ended_at FROM seasons WHERE id = ?", (season_id,)).fetchone()
        assert season[0] == 1  # is_current = 1
        assert season[1] is None  # ended_at cleared

def test_activate_season_archives_current(client):
    """Test that activating a season archives the current one"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Current", 1))
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Archived", 0))
        archived_id = cursor.lastrowid
        conn.commit()

    client.post(f'/seasons/{archived_id}/activate', follow_redirects=True)

    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        current = cursor.execute("SELECT is_current FROM seasons WHERE name = ?", ("Current",)).fetchone()
        assert current[0] == 0

def test_activate_nonexistent_season(client):
    """Test activating a season that doesn't exist"""
    response = client.post('/seasons/999/activate', follow_redirects=True)
    assert b'not found' in response.data
