# Move Tournament Creation to Admin - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Move tournament creation from public home page to authenticated admin dashboard with smart home page redirect.

**Architecture:** 4-phase implementation: (1) Add admin tournament creation, (2) Create new public templates, (3) Implement smart home redirect, (4) Remove old routes.

**Tech Stack:** Flask, Jinja2, SQLite, pytest

---

## Phase 1: Admin Tournament Management

### Task 1: Add Tournament List to Admin Dashboard Route

**Files:**
- Modify: `app.py:1737-1770` (admin_dashboard function)

**Step 1: Update admin_dashboard route to fetch tournaments**

```python
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard main page with season management"""
    db = get_db()

    current_season = get_current_season(db)

    archived_seasons = db.execute("""
        SELECT s.*, COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON s.id = t.season_id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.ended_at DESC, s.created_at DESC
    """).fetchall()

    current_tournament_count = 0
    current_season_tournaments = []  # NEW
    if current_season:
        current_tournament_count = db.execute(
            "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']

        # NEW: Fetch tournaments for current season
        current_season_tournaments = db.execute(
            "SELECT * FROM tournaments WHERE season_id = ? ORDER BY created_at DESC",
            (current_season['id'],)
        ).fetchall()

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          current_season_tournaments=current_season_tournaments,  # NEW
                          archived_seasons=archived_seasons)
```

**Step 2: Test the route manually**

Run: `venv/bin/python app.py` (in background)
Visit: `http://127.0.0.1:5001/admin`
Expected: Admin dashboard loads, no errors

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat(admin): add tournament list query to admin dashboard

Fetch current season's tournaments for display in admin.
Ordered by created_at DESC (newest first).
"
```

---

### Task 2: Add Tournaments Table to Admin Dashboard Template

**Files:**
- Modify: `templates/admin_dashboard.html:68-77`

**Step 1: Add tournaments table section**

Insert after line 67 (after current season card closing div), before the "Create New Season Form" section:

```html
                <!-- Current Season Tournaments -->
                {% if current_season %}
                <div class="current-season-tournaments">
                    <h3>Tournaments in {{ current_season.name }}</h3>

                    {% if current_season_tournaments %}
                    <table>
                        <thead>
                            <tr>
                                <th>Tournament Name</th>
                                <th>Date</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for tournament in current_season_tournaments %}
                            <tr>
                                <td>{{ tournament['name'] }}</td>
                                <td>{{ tournament['created_at'][:10] }}</td>
                                <td>
                                    {% if tournament['status'] == 'active' %}
                                    <span class="status-badge active-badge">Active</span>
                                    {% elif tournament['status'] == 'completed' %}
                                    <span class="status-badge completed-badge">Completed</span>
                                    {% else %}
                                    <span class="status-badge setup-badge">Setup</span>
                                    {% endif %}
                                </td>
                                <td>
                                    <a href="{{ url_for('court_selection', tournament_id=tournament['id']) }}" class="btn-secondary">View</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <p style="color: #888; font-style: italic; margin-top: 1rem;">No tournaments yet. Create one below.</p>
                    {% endif %}
                </div>
                {% endif %}
```

**Step 2: Add CSS for tournaments table**

File: `static/css/admin.css` (append to existing season management styles around line 360)

```css
/* Current Season Tournaments */
.current-season-tournaments {
    margin-top: 3rem; /* 2 line spaces */
    margin-bottom: 3rem;
}

.current-season-tournaments h3 {
    color: var(--yellow);
    margin-bottom: 1.5rem;
    font-size: 1.3rem;
}

.current-season-tournaments table {
    width: 100%;
    border-collapse: collapse;
    background-color: var(--medium-gray);
    border-radius: 8px;
    overflow: hidden;
}

.current-season-tournaments thead {
    background-color: var(--light-gray);
}

.current-season-tournaments th,
.current-season-tournaments td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--light-gray);
}

.current-season-tournaments th {
    color: var(--yellow);
    font-weight: 600;
}

.current-season-tournaments td {
    color: var(--text-light);
}

.current-season-tournaments tbody tr:hover {
    background-color: var(--light-gray);
}

.current-season-tournaments tbody tr:last-child td {
    border-bottom: none;
}

/* Status badges */
.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 600;
}

.active-badge {
    background-color: #22c55e;
    color: white;
}

.completed-badge {
    background-color: #6b7280;
    color: white;
}

.setup-badge {
    background-color: #ff9800;
    color: white;
}
```

**Step 3: Test display**

Visit: `http://127.0.0.1:5001/admin`
Expected:
- Tournaments table appears (empty state or with existing tournaments)
- Status badges display correctly
- View buttons work

**Step 4: Commit**

```bash
git add templates/admin_dashboard.html static/css/admin.css
git commit -m "feat(admin): add tournaments table to Seasons tab

Display all tournaments in current season with:
- Name, date, status badge
- View button to court selection
- Empty state message when no tournaments
"
```

---

### Task 3: Add Tournament Creation Form to Admin Dashboard

**Files:**
- Modify: `templates/admin_dashboard.html:77` (insert before "Archived Seasons" section)

**Step 1: Add create tournament form**

Insert after the tournaments table section, before the "Archived Seasons Table" comment:

```html
                <!-- Create Tournament Form -->
                {% if current_season %}
                <div class="create-tournament-form">
                    <h3>Create New Tournament</h3>
                    <form method="POST" action="/admin/tournaments/create">
                        <div class="form-group">
                            <label for="tournament_name">Tournament Name</label>
                            <input type="text" id="tournament_name" name="tournament_name" placeholder="e.g., Friday Night Padel" maxlength="100" required>
                        </div>

                        <div class="form-group">
                            <label for="num_courts">Number of Courts</label>
                            <select id="num_courts" name="num_courts" required>
                                <option value="">Select courts...</option>
                                <option value="1">1 court (4 players)</option>
                                <option value="2">2 courts (8 players)</option>
                                <option value="3">3 courts (12 players)</option>
                                <option value="4">4 courts (16 players)</option>
                                <option value="5">5 courts (20 players)</option>
                                <option value="6">6 courts (24 players)</option>
                                <option value="7">7 courts (28 players)</option>
                                <option value="8">8 courts (32 players)</option>
                                <option value="9">9 courts (36 players)</option>
                                <option value="10">10 courts (40 players)</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label for="players">Player Names (one per line)</label>
                            <textarea id="players" name="players" rows="12" placeholder="Enter player names, one per line&#10;Example:&#10;John Smith&#10;Jane Doe&#10;..." required></textarea>
                            <p class="form-hint">Minimum <span id="min_players">12</span> players required for <span id="selected_courts">3</span> courts</p>
                        </div>

                        <button type="submit" class="btn-primary">Create Tournament</button>
                    </form>
                </div>
                {% endif %}

                <script>
                // Update player count hint when courts selection changes
                document.addEventListener('DOMContentLoaded', function() {
                    const courtsSelect = document.getElementById('num_courts');
                    const minPlayersSpan = document.getElementById('min_players');
                    const selectedCourtsSpan = document.getElementById('selected_courts');

                    if (courtsSelect) {
                        courtsSelect.addEventListener('change', function() {
                            const courts = parseInt(this.value) || 0;
                            const minPlayers = courts * 4;
                            minPlayersSpan.textContent = minPlayers;
                            selectedCourtsSpan.textContent = courts;
                        });
                    }
                });
                </script>
```

**Step 2: Add CSS for tournament creation form**

File: `static/css/admin.css` (append after tournaments table styles)

```css
/* Create Tournament Form */
.create-tournament-form {
    margin-top: 3rem; /* 2 line spaces */
    margin-bottom: 3rem;
}

.create-tournament-form h3 {
    color: var(--yellow);
    margin-bottom: 1.5rem;
    font-size: 1.3rem;
}

.create-tournament-form .form-group {
    margin-bottom: 1.5rem;
}

.create-tournament-form label {
    display: block;
    color: var(--yellow);
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.create-tournament-form input[type="text"],
.create-tournament-form select,
.create-tournament-form textarea {
    width: 100%;
    padding: 1rem;
    font-size: 1rem;
    background-color: var(--medium-gray);
    border: 2px solid var(--light-gray);
    border-radius: 4px;
    color: var(--white);
    min-height: 48px;
    font-family: inherit;
}

.create-tournament-form textarea {
    min-height: 200px;
    resize: vertical;
}

.create-tournament-form input:focus,
.create-tournament-form select:focus,
.create-tournament-form textarea:focus {
    outline: none;
    border-color: var(--yellow);
}

.create-tournament-form .form-hint {
    color: #888;
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

.create-tournament-form button[type="submit"] {
    margin-top: 1rem;
}
```

**Step 3: Test form display**

Visit: `http://127.0.0.1:5001/admin`
Expected:
- Form appears with all fields
- Court selection updates player count hint
- Form styling matches season management

**Step 4: Commit**

```bash
git add templates/admin_dashboard.html static/css/admin.css
git commit -m "feat(admin): add tournament creation form to Seasons tab

Form includes:
- Tournament name input
- Courts dropdown (1-10 courts)
- Player names textarea
- Dynamic player count hint
- Styled to match admin theme
"
```

---

### Task 4: Create Admin Tournament Creation Route

**Files:**
- Modify: `app.py` (add new route after admin_delete_season around line 1734)

**Step 1: Add tournament creation route**

Insert after `admin_delete_season` route (around line 1734):

```python
@app.route('/admin/tournaments/create', methods=['POST'])
def admin_create_tournament():
    """Create new tournament from admin dashboard (ADMIN)"""
    db = get_db_connection()

    # Check for current season
    current_season = get_current_season(db)
    if not current_season:
        flash('No active season. Please create or activate a season first.')
        return redirect('/admin')

    tournament_name = request.form.get('tournament_name')
    num_courts = int(request.form.get('num_courts'))
    player_names = request.form.get('players').strip().split('\n')

    # Clean up player names
    player_names = [name.strip() for name in player_names if name.strip()]

    # Validate player count
    required_players = num_courts * 4
    if len(player_names) != required_players:
        flash(f'Need exactly {required_players} players for {num_courts} courts. You entered {len(player_names)} players.')
        return redirect('/admin')

    # Create tournament
    cursor = db.execute(
        'INSERT INTO tournaments (name, num_courts, status, season_id) VALUES (?, ?, ?, ?)',
        (tournament_name, num_courts, 'setup', current_season['id'])
    )
    tournament_id = cursor.lastrowid
    db.commit()

    # Add players to Phase 3 player_registry and link to tournament
    for name in player_names:
        parts = name.strip().split(' ', 1)
        first_name = parts[0] if len(parts) > 0 else ''
        last_name = parts[1] if len(parts) > 1 else ''

        # Check if player already exists
        existing_player = db.execute(
            'SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?',
            (first_name, last_name)
        ).fetchone()

        if existing_player:
            player_id = existing_player['id']
        else:
            cursor = db.execute(
                'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
                (first_name, last_name)
            )
            player_id = cursor.lastrowid

        # Link player to tournament
        try:
            db.execute(
                'INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)',
                (tournament_id, player_id)
            )
        except sqlite3.IntegrityError:
            pass  # Player already linked

    db.commit()

    flash(f'Tournament "{tournament_name}" created successfully!')

    # Redirect to court selection to start Round 1
    return redirect(url_for('court_selection', tournament_id=tournament_id))
```

**Step 2: Test tournament creation**

Run: Visit admin, fill form with:
- Name: "Test Tournament"
- Courts: 3
- Players: 12 names (one per line)

Expected:
- Tournament created
- Redirects to court selection
- Flash message shows success

**Step 3: Verify in database**

```bash
sqlite3 instance/padel.db "SELECT * FROM tournaments WHERE name='Test Tournament';"
```
Expected: Tournament record exists with status='setup'

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat(admin): add tournament creation route

POST /admin/tournaments/create:
- Validates active season exists
- Validates player count (courts × 4)
- Creates tournament with status='setup'
- Adds players to registry and links to tournament
- Redirects to court selection to start Round 1
"
```

---

## Phase 2: New Public Templates

### Task 5: Create Tournament Selection Template

**Files:**
- Create: `templates/tournament_selection.html`

**Step 1: Create tournament selection template**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Tournament - Padel King of the Court</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .selection-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        .selection-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .tournament-cards {
            display: grid;
            gap: 1.5rem;
        }
        .tournament-card {
            background: white;
            border: 2px solid #3498db;
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        .tournament-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #2980b9;
        }
        .tournament-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .tournament-info {
            color: #666;
            margin: 0.5rem 0;
            font-size: 0.95rem;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-left: 0.5rem;
        }
        .status-active {
            background-color: #22c55e;
            color: white;
        }
        .status-setup {
            background-color: #ff9800;
            color: white;
        }
        .enter-btn {
            margin-top: 1rem;
        }
        @media (max-width: 768px) {
            .selection-container {
                padding: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="selection-container">
        <div class="selection-header">
            <h1>Select Active Tournament</h1>
            <p>Multiple tournaments are running. Choose one to enter scores:</p>
        </div>

        <div class="tournament-cards">
            {% for tournament in tournaments %}
            <div class="tournament-card">
                <h3>
                    {{ tournament['name'] }}
                    {% if tournament['status'] == 'active' %}
                    <span class="status-badge status-active">Active</span>
                    {% else %}
                    <span class="status-badge status-setup">Setup</span>
                    {% endif %}
                </h3>
                <p class="tournament-info">Created: {{ tournament['created_at'][:10] }}</p>
                <a href="{{ url_for('court_selection', tournament_id=tournament['id']) }}" class="btn-primary enter-btn">
                    Enter Scores
                </a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

**Step 2: Test template (manual)**

Create temporary test route:
```python
@app.route('/test/selection')
def test_selection():
    tournaments = [
        {'id': 1, 'name': 'Tournament A', 'status': 'active', 'created_at': '2025-12-31'},
        {'id': 2, 'name': 'Tournament B', 'status': 'setup', 'created_at': '2025-12-31'}
    ]
    return render_template('tournament_selection.html', tournaments=tournaments)
```

Visit: `http://127.0.0.1:5001/test/selection`
Expected: Cards display correctly, mobile responsive

**Step 3: Commit**

```bash
git add templates/tournament_selection.html
git commit -m "feat: add tournament selection template

Template for multiple active tournaments case.
Shows cards with name, status, date, and 'Enter Scores' button.
Mobile responsive design.
"
```

---

### Task 6: Create No Active Tournament Template

**Files:**
- Create: `templates/no_active_tournament.html`

**Step 1: Create no active tournament template**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No Active Tournament - Padel King of the Court</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .message-container {
            max-width: 600px;
            margin: 4rem auto;
            padding: 2rem;
            text-align: center;
        }
        .message-box {
            background: #f9f9f9;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 3rem 2rem;
        }
        .message-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
        }
        .message-title {
            color: #2c3e50;
            font-size: 1.8rem;
            margin-bottom: 1rem;
        }
        .message-text {
            color: #666;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        .season-info {
            background: white;
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 2rem;
            color: #555;
        }
        .footer-link {
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 1px solid #e0e0e0;
        }
        .footer-link a {
            color: #3498db;
            text-decoration: none;
            font-size: 0.95rem;
        }
        .footer-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="message-container">
        <div class="message-box">
            <div class="message-icon">🎾</div>
            <h1 class="message-title">No Active Tournament</h1>
            <p class="message-text">
                There are currently no tournaments running.
            </p>

            {% if season %}
            <div class="season-info">
                <strong>{{ season.name }}</strong><br>
                {{ season.tournament_count }} tournament{{ 's' if season.tournament_count != 1 else '' }} played this season
            </div>
            {% endif %}

            <a href="{{ url_for('season_leaderboard') }}" class="btn-primary">
                View Season Leaderboard
            </a>

            <div class="footer-link">
                <a href="{{ url_for('admin_dashboard') }}">Admin Dashboard</a>
            </div>
        </div>
    </div>
</body>
</html>
```

**Step 2: Test template (manual)**

Create temporary test route:
```python
@app.route('/test/noactive')
def test_noactive():
    season = {'name': 'Winter 2025', 'tournament_count': 5}
    return render_template('no_active_tournament.html', season=season)
```

Visit: `http://127.0.0.1:5001/test/noactive`
Expected: Centered message, season info, leaderboard button

**Step 3: Commit**

```bash
git add templates/no_active_tournament.html
git commit -m "feat: add no active tournament template

Template for zero active tournaments case.
Shows message, season info, leaderboard link, admin link.
Clean centered design.
"
```

---

## Phase 3: Smart Home Page Redirect

### Task 7: Implement Smart Home Page Logic

**Files:**
- Modify: `app.py:172-202` (index function)

**Step 1: Update index route with smart redirect logic**

Replace the entire `index()` function (around line 172):

```python
@app.route('/')
def index():
    """Home page - smart entry point for scorekeepers/players"""
    db = get_db()

    # Query active tournaments (setup or active status)
    active_tournaments = db.execute(
        '''SELECT * FROM tournaments
           WHERE status IN ('active', 'setup')
           ORDER BY created_at DESC'''
    ).fetchall()

    active_count = len(active_tournaments)

    # Case 1: Exactly 1 active tournament - auto-redirect
    if active_count == 1:
        tournament_id = active_tournaments[0]['id']
        return redirect(url_for('court_selection', tournament_id=tournament_id))

    # Case 2: Multiple active tournaments - show selection
    elif active_count > 1:
        return render_template('tournament_selection.html', tournaments=active_tournaments)

    # Case 3: No active tournaments - show message
    else:
        current_season = get_current_season(db)

        # Get tournament count for season info
        season_info = None
        if current_season:
            tournament_count = db.execute(
                "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
                (current_season['id'],)
            ).fetchone()['count']

            season_info = {
                'name': current_season['name'],
                'tournament_count': tournament_count
            }

        return render_template('no_active_tournament.html', season=season_info)
```

**Step 2: Test all three cases**

**Test Case 1: Zero active tournaments**
```bash
# Delete/complete all active tournaments via admin
# Visit http://127.0.0.1:5001/
```
Expected: Shows "No Active Tournament" page

**Test Case 2: One active tournament**
```bash
# Create one tournament via admin (status='setup')
# Visit http://127.0.0.1:5001/
```
Expected: Auto-redirects to court selection

**Test Case 3: Multiple active tournaments**
```bash
# Create second tournament via admin
# Visit http://127.0.0.1:5001/
```
Expected: Shows tournament selection page

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: implement smart home page redirect

Home page now acts as intelligent entry point:
- 0 active tournaments → show message + leaderboard link
- 1 active tournament → auto-redirect to court selection
- 2+ active tournaments → show selection page

Queries tournaments WHERE status IN ('active', 'setup').
Breaking change: removes old tournament list display.
"
```

---

## Phase 4: Cleanup Old Routes

### Task 8: Remove Old Tournament Creation Route

**Files:**
- Modify: `app.py` (remove GET /setup route, keep POST temporarily)

**Step 1: Find and comment out GET /setup route**

Search for `@app.route('/setup')` (around line 276) and comment it out:

```python
# OLD ROUTE - REMOVED (tournament creation moved to admin)
# @app.route('/setup')
# def setup_tournament():
#     """Setup new tournament and add players"""
#     if request.method == 'GET':
#         return render_template('setup_tournament.html')
#     ...
```

Keep the `if request.method == 'POST':` block for now (backward compatibility).

**Step 2: Test that GET /setup returns 404**

Visit: `http://127.0.0.1:5001/setup`
Expected: 404 Not Found

**Step 3: Verify admin tournament creation still works**

Visit: `http://127.0.0.1:5001/admin`
Create tournament
Expected: Works correctly

**Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: remove GET /setup route

Tournament creation form no longer accessible via /setup.
Kept POST handler temporarily for backward compatibility.
All tournament creation now through admin dashboard.
"
```

---

### Task 9: Update Tests for New Routes

**Files:**
- Modify: `tests/test_home_page.py`
- Modify: `tests/test_tournament_creation.py` (if exists)

**Step 1: Update home page test**

File: `tests/test_home_page.py`

Replace `test_home_page_has_admin_dashboard_link` test:

```python
def test_home_page_with_no_active_tournaments(client):
    """Test home page shows message when no active tournaments"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'No Active Tournament' in response.data
    assert b'View Season Leaderboard' in response.data

def test_home_page_redirects_with_one_active_tournament(client):
    """Test home page redirects when exactly one active tournament"""
    # Create season and tournament
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO seasons (name, is_current) VALUES ('Test', 1)")
        season_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO tournaments (name, num_courts, status, season_id) VALUES (?, ?, ?, ?)",
            ('Active Tournament', 3, 'active', season_id)
        )
        tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert f'/tournament/{tournament_id}/courts' in response.location
```

**Step 2: Run tests**

```bash
venv/bin/pytest tests/test_home_page.py -v
```
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_home_page.py
git commit -m "test: update home page tests for smart redirect

Tests now verify:
- No active tournaments → shows message
- One active tournament → redirects to court selection
- Removed test for 'Start Tournament' button (moved to admin)
"
```

---

### Task 10: Remove Old Setup Template

**Files:**
- Delete: `templates/setup_tournament.html` (if exists)

**Step 1: Check if template exists**

```bash
ls templates/setup_tournament.html 2>/dev/null || echo "Template doesn't exist"
```

**Step 2: If exists, remove it**

```bash
git rm templates/setup_tournament.html
```

**Step 3: Verify app still works**

Visit: `http://127.0.0.1:5001/`
Visit: `http://127.0.0.1:5001/admin`

Expected: Everything works, no broken template references

**Step 4: Commit**

```bash
git commit -m "refactor: remove old setup tournament template

Template no longer needed - tournament creation now in admin.
All functionality moved to admin_dashboard.html.
"
```

---

### Task 11: Final Cleanup and Verification

**Files:**
- Modify: `app.py` (remove POST /setup if not needed)

**Step 1: Remove remaining old route code**

Search for and remove the entire old `setup_tournament` function (both GET and POST):

```python
# DELETE THIS ENTIRE FUNCTION (around line 210-276)
# @app.route('/setup', methods=['GET', 'POST'])
# def setup_tournament():
#     ...entire function...
```

**Step 2: Search for any remaining /setup references**

```bash
grep -r "url_for('setup_tournament')" templates/ || echo "No references found"
grep -r "/setup" templates/ || echo "No references found"
```

Expected: No references found

**Step 3: Run full test suite**

```bash
venv/bin/pytest -v
```

Expected: All relevant tests pass (ignore pre-existing failures)

**Step 4: Manual end-to-end test**

1. Visit home page → should show "No Active Tournament" (if none exist)
2. Login to admin → go to Seasons tab
3. Create tournament with 12 players, 3 courts
4. Submit → should redirect to court selection
5. Go back to home page → should auto-redirect to court selection
6. Create second tournament via admin
7. Go to home page → should show tournament selection
8. Complete/delete all tournaments
9. Go to home page → should show "No Active Tournament"

**Step 5: Commit**

```bash
git add app.py
git commit -m "refactor: complete removal of old tournament creation route

Removed POST /setup route (no longer needed).
All tournament creation now exclusively through admin.

Phase 4 complete:
✅ Old routes removed
✅ Templates cleaned up
✅ Tests updated
✅ End-to-end verified
"
```

---

## Final Verification

### Task 12: Comprehensive Testing

**Manual Test Checklist:**

**Admin Tournament Creation:**
- [ ] Login to admin dashboard
- [ ] Navigate to Seasons tab
- [ ] Create tournament form displays correctly
- [ ] Create tournament with valid data
- [ ] Tournament appears in tournaments table
- [ ] Status badge displays correctly
- [ ] View button navigates to court selection
- [ ] Invalid player count shows error
- [ ] No active season hides form

**Home Page Smart Redirect:**
- [ ] No active tournaments → shows message + leaderboard link
- [ ] One active tournament → auto-redirects to court selection
- [ ] Multiple active tournaments → shows selection page
- [ ] Selection cards display correctly
- [ ] "Enter Scores" buttons work
- [ ] Status badges display correctly

**Public Access:**
- [ ] Non-admin can access home page
- [ ] Non-admin can access score entry
- [ ] Non-admin can view leaderboards
- [ ] Non-admin CANNOT access /admin/tournaments/create

**Edge Cases:**
- [ ] Complete tournament → home page updates correctly
- [ ] Delete last active tournament → home page shows message
- [ ] Session timeout during creation → redirects to login

**Step: Document any issues found**

Create `TESTING_NOTES.md` if issues found:
```markdown
# Testing Notes - Move Tournament Creation

## Issues Found
- [ ] Issue 1: Description
- [ ] Issue 2: Description

## Resolved
- [x] Issue: Description - Fixed by: commit hash
```

---

## Summary

**Implementation complete!**

**Changes:**
- ✅ Phase 1: Admin tournament creation in Seasons tab
- ✅ Phase 2: New public templates (selection, no active)
- ✅ Phase 3: Smart home page redirect
- ✅ Phase 4: Old routes removed

**Files Modified:**
- `app.py` - Routes updated
- `templates/admin_dashboard.html` - Tournaments table + creation form
- `static/css/admin.css` - Tournament management styles
- `templates/tournament_selection.html` - New template
- `templates/no_active_tournament.html` - New template
- `tests/test_home_page.py` - Updated tests

**Files Removed:**
- `templates/setup_tournament.html` (if existed)

**Security:**
- Tournament creation requires admin authentication ✅
- Public routes remain accessible (score entry, viewing) ✅

**User Experience:**
- Admin: All management in one place ✅
- Players: Instant access to scoring ✅
- Smart redirect eliminates navigation ✅
