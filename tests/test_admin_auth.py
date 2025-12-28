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
