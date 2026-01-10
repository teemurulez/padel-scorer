import pytest
import os
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_home.db"
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

def test_home_page_has_admin_dashboard_link(client):
    """Test that home page has link to admin dashboard"""
    response = client.get('/')
    assert 'Ylläpito'.encode('utf-8') in response.data  # Finnish: "Admin Dashboard"
    assert b'/admin' in response.data
