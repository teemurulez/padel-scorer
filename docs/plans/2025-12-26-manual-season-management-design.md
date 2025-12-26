# Manual Season Management - Design Document

**Date:** December 26, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

Replace calendar-year-based seasons with user-controlled manual season management. Users can create custom-named seasons, end the current season, and reactivate archived seasons through a dedicated admin interface.

## Problem Statement

Currently, seasons are defined by calendar year using the `created_at` timestamp. This approach has limitations:

1. **Inflexible timing** - Must wait until January 1 to start a new season
2. **Cannot run multiple seasons per year** - Limited to calendar boundaries
3. **No control over season boundaries** - Automatic, not user-defined
4. **Season names are just years** - Not descriptive (e.g., "Winter League", "Spring Cup")

Users need the ability to manually control when seasons start and end, with custom naming.

## Proposed Solution

### Core Design Decisions

**Season Identification:** Custom names (e.g., "Winter 2024-2025", "Spring League", "Summer Cup")
- Maximum flexibility
- User enters any name when creating a season

**Active Season Model:** Hybrid approach
- One "current" season by default (where new tournaments go)
- Can reactivate archived seasons if needed
- Can end current season without immediately creating a new one
- Allows temporary "no active season" state

**Player Management:** Players carry over automatically
- Global `player_registry` table unchanged
- Seeding calculations can span season boundaries
- Continuity maintained across seasons

**Archived Season Access:** Fully editable
- Archived seasons remain editable
- Can fix mistakes or add late scores
- No read-only restrictions

**UI Access:** Dedicated admin page
- `/seasons` management page
- Accessed via footer link on home page
- Keeps regular user views simple

## Database Schema Changes

### New `seasons` Table

```sql
CREATE TABLE seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_current BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL
);
```

**Constraints:**
- `UNIQUE` on name prevents duplicate season names
- Only ONE season can have `is_current = 1` (enforced in application logic)
- `ended_at` is NULL for active/current season, populated when season ends

### Modify `tournaments` Table

```sql
ALTER TABLE tournaments ADD COLUMN season_id INTEGER REFERENCES seasons(id);
```

### Indexes for Performance

```sql
CREATE INDEX idx_tournaments_season_id ON tournaments(season_id);
CREATE INDEX idx_seasons_is_current ON seasons(is_current);
```

### Application-Level Constraint

When setting a season as current (`is_current = 1`), first set all other seasons to `is_current = 0`. This ensures exactly one current season at all times (or zero if no active season).

### Default Season for New Installations

When initializing a fresh database, create a default season:

```sql
INSERT INTO seasons (name, is_current) VALUES ('Season 1', 1);
```

## Data Migration Strategy

For existing databases with tournaments, migrate data automatically on first run:

### Step 1: Create Seasons from Existing Years

```python
# Get all distinct years from existing tournaments
years = db.execute(
    "SELECT DISTINCT strftime('%Y', created_at) as year FROM tournaments ORDER BY year"
).fetchall()

# Create a season for each year
for year_row in years:
    year = year_row['year']
    db.execute(
        "INSERT INTO seasons (name, is_current, created_at) VALUES (?, ?, ?)",
        (f"Season {year}", 0, f"{year}-01-01")
    )
```

### Step 2: Assign Tournaments to Year-Based Seasons

```python
# For each tournament, assign it to the season matching its year
db.execute("""
    UPDATE tournaments
    SET season_id = (
        SELECT s.id FROM seasons s
        WHERE s.name = 'Season ' || strftime('%Y', tournaments.created_at)
    )
""")
```

### Step 3: Mark Most Recent Season as Current

```python
db.execute("UPDATE seasons SET is_current = 1 WHERE id = (SELECT MAX(id) FROM seasons)")
```

### Migration Trigger

Run migration automatically during app startup if:
- `season_id` column exists in tournaments table
- Any tournaments have `NULL` season_id

## Season Management UI

### Route: `GET /seasons`

Dedicated admin page for managing seasons.

### Page Layout

#### Current Season Card (when one exists)

```
┌─────────────────────────────────────┐
│ 🏆 Current Season: [Season Name]    │
│ Created: Dec 26, 2025               │
│ Tournaments: 5                      │
│                                     │
│ [End Current Season] (Warning btn)  │
└─────────────────────────────────────┘
```

#### No Current Season State

```
┌─────────────────────────────────────┐
│ ⚠️ No Active Season                 │
│ Create a new season or reactivate   │
│ an archived season below.           │
│                                     │
│ [Create New Season]                 │
└─────────────────────────────────────┘
```

#### Archived Seasons Table

Table showing all archived seasons:

| Season Name      | Created    | Ended      | Tournaments | Actions          |
|------------------|------------|------------|-------------|------------------|
| Season 2024      | 2024-01-15 | 2024-12-20 | 12          | [Set as Current] |
| Winter 2023-2024 | 2023-11-01 | 2024-01-10 | 8           | [Set as Current] |

### User Workflows

#### 1. End Current Season (no new season)

1. Click "End Current Season" button
2. Confirmation dialog: "End '[Name]'? You can reactivate it or create a new season later."
3. On confirm:
   - Sets `is_current = 0`
   - Sets `ended_at = NOW()`
   - Redirects to `/seasons` with success message

#### 2. Create New Season

1. Click "Create New Season" button (or link in no-season state)
2. Modal/form appears with input field: "New Season Name" (required)
3. On submit:
   - Validates name (required, unique, max 100 chars)
   - Archives any current season (`is_current = 0`)
   - Creates new season with `is_current = 1`
   - Redirects to `/seasons` with success message

#### 3. Reactivate Archived Season

1. Click "Set as Current" button on archived season row
2. Confirmation dialog: "Make '[Name]' the current season?"
3. On confirm:
   - Archives any current season (`is_current = 0`)
   - Sets selected season `is_current = 1`, `ended_at = NULL`
   - Redirects to `/seasons` with success message

### Access

- Link in home page footer: "Manage Seasons" (small, subtle, admin-style link)
- No authentication required initially (can add later if needed)

## Impact on Existing Features

### Home Page (`/`)

**Changes:**
- Add footer link: "Manage Seasons"
- Season info section remains (shows current season's tournaments instead of current year)

**No changes to:**
- Active tournament redirect
- Setup button
- Overall layout

### Tournament Creation (`/setup`)

**Changes:**
- Auto-assign new tournaments to current season
- Query current season: `SELECT id FROM seasons WHERE is_current = 1`
- If no current season: redirect to `/seasons` with warning

**No UI changes:**
- Completely transparent to users
- Tournament creation form unchanged

### Season Leaderboard (`/leaderboard/season`)

**Changes:**
- Filter by current season instead of current year
- Title changes from "Season 2025" to "Season [name]"
- Show tournaments from current season only

**Query changes:**
```python
# OLD: Filter by calendar year
WHERE strftime('%Y', t.created_at) = ?

# NEW: Filter by current season
current_season = db.execute(
    "SELECT id FROM seasons WHERE is_current = 1"
).fetchone()

WHERE t.season_id = ?
```

**Edge case handling:**
- If no current season: show message "No current season. Visit Season Management to create or activate one."

### Season History (`/leaderboard/history`)

**Changes:**
- Group by archived seasons instead of calendar years
- Each section uses season name instead of year
- Show seasons in reverse order (newest ended_at first)

**Query changes:**
```python
# OLD: Get distinct years
years = db.execute(
    "SELECT DISTINCT strftime('%Y', created_at) as year FROM tournaments WHERE year < current_year"
).fetchall()

# NEW: Get archived seasons
seasons = db.execute(
    "SELECT * FROM seasons WHERE is_current = 0 ORDER BY ended_at DESC"
).fetchall()
```

**"View Previous Seasons" button visibility:**
```python
# OLD: has_previous_seasons = (year_count < current_year) > 0
# NEW: has_previous_seasons = (COUNT(*) FROM seasons WHERE is_current = 0) > 0
```

### Individual Tournament Pages

**No changes:**
- Tournament views, match entry, score entry unchanged
- Season information not displayed on tournament pages

## Edge Cases & Error Handling

### No Current Season

**Tournament Creation:**
- Show warning: "No active season. Please create or activate a season first."
- Redirect to `/seasons` page
- Disable tournament creation until season is active

**Season Leaderboard:**
- Show message: "No current season. Visit Season Management to create or activate one."
- Provide link to `/seasons`

**Home Page:**
- Show warning banner: "⚠️ No active season. Manage Seasons to create or activate one."
- Link to `/seasons` page

### Reactivating a Season

**Behavior:**
- When reactivated, `ended_at` is set back to NULL
- All tournaments in that season become part of "current season" again
- Seeding calculations automatically include those tournaments
- Any previously current season is archived

**Use cases:**
- Mistake: User ended season too early
- Continuation: Need to add more tournaments to a past season

### Season Name Validation

**Rules:**
- Required field (cannot be empty)
- Must be unique (enforced by database UNIQUE constraint)
- Maximum length: 100 characters
- No special validation on characters (allow flexibility)

**Error handling:**
- Empty name: "Season name is required"
- Duplicate name: "Season name already exists. Please choose a different name."
- Too long: "Season name must be 100 characters or less"

### Deleting Seasons

**Initial approach:** Not supported (YAGNI)
- Seasons cannot be deleted
- Can be ended/archived but remain in database

**Future consideration:**
- If deletion needed, require season to have zero tournaments
- Cascade delete would delete all tournaments - probably too dangerous
- Or: soft delete (mark as deleted, hide from UI)

### Permission/Access Control

**Current approach:** No authentication
- Anyone can access `/seasons` page
- Anyone can create/end/activate seasons

**Future consideration:**
- Simple password protection for admin pages
- Or: basic auth check before allowing season management
- Or: role-based access if user accounts are added

## Key Implementation Functions

### Helper: Get Current Season

```python
def get_current_season(db):
    """Get the current active season, or None if no active season"""
    return db.execute(
        "SELECT * FROM seasons WHERE is_current = 1"
    ).fetchone()
```

### Helper: Set Season as Current

```python
def set_current_season(db, season_id):
    """Set a season as current, archiving any other current season"""
    # Archive all current seasons
    db.execute("UPDATE seasons SET is_current = 0 WHERE is_current = 1")

    # Set specified season as current and clear ended_at
    db.execute(
        "UPDATE seasons SET is_current = 1, ended_at = NULL WHERE id = ?",
        (season_id,)
    )
    db.commit()
```

### Route: Season Management Page

```python
@app.route('/seasons')
def seasons_management():
    """Display season management admin page"""
    db = get_db_connection()

    current_season = get_current_season(db)

    # Get archived seasons with tournament counts
    archived_seasons = db.execute("""
        SELECT
            s.*,
            COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON s.id = t.season_id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.ended_at DESC NULLS LAST, s.created_at DESC
    """).fetchall()

    # Get tournament count for current season
    if current_season:
        current_tournament_count = db.execute(
            "SELECT COUNT(*) as count FROM tournaments WHERE season_id = ?",
            (current_season['id'],)
        ).fetchone()['count']
    else:
        current_tournament_count = 0

    return render_template('seasons_management.html',
                          current_season=current_season,
                          current_tournament_count=current_tournament_count,
                          archived_seasons=archived_seasons)
```

### Route: End Current Season

```python
@app.route('/seasons/end-current', methods=['POST'])
def end_current_season():
    """End the current season without creating a new one"""
    db = get_db_connection()

    current_season = get_current_season(db)
    if not current_season:
        flash('No current season to end')
        return redirect(url_for('seasons_management'))

    from datetime import datetime
    db.execute(
        "UPDATE seasons SET is_current = 0, ended_at = ? WHERE id = ?",
        (datetime.now(), current_season['id'])
    )
    db.commit()

    flash(f"Season '{current_season['name']}' has been ended")
    return redirect(url_for('seasons_management'))
```

### Route: Create New Season

```python
@app.route('/seasons/create', methods=['POST'])
def create_season():
    """Create a new season and make it current"""
    db = get_db_connection()
    season_name = request.form.get('season_name', '').strip()

    # Validation
    if not season_name:
        flash('Season name is required')
        return redirect(url_for('seasons_management'))

    if len(season_name) > 100:
        flash('Season name must be 100 characters or less')
        return redirect(url_for('seasons_management'))

    # Check for duplicate
    existing = db.execute(
        "SELECT id FROM seasons WHERE name = ?", (season_name,)
    ).fetchone()

    if existing:
        flash('Season name already exists. Please choose a different name.')
        return redirect(url_for('seasons_management'))

    # Archive current season if exists
    db.execute("UPDATE seasons SET is_current = 0 WHERE is_current = 1")

    # Create new season
    db.execute(
        "INSERT INTO seasons (name, is_current) VALUES (?, 1)",
        (season_name,)
    )
    db.commit()

    flash(f"Season '{season_name}' created successfully!")
    return redirect(url_for('seasons_management'))
```

### Route: Reactivate Season

```python
@app.route('/seasons/<int:season_id>/activate', methods=['POST'])
def activate_season(season_id):
    """Reactivate an archived season as the current season"""
    db = get_db_connection()

    season = db.execute(
        "SELECT * FROM seasons WHERE id = ?", (season_id,)
    ).fetchone()

    if not season:
        flash('Season not found')
        return redirect(url_for('seasons_management'))

    set_current_season(db, season_id)

    flash(f"Season '{season['name']}' is now active")
    return redirect(url_for('seasons_management'))
```

## Implementation Checklist

### Database Changes
- [ ] Create `seasons` table in schema
- [ ] Add `season_id` column to tournaments table
- [ ] Create indexes for performance
- [ ] Write migration script for existing data
- [ ] Test migration with current database

### New Files
- [ ] `templates/seasons_management.html` - Season management page
- [ ] Update `schema.sql` with seasons table

### Modified Files
- [ ] `app.py`:
  - [ ] Add `get_current_season()` helper
  - [ ] Add `set_current_season()` helper
  - [ ] Add `/seasons` route
  - [ ] Add `/seasons/end-current` route
  - [ ] Add `/seasons/create` route
  - [ ] Add `/seasons/<id>/activate` route
  - [ ] Update `/setup` to check for current season
  - [ ] Update `/leaderboard/season` to filter by season
  - [ ] Update `/leaderboard/history` to use seasons
  - [ ] Update `index()` route for season info

- [ ] `templates/index.html`:
  - [ ] Add "Manage Seasons" footer link
  - [ ] Update season info section to use current season

- [ ] `templates/season_leaderboard.html`:
  - [ ] Update title to use season name
  - [ ] Update queries to use current season

- [ ] `templates/season_history.html`:
  - [ ] Update to iterate over seasons instead of years
  - [ ] Use season names instead of year numbers

- [ ] `static/css/style.css`:
  - [ ] Add styles for season management page
  - [ ] Add styles for warning states (no active season)

### Testing
- [ ] Test migration with existing data
- [ ] Test creating first season (new installation)
- [ ] Test ending current season
- [ ] Test creating new season
- [ ] Test reactivating archived season
- [ ] Test no current season state (tournament creation blocked)
- [ ] Test season name validation (empty, duplicate, too long)
- [ ] Test season leaderboard with current season
- [ ] Test season history with archived seasons
- [ ] Test tournament assignment to current season

## Future Enhancements (Out of Scope)

- **Season deletion:** Allow deleting empty seasons
- **Season notes:** Add description/notes field to seasons
- **Season templates:** Copy settings from previous season
- **Season statistics:** Aggregate stats across seasons
- **Authentication:** Protect admin pages with password
- **Season-specific players:** Opt players in/out of specific seasons
- **Season duration tracking:** Show how long each season lasted
- **Export/Import:** Export season data for backup/sharing

## Summary

This design replaces rigid calendar-year seasons with flexible user-controlled season management. Users can create custom-named seasons, end them at any time, and reactivate archived seasons as needed. The implementation maintains backward compatibility through automatic data migration and keeps the regular user interface simple while providing powerful admin controls through a dedicated management page.

**Key benefits:**
- Flexibility: Run multiple seasons per year or span multiple years
- Control: Manually decide when seasons start and end
- Clarity: Descriptive season names instead of just years
- Safety: Can reactivate seasons if ended by mistake
- Simplicity: Transparent to regular users, powerful for admins
