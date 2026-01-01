# Round 1 Court Assignment Editor - Design Document

**Date:** 2026-01-01
**Status:** Design Complete
**Feature:** Manual adjustment of Round 1 court assignments and team pairings in Admin Dashboard

## Overview

Allow tournament administrators to preview and manually adjust Round 1 court assignments before starting the tournament. The seeding algorithm provides smart defaults, but admins can override assignments to separate friends, balance courts differently, or accommodate special requests.

## Requirements Summary

### User Story
As a tournament administrator, I want to:
1. See the seeded Round 1 court assignments before starting the tournament
2. Manually adjust which players are on which courts
3. Control team pairings within each court (Team 1 vs Team 2)
4. Save custom pairings for later use
5. Start Round 1 using my saved custom pairings

### Constraints
- Feature only available for tournaments in "setup" status
- Must work within existing Admin Dashboard edit form
- Saved pairings must be invalidated if player list changes
- Must integrate seamlessly with existing seeding algorithm

## Architecture

### Database Schema

#### New Table: `round1_preview_pairings`

```sql
CREATE TABLE round1_preview_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    court_number INTEGER NOT NULL,
    team1_player1_id INTEGER NOT NULL,
    team1_player2_id INTEGER NOT NULL,
    team2_player1_id INTEGER NOT NULL,
    team2_player2_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (team1_player1_id) REFERENCES player_registry(id),
    FOREIGN KEY (team1_player2_id) REFERENCES player_registry(id),
    FOREIGN KEY (team2_player1_id) REFERENCES player_registry(id),
    FOREIGN KEY (team2_player2_id) REFERENCES player_registry(id),
    UNIQUE(tournament_id, court_number)
);
```

**Data Model:**
- Each row represents one court's complete team configuration
- Tournament with N courts has N rows in this table
- CASCADE DELETE: Preview pairings deleted when tournament deleted
- UNIQUE constraint prevents duplicate court numbers per tournament

**Data Validation:**
- All 4 player IDs must exist in `tournament_players` for this tournament
- No duplicate players within a court
- No duplicate players across courts
- Court numbers must be sequential 1 to N

**Lifecycle:**
- **Created:** Admin clicks "Preview Round 1" (populated by seeding algorithm)
- **Updated:** Admin swaps players and saves changes
- **Deleted:** Player list changes OR number of courts changes OR Round 1 starts

### UI Components

#### Location
Integrated into existing Admin Dashboard expandable edit form (below player list textarea).

#### Layout

```
┌─────────────────────────────────────────────────┐
│ Edit Tournament                                 │
├─────────────────────────────────────────────────┤
│ Tournament Name: [________________]             │
│ Number of Courts: [__]                          │
│ Players (8 required):                           │
│ [Textarea with player names]                    │
│                                                  │
│ ┌─ Round 1 Court Assignments ─────────────┐    │
│ │ [Preview Round 1] button                 │    │
│ │                                           │    │
│ │ (After clicking Preview:)                 │    │
│ │                                           │    │
│ │ ╔═══ Court 1 ════════════════════════╗   │    │
│ │ ║ Team 1        │ Team 2             ║   │    │
│ │ ║ □ Alice Smith │ □ Bob Johnson      ║   │    │
│ │ ║ □ Carol Lee   │ □ David Wong       ║   │    │
│ │ ╚════════════════════════════════════╝   │    │
│ │                                           │    │
│ │ ╔═══ Court 2 ════════════════════════╗   │    │
│ │ ║ Team 1        │ Team 2             ║   │    │
│ │ ║ □ Eve Martinez│ □ Frank Chen       ║   │    │
│ │ ║ □ Grace Park  │ □ Henry Liu        ║   │    │
│ │ ╚════════════════════════════════════╝   │    │
│ │                                           │    │
│ │ [Save Round 1 Pairings]  [Reset]      │    │
│ └───────────────────────────────────────┘    │
│                                                  │
│ [Save Tournament Changes]  [Cancel]             │
└──────────────────────────────────────────────────┘
```

#### Visual Interaction (Click-Then-Click)

**Player Selection:**
1. **First Click:** Player box highlighted with **yellow border + checkmark** (selected state)
2. **Second Click (different player):** Swap animation (500ms slide), then deselect both
3. **Click outside/same player:** Deselect (remove highlight)

**Visual Feedback:**
- Selected player: `border: 3px solid #FFD700; background: #FFFACD;`
- Swap animation: CSS transition on position change
- Court headers show court number and total players (e.g., "Court 1 (4 players)")

#### Button States

| Button | Enabled When | Action |
|--------|--------------|--------|
| Preview Round 1 | Player count = num_courts × 4 | Generate pairings using seeding algorithm |
| Save Round 1 Pairings | Preview exists and modified | Save custom pairings to database |
| Reset | Preview exists | Regenerate pairings (discard changes) |

### Frontend Implementation

#### JavaScript State Management

```javascript
// Global state
let selectedPlayer = null;  // {playerId, courtNum, team, position}
let pairingsData = [];      // Current court assignments
let originalPairingsData = []; // For detecting modifications

// Example pairingsData structure:
[
  {
    court: 1,
    team1: [playerId1, playerId2],
    team2: [playerId3, playerId4]
  },
  {
    court: 2,
    team1: [playerId5, playerId6],
    team2: [playerId7, playerId8]
  }
]
```

#### Click-Then-Click Logic

```javascript
function handlePlayerClick(playerId, courtNum, team, position) {
    if (!selectedPlayer) {
        // First click: Select player
        selectedPlayer = {playerId, courtNum, team, position};
        highlightPlayer(playerId);
    } else if (selectedPlayer.playerId === playerId) {
        // Clicked same player: Deselect
        selectedPlayer = null;
        unhighlightAll();
    } else {
        // Second click: Swap players
        swapPlayers(selectedPlayer, {playerId, courtNum, team, position});
        selectedPlayer = null;
        unhighlightAll();
    }
}

function swapPlayers(player1, player2) {
    const p1Court = pairingsData.find(c => c.court === player1.courtNum);
    const p2Court = pairingsData.find(c => c.court === player2.courtNum);

    // Swap player IDs in data structure
    [p1Court[player1.team][player1.position],
     p2Court[player2.team][player2.position]] =
    [p2Court[player2.team][player2.position],
     p1Court[player1.team][player1.position]];

    // Re-render with animation
    renderCourts(pairingsData);
}
```

#### API Integration

```javascript
// Preview Round 1
async function previewRound1(tournamentId) {
    const response = await fetch(
        `/admin/tournaments/${tournamentId}/preview-round1`,
        {method: 'POST'}
    );
    const data = await response.json();
    pairingsData = data.pairings;
    originalPairingsData = JSON.parse(JSON.stringify(data.pairings));
    renderCourts(pairingsData);
}

// Save Custom Pairings
async function savePairings(tournamentId) {
    const response = await fetch(
        `/admin/tournaments/${tournamentId}/save-round1-pairings`,
        {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                pairings: pairingsData,
                last_modified: lastModifiedTimestamp
            })
        }
    );

    if (response.ok) {
        showSuccessMessage("Round 1 pairings saved!");
        originalPairingsData = JSON.parse(JSON.stringify(pairingsData));
    } else {
        const error = await response.json();
        showErrorMessage(error.message);
    }
}

// Reset to Algorithm Defaults
async function resetPairings(tournamentId) {
    if (confirm('Reset to algorithm-generated pairings? Your changes will be lost.')) {
        await previewRound1(tournamentId);
    }
}
```

### Backend Implementation

#### New Flask Routes

##### 1. POST `/admin/tournaments/<id>/preview-round1`

**Purpose:** Generate Round 1 preview using seeding algorithm

**Request:** Empty POST

**Response:**
```json
{
  "pairings": [
    {
      "court": 1,
      "team1": [1, 2],
      "team2": [3, 4]
    },
    {
      "court": 2,
      "team1": [5, 6],
      "team2": [7, 8]
    }
  ],
  "players": {
    "1": {"first_name": "Alice", "last_name": "Smith"},
    "2": {"first_name": "Bob", "last_name": "Johnson"},
    ...
  }
}
```

**Implementation:**
```python
@app.route('/admin/tournaments/<int:tournament_id>/preview-round1', methods=['POST'])
def admin_preview_round1(tournament_id):
    """Generate Round 1 preview using seeding algorithm"""
    db = get_db_connection()

    # Validate tournament
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ? AND status = ?',
        (tournament_id, 'setup')
    ).fetchone()

    if not tournament:
        return {'error': 'Tournament not found or not in setup'}, 404

    # Get players with seeding
    players_with_seeds = db.execute("""
        SELECT p.id, COALESCE(ps.seed_points, 0) as seed_points
        FROM player_registry p
        JOIN tournament_players tp ON p.id = tp.player_id
        LEFT JOIN player_seeding ps ON p.id = ps.player_id
        WHERE tp.tournament_id = ?
        ORDER BY seed_points DESC
    """, (tournament_id,)).fetchall()

    # Generate seeded pairings
    from seeded_pairing import generate_seeded_round1_pairings
    players_with_seeds = [dict(p) for p in players_with_seeds]
    court_assignments = generate_seeded_round1_pairings(
        players_with_seeds,
        tournament['num_courts']
    )

    # Clear existing preview pairings
    db.execute(
        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    )

    # Store in preview table
    for court_num, player_ids in enumerate(court_assignments, start=1):
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, court_num, *player_ids))

    db.commit()

    # Return formatted data for frontend
    return jsonify(format_pairings_for_frontend(tournament_id, db))
```

##### 2. POST `/admin/tournaments/<id>/save-round1-pairings`

**Purpose:** Save custom Round 1 pairings

**Request:**
```json
{
  "pairings": [
    {"court": 1, "team1": [1, 2], "team2": [3, 4]},
    {"court": 2, "team1": [5, 6], "team2": [7, 8]}
  ],
  "last_modified": "2026-01-01T10:30:00"
}
```

**Response:**
```json
{"success": true}
```

**Errors:**
```json
{
  "errors": [
    "Player 5 not in tournament",
    "Duplicate players in Court 2"
  ]
}
```

**Implementation:**
```python
@app.route('/admin/tournaments/<int:tournament_id>/save-round1-pairings',
           methods=['POST'])
def admin_save_round1_pairings(tournament_id):
    """Save custom Round 1 pairings"""
    db = get_db_connection()
    pairings = request.json.get('pairings', [])

    # Validation
    errors = validate_pairings(tournament_id, pairings, db)
    if errors:
        return {'errors': errors}, 400

    # Clear existing pairings
    db.execute(
        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    )

    # Save new pairings
    for court in pairings:
        db.execute("""
            INSERT INTO round1_preview_pairings
            (tournament_id, court_number, team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tournament_id,
            court['court'],
            court['team1'][0], court['team1'][1],
            court['team2'][0], court['team2'][1]
        ))

    db.commit()
    return {'success': True}
```

##### 3. Helper: Validation Function

```python
def validate_pairings(tournament_id, pairings, db):
    """Validate custom pairings before saving"""
    errors = []

    # Get valid player IDs for this tournament
    tournament_players = db.execute(
        'SELECT player_id FROM tournament_players WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()
    valid_player_ids = {p['player_id'] for p in tournament_players}

    all_players = []

    for court in pairings:
        court_players = court['team1'] + court['team2']

        # Validate all players exist in tournament
        for pid in court_players:
            if pid not in valid_player_ids:
                errors.append(f"Player {pid} not in tournament")

        # Validate no duplicates within court
        if len(court_players) != len(set(court_players)):
            errors.append(f"Duplicate players in Court {court['court']}")

        # Validate each team has exactly 2 players
        if len(court['team1']) != 2 or len(court['team2']) != 2:
            errors.append(f"Court {court['court']} teams must have 2 players each")

        all_players.extend(court_players)

    # Validate no duplicates across courts
    if len(all_players) != len(set(all_players)):
        errors.append("Player assigned to multiple courts")

    # Validate all tournament players are assigned
    if set(all_players) != valid_player_ids:
        missing = valid_player_ids - set(all_players)
        errors.append(f"Not all players assigned. Missing: {missing}")

    return errors
```

### Integration with Start Round

#### Modified `start_round()` Function

**Key Change:** Check for saved custom pairings before using seeding algorithm.

```python
@app.route('/tournament/<int:tournament_id>/start_round', methods=['GET', 'POST'])
def start_round(tournament_id):
    """Generate a new round with seeded/custom pairs"""
    db = get_db_connection()

    # ... existing validation code ...

    if request.method == 'POST':
        # ... existing round creation code ...

        round_number = 1 if not last_round else last_round['round_number'] + 1

        cursor = db.execute(
            'INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)',
            (tournament_id, round_number)
        )
        round_id = cursor.lastrowid

        if round_number == 1:
            # NEW: Check for saved custom pairings first
            saved_pairings = db.execute("""
                SELECT * FROM round1_preview_pairings
                WHERE tournament_id = ?
                ORDER BY court_number
            """, (tournament_id,)).fetchall()

            if saved_pairings:
                # Use saved custom pairings
                for pairing in saved_pairings:
                    db.execute('''
                        INSERT INTO matches
                        (round_id, court_number, player1_id, player2_id,
                         player3_id, player4_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        round_id,
                        pairing['court_number'],
                        pairing['team1_player1_id'],
                        pairing['team1_player2_id'],
                        pairing['team2_player1_id'],
                        pairing['team2_player2_id']
                    ))

                # Delete used pairings
                db.execute(
                    'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
                    (tournament_id,)
                )
                db.commit()

                flash('Round 1 started with your custom pairings!')
            else:
                # EXISTING: Use seeding algorithm
                from seeded_pairing import generate_seeded_round1_pairings
                # ... existing seeding algorithm code ...
                flash('Round 1 started with seeded pairings')
        else:
            # Round 2+: Use movement algorithm (no changes)
            # ... existing code ...

        # ... rest of existing code ...
```

### Edge Cases & Error Handling

#### 1. Player List Changes

**Scenario:** Admin saves custom pairings, then edits player list (add/remove players).

**Behavior:** Clear saved pairings with warning.

**Implementation:**

```python
# Modified admin_edit_tournament() route
@app.route('/admin/tournaments/<int:tournament_id>/edit', methods=['POST'])
def admin_edit_tournament(tournament_id):
    db = get_db_connection()

    # Get current player IDs
    current_players = db.execute(
        'SELECT player_id FROM tournament_players WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()
    current_player_ids = {p['player_id'] for p in current_players}

    # Parse new player list from form
    new_player_ids = get_player_ids_from_form(request.form.get('players'), db)

    # Check if player list changed
    if current_player_ids != new_player_ids:
        # Clear saved Round 1 pairings
        db.execute(
            'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        )
        flash('⚠️ Player list changed - Round 1 pairings have been reset', 'warning')

    # ... rest of update logic ...
```

**Frontend Warning:**
```javascript
function checkPlayerListChanged(originalPlayers, newPlayers, hasPairings) {
    if (hasPairings && !arraysEqual(originalPlayers, newPlayers)) {
        return confirm(
            '⚠️ Warning: Changing the player list will reset your ' +
            'custom Round 1 pairings. Continue?'
        );
    }
    return true;
}
```

#### 2. Number of Courts Changes

**Scenario:** Admin saves pairings for 2 courts, then changes num_courts to 3.

**Behavior:** Clear saved pairings (incompatible structure).

**Implementation:**
```python
# In admin_edit_tournament()
if tournament['num_courts'] != new_num_courts:
    db.execute(
        'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    )
    flash('⚠️ Number of courts changed - Round 1 pairings reset', 'warning')
```

#### 3. Invalid Pairings on Start Round 1

**Scenario:** Saved pairings exist but reference deleted/invalid players.

**Behavior:** Detect mismatch, delete invalid pairings, fallback to algorithm.

**Implementation:**
```python
def validate_saved_pairings_still_valid(tournament_id, db):
    """Check if saved pairings match current tournament players"""
    saved_pairings = db.execute(
        'SELECT * FROM round1_preview_pairings WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()

    if not saved_pairings:
        return True  # No saved pairings

    # Extract all player IDs from saved pairings
    pairing_player_ids = set()
    for p in saved_pairings:
        pairing_player_ids.update([
            p['team1_player1_id'], p['team1_player2_id'],
            p['team2_player1_id'], p['team2_player2_id']
        ])

    # Get current tournament players
    current_players = db.execute(
        'SELECT player_id FROM tournament_players WHERE tournament_id = ?',
        (tournament_id,)
    ).fetchall()
    current_player_ids = {p['player_id'] for p in current_players}

    # If mismatch, delete invalid pairings
    if pairing_player_ids != current_player_ids:
        db.execute(
            'DELETE FROM round1_preview_pairings WHERE tournament_id = ?',
            (tournament_id,)
        )
        db.commit()
        return False  # Invalid pairings deleted

    return True  # Pairings valid
```

**Call in start_round() before using saved pairings:**
```python
if round_number == 1:
    if validate_saved_pairings_still_valid(tournament_id, db):
        saved_pairings = db.execute(...).fetchall()
        # Use saved pairings
    else:
        # Fallback to algorithm
        flash('⚠️ Saved pairings were invalid - using seeded pairings', 'warning')
```

#### 4. Tournament Deleted

**Scenario:** Tournament deleted while preview pairings exist.

**Behavior:** Automatic cleanup via CASCADE DELETE.

**Implementation:** Already handled by foreign key constraint:
```sql
FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
```

#### 5. Concurrent Admin Edits

**Scenario:** Two admins editing same tournament's Round 1 pairings simultaneously.

**Behavior:** Optimistic locking with modified_at timestamp.

**Implementation:**
```python
# In save_round1_pairings()
last_modified_client = request.json.get('last_modified')

if last_modified_client:
    current_modified = db.execute("""
        SELECT MAX(modified_at) FROM round1_preview_pairings
        WHERE tournament_id = ?
    """, (tournament_id,)).fetchone()[0]

    if current_modified and current_modified > last_modified_client:
        return {
            'error': 'Pairings were modified by another admin. Please refresh.'
        }, 409
```

## Testing Strategy

### Unit Tests

1. **Validation Tests:**
   - `test_validate_pairings_valid()`
   - `test_validate_pairings_duplicate_player()`
   - `test_validate_pairings_missing_player()`
   - `test_validate_pairings_invalid_player_id()`

2. **Database Tests:**
   - `test_create_preview_pairings()`
   - `test_delete_preview_pairings_on_tournament_delete()`
   - `test_unique_constraint_court_number()`

### Integration Tests

3. **API Tests:**
   - `test_preview_round1_generates_pairings()`
   - `test_save_custom_pairings()`
   - `test_save_invalid_pairings_returns_400()`
   - `test_preview_round1_non_setup_tournament_returns_404()`

4. **Edge Case Tests:**
   - `test_edit_players_clears_pairings()`
   - `test_change_num_courts_clears_pairings()`
   - `test_start_round1_uses_saved_pairings()`
   - `test_start_round1_fallback_to_algorithm_if_invalid()`
   - `test_concurrent_edit_conflict_detection()`

### Manual Testing Checklist

- [ ] Create tournament, preview Round 1, verify algorithm pairings
- [ ] Swap players between courts, verify visual feedback
- [ ] Swap players within court (different teams), verify teams update
- [ ] Save custom pairings, verify success message
- [ ] Start Round 1, verify custom pairings used
- [ ] Edit player list after saving pairings, verify warning and clearing
- [ ] Change num_courts after saving pairings, verify clearing
- [ ] Delete tournament with saved pairings, verify cascade delete
- [ ] Reset button, verify regeneration from algorithm

## Migration Plan

### Database Migration

**File:** `migrations/add_round1_preview_pairings.sql`

```sql
-- Create round1_preview_pairings table
CREATE TABLE IF NOT EXISTS round1_preview_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    court_number INTEGER NOT NULL,
    team1_player1_id INTEGER NOT NULL,
    team1_player2_id INTEGER NOT NULL,
    team2_player1_id INTEGER NOT NULL,
    team2_player2_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (team1_player1_id) REFERENCES player_registry(id),
    FOREIGN KEY (team1_player2_id) REFERENCES player_registry(id),
    FOREIGN KEY (team2_player1_id) REFERENCES player_registry(id),
    FOREIGN KEY (team2_player2_id) REFERENCES player_registry(id),
    UNIQUE(tournament_id, court_number)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_round1_preview_tournament
ON round1_preview_pairings(tournament_id);
```

**Migration Script:** `migration.py`

```python
def migrate_add_round1_preview_pairings():
    """Add round1_preview_pairings table"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='round1_preview_pairings'
    """)

    if cursor.fetchone():
        print("✅ round1_preview_pairings table already exists")
        return

    # Create table
    with open('migrations/add_round1_preview_pairings.sql', 'r') as f:
        migration_sql = f.read()

    cursor.executescript(migration_sql)
    conn.commit()
    conn.close()

    print("✅ Created round1_preview_pairings table")
```

### Rollout Phases

**Phase 1: Backend Foundation (Week 1)**
- Create database table and migration
- Implement validation helper functions
- Add new Flask routes (preview, save)
- Write unit tests
- Integrate with start_round()

**Phase 2: Frontend UI (Week 2)**
- Add Round 1 preview section to edit form template
- Implement JavaScript click-then-click interaction
- Add swap animation and visual feedback
- Implement API integration (fetch, save, reset)
- Test in isolation

**Phase 3: Edge Cases & Polish (Week 3)**
- Implement player list change detection and clearing
- Add concurrent edit conflict detection
- Improve error messages and user feedback
- Write integration tests
- Manual testing and bug fixes

**Phase 4: Production Deployment (Week 4)**
- Run migration on production database
- Deploy backend and frontend changes
- Monitor for errors
- Gather user feedback
- Document feature in user guide

## Future Enhancements

### Potential Improvements (Not in Scope)

1. **Drag-and-Drop Interface:**
   - Upgrade from click-then-click to full drag-and-drop
   - Use HTML5 Drag API or library like SortableJS
   - Better mobile experience

2. **Pairing Templates:**
   - Save custom pairing patterns as templates
   - Reuse templates across tournaments
   - Community-shared templates

3. **Constraint-Based Pairing:**
   - Mark players as "must be separated" (friends, family)
   - Mark players as "must be together" (carpooling)
   - Algorithm respects constraints

4. **Round 2+ Manual Adjustment:**
   - Extend feature to all rounds, not just Round 1
   - Override movement algorithm when needed
   - Use case: Accommodate player absences

5. **Undo/Redo Stack:**
   - Track pairing change history
   - Undo last swap
   - Redo undone swap

## Open Questions

### Resolved

- ✅ Should admins control team pairings or just court assignments? **Answer:** Both
- ✅ When should pairings be generated? **Answer:** Button click (explicit action)
- ✅ What happens if player list changes? **Answer:** Clear pairings with warning
- ✅ Where in admin UI? **Answer:** Inside expandable edit form

### Remaining

None - design complete and approved.

## Success Criteria

Feature is successful if:
1. ✅ Admins can preview Round 1 pairings before tournament starts
2. ✅ Admins can swap players between courts with visual feedback
3. ✅ Admins can control team pairings within courts
4. ✅ Custom pairings are used when starting Round 1
5. ✅ Player list changes invalidate saved pairings safely
6. ✅ No performance degradation on tournament creation or Round 1 start
7. ✅ All existing tournament functionality works unchanged
8. ✅ Zero data loss or corruption from edge cases

## Conclusion

This design provides tournament administrators with complete control over Round 1 court assignments while preserving the benefits of the seeding algorithm as a starting point. The click-then-click interaction is simple and intuitive, the database schema is clean and normalized, and edge cases are handled safely with clear user feedback.

Implementation follows the existing Admin Dashboard patterns and integrates seamlessly with the current tournament workflow. The feature is scoped appropriately for an MVP while leaving room for future enhancements based on user feedback.
