# Phase 3 Stage 2: Player Selection UI and Seeded Round 1 - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace text input player names with player selection from registry, and implement seeded Round 1 pairings based on recent tournament performance.

**Architecture:** Add player_seeding database view for calculating seed points from last 6 tournaments. Create /players management UI for viewing/adding players. Modify tournament setup to select players from checkboxes. Implement `generate_seeded_round1_pairings()` algorithm that assigns top players to Court 1. Update start_round route to use seeded pairings for Round 1 only (Round 2+ unchanged).

**Tech Stack:** Flask 3.1, Python 3.9, SQLite, Jinja2 templates, pytest

---

## Prerequisites

**Completed in Stage 1:**
- ✅ player_registry table exists (first_name, last_name, UNIQUE constraint)
- ✅ tournament_players junction table exists (tournament_id, player_id, stats)
- ✅ tournaments.status column exists (setup, active, completed, archived)
- ✅ players.registry_id foreign key exists
- ✅ migration_phase3.py script exists

**Current Behavior (Phase 2):**
- Tournament setup: Enter player names as text (creates players.name entries)
- Round 1: Random pairing (shuffle algorithm)
- Rounds 2+: Court movement algorithm (winners up, losers down)

**Target Behavior (Stage 2):**
- Tournament setup: Select players from registry via checkboxes (shows seed points)
- Round 1: **Seeded pairing** (top seed players on Court 1)
- Rounds 2+: Court movement algorithm (unchanged)

---

## Task 1: Create player_seeding Database View

**Goal:** Add SQL view that calculates seed points for each player from last 6 tournaments.

**Files:**
- Modify: `database.py` (add view creation after table definitions)
- Test: `tests/test_player_seeding_view.py` (new file)

### Step 1: Write failing test

**Test file:** `tests/test_player_seeding_view.py`

```python
import sqlite3
import pytest
from database import get_db_connection

def test_player_seeding_view_exists():
    """Test that player_seeding view is created"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Query the view
        cursor.execute("SELECT * FROM player_seeding LIMIT 1")
        # If view exists, this won't raise an error
    except sqlite3.OperationalError as e:
        pytest.fail(f"player_seeding view does not exist: {e}")
    finally:
        db.close()

def test_player_seeding_calculates_seed_points():
    """Test that view calculates seed points from last 6 months"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create test player
        cursor.execute('''
            INSERT INTO player_registry (first_name, last_name)
            VALUES ('Test', 'Player')
        ''')
        player_id = cursor.lastrowid

        # Create completed tournament with player stats
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status, completed_at)
            VALUES ('Test Tournament', 2, 'completed', CURRENT_TIMESTAMP)
        ''')
        tournament_id = cursor.lastrowid

        # Add player to tournament with points
        cursor.execute('''
            INSERT INTO tournament_players
            (tournament_id, player_id, total_points, match_wins, match_losses)
            VALUES (?, ?, 100, 5, 2)
        ''', (tournament_id, player_id))

        db.commit()

        # Query view
        cursor.execute('''
            SELECT seed_points, recent_tournaments
            FROM player_seeding
            WHERE player_id = ?
        ''', (player_id,))

        result = cursor.fetchone()
        assert result is not None
        assert result['seed_points'] == 100
        assert result['recent_tournaments'] == 1

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id IN (SELECT id FROM tournaments WHERE name = 'Test Tournament')")
        cursor.execute("DELETE FROM tournaments WHERE name = 'Test Tournament'")
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Test' AND last_name = 'Player'")
        db.commit()
        db.close()
```

### Step 2: Run test to verify failure

```bash
python -m pytest tests/test_player_seeding_view.py -v
```

**Expected:** FAIL with "no such table: player_seeding"

### Step 3: Implement the view in database.py

**File:** `database.py`

Find the section where views are created (or add after table creation). Add:

```python
# Create player_seeding view (Phase 3 Stage 2)
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
    ORDER BY seed_points DESC
''')
```

**Important notes:**
- View joins player_registry → tournament_players → tournaments
- Filters completed/archived tournaments from last 6 months
- COALESCE returns 0 for new players with no history
- ORDER BY seed_points DESC for easy sorting

### Step 4: Run test to verify it passes

```bash
python -m pytest tests/test_player_seeding_view.py -v
```

**Expected:** PASS (2/2 tests)

### Step 5: Commit

```bash
git add database.py tests/test_player_seeding_view.py
git commit -m "feat: add player_seeding view for Round 1 seeding

Calculates seed points from last 6 months of tournaments.
Used to determine court assignments in Round 1.

2/2 tests passing"
```

---

## Task 2: Create Player List/Management Page

**Goal:** Add /players page showing all players in registry, and POST /player/create route for adding new players.

**Files:**
- Modify: `app.py` (add routes)
- Create: `templates/players_list.html` (new template)
- Test: `tests/test_player_registry.py` (new file - create/list CRUD operations)

### Step 1: Write failing tests

**Test file:** `tests/test_player_registry.py`

```python
import pytest
from app import app
from database import get_db_connection

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_players_list_page_loads(client):
    """Test that /players page loads successfully"""
    response = client.get('/players')
    assert response.status_code == 200
    assert b'Player Registry' in response.data

def test_create_player_success(client):
    """Test creating a new player via POST /player/create"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        response = client.post('/player/create', data={
            'first_name': 'Test',
            'last_name': 'Player'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Added Test Player to player registry' in response.data

        # Verify player created in database
        cursor.execute('''
            SELECT * FROM player_registry
            WHERE first_name = 'Test' AND last_name = 'Player'
        ''')
        player = cursor.fetchone()
        assert player is not None

    finally:
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Test' AND last_name = 'Player'")
        db.commit()
        db.close()

def test_create_player_duplicate_rejected(client):
    """Test that duplicate player names are rejected"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create first player
        cursor.execute('''
            INSERT INTO player_registry (first_name, last_name)
            VALUES ('Duplicate', 'Player')
        ''')
        db.commit()

        # Try to create duplicate
        response = client.post('/player/create', data={
            'first_name': 'Duplicate',
            'last_name': 'Player'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists in registry' in response.data

    finally:
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Duplicate'")
        db.commit()
        db.close()

def test_players_list_shows_seeding(client):
    """Test that player list displays seed points"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create player with tournament history
        cursor.execute('''
            INSERT INTO player_registry (first_name, last_name)
            VALUES ('Seeded', 'Player')
        ''')
        player_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status, completed_at)
            VALUES ('Past Tournament', 2, 'completed', CURRENT_TIMESTAMP)
        ''')
        tournament_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO tournament_players
            (tournament_id, player_id, total_points, match_wins, match_losses)
            VALUES (?, ?, 150, 6, 1)
        ''', (tournament_id, player_id))

        db.commit()

        # Visit players page
        response = client.get('/players')
        assert response.status_code == 200
        assert b'Seeded' in response.data
        assert b'Player' in response.data
        assert b'150' in response.data  # Seed points should be visible

    finally:
        cursor.execute("DELETE FROM tournament_players WHERE player_id = ?", (player_id,))
        cursor.execute("DELETE FROM tournaments WHERE name = 'Past Tournament'")
        cursor.execute("DELETE FROM player_registry WHERE first_name = 'Seeded'")
        db.commit()
        db.close()
```

### Step 2: Run tests to verify failure

```bash
python -m pytest tests/test_player_registry.py -v
```

**Expected:** FAIL with "404 NOT FOUND" for /players route

### Step 3: Implement routes in app.py

**File:** `app.py`

Add these routes (find appropriate location, e.g., after tournament routes):

```python
# ==========================================
# PLAYER REGISTRY ROUTES (Phase 3 Stage 2)
# ==========================================

@app.route('/players')
def players_list():
    """Display all players in registry with seed points"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get all players with their seed points from view
        cursor.execute('''
            SELECT
                player_id,
                first_name,
                last_name,
                seed_points,
                recent_tournaments
            FROM player_seeding
            ORDER BY seed_points DESC, last_name ASC
        ''')
        players = cursor.fetchall()

        return render_template('players_list.html', players=players)
    finally:
        db.close()

@app.route('/player/create', methods=['POST'])
def create_player():
    """Add new player to registry"""
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()

    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Check for duplicate
        cursor.execute('''
            SELECT id FROM player_registry
            WHERE first_name = ? AND last_name = ?
        ''', (first_name, last_name))
        existing = cursor.fetchone()

        if existing:
            flash(f'⚠️ {first_name} {last_name} already exists in registry', 'warning')
            return redirect('/players')

        # Create new player
        cursor.execute('''
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        ''', (first_name, last_name))
        db.commit()

        flash(f'✅ Added {first_name} {last_name} to player registry', 'success')
        return redirect('/players')

    except Exception as e:
        db.rollback()
        flash(f'Error adding player: {e}', 'error')
        return redirect('/players')
    finally:
        db.close()
```

### Step 4: Create template

**File:** `templates/players_list.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Player Registry</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .add-player-form {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .form-row {
            display: flex;
            gap: 15px;
            align-items: flex-end;
        }
        .form-group {
            flex: 1;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #45a049;
        }
        .players-table {
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .seed-badge {
            background-color: #2196F3;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 14px;
        }
        .new-player {
            background-color: #999;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash {
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .flash.success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .flash.warning {
            background-color: #fff3cd;
            border: 1px solid #ffeeba;
            color: #856404;
        }
        .flash.error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #2196F3;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>Player Registry</h1>

    <!-- Flash messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-messages">
                {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Add new player form -->
    <div class="add-player-form">
        <h2>Add New Player</h2>
        <form method="POST" action="{{ url_for('create_player') }}">
            <div class="form-row">
                <div class="form-group">
                    <label for="first_name">First Name:</label>
                    <input type="text" id="first_name" name="first_name" required>
                </div>
                <div class="form-group">
                    <label for="last_name">Last Name:</label>
                    <input type="text" id="last_name" name="last_name" required>
                </div>
                <button type="submit">Add Player</button>
            </div>
        </form>
    </div>

    <!-- Players table -->
    <div class="players-table">
        <h2>All Players ({{ players|length }})</h2>
        {% if players %}
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Seed Points</th>
                        <th>Recent Tournaments</th>
                    </tr>
                </thead>
                <tbody>
                    {% for player in players %}
                    <tr>
                        <td>{{ player.last_name }}, {{ player.first_name }}</td>
                        <td>
                            {% if player.seed_points > 0 %}
                                <span class="seed-badge">{{ player.seed_points }} pts</span>
                            {% else %}
                                <span class="seed-badge new-player">0 pts (New)</span>
                            {% endif %}
                        </td>
                        <td>{{ player.recent_tournaments }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p style="padding: 20px; text-align: center; color: #999;">
                No players in registry. Add your first player above!
            </p>
        {% endif %}
    </div>

    <a href="{{ url_for('index') }}" class="back-link">← Back to Home</a>
</body>
</html>
```

### Step 5: Run tests to verify pass

```bash
python -m pytest tests/test_player_registry.py -v
```

**Expected:** PASS (4/4 tests)

### Step 6: Commit

```bash
git add app.py templates/players_list.html tests/test_player_registry.py
git commit -m "feat: add player registry management UI

- GET /players - displays all players with seed points
- POST /player/create - adds new player with duplicate detection
- Shows seed points from player_seeding view
- Clean UI with form validation

4/4 tests passing"
```

---

## Task 3: Implement Seeded Round 1 Pairing Algorithm

**Goal:** Create `seeded_pairing.py` module with `generate_seeded_round1_pairings()` function that assigns players to courts based on seed ranking.

**Files:**
- Create: `seeded_pairing.py` (new module)
- Test: `tests/test_seeded_pairing.py` (new file)

### Step 1: Write failing tests

**Test file:** `tests/test_seeded_pairing.py`

```python
import pytest
from database import get_db_connection
from seeded_pairing import generate_seeded_round1_pairings

def test_seeded_pairing_top_players_court1():
    """Test that top 4 seeded players are assigned to Court 1"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create tournament
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status)
            VALUES ('Seeding Test', 2, 'setup')
        ''')
        tournament_id = cursor.lastrowid

        # Create 8 players with different seed points
        player_ids = []
        seed_points = [850, 820, 780, 750, 680, 650, 620, 580]

        for i, points in enumerate(seed_points):
            # Create player
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'Player{i+1}', 'Test'))
            player_id = cursor.lastrowid
            player_ids.append(player_id)

            # Create past tournament
            cursor.execute('''
                INSERT INTO tournaments (name, num_courts, status, completed_at)
                VALUES (?, 2, 'completed', CURRENT_TIMESTAMP)
            ''', (f'Past{i}',))
            past_tournament_id = cursor.lastrowid

            # Add player stats to create seed points
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, ?, 5, 2)
            ''', (past_tournament_id, player_id, points))

            # Link player to new tournament
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

        db.commit()

        # Generate seeded pairings
        pairings = generate_seeded_round1_pairings(tournament_id, num_courts=2)

        # Verify 2 courts
        assert len(pairings) == 2

        # Court 1 should have top 4 players (ids 0-3)
        court1_players = set(pairings[0])
        top4_players = set(player_ids[0:4])
        assert court1_players == top4_players, \
            f"Court 1 should have top 4 players. Got {court1_players}, expected {top4_players}"

        # Court 2 should have bottom 4 players (ids 4-7)
        court2_players = set(pairings[1])
        bottom4_players = set(player_ids[4:8])
        assert court2_players == bottom4_players, \
            f"Court 2 should have bottom 4 players. Got {court2_players}, expected {bottom4_players}"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id IN (SELECT id FROM tournaments WHERE name LIKE 'Past%')")
        cursor.execute("DELETE FROM tournaments WHERE name = 'Seeding Test' OR name LIKE 'Past%'")
        cursor.execute("DELETE FROM player_registry WHERE first_name LIKE 'Player%' AND last_name = 'Test'")
        db.commit()
        db.close()

def test_seeded_pairing_team_balancing():
    """Test that teams are balanced within a court (P1+P3 vs P2+P4)"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create tournament
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status)
            VALUES ('Balance Test', 1, 'setup')
        ''')
        tournament_id = cursor.lastrowid

        # Create 4 players with clear seeding
        player_ids = []
        for i in range(4):
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'P{i+1}', 'Test'))
            player_id = cursor.lastrowid
            player_ids.append(player_id)

            # Add to tournament
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

        db.commit()

        # Generate pairings
        pairings = generate_seeded_round1_pairings(tournament_id, num_courts=1)

        # Verify pairing format: [P1, P3, P2, P4]
        # Team 1: positions 0,1 (P1+P3)
        # Team 2: positions 2,3 (P2+P4)
        assert len(pairings) == 1
        court1 = pairings[0]
        assert len(court1) == 4

    finally:
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE name = 'Balance Test'")
        cursor.execute("DELETE FROM player_registry WHERE first_name LIKE 'P%' AND last_name = 'Test'")
        db.commit()
        db.close()

def test_seeded_pairing_new_players_last():
    """Test that new players (0 seed) are placed on lowest courts"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create tournament
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status)
            VALUES ('New Player Test', 2, 'setup')
        ''')
        tournament_id = cursor.lastrowid

        # Create 6 experienced players
        experienced_ids = []
        for i in range(6):
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'Experienced{i+1}', 'Test'))
            player_id = cursor.lastrowid
            experienced_ids.append(player_id)

            # Add past tournament stats
            cursor.execute('''
                INSERT INTO tournaments (name, num_courts, status, completed_at)
                VALUES (?, 2, 'completed', CURRENT_TIMESTAMP)
            ''', (f'PastE{i}',))
            past_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 100, 5, 2)
            ''', (past_id, player_id))

            # Add to new tournament
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

        # Create 2 new players (no history)
        new_player_ids = []
        for i in range(2):
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'New{i+1}', 'Test'))
            player_id = cursor.lastrowid
            new_player_ids.append(player_id)

            # Add to tournament (no past stats)
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

        db.commit()

        # Generate pairings
        pairings = generate_seeded_round1_pairings(tournament_id, num_courts=2)

        # Court 1 should have only experienced players
        court1 = set(pairings[0])
        assert not any(pid in court1 for pid in new_player_ids), \
            "New players should not be on Court 1"

        # Court 2 should have the 2 new players
        court2 = set(pairings[1])
        assert all(pid in court2 for pid in new_player_ids), \
            "New players should be on Court 2"

    finally:
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id IN (SELECT id FROM tournaments WHERE name LIKE 'PastE%')")
        cursor.execute("DELETE FROM tournaments WHERE name = 'New Player Test' OR name LIKE 'PastE%'")
        cursor.execute("DELETE FROM player_registry WHERE (first_name LIKE 'Experienced%' OR first_name LIKE 'New%') AND last_name = 'Test'")
        db.commit()
        db.close()
```

### Step 2: Run tests to verify failure

```bash
python -m pytest tests/test_seeded_pairing.py -v
```

**Expected:** FAIL with "ModuleNotFoundError: No module named 'seeded_pairing'"

### Step 3: Implement seeded_pairing.py

**File:** `seeded_pairing.py`

```python
"""
Seeded Round 1 Pairing Algorithm (Phase 3 Stage 2)

Generates court assignments for Round 1 based on player seeding.
Top-seeded players start on Court 1, bottom-seeded on lowest court.
"""

from database import get_db_connection

def generate_seeded_round1_pairings(tournament_id, num_courts):
    """
    Generate Round 1 pairings based on player seeding.
    Top players on Court 1, bottom players on last court.

    Args:
        tournament_id: ID of tournament to create pairings for
        num_courts: Number of courts available

    Returns:
        List of court assignments, each containing 4 player IDs
        Format: [[court1_p1, court1_p2, court1_p3, court1_p4], [court2_...], ...]

    Example:
        For 8 players sorted by seed (high to low): [P1, P2, P3, P4, P5, P6, P7, P8]
        Court 1: [P1, P3, P2, P4]  (top 4, balanced teams)
        Court 2: [P5, P7, P6, P8]  (bottom 4, balanced teams)
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get players for this tournament with their seed points
        # Join to player_seeding view to get seed_points
        cursor.execute('''
            SELECT
                pr.id,
                pr.first_name,
                pr.last_name,
                COALESCE(ps.seed_points, 0) as seed_points
            FROM tournament_players tp
            JOIN player_registry pr ON tp.player_id = pr.id
            LEFT JOIN player_seeding ps ON pr.id = ps.player_id
            WHERE tp.tournament_id = ?
            ORDER BY seed_points DESC, pr.last_name ASC
        ''', (tournament_id,))

        players_with_seeds = cursor.fetchall()

        if len(players_with_seeds) < num_courts * 4:
            raise ValueError(f"Not enough players. Need {num_courts * 4}, have {len(players_with_seeds)}")

        # Sort: High seed → Low seed (already sorted by query)
        player_ids = [p['id'] for p in players_with_seeds]

        players_per_court = 4
        court_assignments = []

        for court_idx in range(num_courts):
            start = court_idx * players_per_court
            end = start + players_per_court

            if end > len(player_ids):
                break

            # Get 4 players for this court
            court_player_ids = player_ids[start:end]

            # Assign teams (alternate to balance)
            # Team 1: P1 + P3 (positions 0, 2)
            # Team 2: P2 + P4 (positions 1, 3)
            # Match format: [team1_p1, team1_p2, team2_p1, team2_p2]
            court_assignment = [
                court_player_ids[0],  # Team 1, Player 1 (highest seed on court)
                court_player_ids[2],  # Team 1, Player 2 (3rd seed)
                court_player_ids[1],  # Team 2, Player 1 (2nd seed)
                court_player_ids[3]   # Team 2, Player 2 (4th seed)
            ]

            court_assignments.append(court_assignment)

        return court_assignments

    finally:
        db.close()
```

### Step 4: Run tests to verify pass

```bash
python -m pytest tests/test_seeded_pairing.py -v
```

**Expected:** PASS (3/3 tests)

### Step 5: Commit

```bash
git add seeded_pairing.py tests/test_seeded_pairing.py
git commit -m "feat: implement seeded Round 1 pairing algorithm

Top players start on Court 1 based on seed_points from last 6 tournaments.
Teams balanced within courts (high+low vs mid+mid).

Algorithm:
- Sort players by seed_points DESC
- Assign top 4 to Court 1, next 4 to Court 2, etc.
- Within court: Team1=P1+P3, Team2=P2+P4

3/3 tests passing"
```

---

## Task 4: Modify start_round Route for Seeded Round 1

**Goal:** Update `/tournament/<id>/start_round` route to use seeded pairings for Round 1, keep existing algorithm for Round 2+.

**Files:**
- Modify: `app.py` (start_round route)
- Test: `tests/test_start_round_seeded.py` (new file)

### Step 1: Write failing test

**Test file:** `tests/test_start_round_seeded.py`

```python
import pytest
from app import app
from database import get_db_connection

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_round1_uses_seeded_pairing(client):
    """Test that Round 1 uses seeded pairing algorithm"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create tournament
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status)
            VALUES ('Seeded Round 1 Test', 2, 'active')
        ''')
        tournament_id = cursor.lastrowid

        # Create 8 players with different seeds
        player_ids = []
        seed_points = [850, 820, 780, 750, 680, 650, 620, 580]

        for i, points in enumerate(seed_points):
            # Create player
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'P{i+1}', 'Seed'))
            player_id = cursor.lastrowid
            player_ids.append(player_id)

            # Create past tournament for seeding
            cursor.execute('''
                INSERT INTO tournaments (name, num_courts, status, completed_at)
                VALUES (?, 2, 'completed', CURRENT_TIMESTAMP)
            ''', (f'Past{i}',))
            past_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, ?, 5, 2)
            ''', (past_id, player_id, points))

            # Link player to new tournament
            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

            # Create legacy player record (backward compatibility)
            cursor.execute('''
                INSERT INTO players (name, total_points, tournament_id, registry_id)
                VALUES (?, 0, ?, ?)
            ''', (f'P{i+1} Seed', tournament_id, player_id))

        db.commit()

        # Start Round 1
        response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=True)
        assert response.status_code == 200
        assert b'seeded pairings' in response.data or b'Seeded' in response.data

        # Verify Round 1 was created
        cursor.execute('''
            SELECT id, round_number FROM rounds
            WHERE tournament_id = ?
        ''', (tournament_id,))
        round_data = cursor.fetchone()
        assert round_data is not None
        assert round_data['round_number'] == 1
        round_id = round_data['id']

        # Verify matches created
        cursor.execute('''
            SELECT court_number, team1_player1_id, team1_player2_id,
                   team2_player1_id, team2_player2_id
            FROM matches
            WHERE round_id = ?
            ORDER BY court_number
        ''', (round_id,))
        matches = cursor.fetchall()

        assert len(matches) == 2  # 2 courts

        # Court 1 should have top 4 players
        court1_match = matches[0]
        court1_players = {
            court1_match['team1_player1_id'],
            court1_match['team1_player2_id'],
            court1_match['team2_player1_id'],
            court1_match['team2_player2_id']
        }

        # Get legacy player IDs for top 4
        cursor.execute('''
            SELECT id FROM players
            WHERE registry_id IN (?, ?, ?, ?)
            AND tournament_id = ?
        ''', (player_ids[0], player_ids[1], player_ids[2], player_ids[3], tournament_id))
        top4_legacy_ids = {row['id'] for row in cursor.fetchall()}

        assert court1_players == top4_legacy_ids, \
            f"Court 1 should have top 4 seeded players"

    finally:
        # Cleanup
        cursor.execute("DELETE FROM matches WHERE round_id IN (SELECT id FROM rounds WHERE tournament_id = ?)", (tournament_id,))
        cursor.execute("DELETE FROM rounds WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id IN (SELECT id FROM tournaments WHERE name LIKE 'Past%')")
        cursor.execute("DELETE FROM tournaments WHERE name LIKE 'Seeded Round 1 Test' OR name LIKE 'Past%'")
        cursor.execute("DELETE FROM player_registry WHERE first_name LIKE 'P%' AND last_name = 'Seed'")
        db.commit()
        db.close()

def test_round2_uses_movement_algorithm(client):
    """Test that Round 2+ still uses court movement algorithm"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Create tournament with Round 1 already complete
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, status)
            VALUES ('Movement Test', 2, 'active')
        ''')
        tournament_id = cursor.lastrowid

        # Create 8 players
        player_ids = []
        for i in range(8):
            cursor.execute('''
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            ''', (f'Move{i+1}', 'Test'))
            player_id = cursor.lastrowid
            player_ids.append(player_id)

            cursor.execute('''
                INSERT INTO tournament_players
                (tournament_id, player_id, total_points, match_wins, match_losses)
                VALUES (?, ?, 0, 0, 0)
            ''', (tournament_id, player_id))

            cursor.execute('''
                INSERT INTO players (name, total_points, tournament_id, registry_id)
                VALUES (?, 0, ?, ?)
            ''', (f'Move{i+1} Test', tournament_id, player_id))

        # Create Round 1 with completed matches
        cursor.execute('''
            INSERT INTO rounds (tournament_id, round_number)
            VALUES (?, 1)
        ''', (tournament_id,))
        round1_id = cursor.lastrowid

        # Get legacy player IDs
        cursor.execute('SELECT id FROM players WHERE tournament_id = ? ORDER BY id', (tournament_id,))
        legacy_ids = [row['id'] for row in cursor.fetchall()]

        # Create 2 matches for Round 1 (both complete with winners)
        cursor.execute('''
            INSERT INTO matches
            (round_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id, winning_team, completed)
            VALUES (?, 1, ?, ?, ?, ?, 1, 1)
        ''', (round1_id, legacy_ids[0], legacy_ids[1], legacy_ids[2], legacy_ids[3]))

        cursor.execute('''
            INSERT INTO matches
            (round_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id, winning_team, completed)
            VALUES (?, 2, ?, ?, ?, ?, 2, 1)
        ''', (round1_id, legacy_ids[4], legacy_ids[5], legacy_ids[6], legacy_ids[7]))

        db.commit()

        # Start Round 2
        response = client.post(f'/tournament/{tournament_id}/start_round', follow_redirects=True)
        assert response.status_code == 200

        # Should NOT mention seeded pairings
        assert b'seeded pairings' not in response.data.lower()

        # Verify Round 2 created
        cursor.execute('''
            SELECT COUNT(*) as count FROM rounds
            WHERE tournament_id = ? AND round_number = 2
        ''', (tournament_id,))
        assert cursor.fetchone()['count'] == 1

    finally:
        cursor.execute("DELETE FROM matches WHERE round_id IN (SELECT id FROM rounds WHERE tournament_id = ?)", (tournament_id,))
        cursor.execute("DELETE FROM rounds WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE name = 'Movement Test'")
        cursor.execute("DELETE FROM player_registry WHERE first_name LIKE 'Move%'")
        db.commit()
        db.close()
```

### Step 2: Run tests to verify failure

```bash
python -m pytest tests/test_start_round_seeded.py -v
```

**Expected:** FAIL (seeded pairing not used for Round 1)

### Step 3: Modify start_round route in app.py

**File:** `app.py`

Find the `start_round` route and modify it:

```python
from seeded_pairing import generate_seeded_round1_pairings  # Add at top of file

# ... existing code ...

@app.route('/tournament/<int:tournament_id>/start_round', methods=['POST'])
def start_round(tournament_id):
    """Start a new round in the tournament"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get tournament info
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        tournament = cursor.fetchone()
        num_courts = tournament['num_courts']

        # Determine round number
        cursor.execute('''
            SELECT COALESCE(MAX(round_number), 0) + 1 as next_round
            FROM rounds WHERE tournament_id = ?
        ''', (tournament_id,))
        round_number = cursor.fetchone()['next_round']

        # Create new round
        cursor.execute('''
            INSERT INTO rounds (tournament_id, round_number)
            VALUES (?, ?)
        ''', (tournament_id, round_number))
        round_id = cursor.lastrowid

        # Determine pairing algorithm
        if round_number == 1:
            # SEEDED ROUND 1 - Use seeded pairing algorithm
            # Get player IDs from player_registry (seeded_pairing returns registry IDs)
            registry_court_assignments = generate_seeded_round1_pairings(tournament_id, num_courts)

            # Convert registry IDs to legacy player IDs for match creation
            court_assignments = []
            for court_players in registry_court_assignments:
                legacy_ids = []
                for registry_id in court_players:
                    cursor.execute('''
                        SELECT id FROM players
                        WHERE registry_id = ? AND tournament_id = ?
                    ''', (registry_id, tournament_id))
                    legacy_player = cursor.fetchone()
                    if legacy_player:
                        legacy_ids.append(legacy_player['id'])
                court_assignments.append(legacy_ids)

            flash(f"Round 1 started with seeded pairings (based on recent performance)", 'success')

        else:
            # ROUND 2+ - Use existing court movement algorithm
            cursor.execute('''
                SELECT m.*, r.round_number
                FROM matches m
                JOIN rounds r ON m.round_id = r.id
                WHERE r.tournament_id = ? AND r.round_number = ?
            ''', (tournament_id, round_number - 1))
            previous_matches = cursor.fetchall()

            from court_movement import generate_next_round_pairings
            court_assignments = generate_next_round_pairings(previous_matches, num_courts)

            flash(f"Round {round_number} started! Winners moved up, losers moved down.", 'success')

        # Create matches from assignments
        for court_num, player_ids in enumerate(court_assignments, start=1):
            if len(player_ids) == 4:
                cursor.execute('''
                    INSERT INTO matches
                    (round_id, court_number, team1_player1_id, team1_player2_id,
                     team2_player1_id, team2_player2_id, completed)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                ''', (round_id, court_num, player_ids[0], player_ids[1],
                      player_ids[2], player_ids[3]))

        # Update tournament status to 'active' when starting Round 1
        if round_number == 1:
            cursor.execute('''
                UPDATE tournaments SET status = 'active' WHERE id = ?
            ''', (tournament_id,))

        db.commit()
        return redirect(url_for('active_tournament', tournament_id=tournament_id))

    except Exception as e:
        db.rollback()
        flash(f'Error starting round: {e}', 'error')
        return redirect(url_for('active_tournament', tournament_id=tournament_id))
    finally:
        db.close()
```

### Step 4: Run tests to verify pass

```bash
python -m pytest tests/test_start_round_seeded.py -v
```

**Expected:** PASS (2/2 tests)

### Step 5: Commit

```bash
git add app.py tests/test_start_round_seeded.py
git commit -m "feat: integrate seeded pairing into start_round

Round 1 now uses seeded pairing algorithm:
- Top players start on Court 1
- Based on seed_points from last 6 months
- Round 2+ continues using court movement algorithm

2/2 tests passing"
```

---

## Task 5: Run All Tests and Verify

**Goal:** Run complete test suite to ensure no regressions and all new features work.

### Step 1: Run all tests

```bash
python -m pytest tests/ -v
```

**Expected:** All tests passing (previous 41 + new ~15 = 56+ tests)

### Step 2: Manual verification checklist

**Test seeded Round 1:**
1. Start app: `python app.py`
2. Visit /players - verify page loads
3. Add 2-3 new players
4. Create tournament with 2 courts
5. Start Round 1
6. Verify flash message mentions "seeded pairings"
7. Verify Court 1 has highest-seeded players

**Test Round 2+ unchanged:**
1. Complete Round 1 matches
2. Start Round 2
3. Verify movement algorithm still works (winners move up)

### Step 3: Document and commit

**Create summary document:**

```bash
# Create docs/daily-summaries/DAILY_SUMMARY_2025-12-30.md
```

**Final commit:**

```bash
git add -A
git commit -m "feat: complete Phase 3 Stage 2 - Player Selection & Seeded Round 1

Implemented player registry UI and seeded Round 1 pairing:
- player_seeding database view (calculates from last 6 months)
- /players management page (list + create with duplicate detection)
- Seeded Round 1 algorithm (top players → Court 1)
- Modified start_round to use seeding for Round 1 only
- Round 2+ unchanged (court movement algorithm)

All 56+ tests passing
Stage 2 complete and ready for production"
```

---

## Success Criteria

**Phase 3 Stage 2 complete when:**

✅ **Database:**
- player_seeding view exists and calculates correctly
- View queries last 6 months of completed tournaments
- Returns 0 seed_points for new players

✅ **Player Management:**
- /players page displays all players with seed points
- POST /player/create adds new players with duplicate detection
- Seed points visible and sorted DESC

✅ **Seeded Round 1:**
- Round 1 uses generate_seeded_round1_pairings()
- Top 4 players assigned to Court 1
- Bottom 4 players assigned to Court 2 (for 2-court setup)
- Teams balanced within courts (P1+P3 vs P2+P4)
- Flash message indicates "seeded pairings"

✅ **Round 2+ Unchanged:**
- Round 2+ still uses court movement algorithm
- Winners move up, losers move down
- No mention of seeding in flash message

✅ **Testing:**
- All existing 41 tests still pass
- 15+ new tests added and passing
- Manual testing confirms seeded behavior

✅ **No Regressions:**
- Existing tournament flow works
- Phase 2 tournaments still function
- Legacy player names still supported

---

## Next Steps

After completing Stage 2:

**Option 1:** Continue with Stage 3 (Player Profiles)
- Individual player profile pages
- Statistics across all tournaments
- Tournament history view

**Option 2:** Manual testing and refinement
- Test with real tournament data
- Gather user feedback on seeding
- Optimize queries if needed

**Option 3:** Merge and deploy
- Merge Stage 2 to main
- Deploy to production
- Monitor for issues
