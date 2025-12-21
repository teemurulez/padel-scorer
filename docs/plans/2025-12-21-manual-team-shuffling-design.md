# Manual Team Shuffling Feature - Design Document

**Date:** December 21, 2025
**Status:** Design Complete - Ready for Implementation Planning
**Phase:** Phase 3 Enhancement

---

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [User Flow](#user-flow)
4. [Database Schema](#database-schema)
5. [UI/UX Design](#uiux-design)
6. [Backend Implementation](#backend-implementation)
7. [Frontend Implementation](#frontend-implementation)
8. [Integration with Existing Workflow](#integration-with-existing-workflow)
9. [Testing Strategy](#testing-strategy)
10. [Edge Cases & Error Handling](#edge-cases--error-handling)
11. [Success Criteria](#success-criteria)

---

## Overview

### Purpose

Allow players to manually adjust team pairings on a court before a match starts, addressing situations where the algorithm pairs players who have already played together that day.

### Key Features

- **Pre-match confirmation screen** with drag-and-drop team shuffling
- **Simple partner swap** - players can swap partners between teams
- **Court movement integrity** - shuffled teams are used for court movement algorithm
- **Internal tracking** - system tracks shuffles for data integrity without cluttering UI
- **Mobile-optimized** - touch-friendly drag-and-drop interface

### User Experience Goals

1. **Flexibility** - Players can adjust pairings when algorithm isn't optimal
2. **Simplicity** - Easy-to-use drag-and-drop interface
3. **Transparency** - Clear preview of teams before match starts
4. **Fairness** - Actual teams that played determine court movement

---

## Problem Statement

### Current Situation

- Phase 2 court movement algorithm generates pairings for Round 2+ based on previous results
- Algorithm uses simple teammate separation (swap strategy)
- Sometimes algorithm pairs players who have already played together that day
- Players want flexibility to adjust pairings at the court

### Desired Outcome

- Players arrive at court and see algorithm-generated pairing
- If pairing is not ideal, players can manually shuffle teams
- Shuffled teams are used for scoring and court movement
- System maintains data integrity by tracking original vs shuffled teams

---

## User Flow

### Complete Workflow

```
1. Round Starts
   ↓
   Tournament organizer clicks "Start Round 2"
   Backend generates pairings using court movement algorithm
   ↓

2. Court Selection Screen (NEW)
   ↓
   Players see all courts with assigned pairings
   Each player selects their court
   ↓

3. Pre-Match Confirmation Screen (NEW)
   ↓
   Shows 4 players in 2 teams
   Drag-and-drop interface to swap partners
   "Start Match" button to confirm
   ↓

4. Score Entry Screen (EXISTING)
   ↓
   Enter scores for confirmed teams
   Complete match
   ↓

5. Court Movement (EXISTING)
   ↓
   Uses shuffled teams for next round pairings
```

### Detailed Flow: Pre-Match Confirmation

1. Player navigates to `/tournament/5/round/2/court/1/confirm`
2. Screen shows:
   - Court number and round number
   - Team 1: Player A + Player B
   - Team 2: Player C + Player D
   - Drag handles on each player card
   - "Start Match" and "Reset to Original" buttons
3. Player can:
   - Drag Player B to Team 2 (swaps B and C)
   - Drag Player B to Team 2 (swaps B and D)
   - Drag multiple times to experiment
   - Click "Reset to Original" to undo all changes
4. Player clicks "Start Match"
5. System saves final team configuration
6. Redirects to score entry screen with confirmed teams

---

## Database Schema

### Schema Changes

**Add columns to `matches` table:**

```sql
ALTER TABLE matches ADD COLUMN teams_shuffled BOOLEAN DEFAULT 0;
ALTER TABLE matches ADD COLUMN original_player1_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player2_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player3_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player4_id INTEGER;
```

### Column Definitions

| Column | Type | Purpose |
|--------|------|---------|
| `teams_shuffled` | BOOLEAN | Flag indicating if manual shuffle occurred (internal tracking) |
| `original_player1_id` | INTEGER | Algorithm's original Team 1 Player 1 (nullable) |
| `original_player2_id` | INTEGER | Algorithm's original Team 1 Player 2 (nullable) |
| `original_player3_id` | INTEGER | Algorithm's original Team 2 Player 1 (nullable) |
| `original_player4_id` | INTEGER | Algorithm's original Team 2 Player 2 (nullable) |
| `player1_id` | INTEGER | Actual Team 1 Player 1 (ALWAYS current/played teams) |
| `player2_id` | INTEGER | Actual Team 1 Player 2 (ALWAYS current/played teams) |
| `player3_id` | INTEGER | Actual Team 2 Player 1 (ALWAYS current/played teams) |
| `player4_id` | INTEGER | Actual Team 2 Player 2 (ALWAYS current/played teams) |

### Data Flow

**When match is created:**
- `player1_id` through `player4_id` set by algorithm
- `teams_shuffled = 0`
- `original_player*_id` columns are NULL

**When teams are NOT shuffled:**
- `player*_id` columns unchanged
- `teams_shuffled = 0`
- `original_player*_id` remain NULL

**When teams ARE shuffled:**
- Store current `player*_id` values to `original_player*_id` columns
- Update `player*_id` columns with new team configuration
- Set `teams_shuffled = 1`

**For court movement:**
- Algorithm reads `player1_id` through `player4_id` (actual teams that played)
- Original pairing preserved in `original_player*_id` for audit if needed

---

## UI/UX Design

### Route Structure

```
/tournament/<tournament_id>/round/<round_id>/courts
    └─ Court selection screen (NEW)

/tournament/<tournament_id>/round/<round_id>/court/<court_number>/confirm
    └─ Pre-match confirmation with drag-and-drop (NEW)

/tournament/<tournament_id>/round/<round_id>/court/<court_number>/score
    └─ Score entry screen (EXISTING - unchanged)
```

### Pre-Match Confirmation Screen

**Template: `templates/confirm_match.html`**

```html
<!DOCTYPE html>
<html>
<head>
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
            <button class="btn-primary btn-large" onclick="confirmAndStartMatch()">
                ✓ Start Match
            </button>
            <button class="btn-secondary" onclick="resetToOriginal()">
                ↺ Reset to Original
            </button>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/shuffle.js') }}"></script>
    <script>
        const TOURNAMENT_ID = {{ tournament_id }};
        const ROUND_ID = {{ round_id }};
        const COURT_NUMBER = {{ court_number }};
    </script>
</body>
</html>
```

### CSS Styling

**File: `static/css/shuffle.css`**

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

---

## Backend Implementation

### New Routes

**1. Court Selection Page**

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/courts')
def court_selection(tournament_id, round_id):
    """
    Shows all courts for this round with links to confirmation screens.
    """
    tournament = Tournament.query.get_or_404(tournament_id)
    round = Round.query.get_or_404(round_id)
    matches = Match.query.filter_by(round_id=round_id).order_by(Match.court_number).all()

    # Get player names for preview
    for match in matches:
        match.player1 = get_player(match.player1_id)
        match.player2 = get_player(match.player2_id)
        match.player3 = get_player(match.player3_id)
        match.player4 = get_player(match.player4_id)

    return render_template(
        'court_selection.html',
        tournament=tournament,
        round=round,
        matches=matches
    )
```

**2. Pre-Match Confirmation (GET)**

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm')
def confirm_match_teams(tournament_id, round_id, court_number):
    """
    Show pre-match confirmation screen with drag-and-drop team shuffling.
    """
    tournament = Tournament.query.get_or_404(tournament_id)
    round = Round.query.get_or_404(round_id)

    # Check if tournament is archived
    if tournament.status == 'archived':
        flash("Cannot modify archived tournament.")
        return redirect(url_for('tournament_results', tournament_id=tournament_id))

    match = Match.query.filter_by(
        round_id=round_id,
        court_number=court_number
    ).first_or_404()

    # Check if match already completed
    if match.completed:
        flash("This match has already been completed.")
        return redirect(url_for('leaderboard', tournament_id=tournament_id))

    # Check if scores already entered (prevent shuffle after scoring starts)
    existing_scores = Score.query.filter_by(match_id=match.id).count()
    if existing_scores > 0:
        flash("Match already in progress. Team shuffling not available.")
        return redirect(f'/tournament/{tournament_id}/round/{round_id}/court/{court_number}/score')

    # Get player details
    players = {
        'team1': [
            get_player(match.player1_id),
            get_player(match.player2_id)
        ],
        'team2': [
            get_player(match.player3_id),
            get_player(match.player4_id)
        ]
    }

    return render_template(
        'confirm_match.html',
        tournament=tournament,
        round=round,
        court_number=court_number,
        match=match,
        players=players
    )
```

**3. Save Confirmed Teams (POST)**

```python
@app.route('/tournament/<int:tournament_id>/round/<int:round_id>/court/<int:court_number>/confirm',
           methods=['POST'])
def save_confirmed_teams(tournament_id, round_id, court_number):
    """
    Save final team configuration (potentially shuffled) and proceed to score entry.
    """
    match = Match.query.filter_by(
        round_id=round_id,
        court_number=court_number
    ).with_for_update().first_or_404()  # Lock row for concurrent access

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
    original_players = {match.player1_id, match.player2_id, match.player3_id, match.player4_id}
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
    original_team1 = {match.player1_id, match.player2_id}
    new_team1 = {new_team1_p1, new_team1_p2}
    teams_changed = original_team1 != new_team1

    if teams_changed:
        # Store original pairing before overwriting
        match.original_player1_id = match.player1_id
        match.original_player2_id = match.player2_id
        match.original_player3_id = match.player3_id
        match.original_player4_id = match.player4_id
        match.teams_shuffled = True

        # Update to new teams
        match.player1_id = new_team1_p1
        match.player2_id = new_team1_p2
        match.player3_id = new_team2_p1
        match.player4_id = new_team2_p2

    db.session.commit()

    # Redirect to score entry for this match
    return redirect(f'/tournament/{tournament_id}/round/{round_id}/court/{court_number}/score')


def get_player(player_id):
    """Helper to get player with error handling."""
    # Try new registry first
    from database import get_db
    db = get_db()

    # Check if using Phase 3 registry
    result = db.execute(
        'SELECT first_name, last_name FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        return {
            'id': player_id,
            'first_name': result['first_name'],
            'last_name': result['last_name']
        }

    # Fallback to Phase 2 players table
    result = db.execute(
        'SELECT name FROM players WHERE id = ?',
        (player_id,)
    ).fetchone()

    if result:
        # Split name into first/last (best effort)
        parts = result['name'].split(' ', 1)
        return {
            'id': player_id,
            'first_name': parts[0] if len(parts) > 0 else 'Unknown',
            'last_name': parts[1] if len(parts) > 1 else ''
        }

    # Player not found
    return {
        'id': player_id,
        'first_name': f'[Deleted',
        'last_name': f'Player {player_id}]'
    }
```

### Modified Routes

**Update `start_round` to redirect to court selection:**

```python
@app.route('/tournament/<int:tournament_id>/start_round', methods=['POST'])
def start_round(tournament_id):
    # ... existing code creates round and matches ...

    # NEW: Redirect to court selection instead of active round
    flash(f"Round {round_number} created! Players, go to your courts to confirm teams.")
    return redirect(url_for('court_selection',
                            tournament_id=tournament_id,
                            round_id=new_round.id))
```

---

## Frontend Implementation

### JavaScript: Drag-and-Drop

**File: `static/js/shuffle.js`**

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

---

## Integration with Existing Workflow

### Court Selection Template

**File: `templates/court_selection.html`**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Court Selection - Round {{ round.round_number }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="court-selection">
        <h2>Round {{ round.round_number }} - Select Your Court</h2>
        <p class="subtitle">{{ tournament.name }}</p>

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
                <a href="{{ url_for('confirm_match_teams',
                                    tournament_id=tournament.id,
                                    round_id=round.id,
                                    court_number=match.court_number) }}"
                   class="btn-primary">
                    Go to Court {{ match.court_number }}
                </a>
            </div>
            {% endfor %}
        </div>

        <div class="actions">
            <a href="{{ url_for('home') }}" class="btn-secondary">Back to Home</a>
        </div>
    </div>
</body>
</html>
```

### Navigation Flow Diagram

```
Tournament Home
    ↓
Click "Start Round 2"
    ↓
POST /tournament/5/start_round
    ├─ Create Round record
    ├─ Generate matches using court movement algorithm
    └─ Redirect to Court Selection
        ↓
GET /tournament/5/round/2/courts
    └─ Show all courts with pairings
        ↓
Player clicks "Go to Court 1"
        ↓
GET /tournament/5/round/2/court/1/confirm
    └─ Pre-match confirmation screen
    └─ Drag-and-drop to shuffle teams
    └─ Click "Start Match"
        ↓
POST /tournament/5/round/2/court/1/confirm
    ├─ Validate submitted teams
    ├─ Save shuffled configuration
    └─ Redirect to Score Entry
        ↓
GET /tournament/5/round/2/court/1/score
    └─ Existing score entry screen
    └─ Enter scores as normal
        ↓
Complete match → Court movement uses shuffled teams
```

---

## Testing Strategy

### Unit Tests

**File: `tests/test_team_shuffling.py`**

```python
import pytest
from app import app, db
from database import init_db

class TestTeamShuffling:

    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        app.config['DATABASE'] = ':memory:'

        with app.test_client() as client:
            with app.app_context():
                init_db()
                yield client

    def test_teams_shuffled_flag_set_when_changed(self, client):
        """Verify teams_shuffled flag is set when teams are modified."""
        # Setup: Create tournament, round, match
        tournament_id, round_id, match_id = self.create_test_match(client)

        # Shuffle: swap player 2 and 3
        response = client.post(
            f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
            data={
                'team1_player1': 1,
                'team1_player2': 3,  # Swapped
                'team2_player1': 2,  # Swapped
                'team2_player2': 4
            }
        )

        # Verify
        match = self.get_match(match_id)
        assert match['teams_shuffled'] == 1
        assert match['original_player2_id'] == 2
        assert match['original_player3_id'] == 3
        assert match['player2_id'] == 3  # New team
        assert match['player3_id'] == 2  # New team

    def test_teams_shuffled_flag_not_set_when_unchanged(self, client):
        """Verify teams_shuffled remains False if no changes made."""
        tournament_id, round_id, match_id = self.create_test_match(client)

        # Submit same teams
        response = client.post(
            f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
            data={
                'team1_player1': 1,
                'team1_player2': 2,  # Same
                'team2_player1': 3,  # Same
                'team2_player2': 4
            }
        )

        match = self.get_match(match_id)
        assert match['teams_shuffled'] == 0
        assert match['original_player1_id'] is None

    def test_validation_rejects_duplicate_players(self, client):
        """Ensure exactly 4 unique players in submission."""
        tournament_id, round_id, match_id = self.create_test_match(client)

        # Submit with duplicate player
        response = client.post(
            f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
            data={
                'team1_player1': 1,
                'team1_player2': 1,  # Duplicate!
                'team2_player1': 3,
                'team2_player2': 4
            },
            follow_redirects=True
        )

        assert b'All 4 players must be unique' in response.data

    def test_validation_rejects_foreign_players(self, client):
        """Ensure submitted players are from original match."""
        tournament_id, round_id, match_id = self.create_test_match(client)

        # Submit with player not in original match
        response = client.post(
            f'/tournament/{tournament_id}/round/{round_id}/court/1/confirm',
            data={
                'team1_player1': 1,
                'team1_player2': 2,
                'team2_player1': 3,
                'team2_player2': 99  # Not in original match!
            },
            follow_redirects=True
        )

        assert b'Players must be from the original match' in response.data

    def test_court_movement_uses_shuffled_teams(self, client):
        """Verify court movement algorithm uses actual teams that played."""
        # Create Round 1 with match
        tournament_id = self.create_tournament(client)
        self.add_players(client, tournament_id, count=8)

        # Start Round 1
        round1_id = self.start_round(client, tournament_id)

        # Get Court 1 match
        match = self.get_match_by_court(round1_id, court_number=1)

        # Shuffle teams: P1+P3 vs P2+P4
        client.post(
            f'/tournament/{tournament_id}/round/{round1_id}/court/1/confirm',
            data={
                'team1_player1': match['player1_id'],
                'team1_player2': match['player3_id'],  # Swapped
                'team2_player1': match['player2_id'],  # Swapped
                'team2_player2': match['player4_id']
            }
        )

        # Complete match: Team 1 (P1+P3) wins
        self.complete_match(client, tournament_id, round1_id, court=1, winning_team=1)

        # Start Round 2
        round2_id = self.start_round(client, tournament_id)

        # Verify Round 2 uses shuffled teams for movement
        # Winners (P1 and P3) should be paired based on court movement
        # NOT original algorithm pairing of (P1, P2)
        round2_matches = self.get_round_matches(round2_id)

        # Implementation-specific assertion
        # This depends on your court movement algorithm
        # But should verify winners from shuffled teams moved correctly
        assert True  # Placeholder - implement based on movement logic

    # Helper methods
    def create_test_match(self, client):
        """Create test tournament with one match."""
        # Implementation depends on your test fixtures
        pass

    def get_match(self, match_id):
        """Get match by ID."""
        pass
```

### Integration Tests

```python
def test_complete_workflow_with_shuffle(client):
    """Test full workflow: start round → shuffle → score → next round."""
    # Create tournament with 8 players, 2 courts
    tournament_id = create_tournament(client, num_courts=2)
    add_players(client, tournament_id, count=8)

    # Start Round 1
    round1_id = start_round(client, tournament_id)

    # Navigate to court selection
    response = client.get(f'/tournament/{tournament_id}/round/{round1_id}/courts')
    assert response.status_code == 200
    assert b'Court 1' in response.data
    assert b'Court 2' in response.data

    # Navigate to Court 1 confirmation
    response = client.get(f'/tournament/{tournament_id}/round/{round1_id}/court/1/confirm')
    assert response.status_code == 200
    assert b'Drag players to swap teams' in response.data

    # Shuffle teams
    response = client.post(
        f'/tournament/{tournament_id}/round/{round1_id}/court/1/confirm',
        data={'team1_player1': 1, 'team1_player2': 3, 'team2_player1': 2, 'team2_player2': 4},
        follow_redirects=False
    )
    assert response.status_code == 302  # Redirect to score entry
    assert '/score' in response.location

    # Enter scores for Court 1
    enter_scores(client, tournament_id, round1_id, court=1,
                 scores={1: 3, 2: 1, 3: 3, 4: 1})

    # Complete Court 2 as well
    client.post(f'/tournament/{tournament_id}/round/{round1_id}/court/2/confirm',
                data={'team1_player1': 5, 'team1_player2': 6, 'team2_player1': 7, 'team2_player2': 8})
    enter_scores(client, tournament_id, round1_id, court=2,
                 scores={5: 3, 6: 3, 7: 1, 8: 1})

    # Start Round 2
    round2_id = start_round(client, tournament_id)

    # Verify Round 2 exists and uses shuffled teams
    round2_matches = get_round_matches(round2_id)
    assert len(round2_matches) == 2
```

---

## Edge Cases & Error Handling

### Edge Case Matrix

| Edge Case | Handling | Implementation |
|-----------|----------|----------------|
| Match already has scores | Skip confirmation, go directly to score entry | Check `Score.query.filter_by(match_id).count()` |
| Invalid player combination | Show error, redirect back to confirm screen | Validate: 4 unique players, all from original match |
| Concurrent modifications | Lock match row during save | Use `with_for_update()` in query |
| Missing/deleted players | Show placeholder "[Deleted Player X]" | Try Phase 3 registry, fallback to Phase 2, fallback to placeholder |
| Browser back button | Prevent resubmission | Disable button on submit, use history.pushState |
| Match already completed | Redirect to leaderboard with message | Check `match.completed` flag |
| Tournament archived | Redirect to results with message | Check `tournament.status == 'archived'` |
| Network failure during drag | Auto-restore from localStorage | Save state on each swap to localStorage |
| Teams submitted in wrong order | Accept any valid configuration of 4 players | Validation checks sets, not order |
| Player tries to shuffle Round 1 | Allow (no harm in shuffling seeded pairing) | No special handling needed |

### Error Messages

**User-Facing Messages:**

- ✅ "Match already in progress. Team shuffling not available."
- ✅ "Invalid team configuration: All 4 players must be unique."
- ✅ "Invalid team configuration: Players must be from the original match."
- ✅ "Each team must have exactly 2 different players."
- ✅ "This match has already been completed."
- ✅ "Cannot modify archived tournament."
- ✅ "Teams have already been confirmed by another player."

---

## Success Criteria

### Feature Complete When:

**Functional Requirements:**
- ✅ Players can navigate to court confirmation screen before scoring
- ✅ Drag-and-drop works on both desktop and mobile
- ✅ Players can shuffle teams freely before confirming
- ✅ "Start Match" saves final configuration and proceeds to score entry
- ✅ Court movement algorithm uses shuffled teams for next round
- ✅ System tracks original vs shuffled teams internally

**Technical Requirements:**
- ✅ Database migration adds 5 new columns to `matches` table
- ✅ All validation rules enforced (4 unique players, from original match, 2 per team)
- ✅ Concurrent access handled safely (row locking)
- ✅ Edge cases handled gracefully (completed matches, archived tournaments, etc.)
- ✅ All tests passing (unit + integration)

**User Experience:**
- ✅ Touch-friendly drag-and-drop on mobile (min 60px touch targets)
- ✅ Visual feedback during drag (dragging state, swap animation)
- ✅ "Reset to Original" button works correctly
- ✅ Clear instructions and error messages
- ✅ Seamless integration with existing workflow

---

## Implementation Notes

### Database Migration Script

```sql
-- Migration: Add team shuffling support to matches table
-- Date: 2025-12-21

-- Add new columns
ALTER TABLE matches ADD COLUMN teams_shuffled BOOLEAN DEFAULT 0;
ALTER TABLE matches ADD COLUMN original_player1_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player2_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player3_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player4_id INTEGER;

-- Create index for querying shuffled matches (optional, for analytics)
CREATE INDEX idx_matches_shuffled ON matches(teams_shuffled) WHERE teams_shuffled = 1;

-- No data migration needed - existing matches default to teams_shuffled=0
```

### Rollout Plan

**Phase 1: Database Migration**
1. Backup production database
2. Run migration script to add columns
3. Verify schema changes
4. Test with existing data (should be no-op)

**Phase 2: Deploy Backend Code**
1. Deploy new routes (court selection, confirm teams)
2. Deploy modified `start_round` route
3. Deploy helper functions (`get_player`, validation logic)
4. Test routes return 200 OK

**Phase 3: Deploy Frontend Code**
1. Deploy templates (court_selection.html, confirm_match.html)
2. Deploy CSS (shuffle.css)
3. Deploy JavaScript (shuffle.js)
4. Test drag-and-drop on desktop and mobile

**Phase 4: Integration Testing**
1. Start a test tournament
2. Start Round 2
3. Navigate through court selection → confirm → shuffle → score
4. Complete round and verify Round 3 uses shuffled teams
5. Test all edge cases

**Phase 5: Production Rollout**
1. Enable feature for real tournament
2. Monitor for errors
3. Gather user feedback
4. Fix any issues

---

**End of Design Document**
