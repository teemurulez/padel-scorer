# Admin Dashboard - Design Document

**Date:** December 27, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

A unified Admin Dashboard that provides password-protected access to all administrative functions through a tabbed interface. The dashboard consolidates season management, point editing, player registry management, and data cleanup into a single `/admin` hub.

## Problem Statement

Current administrative needs scattered across multiple locations:
1. **No centralized admin area** - Features spread across different pages
2. **No point correction mechanism** - Cannot fix errors in match results or player points
3. **No access control** - Anyone with URL access can perform destructive actions
4. **Manual season management not implemented** - Still using calendar years (designed Dec 26)
5. **Limited data cleanup options** - Only "clear all" available, no granular deletion

Users need a secure, centralized admin interface to manage seasons, correct errors, manage players, and clean up data with appropriate safeguards.

## Proposed Solution

### Core Design Decisions

**Unified Dashboard Approach:**
- Single `/admin` hub for all administrative tasks
- Tabbed interface: Seasons | Points | Players | Data
- Consolidates all admin features in one discoverable location
- Room to grow with additional admin features

**Access Control:**
- Simple password protection (single admin password)
- First-run setup: prompt to create admin password on initial launch
- Session-based authentication with 30-minute inactivity timeout
- Password stored hashed in database

**Point Editing Mechanics:**
- **Primary method:** Edit match results (winner, team composition, court)
- **Secondary method:** Manual point override for edge cases
- Match edits trigger automatic point recalculation
- Manual overrides stored separately, added to calculated points

**UI Organization:**
- Tabbed interface on single page (JavaScript tab switching)
- Black and bright yellow brand colors
- Logo placeholder in header (can add later)
- Distinct visual styling to indicate admin mode

**Deletion Behavior:**
- Cascade delete with detailed warnings
- Show impact before deletion (X tournaments, Y matches, Z scores)
- Confirmation dialogs scaled to risk level
- Nuclear "Clear All" requires typing "DELETE"

## Database Schema

### New Tables

**admin_users table:**
```sql
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Constraints:**
- Single row only (enforced in application logic)
- Password hashed using `werkzeug.security.generate_password_hash` (pbkdf2:sha256)
- `updated_at` changes when password is changed via password change feature

**admin_sessions table (optional, for audit tracking):**
```sql
CREATE TABLE admin_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    logged_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logged_out_at TIMESTAMP NULL
);
```

**seasons table (from Dec 26 design):**
```sql
CREATE TABLE seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_current BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL
);

-- Modify tournaments table
ALTER TABLE tournaments ADD COLUMN season_id INTEGER REFERENCES seasons(id);

-- Indexes for performance
CREATE INDEX idx_tournaments_season_id ON tournaments(season_id);
CREATE INDEX idx_seasons_is_current ON seasons(is_current);
```

**No schema changes needed for:**
- Point editing (edits existing `matches` and `scores` tables)
- Player management (uses existing `player_registry` table)
- Data cleanup (deletes from existing tables)

## Feature Details

### Tab 1: Season Management

Integrates the Manual Season Management design (Dec 26) into admin dashboard.

**Display:**
- Current season highlighted at top (if exists)
- List of all seasons (current + archived), newest first
- Each season shows: Name, Status (Current/Archived), Date range, Tournament count

**Actions:**

**1. Create New Season**
- Button: "Create New Season"
- Modal/form: Enter season name (max 100 chars, unique, required)
- On submit:
  - Archives current season (sets `is_current = 0`, `ended_at = NOW()`)
  - Creates new season with `is_current = 1`
- Validation: Name required, must be unique, trim whitespace

**2. End Current Season**
- Button: "End Current Season" (only if current season exists)
- Confirmation: "End [Season Name]? You can reactivate it later."
- On confirm: Sets `is_current = 0`, `ended_at = NOW()`
- Result: No active season (allowed state)

**3. Reactivate Archived Season**
- Button next to each archived season: "Reactivate"
- Confirmation: "Make [Season Name] the current season?"
- On confirm:
  - Deactivates current season (if exists)
  - Sets selected season as current (`is_current = 1`)
  - Clears `ended_at`

**4. Delete Season**
- Button: "Delete" (trash icon, red styling)
- Warning: "Delete [Season Name]? This will also delete X tournaments, Y matches, Z scores. This cannot be undone."
- Show detailed impact: Number of tournaments, matches, scores to be deleted
- On confirm: CASCADE DELETE season + all tournaments + rounds + matches + scores

### Tab 2: Point Editing

Provides two methods for correcting points: editing match results (primary) and manual point overrides (edge cases).

**Method 1: Edit Match Results**

**Workflow:**
1. **Select Tournament** - Dropdown of all tournaments, grouped by season
2. **Select Round** - Shows all rounds in selected tournament
3. **View Matches** - Table displays all matches with:
   - Court number
   - Team A players (2 names)
   - Team B players (2 names)
   - Current winner (highlighted in yellow)
   - "Edit" button per match

4. **Edit Match Modal** - Opens when clicking "Edit":
   - **Winner Selection:** Radio buttons for Team A or Team B
   - **Team Composition:** 4 dropdowns:
     - Team A Player 1 (from tournament player list)
     - Team A Player 2 (from tournament player list)
     - Team B Player 1 (from tournament player list)
     - Team B Player 2 (from tournament player list)
   - **Court Number:** Editable number field (positive integer)
   - **Save** button - updates match, recalculates all player stats
   - **Cancel** button - closes modal without changes

**Validation:**
- All 4 players must be selected
- Players must be unique (no player in both teams)
- Court number must be positive integer
- Winner must be Team A or Team B

**On Save:**
- Update `matches` table with new data
- Recalculate all player statistics for the tournament
- Flash success message: "Match updated. Points recalculated."

**Method 2: Manual Point Override**

Below match editing section, show:
- **Player Points Table** for selected tournament
- Columns:
  - Player Name
  - Calculated Points (from match wins)
  - Manual Adjustment (editable: "+5", "-3", or "0")
  - Final Points (Calculated + Adjustment)
- Save button updates override values
- Adjustments stored in new column or separate table
- Range: -999 to +999

**Use Case:** Special awards, bonus points, manual corrections that don't correspond to match results

### Tab 3: Player Registry Management

CRUD operations for managing players in the global registry.

**Display:**
- Table of all players with columns:
  - ID
  - First Name
  - Last Name
  - Total Tournaments Played (count across all seasons)
  - Total Matches Played
  - Total Wins
  - Actions (Edit, Delete buttons)
- Search/filter box at top: "Filter by name..." (filters as you type)
- "Add New Player" button at top (yellow background, black text)

**Actions:**

**1. Add New Player**
- Button: "Add New Player"
- Modal with form fields:
  - First Name (required, trim whitespace)
  - Last Name (required, trim whitespace)
- Validation: Check for duplicate (same first + last name)
- If duplicate exists: Show warning "Player already exists"
- On submit: INSERT into `player_registry`
- Flash success: "Player added successfully"

**2. Edit Player**
- Click "Edit" button next to player row
- Modal with pre-filled form:
  - First Name (editable)
  - Last Name (editable)
- Validation: Same duplicate check as create
- On save: UPDATE `player_registry` record
- All historical match data automatically reflects new name
- Flash success: "Player updated successfully"

**3. Delete Player**
- Click "Delete" button (red background, trash icon)
- Warning dialog: "Delete [First Last]? This will remove them from X tournaments and delete Y match records. This cannot be undone."
- Show affected data:
  - List of tournaments where player participated
  - Total matches to be deleted
- On confirm: CASCADE DELETE
  - Removes player from `player_registry`
  - Deletes all their match participations and scores
- Flash success: "Player deleted"

### Tab 4: Data Cleanup

Granular data deletion options plus nuclear "Clear All" option.

**Display:**
- Warning banner at top: "⚠️ Data cleanup actions are permanent and cannot be undone. Use with caution." (red background)
- Four cleanup sections, each with description and action button

**Cleanup Options:**

**1. Delete Specific Tournament**
- Dropdown: Select tournament (grouped by season: "Season Name → Tournament Name")
- Shows tournament info after selection:
  - Rounds: X
  - Matches: Y
  - Players: Z
- Button: "Delete Tournament" (red)
- Confirmation: "Delete [Tournament Name]? This will remove X rounds, Y matches, Z scores. Cannot be undone."
- On confirm: CASCADE DELETE tournament + rounds + matches + scores
- Flash success: "Tournament deleted"

**2. Delete Specific Season**
- Dropdown: Select season (shows tournament count)
- Shows season info after selection:
  - Tournaments: X
  - Total matches: Y
- Button: "Delete Season" (red)
- Confirmation: "Delete [Season Name]? This will remove the season AND all X tournaments within it (Y total matches). Cannot be undone."
- On confirm: CASCADE DELETE season + all tournaments + rounds + matches + scores
- Flash success: "Season deleted"

**3. Clear Player Statistics**
- Description: "Reset all player wins/losses to zero. Players remain in registry, tournaments remain, but all match history is deleted."
- Button: "Clear All Player Statistics" (red)
- Confirmation: "Reset all player statistics? Players will remain in the registry but all match history will be deleted. Cannot be undone."
- On confirm: DELETE all scores and matches, keep `player_registry` and `tournaments`
- Flash success: "All player statistics cleared"

**4. Clear All Data (Nuclear Option)**
- Description: "Delete everything except admin account. Complete database reset."
- Big red button: "Clear All Data"
- Confirmation: "DELETE EVERYTHING? This will remove all tournaments, matches, scores, players, and seasons. This is permanent and cannot be undone. Type 'DELETE' to confirm."
- Requires typing "DELETE" (case-sensitive) in text field
- Button disabled until "DELETE" is typed correctly
- On confirm: Deletes all data from all tables (except `admin_users`)
- Flash success: "All data cleared"

## Routes & API Endpoints

### Public Routes (no auth required)

- `GET /admin/login` - Login page
- `POST /admin/login` - Process login (check password, create session)
- `GET /admin/setup` - First-run password setup page (only if no admin exists)
- `POST /admin/setup` - Create initial admin password

### Protected Routes (require auth)

**Main Dashboard:**
- `GET /admin` - Main dashboard page (tabbed interface)
- `POST /admin/logout` - Clear session, redirect to login
- `GET /admin/check-session` - AJAX endpoint to check session validity (returns JSON)

**Season Management:**
- `POST /admin/seasons/create` - Create new season (JSON: `{name}`)
- `POST /admin/seasons/<id>/end` - End current season
- `POST /admin/seasons/<id>/activate` - Reactivate archived season
- `DELETE /admin/seasons/<id>` - Delete season (cascade)

**Point Editing:**
- `GET /admin/tournaments/<id>/rounds` - Get rounds for tournament (AJAX, returns JSON)
- `GET /admin/rounds/<id>/matches` - Get matches for round (AJAX, returns JSON)
- `PUT /admin/matches/<id>` - Update match (JSON: `{winner_team, team_a_player_1, team_a_player_2, team_b_player_1, team_b_player_2, court}`)
- `PUT /admin/tournaments/<id>/point-overrides` - Update manual point adjustments (JSON: `{player_id: adjustment, ...}`)

**Player Registry:**
- `POST /admin/players/create` - Add new player (JSON: `{first_name, last_name}`)
- `PUT /admin/players/<id>` - Update player (JSON: `{first_name, last_name}`)
- `DELETE /admin/players/<id>` - Delete player (cascade)

**Data Cleanup:**
- `DELETE /admin/tournaments/<id>` - Delete tournament (cascade)
- `DELETE /admin/seasons/<id>` - Delete season (cascade)
- `POST /admin/cleanup/stats` - Clear all statistics
- `POST /admin/cleanup/all` - Clear all data (JSON: `{confirmation: "DELETE"}`)

## Authentication Implementation

### Password Hashing & Verification

**First-Run Setup:**
```python
from werkzeug.security import generate_password_hash, check_password_hash

# On /admin/setup POST
password = request.form['password']
password_hash = generate_password_hash(password, method='pbkdf2:sha256')
db.execute('INSERT INTO admin_users (password_hash) VALUES (?)', (password_hash,))
db.commit()
```

**Login Flow:**
```python
# On /admin/login POST
password = request.form['password']
admin = db.execute('SELECT password_hash FROM admin_users LIMIT 1').fetchone()

if admin and check_password_hash(admin['password_hash'], password):
    session['logged_in_as_admin'] = True
    session['login_time'] = datetime.now().isoformat()
    session['last_activity'] = datetime.now().isoformat()
    return redirect('/admin')
else:
    flash('Invalid password')
    return redirect('/admin/login')
```

### Session Timeout Middleware

**Before each request:**
```python
from datetime import datetime, timedelta

@app.before_request
def check_admin_session():
    # Only check for admin routes (except login)
    if request.path.startswith('/admin') and request.path not in ['/admin/login', '/admin/setup']:
        # Check if logged in
        if not session.get('logged_in_as_admin'):
            return redirect('/admin/login')

        # Check 30-minute timeout
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            session.clear()
            flash('Session expired. Please log in again.')
            return redirect('/admin/login')

        # Update last activity
        session['last_activity'] = datetime.now().isoformat()
```

### Password Change Feature

Add to admin dashboard (Settings section or fifth tab):
- **Current Password** field (verify before allowing change)
- **New Password** field (min 8 chars)
- **Confirm New Password** field (must match)
- Validation: Current password correct, new passwords match, meets requirements
- On submit: Update `admin_users` table with new hash, set `updated_at = NOW()`

## UI/UX Design

### Visual Design with Brand Colors

**Color Scheme:**
- **Primary:** Black (`#000000`) - headers, backgrounds, primary text
- **Accent:** Bright Yellow (`#FFD700` or `#FFEB3B`) - highlights, active states, primary buttons
- **Contrast:** White text on black backgrounds
- **Warnings:** Red (`#DC2626`) for destructive actions (delete buttons)
- **Success:** Green (`#16A34A`) for confirmations and success messages

**Admin Section Styling:**

**Header:**
- Black background with yellow accent stripe at bottom
- Logo placeholder (top-left) - can add `static/images/logo.png` later
- Title: "ADMIN DASHBOARD" (white text)
- Lock icon: 🔒 in yellow
- Logout button (top-right): Yellow text on black background

**Tabs:**
- Black background
- Yellow underline for active tab (4px thick)
- White text, increases brightness on hover
- Smooth transition animation on tab switch

**Buttons:**
- **Primary actions:** Yellow background (`#FFD700`), black text, black border
- **Danger actions:** Red background (`#DC2626`), white text (delete buttons)
- **Secondary actions:** Black outline, yellow text (cancel buttons)

**Tables:**
- Zebra striping: Alternating white/light gray rows
- Yellow hover highlight on rows
- Black text on white background for readability

**Example Header Layout:**
```
┌──────────────────────────────────────────────────────────┐
│ [LOGO]   ADMIN DASHBOARD 🔒              [Logout]        │ ← Black bg, white text
├──────────────────────────────────────────────────────────┤
│ Seasons | Points | Players | Data Cleanup                │ ← Yellow underline on active
└──────────────────────────────────────────────────────────┘
```

### Tabbed Interface Implementation

**HTML Structure:**
```html
<!-- Tab Buttons -->
<div class="admin-tabs">
  <button class="tab-btn active" data-tab="seasons">Seasons</button>
  <button class="tab-btn" data-tab="points">Points</button>
  <button class="tab-btn" data-tab="players">Players</button>
  <button class="tab-btn" data-tab="data">Data Cleanup</button>
</div>

<!-- Tab Content -->
<div id="tab-seasons" class="tab-content active">
  <!-- Season Management UI -->
</div>
<div id="tab-points" class="tab-content">
  <!-- Point Editing UI -->
</div>
<div id="tab-players" class="tab-content">
  <!-- Player Registry UI -->
</div>
<div id="tab-data" class="tab-content">
  <!-- Data Cleanup UI -->
</div>
```

**JavaScript for Tab Switching:**
```javascript
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tabName = btn.dataset.tab;

    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
      tab.classList.remove('active');
    });

    // Remove active from all buttons
    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('active');
    });

    // Show selected tab and activate button
    document.getElementById('tab-' + tabName).classList.add('active');
    btn.classList.add('active');

    // Preserve in sessionStorage
    sessionStorage.setItem('activeAdminTab', tabName);
  });
});

// Restore active tab on page load
const activeTab = sessionStorage.getItem('activeAdminTab') || 'seasons';
document.querySelector(`[data-tab="${activeTab}"]`).click();
```

### Confirmation Dialogs

**Three Levels of Confirmation:**

**1. Simple confirm() - Low Risk Actions:**
- Edit player
- End season
- Reactivate season
```javascript
if (!confirm('End current season? You can reactivate it later.')) {
  return;
}
```

**2. Detailed Warning + confirm() - Medium Risk:**
- Delete tournament
- Delete season
- Delete player
```javascript
const message = `Delete ${seasonName}? This will remove ${tournamentCount} tournaments, ${matchCount} matches. Cannot be undone.`;
if (!confirm(message)) {
  return;
}
```

**3. Type "DELETE" - High Risk (Nuclear):**
- Clear all data
```html
<div class="confirm-delete-modal">
  <p>DELETE EVERYTHING? Type 'DELETE' to confirm:</p>
  <input type="text" id="delete-confirm" />
  <button id="confirm-btn" disabled>Confirm</button>
</div>
```
```javascript
document.getElementById('delete-confirm').addEventListener('input', (e) => {
  const btn = document.getElementById('confirm-btn');
  btn.disabled = e.target.value !== 'DELETE';
});
```

### Loading States & Feedback

**During AJAX Requests:**
- Show spinner/loading indicator
- Disable submit button
- Change button text: "Saving..." or "Deleting..."

**Success Feedback:**
- Flash message: Green banner at top of page
- Auto-dismiss after 5 seconds
- Examples: "Tournament deleted successfully", "Player updated"

**Error Feedback:**
- Flash message: Red banner at top of page
- Stays visible until user dismisses
- Examples: "Invalid password", "Player name already exists"

## Error Handling & Validation

### Input Validation

**Season Management:**
- **Create Season:**
  - Name required (1-100 chars)
  - Must be unique (case-insensitive check)
  - Trim leading/trailing whitespace
- **Delete Season:**
  - Must exist
  - Confirmation required
- **Activate Season:**
  - Must exist
  - Must not already be current

**Point Editing:**
- **Edit Match:**
  - All 4 players must be selected
  - Players must be unique (no player on both teams)
  - Court number must be positive integer (1-999)
  - Winner team must be 'A' or 'B'
- **Point Override:**
  - Adjustment must be integer (-999 to +999)
  - Tournament must exist

**Player Management:**
- **Create Player:**
  - First and last name required
  - Trim whitespace
  - Check duplicate (exact match on first + last)
- **Edit Player:**
  - Same as create
  - Player must exist
- **Delete Player:**
  - Player must exist
  - Confirmation required

**Data Cleanup:**
- **Delete Tournament/Season:**
  - Must exist
  - Confirmation required
- **Clear All:**
  - Must type "DELETE" exactly (case-sensitive)

### Error Response Patterns

**Client-Side Validation (JavaScript):**
- Check required fields before form submission
- Show inline error messages (red text below field)
- Disable submit button until valid
- Real-time validation on input (e.g., duplicate check on blur)

**Server-Side Validation (Flask):**
- Always re-validate on server (never trust client)
- Return JSON for AJAX requests:
  ```json
  {
    "success": false,
    "error": "Season name already exists"
  }
  ```
- Flash messages for full page requests
- HTTP status codes:
  - 200: Success
  - 400: Bad request (validation error)
  - 404: Not found
  - 500: Server error

**Example Flask Route with Validation:**
```python
@app.route('/admin/seasons/create', methods=['POST'])
def create_season():
    if not session.get('logged_in_as_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    name = request.json.get('name', '').strip()

    # Validate
    if not name:
        return jsonify({'success': False, 'error': 'Season name required'}), 400
    if len(name) > 100:
        return jsonify({'success': False, 'error': 'Name too long (max 100 chars)'}), 400

    # Check duplicate
    existing = db.execute('SELECT id FROM seasons WHERE name = ?', (name,)).fetchone()
    if existing:
        return jsonify({'success': False, 'error': 'Season name already exists'}), 400

    # Archive current season and create new
    try:
        db.execute('UPDATE seasons SET is_current = 0, ended_at = ? WHERE is_current = 1',
                   (datetime.now(),))
        db.execute('INSERT INTO seasons (name, is_current) VALUES (?, 1)', (name,))
        db.commit()
        return jsonify({'success': True, 'message': 'Season created'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500
```

### Database Error Handling

**Foreign Key Violations:**
- Shouldn't happen with cascade deletes
- If it does: Catch and show friendly error
- Example: "Cannot delete (database integrity error)"

**Unique Constraint Violations:**
- Season name duplicate: "Season name already exists"
- Player duplicate: "Player already exists in registry"

**Transaction Failures:**
- Wrap multi-step operations in transactions
- Roll back on error
- Show: "Operation failed. No changes were made."

**Example Transaction Pattern:**
```python
try:
    db.execute('BEGIN TRANSACTION')
    # Multiple operations
    db.execute('UPDATE seasons SET is_current = 0')
    db.execute('INSERT INTO seasons ...')
    db.execute('COMMIT')
    return success_response()
except Exception as e:
    db.execute('ROLLBACK')
    return error_response('Operation failed. No changes made.')
```

## Implementation Phases

### Phase 1: Foundation & Authentication (Est. 1 week)
**Goal:** Get admin authentication working

**Tasks:**
1. Create `admin_users` table in schema.sql
2. Add initialization check (if no admin exists, redirect to setup)
3. Build first-run setup page (`/admin/setup`)
   - Form: password input (min 8 chars)
   - Hash and store in database
4. Build login page (`/admin/login`)
   - Form: password input
   - Check against hashed password
   - Create session on success
5. Implement session middleware
   - Check auth before all `/admin/*` routes
   - 30-minute inactivity timeout
   - Auto-logout on timeout
6. Create admin dashboard shell
   - Header with logo placeholder and logout button
   - Empty tabbed interface (4 tabs)
   - Black/yellow styling
7. Add logout functionality
   - Clear session
   - Redirect to login

**Testing:**
- Can set up admin password on first run
- Can log in with correct password
- Cannot log in with wrong password
- Session expires after 30 minutes
- Can log out manually

**Deliverable:** Working authentication, empty admin dashboard

### Phase 2: Season Management (Est. 1 week)
**Goal:** Integrate Manual Season Management design into admin

**Tasks:**
1. Create `seasons` table
2. Add `season_id` column to `tournaments`
3. Create migration script for existing data
   - Create seasons from distinct tournament years
   - Assign tournaments to year-based seasons
   - Mark most recent as current
4. Build Season Management tab UI
   - List of seasons (current + archived)
   - Create, End, Activate, Delete buttons
5. Implement routes:
   - `POST /admin/seasons/create`
   - `POST /admin/seasons/<id>/end`
   - `POST /admin/seasons/<id>/activate`
   - `DELETE /admin/seasons/<id>`
6. Add confirmation dialogs
7. Test cascade deletes
8. Update home page to use current season

**Testing:**
- Can create new season
- Can end current season
- Can reactivate archived season
- Can delete season (cascade)
- Confirmations work correctly
- Validation prevents duplicates

**Deliverable:** Full season management in admin dashboard

### Phase 3: Player Registry Management (Est. 1 week)
**Goal:** Complete player CRUD operations

**Tasks:**
1. Build Player Registry tab UI
   - Table view with all players
   - Search/filter box
   - Add/Edit/Delete buttons
2. Implement `POST /admin/players/create`
   - Reuse existing player creation logic
   - Add duplicate detection
3. Implement `PUT /admin/players/<id>`
   - Edit first/last name
   - Check for duplicates
4. Implement `DELETE /admin/players/<id>`
   - Show cascade warning
   - Delete player + all match participations
5. Add client-side search/filter
6. Add loading states and error messages

**Testing:**
- Can add new player
- Cannot add duplicate
- Can edit player name
- Can delete player (cascade works)
- Search/filter works
- Validation prevents errors

**Deliverable:** Full player management in admin dashboard

### Phase 4: Point Editing (Est. 1-2 weeks)
**Goal:** Implement core error correction feature

**Tasks:**
1. Build Point Editing tab UI
   - Tournament dropdown (grouped by season)
   - Round dropdown (AJAX load)
   - Match table (AJAX load)
2. Implement AJAX routes:
   - `GET /admin/tournaments/<id>/rounds`
   - `GET /admin/rounds/<id>/matches`
3. Build match editing modal
   - Winner selection (Team A/B)
   - Team composition (4 player dropdowns)
   - Court number input
   - Validation
4. Implement `PUT /admin/matches/<id>`
   - Update match data
   - Trigger point recalculation
5. Build manual point override UI
   - Player points table
   - Adjustment input per player
6. Implement `PUT /admin/tournaments/<id>/point-overrides`
   - Store overrides (new column or table)
   - Add to calculated points
7. Test point calculation accuracy
8. Add loading states and error handling

**Testing:**
- Can select tournament/round/match
- Can edit match winner
- Can edit team composition
- Can edit court number
- Points recalculate correctly
- Can add manual point override
- Final points = calculated + override

**Deliverable:** Full point editing functionality

### Phase 5: Data Cleanup & Polish (Est. 1 week)
**Goal:** Complete all features and polish UI

**Tasks:**
1. Build Data Cleanup tab UI
   - 4 sections (Delete Tournament, Delete Season, Clear Stats, Clear All)
   - Warning banner at top
2. Implement routes:
   - `DELETE /admin/tournaments/<id>`
   - `DELETE /admin/seasons/<id>` (may already exist from Phase 2)
   - `POST /admin/cleanup/stats`
   - `POST /admin/cleanup/all`
3. Add confirmation dialogs
   - Simple confirm for tournament/season delete
   - Type "DELETE" for Clear All
4. Apply black/yellow brand colors throughout
   - Review all buttons, tabs, headers
   - Ensure consistent styling
5. Add logo placeholder in header
   - `<img>` tag with fallback
   - Can drop in `static/images/logo.png` later
6. Add password change feature
   - New modal or section
   - Current password verification
   - New password + confirm
7. Comprehensive testing
   - Test all tabs
   - Test all confirmations
   - Test cascade deletes
   - Test session timeout
   - Test error handling
8. Write user documentation

**Testing:**
- Can delete specific tournament
- Can delete specific season
- Can clear player stats
- Can clear all data (with DELETE confirmation)
- All confirmations work
- Brand colors applied consistently
- Password change works
- All error messages friendly and clear

**Deliverable:** Fully functional, polished admin dashboard ready for production

## Edge Cases & Special Considerations

### First Run Experience
- If no admin password exists, redirect `/admin` → `/admin/setup`
- Setup page: Simple password form (min 8 chars recommended)
- After setup, redirect to `/admin/login`

### No Active Season
- Allowed state: Can have zero seasons or all seasons archived
- Tournament creation should block if no current season
- Display message: "No active season. Create or activate a season first."

### Point Recalculation
- When editing match result, recalculate:
  - Player wins/losses in tournament
  - Player match counts
  - Tournament leaderboard rankings
- Use existing `get_tournament_leaderboard()` logic
- Cache invalidation if using caching

### Manual Point Overrides
- Store in new column: `player_tournament_stats.manual_adjustment` (INT default 0)
- OR create new table: `point_overrides (player_id, tournament_id, adjustment)`
- Final points = calculated wins + manual adjustment
- Display both values in UI for transparency

### Cascade Delete Impacts
- **Delete Season:** Removes season + all tournaments in it (could be many)
- **Delete Tournament:** Affects season statistics
- **Delete Player:** Affects tournament leaderboards, seeding calculations
- Always show detailed impact before confirming

### Session Security
- Session data stored server-side (Flask session)
- SECRET_KEY must be strong and kept secret
- Consider adding CSRF protection for forms
- HTTPS recommended in production

### Password Requirements
- Minimum 8 characters (recommended, not enforced initially)
- Consider adding: uppercase, lowercase, number, special char
- Can enhance in future versions

### Concurrent Edits
- Single admin user: Low risk of conflicts
- If adding multi-user later: Consider optimistic locking

## Future Enhancements (Not in v1)

### Authentication Enhancements
- Multi-user support with roles (admin, viewer)
- Two-factor authentication (TOTP)
- Password reset via email
- Account lockout after failed attempts

### Audit Logging
- Track who changed what and when
- View audit log in admin dashboard
- Export audit log to CSV

### Advanced Point Editing
- Bulk edit multiple matches
- Import/export match results CSV
- Undo last edit

### Player Enhancements
- Merge duplicate players (combine stats)
- Player profiles with photos
- Player notes/comments

### Data Export
- Export season data to PDF
- Export leaderboards to Excel
- Scheduled backups

### UI Enhancements
- Keyboard shortcuts
- Dark mode toggle
- Mobile-optimized admin interface

## Success Metrics

### Functional Success
- ✅ Can log in and access admin dashboard
- ✅ Can manage seasons (create, end, activate, delete)
- ✅ Can correct match errors (edit winner, teams, court)
- ✅ Can manually adjust points for edge cases
- ✅ Can manage players (add, edit, delete)
- ✅ Can cleanup data granularly
- ✅ All cascade deletes work correctly
- ✅ Session timeout works (30 minutes)

### Security Success
- ✅ Cannot access `/admin` without login
- ✅ Password stored hashed (not plaintext)
- ✅ Session expires after inactivity
- ✅ Destructive actions require confirmation
- ✅ No SQL injection vulnerabilities

### UX Success
- ✅ Admin interface visually distinct from main app
- ✅ Brand colors (black/yellow) applied consistently
- ✅ Confirmation dialogs scaled to risk level
- ✅ Error messages clear and helpful
- ✅ Loading states prevent confusion
- ✅ Tab switching smooth and intuitive

## Migration from Current State

### For Existing Installations

**Step 1: Run Migration Script**
- Add `admin_users` table
- Add `seasons` table
- Add `season_id` to tournaments
- Migrate existing tournaments to year-based seasons

**Step 2: First Login**
- On first access to `/admin`, redirect to setup
- Create admin password
- Redirect to login

**Step 3: Verify Data**
- Check that all tournaments assigned to seasons
- Check that current season is correct
- Verify all players intact

### For New Installations

**First Run:**
1. Initialize database with all new tables
2. Create default "Season 1" with `is_current = 1`
3. Redirect to `/admin/setup` on first access
4. Set admin password
5. Ready to use

## Documentation Requirements

### User Documentation
- How to access admin dashboard
- How to log in / change password
- How to manage seasons
- How to correct match errors
- How to manage players
- How to cleanup data safely
- Confirmation dialog guide
- Troubleshooting common errors

### Developer Documentation
- Database schema diagram
- API endpoint reference
- Authentication flow diagram
- Cascade delete behavior
- Point recalculation logic
- Testing guide
- Deployment checklist

## Notes

- Admin dashboard is foundation for future admin features
- Single admin user sufficient for tournament use case
- Can scale to multi-user if needed later
- Black/yellow brand colors make admin mode visually distinct
- Cascade deletes keep database clean but require careful confirmations
- Point editing provides flexibility for error correction
- Granular cleanup allows precision without losing everything

---

**End of Design Document**

This design provides a comprehensive, secure, and user-friendly admin dashboard that consolidates all administrative functions into a single interface while maintaining data integrity and user safety through appropriate confirmations and validations.
