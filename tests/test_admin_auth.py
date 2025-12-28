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
    assert b'Admin Setup' in response.data
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
