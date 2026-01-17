# Admin Tournament Edit UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve tournament editing UX with full-screen edit mode, player name validation, smart pairing preservation, and change history.

**Architecture:** New dedicated edit page (`/admin/tournaments/<id>/edit`) replaces inline editing. Player validation via AJAX endpoint with fuzzy matching against registry. Pairings stored with NULL for removed players, unassigned pool for new players. Edit history logged to new table.

**Tech Stack:** Flask, SQLite, Jinja2, vanilla JavaScript, difflib for fuzzy matching

---

## Task 1: Create Tournament Edit History Table

**Files:**
- Modify: `database.py:253-266`
- Test: `tests/test_edit_history_schema.py`

**Step 1: Write the failing test**

Create `tests/test_edit_history_schema.py`:

```python
import pytest
import os
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_history_schema.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_tournament_edit_history_table_exists(client):
    """Test that tournament_edit_history table exists with correct schema"""
    from database import get_db
    with app.app_context():
        db = get_db()

        # Check table exists
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tournament_edit_history'"
        ).fetchone()
        assert result is not None

        # Check columns
        columns = db.execute("PRAGMA table_info(tournament_edit_history)").fetchall()
        column_names = [col[1] for col in columns]

        assert 'id' in column_names
        assert 'tournament_id' in column_names
        assert 'changed_at' in column_names
        assert 'change_type' in column_names
        assert 'change_data' in column_names

def test_can_insert_edit_history(client):
    """Test that we can insert edit history records"""
    from database import get_db
    import json

    with app.app_context():
        db = get_db()

        # Create season and tournament first
        db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
        db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                  ("Test Tournament", 2, 1, "setup"))

        # Insert history record
        change_data = json.dumps({"player_name": "Matti Virtanen", "action": "added"})
        db.execute(
            """INSERT INTO tournament_edit_history
               (tournament_id, change_type, change_data)
               VALUES (?, ?, ?)""",
            (1, 'player_added', change_data)
        )
        db.commit()

        # Verify insertion
        result = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = ?"
        , (1,)).fetchone()

        assert result is not None
        assert result['change_type'] == 'player_added'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_edit_history_schema.py -v`

Expected: FAIL with "no such table: tournament_edit_history"

**Step 3: Add table creation to database.py**

Add after line 266 (after player_points_adjustment table) in `database.py`:

```python
    # Tournament edit history table (for tracking changes across edit sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_edit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            change_type TEXT NOT NULL,
            change_data TEXT NOT NULL,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_edit_history_tournament
        ON tournament_edit_history(tournament_id)
    ''')
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_edit_history_schema.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add database.py tests/test_edit_history_schema.py
git commit -m "feat: add tournament_edit_history table for tracking changes"
```

---

## Task 2: Create Player Name Validation Helper

**Files:**
- Create: `player_validation.py`
- Test: `tests/test_player_validation.py`

**Step 1: Write the failing test**

Create `tests/test_player_validation.py`:

```python
import pytest
from player_validation import validate_player_names, find_similar_player

def test_find_similar_player_exact_match():
    """Exact match returns the player"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
        {'id': 2, 'first_name': 'Anna', 'last_name': 'Korhonen'},
    ]
    result = find_similar_player('Matti Virtanen', registry)
    assert result['status'] == 'exact'
    assert result['player_id'] == 1

def test_find_similar_player_fuzzy_match():
    """Similar name suggests correction"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Meikäläinen'},
    ]
    result = find_similar_player('Matti Meikalainen', registry)  # Missing ä
    assert result['status'] == 'similar'
    assert result['suggestion'] == 'Matti Meikäläinen'
    assert result['player_id'] == 1

def test_find_similar_player_no_match():
    """New player detected"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
    ]
    result = find_similar_player('Liisa Nieminen', registry)
    assert result['status'] == 'new'
    assert result['player_id'] is None

def test_validate_player_names_mixed():
    """Validate list with mix of exact, similar, and new"""
    registry = [
        {'id': 1, 'first_name': 'Matti', 'last_name': 'Virtanen'},
        {'id': 2, 'first_name': 'Anna', 'last_name': 'Korhonen'},
    ]
    names = ['Matti Virtanen', 'Matti Virtanen', 'Anna Korhonnen', 'Liisa Uusi']

    results = validate_player_names(names, registry)

    assert len(results) == 4
    assert results[0]['status'] == 'exact'
    assert results[1]['status'] == 'duplicate'  # Duplicate of first
    assert results[2]['status'] == 'similar'  # Typo
    assert results[3]['status'] == 'new'

def test_validate_player_names_empty_lines_ignored():
    """Empty lines in input are filtered out"""
    registry = []
    names = ['Matti Virtanen', '', '  ', 'Anna Korhonen']

    results = validate_player_names(names, registry)

    assert len(results) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_player_validation.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'player_validation'"

**Step 3: Create player_validation.py**

Create `player_validation.py`:

```python
"""
Player name validation with fuzzy matching against registry.
"""
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.8


def normalize_name(name):
    """Normalize name for comparison (lowercase, strip whitespace)"""
    return ' '.join(name.lower().split())


def similarity_ratio(name1, name2):
    """Calculate similarity ratio between two names"""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()


def find_similar_player(name, registry):
    """
    Find matching or similar player in registry.

    Returns dict with:
    - status: 'exact', 'similar', or 'new'
    - player_id: ID if exact/similar match, None if new
    - suggestion: suggested name if similar match
    - similarity: similarity score if similar match
    """
    name = name.strip()
    if not name:
        return {'status': 'invalid', 'player_id': None}

    # Check for exact match first
    for player in registry:
        full_name = f"{player['first_name']} {player['last_name']}"
        if normalize_name(name) == normalize_name(full_name):
            return {
                'status': 'exact',
                'player_id': player['id'],
                'name': full_name
            }

    # Look for similar matches
    best_match = None
    best_score = 0

    for player in registry:
        full_name = f"{player['first_name']} {player['last_name']}"
        score = similarity_ratio(name, full_name)

        if score > best_score and score >= SIMILARITY_THRESHOLD:
            best_score = score
            best_match = player

    if best_match:
        full_name = f"{best_match['first_name']} {best_match['last_name']}"
        return {
            'status': 'similar',
            'player_id': best_match['id'],
            'suggestion': full_name,
            'similarity': best_score
        }

    # No match found - new player
    return {
        'status': 'new',
        'player_id': None,
        'name': name
    }


def validate_player_names(names, registry):
    """
    Validate a list of player names against registry.

    Returns list of validation results, one per non-empty name.
    Detects duplicates within the input list.
    """
    results = []
    seen_names = {}  # normalized name -> index

    for name in names:
        name = name.strip()
        if not name:
            continue

        normalized = normalize_name(name)

        # Check for duplicate within this list
        if normalized in seen_names:
            results.append({
                'status': 'duplicate',
                'name': name,
                'duplicate_of_index': seen_names[normalized],
                'player_id': None
            })
            continue

        # Validate against registry
        result = find_similar_player(name, registry)
        result['name'] = name
        result['index'] = len(results)
        results.append(result)

        seen_names[normalized] = len(results) - 1

    return results
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_player_validation.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add player_validation.py tests/test_player_validation.py
git commit -m "feat: add player name validation with fuzzy matching"
```

---

## Task 3: Create Validate Players API Endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_validate_players_api.py`

**Step 1: Write the failing test**

Create `tests/test_validate_players_api.py`:

```python
import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_validate_api.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        # Setup admin session
        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        # Add some players to registry
        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Matti", "Virtanen"))
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Anna", "Korhonen"))
            db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                      ("Matti", "Meikäläinen"))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_validate_players_endpoint_exists(client):
    """Test that validate-players endpoint exists"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Virtanen'},
                          content_type='application/json')
    assert response.status_code == 200

def test_validate_players_exact_match(client):
    """Test validation returns exact match for known player"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Virtanen'},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'exact'
    assert data['results'][0]['player_id'] == 1

def test_validate_players_fuzzy_match(client):
    """Test validation suggests correction for typo"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Matti Meikalainen'},  # Missing ä
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'similar'
    assert data['results'][0]['suggestion'] == 'Matti Meikäläinen'

def test_validate_players_new_player(client):
    """Test validation detects new player"""
    response = client.post('/admin/validate-players',
                          json={'players': 'Liisa Nieminen'},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 1
    assert data['results'][0]['status'] == 'new'

def test_validate_players_multiple(client):
    """Test validation with multiple players"""
    players = "Matti Virtanen\nMatti Meikalainen\nLiisa Uusi"
    response = client.post('/admin/validate-players',
                          json={'players': players},
                          content_type='application/json')
    data = json.loads(response.data)

    assert len(data['results']) == 3
    assert data['summary']['exact'] == 1
    assert data['summary']['similar'] == 1
    assert data['summary']['new'] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_validate_players_api.py -v`

Expected: FAIL with 404 Not Found

**Step 3: Add endpoint to app.py**

Find the admin routes section in `app.py` and add:

```python
@app.route('/admin/validate-players', methods=['POST'])
@require_admin
def admin_validate_players():
    """Validate player names against registry (AJAX endpoint)"""
    from player_validation import validate_player_names

    data = request.get_json()
    if not data or 'players' not in data:
        return jsonify({'error': 'No players provided'}), 400

    players_text = data['players']
    player_names = [line.strip() for line in players_text.split('\n') if line.strip()]

    # Get all players from registry
    db = get_db_connection()
    registry = db.execute(
        'SELECT id, first_name, last_name FROM player_registry ORDER BY first_name, last_name'
    ).fetchall()

    # Convert to list of dicts for validation
    registry_list = [dict(p) for p in registry]

    # Validate
    results = validate_player_names(player_names, registry_list)

    # Build summary
    summary = {
        'exact': sum(1 for r in results if r['status'] == 'exact'),
        'similar': sum(1 for r in results if r['status'] == 'similar'),
        'new': sum(1 for r in results if r['status'] == 'new'),
        'duplicate': sum(1 for r in results if r['status'] == 'duplicate'),
        'total': len(results)
    }

    return jsonify({
        'results': results,
        'summary': summary
    })
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_validate_players_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app.py tests/test_validate_players_api.py
git commit -m "feat: add player name validation API endpoint"
```

---

## Task 4: Create Full-Screen Edit Page Template

**Files:**
- Create: `templates/admin_tournament_edit.html`
- Create: `static/css/admin_edit.css`

**Step 1: Create the HTML template**

Create `templates/admin_tournament_edit.html`:

```html
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Muokkaa turnausta - {{ tournament.name }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin_edit.css') }}">
</head>
<body class="edit-page">
    <!-- Header -->
    <header class="edit-header">
        <a href="{{ url_for('admin_dashboard') }}" class="back-link">← Takaisin</a>
        <h1>Muokkaa turnausta</h1>
        <div class="header-spacer"></div>
    </header>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-messages">
                {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Tournament Info Bar -->
    <div class="tournament-info-bar">
        <div class="tournament-title">
            <input type="text" id="tournament-name" value="{{ tournament.name }}" class="title-input">
            <span class="status-badge setup-badge">Valmistelu</span>
        </div>
        <div class="tournament-meta">
            {{ tournament.num_courts }} kenttää · {{ players|length }} pelaajaa · Luotu {{ tournament.created_at[:10] }}
        </div>
    </div>

    <!-- Change History (if any) -->
    {% if edit_history %}
    <div class="change-history" id="change-history">
        <div class="history-header">
            <h3>Viimeisimmät muutokset ({{ edit_history[0].changed_at[:16] }})</h3>
            <button type="button" onclick="toggleHistory()" class="btn-link">Piilota</button>
        </div>
        <div class="history-content">
            {% for change in edit_history[:10] %}
            <div class="history-item {{ change.change_type }}">
                {% if change.change_type == 'player_added' %}
                <span class="change-icon">+</span> {{ change.change_data }}
                {% elif change.change_type == 'player_removed' %}
                <span class="change-icon">−</span> {{ change.change_data }}
                {% elif change.change_type == 'player_renamed' %}
                <span class="change-icon">~</span> {{ change.change_data }}
                {% elif change.change_type == 'pairing_changed' %}
                <span class="change-icon">↔</span> {{ change.change_data }}
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Main Content: Two Column Layout -->
    <main class="edit-container">
        <!-- Left Column: Players -->
        <section class="players-panel">
            <div class="panel-header">
                <h2>Pelaajat</h2>
                <button type="button" id="edit-players-btn" onclick="showPlayerEditor()" class="btn-secondary">Muokkaa</button>
            </div>

            <!-- Player List View (read-only) -->
            <div id="player-list-view" class="player-list">
                {% for player in players %}
                <div class="player-item">
                    <span class="player-name">{{ player.first_name }} {{ player.last_name }}</span>
                </div>
                {% endfor %}
            </div>

            <!-- Player Editor (hidden by default) -->
            <div id="player-editor" class="player-editor" style="display: none;">
                <textarea id="players-textarea" rows="16" placeholder="Liitä pelaajien nimet, yksi per rivi">{% for player in players %}{{ player.first_name }} {{ player.last_name }}
{% endfor %}</textarea>
                <div class="editor-actions">
                    <button type="button" onclick="validatePlayers()" class="btn-primary">Tarkista nimet</button>
                    <button type="button" onclick="cancelPlayerEdit()" class="btn-secondary">Peruuta</button>
                </div>
            </div>

            <!-- Validation Results (hidden by default) -->
            <div id="validation-results" class="validation-results" style="display: none;">
                <div id="validation-list"></div>
                <div class="validation-summary" id="validation-summary"></div>
                <div class="validation-actions">
                    <button type="button" onclick="backToEditor()" class="btn-secondary">Takaisin muokkaukseen</button>
                    <button type="button" onclick="applyPlayerChanges()" class="btn-primary" id="apply-btn" disabled>Hyväksy ja jatka</button>
                </div>
            </div>
        </section>

        <!-- Right Column: Pairings -->
        <section class="pairings-panel">
            <div class="panel-header">
                <h2>Kierros 1 - Parit</h2>
                <button type="button" onclick="regeneratePairings()" class="btn-secondary">Luo uudet parit</button>
            </div>

            <!-- Courts Display -->
            <div id="courts-container" class="courts-container">
                {% if pairings %}
                    {% for court in pairings %}
                    <div class="court-card" data-court="{{ court.court_number }}">
                        <div class="court-header">Kenttä {{ court.court_number }}</div>
                        <div class="court-teams">
                            <div class="team team1">
                                <h4>Tiimi 1</h4>
                                <div class="player-slot" data-player-id="{{ court.team1_player1_id }}" onclick="selectPlayer(this)">
                                    {{ court.team1_player1_name or '[TYHJÄ]' }}
                                </div>
                                <div class="player-slot" data-player-id="{{ court.team1_player2_id }}" onclick="selectPlayer(this)">
                                    {{ court.team1_player2_name or '[TYHJÄ]' }}
                                </div>
                            </div>
                            <div class="team team2">
                                <h4>Tiimi 2</h4>
                                <div class="player-slot" data-player-id="{{ court.team2_player1_id }}" onclick="selectPlayer(this)">
                                    {{ court.team2_player1_name or '[TYHJÄ]' }}
                                </div>
                                <div class="player-slot" data-player-id="{{ court.team2_player2_id }}" onclick="selectPlayer(this)">
                                    {{ court.team2_player2_name or '[TYHJÄ]' }}
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="no-pairings">
                        <p>Ei vielä pareja. Klikkaa "Luo uudet parit" luodaksesi kierros 1 parit.</p>
                    </div>
                {% endif %}
            </div>

            <!-- Unassigned Players Pool -->
            <div id="unassigned-pool" class="unassigned-pool" style="display: {% if unassigned_players %}block{% else %}none{% endif %};">
                <h3>Sijoittamattomat pelaajat</h3>
                <div class="unassigned-list">
                    {% for player in unassigned_players %}
                    <div class="unassigned-player" data-player-id="{{ player.id }}" onclick="selectPlayer(this)">
                        {{ player.first_name }} {{ player.last_name }}
                    </div>
                    {% endfor %}
                </div>
                <p class="hint">Klikkaa pelaajaa, sitten tyhjää paikkaa sijoittaaksesi</p>
            </div>
        </section>
    </main>

    <!-- Action Bar -->
    <footer class="action-bar">
        <div class="action-bar-left">
            <form method="POST" action="{{ url_for('admin_delete_tournament', tournament_id=tournament.id) }}"
                  onsubmit="return confirm('⚠️ Haluatko varmasti poistaa turnauksen? Tätä ei voi perua.');">
                <button type="submit" class="btn-danger">Poista turnaus</button>
            </form>
        </div>
        <div class="action-bar-right">
            <button type="button" onclick="saveTournament()" class="btn-secondary" id="save-btn">Tallenna</button>
            <button type="button" onclick="startTournament()" class="btn-primary" id="start-btn"
                    {% if not can_start %}disabled title="Täytä kaikki paikat ennen aloittamista"{% endif %}>
                Aloita turnaus
            </button>
        </div>
    </footer>

    <!-- Hidden form for saving -->
    <form id="save-form" method="POST" action="{{ url_for('admin_edit_tournament', tournament_id=tournament.id) }}" style="display: none;">
        <input type="hidden" name="tournament_name" id="form-tournament-name">
        <input type="hidden" name="num_courts" value="{{ tournament.num_courts }}">
        <input type="hidden" name="players" id="form-players">
        <input type="hidden" name="round1_pairings" id="form-pairings">
    </form>

    <script src="{{ url_for('static', filename='js/tournament_edit.js') }}"></script>
    <script>
        // Initialize with tournament data
        const tournamentId = {{ tournament.id }};
        const numCourts = {{ tournament.num_courts }};
    </script>
</body>
</html>
```

**Step 2: Create the CSS file**

Create `static/css/admin_edit.css`:

```css
/* Full-screen edit page styles */

body.edit-page {
    margin: 0;
    padding: 0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: #f5f5f5;
}

/* Header */
.edit-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 2rem;
    background: #1a1a2e;
    color: white;
}

.edit-header h1 {
    margin: 0;
    font-size: 1.25rem;
}

.back-link {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
}

.back-link:hover {
    background: rgba(255,255,255,0.2);
}

.header-spacer {
    width: 100px;
}

/* Tournament Info Bar */
.tournament-info-bar {
    padding: 1rem 2rem;
    background: white;
    border-bottom: 1px solid #ddd;
}

.tournament-title {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.title-input {
    font-size: 1.5rem;
    font-weight: bold;
    border: none;
    background: transparent;
    padding: 0.25rem;
    border-bottom: 2px solid transparent;
}

.title-input:focus {
    outline: none;
    border-bottom-color: #007bff;
}

.tournament-meta {
    color: #666;
    margin-top: 0.5rem;
}

/* Change History */
.change-history {
    margin: 1rem 2rem;
    padding: 1rem;
    background: #fff9e6;
    border: 1px solid #ffe066;
    border-radius: 8px;
}

.history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.history-header h3 {
    margin: 0;
    font-size: 1rem;
}

.history-item {
    padding: 0.25rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.change-icon {
    font-weight: bold;
    width: 1.5rem;
    text-align: center;
}

.player_added .change-icon { color: #28a745; }
.player_removed .change-icon { color: #dc3545; }
.player_renamed .change-icon { color: #ffc107; }
.pairing_changed .change-icon { color: #17a2b8; }

/* Main Container */
.edit-container {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 2rem;
    padding: 2rem;
    flex: 1;
    overflow: auto;
}

/* Panel Common Styles */
.players-panel,
.pairings-panel {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #eee;
}

.panel-header h2 {
    margin: 0;
    font-size: 1.25rem;
}

/* Player List */
.player-list {
    max-height: 400px;
    overflow-y: auto;
}

.player-item {
    padding: 0.5rem;
    border-bottom: 1px solid #f0f0f0;
}

/* Player Editor */
.player-editor textarea {
    width: 100%;
    font-family: inherit;
    font-size: 0.9rem;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    resize: vertical;
}

.editor-actions {
    margin-top: 1rem;
    display: flex;
    gap: 0.5rem;
}

/* Validation Results */
.validation-results {
    max-height: 400px;
    overflow-y: auto;
}

.validation-item {
    padding: 0.75rem;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.validation-item.exact { background: #e8f5e9; }
.validation-item.similar { background: #fff3e0; }
.validation-item.new { background: #e3f2fd; }
.validation-item.duplicate { background: #ffebee; }

.validation-icon {
    font-size: 1.25rem;
}

.validation-suggestion {
    margin-left: auto;
}

.validation-summary {
    padding: 1rem;
    background: #f5f5f5;
    margin-top: 1rem;
    border-radius: 4px;
}

.validation-actions {
    margin-top: 1rem;
    display: flex;
    justify-content: space-between;
}

/* Courts Container */
.courts-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
}

.court-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
}

.court-header {
    background: #f0f0f0;
    padding: 0.75rem;
    font-weight: bold;
    text-align: center;
}

.court-teams {
    display: grid;
    grid-template-columns: 1fr 1fr;
}

.team {
    padding: 1rem;
}

.team h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    color: #666;
}

.team1 { background: #e3f2fd; }
.team2 { background: #fce4ec; }

.player-slot {
    padding: 0.5rem;
    margin: 0.25rem 0;
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.player-slot:hover {
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.player-slot.selected {
    background: #007bff;
    color: white;
}

.player-slot.empty {
    background: #ffebee;
    color: #dc3545;
    font-style: italic;
}

/* Unassigned Pool */
.unassigned-pool {
    margin-top: 1.5rem;
    padding: 1rem;
    background: #fff9e6;
    border: 1px solid #ffe066;
    border-radius: 8px;
}

.unassigned-pool h3 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
}

.unassigned-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.unassigned-player {
    padding: 0.5rem 1rem;
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
}

.unassigned-player:hover {
    border-color: #007bff;
}

.unassigned-player.selected {
    background: #007bff;
    color: white;
    border-color: #007bff;
}

.hint {
    margin-top: 0.5rem;
    color: #666;
    font-size: 0.875rem;
}

/* No Pairings */
.no-pairings {
    padding: 2rem;
    text-align: center;
    color: #666;
}

/* Action Bar */
.action-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background: white;
    border-top: 1px solid #ddd;
}

.action-bar-right {
    display: flex;
    gap: 1rem;
}

/* Buttons */
.btn-primary {
    background: #007bff;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
}

.btn-primary:hover { background: #0056b3; }
.btn-primary:disabled { background: #ccc; cursor: not-allowed; }

.btn-secondary {
    background: #6c757d;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
}

.btn-secondary:hover { background: #545b62; }

.btn-danger {
    background: #dc3545;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
}

.btn-danger:hover { background: #c82333; }

.btn-link {
    background: none;
    border: none;
    color: #007bff;
    cursor: pointer;
    text-decoration: underline;
}
```

**Step 3: Commit the templates**

```bash
git add templates/admin_tournament_edit.html static/css/admin_edit.css
git commit -m "feat: add full-screen tournament edit page template and styles"
```

---

## Task 5: Create Tournament Edit JavaScript

**Files:**
- Create: `static/js/tournament_edit.js`

**Step 1: Create the JavaScript file**

Create `static/js/tournament_edit.js`:

```javascript
/**
 * Tournament Edit Page JavaScript
 * Handles player editing, validation, and pairing interactions
 */

// State
let currentPlayers = [];
let validationResults = [];
let selectedSlot = null;
let pairingsModified = false;

// Player Editor
function showPlayerEditor() {
    document.getElementById('player-list-view').style.display = 'none';
    document.getElementById('player-editor').style.display = 'block';
    document.getElementById('edit-players-btn').style.display = 'none';
}

function cancelPlayerEdit() {
    document.getElementById('player-list-view').style.display = 'block';
    document.getElementById('player-editor').style.display = 'none';
    document.getElementById('edit-players-btn').style.display = 'inline-block';
}

function backToEditor() {
    document.getElementById('validation-results').style.display = 'none';
    document.getElementById('player-editor').style.display = 'block';
}

// Validation
async function validatePlayers() {
    const textarea = document.getElementById('players-textarea');
    const playersText = textarea.value.trim();

    if (!playersText) {
        alert('Syötä pelaajien nimet');
        return;
    }

    // Check player count
    const lines = playersText.split('\n').filter(l => l.trim());
    const requiredPlayers = numCourts * 4;

    if (lines.length !== requiredPlayers) {
        alert(`Tarvitaan ${requiredPlayers} pelaajaa ${numCourts} kentälle. Syötit ${lines.length} pelaajaa.`);
        return;
    }

    try {
        const response = await fetch('/admin/validate-players', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ players: playersText })
        });

        const data = await response.json();
        validationResults = data.results;

        displayValidationResults(data);

        document.getElementById('player-editor').style.display = 'none';
        document.getElementById('validation-results').style.display = 'block';

    } catch (error) {
        console.error('Validation error:', error);
        alert('Virhe tarkistuksessa. Yritä uudelleen.');
    }
}

function displayValidationResults(data) {
    const container = document.getElementById('validation-list');
    const summary = document.getElementById('validation-summary');
    const applyBtn = document.getElementById('apply-btn');

    container.innerHTML = '';

    data.results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = `validation-item ${result.status}`;
        item.dataset.index = index;

        let icon, content;

        switch (result.status) {
            case 'exact':
                icon = '✓';
                content = `<span class="player-name">${result.name}</span>`;
                break;
            case 'similar':
                icon = '⚠';
                content = `
                    <span class="player-name">${result.name}</span>
                    <span class="validation-suggestion">
                        → ${result.suggestion}?
                        <button onclick="acceptSuggestion(${index})" class="btn-link">Kyllä</button>
                        <button onclick="rejectSuggestion(${index})" class="btn-link">Ei, uusi pelaaja</button>
                    </span>
                `;
                break;
            case 'new':
                icon = '★';
                content = `<span class="player-name">${result.name}</span> <span class="tag">uusi pelaaja</span>`;
                break;
            case 'duplicate':
                icon = '✕';
                content = `<span class="player-name">${result.name}</span> <span class="error">duplikaatti</span>`;
                break;
        }

        item.innerHTML = `<span class="validation-icon">${icon}</span>${content}`;
        container.appendChild(item);
    });

    // Summary
    summary.innerHTML = `
        <strong>Yhteenveto:</strong>
        ${data.summary.exact} tunnettua ·
        ${data.summary.similar} tarkistettavaa ·
        ${data.summary.new} uutta
        ${data.summary.duplicate > 0 ? ` · <span class="error">${data.summary.duplicate} duplikaattia</span>` : ''}
    `;

    // Enable/disable apply button
    const hasUnresolvedSimilar = data.results.some(r => r.status === 'similar');
    const hasDuplicates = data.summary.duplicate > 0;
    applyBtn.disabled = hasUnresolvedSimilar || hasDuplicates;
}

function acceptSuggestion(index) {
    // Update the textarea with the suggested name
    const textarea = document.getElementById('players-textarea');
    const lines = textarea.value.split('\n');
    const result = validationResults[index];

    // Find and replace the line
    let lineIndex = 0;
    for (let i = 0; i < validationResults.length && i <= index; i++) {
        if (i === index) break;
        lineIndex++;
    }

    lines[lineIndex] = result.suggestion;
    textarea.value = lines.join('\n');

    // Re-validate
    validatePlayers();
}

function rejectSuggestion(index) {
    // Mark as confirmed new player
    validationResults[index].status = 'new';
    validationResults[index].confirmed_new = true;

    // Re-render without re-fetching
    const data = {
        results: validationResults,
        summary: {
            exact: validationResults.filter(r => r.status === 'exact').length,
            similar: validationResults.filter(r => r.status === 'similar').length,
            new: validationResults.filter(r => r.status === 'new').length,
            duplicate: validationResults.filter(r => r.status === 'duplicate').length
        }
    };
    displayValidationResults(data);
}

async function applyPlayerChanges() {
    // Players validated, now save and reload
    saveTournament();
}

// Pairings
function selectPlayer(element) {
    const playerId = element.dataset.playerId;

    if (selectedSlot) {
        // Second click - swap
        if (selectedSlot !== element) {
            swapPlayers(selectedSlot, element);
        }
        selectedSlot.classList.remove('selected');
        selectedSlot = null;
    } else {
        // First click - select
        selectedSlot = element;
        element.classList.add('selected');
    }
}

function swapPlayers(slot1, slot2) {
    const id1 = slot1.dataset.playerId;
    const id2 = slot2.dataset.playerId;
    const name1 = slot1.textContent;
    const name2 = slot2.textContent;

    slot1.dataset.playerId = id2;
    slot1.textContent = name2;
    slot2.dataset.playerId = id1;
    slot2.textContent = name1;

    // Handle empty slot styling
    slot1.classList.toggle('empty', !id2 || id2 === 'null');
    slot2.classList.toggle('empty', !id1 || id1 === 'null');

    pairingsModified = true;
}

async function regeneratePairings() {
    if (!confirm('Luo uudet parit algoritmilla? Nykyiset parit korvataan.')) {
        return;
    }

    try {
        const response = await fetch(`/admin/tournaments/${tournamentId}/preview-round1`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });

        if (response.ok) {
            location.reload();
        } else {
            const error = await response.json();
            alert('Virhe: ' + (error.error || 'Tuntematon virhe'));
        }
    } catch (error) {
        console.error('Regenerate error:', error);
        alert('Virhe parien luomisessa');
    }
}

// Save
function saveTournament() {
    const form = document.getElementById('save-form');

    // Tournament name
    document.getElementById('form-tournament-name').value =
        document.getElementById('tournament-name').value;

    // Players
    document.getElementById('form-players').value =
        document.getElementById('players-textarea').value;

    // Pairings
    if (pairingsModified) {
        const pairings = collectPairingsData();
        document.getElementById('form-pairings').value = JSON.stringify(pairings);
    }

    form.submit();
}

function collectPairingsData() {
    const courts = document.querySelectorAll('.court-card');
    const pairings = [];

    courts.forEach(court => {
        const courtNumber = parseInt(court.dataset.court);
        const slots = court.querySelectorAll('.player-slot');

        pairings.push({
            court: courtNumber,
            team1: [
                parseInt(slots[0].dataset.playerId) || null,
                parseInt(slots[1].dataset.playerId) || null
            ],
            team2: [
                parseInt(slots[2].dataset.playerId) || null,
                parseInt(slots[3].dataset.playerId) || null
            ]
        });
    });

    return pairings;
}

// Start Tournament
async function startTournament() {
    // Validate: no empty slots, no unassigned players
    const emptySlots = document.querySelectorAll('.player-slot.empty');
    const unassigned = document.querySelectorAll('.unassigned-player');

    if (emptySlots.length > 0) {
        alert('Täytä kaikki tyhjät paikat ennen aloittamista.');
        return;
    }

    if (unassigned.length > 0) {
        alert('Sijoita kaikki pelaajat ennen aloittamista.');
        return;
    }

    if (confirm('Aloita turnaus? Pelaajia ja pareja ei voi enää muokata.')) {
        // Save first, then start
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/admin/start-round/${tournamentId}`;
        document.body.appendChild(form);
        form.submit();
    }
}

// History toggle
function toggleHistory() {
    const history = document.getElementById('change-history');
    if (history) {
        history.style.display = history.style.display === 'none' ? 'block' : 'none';
    }
}

// Initialize empty slots
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.player-slot').forEach(slot => {
        const text = slot.textContent.trim();
        if (text === '[TYHJÄ]' || !slot.dataset.playerId || slot.dataset.playerId === 'None') {
            slot.classList.add('empty');
        }
    });
});
```

**Step 2: Commit**

```bash
git add static/js/tournament_edit.js
git commit -m "feat: add tournament edit page JavaScript for player validation and pairings"
```

---

## Task 6: Create Edit Page Route

**Files:**
- Modify: `app.py`
- Test: `tests/test_tournament_edit_page.py`

**Step 1: Write the failing test**

Create `tests/test_tournament_edit_page.py`:

```python
import pytest
import os
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_edit_page.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        # Create test data
        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
            db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                      ("Test Tournament", 2, 1, "setup"))

            # Add 8 players
            for i in range(1, 9):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (1, i))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_edit_page_exists(client):
    """Test that edit page route exists"""
    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 200

def test_edit_page_shows_tournament_name(client):
    """Test that edit page shows tournament name"""
    response = client.get('/admin/tournaments/1/edit')
    assert b'Test Tournament' in response.data

def test_edit_page_shows_players(client):
    """Test that edit page shows player list"""
    response = client.get('/admin/tournaments/1/edit')
    assert b'Player1 Last1' in response.data

def test_edit_page_requires_admin(client):
    """Test that edit page requires admin login"""
    # Clear admin session
    with client.session_transaction() as sess:
        sess.clear()

    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 302  # Redirect to login

def test_edit_page_404_for_nonexistent(client):
    """Test that edit page returns 404 for nonexistent tournament"""
    response = client.get('/admin/tournaments/999/edit')
    assert response.status_code == 404

def test_edit_page_404_for_non_setup(client):
    """Test that edit page returns 404 for non-setup tournament"""
    from database import get_db
    with app.app_context():
        db = get_db()
        db.execute("UPDATE tournaments SET status = 'active' WHERE id = 1")
        db.commit()

    response = client.get('/admin/tournaments/1/edit')
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_tournament_edit_page.py -v`

Expected: FAIL with 404 Not Found

**Step 3: Add route to app.py**

Add to app.py in the admin routes section:

```python
@app.route('/admin/tournaments/<int:tournament_id>/edit')
@require_admin
def admin_tournament_edit_page(tournament_id):
    """Full-screen tournament edit page (ADMIN)"""
    db = get_db_connection()

    # Get tournament (must be in setup mode)
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ? AND status = ?',
        (tournament_id, 'setup')
    ).fetchone()

    if not tournament:
        abort(404)

    # Get players
    players = db.execute('''
        SELECT pr.id, pr.first_name, pr.last_name
        FROM player_registry pr
        JOIN tournament_players tp ON pr.id = tp.player_id
        WHERE tp.tournament_id = ?
        ORDER BY pr.first_name, pr.last_name
    ''', (tournament_id,)).fetchall()

    # Get pairings with player names
    pairings_raw = db.execute('''
        SELECT p.*,
               p1.first_name || ' ' || p1.last_name as team1_player1_name,
               p2.first_name || ' ' || p2.last_name as team1_player2_name,
               p3.first_name || ' ' || p3.last_name as team2_player1_name,
               p4.first_name || ' ' || p4.last_name as team2_player2_name
        FROM round1_preview_pairings p
        LEFT JOIN player_registry p1 ON p.team1_player1_id = p1.id
        LEFT JOIN player_registry p2 ON p.team1_player2_id = p2.id
        LEFT JOIN player_registry p3 ON p.team2_player1_id = p3.id
        LEFT JOIN player_registry p4 ON p.team2_player2_id = p4.id
        WHERE p.tournament_id = ?
        ORDER BY p.court_number
    ''', (tournament_id,)).fetchall()

    pairings = [dict(p) for p in pairings_raw] if pairings_raw else []

    # Find unassigned players (in tournament but not in pairings)
    assigned_player_ids = set()
    for p in pairings:
        assigned_player_ids.add(p['team1_player1_id'])
        assigned_player_ids.add(p['team1_player2_id'])
        assigned_player_ids.add(p['team2_player1_id'])
        assigned_player_ids.add(p['team2_player2_id'])
    assigned_player_ids.discard(None)

    unassigned_players = [p for p in players if p['id'] not in assigned_player_ids]

    # Check if tournament can start (all slots filled, no unassigned)
    has_empty_slots = any(
        p['team1_player1_id'] is None or p['team1_player2_id'] is None or
        p['team2_player1_id'] is None or p['team2_player2_id'] is None
        for p in pairings
    )
    can_start = pairings and not has_empty_slots and not unassigned_players

    # Get edit history
    edit_history = db.execute('''
        SELECT * FROM tournament_edit_history
        WHERE tournament_id = ?
        ORDER BY changed_at DESC
        LIMIT 20
    ''', (tournament_id,)).fetchall()

    return render_template('admin_tournament_edit.html',
                          tournament=tournament,
                          players=players,
                          pairings=pairings,
                          unassigned_players=unassigned_players,
                          can_start=can_start,
                          edit_history=edit_history)
```

Also add at the top of app.py if not present:
```python
from flask import abort
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_tournament_edit_page.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app.py tests/test_tournament_edit_page.py
git commit -m "feat: add full-screen tournament edit page route"
```

---

## Task 7: Update Dashboard to Link to Edit Page

**Files:**
- Modify: `templates/admin_dashboard.html`

**Step 1: Update the Muokkaa button**

In `templates/admin_dashboard.html`, find the "Muokkaa" button (around line 103) and change it from:

```html
<button onclick="toggleEditTournament({{ tournament['id'] }})" class="btn-secondary" id="edit-btn-{{ tournament['id'] }}">Muokkaa</button>
```

To:

```html
<a href="{{ url_for('admin_tournament_edit_page', tournament_id=tournament['id']) }}" class="btn-secondary">Muokkaa</a>
```

**Step 2: Remove inline edit form**

Remove the entire `<tr id="edit-row-{{ tournament['id'] }}" ...>` section (lines 117-172) as it's no longer needed.

**Step 3: Remove toggleEditTournament JavaScript**

Remove the `toggleEditTournament` function and related JavaScript (lines 419-443).

**Step 4: Commit**

```bash
git add templates/admin_dashboard.html
git commit -m "refactor: link to full-screen edit page from dashboard"
```

---

## Task 8: Add Edit History Logging

**Files:**
- Modify: `app.py`
- Test: `tests/test_edit_history_logging.py`

**Step 1: Write the failing test**

Create `tests/test_edit_history_logging.py`:

```python
import pytest
import os
import json
from datetime import datetime
from app import app

@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    db_path = tmp_path / "test_history_log.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        with app.app_context():
            from database import init_db
            init_db()

        with client.session_transaction() as sess:
            sess['logged_in_as_admin'] = True
            sess['login_time'] = datetime.now().isoformat()
            sess['last_activity'] = datetime.now().isoformat()

        from database import get_db
        with app.app_context():
            db = get_db()
            db.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test", 1))
            db.execute("INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
                      ("Test Tournament", 1, 1, "setup"))

            for i in range(1, 5):
                db.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                          (f"Player{i}", f"Last{i}"))
                db.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                          (1, i))
            db.commit()

        yield client

    if os.path.exists(db_path):
        os.remove(db_path)

def test_adding_player_logs_history(client):
    """Test that adding a player creates history entry"""
    # Edit with one new player
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nNewPlayer New"

    response = client.post('/admin/tournaments/1/edit',
                          data={
                              'tournament_name': 'Test Tournament',
                              'num_courts': 1,
                              'players': new_players
                          },
                          follow_redirects=True)

    assert response.status_code == 200

    from database import get_db
    with app.app_context():
        db = get_db()
        history = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = 1 AND change_type = 'player_added'"
        ).fetchall()

        assert len(history) >= 1

def test_removing_player_logs_history(client):
    """Test that removing a player creates history entry"""
    # Edit with fewer players (different names, same count to avoid court change)
    # But with one player swapped out
    new_players = "Player1 Last1\nPlayer2 Last2\nPlayer3 Last3\nDifferent Person"

    response = client.post('/admin/tournaments/1/edit',
                          data={
                              'tournament_name': 'Test Tournament',
                              'num_courts': 1,
                              'players': new_players
                          },
                          follow_redirects=True)

    assert response.status_code == 200

    from database import get_db
    with app.app_context():
        db = get_db()
        history = db.execute(
            "SELECT * FROM tournament_edit_history WHERE tournament_id = 1"
        ).fetchall()

        # Should have both added and removed entries
        assert len(history) >= 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_edit_history_logging.py -v`

Expected: FAIL (no history entries created)

**Step 3: Add history logging to admin_edit_tournament**

In `app.py`, in the `admin_edit_tournament` function, after processing player changes, add history logging. Find the section where players are added/removed and add:

```python
def log_edit_history(db, tournament_id, change_type, change_data):
    """Helper to log tournament edit history"""
    import json
    db.execute(
        '''INSERT INTO tournament_edit_history (tournament_id, change_type, change_data)
           VALUES (?, ?, ?)''',
        (tournament_id, change_type, json.dumps(change_data) if isinstance(change_data, dict) else change_data)
    )
```

Then in the `admin_edit_tournament` function, after determining which players were added/removed:

```python
    # Log player changes to history
    # Calculate added and removed players
    new_player_ids_set = set(final_player_ids_ordered)
    added_players = new_player_ids_set - current_player_ids
    removed_players = current_player_ids - new_player_ids_set

    # Log additions
    for player_id in added_players:
        player = db.execute(
            'SELECT first_name, last_name FROM player_registry WHERE id = ?',
            (player_id,)
        ).fetchone()
        if player:
            log_edit_history(db, tournament_id, 'player_added',
                           f"{player['first_name']} {player['last_name']}")

    # Log removals
    for player_id in removed_players:
        player = db.execute(
            'SELECT first_name, last_name FROM player_registry WHERE id = ?',
            (player_id,)
        ).fetchone()
        if player:
            log_edit_history(db, tournament_id, 'player_removed',
                           f"{player['first_name']} {player['last_name']}")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest tests/test_edit_history_logging.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app.py tests/test_edit_history_logging.py
git commit -m "feat: log player changes to tournament edit history"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest -v`

Expected: All tests pass

**Step 2: Fix any failures**

If any tests fail, investigate and fix before proceeding.

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test failures from edit UX changes"
```

---

## Task 10: Manual Testing and Polish

**Step 1: Start the application**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python app.py`

**Step 2: Test the edit workflow**

1. Log in to admin
2. Create a tournament with 8 players
3. Click "Muokkaa" - should open full-screen edit page
4. Test player validation:
   - Paste names with a typo
   - Click "Tarkista nimet"
   - Accept/reject suggestions
5. Test pairing swaps
6. Save and verify changes persist
7. Return another day and verify history shows

**Step 3: Fix any issues found**

Make necessary adjustments based on manual testing.

**Step 4: Final commit**

```bash
git add -A
git commit -m "polish: refine tournament edit UX based on testing"
```

---

## Summary

This plan implements:

1. **Edit history table** - Track changes across sessions
2. **Player validation helper** - Fuzzy matching with difflib
3. **Validation API endpoint** - AJAX endpoint for real-time validation
4. **Full-screen edit template** - Two-column layout with players and pairings
5. **Edit page CSS** - Clean, focused styling
6. **Edit page JavaScript** - Player validation, pairing swaps
7. **Edit page route** - Dedicated page instead of inline editing
8. **Dashboard updates** - Link to new edit page
9. **History logging** - Log player changes automatically

Total: 10 tasks, each with TDD approach and frequent commits.
