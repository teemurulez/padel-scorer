# Admin Dashboard Phase 1: Foundation & Authentication - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build password-protected admin dashboard with first-run setup, login, session management, and empty tabbed interface.

**Architecture:** Simple password authentication with session-based auth, 30-minute timeout, first-run setup flow, and tabbed dashboard shell ready for future phases.

**Tech Stack:** Flask, Flask sessions, werkzeug.security (password hashing), SQLite, Jinja2 templates

---

## Task 1: Database Schema - admin_users Table

**Files:**
- Modify: `database.py` (add admin_users table to init_db function)
- Test: `tests/test_admin_auth.py` (new file)

### Step 1: Write failing test for admin_users table existence

**Create:** `tests/test_admin_auth.py`

```python
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
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_users_table_exists -v`

**Expected:** FAIL - table does not exist

### Step 3: Add admin_users table to database.py

**Modify:** `database.py` - Add after the scores table creation (around line 100)

```python
    # Create admin_users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
```

### Step 4: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** 2 tests PASS

### Step 5: Commit

```bash
git add database.py tests/test_admin_auth.py
git commit -m "feat: add admin_users table to database schema

- Create admin_users table with password_hash, timestamps
- Add comprehensive tests for table existence and schema
- Part of Phase 1: Foundation & Authentication

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: First-Run Setup - GET Route

**Files:**
- Modify: `app.py` (add /admin/setup GET route)
- Create: `templates/admin_setup.html`
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for setup page access

**Add to:** `tests/test_admin_auth.py`

```python
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
            (generate_password_hash('testpass123'),)
        )
        db.commit()

    response = client.get('/admin/setup')
    assert response.status_code == 302
    assert '/admin/login' in response.location
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_setup_page_loads_when_no_admin_exists -v`

**Expected:** FAIL - route does not exist (404)

### Step 3: Create admin setup template

**Create:** `templates/admin_setup.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Setup</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        body {
            background-color: #000;
            color: #fff;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .setup-container {
            background-color: #1a1a1a;
            border: 2px solid #FFD700;
            border-radius: 8px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #FFD700;
            margin-top: 0;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #FFD700;
            font-weight: bold;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #FFD700;
            background-color: #000;
            color: #fff;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #fff;
            box-shadow: 0 0 5px #FFD700;
        }
        .btn-primary {
            width: 100%;
            padding: 12px;
            background-color: #FFD700;
            color: #000;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #FFC700;
        }
        .help-text {
            color: #999;
            font-size: 14px;
            margin-top: 5px;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-error {
            background-color: #DC2626;
            color: #fff;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="setup-container">
        <h1>🔒 Admin Setup</h1>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-error">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <p style="color: #999; text-align: center; margin-bottom: 30px;">
            Create your admin password to secure the admin dashboard.
        </p>

        <form method="POST" action="/admin/setup">
            <div class="form-group">
                <label for="password">Password</label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    required
                    minlength="8"
                    placeholder="Enter password (min 8 characters)"
                >
                <div class="help-text">Minimum 8 characters required</div>
            </div>

            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input
                    type="password"
                    id="confirm_password"
                    name="confirm_password"
                    required
                    minlength="8"
                    placeholder="Confirm password"
                >
            </div>

            <button type="submit" class="btn-primary">Create Admin Account</button>
        </form>
    </div>
</body>
</html>
```

### Step 4: Add /admin/setup GET route to app.py

**Add to:** `app.py` (add near the end, before `if __name__ == '__main__':`)

```python
# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin/setup', methods=['GET'])
def admin_setup():
    """First-run admin setup page"""
    db = get_db()

    # Check if admin already exists
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if admin:
        return redirect('/admin/login')

    return render_template('admin_setup.html')
```

### Step 5: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 6: Commit

```bash
git add app.py templates/admin_setup.html tests/test_admin_auth.py
git commit -m "feat: add admin setup GET route and template

- GET /admin/setup shows setup form when no admin exists
- Redirects to login if admin already exists
- Black/yellow styled setup page with password validation
- Tests for both scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: First-Run Setup - POST Route

**Files:**
- Modify: `app.py` (add /admin/setup POST route)
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for setup POST

**Add to:** `tests/test_admin_auth.py`

```python
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
            (generate_password_hash('existing'),)
        )
        db.commit()

    response = client.post('/admin/setup', data={
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    }, follow_redirects=False)

    # Should redirect to login
    assert response.status_code == 302
    assert '/admin/login' in response.location
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_setup_post_creates_admin_user -v`

**Expected:** FAIL - POST route does not exist (405 Method Not Allowed)

### Step 3: Add POST handler to /admin/setup route

**Modify:** `app.py` - Update the admin_setup route

```python
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    """First-run admin setup page"""
    db = get_db()

    # Check if admin already exists
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if admin:
        return redirect('/admin/login')

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return render_template('admin_setup.html')

        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('admin_setup.html')

        # Create admin user
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (password_hash,)
        )
        db.commit()

        flash('Admin account created successfully! Please log in.')
        return redirect('/admin/login')

    return render_template('admin_setup.html')
```

### Step 4: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 5: Commit

```bash
git add app.py tests/test_admin_auth.py
git commit -m "feat: add admin setup POST route with validation

- POST /admin/setup creates hashed admin password
- Validates password length (min 8 chars)
- Validates password confirmation match
- Prevents creation if admin already exists
- Comprehensive test coverage for all scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Login Page - GET Route

**Files:**
- Modify: `app.py` (add /admin/login GET route)
- Create: `templates/admin_login.html`
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for login page

**Add to:** `tests/test_admin_auth.py`

```python
def test_admin_login_page_loads(client):
    """Test that /admin/login loads"""
    response = client.get('/admin/login')
    assert response.status_code == 200
    assert b'Admin Login' in response.data
    assert b'password' in response.data.lower()


def test_admin_login_redirects_to_setup_when_no_admin(client):
    """Test that /admin/login redirects to setup when no admin exists"""
    response = client.get('/admin/login')
    assert response.status_code == 302
    assert '/admin/setup' in response.location
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_login_page_loads -v`

**Expected:** FAIL - route does not exist (404)

### Step 3: Create admin login template

**Create:** `templates/admin_login.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        body {
            background-color: #000;
            color: #fff;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .login-container {
            background-color: #1a1a1a;
            border: 2px solid #FFD700;
            border-radius: 8px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #FFD700;
            margin-top: 0;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #FFD700;
            font-weight: bold;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #FFD700;
            background-color: #000;
            color: #fff;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #fff;
            box-shadow: 0 0 5px #FFD700;
        }
        .btn-primary {
            width: 100%;
            padding: 12px;
            background-color: #FFD700;
            color: #000;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #FFC700;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-error {
            background-color: #DC2626;
            color: #fff;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .flash-success {
            background-color: #16A34A;
            color: #fff;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .back-link {
            text-align: center;
            margin-top: 20px;
        }
        .back-link a {
            color: #FFD700;
            text-decoration: none;
        }
        .back-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔒 Admin Login</h1>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        {% if 'success' in message.lower() or 'created' in message.lower() %}
                            <div class="flash-success">{{ message }}</div>
                        {% else %}
                            <div class="flash-error">{{ message }}</div>
                        {% endif %}
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <form method="POST" action="/admin/login">
            <div class="form-group">
                <label for="password">Password</label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    required
                    placeholder="Enter admin password"
                    autofocus
                >
            </div>

            <button type="submit" class="btn-primary">Login</button>
        </form>

        <div class="back-link">
            <a href="/">← Back to Home</a>
        </div>
    </div>
</body>
</html>
```

### Step 4: Add /admin/login GET route to app.py

**Add to:** `app.py` (after admin_setup route)

```python
@app.route('/admin/login', methods=['GET'])
def admin_login():
    """Admin login page"""
    db = get_db()

    # Check if admin exists, redirect to setup if not
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if not admin:
        return redirect('/admin/setup')

    return render_template('admin_login.html')
```

### Step 5: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 6: Commit

```bash
git add app.py templates/admin_login.html tests/test_admin_auth.py
git commit -m "feat: add admin login GET route and template

- GET /admin/login shows login form
- Redirects to setup if no admin exists
- Black/yellow styled login page
- Tests for both scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Login - POST Route with Session

**Files:**
- Modify: `app.py` (add /admin/login POST route with session)
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for login POST

**Add to:** `tests/test_admin_auth.py`

```python
def test_admin_login_post_success(client):
    """Test successful admin login"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin user
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123'),)
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
            (generate_password_hash('testpass123'),)
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
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_login_post_success -v`

**Expected:** FAIL - POST route does not exist (405 Method Not Allowed)

### Step 3: Add POST handler to /admin/login route

**Modify:** `app.py` - Update the admin_login route

```python
from datetime import datetime

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    db = get_db()

    # Check if admin exists, redirect to setup if not
    admin = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
    if not admin:
        return redirect('/admin/setup')

    if request.method == 'POST':
        password = request.form.get('password', '')

        # Get admin password hash
        admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()

        if admin and check_password_hash(admin['password_hash'], password):
            # Set session
            session['logged_in_as_admin'] = True
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            return redirect('/admin')
        else:
            flash('Invalid password')
            return render_template('admin_login.html')

    return render_template('admin_login.html')
```

### Step 4: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 5: Commit

```bash
git add app.py tests/test_admin_auth.py
git commit -m "feat: add admin login POST route with session management

- POST /admin/login validates password and creates session
- Sets logged_in_as_admin, login_time, last_activity in session
- Redirects to /admin on success
- Shows error flash on failure
- Comprehensive test coverage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Session Middleware with 30-Minute Timeout

**Files:**
- Modify: `app.py` (add before_request middleware)
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for session middleware

**Add to:** `tests/test_admin_auth.py`

```python
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
            (generate_password_hash('testpass123'),)
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
            (generate_password_hash('testpass123'),)
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
    assert b'Session expired' in response.data or b'Admin Login' in response.data


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
            (generate_password_hash('testpass123'),)
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
            (generate_password_hash('test'),)
        )
        db.commit()

    response = client.get('/admin/login')
    assert response.status_code == 200
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_dashboard_requires_login -v`

**Expected:** FAIL - /admin route doesn't exist yet, but test framework is ready

### Step 3: Add session middleware to app.py

**Add to:** `app.py` (before any routes, after app initialization)

```python
from datetime import timedelta

@app.before_request
def check_admin_session():
    """Check admin authentication and session timeout before each request"""
    # Only check for admin routes (except login and setup)
    if request.path.startswith('/admin') and request.path not in ['/admin/login', '/admin/setup']:
        # Check if logged in
        if not session.get('logged_in_as_admin'):
            return redirect('/admin/login')

        # Check 30-minute timeout
        last_activity_str = session.get('last_activity')
        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str)
            if datetime.now() - last_activity > timedelta(minutes=30):
                session.clear()
                flash('Session expired. Please log in again.')
                return redirect('/admin/login')

        # Update last activity
        session['last_activity'] = datetime.now().isoformat()
```

### Step 4: Create minimal /admin route for testing

**Add to:** `app.py` (after login route)

```python
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page"""
    # This will be expanded in next task
    return "Admin Dashboard (placeholder)"
```

### Step 5: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 6: Commit

```bash
git add app.py tests/test_admin_auth.py
git commit -m "feat: add session middleware with 30-minute timeout

- Add before_request middleware for admin route protection
- Check authentication for all /admin/* routes (except login/setup)
- Implement 30-minute inactivity timeout
- Auto-clear session and redirect to login on timeout
- Update last_activity on each request
- Add placeholder /admin route
- Comprehensive test coverage for all scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Admin Dashboard Shell with Tabbed Interface

**Files:**
- Modify: `app.py` (update /admin route)
- Create: `templates/admin_dashboard.html`
- Create: `static/css/admin.css`
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for admin dashboard

**Add to:** `tests/test_admin_auth.py`

```python
def test_admin_dashboard_shows_tabs(client):
    """Test that admin dashboard shows all four tabs"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123'),)
        )
        db.commit()

    client.post('/admin/login', data={'password': 'testpass123'})

    # Access admin dashboard
    response = client.get('/admin')
    assert response.status_code == 200
    assert b'Seasons' in response.data
    assert b'Points' in response.data
    assert b'Players' in response.data
    assert b'Data' in response.data
    assert b'Logout' in response.data


def test_admin_dashboard_has_logo_placeholder(client):
    """Test that admin dashboard has logo placeholder"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123'),)
        )
        db.commit()

    client.post('/admin/login', data={'password': 'testpass123'})

    response = client.get('/admin')
    assert response.status_code == 200
    assert b'ADMIN DASHBOARD' in response.data or b'[LOGO]' in response.data
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_dashboard_shows_tabs -v`

**Expected:** FAIL - tabs not present in placeholder response

### Step 3: Create admin dashboard CSS

**Create:** `static/css/admin.css`

```css
/* Admin Dashboard Styles - Black & Yellow Theme */

/* Reset and base styles */
.admin-body {
    background-color: #000;
    color: #fff;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    min-height: 100vh;
}

/* Header */
.admin-header {
    background-color: #000;
    border-bottom: 3px solid #FFD700;
    padding: 20px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.admin-header h1 {
    color: #FFD700;
    margin: 0;
    font-size: 24px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.logo-placeholder {
    width: 40px;
    height: 40px;
    background-color: #FFD700;
    border-radius: 4px;
    display: inline-block;
}

.logout-btn {
    background-color: #DC2626;
    color: #fff;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    transition: background-color 0.3s;
}

.logout-btn:hover {
    background-color: #B91C1C;
}

/* Tab navigation */
.tab-navigation {
    background-color: #1a1a1a;
    border-bottom: 2px solid #FFD700;
    padding: 0;
    display: flex;
}

.tab-button {
    background-color: #1a1a1a;
    color: #999;
    border: none;
    padding: 15px 30px;
    cursor: pointer;
    font-size: 16px;
    font-weight: bold;
    transition: all 0.3s;
    border-bottom: 3px solid transparent;
}

.tab-button:hover {
    color: #FFD700;
    background-color: #2a2a2a;
}

.tab-button.active {
    color: #FFD700;
    background-color: #000;
    border-bottom-color: #FFD700;
}

/* Tab content */
.tab-content-container {
    padding: 40px;
}

.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

.tab-content h2 {
    color: #FFD700;
    margin-top: 0;
    margin-bottom: 20px;
}

.tab-content p {
    color: #999;
    line-height: 1.6;
}

/* Placeholder content */
.coming-soon {
    background-color: #1a1a1a;
    border: 2px dashed #FFD700;
    border-radius: 8px;
    padding: 40px;
    text-align: center;
}

.coming-soon h3 {
    color: #FFD700;
    margin-top: 0;
}

.coming-soon p {
    color: #999;
}

/* Flash messages */
.flash-messages {
    padding: 0 40px;
    margin-top: 20px;
}

.flash-success {
    background-color: #16A34A;
    color: #fff;
    padding: 15px;
    border-radius: 4px;
    margin-bottom: 10px;
}

.flash-error {
    background-color: #DC2626;
    color: #fff;
    padding: 15px;
    border-radius: 4px;
    margin-bottom: 10px;
}

/* Responsive */
@media (max-width: 768px) {
    .admin-header {
        flex-direction: column;
        gap: 15px;
        padding: 20px;
    }

    .tab-navigation {
        flex-wrap: wrap;
    }

    .tab-button {
        flex: 1 1 50%;
        min-width: 120px;
    }

    .tab-content-container {
        padding: 20px;
    }
}
```

### Step 4: Create admin dashboard template

**Create:** `templates/admin_dashboard.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
</head>
<body class="admin-body">
    <!-- Header -->
    <header class="admin-header">
        <h1>
            <span class="logo-placeholder"></span>
            ADMIN DASHBOARD 🔒
        </h1>
        <form method="POST" action="/admin/logout" style="margin: 0;">
            <button type="submit" class="logout-btn">Logout</button>
        </form>
    </header>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <div class="flash-messages">
                {% for message in messages %}
                    {% if 'success' in message.lower() %}
                        <div class="flash-success">{{ message }}</div>
                    {% else %}
                        <div class="flash-error">{{ message }}</div>
                    {% endif %}
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Tab Navigation -->
    <nav class="tab-navigation">
        <button class="tab-button active" data-tab="seasons">Seasons</button>
        <button class="tab-button" data-tab="points">Points</button>
        <button class="tab-button" data-tab="players">Players</button>
        <button class="tab-button" data-tab="data">Data</button>
    </nav>

    <!-- Tab Content Container -->
    <div class="tab-content-container">
        <!-- Seasons Tab -->
        <div id="seasons-tab" class="tab-content active">
            <h2>Season Management</h2>
            <div class="coming-soon">
                <h3>🏆 Coming in Phase 2</h3>
                <p>
                    Season management features will include:
                    <br>• Create custom-named seasons
                    <br>• End current season
                    <br>• Reactivate archived seasons
                    <br>• Delete seasons with cascade
                </p>
            </div>
        </div>

        <!-- Points Tab -->
        <div id="points-tab" class="tab-content">
            <h2>Point Editing</h2>
            <div class="coming-soon">
                <h3>📊 Coming in Phase 4</h3>
                <p>
                    Point editing features will include:
                    <br>• Edit match results (winner, teams, court)
                    <br>• Manual point overrides for special cases
                    <br>• Automatic point recalculation
                    <br>• Audit trail of changes
                </p>
            </div>
        </div>

        <!-- Players Tab -->
        <div id="players-tab" class="tab-content">
            <h2>Player Registry Management</h2>
            <div class="coming-soon">
                <h3>👥 Coming in Phase 3</h3>
                <p>
                    Player management features will include:
                    <br>• Add new players
                    <br>• Edit player names
                    <br>• Delete players (with cascade warnings)
                    <br>• Search and filter players
                </p>
            </div>
        </div>

        <!-- Data Tab -->
        <div id="data-tab" class="tab-content">
            <h2>Data Cleanup</h2>
            <div class="coming-soon">
                <h3>🗑️ Coming in Phase 5</h3>
                <p>
                    Data cleanup features will include:
                    <br>• Delete specific tournaments
                    <br>• Delete specific seasons
                    <br>• Clear all statistics
                    <br>• Clear all data (with confirmation)
                </p>
            </div>
        </div>
    </div>

    <!-- Tab Switching JavaScript -->
    <script>
        // Tab switching logic
        document.addEventListener('DOMContentLoaded', function() {
            const tabButtons = document.querySelectorAll('.tab-button');
            const tabContents = document.querySelectorAll('.tab-content');

            tabButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const targetTab = this.getAttribute('data-tab');

                    // Remove active class from all buttons and contents
                    tabButtons.forEach(btn => btn.classList.remove('active'));
                    tabContents.forEach(content => content.classList.remove('active'));

                    // Add active class to clicked button and corresponding content
                    this.classList.add('active');
                    document.getElementById(targetTab + '-tab').classList.add('active');
                });
            });
        });
    </script>
</body>
</html>
```

### Step 5: Update /admin route in app.py

**Modify:** `app.py` - Replace the placeholder admin_dashboard route

```python
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page"""
    return render_template('admin_dashboard.html')
```

### Step 6: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 7: Commit

```bash
git add app.py templates/admin_dashboard.html static/css/admin.css tests/test_admin_auth.py
git commit -m "feat: add admin dashboard shell with tabbed interface

- Create admin dashboard with 4 tabs (Seasons, Points, Players, Data)
- Black/yellow brand colors throughout
- Logo placeholder in header
- Logout button in header
- JavaScript tab switching
- Placeholder content for future phases
- Comprehensive admin CSS styling
- Tests for dashboard access and content

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Logout Functionality

**Files:**
- Modify: `app.py` (add /admin/logout route)
- Test: `tests/test_admin_auth.py`

### Step 1: Write failing test for logout

**Add to:** `tests/test_admin_auth.py`

```python
def test_admin_logout_clears_session(client):
    """Test that logout clears session and redirects to login"""
    from database import get_db
    from werkzeug.security import generate_password_hash

    # Create admin and login
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO admin_users (password_hash) VALUES (?)',
            (generate_password_hash('testpass123'),)
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
```

### Step 2: Run test to verify it fails

**Run:** `pytest tests/test_admin_auth.py::test_admin_logout_clears_session -v`

**Expected:** FAIL - route does not exist (404)

### Step 3: Add /admin/logout route to app.py

**Add to:** `app.py` (after admin_dashboard route)

```python
@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Logout and clear admin session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect('/admin/login')
```

### Step 4: Run tests to verify they pass

**Run:** `pytest tests/test_admin_auth.py -v`

**Expected:** All tests PASS

### Step 5: Commit

```bash
git add app.py tests/test_admin_auth.py
git commit -m "feat: add admin logout functionality

- POST /admin/logout clears session and redirects to login
- Complete session cleanup (all session variables removed)
- Success flash message on logout
- Tests for logout flow and POST-only enforcement

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Integration Testing & Manual Verification

**Files:**
- Test: Manual testing checklist

### Step 1: Run full test suite

**Run:** `pytest -v`

**Expected:** All tests PASS (should be 46 existing + new admin auth tests)

### Step 2: Manual testing checklist

**Start the app:**
```bash
python app.py
```

**Test Flow:**

1. **First-Run Setup:**
   - Navigate to `http://localhost:5001/admin`
   - Should redirect to `/admin/setup`
   - Create admin password (min 8 chars)
   - Should redirect to `/admin/login` with success message

2. **Login:**
   - Enter correct password → should access dashboard
   - Enter wrong password → should show error
   - Verify black/yellow styling

3. **Dashboard:**
   - Verify 4 tabs visible: Seasons, Points, Players, Data
   - Click each tab → content should switch
   - Verify logo placeholder and "ADMIN DASHBOARD 🔒" title
   - Verify logout button present

4. **Session Timeout:**
   - Login successfully
   - Wait 30 minutes OR manually set last_activity in session
   - Try to access `/admin`
   - Should redirect to login with "Session expired" message

5. **Logout:**
   - Click logout button
   - Should redirect to login page
   - Try to access `/admin` → should redirect to login

6. **Already Setup:**
   - Try to access `/admin/setup` after admin exists
   - Should redirect to `/admin/login`

### Step 3: Document any issues found

If issues found, create new tasks and fix before final commit.

### Step 4: Final commit

```bash
git add -A
git commit -m "test: verify Phase 1 integration and manual testing

Complete Phase 1: Foundation & Authentication
- All automated tests passing
- Manual testing completed
- First-run setup flow verified
- Login/logout flow verified
- Session timeout verified
- Dashboard shell verified

Ready for Phase 2 implementation.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 1 Complete! 🎉

**Deliverables:**
- ✅ admin_users table in database
- ✅ First-run setup page (GET/POST /admin/setup)
- ✅ Login page (GET/POST /admin/login)
- ✅ Session middleware with 30-minute timeout
- ✅ Admin dashboard shell with 4 tabs
- ✅ Logout functionality
- ✅ Black/yellow brand styling
- ✅ Comprehensive test coverage

**Next Steps:**
- Phase 2: Season Management (separate implementation plan)
- Phase 3: Player Registry Management
- Phase 4: Point Editing
- Phase 5: Data Cleanup & Polish

**Files Modified:**
- `database.py` - Added admin_users table
- `app.py` - Added admin routes and middleware
- `templates/admin_setup.html` - First-run setup page
- `templates/admin_login.html` - Login page
- `templates/admin_dashboard.html` - Main dashboard with tabs
- `static/css/admin.css` - Admin dashboard styling
- `tests/test_admin_auth.py` - Comprehensive auth tests

**Estimated Time:** Each task should take 2-5 minutes, total ~45-60 minutes for Phase 1
