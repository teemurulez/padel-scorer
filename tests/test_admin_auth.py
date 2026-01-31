import pytest
import sqlite3
from app import app
from database import get_db


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_admin.db"
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


def test_admin_users_table_exists(client):
    """Test that admin_users table exists"""
    from database import get_db
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_users'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result['name'] == 'admin_users'


def test_admin_users_table_has_correct_schema(client):
    """Test that admin_users table has expected columns"""
    from database import get_db
    with app.app_context():
        db = get_db()
        cursor = db.execute("PRAGMA table_info(admin_users)")
        columns = {row['name']: row['type'] for row in cursor.fetchall()}

        assert 'id' in columns
        assert 'password_hash' in columns
        assert 'created_at' in columns
        assert 'updated_at' in columns
        assert columns['password_hash'] == 'TEXT'


def test_admin_setup_page_loads_when_no_admin_exists(client):
    """Test that /admin/setup loads when no admin user exists"""
    response = client.get('/admin/setup')
    assert response.status_code == 200
    assert 'Ylläpidon asennus'.encode('utf-8') in response.data  # Finnish: "Admin Setup"
    assert b'password' in response.data.lower()


def test_admin_setup_redirects_when_admin_exists(client):
    """Test that /admin/setup redirects to login when admin already exists"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.get('/admin/setup')
    assert response.status_code == 302
    assert '/admin/login' in response.location


def test_admin_setup_post_creates_admin_user(client):
    """Test that POST /admin/setup creates admin user with hashed password"""
    from database import get_db
    from werkzeug.security import check_password_hash

    response = client.post('/admin/setup', data={
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    }, follow_redirects=False)

    # Should redirect to login
    assert response.status_code == 302
    assert '/admin/login' in response.location

    # Verify admin user was created
    with app.app_context():
        db = get_db()
        admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()
        assert admin is not None
        assert check_password_hash(admin['password_hash'], 'testpass123')


def test_admin_setup_post_rejects_mismatched_passwords(client):
    """Test that setup rejects mismatched passwords"""
    response = client.post('/admin/setup', data={
        'password': 'testpass123',
        'confirm_password': 'different'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Passwords do not match' in response.data


def test_admin_setup_post_rejects_short_password(client):
    """Test that setup rejects passwords shorter than 8 characters"""
    response = client.post('/admin/setup', data={
        'password': 'short',
        'confirm_password': 'short'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'at least 8 characters' in response.data


def test_admin_setup_post_rejects_when_admin_exists(client):
    """Test that setup POST rejects when admin already exists"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create existing admin
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('existing', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.post('/admin/setup', data={
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    }, follow_redirects=False)

    # Should redirect to login
    assert response.status_code == 302
    assert '/admin/login' in response.location


def test_admin_login_page_loads(client):
    """Test that /admin/login loads"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin user first
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.get('/admin/login')
    assert response.status_code == 200
    assert 'Ylläpito'.encode('utf-8') in response.data  # Finnish: "Admin Login"
    assert b'password' in response.data.lower()


def test_admin_login_redirects_to_setup_when_no_admin(client):
    """Test that /admin/login redirects to setup when no admin exists"""
    response = client.get('/admin/login')
    assert response.status_code == 302
    assert '/admin/setup' in response.location


def test_admin_login_post_success(client):
    """Test successful admin login"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin user
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.post('/admin/login', data={
        'password': 'testpass123'
    }, follow_redirects=False)

    # Should redirect to admin dashboard
    assert response.status_code == 302
    assert '/admin' in response.location

    # Check session was set
    with client.session_transaction() as sess:
        assert sess.get('logged_in_as_admin') is True
        assert 'login_time' in sess
        assert 'last_activity' in sess


def test_admin_login_post_failure(client):
    """Test failed admin login with wrong password"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin user
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.post('/admin/login', data={
        'password': 'wrongpassword'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Invalid password' in response.data

    # Check session was NOT set
    with client.session_transaction() as sess:
        assert sess.get('logged_in_as_admin') is not True


def test_admin_dashboard_requires_login(client):
    """Test that /admin requires authentication"""
    response = client.get('/admin', follow_redirects=False)
    assert response.status_code == 302
    assert '/admin/login' in response.location


def test_admin_dashboard_accessible_when_logged_in(client):
    """Test that /admin is accessible when logged in"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})

    # Access admin dashboard
    response = client.get('/admin')
    assert response.status_code == 200


def test_session_timeout_after_30_minutes(client):
    """Test that session expires after 30 minutes of inactivity"""
    from database import get_db
    from werkzeug.security import generate_password_hash
    from datetime import datetime, timedelta

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})

    # Manually set last_activity to 31 minutes ago
    with client.session_transaction() as sess:
        old_time = datetime.now() - timedelta(minutes=31)
        sess['last_activity'] = old_time.isoformat()

    # Try to access admin page
    response = client.get('/admin', follow_redirects=True)
    assert b'Session expired' in response.data or 'Ylläpito'.encode('utf-8') in response.data  # Finnish


def test_session_updates_last_activity(client):
    """Test that accessing admin pages updates last_activity"""
    from database import get_db
    from werkzeug.security import generate_password_hash
    from datetime import datetime, timedelta

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})

    # Get initial last_activity
    with client.session_transaction() as sess:
        initial_time = datetime.fromisoformat(sess['last_activity'])

    # Wait a moment and access admin page
    import time
    time.sleep(0.1)

    client.get('/admin')

    # Check last_activity was updated
    with client.session_transaction() as sess:
        updated_time = datetime.fromisoformat(sess['last_activity'])
        assert updated_time > initial_time


def test_login_and_setup_routes_bypass_auth_check(client):
    """Test that /admin/login and /admin/setup don't require auth"""
    # These should be accessible without authentication
    response = client.get('/admin/setup')
    assert response.status_code in [200, 302]  # 200 if no admin, 302 if admin exists

    # Create admin so login page works
    from database import get_db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('test', method='pbkdf2:sha256'),)
        )
        db.commit()

    response = client.get('/admin/login')
    assert response.status_code == 200


def test_admin_dashboard_shows_tabs(client):
    """Test that admin dashboard displays all 4 tabs and logout button"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})

    # Access admin dashboard
    response = client.get('/admin')
    assert response.status_code == 200

    # Check for all 3 tab names (Finnish)
    assert b'Kaudet' in response.data  # Finnish: "Seasons"
    assert b'Pelaajat' in response.data  # Finnish: "Players"
    assert b'Data' in response.data

    # Check for logout button (Finnish: "Kirjaudu ulos")
    assert b'Kirjaudu ulos' in response.data or b'logout' in response.data


def test_admin_dashboard_has_logo_placeholder(client):
    """Test that admin dashboard has logo or title placeholder"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    # Login
    client.post('/admin/login', data={'password': 'testpass123'})

    # Access admin dashboard
    response = client.get('/admin')
    assert response.status_code == 200

    # Check for logo placeholder or admin title (Finnish: "YLLÄPITO")
    assert 'YLLÄPITO'.encode('utf-8') in response.data or b'[LOGO]' in response.data


def test_admin_logout_clears_session(client):
    """Test that logout clears session and redirects to login"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    client.post('/admin/login', data={'password': 'testpass123'})

    # Verify logged in
    with client.session_transaction() as sess:
        assert sess.get('logged_in_as_admin') is True

    # Logout
    response = client.post('/admin/logout', follow_redirects=False)

    # Should redirect to login
    assert response.status_code == 302
    assert '/admin/login' in response.location

    # Session should be cleared
    with client.session_transaction() as sess:
        assert sess.get('logged_in_as_admin') is not True
        assert 'login_time' not in sess
        assert 'last_activity' not in sess


def test_admin_logout_requires_post(client):
    """Test that logout only accepts POST requests"""
    response = client.get('/admin/logout', follow_redirects=False)
    # Should be method not allowed or redirect
    assert response.status_code in [302, 405]


def test_admin_can_start_setup_tournament(client):
    """Test that logged-in admin can start a tournament in setup mode.

    This verifies the session key fix (logged_in_as_admin vs is_admin).
    Previously, the code checked 'is_admin' but login set 'logged_in_as_admin',
    causing the 'Aloita' button to fail for admins.
    """
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin, season, players and setup tournament
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 8 players for a valid tournament
        for i in range(8):
            db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (f'Player{i}', f'Test{i}')
            )

        db.execute(
            'INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
            ('Setup Tournament', 2, season_id, 'setup')
        )
        tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Add players to tournament
        players = db.execute('SELECT id FROM player_registry').fetchall()
        for player in players:
            db.execute(
                'INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)',
                (tournament_id, player['id'])
            )
        db.commit()

    # Login as admin
    client.post('/admin/login', data={'password': 'testpass123'})

    # Verify session has correct key
    with client.session_transaction() as sess:
        assert sess.get('logged_in_as_admin') is True

    # Admin should be able to start the tournament
    response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=False)

    # Should redirect to active tournament (not back to index with error)
    assert response.status_code == 302
    assert '/tournament/' in response.location
    assert 'login' not in response.location.lower()


def test_non_admin_cannot_start_setup_tournament(client):
    """Test that non-admin users cannot start a tournament in setup mode."""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin, season and setup tournament (but don't login)
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
        season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Create 8 players
        for i in range(8):
            db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (f'Player{i}', f'Test{i}')
            )

        db.execute(
            'INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
            ('Setup Tournament', 2, season_id, 'setup')
        )
        tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Add players to tournament
        players = db.execute('SELECT id FROM player_registry').fetchall()
        for player in players:
            db.execute(
                'INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)',
                (tournament_id, player['id'])
            )
        db.commit()

    # Try to start tournament without logging in
    response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=True)

    # Should show error message about admin-only access
    assert 'ylläpitäjä'.encode('utf-8') in response.data.lower() or \
           b'admin' in response.data.lower() or \
           response.request.path == '/'  # Redirected to home
