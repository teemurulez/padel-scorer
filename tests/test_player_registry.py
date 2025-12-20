import pytest
import sqlite3
from app import app


@pytest.fixture
def client():
    """Create test client with in-memory database"""
    app.config['TESTING'] = True
    app.config['DATABASE'] = ':memory:'

    with app.test_client() as client:
        with app.app_context():
            init_test_db()
        yield client


def init_test_db():
    """Initialize test database with Phase 3 schema"""
    from database import get_db
    db = get_db()

    # Create minimal Phase 3 schema for testing
    db.executescript("""
        CREATE TABLE IF NOT EXISTS player_registry (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT,
            status TEXT DEFAULT 'setup',
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id INTEGER,
            player_id INTEGER,
            total_points INTEGER,
            PRIMARY KEY (tournament_id, player_id)
        );

        -- Create player_seeding view
        CREATE VIEW IF NOT EXISTS player_seeding AS
        SELECT
            pr.id as player_id,
            pr.first_name,
            pr.last_name,
            COALESCE(SUM(tp.total_points), 0) as seed_points,
            COUNT(DISTINCT tp.tournament_id) as recent_tournaments
        FROM player_registry pr
        LEFT JOIN tournament_players tp ON pr.id = tp.player_id
        LEFT JOIN tournaments t ON tp.tournament_id = t.id
            AND t.status IN ('completed', 'archived')
            AND t.completed_at >= datetime('now', '-180 days')
        GROUP BY pr.id, pr.first_name, pr.last_name
        ORDER BY seed_points DESC;

        -- Insert test data
        INSERT OR REPLACE INTO player_registry (id, first_name, last_name)
        VALUES (1, 'Existing', 'Player');
    """)
    db.commit()


def test_create_player_adds_to_registry(client):
    """Test creating a new player in registry"""
    response = client.post('/player/create', data={
        'first_name': 'New',
        'last_name': 'Player'
    }, follow_redirects=True)

    assert response.status_code == 200

    # Verify player was added
    from database import get_db
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT * FROM player_registry WHERE first_name = 'New' AND last_name = 'Player'"
        ).fetchone()
        assert player is not None
        assert player['first_name'] == 'New'
        assert player['last_name'] == 'Player'


def test_create_player_prevents_duplicates(client):
    """Test that duplicate players are rejected"""
    # Try to create a player that already exists (from test data)
    response = client.post('/player/create', data={
        'first_name': 'Existing',
        'last_name': 'Player'
    }, follow_redirects=True)

    assert response.status_code == 200

    # Verify only one instance exists
    from database import get_db
    with app.app_context():
        db = get_db()
        players = db.execute(
            "SELECT * FROM player_registry WHERE first_name = 'Existing' AND last_name = 'Player'"
        ).fetchall()
        assert len(players) == 1


def test_create_player_requires_both_names(client):
    """Test that both first and last names are required"""
    # Try with missing last name
    response = client.post('/player/create', data={
        'first_name': 'OnlyFirst',
        'last_name': ''
    }, follow_redirects=True)

    # Should redirect without creating player
    from database import get_db
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT * FROM player_registry WHERE first_name = 'OnlyFirst'"
        ).fetchone()
        assert player is None


def test_create_player_trims_whitespace(client):
    """Test that whitespace is trimmed from names"""
    response = client.post('/player/create', data={
        'first_name': '  Spaced  ',
        'last_name': '  Name  '
    }, follow_redirects=True)

    # Verify player was added with trimmed names
    from database import get_db
    with app.app_context():
        db = get_db()
        player = db.execute(
            "SELECT * FROM player_registry WHERE first_name = 'Spaced' AND last_name = 'Name'"
        ).fetchone()
        assert player is not None


def test_players_list_displays_all_players(client):
    """Test that players list shows all registered players"""
    # Add a few more players
    client.post('/player/create', data={'first_name': 'Alice', 'last_name': 'Smith'})
    client.post('/player/create', data={'first_name': 'Bob', 'last_name': 'Jones'})

    response = client.get('/players')
    assert response.status_code == 200

    # Should contain player names
    assert b'Existing' in response.data or b'existing' in response.data.lower()
    assert b'Alice' in response.data or b'alice' in response.data.lower()
    assert b'Bob' in response.data or b'bob' in response.data.lower()


def test_players_list_shows_seeding_info(client):
    """Test that players list includes seeding information"""
    response = client.get('/players')
    assert response.status_code == 200

    # Should contain seeding-related text
    assert b'Seed' in response.data or b'seed' in response.data.lower()
