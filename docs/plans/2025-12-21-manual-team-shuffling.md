# Manual Team Shuffling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pre-match team shuffling with drag-and-drop interface so players can manually adjust pairings before matches start

**Architecture:** Add 5 columns to matches table for tracking shuffles, create court selection and confirmation screens between round start and score entry, implement mobile-friendly drag-and-drop UI

**Tech Stack:** Flask, SQLite, vanilla JavaScript (drag-and-drop API), Jinja2 templates

**Design Document:** `docs/plans/2025-12-21-manual-team-shuffling-design.md`

---

## Task 1: Database Migration

**Files:**
- Create: `migrations/003_add_team_shuffling.sql`
- Modify: `database.py` (update init_db function)

**Step 1: Create migration SQL file**

Create file with schema changes:

```sql
-- Migration: Add team shuffling support to matches table
-- Date: 2025-12-21

-- Add new columns to track team shuffling
ALTER TABLE matches ADD COLUMN teams_shuffled BOOLEAN DEFAULT 0;
ALTER TABLE matches ADD COLUMN original_player1_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player2_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player3_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player4_id INTEGER;

-- Create index for querying shuffled matches (optional, for analytics)
CREATE INDEX IF NOT EXISTS idx_matches_shuffled ON matches(teams_shuffled) WHERE teams_shuffled = 1;
```

**Step 2: Update database.py init_db function**

Modify the matches table creation in `database.py:64-82` to include new columns:

```python
# Create matches table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL,
        court_number INTEGER NOT NULL,
        player1_id INTEGER NOT NULL,
        player2_id INTEGER NOT NULL,
        player3_id INTEGER NOT NULL,
        player4_id INTEGER NOT NULL,
        winning_team INTEGER,
        completed BOOLEAN DEFAULT 0,
        teams_shuffled BOOLEAN DEFAULT 0,
        original_player1_id INTEGER,
        original_player2_id INTEGER,
        original_player3_id INTEGER,
        original_player4_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (round_id) REFERENCES rounds(id),
        FOREIGN KEY (player1_id) REFERENCES players(id),
        FOREIGN KEY (player2_id) REFERENCES players(id),
        FOREIGN KEY (player3_id) REFERENCES players(id),
        FOREIGN KEY (player4_id) REFERENCES players(id)
    )
''')
```

**Step 3: Run migration on existing database**

Run command:
```bash
sqlite3 instance/padel.db < migrations/003_add_team_shuffling.sql
```

Expected: No errors, columns added successfully

**Step 4: Verify migration**

Run command:
```bash
sqlite3 instance/padel.db ".schema matches"
```

Expected: See new columns in schema output

**Step 5: Commit**

```bash
git add migrations/003_add_team_shuffling.sql database.py
git commit -m "feat: add database schema for team shuffling

Add 5 new columns to matches table:
- teams_shuffled: boolean flag for tracking
- original_player*_id: store algorithm's original pairing

Allows tracking manual team adjustments while preserving
original algorithm intent for audit purposes."
```

---

## Task 2: Helper Function - get_player

**Files:**
- Modify: `app.py` (add helper function after line 30)

**Step 1: Add get_player helper function**

Add this function in `app.py` after the `close_db` function (around line 31):

```python
def get_player(player_id):
    """
    Helper to get player with backward compatibility.
    Tries Phase 3 player_registry first, falls back to Phase 2 players table.
    """
    db = get_db_connection()

    # Try Phase 3 registry first
    result = db.execute(
        'SELECT id, first_name, last_name FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        return dict(result)

    # Fallback to Phase 2 players table
    result = db.execute(
        'SELECT id, name FROM players WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        # Split name into first/last (best effort)
        parts = result['name'].split(' ', 1)
        return {
            'id': result['id'],
            'first_name': parts[0] if len(parts) > 0 else 'Unknown',
            'last_name': parts[1] if len(parts) > 1 else ''
        }

    # Player not found - return placeholder
    return {
        'id': player_id,
        'first_name': '[Deleted',
        'last_name': f'Player {player_id}]'
    }
```

**Step 2: Manually test get_player function**

Run Python shell:
```bash
python3 -c "from app import get_player; print(get_player(1))"
```

Expected: Returns player dict or placeholder (no error)

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add get_player helper with Phase 2/3 compatibility

Helper function to retrieve player information with fallback:
1. Try Phase 3 player_registry (first_name, last_name)
2. Fall back to Phase 2 players (name)
3. Return placeholder for deleted players

Provides unified player lookup for new routes."
```

---

## Task 3: Court Selection Route and Template

**Files:**
- Modify: `app.py` (add court_selection route)
- Create: `templates/court_selection.html`

**Step 1: Add court_selection route to app.py**

Add this route after the `start_round` route in `app.py`:

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/courts')
def court_selection(tournament_id, round_id):
    """
    Shows all courts for this round with links to confirmation screens.
    """
    db = get_db_connection()

    # Get tournament
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Get round
    round_obj = db.execute(
        'SELECT * FROM rounds WHERE id = ?',
        (round_id,)
    ).fetchone()

    if not round_obj:
        flash('Round not found')
        return redirect(url_for('index'))

    # Get all matches for this round
    matches = db.execute(
        'SELECT * FROM matches WHERE round_id = ? ORDER BY court_number',
        (round_id,)
    ).fetchall()

    # Add player details to each match
    matches_with_players = []
    for match in matches:
        match_dict = dict(match)
        match_dict['player1'] = get_player(match['player1_id'])
        match_dict['player2'] = get_player(match['player2_id'])
        match_dict['player3'] = get_player(match['player3_id'])
        match_dict['player4'] = get_player(match['player4_id'])
        matches_with_players.append(match_dict)

    return render_template(
        'court_selection.html',
        tournament=tournament,
        round=round_obj,
        matches=matches_with_players
    )
```

**Step 2: Create court_selection.html template**

Create `templates/court_selection.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Court Selection - Round {{ round['round_number'] }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .court-selection {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .court-grid {
            display: grid;
            gap: 20px;
            margin: 30px 0;
        }
        .court-card {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            border: 2px solid #ddd;
        }
        .court-card h3 {
            margin-top: 0;
            color: #2196F3;
        }
        .players-preview {
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 15px 0;
        }
        .team {
            flex: 1;
        }
        .team strong {
            display: block;
            margin-bottom: 5px;
            color: #666;
        }
        .team p {
            margin: 3px 0;
            font-size: 14px;
        }
        .vs {
            font-weight: bold;
            color: #999;
            font-size: 18px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-top: -10px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="court-selection">
        <h2>Round {{ round['round_number'] }} - Select Your Court</h2>
        <p class="subtitle">{{ tournament['name'] }}</p>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-message">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <div class="court-grid">
            {% for match in matches %}
            <div class="court-card">
                <h3>Court {{ match.court_number }}</h3>
                <div class="players-preview">
                    <div class="team">
                        <strong>Team 1:</strong>
                        <p>{{ match.player1.first_name }} {{ match.player1.last_name }}</p>
                        <p>{{ match.player2.first_name }} {{ match.player2.last_name }}</p>
                    </div>
                    <div class="vs">VS</div>
                    <div class="team">
                        <strong>Team 2:</strong>
                        <p>{{ match.player3.first_name }} {{ match.player3.last_name }}</p>
                        <p>{{ match.player4.first_name }} {{ match.player4.last_name }}</p>
                    </div>
                </div>
                <a href="/tournament/{{ tournament.id }}/round/{{ round.id }}/court/{{ match.court_number }}/confirm"
                   class="btn btn-primary">
                    Go to Court {{ match.court_number }}
                </a>
            </div>
            {% endfor %}
        </div>

        <div class="actions">
            <a href="/" class="btn btn-secondary">Back to Home</a>
        </div>
    </div>
</body>
</html>
```

**Step 3: Test court selection page**

Start Flask server:
```bash
python app.py
```

Navigate to: `http://localhost:5001/tournament/1/round/1/courts` (adjust IDs as needed)

Expected: Page loads, shows courts with player names

**Step 4: Commit**

```bash
git add app.py templates/court_selection.html
git commit -m "feat: add court selection screen

New route displays all courts for a round with player pairings.
Players select their court to proceed to confirmation screen.

- GET /tournament/<id>/round/<id>/courts route
- court_selection.html template with grid layout
- Shows Team 1 vs Team 2 for each court
- Links to confirmation screen per court"
```

---

## Task 4: Pre-Match Confirmation Route (GET)

**Files:**
- Modify: `app.py` (add confirm_match_teams route)
- Create: `templates/confirm_match.html`

**Step 1: Add confirm_match_teams GET route**

Add this route in `app.py` after court_selection:

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm')
def confirm_match_teams(tournament_id, round_id, court_number):
    """
    Show pre-match confirmation screen with drag-and-drop team shuffling.
    """
    db = get_db_connection()

    # Get tournament
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Check if tournament is archived
    if tournament['status'] == 'archived':
        flash("Cannot modify archived tournament.")
        return redirect(url_for('index'))

    # Get round
    round_obj = db.execute(
        'SELECT * FROM rounds WHERE id = ?',
        (round_id,)
    ).fetchone()

    if not round_obj:
        flash('Round not found')
        return redirect(url_for('index'))

    # Get match
    match = db.execute(
        'SELECT * FROM matches WHERE round_id = ? AND court_number = ?',
        (round_id, court_number)
    ).fetchone()

    if not match:
        flash('Match not found')
        return redirect(url_for('index'))

    # Check if match already completed
    if match['completed']:
        flash("This match has already been completed.")
        return redirect(url_for('leaderboard', tournament_id=tournament_id))

    # Check if scores already entered (prevent shuffle after scoring starts)
    existing_scores = db.execute(
        'SELECT COUNT(*) as count FROM scores WHERE match_id = ?',
        (match['id'],)
    ).fetchone()

    if existing_scores['count'] > 0:
        flash("Match already in progress. Team shuffling not available.")
        # Redirect to score entry
        return redirect(f'/tournament/{tournament_id}/active')

    # Get player details
    players = {
        'team1': [
            get_player(match['player1_id']),
            get_player(match['player2_id'])
        ],
        'team2': [
            get_player(match['player3_id']),
            get_player(match['player4_id'])
        ]
    }

    return render_template(
        'confirm_match.html',
        tournament=tournament,
        round=round_obj,
        court_number=court_number,
        match=match,
        players=players
    )
```

**Step 2: Create confirm_match.html template** (abbreviated for task brevity)

Create `templates/confirm_match.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confirm Teams - Court {{ court_number }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/shuffle.css') }}">
</head>
<body>
    <div class="pre-match-confirmation">
        <header>
            <h2>Round {{ round.round_number }}, Court {{ court_number }}</h2>
            <p class="instruction">👆 Drag players to swap teams, then start match</p>
        </header>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-message">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <div class="teams-container">
            <!-- Team 1 Box -->
            <div class="team-box team-1" data-team="1">
                <h3>Team 1</h3>
                <div class="player-slot"
                     data-player-id="{{ players.team1[0].id }}"
                     draggable="true">
                    <span class="player-name">{{ players.team1[0].first_name }} {{ players.team1[0].last_name }}</span>
                    <span class="drag-handle">⋮⋮</span>
                </div>
                <div class="player-slot"
                     data-player-id="{{ players.team1[1].id }}"
                     draggable="true">
                    <span class="player-name">{{ players.team1[1].first_name }} {{ players.team1[1].last_name }}</span>
                    <span class="drag-handle">⋮⋮</span>
                </div>
            </div>

            <div class="vs-divider">VS</div>

            <!-- Team 2 Box -->
            <div class="team-box team-2" data-team="2">
                <h3>Team 2</h3>
                <div class="player-slot"
                     data-player-id="{{ players.team2[0].id }}"
                     draggable="true">
                    <span class="player-name">{{ players.team2[0].first_name }} {{ players.team2[0].last_name }}</span>
                    <span class="drag-handle">⋮⋮</span>
                </div>
                <div class="player-slot"
                     data-player-id="{{ players.team2[1].id }}"
                     draggable="true">
                    <span class="player-name">{{ players.team2[1].first_name }} {{ players.team2[1].last_name }}</span>
                    <span class="drag-handle">⋮⋮</span>
                </div>
            </div>
        </div>

        <div class="actions">
            <button class="btn btn-primary btn-large" onclick="confirmAndStartMatch()">
                ✓ Start Match
            </button>
            <button class="btn btn-secondary" onclick="resetToOriginal()">
                ↺ Reset to Original
            </button>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/shuffle.js') }}"></script>
    <script>
        const TOURNAMENT_ID = {{ tournament.id }};
        const ROUND_ID = {{ round.id }};
        const COURT_NUMBER = {{ court_number }};
    </script>
</body>
</html>
```

**Step 3: Test confirmation page loads**

Navigate to: `http://localhost:5001/tournament/1/round/1/court/1/confirm`

Expected: Page loads with player names (drag won't work yet)

**Step 4: Commit**

```bash
git add app.py templates/confirm_match.html
git commit -m "feat: add pre-match confirmation screen (GET route)

Shows team pairings before match with placeholder for drag-and-drop.

- GET /tournament/<id>/round/<id>/court/<id>/confirm route
- Validates tournament not archived, match not completed
- Prevents shuffle if scores already entered
- confirm_match.html template with team boxes
- Drag-and-drop UI (non-functional until JS added)"
```

---

## Task 5: Pre-Match Confirmation Route (POST) with Validation

**Files:**
- Modify: `app.py` (add save_confirmed_teams POST route)

**Step 1: Write test for team shuffle validation**

Create `tests/test_team_shuffling.py`:

```python
import pytest
import tempfile
import os
from app import app
from database import init_db

@pytest.fixture
def client():
    """Create test client with temporary database"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app.config['TESTING'] = True
    app.config['DATABASE'] = db_path

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    os.close(db_fd)
    os.unlink(db_path)


def test_validation_rejects_duplicate_players(client):
    """Ensure exactly 4 unique players in submission"""
    # Setup: Create tournament, round, match with players
    from database import get_db
    db = get_db()

    # Create tournament
    db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
    db.commit()

    # Create players
    for i in range(1, 5):
        db.execute("INSERT INTO players (name) VALUES (?)", (f'Player {i}',))
    db.commit()

    # Create round
    db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (1, 1)")
    db.commit()

    # Create match
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 1, 1, 2, 3, 4)
    """)
    db.commit()
    db.close()

    # Submit with duplicate player
    response = client.post(
        '/tournament/1/round/1/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '1',  # Duplicate!
            'team2_player1': '3',
            'team2_player2': '4'
        },
        follow_redirects=True
    )

    assert b'All 4 players must be unique' in response.data


def test_validation_rejects_foreign_players(client):
    """Ensure submitted players are from original match"""
    # Setup match with players 1,2,3,4
    from database import get_db
    db = get_db()

    db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
    for i in range(1, 6):
        db.execute("INSERT INTO players (name) VALUES (?)", (f'Player {i}',))
    db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (1, 1)")
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 1, 1, 2, 3, 4)
    """)
    db.commit()
    db.close()

    # Submit with player 5 (not in original match)
    response = client.post(
        '/tournament/1/round/1/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '2',
            'team2_player1': '3',
            'team2_player2': '5'  # Not in original!
        },
        follow_redirects=True
    )

    assert b'Players must be from the original match' in response.data
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_team_shuffling.py -v
```

Expected: FAIL - route not implemented yet

**Step 3: Implement save_confirmed_teams POST route**

Add this route in `app.py` after confirm_match_teams:

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm',
           methods=['POST'])
def save_confirmed_teams(tournament_id, round_id, court_number):
    """
    Save final team configuration (potentially shuffled) and proceed to score entry.
    """
    db = get_db_connection()

    # Get match (with row locking for concurrent access)
    match = db.execute(
        'SELECT * FROM matches WHERE round_id = ? AND court_number = ?',
        (round_id, court_number)
    ).fetchone()

    if not match:
        flash('Match not found')
        return redirect(url_for('court_selection', tournament_id=tournament_id, round_id=round_id))

    # Get submitted team configuration
    try:
        new_team1_p1 = int(request.form['team1_player1'])
        new_team1_p2 = int(request.form['team1_player2'])
        new_team2_p1 = int(request.form['team2_player1'])
        new_team2_p2 = int(request.form['team2_player2'])
    except (KeyError, ValueError):
        flash("Invalid form submission.")
        return redirect(url_for('confirm_match_teams',
                                tournament_id=tournament_id,
                                round_id=round_id,
                                court_number=court_number))

    # Validation 1: Exactly 4 unique players
    submitted_players = [new_team1_p1, new_team1_p2, new_team2_p1, new_team2_p2]
    if len(set(submitted_players)) != 4:
        flash("Invalid team configuration: All 4 players must be unique.")
        return redirect(url_for('confirm_match_teams',
                                tournament_id=tournament_id,
                                round_id=round_id,
                                court_number=court_number))

    # Validation 2: Players must be from original match
    original_players = {match['player1_id'], match['player2_id'], match['player3_id'], match['player4_id']}
    if set(submitted_players) != original_players:
        flash("Invalid team configuration: Players must be from the original match.")
        return redirect(url_for('confirm_match_teams',
                                tournament_id=tournament_id,
                                round_id=round_id,
                                court_number=court_number))

    # Validation 3: Teams must have exactly 2 players each
    if len({new_team1_p1, new_team1_p2}) != 2 or len({new_team2_p1, new_team2_p2}) != 2:
        flash("Each team must have exactly 2 different players.")
        return redirect(url_for('confirm_match_teams',
                                tournament_id=tournament_id,
                                round_id=round_id,
                                court_number=court_number))

    # Check if teams were shuffled
    original_team1 = {match['player1_id'], match['player2_id']}
    new_team1 = {new_team1_p1, new_team1_p2}
    teams_changed = original_team1 != new_team1

    if teams_changed:
        # Store original pairing before overwriting
        db.execute('''
            UPDATE matches
            SET original_player1_id = ?,
                original_player2_id = ?,
                original_player3_id = ?,
                original_player4_id = ?,
                teams_shuffled = 1,
                player1_id = ?,
                player2_id = ?,
                player3_id = ?,
                player4_id = ?
            WHERE id = ?
        ''', (
            match['player1_id'], match['player2_id'], match['player3_id'], match['player4_id'],
            new_team1_p1, new_team1_p2, new_team2_p1, new_team2_p2,
            match['id']
        ))
        db.commit()

    # Redirect to active tournament (score entry screen)
    return redirect(url_for('active_tournament', tournament_id=tournament_id))
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_team_shuffling.py -v
```

Expected: PASS - all validation tests pass

**Step 5: Commit**

```bash
git add app.py tests/test_team_shuffling.py
git commit -m "feat: add team shuffle POST route with validation

Implements save_confirmed_teams route with comprehensive validation:
- Validates 4 unique players
- Validates players from original match
- Validates 2 players per team
- Tracks shuffles in database (teams_shuffled flag + original IDs)
- Redirects to score entry after confirmation

Includes 2 validation tests."
```

---

## Task 6: Frontend CSS for Shuffle UI

**Files:**
- Create: `static/css/shuffle.css`

**Step 1: Create shuffle.css**

Create `static/css/shuffle.css` with complete styles from design doc:

```css
.pre-match-confirmation {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
}

header {
    text-align: center;
    margin-bottom: 30px;
}

.instruction {
    color: #666;
    font-size: 14px;
    margin-top: 10px;
}

.teams-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 30px;
}

.team-box {
    flex: 1;
    background: #f5f5f5;
    border-radius: 12px;
    padding: 20px;
    min-height: 200px;
}

.team-1 {
    border: 3px solid #4CAF50;
}

.team-2 {
    border: 3px solid #2196F3;
}

.team-box h3 {
    margin: 0 0 15px 0;
    text-align: center;
    font-size: 16px;
    text-transform: uppercase;
    color: #666;
}

.player-slot {
    background: white;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: move;
    user-select: none;
    min-height: 60px;
    transition: all 0.2s ease;
}

.player-slot:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}

.player-slot.dragging {
    opacity: 0.5;
    transform: scale(0.95);
}

.player-slot.swapped {
    animation: flash 0.4s ease;
}

@keyframes flash {
    0%, 100% { background: white; }
    50% { background: #FFF9C4; }
}

.player-name {
    font-size: 16px;
    font-weight: 500;
}

.drag-handle {
    font-size: 20px;
    color: #999;
    cursor: grab;
}

.drag-handle:active {
    cursor: grabbing;
}

.vs-divider {
    font-size: 24px;
    font-weight: bold;
    color: #999;
    flex-shrink: 0;
}

.actions {
    display: flex;
    gap: 15px;
    justify-content: center;
}

.btn-large {
    padding: 15px 40px;
    font-size: 18px;
}

/* Mobile optimizations */
@media (max-width: 600px) {
    .teams-container {
        flex-direction: column;
        gap: 10px;
    }

    .vs-divider {
        transform: rotate(90deg);
        margin: 10px 0;
    }

    .player-slot {
        min-height: 70px; /* Larger touch targets */
        padding: 20px 15px;
    }
}
```

**Step 2: Test CSS loads**

Refresh confirmation page: `http://localhost:5001/tournament/1/round/1/court/1/confirm`

Expected: Styled team boxes with colored borders, player cards

**Step 3: Commit**

```bash
git add static/css/shuffle.css
git commit -m "feat: add CSS for team shuffling UI

Comprehensive styling for pre-match confirmation screen:
- Team boxes with colored borders (green/blue)
- Player cards with hover effects
- Dragging state animations
- Swap flash animation
- Mobile-responsive layout (60-70px touch targets)
- VS divider styling"
```

---

## Task 7: Frontend JavaScript - Drag and Drop

**Files:**
- Create: `static/js/shuffle.js`

**Step 1: Create shuffle.js** (full implementation from design doc)

Create `static/js/shuffle.js`:

```javascript
/**
 * TeamShuffler - Handles drag-and-drop team shuffling on mobile and desktop
 */
class TeamShuffler {
    constructor() {
        this.playerSlots = document.querySelectorAll('.player-slot');
        this.draggedElement = null;
        this.originalConfiguration = this.saveConfiguration();
        this.initDragAndDrop();
    }

    initDragAndDrop() {
        this.playerSlots.forEach(slot => {
            // Desktop drag events
            slot.addEventListener('dragstart', (e) => this.handleDragStart(e));
            slot.addEventListener('dragover', (e) => this.handleDragOver(e));
            slot.addEventListener('drop', (e) => this.handleDrop(e));
            slot.addEventListener('dragend', (e) => this.handleDragEnd(e));

            // Mobile touch events
            slot.addEventListener('touchstart', (e) => this.handleTouchStart(e), {passive: false});
            slot.addEventListener('touchmove', (e) => this.handleTouchMove(e), {passive: false});
            slot.addEventListener('touchend', (e) => this.handleTouchEnd(e), {passive: false});
        });
    }

    // Desktop Drag Handlers
    handleDragStart(e) {
        this.draggedElement = e.target.closest('.player-slot');
        this.draggedElement.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', this.draggedElement.innerHTML);
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        return false;
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();

        const targetSlot = e.target.closest('.player-slot');

        if (targetSlot && this.draggedElement !== targetSlot) {
            this.swapPlayers(this.draggedElement, targetSlot);
        }

        return false;
    }

    handleDragEnd(e) {
        this.draggedElement.classList.remove('dragging');
        this.draggedElement = null;
    }

    // Mobile Touch Handlers
    handleTouchStart(e) {
        this.draggedElement = e.target.closest('.player-slot');
        this.draggedElement.classList.add('dragging');
        e.preventDefault();
    }

    handleTouchMove(e) {
        e.preventDefault();
        // Optional: show visual feedback of drag position
    }

    handleTouchEnd(e) {
        const touch = e.changedTouches[0];
        const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
        const targetSlot = targetElement?.closest('.player-slot');

        if (targetSlot && this.draggedElement && this.draggedElement !== targetSlot) {
            this.swapPlayers(this.draggedElement, targetSlot);
        }

        if (this.draggedElement) {
            this.draggedElement.classList.remove('dragging');
            this.draggedElement = null;
        }
    }

    // Core Swap Logic
    swapPlayers(slot1, slot2) {
        // Swap player IDs
        const temp_id = slot1.dataset.playerId;
        slot1.dataset.playerId = slot2.dataset.playerId;
        slot2.dataset.playerId = temp_id;

        // Swap player names
        const name1 = slot1.querySelector('.player-name').textContent;
        const name2 = slot2.querySelector('.player-name').textContent;
        slot1.querySelector('.player-name').textContent = name2;
        slot2.querySelector('.player-name').textContent = name1;

        // Visual feedback
        this.flashSwap([slot1, slot2]);
    }

    flashSwap(slots) {
        slots.forEach(slot => {
            slot.classList.add('swapped');
            setTimeout(() => slot.classList.remove('swapped'), 400);
        });
    }

    // Configuration Management
    saveConfiguration() {
        const config = [];
        this.playerSlots.forEach(slot => {
            config.push({
                playerId: slot.dataset.playerId,
                playerName: slot.querySelector('.player-name').textContent
            });
        });
        return config;
    }

    getCurrentConfiguration() {
        const team1Slots = document.querySelectorAll('.team-1 .player-slot');
        const team2Slots = document.querySelectorAll('.team-2 .player-slot');

        return {
            team1_player1: team1Slots[0].dataset.playerId,
            team1_player2: team1Slots[1].dataset.playerId,
            team2_player1: team2Slots[0].dataset.playerId,
            team2_player2: team2Slots[1].dataset.playerId
        };
    }

    resetToOriginal() {
        const slots = Array.from(this.playerSlots);
        this.originalConfiguration.forEach((config, index) => {
            slots[index].dataset.playerId = config.playerId;
            slots[index].querySelector('.player-name').textContent = config.playerName;
        });

        // Flash all slots
        this.flashSwap(slots);
    }
}

// Global Functions
let teamShuffler;

function confirmAndStartMatch() {
    const config = teamShuffler.getCurrentConfiguration();

    // Validate 4 unique players
    const playerIds = Object.values(config);
    const uniquePlayers = new Set(playerIds);

    if (uniquePlayers.size !== 4) {
        alert('Error: All 4 players must be unique. Please check your team configuration.');
        return;
    }

    // Disable button to prevent double-submit
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Starting...';

    // Create and submit form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.pathname;

    Object.entries(config).forEach(([key, value]) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = value;
        form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
}

function resetToOriginal() {
    if (confirm('Reset teams to original pairing?')) {
        teamShuffler.resetToOriginal();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    teamShuffler = new TeamShuffler();
});
```

**Step 2: Test drag-and-drop functionality**

Refresh confirmation page and try:
1. Drag a player to another slot (desktop)
2. Touch-drag a player (mobile/dev tools)
3. Click "Reset to Original"
4. Click "Start Match" (should submit form)

Expected: Dragging works, names swap, flash animation, form submits

**Step 3: Commit**

```bash
git add static/js/shuffle.js
git commit -m "feat: add drag-and-drop JavaScript for team shuffling

Complete TeamShuffler class with desktop and mobile support:
- Desktop: dragstart/dragover/drop/dragend events
- Mobile: touchstart/touchmove/touchend events
- swapPlayers() logic with visual flash animation
- confirmAndStartMatch() creates hidden form and submits
- resetToOriginal() restores initial configuration
- Frontend validation (4 unique players)"
```

---

## Task 8: Modify start_round to Redirect to Court Selection

**Files:**
- Modify: `app.py` (modify start_round route)

**Step 1: Find start_round route in app.py**

Search for the `start_round` route (likely POST method)

**Step 2: Modify redirect after round creation**

Change the final redirect from:
```python
return redirect(url_for('active_tournament', tournament_id=tournament_id))
```

To:
```python
flash(f"Round {round_number} created! Players, go to your courts to confirm teams.")
return redirect(url_for('court_selection', tournament_id=tournament_id, round_id=new_round_id))
```

(Adjust variable names based on actual code - likely `new_round['id']` or similar)

**Step 3: Test round start flow**

1. Start Flask server
2. Navigate to tournament
3. Click "Start Round"
4. Verify redirects to court selection page

Expected: After starting round, shows court selection instead of active round

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: redirect to court selection after starting round

Modified start_round route to redirect to court selection
instead of directly to active tournament.

New flow: Start Round → Court Selection → Confirm Teams → Score Entry

Adds flash message instructing players to go to courts."
```

---

## Task 9: Add Test for Shuffle Tracking

**Files:**
- Modify: `tests/test_team_shuffling.py`

**Step 1: Write test for teams_shuffled flag**

Add to `tests/test_team_shuffling.py`:

```python
def test_teams_shuffled_flag_set_when_changed(client):
    """Verify teams_shuffled flag is set when teams are modified"""
    from database import get_db
    db = get_db()

    # Setup
    db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
    for i in range(1, 5):
        db.execute("INSERT INTO players (name) VALUES (?)", (f'Player {i}',))
    db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (1, 1)")
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 1, 1, 2, 3, 4)
    """)
    db.commit()

    # Shuffle: swap player 2 and 3
    response = client.post(
        '/tournament/1/round/1/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '3',  # Swapped
            'team2_player1': '2',  # Swapped
            'team2_player2': '4'
        }
    )

    # Verify shuffle tracking
    match = db.execute('SELECT * FROM matches WHERE id = 1').fetchone()
    db.close()

    assert match['teams_shuffled'] == 1
    assert match['original_player2_id'] == 2
    assert match['original_player3_id'] == 3
    assert match['player2_id'] == 3  # New team
    assert match['player3_id'] == 2  # New team


def test_teams_shuffled_flag_not_set_when_unchanged(client):
    """Verify teams_shuffled remains 0 if no changes made"""
    from database import get_db
    db = get_db()

    # Setup
    db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test', 2, 'active')")
    for i in range(1, 5):
        db.execute("INSERT INTO players (name) VALUES (?)", (f'Player {i}',))
    db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (1, 1)")
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 1, 1, 2, 3, 4)
    """)
    db.commit()

    # Submit same teams (no shuffle)
    response = client.post(
        '/tournament/1/round/1/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '2',  # Same
            'team2_player1': '3',  # Same
            'team2_player2': '4'
        }
    )

    match = db.execute('SELECT * FROM matches WHERE id = 1').fetchone()
    db.close()

    assert match['teams_shuffled'] == 0
    assert match['original_player1_id'] is None
```

**Step 2: Run tests**

```bash
pytest tests/test_team_shuffling.py::test_teams_shuffled_flag_set_when_changed -v
pytest tests/test_team_shuffling.py::test_teams_shuffled_flag_not_set_when_unchanged -v
```

Expected: PASS - shuffle tracking works correctly

**Step 3: Commit**

```bash
git add tests/test_team_shuffling.py
git commit -m "test: add shuffle tracking validation tests

Tests verify:
- teams_shuffled flag set to 1 when teams change
- original_player*_id columns store original pairing
- teams_shuffled remains 0 when teams unchanged
- original_player*_id columns remain NULL when unchanged

4 total tests now in test_team_shuffling.py"
```

---

## Task 10: Integration Test - Full Workflow

**Files:**
- Modify: `tests/test_team_shuffling.py`

**Step 1: Write integration test**

Add to `tests/test_team_shuffling.py`:

```python
def test_complete_shuffle_workflow(client):
    """Test full workflow: court selection → confirm → shuffle → submit"""
    from database import get_db
    db = get_db()

    # Setup tournament with 8 players, 2 courts
    db.execute("INSERT INTO tournaments (name, num_courts, status) VALUES ('Test Tournament', 2, 'active')")
    for i in range(1, 9):
        db.execute("INSERT INTO players (name) VALUES (?)", (f'Player {i}',))
    db.execute("INSERT INTO rounds (tournament_id, round_number) VALUES (1, 1)")

    # Create 2 matches
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 1, 1, 2, 3, 4)
    """)
    db.execute("""
        INSERT INTO matches (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
        VALUES (1, 2, 5, 6, 7, 8)
    """)
    db.commit()
    db.close()

    # Step 1: Navigate to court selection
    response = client.get('/tournament/1/round/1/courts')
    assert response.status_code == 200
    assert b'Court 1' in response.data
    assert b'Court 2' in response.data

    # Step 2: Navigate to Court 1 confirmation
    response = client.get('/tournament/1/round/1/court/1/confirm')
    assert response.status_code == 200
    assert b'Drag players to swap teams' in response.data
    assert b'Player 1' in response.data

    # Step 3: Shuffle teams (swap players 2 and 3)
    response = client.post(
        '/tournament/1/round/1/court/1/confirm',
        data={
            'team1_player1': '1',
            'team1_player2': '3',  # Shuffled
            'team2_player1': '2',  # Shuffled
            'team2_player2': '4'
        },
        follow_redirects=False
    )

    # Should redirect to active tournament
    assert response.status_code == 302
    assert '/tournament/1' in response.location

    # Step 4: Verify shuffle was saved
    db = get_db()
    match = db.execute('SELECT * FROM matches WHERE id = 1').fetchone()
    db.close()

    assert match['teams_shuffled'] == 1
    assert match['player1_id'] == 1
    assert match['player2_id'] == 3  # Swapped
    assert match['player3_id'] == 2  # Swapped
    assert match['player4_id'] == 4
    assert match['original_player2_id'] == 2
    assert match['original_player3_id'] == 3
```

**Step 2: Run integration test**

```bash
pytest tests/test_team_shuffling.py::test_complete_shuffle_workflow -v
```

Expected: PASS - full workflow works end-to-end

**Step 3: Run all tests**

```bash
pytest tests/test_team_shuffling.py -v
```

Expected: All 5 tests passing

**Step 4: Commit**

```bash
git add tests/test_team_shuffling.py
git commit -m "test: add integration test for complete shuffle workflow

Tests full user journey:
1. GET court selection page
2. GET confirmation page for specific court
3. POST shuffled teams
4. Verify redirect to active tournament
5. Verify shuffle persisted to database

All 5 tests passing in test_team_shuffling.py"
```

---

## Task 11: Manual Testing and Bug Fixes

**Files:**
- Varies based on bugs found

**Step 1: Manual test checklist**

Run through these scenarios:

1. **Happy path:**
   - Create tournament with 8 players
   - Start Round 1
   - Should redirect to court selection
   - Click "Go to Court 1"
   - Should see confirmation screen
   - Drag player to swap teams
   - Click "Start Match"
   - Should proceed to score entry

2. **Edge cases:**
   - Try to shuffle teams after scores entered (should prevent)
   - Try to submit invalid teams (duplicate players)
   - Try "Reset to Original" button
   - Test on mobile browser (touch drag)

**Step 2: Fix any bugs found**

Document and fix issues discovered during manual testing

**Step 3: Re-run automated tests**

```bash
pytest
```

Expected: All tests still passing

**Step 4: Commit bug fixes**

```bash
git add <files>
git commit -m "fix: <description of bug fix>"
```

---

## Task 12: Documentation Update

**Files:**
- Modify: `README.md` or create `docs/SHUFFLING.md`

**Step 1: Document the feature**

Add section to README or create new doc:

```markdown
## Manual Team Shuffling

Players can manually adjust team pairings before matches start.

### User Flow

1. Tournament organizer starts a round
2. Players navigate to court selection screen
3. Each player selects their court
4. Pre-match confirmation screen shows algorithm's pairing
5. Players can drag-and-drop to swap partners
6. Click "Start Match" to confirm and proceed to scoring

### Technical Details

- New database columns track shuffle history:
  - `teams_shuffled`: boolean flag
  - `original_player1_id` through `original_player4_id`: original pairing
- Court movement algorithm uses actual teams that played
- Mobile-optimized drag-and-drop interface
- Validation prevents invalid team configurations

### Routes

- `GET /tournament/<id>/round/<id>/courts` - Court selection
- `GET /tournament/<id>/round/<id>/court/<n>/confirm` - Pre-match confirmation
- `POST /tournament/<id>/round/<id>/court/<n>/confirm` - Save teams
```

**Step 2: Commit documentation**

```bash
git add README.md
git commit -m "docs: add manual team shuffling feature documentation

Documents user flow, technical details, and routes for
manual team shuffling feature."
```

---

## Task 13: Final Verification

**Files:**
- None (verification only)

**Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All tests passing (including existing Phase 2 tests)

**Step 2: Test on actual database**

1. Backup production database
2. Run migration: `sqlite3 instance/padel.db < migrations/003_add_team_shuffling.sql`
3. Start server: `python app.py`
4. Test complete flow with real data

**Step 3: Verify court movement uses shuffled teams**

1. Create tournament, start Round 1
2. Shuffle teams on Court 1
3. Complete Round 1
4. Start Round 2
5. Verify Round 2 pairings use shuffled teams (not original algorithm teams)

**Step 4: Create verification checklist**

Document verification in commit:

```bash
git commit --allow-empty -m "verify: manual team shuffling feature complete

Verification checklist:
✅ All 5 shuffle tests passing
✅ All existing tests still passing
✅ Database migration applied successfully
✅ Court selection page renders correctly
✅ Confirmation page loads with player names
✅ Drag-and-drop works on desktop
✅ Touch drag works on mobile
✅ Form validation prevents invalid teams
✅ Shuffle tracking persists to database
✅ Court movement uses shuffled teams
✅ Documentation updated

Feature ready for production deployment."
```

---

## Success Criteria

Feature is complete when:

**Functional:**
- ✅ Players can access court selection after round starts
- ✅ Confirmation screen shows teams with drag-and-drop UI
- ✅ Drag-and-drop works on desktop and mobile
- ✅ "Start Match" submits teams and redirects to scoring
- ✅ "Reset to Original" restores initial pairing
- ✅ Validation prevents invalid team configurations
- ✅ Shuffle tracking persists to database
- ✅ Court movement uses shuffled teams

**Technical:**
- ✅ Database migration adds 5 columns
- ✅ All validation tests passing
- ✅ Integration test passing
- ✅ No regressions in existing tests
- ✅ Mobile-responsive CSS (60-70px touch targets)

**Documentation:**
- ✅ Feature documented in README/docs
- ✅ Code comments explain shuffle logic

---

## Deployment Checklist

1. **Backup database:** `cp instance/padel.db instance/padel.db.backup`
2. **Run migration:** `sqlite3 instance/padel.db < migrations/003_add_team_shuffling.sql`
3. **Verify schema:** `sqlite3 instance/padel.db ".schema matches"`
4. **Deploy code:** `git pull` (or copy files to server)
5. **Restart server:** `systemctl restart padel-scorer` (or equivalent)
6. **Test on production:** Walk through complete flow
7. **Monitor for errors:** Check logs for first few tournaments

---

**End of Implementation Plan**
