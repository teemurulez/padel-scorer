import sqlite3
import pytest
from datetime import datetime, timedelta

@pytest.fixture
def db():
    """Create test database with Phase 3 schema including player_seeding view."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tables (from Stage 1)
    cursor.execute('''
        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'setup',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE tournament_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            total_points INTEGER DEFAULT 0,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, player_id)
        )
    ''')

    # CREATE VIEW player_seeding HERE (this is what you'll implement)
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS player_seeding AS
        SELECT
            pr.id as player_id,
            pr.first_name,
            pr.last_name,
            COALESCE(SUM(tp.total_points), 0) as seed_points,
            COUNT(tp.tournament_id) as recent_tournaments
        FROM player_registry pr
        LEFT JOIN tournament_players tp ON pr.id = tp.player_id
        LEFT JOIN tournaments t ON tp.tournament_id = t.id
        WHERE (t.status IN ('completed', 'archived')
               AND t.completed_at >= date('now', '-6 months'))
            OR t.id IS NULL
        GROUP BY pr.id, pr.first_name, pr.last_name
        ORDER BY seed_points DESC, last_name ASC, first_name ASC
    ''')

    conn.commit()
    yield conn
    conn.close()

def test_player_seeding_view_calculates_seed_points(db):
    """Seed points are sum of total_points from last 6 months of completed tournaments."""
    cursor = db.cursor()

    # Add 2 players
    cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Alice", "Smith"))
    cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Bob", "Jones"))
    alice_id = 1
    bob_id = 2

    # Add 3 tournaments: 1 recent completed, 1 old completed, 1 active
    now = datetime.now()
    recent_date = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    old_date = (now - timedelta(days=200)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("INSERT INTO tournaments (name, status, completed_at) VALUES (?, ?, ?)",
                   ("Recent Tournament", "completed", recent_date))
    cursor.execute("INSERT INTO tournaments (name, status, completed_at) VALUES (?, ?, ?)",
                   ("Old Tournament", "completed", old_date))
    cursor.execute("INSERT INTO tournaments (name, status) VALUES (?, ?)",
                   ("Active Tournament", "active"))

    # Alice: 15 points (recent) + 10 points (old, should NOT count) = 15 seed_points
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, ?)",
                   (1, alice_id, 15))
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, ?)",
                   (2, alice_id, 10))

    # Bob: 12 points (recent) + 8 points (active, should NOT count) = 12 seed_points
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, ?)",
                   (1, bob_id, 12))
    cursor.execute("INSERT INTO tournament_players (tournament_id, player_id, total_points) VALUES (?, ?, ?)",
                   (3, bob_id, 8))

    db.commit()

    # Query view
    cursor.execute("SELECT * FROM player_seeding ORDER BY seed_points DESC")
    results = cursor.fetchall()

    assert len(results) == 2
    assert results[0]['first_name'] == 'Alice'
    assert results[0]['seed_points'] == 15
    assert results[0]['recent_tournaments'] == 1
    assert results[1]['first_name'] == 'Bob'
    assert results[1]['seed_points'] == 12
    assert results[1]['recent_tournaments'] == 1

def test_player_seeding_view_includes_players_with_no_tournaments(db):
    """Players with no tournament history appear with 0 seed_points."""
    cursor = db.cursor()

    # Add player with no tournaments
    cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Charlie", "Brown"))
    db.commit()

    # Query view
    cursor.execute("SELECT * FROM player_seeding WHERE first_name = ?", ("Charlie",))
    result = cursor.fetchone()

    assert result is not None
    assert result['first_name'] == 'Charlie'
    assert result['last_name'] == 'Brown'
    assert result['seed_points'] == 0
    assert result['recent_tournaments'] == 0
