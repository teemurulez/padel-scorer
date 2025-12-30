"""
Integration tests for Round 1 seeded pairing vs Round 2+ court movement.

Verifies that the start_round route correctly:
- Uses seeded pairing (top players on Court 1) for Round 1
- Uses court movement (winners up, losers down) for Round 2+
"""
import pytest
import os
from app import app
from datetime import datetime, timedelta


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_round1_seeding.db"
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
    """Initialize test database with Phase 3 schema and test data"""
    from app import get_db_connection
    db = get_db_connection()

    # Create Phase 3 schema
    db.executescript("""
        DROP TABLE IF EXISTS scores;
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS tournament_players;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS player_registry;
        DROP TABLE IF EXISTS seasons;
        DROP VIEW IF EXISTS player_seeding;

        CREATE TABLE seasons (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            is_current BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP NULL
        );

        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        );

        -- Phase 2 players table (for backward compatibility)
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            total_points INTEGER DEFAULT 0,
            registry_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (registry_id) REFERENCES player_registry(id)
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            num_courts INTEGER NOT NULL,
            season_id INTEGER,
            status TEXT DEFAULT 'setup',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            archived_at TIMESTAMP NULL,
            FOREIGN KEY (season_id) REFERENCES seasons(id)
        );

        CREATE TABLE tournament_players (
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            final_rank INTEGER,
            total_points INTEGER DEFAULT 0,
            match_wins INTEGER DEFAULT 0,
            match_losses INTEGER DEFAULT 0,
            PRIMARY KEY (tournament_id, player_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE RESTRICT
        );

        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            status TEXT DEFAULT 'in_progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
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
            FOREIGN KEY (round_id) REFERENCES rounds(id)
        );

        CREATE TABLE scores (
            id INTEGER PRIMARY KEY,
            match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (player_id) REFERENCES player_registry(id)
        );

        -- Create player_seeding view
        CREATE VIEW player_seeding AS
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
        ORDER BY seed_points DESC, last_name ASC, first_name ASC;
    """)

    db.commit()


def test_round1_uses_seeded_pairing(client):
    """
    Test that Round 1 uses seeded pairing algorithm.

    Verifies:
    - Top 4 seeded players are assigned to Court 1
    - Bottom 4 seeded players are assigned to Court 2
    - Flash message mentions 'seeded pairings'
    """
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Setup: Create season
        db.execute(
            "INSERT INTO seasons (id, name, is_current) VALUES (1, 'Test Season', 1)"
        )

        # Create 8 players with different seed points (from past tournaments)
        # We'll create completed tournaments with points to establish seeding
        players_data = [
            (1, 'Alice', 'Top', 850),      # Highest seed
            (2, 'Bob', 'Strong', 820),     # 2nd seed
            (3, 'Carol', 'Good', 780),     # 3rd seed
            (4, 'David', 'Decent', 750),   # 4th seed
            (5, 'Eve', 'Average', 680),    # 5th seed
            (6, 'Frank', 'Okay', 650),     # 6th seed
            (7, 'Grace', 'Beginner', 620), # 7th seed
            (8, 'Henry', 'Newbie', 580),   # 8th seed (lowest)
        ]

        # Create players (in both player_registry and players table for compatibility)
        for player_id, first, last, _ in players_data:
            db.execute(
                "INSERT INTO player_registry (id, first_name, last_name) VALUES (?, ?, ?)",
                (player_id, first, last)
            )
            # Also add to Phase 2 players table (for backward compatibility)
            db.execute(
                "INSERT INTO players (id, name, registry_id) VALUES (?, ?, ?)",
                (player_id, f'{first} {last}', player_id)
            )

        # Create a completed past tournament to establish seeding
        past_date = (datetime.now() - timedelta(days=30)).isoformat()
        db.execute(
            """INSERT INTO tournaments (id, name, num_courts, season_id, status, completed_at)
               VALUES (999, 'Past Tournament', 2, 1, 'completed', ?)""",
            (past_date,)
        )

        # Add tournament_players entries with seed points
        for player_id, _, _, points in players_data:
            db.execute(
                """INSERT INTO tournament_players (tournament_id, player_id, total_points)
                   VALUES (999, ?, ?)""",
                (player_id, points)
            )

        # Create the actual tournament we're testing
        db.execute(
            """INSERT INTO tournaments (id, name, num_courts, season_id, status)
               VALUES (1, 'Test Tournament', 2, 1, 'setup')"""
        )

        db.commit()

    # Start Round 1
    response = client.post('/tournament/1/start_round', follow_redirects=False)

    # Verify redirect to court selection
    assert response.status_code == 302
    assert '/tournament/1/round/' in response.location

    with app.app_context():
        db = get_db_connection()

        # Get Round 1 matches
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = 1 AND r.round_number = 1
            ORDER BY m.court_number
        """).fetchall()

        assert len(matches) == 2, "Should have 2 courts"

        # Court 1 should have top 4 players (ids 1, 2, 3, 4)
        court1 = matches[0]
        court1_players = {
            court1['player1_id'],
            court1['player2_id'],
            court1['player3_id'],
            court1['player4_id']
        }
        assert court1_players == {1, 2, 3, 4}, \
            f"Court 1 should have top 4 players (1,2,3,4), got {court1_players}"

        # Court 2 should have bottom 4 players (ids 5, 6, 7, 8)
        court2 = matches[1]
        court2_players = {
            court2['player1_id'],
            court2['player2_id'],
            court2['player3_id'],
            court2['player4_id']
        }
        assert court2_players == {5, 6, 7, 8}, \
            f"Court 2 should have bottom 4 players (5,6,7,8), got {court2_players}"

        # Verify tournament status changed to 'active'
        tournament = db.execute(
            "SELECT status FROM tournaments WHERE id = 1"
        ).fetchone()
        assert tournament['status'] == 'active'

    # Check flash message (follow redirects to see flash)
    response_with_flash = client.post('/tournament/1/start_round', follow_redirects=True)
    assert b'seeded pairings' in response_with_flash.data or \
           b'based on recent performance' in response_with_flash.data, \
           "Flash message should mention seeded pairings"


def test_round2_uses_court_movement(client):
    """
    Test that Round 2+ uses court movement algorithm.

    Verifies:
    - Winners from Court 2 move up to Court 1
    - Losers from Court 1 move down to Court 2
    - Flash message mentions 'Winners moved up'
    """
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Setup: Create season, players, and tournament
        db.execute(
            "INSERT INTO seasons (id, name, is_current) VALUES (1, 'Test Season', 1)"
        )

        # Create 8 players (no seed points needed for this test)
        for i in range(1, 9):
            db.execute(
                "INSERT INTO player_registry (id, first_name, last_name) VALUES (?, ?, ?)",
                (i, f'Player', f'{i}')
            )
            # Also add to Phase 2 players table
            db.execute(
                "INSERT INTO players (id, name, registry_id) VALUES (?, ?, ?)",
                (i, f'Player {i}', i)
            )

        # Create tournament with status='active' (already past Round 1)
        db.execute(
            """INSERT INTO tournaments (id, name, num_courts, season_id, status)
               VALUES (1, 'Test Tournament', 2, 1, 'active')"""
        )

        # Create completed Round 1 with specific match results
        db.execute(
            "INSERT INTO rounds (id, tournament_id, round_number, status) VALUES (1, 1, 1, 'completed')"
        )

        # Court 1 Round 1: Players 1,2,3,4 - Team 2 wins (players 3,4 are winners)
        db.execute(
            """INSERT INTO matches (id, round_id, court_number, player1_id, player2_id,
                                   player3_id, player4_id, winning_team, completed)
               VALUES (1, 1, 1, 1, 2, 3, 4, 2, 1)"""
        )

        # Court 2 Round 1: Players 5,6,7,8 - Team 1 wins (players 5,6 are winners)
        db.execute(
            """INSERT INTO matches (id, round_id, court_number, player1_id, player2_id,
                                   player3_id, player4_id, winning_team, completed)
               VALUES (2, 1, 2, 5, 6, 7, 8, 1, 1)"""
        )

        # Add scores for winners
        for winner_id in [3, 4, 5, 6]:
            db.execute(
                "INSERT INTO scores (player_id, match_id, points) VALUES (?, ?, 1)",
                (winner_id, 1 if winner_id in [3, 4] else 2)
            )

        db.commit()

    # Start Round 2
    response = client.post('/tournament/1/start_round', follow_redirects=False)

    assert response.status_code == 302

    with app.app_context():
        db = get_db_connection()

        # Get Round 2 matches
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = 1 AND r.round_number = 2
            ORDER BY m.court_number
        """).fetchall()

        assert len(matches) == 2, "Should have 2 courts for Round 2"

        # Court 1 should have winners from both courts (movement algorithm)
        # Expected: Winners from Court 1 (3,4) + Winners from Court 2 (5,6)
        court1 = matches[0]
        court1_players = {
            court1['player1_id'],
            court1['player2_id'],
            court1['player3_id'],
            court1['player4_id']
        }
        # All winners should be on Court 1
        assert court1_players == {3, 4, 5, 6}, \
            f"Court 1 should have all winners (3,4,5,6), got {court1_players}"

        # Court 2 should have losers from both courts
        # Expected: Losers from Court 1 (1,2) + Losers from Court 2 (7,8)
        court2 = matches[1]
        court2_players = {
            court2['player1_id'],
            court2['player2_id'],
            court2['player3_id'],
            court2['player4_id']
        }
        assert court2_players == {1, 2, 7, 8}, \
            f"Court 2 should have all losers (1,2,7,8), got {court2_players}"

    # Check flash message
    response_with_flash = client.post('/tournament/1/start_round', follow_redirects=True)
    assert b'Winners moved up' in response_with_flash.data or \
           b'losers moved down' in response_with_flash.data, \
           "Flash message should mention winners/losers movement"


def test_round1_with_no_previous_tournaments(client):
    """
    Test that Round 1 works even when players have no seeding history.

    All players should have seed_points=0, but algorithm should still work.
    """
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Setup: Create season
        db.execute(
            "INSERT INTO seasons (id, name, is_current) VALUES (1, 'Test Season', 1)"
        )

        # Create 8 new players (no past tournament data)
        for i in range(1, 9):
            db.execute(
                "INSERT INTO player_registry (id, first_name, last_name) VALUES (?, ?, ?)",
                (i, f'New', f'Player{i}')
            )
            # Also add to Phase 2 players table
            db.execute(
                "INSERT INTO players (id, name, registry_id) VALUES (?, ?, ?)",
                (i, f'New Player{i}', i)
            )

        # Create tournament
        db.execute(
            """INSERT INTO tournaments (id, name, num_courts, season_id, status)
               VALUES (1, 'Test Tournament', 2, 1, 'setup')"""
        )

        db.commit()

    # Start Round 1
    response = client.post('/tournament/1/start_round', follow_redirects=False)

    # Should succeed even with no seeding data
    assert response.status_code == 302

    with app.app_context():
        db = get_db_connection()

        # Get Round 1 matches
        matches = db.execute("""
            SELECT * FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = 1 AND r.round_number = 1
            ORDER BY m.court_number
        """).fetchall()

        # Should have created 2 courts
        assert len(matches) == 2, "Should create 2 courts even with no seeding data"

        # Each court should have 4 unique players
        court1 = matches[0]
        court1_players = {
            court1['player1_id'],
            court1['player2_id'],
            court1['player3_id'],
            court1['player4_id']
        }
        assert len(court1_players) == 4, "Court 1 should have 4 unique players"

        court2 = matches[1]
        court2_players = {
            court2['player1_id'],
            court2['player2_id'],
            court2['player3_id'],
            court2['player4_id']
        }
        assert len(court2_players) == 4, "Court 2 should have 4 unique players"

        # Courts should have no overlapping players
        assert court1_players.isdisjoint(court2_players), \
            "Courts should have no overlapping players"
