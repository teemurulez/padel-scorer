# Phase 2 Court Movement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "King of the Court" movement logic where winners move up courts, losers move down, and previous teammates are split.

**Architecture:** Extend the existing round generation system to use match results from the previous round instead of pure randomization. Winners from lower courts move up, losers from higher courts move down, and the pairing algorithm ensures teammates from the previous round are separated.

**Tech Stack:** Python 3.9, Flask 3.1.2, SQLite3, Jinja2 templates

---

## Background: Understanding the Current System

**Current Database Schema:**
- `players` - Player records with total_points
- `tournaments` - Tournament metadata (name, num_courts, status)
- `rounds` - Round tracking (tournament_id, round_number, status)
- `matches` - Match records (round_id, court_number, player1-4_id, winning_team, completed)
- `scores` - Individual points per match (player_id, match_id, points)

**Current Round Generation (app.py:86-162):**
- Shuffles all players randomly
- Assigns 4 players per court sequentially
- No consideration of previous results
- Works for Round 1 but needs enhancement for subsequent rounds

**What We're Adding:**
1. Court movement based on match results
2. Teammate separation algorithm
3. Different logic for Round 1 (random) vs Round 2+ (result-based)

---

## Task 1: Add Database Schema for Match History

**Files:**
- Modify: `database.py:1-93`
- Test: Manual verification with SQLite browser

**Step 1: Add previous_match tracking to matches table**

Add a new column to track which players were teammates in previous rounds:

```python
# In init_db() function, modify the matches table creation (line 54-72)
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (round_id) REFERENCES rounds(id),
        FOREIGN KEY (player1_id) REFERENCES players(id),
        FOREIGN KEY (player2_id) REFERENCES players(id),
        FOREIGN KEY (player3_id) REFERENCES players(id),
        FOREIGN KEY (player4_id) REFERENCES players(id)
    )
''')
```

Note: No schema change needed - current schema already has winning_team which we'll use.

**Step 2: Verify database structure**

Run: `sqlite3 instance/padel.db ".schema matches"`
Expected: See the matches table with winning_team column

**Step 3: Commit**

```bash
git add database.py
git commit -m "docs: confirm matches schema supports court movement"
```

---

## Task 2: Create Court Movement Algorithm Module

**Files:**
- Create: `court_movement.py`
- Test: `tests/test_court_movement.py`

**Step 2.1: Write failing test for get_previous_teammates**

Create test file:

```python
# tests/test_court_movement.py
import pytest
from court_movement import get_previous_teammates

def test_get_previous_teammates_empty_round():
    """Test that empty round history returns empty set"""
    previous_matches = []
    result = get_previous_teammates(player_id=1, previous_matches=previous_matches)
    assert result == set()
```

**Step 2.2: Run test to verify it fails**

Run: `pytest tests/test_court_movement.py::test_get_previous_teammates_empty_round -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'court_movement'"

**Step 2.3: Write minimal implementation**

```python
# court_movement.py
def get_previous_teammates(player_id, previous_matches):
    """
    Get set of player IDs who were teammates with player_id in previous matches.

    Args:
        player_id: The player to check
        previous_matches: List of match dicts from previous round

    Returns:
        Set of player IDs who were teammates
    """
    teammates = set()

    for match in previous_matches:
        # Check if player was in this match
        player_ids = [
            match['player1_id'],
            match['player2_id'],
            match['player3_id'],
            match['player4_id']
        ]

        if player_id not in player_ids:
            continue

        # Find which team they were on
        if player_id in [match['player1_id'], match['player2_id']]:
            # Team 1
            teammates.add(match['player1_id'])
            teammates.add(match['player2_id'])
        else:
            # Team 2
            teammates.add(match['player3_id'])
            teammates.add(match['player4_id'])

    # Remove the player themselves
    teammates.discard(player_id)

    return teammates
```

**Step 2.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_get_previous_teammates_empty_round -v`
Expected: PASS

**Step 2.5: Commit**

```bash
git add court_movement.py tests/test_court_movement.py
git commit -m "feat: add get_previous_teammates function"
```

---

## Task 3: Test Teammate Identification with Real Data

**Files:**
- Modify: `tests/test_court_movement.py`

**Step 3.1: Write failing test for teammate identification**

```python
def test_get_previous_teammates_identifies_team1_partner():
    """Test identifying teammate from team 1"""
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        }
    ]
    result = get_previous_teammates(player_id=1, previous_matches=previous_matches)
    assert result == {2}
```

**Step 3.2: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_get_previous_teammates_identifies_team1_partner -v`
Expected: PASS (implementation already handles this)

**Step 3.3: Write test for team 2 partner**

```python
def test_get_previous_teammates_identifies_team2_partner():
    """Test identifying teammate from team 2"""
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2
        }
    ]
    result = get_previous_teammates(player_id=3, previous_matches=previous_matches)
    assert result == {4}
```

**Step 3.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_get_previous_teammates_identifies_team2_partner -v`
Expected: PASS

**Step 3.5: Commit**

```bash
git add tests/test_court_movement.py
git commit -m "test: add teammate identification test cases"
```

---

## Task 4: Implement Court Position Sorting

**Files:**
- Modify: `court_movement.py`
- Modify: `tests/test_court_movement.py`

**Step 4.1: Write failing test for sort_players_by_court_position**

```python
def test_sort_players_by_court_position_winners_first():
    """Test that winners are sorted before losers within same court"""
    matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2  # Team 2 won
        }
    ]
    result = sort_players_by_court_position(matches)
    # Winners (3, 4) should come before losers (1, 2) for court 1
    assert result == [3, 4, 1, 2]
```

**Step 4.2: Run test to verify it fails**

Run: `pytest tests/test_court_movement.py::test_sort_players_by_court_position_winners_first -v`
Expected: FAIL with "NameError: name 'sort_players_by_court_position' is not defined"

**Step 4.3: Write minimal implementation**

```python
# In court_movement.py
def sort_players_by_court_position(matches):
    """
    Sort players by their position in court hierarchy.
    Winners move up, losers move down.

    Args:
        matches: List of completed match dicts with court_number and winning_team

    Returns:
        List of player IDs in order: Court 1 winners, Court 1 losers,
        Court 2 winners, Court 2 losers, etc.
    """
    # Sort matches by court number
    sorted_matches = sorted(matches, key=lambda m: m['court_number'])

    result = []

    for match in sorted_matches:
        if match['winning_team'] == 1:
            # Team 1 won
            winners = [match['player1_id'], match['player2_id']]
            losers = [match['player3_id'], match['player4_id']]
        else:
            # Team 2 won
            winners = [match['player3_id'], match['player4_id']]
            losers = [match['player1_id'], match['player2_id']]

        # Winners first, then losers
        result.extend(winners)
        result.extend(losers)

    return result
```

**Step 4.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_sort_players_by_court_position_winners_first -v`
Expected: PASS

**Step 4.5: Commit**

```bash
git add court_movement.py tests/test_court_movement.py
git commit -m "feat: add court position sorting for winners/losers"
```

---

## Task 5: Test Multi-Court Sorting

**Files:**
- Modify: `tests/test_court_movement.py`

**Step 5.1: Write test for multi-court scenario**

```python
def test_sort_players_multi_court():
    """Test sorting across multiple courts maintains court order"""
    matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        },
        {
            'court_number': 2,
            'player1_id': 5,
            'player2_id': 6,
            'player3_id': 7,
            'player4_id': 8,
            'winning_team': 2
        }
    ]
    result = sort_players_by_court_position(matches)
    # Court 1 winners, Court 1 losers, Court 2 winners, Court 2 losers
    assert result == [1, 2, 3, 4, 7, 8, 5, 6]
```

**Step 5.2: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_sort_players_multi_court -v`
Expected: PASS

**Step 5.3: Commit**

```bash
git add tests/test_court_movement.py
git commit -m "test: verify multi-court position sorting"
```

---

## Task 6: Implement Team Assignment with Separation

**Files:**
- Modify: `court_movement.py`
- Modify: `tests/test_court_movement.py`

**Step 6.1: Write failing test for assign_teams_with_separation**

```python
def test_assign_teams_prevents_same_teammates():
    """Test that previous teammates are not paired together"""
    sorted_player_ids = [1, 2, 3, 4]  # 4 players for 1 court
    previous_matches = [
        {
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 1
        }
    ]

    result = assign_teams_with_separation(
        sorted_player_ids=sorted_player_ids,
        previous_matches=previous_matches,
        num_courts=1
    )

    # Result should be list of court assignments
    # Each court has [p1, p2, p3, p4] where p1+p2 are NOT previous teammates
    assert len(result) == 1
    court = result[0]
    assert len(court) == 4

    # Player 1 and 2 were teammates, should NOT be together
    if court[0] == 1:
        assert court[1] != 2
    if court[0] == 2:
        assert court[1] != 1
```

**Step 6.2: Run test to verify it fails**

Run: `pytest tests/test_court_movement.py::test_assign_teams_prevents_same_teammates -v`
Expected: FAIL with "NameError: name 'assign_teams_with_separation' is not defined"

**Step 6.3: Write minimal implementation**

```python
# In court_movement.py
import random

def assign_teams_with_separation(sorted_player_ids, previous_matches, num_courts):
    """
    Assign players to courts and teams, avoiding previous teammates.

    Args:
        sorted_player_ids: Players in court hierarchy order (winners->losers)
        previous_matches: Previous round matches for teammate history
        num_courts: Number of courts to fill

    Returns:
        List of court assignments, each court is [p1, p2, p3, p4]
        where p1+p2 are team 1, p3+p4 are team 2
    """
    courts = []
    players_per_court = 4

    for court_idx in range(num_courts):
        start_idx = court_idx * players_per_court
        end_idx = start_idx + players_per_court

        if end_idx > len(sorted_player_ids):
            break  # Not enough players for this court

        court_players = sorted_player_ids[start_idx:end_idx]

        # Try to assign teams avoiding previous teammates
        # Strategy: Take players in order but swap if needed
        p1, p2, p3, p4 = court_players

        # Check if p1 and p2 were previous teammates
        p1_teammates = get_previous_teammates(p1, previous_matches)

        if p2 in p1_teammates:
            # Swap p2 with p3 to separate teammates
            p2, p3 = p3, p2

        courts.append([p1, p2, p3, p4])

    return courts
```

**Step 6.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_assign_teams_prevents_same_teammates -v`
Expected: PASS

**Step 6.5: Commit**

```bash
git add court_movement.py tests/test_court_movement.py
git commit -m "feat: add team assignment with teammate separation"
```

---

## Task 7: Implement Complete Movement Algorithm

**Files:**
- Modify: `court_movement.py`
- Modify: `tests/test_court_movement.py`

**Step 7.1: Write failing test for generate_next_round_pairings**

```python
def test_generate_next_round_pairings_moves_winners_up():
    """Test that winners from court 2 move to court 1"""
    previous_matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': 2  # 3, 4 won
        },
        {
            'court_number': 2,
            'player1_id': 5,
            'player2_id': 6,
            'player3_id': 7,
            'player4_id': 8,
            'winning_team': 1  # 5, 6 won
        }
    ]

    result = generate_next_round_pairings(previous_matches, num_courts=2)

    # Court 1 should have winners from both courts
    # Court 2 should have losers from both courts
    court1 = result[0]
    court2 = result[1]

    # Winners: 3, 4, 5, 6 should be on court 1
    assert set(court1) == {3, 4, 5, 6}
    # Losers: 1, 2, 7, 8 should be on court 2
    assert set(court2) == {1, 2, 7, 8}
```

**Step 7.2: Run test to verify it fails**

Run: `pytest tests/test_court_movement.py::test_generate_next_round_pairings_moves_winners_up -v`
Expected: FAIL with "NameError: name 'generate_next_round_pairings' is not defined"

**Step 7.3: Write minimal implementation**

```python
# In court_movement.py
def generate_next_round_pairings(previous_matches, num_courts):
    """
    Generate court and team assignments for next round based on results.

    King of the Court rules:
    - Winners move up in court order (lower court number = higher)
    - Losers move down in court order
    - Previous teammates are separated when possible

    Args:
        previous_matches: List of completed match dicts from previous round
        num_courts: Number of courts available

    Returns:
        List of court assignments [court1, court2, ...] where each court
        is [player1_id, player2_id, player3_id, player4_id]
    """
    # Step 1: Sort all players by position (winners up, losers down)
    sorted_players = sort_players_by_court_position(previous_matches)

    # Step 2: Redistribute to new courts
    # Top 4 players -> Court 1
    # Next 4 players -> Court 2, etc.
    redistributed = []

    for court_idx in range(num_courts):
        start = court_idx * 4
        end = start + 4

        if end > len(sorted_players):
            break

        # Get top 4 for this court position
        court_players = sorted_players[start:end]
        redistributed.append(court_players)

    # Step 3: Within each court, assign teams to avoid previous teammates
    final_courts = []

    for court_players in redistributed:
        p1, p2, p3, p4 = court_players

        # Check if default pairing has previous teammates
        p1_teammates = get_previous_teammates(p1, previous_matches)

        if p2 in p1_teammates:
            # Swap to separate teammates
            p2, p3 = p3, p2

        final_courts.append([p1, p2, p3, p4])

    return final_courts
```

**Step 7.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_generate_next_round_pairings_moves_winners_up -v`
Expected: PASS

**Step 7.5: Commit**

```bash
git add court_movement.py tests/test_court_movement.py
git commit -m "feat: implement complete court movement algorithm"
```

---

## Task 8: Run All Court Movement Tests

**Files:**
- Test: `tests/test_court_movement.py`

**Step 8.1: Run complete test suite**

Run: `pytest tests/test_court_movement.py -v`
Expected: All tests PASS

**Step 8.2: If failures occur, fix and rerun**

Analyze failures, fix implementation, rerun until all pass.

**Step 8.3: Commit test verification**

```bash
git add tests/test_court_movement.py
git commit -m "test: verify all court movement tests pass"
```

---

## Task 9: Integrate Movement Algorithm into Flask App

**Files:**
- Modify: `app.py:86-162` (start_round function)

**Step 9.1: Import court_movement module**

```python
# At top of app.py, add after line 6:
from court_movement import generate_next_round_pairings
```

**Step 9.2: Modify start_round route to use algorithm**

Replace the random pairing logic (lines 110-141) with:

```python
# Get or create current round
last_round = db.execute(
    'SELECT * FROM rounds WHERE tournament_id = ? ORDER BY round_number DESC LIMIT 1',
    (tournament_id,)
).fetchone()

round_number = 1 if not last_round else last_round['round_number'] + 1

cursor = db.execute(
    'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
    (tournament_id, round_number)
)
round_id = cursor.lastrowid

# Determine pairing strategy
if round_number == 1:
    # Round 1: Random pairing (existing logic)
    player_list = list(players)
    random.shuffle(player_list)

    for court in range(num_courts):
        idx = court * 4
        if idx + 3 < num_players:
            db.execute(
                '''INSERT INTO matches
                   (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (round_id, court + 1,
                 player_list[idx]['id'],
                 player_list[idx + 1]['id'],
                 player_list[idx + 2]['id'],
                 player_list[idx + 3]['id'])
            )
else:
    # Round 2+: Movement-based pairing
    previous_matches = db.execute(
        '''SELECT m.* FROM matches m
           JOIN rounds r ON m.round_id = r.id
           WHERE r.tournament_id = ?
           AND r.round_number = ?
           AND m.completed = 1''',
        (tournament_id, round_number - 1)
    ).fetchall()

    # Convert to list of dicts
    previous_matches = [dict(m) for m in previous_matches]

    # Generate new pairings
    court_assignments = generate_next_round_pairings(previous_matches, num_courts)

    # Create matches from assignments
    for court_num, players_on_court in enumerate(court_assignments, start=1):
        db.execute(
            '''INSERT INTO matches
               (round_id, court_number, player1_id, player2_id, player3_id, player4_id)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (round_id, court_num, *players_on_court)
        )

db.commit()
```

**Step 9.3: Test manually - Start server and create tournament**

Run: `python app.py`
Navigate to: `http://localhost:5001`
Action: Create tournament with 2 courts and 8 players

**Step 9.4: Test manually - Complete Round 1 and start Round 2**

Action:
1. Start Round 1
2. Enter scores for all matches
3. Start Round 2
4. Verify winners moved up

Expected: Court 1 in Round 2 has winners from Round 1

**Step 9.5: Commit integration**

```bash
git add app.py
git commit -m "feat: integrate court movement into round generation"
```

---

## Task 10: Add Visual Indicators for Court Movement

**Files:**
- Modify: `templates/active_round.html`
- Modify: `static/css/style.css`

**Step 10.1: Add round number display to template**

In `templates/active_round.html`, after line 10, add:

```html
<div class="round-info">
    <h2>Round {{ round_data.round_number }}</h2>
    {% if round_data.round_number > 1 %}
        <p class="movement-note">Winners moved up • Losers moved down</p>
    {% endif %}
</div>
```

**Step 10.2: Add CSS styling for movement indicators**

In `static/css/style.css`, add at end:

```css
.round-info {
    text-align: center;
    margin: 1rem 0;
}

.movement-note {
    font-size: 0.9rem;
    color: #666;
    font-style: italic;
}

.court-card {
    position: relative;
}

.court-card::before {
    content: attr(data-movement);
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    font-size: 0.8rem;
    color: #007bff;
    font-weight: bold;
}
```

**Step 10.3: Test visual changes**

Run: `python app.py`
Navigate through: Create tournament → Round 1 → Complete matches → Round 2
Expected: See "Round 2" heading with movement note

**Step 10.4: Commit visual enhancements**

```bash
git add templates/active_round.html static/css/style.css
git commit -m "feat: add visual indicators for court movement"
```

---

## Task 11: Handle Edge Cases

**Files:**
- Modify: `court_movement.py`
- Modify: `tests/test_court_movement.py`

**Step 11.1: Write test for incomplete previous round**

```python
def test_generate_pairings_handles_incomplete_matches():
    """Test that algorithm handles incomplete previous round gracefully"""
    previous_matches = [
        {
            'court_number': 1,
            'player1_id': 1,
            'player2_id': 2,
            'player3_id': 3,
            'player4_id': 4,
            'winning_team': None,  # Not completed
            'completed': 0
        }
    ]

    # Should raise error or handle gracefully
    with pytest.raises(ValueError, match="incomplete matches"):
        generate_next_round_pairings(previous_matches, num_courts=1)
```

**Step 11.2: Run test to verify it fails**

Run: `pytest tests/test_court_movement.py::test_generate_pairings_handles_incomplete_matches -v`
Expected: FAIL (no error raised)

**Step 11.3: Add validation to generate_next_round_pairings**

```python
# At start of generate_next_round_pairings function
def generate_next_round_pairings(previous_matches, num_courts):
    """..."""

    # Validate all matches are completed
    for match in previous_matches:
        if not match.get('completed') or match.get('winning_team') is None:
            raise ValueError(
                f"Cannot generate pairings: Match {match.get('id')} has incomplete matches"
            )

    # ... rest of implementation
```

**Step 11.4: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_generate_pairings_handles_incomplete_matches -v`
Expected: PASS

**Step 11.5: Commit edge case handling**

```bash
git add court_movement.py tests/test_court_movement.py
git commit -m "feat: add validation for incomplete matches"
```

---

## Task 12: Add User Feedback for Movement

**Files:**
- Modify: `app.py:86-162`

**Step 12.1: Add flash message when starting Round 2+**

In `app.py` start_round function, after creating Round 2+ matches:

```python
else:
    # Round 2+: Movement-based pairing
    # ... existing code ...

    db.commit()

    # Add feedback message
    flash(f'Round {round_number} started! Winners moved up, losers moved down.')
```

**Step 12.2: Test flash message**

Run: `python app.py`
Action: Complete Round 1, start Round 2
Expected: See flash message "Round 2 started! Winners moved up, losers moved down."

**Step 12.3: Commit user feedback**

```bash
git add app.py
git commit -m "feat: add flash message for court movement"
```

---

## Task 13: Update Leaderboard to Show Round Performance

**Files:**
- Modify: `templates/leaderboard.html`
- Modify: `app.py:291-312` (leaderboard route)

**Step 13.1: Enhance leaderboard query to include match history**

In `app.py` leaderboard function, replace the players query (lines 305-308):

```python
# Get all players with their match statistics
players = db.execute(
    '''SELECT
        p.id,
        p.name,
        p.total_points,
        COUNT(DISTINCT s.match_id) as matches_played,
        ROUND(CAST(p.total_points AS FLOAT) /
              NULLIF(COUNT(DISTINCT s.match_id), 0) * 100, 1) as win_rate
       FROM players p
       LEFT JOIN scores s ON p.id = s.player_id
       LEFT JOIN matches m ON s.match_id = m.id
       LEFT JOIN rounds r ON m.round_id = r.id
       WHERE r.tournament_id = ?
       GROUP BY p.id, p.name, p.total_points
       ORDER BY p.total_points DESC, p.name ASC''',
    (tournament_id,)
).fetchall()
```

**Step 13.2: Update leaderboard template to display stats**

In `templates/leaderboard.html`, replace the player list section (around line 20-40):

```html
{% for player in players %}
<div class="player-row">
    <span class="rank">{{ loop.index }}</span>
    <span class="player-name">{{ player.name }}</span>
    <div class="player-stats">
        <span class="points">{{ player.total_points }} pts</span>
        <span class="matches">{{ player.matches_played }} matches</span>
        {% if player.win_rate %}
            <span class="win-rate">{{ player.win_rate }}% win</span>
        {% endif %}
    </div>
</div>
{% endfor %}
```

**Step 13.3: Add CSS for stat display**

In `static/css/style.css`, add:

```css
.player-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #eee;
}

.player-stats {
    display: flex;
    gap: 1rem;
    font-size: 0.9rem;
    color: #666;
}

.win-rate {
    color: #28a745;
    font-weight: bold;
}
```

**Step 13.4: Test leaderboard enhancements**

Run: `python app.py`
Action: Navigate to leaderboard after completing matches
Expected: See player stats with match count and win rate

**Step 13.5: Commit leaderboard enhancements**

```bash
git add app.py templates/leaderboard.html static/css/style.css
git commit -m "feat: enhance leaderboard with match statistics"
```

---

## Task 14: Add Pytest Configuration

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`

**Step 14.1: Create pytest configuration**

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**Step 14.2: Create tests package**

```python
# tests/__init__.py
# Empty file to make tests a package
```

**Step 14.3: Install pytest**

Run: `pip install pytest`
Expected: pytest installed successfully

**Step 14.4: Run full test suite**

Run: `pytest`
Expected: All court_movement tests pass

**Step 14.5: Update requirements.txt**

Run: `pip freeze | grep pytest >> requirements.txt`

**Step 14.6: Commit test configuration**

```bash
git add pytest.ini tests/__init__.py requirements.txt
git commit -m "test: add pytest configuration"
```

---

## Task 15: Integration Testing

**Files:**
- Test: Manual testing of full flow

**Step 15.1: Start server**

Run: `python app.py`
Expected: Server starts on port 5001

**Step 15.2: Test Round 1 (Random Pairing)**

Action:
1. Create tournament "Test" with 2 courts
2. Add 8 players: Alice, Bob, Carol, Dave, Eve, Frank, Grace, Hank
3. Start Round 1
4. Verify random pairing on 2 courts

Expected: 8 players distributed across 2 courts randomly

**Step 15.3: Test Score Entry**

Action:
1. Enter scores for Court 1 (Team 1 wins)
2. Enter scores for Court 2 (Team 2 wins)

Expected: Matches marked complete, leaderboard updates

**Step 15.4: Test Round 2 (Movement)**

Action:
1. Start Round 2
2. Verify Court 1 has 4 winners from Round 1
3. Verify Court 2 has 4 losers from Round 1
4. Verify teammates separated

Expected:
- Court 1: All previous winners
- Court 2: All previous losers
- No previous teammates paired together

**Step 15.5: Test Round 3 (Continued Movement)**

Action:
1. Complete Round 2 matches
2. Start Round 3
3. Verify continued movement based on Round 2 results

Expected: Movement continues to work correctly

**Step 15.6: Document test results**

Create: `docs/test-results.md` with observations

**Step 15.7: Commit test documentation**

```bash
git add docs/test-results.md
git commit -m "docs: add integration test results"
```

---

## Task 16: Update Documentation

**Files:**
- Modify: `DAILY_SUMMARY.md`
- Create: `docs/COURT_MOVEMENT.md`

**Step 16.1: Create court movement documentation**

```markdown
# Court Movement Algorithm

## Overview
The King of the Court tournament format uses dynamic court assignment based on match results.

## Rules
1. **Round 1**: Random pairing of all players
2. **Round 2+**: Position-based pairing
   - Winners move up in court order (Court 1 is highest)
   - Losers move down in court order
   - Previous teammates are separated when possible

## Algorithm Steps
1. Get results from previous round
2. Sort players by court position:
   - Court 1 winners (top)
   - Court 1 losers
   - Court 2 winners
   - Court 2 losers
   - ... (continue for all courts)
3. Redistribute to new courts:
   - Top 4 → Court 1
   - Next 4 → Court 2
   - etc.
4. Within each court, assign teams avoiding previous teammates

## Example
**Round 1:**
- Court 1: (A+B) vs (C+D) → C+D win
- Court 2: (E+F) vs (G+H) → E+F win

**Round 2:**
- Court 1: (C+E) vs (D+F) ← All winners, teammates separated
- Court 2: (A+G) vs (B+H) ← All losers, teammates separated

## Implementation
See `court_movement.py` for full implementation.
```

**Step 16.2: Update DAILY_SUMMARY.md**

Add Phase 2 completion section to DAILY_SUMMARY.md

**Step 16.3: Commit documentation**

```bash
git add docs/COURT_MOVEMENT.md DAILY_SUMMARY.md
git commit -m "docs: document court movement algorithm"
```

---

## Task 17: Final Verification

**Files:**
- Test: All components

**Step 17.1: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 17.2: Start server and verify UI**

Run: `python app.py`
Action: Click through all pages
Expected: No errors, all features work

**Step 17.3: Check for TODOs or FIXMEs**

Run: `grep -r "TODO\|FIXME" --include="*.py" --include="*.html"`
Expected: None found or all documented

**Step 17.4: Verify no debug prints**

Run: `grep -r "print(" --include="*.py" | grep -v "# print" | grep -v test_`
Expected: Only legitimate logging, no debug prints

**Step 17.5: Create completion checklist**

- ✅ Court movement algorithm implemented
- ✅ Tests passing
- ✅ Integration with Flask app
- ✅ Visual indicators added
- ✅ Edge cases handled
- ✅ Documentation complete
- ✅ Manual testing complete

**Step 17.6: Final commit**

```bash
git add .
git commit -m "feat: complete Phase 2 court movement implementation"
```

---

## Success Criteria

✅ **Round 1**: Players randomly paired across courts
✅ **Round 2+**: Winners move to higher courts, losers to lower courts
✅ **Teammate Separation**: Previous teammates are not paired together
✅ **Visual Feedback**: Users see round number and movement indicators
✅ **Leaderboard**: Shows match statistics and win rates
✅ **Tests**: All unit tests pass
✅ **Integration**: Feature works end-to-end in live tournament

---

## Architecture Decisions

**Why separate court_movement.py module?**
- Single Responsibility: Round generation logic isolated from Flask routing
- Testability: Easy to unit test without Flask context
- Reusability: Could be used in CLI version or other interfaces

**Why validate completed matches?**
- Data Integrity: Prevents generating invalid pairings
- User Feedback: Clear error messages if trying to start round early
- Debugging: Makes it obvious when state is incorrect

**Why swap strategy for teammate separation?**
- Simplicity: Simple algorithm that works for most cases
- Performance: O(n) operation, no complex optimization needed
- Good Enough: King of the Court format naturally rotates players

---

## Reference Skills

- @superpowers:test-driven-development - Write test first, watch it fail, implement
- @superpowers:verification-before-completion - Run tests before claiming complete
- @superpowers:systematic-debugging - If failures occur, investigate systematically

---

## Future Enhancements (Phase 3)

Not included in this plan:
- Match timer functionality
- Tournament history/archive
- CSV export
- Admin password protection
- Player check-in system
- More sophisticated teammate separation (graph-based matching)
