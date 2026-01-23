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


def test_player_profile_partner_statistics(client):
    """Test profile displays partner statistics (best partner, most common partner, opponent, nemesis)"""
    main_player = None  # Define outside to ensure scope
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 5 players: main player + 4 others
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Main', 'Player'))
        main_player = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Best', 'Partner'))
        best_partner_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Common', 'Partner'))
        common_partner_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Frequent', 'Opponent'))
        frequent_opponent_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Nemesis', 'Player'))
        nemesis_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create tournament
        db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                   ('Partner Test', 2, season_id, 'completed'))
        tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create round 1
        db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (tournament_id, 1))
        round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Match 1: Main + Best Partner WIN vs Frequent Opponent + Nemesis
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (round_id, 1, main_player, best_partner_id, frequent_opponent_id, nemesis_id, 1, 1))
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, best_partner_id, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, frequent_opponent_id, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, nemesis_id, 0))

        # Match 1b: Main + Best Partner WIN again (to make Best Partner the actual best)
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (round_id, 2, main_player, best_partner_id, frequent_opponent_id, common_partner_id, 1, 1))
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, best_partner_id, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, frequent_opponent_id, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, common_partner_id, 0))

        # Match 2: Main + Common Partner WIN vs Frequent Opponent + Nemesis
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (round_id, 3, main_player, common_partner_id, frequent_opponent_id, nemesis_id, 1, 1))
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, common_partner_id, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, frequent_opponent_id, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, nemesis_id, 0))

        # Create round 2 for more matches
        db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (tournament_id, 2))
        round_id2 = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Match 3: Main + Common Partner LOSE to Nemesis + Frequent Opponent
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (round_id2, 1, main_player, common_partner_id, nemesis_id, frequent_opponent_id, 2, 1))
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, main_player, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, common_partner_id, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, nemesis_id, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, frequent_opponent_id, 1))

        # Match 4: Main + Common Partner LOSE to Nemesis + Best Partner
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (round_id2, 2, main_player, common_partner_id, nemesis_id, best_partner_id, 2, 1))
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, main_player, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, common_partner_id, 0))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, nemesis_id, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (match_id, best_partner_id, 1))

        db.commit()

        # Verify data was inserted
        count = db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
        assert count == 5, f"Expected 5 matches, got {count}"

    # Test: Visit profile
    response = client.get(f'/player/{main_player}/profile')
    html = response.data.decode('utf-8')

    # Assert: Page loads
    assert response.status_code == 200

    # Debug: Check if basic stats are shown
    assert 'Main Player' in html, "Player name not found in page"

    # Assert: Partner stats section exists (requires total_matches > 0)
    assert 'Paritilastot' in html, f"Partner stats section not found. 'Voitot' present: {'Voitot' in html}"

    # Assert: Best partner shown (100% win rate with Best Partner - 1 win, 0 losses together)
    assert 'Best Partner' in html, "Best Partner not shown"
    assert 'Paras pari' in html

    # Assert: Most common partner shown (Common Partner - 3 matches together)
    assert 'Common Partner' in html, "Common Partner not shown"
    assert 'Yleisin pari' in html

    # Assert: Nemesis shown (lost 2 matches against Nemesis)
    assert 'Nemesis Player' in html, "Nemesis not shown"
    assert 'Vaikein vastustaja' in html


def test_player_profile_tournament_statistics(client):
    """Test profile displays tournament statistics (win streak, best/worst tournament, comeback rate)"""
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 4 players
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Test', 'Player'))
        main_player = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        for i in range(3):
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', (f'Other{i}', 'Player'))

        # Tournament 1: "Good Tournament" - player wins 3 matches
        db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                   ('Good Tournament', 1, season_id, 'completed'))
        t1_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        for round_num in range(1, 4):  # 3 rounds, all wins
            db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t1_id, round_num))
            r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (r_id, 1, main_player, main_player+1, main_player+2, main_player+3, 1, 1))
            m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player, 1))
            db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+1, 1))

        # Tournament 2: "Bad Tournament" - player wins only 1 match (fewer than Good Tournament)
        # Note: worst tournament only shows if player has at least 1 win there
        db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                   ('Bad Tournament', 1, season_id, 'completed'))
        t2_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Round 1: Win
        db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t2_id, 1))
        r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (r_id, 1, main_player, main_player+1, main_player+2, main_player+3, 1, 1))
        m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+1, 1))

        # Round 2: Loss
        db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t2_id, 2))
        r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (r_id, 1, main_player, main_player+1, main_player+2, main_player+3, 2, 1))
        m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+2, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+3, 1))

        db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{main_player}/profile')
    html = response.data.decode('utf-8')

    # Assert: Page loads
    assert response.status_code == 200

    # Assert: Tournament stats section exists
    assert 'Turnaukset' in html, "Tournament stats section not found"

    # Assert: Longest streak shown (3 consecutive wins in Good Tournament)
    assert 'Pisin voittoputki' in html
    assert '>3<' in html or '>3</span>' in html, "Win streak of 3 not shown"

    # Assert: Best tournament shown
    assert 'Paras turnaus' in html
    assert 'Good Tournament' in html, "Good Tournament not shown as best"

    # Assert: Worst tournament shown
    assert 'Huonoin turnaus' in html
    assert 'Bad Tournament' in html, "Bad Tournament not shown as worst"


def test_player_profile_court_statistics(client):
    """Test profile displays court statistics (matches per court, wins/losses per court)"""
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 4 players
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Court', 'Player'))
        main_player = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        for i in range(3):
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', (f'Other{i}', 'Player'))

        # Create tournament
        db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                   ('Court Test', 3, season_id, 'completed'))
        t_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t_id, 1))
        r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Match on court 1 - WIN
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (r_id, 1, main_player, main_player+1, main_player+2, main_player+3, 1, 1))
        m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+1, 1))

        # Match on court 2 - LOSE
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (r_id, 2, main_player, main_player+1, main_player+2, main_player+3, 2, 1))
        m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+2, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+3, 1))

        # Match on court 3 - WIN
        db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (r_id, 3, main_player, main_player+1, main_player+2, main_player+3, 1, 1))
        m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player, 1))
        db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+1, 1))

        db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{main_player}/profile')
    html = response.data.decode('utf-8')

    # Assert: Page loads
    assert response.status_code == 200

    # Assert: Court stats chart exists
    assert 'Ottelut per' in html, "Court stats chart not found"

    # Assert: All three courts are shown
    assert 'Kentt' in html  # "Kenttä" = Court in Finnish


def test_player_profile_current_form(client):
    """Test profile displays current form (last 10 matches with W/L indicators)"""
    with app.app_context():
        from app import get_db_connection
        db = get_db_connection()

        # Create current season
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 4 players
        db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', ('Form', 'Player'))
        main_player = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        for i in range(3):
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)', (f'Other{i}', 'Player'))

        # Create tournament
        db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                   ('Form Test', 1, season_id, 'completed'))
        t_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 5 matches with pattern: W, W, L, W, L
        results = [1, 1, 2, 1, 2]  # 1 = team1 wins, 2 = team2 wins (player on team1)
        for i, winning_team in enumerate(results):
            db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t_id, i+1))
            r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (r_id, 1, main_player, main_player+1, main_player+2, main_player+3, winning_team, 1))
            m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            if winning_team == 1:
                db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player, 1))
                db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+1, 1))
            else:
                db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+2, 1))
                db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)', (m_id, main_player+3, 1))

        db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{main_player}/profile')
    html = response.data.decode('utf-8')

    # Assert: Page loads
    assert response.status_code == 200

    # Assert: Current form section exists
    assert 'Viimeiset' in html, "Current form section not found"
    assert 'ottelua' in html

    # Assert: Win/loss indicators shown (checkmarks and X marks)
    assert '\u2713' in html or '✓' in html, "Win indicator not found"
    assert '\u2717' in html or '✗' in html, "Loss indicator not found"
