import pytest
from app import app
from datetime import datetime


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_player_profile.db"
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
    """Initialize test database with Phase 3 schema"""
    from database import init_db
    init_db()


def test_player_profile_with_season_data(client):
    """Test profile page displays correctly for player with season data"""
    # Setup test data within app context
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        current_year = datetime.now().year
        db.execute(
            'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
            (f'Season {current_year}',)
        )
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create player
        db.execute(
            'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
            ('Erik', 'Andersson')
        )
        player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create additional players for matches (need 3 more for 4-player matches)
        for i in range(1, 4):
            db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (f'Player{i}', 'Opponent')
            )

        # Create tournament
        db.execute(
            'INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
            ('Test Tournament', 3, season_id, 'completed')
        )
        tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create round
        db.execute(
            'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
            (tournament_id, 1)
        )
        round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 3 matches where player wins 2
        for i in range(3):
            db.execute(
                '''INSERT INTO matches
                   (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (round_id, i+1, player_id, player_id+1, player_id+2, player_id+3, 1 if i < 2 else 2, 1)
            )
            match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Add scores for all players in the match
            # Winners get 3 points, losers get 1 point
            team1_won = i < 2
            # Player is on team 1 (player1)
            db.execute(
                'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                (match_id, player_id, 3 if team1_won else 1)
            )
            db.execute(
                'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                (match_id, player_id+1, 3 if team1_won else 1)
            )
            db.execute(
                'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                (match_id, player_id+2, 1 if team1_won else 3)
            )
            db.execute(
                'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                (match_id, player_id+3, 1 if team1_won else 3)
            )

        db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{player_id}/profile')

    # Assert
    assert response.status_code == 200
    assert b'Erik Andersson' in response.data
    assert str(current_year).encode() in response.data
    # Should show rank, wins, tournaments (Finnish: "Kauden sijoitus")
    assert 'Kauden sijoitus'.encode('utf-8') in response.data


def test_player_profile_no_season_data(client):
    """Test profile shows 'No data' message for player with no season participation"""
    # Setup test data within app context
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        current_year = datetime.now().year
        db.execute(
            'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
            (f'Season {current_year}',)
        )

        # Create player but no tournament/match data
        db.execute(
            'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
            ('New', 'Player')
        )
        player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{player_id}/profile')

    # Assert
    assert response.status_code == 200
    assert b'New Player' in response.data
    assert 'Ei pelattuja turnauksia'.encode('utf-8') in response.data  # Finnish: "No tournaments played"


def test_player_profile_not_found(client):
    """Test profile redirects for non-existent player"""
    # Test: Try to visit non-existent player profile
    response = client.get('/player/99999/profile')

    # Assert: Redirects to home
    assert response.status_code == 302
    assert b'/player/99999/profile' not in response.data


def test_season_leaderboard_has_clickable_names(client):
    """Test that player names in season leaderboard are clickable links to profiles"""
    # Setup test data within app context
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        current_year = datetime.now().year
        db.execute(
            'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
            (f'Season {current_year}',)
        )
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create two players
        db.execute(
            'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
            ('Alice', 'Johnson')
        )
        player1_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        db.execute(
            'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
            ('Bob', 'Smith')
        )
        player2_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create two more players for 4-player match
        for i in range(2):
            db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (f'Player{i}', 'Opponent')
            )

        # Create tournament
        db.execute(
            'INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
            ('Test Tournament', 2, season_id, 'completed')
        )
        tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create round
        db.execute(
            'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
            (tournament_id, 1)
        )
        round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create completed match
        db.execute(
            '''INSERT INTO matches
               (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (round_id, 1, player1_id, player2_id, player1_id+2, player1_id+3, 1, 1)
        )
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Add scores - team 1 (Alice, Bob) wins
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                   (match_id, player1_id, 3))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                   (match_id, player2_id, 3))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                   (match_id, player1_id+2, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                   (match_id, player1_id+3, 1))
        db.commit()

    # Test: Visit season leaderboard
    response = client.get('/leaderboard/season')

    # Assert: Page loads
    assert response.status_code == 200

    # Assert: Player names are present
    assert b'Alice Johnson' in response.data
    assert b'Bob Smith' in response.data

    # Assert: Links to player profiles exist
    html = response.data.decode('utf-8')
    assert f'/player/{player1_id}/profile' in html
    assert f'/player/{player2_id}/profile' in html

    # Assert: Links are in anchor tags
    assert f'<a href="/player/{player1_id}/profile">' in html or f"<a href=\"/player/{player1_id}/profile\">" in html
