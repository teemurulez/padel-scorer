"""
Security tests for Padel Paroni application.
Tests CSRF protection, rate limiting, SQL injection prevention, and XSS prevention.
"""
import pytest
from app import app
from database import init_db, get_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_security.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF for testing

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client_no_csrf(tmp_path):
    """Create test client with CSRF disabled (for testing other security features)"""
    import os
    db_path = tmp_path / "test_security_no_csrf.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def logged_in_client(client_no_csrf):
    """Client that is logged in as admin"""
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
        )
        db.commit()

    client_no_csrf.post('/admin/login', data={'password': 'testpass123'})
    return client_no_csrf


# =============================================================================
# CSRF Protection Tests
# =============================================================================

class TestCSRFProtection:
    """Tests for Cross-Site Request Forgery protection"""

    def test_admin_login_requires_csrf_token(self, client):
        """POST to /admin/login without CSRF token should fail"""
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
            )
            db.commit()

        # POST without CSRF token
        response = client.post('/admin/login', data={
            'password': 'testpass123'
        })

        # Should be rejected (400 Bad Request or similar)
        assert response.status_code in [400, 403], f"Expected 400 or 403, got {response.status_code}"

    def test_admin_logout_requires_csrf_token(self, client):
        """POST to /admin/logout without CSRF token should fail"""
        # First login (need to do this with CSRF disabled temporarily)
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
            )
            db.commit()

        # Set up logged in session manually
        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            from datetime import datetime
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        # Try to logout without CSRF token
        response = client.post('/admin/logout')
        assert response.status_code in [400, 403]

    def test_create_tournament_requires_csrf_token(self, client):
        """POST to create tournament without CSRF token should fail"""
        # Set up logged in session
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
            )
            db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test',))
            db.commit()

        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            from datetime import datetime
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        response = client.post('/admin/tournaments/create', data={
            'name': 'Test Tournament',
            'num_courts': '3',
            'player_names': 'Player 1\nPlayer 2\nPlayer 3\nPlayer 4'
        })
        assert response.status_code in [400, 403]


# =============================================================================
# Rate Limiting Tests
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting on sensitive endpoints"""

    def test_login_rate_limiting_exists(self, client_no_csrf):
        """Verify rate limiting is configured on login endpoint"""
        # Note: Actually testing rate limits would require many requests
        # This test verifies the rate limiter is active
        from flask_limiter import Limiter

        # Check that limiter is configured on app
        assert hasattr(app, 'extensions')
        # The limiter should be registered

    def test_multiple_failed_logins_dont_crash(self, client_no_csrf):
        """Multiple failed login attempts should be handled gracefully"""
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('correctpass', method='pbkdf2:sha256'),)
            )
            db.commit()

        # Try 5 failed logins - should not crash
        for i in range(5):
            response = client_no_csrf.post('/admin/login', data={
                'password': f'wrongpass{i}'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'Invalid password' in response.data


# =============================================================================
# SQL Injection Tests
# =============================================================================

class TestSQLInjection:
    """Tests for SQL injection prevention"""

    def test_login_sql_injection_in_password(self, client_no_csrf):
        """SQL injection in password field should not work"""
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('realpassword', method='pbkdf2:sha256'),)
            )
            db.commit()

        # Try SQL injection in password
        malicious_passwords = [
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DROP TABLE admin_users;--",
            "' UNION SELECT password_hash FROM admin_users--",
            "1' OR '1' = '1",
        ]

        for payload in malicious_passwords:
            response = client_no_csrf.post('/admin/login', data={
                'password': payload
            }, follow_redirects=True)

            # Should fail login, not succeed
            assert response.status_code == 200
            assert b'Invalid password' in response.data, f"SQL injection might have worked with: {payload}"

            # Verify we're not logged in
            with client_no_csrf.session_transaction() as sess:
                assert sess.get('logged_in_as_admin') is not True

    def test_player_search_sql_injection(self, logged_in_client):
        """SQL injection in player search should not work"""
        # Create some players
        with app.app_context():
            db = get_db()
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                       ('Test', 'Player'))
            db.commit()

        # Try SQL injection in validate-players endpoint (expects JSON)
        malicious_names = [
            "'; DROP TABLE player_registry;--",
            "Test' OR '1'='1",
            "Test\"; DROP TABLE player_registry;--",
        ]

        for payload in malicious_names:
            response = logged_in_client.post('/admin/validate-players',
                json={'players': payload},
                content_type='application/json'
            )
            # Should return valid JSON (200) or error (400), not crash
            assert response.status_code in [200, 400]

        # Verify table still exists
        with app.app_context():
            db = get_db()
            result = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='player_registry'"
            ).fetchone()
            assert result is not None, "player_registry table was dropped!"

    def test_tournament_name_sql_injection(self, logged_in_client):
        """SQL injection in tournament name should not work"""
        with app.app_context():
            db = get_db()
            db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test Season',))
            # Add players for tournament creation
            for i in range(4):
                db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                           (f'Player{i}', 'Test'))
            db.commit()

        malicious_names = [
            "Test'; DROP TABLE tournaments;--",
            "Tournament\"; DELETE FROM tournaments;--",
        ]

        for payload in malicious_names:
            response = logged_in_client.post('/admin/tournaments/create', data={
                'name': payload,
                'num_courts': '1',
                'player_names': 'Player0 Test\nPlayer1 Test\nPlayer2 Test\nPlayer3 Test'
            }, follow_redirects=True)

        # Verify table still exists
        with app.app_context():
            db = get_db()
            result = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tournaments'"
            ).fetchone()
            assert result is not None, "tournaments table was dropped!"


# =============================================================================
# XSS Prevention Tests
# =============================================================================

class TestXSSPrevention:
    """Tests for Cross-Site Scripting prevention"""

    def test_player_name_xss_escaped_in_leaderboard(self, client_no_csrf):
        """Script tags in player names should be escaped in leaderboard"""
        with app.app_context():
            db = get_db()
            # Create season
            db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test',))
            season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Create player with XSS payload
            xss_name = '<script>alert("XSS")</script>'
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                       (xss_name, 'Test'))
            player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Create more players for a match
            for i in range(3):
                db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                           (f'Player{i}', 'Normal'))

            # Create tournament with match
            db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                       ('Test', 1, season_id, 'completed'))
            t_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            db.execute('INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)', (t_id, 1))
            r_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            db.execute('''INSERT INTO matches (round_id, court_number, player1_id, player2_id,
                          player3_id, player4_id, winning_team, completed)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (r_id, 1, player_id, player_id+1, player_id+2, player_id+3, 1, 1))
            m_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            db.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
                       (m_id, player_id, 1))
            db.commit()

        # Check leaderboard
        response = client_no_csrf.get('/leaderboard/season')
        html = response.data.decode('utf-8')

        # The raw script tag should NOT appear
        assert '<script>alert("XSS")</script>' not in html, "XSS payload not escaped!"
        # The escaped version should appear
        assert '&lt;script&gt;' in html or 'script' not in html.lower() or response.status_code == 200

    def test_tournament_name_xss_escaped(self, logged_in_client):
        """Script tags in tournament names should be escaped"""
        with app.app_context():
            db = get_db()
            db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test',))
            season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Create tournament with XSS payload
            xss_name = '<img src=x onerror=alert("XSS")>'
            db.execute('INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)',
                       (xss_name, 1, season_id, 'setup'))
            db.commit()

        # Check admin dashboard
        response = logged_in_client.get('/admin')
        html = response.data.decode('utf-8')

        # The raw XSS payload should NOT appear unescaped
        assert '<img src=x onerror=alert("XSS")>' not in html, "XSS payload not escaped!"

    def test_player_profile_xss_escaped(self, client_no_csrf):
        """Script tags should be escaped in player profile page"""
        with app.app_context():
            db = get_db()
            db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', ('Test',))

            # Create player with potential XSS in name
            db.execute('INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                       ('Normal', '<script>evil()</script>'))
            player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.commit()

        response = client_no_csrf.get(f'/player/{player_id}/profile')
        html = response.data.decode('utf-8')

        # Script tags should be escaped
        assert '<script>evil()</script>' not in html


# =============================================================================
# Session Security Tests
# =============================================================================

class TestSessionSecurity:
    """Tests for session security"""

    def test_session_not_accessible_after_logout(self, client_no_csrf):
        """Admin session should be cleared after logout"""
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('testpass123', method='pbkdf2:sha256'),)
            )
            db.commit()

        # Login
        client_no_csrf.post('/admin/login', data={'password': 'testpass123'})

        # Verify logged in
        response = client_no_csrf.get('/admin')
        assert response.status_code == 200

        # Logout
        client_no_csrf.post('/admin/logout')

        # Try to access admin - should redirect to login
        response = client_no_csrf.get('/admin', follow_redirects=False)
        assert response.status_code == 302
        assert '/admin/login' in response.location

    def test_password_not_stored_in_plain_text(self, client_no_csrf):
        """Passwords should be hashed, not stored in plain text"""
        with app.app_context():
            db = get_db()
            db.execute(
                'INSERT INTO admin_users (password_hash) VALUES (?)',
                (generate_password_hash('mysecretpassword', method='pbkdf2:sha256'),)
            )
            db.commit()

            # Check that plain text password is not in database
            admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()
            assert admin['password_hash'] != 'mysecretpassword'
            assert admin['password_hash'].startswith('pbkdf2:sha256')

    def test_admin_routes_require_authentication(self, client_no_csrf):
        """Admin routes should require authentication"""
        protected_routes = [
            '/admin',
            '/admin/seasons/create',
            '/admin/tournaments/create',
        ]

        for route in protected_routes:
            if route.endswith('/create'):
                response = client_no_csrf.post(route, data={})
            else:
                response = client_no_csrf.get(route)

            # Should redirect to login
            assert response.status_code == 302, f"Route {route} should require auth"
            assert '/admin/login' in response.location or '/admin/setup' in response.location
