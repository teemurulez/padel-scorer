# Phase 3 Stage 3a: Minimal Player Profiles - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create player profile pages showing current season stats, accessible via clickable names in season leaderboard.

**Architecture:** Add new `/player/<id>/profile` route that queries existing season data and displays in a dedicated template. Make player names in season_leaderboard.html clickable links. No database schema changes needed.

**Tech Stack:** Flask (routes), Jinja2 (templates), SQLite (queries), Pytest (testing)

---

## Task 1: Create Player Profile Route - Test First

**Files:**
- Create: `/Users/teemu/Documents/Teemu/Code/tennis-scorer/tests/test_player_profile.py`
- Modify: None yet

**Step 1: Write the failing test for player profile with data**

Create test file with fixture and first test:

```python
import pytest
import sqlite3
from app import app
from datetime import datetime


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database"""
    import os
    db_path = tmp_path / "test_player_profile.db"
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(db_path)

    with app.test_client() as client:
        with app.app_context():
            init_test_db()
        yield client

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def init_test_db():
    """Initialize test database with Phase 3 schema"""
    from database import get_db
    db = get_db()

    # Create minimal schema for player profile testing
    db.executescript("""
        DROP TABLE IF EXISTS scores;
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS tournament_players;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS seasons;
        DROP TABLE IF EXISTS player_registry;

        CREATE TABLE player_registry (
            id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL
        );

        CREATE TABLE seasons (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            is_current INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP
        );

        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT,
            season_id INTEGER,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (season_id) REFERENCES seasons(id)
        );

        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER,
            round_number INTEGER,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            round_id INTEGER,
            court_number INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            player3_id INTEGER,
            player4_id INTEGER,
            winning_team INTEGER,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (round_id) REFERENCES rounds(id)
        );

        CREATE TABLE scores (
            id INTEGER PRIMARY KEY,
            match_id INTEGER,
            player_id INTEGER,
            points INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (player_id) REFERENCES player_registry(id)
        );
    """)
    db.commit()


def test_player_profile_with_season_data(client):
    """Test profile page displays correctly for player with season data"""
    from database import get_db
    db = get_db()

    # Setup: Create current season
    current_year = datetime.now().year
    db.execute(
        'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
        (f'Season {current_year}',)
    )
    season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create player
    db.execute(
        'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
        ('Erik', 'Andersson')
    )
    player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create tournament
    db.execute(
        'INSERT INTO tournaments (name, season_id, status) VALUES (?, ?, ?)',
        ('Test Tournament', season_id, 'completed')
    )
    tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create round
    db.execute(
        'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
        (tournament_id, 1)
    )
    round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create 3 matches where player wins 2
    for i in range(3):
        db.execute(
            '''INSERT INTO matches
               (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (round_id, i+1, player_id, player_id+1, player_id+2, player_id+3, 1 if i < 2 else 2, 1)
        )
        match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Add scores (player won if i < 2)
        points = 10 if i < 2 else 5
        db.execute(
            'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
            (match_id, player_id, points)
        )

    db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{player_id}/profile')

    # Assert
    assert response.status_code == 200
    assert b'Erik Andersson' in response.data
    assert b'2025 Season' in response.data or str(current_year).encode() in response.data
    # Should show rank, wins, tournaments
    assert b'#1' in response.data or b'Season Rank' in response.data
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && venv/bin/pytest tests/test_player_profile.py::test_player_profile_with_season_data -v`

Expected: FAIL with "404 NOT FOUND" (route doesn't exist yet)

**Step 3: Commit the failing test**

```bash
cd /Users/teemu/Documents/Teemu/Code/tennis-scorer
git add tests/test_player_profile.py
git commit -m "test: add failing test for player profile with season data"
```

---

## Task 2: Implement Player Profile Route

**Files:**
- Modify: `/Users/teemu/Documents/Teemu/Code/tennis-scorer/app.py` (add new route after line 1037)

**Step 1: Add the player_profile route**

Add this route after the `/leaderboard/clear-all` route (after line 1037):

```python
@app.route('/player/<int:player_id>/profile')
def player_profile(player_id):
    """Display player profile with current season statistics"""
    db = get_db_connection()

    # Get player from registry
    player = db.execute(
        'SELECT * FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if not player:
        flash('Player not found')
        return redirect(url_for('index'))

    # Get current season
    current_season = get_current_season(db)
    if not current_season:
        # No current season - show player with no data
        return render_template(
            'player_profile.html',
            player=player,
            season_stats=None,
            season_name='No Current Season',
            rank=None
        )

    current_year = datetime.now().year

    # Get season stats for this player
    # Using same query logic as season_leaderboard route
    season_stats = db.execute("""
        SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
            COUNT(DISTINCT m.id) as total_matches,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate,
            SUM(s.points) as total_points,
            COUNT(DISTINCT t.id) as tournaments_played
        FROM player_registry pr
        LEFT JOIN matches m ON (
            pr.id = m.player1_id OR
            pr.id = m.player2_id OR
            pr.id = m.player3_id OR
            pr.id = m.player4_id
        )
        LEFT JOIN rounds r ON m.round_id = r.id
        LEFT JOIN tournaments t ON r.tournament_id = t.id
        LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
        WHERE pr.id = ?
          AND t.season_id = ?
          AND m.completed = 1
        GROUP BY pr.id, pr.first_name, pr.last_name
    """, (player_id, current_season['id'])).fetchone()

    # Calculate wins per tournament
    wins_per_tournament = None
    if season_stats and season_stats['total_wins'] and season_stats['tournaments_played']:
        wins_per_tournament = round(
            season_stats['total_wins'] / season_stats['tournaments_played'], 2
        )

    # Calculate rank (get all players in order and find position)
    rank = None
    if season_stats and season_stats['total_wins'] > 0:
        all_standings = db.execute("""
            SELECT
                pr.id,
                COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins
            FROM player_registry pr
            LEFT JOIN matches m ON (
                pr.id = m.player1_id OR
                pr.id = m.player2_id OR
                pr.id = m.player3_id OR
                pr.id = m.player4_id
            )
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN tournaments t ON r.tournament_id = t.id
            LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
            WHERE t.season_id = ?
              AND m.completed = 1
            GROUP BY pr.id
            HAVING COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) > 0
            ORDER BY total_wins DESC
        """, (current_season['id'],)).fetchall()

        for idx, row in enumerate(all_standings, start=1):
            if row['id'] == player_id:
                rank = idx
                break

    return render_template(
        'player_profile.html',
        player=player,
        season_stats=season_stats,
        season_name=current_season['name'],
        current_year=current_year,
        rank=rank,
        wins_per_tournament=wins_per_tournament
    )
```

**Step 2: Run test to verify it passes (will fail - missing template)**

Run: `venv/bin/pytest tests/test_player_profile.py::test_player_profile_with_season_data -v`

Expected: Still FAIL (TemplateNotFound: player_profile.html)

**Step 3: Don't commit yet - wait for template**

---

## Task 3: Create Player Profile Template

**Files:**
- Create: `/Users/teemu/Documents/Teemu/Code/tennis-scorer/templates/player_profile.html`

**Step 1: Create the template file**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ player.first_name }} {{ player.last_name }} - Profile</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .player-profile {
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }
        .profile-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .profile-header h1 {
            margin-bottom: 0.5rem;
        }
        .season-label {
            color: #666;
            font-size: 1.1rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: #f5f5f5;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card.primary {
            background: #fff3cd;
            border: 2px solid #ffc107;
        }
        .stat-card.rank {
            background: #d4edda;
            border: 2px solid #28a745;
        }
        .stat-card .label {
            display: block;
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 0.5rem;
        }
        .stat-card .value {
            display: block;
            font-size: 2rem;
            font-weight: bold;
            color: #333;
        }
        .no-data {
            text-align: center;
            padding: 3rem;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 2rem;
        }
        .no-data p {
            font-size: 1.2rem;
            color: #666;
        }
        .profile-actions {
            text-align: center;
            margin-top: 2rem;
        }
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            }
            .stat-card {
                padding: 1rem;
            }
            .stat-card .value {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="player-profile">
            <!-- Header -->
            <div class="profile-header">
                <h1>{{ player.first_name }} {{ player.last_name }}</h1>
                <p class="season-label">{{ season_name }}</p>
            </div>

            {% if season_stats and season_stats.total_wins > 0 %}
                <!-- Season Statistics -->
                <div class="stats-grid">
                    {% if rank %}
                    <div class="stat-card rank">
                        <span class="label">Season Rank</span>
                        <span class="value">#{{ rank }}</span>
                    </div>
                    {% endif %}

                    <div class="stat-card primary">
                        <span class="label">Match Wins</span>
                        <span class="value">{{ season_stats.total_wins }}</span>
                    </div>

                    <div class="stat-card">
                        <span class="label">Tournaments</span>
                        <span class="value">{{ season_stats.tournaments_played }}</span>
                    </div>

                    {% if wins_per_tournament %}
                    <div class="stat-card">
                        <span class="label">Wins/Tournament</span>
                        <span class="value">{{ wins_per_tournament }}</span>
                    </div>
                    {% endif %}

                    <div class="stat-card">
                        <span class="label">Total Points</span>
                        <span class="value">{{ season_stats.total_points or 0 }}</span>
                    </div>

                    {% if season_stats.win_rate %}
                    <div class="stat-card">
                        <span class="label">Win Rate</span>
                        <span class="value">{{ season_stats.win_rate }}%</span>
                    </div>
                    {% endif %}
                </div>
            {% else %}
                <!-- No Data Message -->
                <div class="no-data">
                    <p>No tournaments played this season yet.</p>
                </div>
            {% endif %}

            <!-- Navigation -->
            <div class="profile-actions">
                <a href="{{ url_for('season_leaderboard') }}" class="btn btn-secondary">← Back to Season Leaderboard</a>
            </div>
        </div>
    </div>
</body>
</html>
```

**Step 2: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_player_profile.py::test_player_profile_with_season_data -v`

Expected: PASS

**Step 3: Commit route and template together**

```bash
git add app.py templates/player_profile.html
git commit -m "feat: add player profile page with season stats

- New route /player/<id>/profile
- Display season rank, match wins, tournaments, win rate
- Query season stats using current season filter
- Calculate rank from season standings
- Handle edge case: player not found redirects home"
```

---

## Task 4: Test Player Profile Without Data

**Files:**
- Modify: `/Users/teemu/Documents/Teemu/Code/tennis-scorer/tests/test_player_profile.py`

**Step 1: Add test for player with no season data**

Add this test after the first test:

```python
def test_player_profile_no_season_data(client):
    """Test profile shows 'No data' message for player with no season participation"""
    from database import get_db
    db = get_db()

    # Setup: Create current season
    current_year = datetime.now().year
    db.execute(
        'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
        (f'Season {current_year}',)
    )

    # Create player but no tournament/match data
    db.execute(
        'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
        ('New', 'Player')
    )
    player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    db.commit()

    # Test: Visit profile
    response = client.get(f'/player/{player_id}/profile')

    # Assert
    assert response.status_code == 200
    assert b'New Player' in response.data
    assert b'No tournaments played this season yet' in response.data
```

**Step 2: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_player_profile.py::test_player_profile_no_season_data -v`

Expected: PASS

**Step 3: Add test for player not found**

Add this test:

```python
def test_player_profile_not_found(client):
    """Test profile redirects for non-existent player"""
    # Test: Try to visit non-existent player profile
    response = client.get('/player/99999/profile')

    # Assert: Redirects to home
    assert response.status_code == 302
    assert b'/player/99999/profile' not in response.data
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_player_profile.py::test_player_profile_not_found -v`

Expected: PASS

**Step 5: Run all profile tests**

Run: `venv/bin/pytest tests/test_player_profile.py -v`

Expected: 3/3 PASS

**Step 6: Commit the additional tests**

```bash
git add tests/test_player_profile.py
git commit -m "test: add tests for player profile edge cases

- Test player with no season data shows message
- Test non-existent player redirects to home
- All 3 player profile tests passing"
```

---

## Task 5: Make Player Names Clickable in Season Leaderboard

**Files:**
- Modify: `/Users/teemu/Documents/Teemu/Code/tennis-scorer/templates/season_leaderboard.html` (line 149)

**Step 1: Write failing test for clickable names**

Add to tests/test_player_profile.py:

```python
def test_season_leaderboard_has_clickable_names(client):
    """Test season leaderboard shows clickable player names"""
    from database import get_db
    db = get_db()

    # Setup: Create current season
    current_year = datetime.now().year
    db.execute(
        'INSERT INTO seasons (name, is_current) VALUES (?, 1)',
        (f'Season {current_year}',)
    )
    season_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create player
    db.execute(
        'INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)',
        ('Erik', 'Andersson')
    )
    player_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Create tournament with match
    db.execute(
        'INSERT INTO tournaments (name, season_id, status) VALUES (?, ?, ?)',
        ('Test Tournament', season_id, 'completed')
    )
    tournament_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    db.execute(
        'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
        (tournament_id, 1)
    )
    round_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    db.execute(
        '''INSERT INTO matches
           (round_id, court_number, player1_id, player2_id, player3_id, player4_id, winning_team, completed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (round_id, 1, player_id, player_id+1, player_id+2, player_id+3, 1, 1)
    )
    match_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    db.execute(
        'INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)',
        (match_id, player_id, 10)
    )
    db.commit()

    # Test: Visit season leaderboard
    response = client.get('/leaderboard/season')

    # Assert: Should have link to player profile
    assert response.status_code == 200
    expected_link = f'/player/{player_id}/profile'.encode()
    assert expected_link in response.data
    assert b'Erik Andersson' in response.data or b'Andersson, Erik' in response.data
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_player_profile.py::test_season_leaderboard_has_clickable_names -v`

Expected: FAIL (link not present yet)

**Step 3: Modify season_leaderboard.html to make names clickable**

Find line 149 in season_leaderboard.html:
```html
<td class="player-name">{{ player['first_name'] }} {{ player['last_name'] }}</td>
```

Replace with:
```html
<td class="player-name">
    <a href="{{ url_for('player_profile', player_id=player['id']) }}">
        {{ player['first_name'] }} {{ player['last_name'] }}
    </a>
</td>
```

Also update the tournament-specific leaderboard (line 203):
```html
<td class="player-name">
    <a href="{{ url_for('player_profile', player_id=player['id']) }}">
        {{ player['first_name'] }} {{ player['last_name'] }}
    </a>
</td>
```

**Step 4: Add CSS for player name links**

Add to the `<style>` section in season_leaderboard.html (around line 95, before closing </style>):

```css
.player-name a {
    color: #2563eb;
    text-decoration: none;
}
.player-name a:hover {
    text-decoration: underline;
    color: #1d4ed8;
}
```

**Step 5: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_player_profile.py::test_season_leaderboard_has_clickable_names -v`

Expected: PASS

**Step 6: Commit the clickable names**

```bash
git add templates/season_leaderboard.html
git commit -m "feat: make player names clickable in season leaderboard

- Convert player names to links to player profile
- Add hover styles for links (blue, underline on hover)
- Applied to both season-wide and tournament-specific tables"
```

---

## Task 6: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all player profile tests**

Run: `venv/bin/pytest tests/test_player_profile.py -v`

Expected: 4/4 PASS

**Step 2: Run full test suite to check for regressions**

Run: `venv/bin/pytest -v`

Expected: All tests pass (or same failures as before Stage 3a)

**Step 3: Manual testing checklist**

Test manually:
- [ ] Navigate to `/player/1/profile` directly - verify shows profile or redirects if no player
- [ ] Go to season leaderboard - verify player names are blue/clickable
- [ ] Click a player name - verify navigates to profile
- [ ] Profile with data - verify shows all stats (rank, wins, tournaments, win rate, points)
- [ ] Profile without data - verify shows "No tournaments played" message
- [ ] Click "Back to Season Leaderboard" - verify returns to leaderboard
- [ ] Test on mobile browser - verify responsive layout

**Step 4: Create summary commit (if needed)**

If all tests pass and manual testing succeeds:

```bash
git add -A
git commit -m "feat: Phase 3 Stage 3a complete - minimal player profiles

Implemented player profile pages with current season stats:
- New route: /player/<id>/profile
- Display: rank, match wins, tournaments, win/tournament, points, win%
- Clickable player names in season leaderboard
- Handle edge cases: no data, player not found
- Responsive layout with stat cards
- 4/4 tests passing

Stage 3a scope: Minimal MVP with season stats only
Future: Tournament history, career stats, exports (Stage 3b+)"
```

---

## Success Criteria

**Feature complete when:**
- ✅ All 4 tests in test_player_profile.py passing
- ✅ Can navigate to player profile from season leaderboard (clickable names)
- ✅ Profile displays all season stats correctly (rank, wins, tournaments, rate, points)
- ✅ Profile handles players with no data gracefully ("No tournaments played")
- ✅ Profile redirects for non-existent players
- ✅ Navigation back to leaderboard works
- ✅ Layout is responsive on mobile (manual test)
- ✅ No regressions in existing tests

---

## Notes

**Why no season_standings view?**
- The design document proposed a `season_standings` view for cleaner queries
- Current implementation calculates stats directly in the route (same as existing season_leaderboard route)
- Keeping consistency with existing code patterns for this minimal version
- View can be added in future optimization phase if needed

**Database queries:**
- Using same query pattern as `/leaderboard/season` route for consistency
- Filtering by current season using `season_id`
- Counting wins as matches where player scored points
- Calculating rank by ordering all players and finding position

**Future enhancements (out of scope for Stage 3a):**
- Tournament history table (Stage 3b)
- Career statistics across all seasons (Stage 3b)
- CSV export for player data (Stage 4)
- Player comparison view
- Performance graphs/charts

---

**End of Implementation Plan**
