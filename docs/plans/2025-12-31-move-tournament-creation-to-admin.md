# Move Tournament Creation to Admin Dashboard

**Date:** December 31, 2025
**Goal:** Move tournament creation from public home page to authenticated admin dashboard, making home page a smart entry point for scorekeepers and players.

---

## User Workflow Analysis

### Current State
- **Home page**: Shows "Start New Tournament" button (public, no authentication)
- **Workflow**: Anyone can create tournaments from the home page
- **Problem**: Tournament creation is an admin function, not a public feature

### Target Workflow
- **Admin prepares**: Creates tournaments beforehand (at home) via Admin Dashboard
- **At venue**: Players/scorekeepers open the app and jump straight to score entry
- **Home page**: Smart entry point that auto-redirects to active tournament or shows selection

### User Roles
- **Organizer (Admin)**: Creates tournaments, manages seasons (requires authentication)
- **Scorekeepers/Players**: Enter match results, view standings (public access, no login)

---

## Design Overview

### Home Page - Smart Tournament Entry

**Behavior:**

1. **On page load**, query active tournaments: `WHERE status IN ('active', 'setup')`

2. **If exactly 1 active tournament:**
   - Auto-redirect to `/tournament/{id}/courts` (court selection page)
   - No home page displayed - instant entry to scoring

3. **If multiple active tournaments:**
   - Show tournament selection page
   - Display each tournament as clickable card: name, status, date
   - Click → redirect to that tournament's court selection

4. **If zero active tournaments:**
   - Show "No active tournament running" message
   - Display current season name and tournament count
   - Button: "View Season Leaderboard"
   - Footer: "Admin Dashboard" link (for organizers)

**Removed:**
- "Start New Tournament" button (moved to admin)
- Static tournament list display (replaced by smart redirect)

---

## Admin Dashboard - Seasons Tab

### New Structure (Top to Bottom)

**1. Current Season Card** *(existing, unchanged)*
- Header: "🏆 Current Season: {name}"
- Info: Created date, total tournaments
- Button: "End Current Season"

**2. Current Season Tournaments** *(NEW)*
- Header: "Tournaments in {season name}"
- Table columns:
  - Tournament Name
  - Date (created_at)
  - Status (Active/Completed/Setup badge)
  - Actions (View | Archive)

**Table behavior:**
- "View" button → `/tournament/{id}/courts` or `/tournament/{id}/leaderboard` (depends on status)
- "Archive" button → only shown for completed tournaments
- Empty state: "No tournaments yet. Create one below."
- Sorted by: `created_at DESC` (newest first)

**Status badges:**
- `active` = Green "Active"
- `completed` = Gray "Completed"
- `setup` = Yellow "Setup" (created but Round 1 not started)

**3. Create Tournament Form** *(NEW - moved from /setup)*
- Header: "Create New Tournament"
- Fields:
  - Tournament name (text input, max 100 chars)
  - Number of courts (dropdown: 1-10)
  - Player names (textarea, one per line, min-height: 200px)
- Validation hint: "Enter one name per line. Minimum {courts × 4} players required."
- Button: "Create Tournament"
- Only shown when current season exists (hidden if no active season)

**Form behavior:**
- Submit → validates player count
- Success → creates tournament, redirects to `/tournament/{id}/courts` (start Round 1)
- Stays in admin context (protected route)

**4. Archived Seasons Table** *(existing, unchanged)*
- Shows past seasons with activate/delete actions

---

## Routes and Authentication

### Modified Routes

**Home Page: `GET /`**

Current:
```python
@app.route('/')
def index():
    # Shows tournament list + "Start Tournament" button
```

New:
```python
@app.route('/')
def index():
    # Smart redirect logic
    active_tournaments = query("WHERE status IN ('active', 'setup')")

    if len(active_tournaments) == 1:
        return redirect(f'/tournament/{active_tournaments[0].id}/courts')
    elif len(active_tournaments) > 1:
        return render_template('tournament_selection.html', tournaments=active_tournaments)
    else:
        return render_template('no_active_tournament.html', season=current_season)
```

**Tournament Setup: `/setup` → `/admin/tournaments/create`**

Current:
- `GET /setup` - Shows tournament creation form (public)
- `POST /setup` - Creates tournament (public)

New:
- Remove `GET /setup` (form now in admin dashboard)
- Move to `POST /admin/tournaments/create` (protected)
- After creation → redirect to `/tournament/{id}/courts`

**Admin Dashboard: `GET /admin`**

Current:
```python
@app.route('/admin')
def admin_dashboard():
    # Shows season data only
```

New:
```python
@app.route('/admin')
def admin_dashboard():
    # Shows season data + current season's tournaments
    current_season = get_current_season(db)

    tournaments = []
    if current_season:
        tournaments = db.execute(
            "SELECT * FROM tournaments WHERE season_id = ? ORDER BY created_at DESC",
            (current_season['id'],)
        ).fetchall()

    return render_template('admin_dashboard.html',
                          current_season=current_season,
                          tournaments=tournaments,
                          ...)
```

### Authentication

**Protected (Require Admin Login):**
- `/admin/*` - All admin routes (already protected ✅)
- `/admin/tournaments/create` - Tournament creation (new route, auto-protected)

**Public (No Authentication):**
- `/` - Home page (smart entry point)
- `/tournament/{id}/courts` - Court selection
- `/tournament/{id}/round/{round}/score` - Score entry
- `/season/leaderboard` - Season standings
- All tournament/match viewing and scoring routes

---

## UI/UX Details

### Admin Seasons Tab Styling

**Tournament Table:**
- Use same styling as Archived Seasons table (consistent look)
- Full-width table with proper padding (1rem)
- Hover effect on rows (`background-color: var(--light-gray)`)
- Status badges:
  - Active: `background: #22c55e; color: white`
  - Completed: `background: #6b7280; color: white`
  - Setup: `background: #ff9800; color: white`

**Action Buttons:**
- "View": `btn-secondary` (yellow border, always visible)
- "Archive": `btn-warning` (orange, only for completed)
- Inline display with 0.5rem spacing

**Create Tournament Form:**
- Match "Create Season" form styling
- Larger inputs: `min-height: 48px`
- Textarea: `min-height: 200px` (room for 12+ player names)
- Vertical stack layout (not inline)
- Margin-top: `3rem` (2 line spaces from tournaments table)
- Yellow "Create Tournament" button (`btn-primary`)

### New Public Templates

**tournament_selection.html** (Multiple Active Tournaments)
- Clean card layout, similar to season cards
- Each card shows:
  - Tournament name (heading)
  - Created date
  - Status badge
  - "Enter Scores" button
- Black/yellow theme (public page, not admin theme)
- Mobile-friendly: cards stack vertically on small screens
- Page title: "Select Active Tournament"

**no_active_tournament.html** (Zero Active Tournaments)
- Centered message layout
- Message: "No active tournament running"
- Show current season name and tournament count
- Large "View Season Leaderboard" button (`btn-primary`)
- Footer: "Admin Dashboard" link (subtle, for organizers)
- Background: Light gray box with border

---

## Error Handling and Edge Cases

### Tournament Creation Validation

**No active season:**
- Show error: "Cannot create tournament without an active season. Create a season first."
- Redirect to Seasons tab (already there)

**Invalid player count:**
- Error: "Need exactly {courts × 4} players for {courts} courts. You entered {count} players."
- Highlight player textarea in red
- Don't submit form

**Duplicate tournament name:**
- Warning (not error): "A tournament with this name already exists. Continue anyway?"
- Allow creation (names don't need to be unique)

**Empty player names:**
- Strip empty lines from textarea
- Validate final count after stripping
- Trim whitespace from each name

### Session Management

**Session expires during creation:**
- Admin session timeout → redirect to `/admin/login`
- Don't preserve form data (security - no session storage)
- After login → show message: "Session expired. Please try again."
- User re-enters tournament data (acceptable for admin task)

### Home Page Edge Cases

**Multiple tournaments in different states:**
- 1 "completed" + 1 "active" → Auto-redirect to active (only count active/setup)
- 2 "setup" tournaments → Show selection (count both as active)
- Query: `WHERE status IN ('active', 'setup')`

**Tournament status transitions:**
- Tournament completes while player on home page → Player refreshes to see change
- No real-time updates needed (refresh acceptable)

**Concurrent access:**
- Admin creates tournament while player viewing home → Player refreshes to see new tournament
- No websocket/polling required

### Data Integrity

**Tournament creation failure:**
- Use database transaction
- Rollback on error (no partial tournament data)
- Show error message, keep form data

**Current season deleted:**
- Tournament creation form hidden (no active season)
- If form open when season deleted → submission fails with error
- Redirect to season management

**Player registry issues:**
- If player creation fails → rollback entire transaction
- Show error: "Failed to add players to registry"

---

## Database and Data Flow

### No Schema Changes Required ✅

All existing tables support this feature:
- `tournaments` table has `season_id`, `status`, `created_at`
- `player_registry` table stores players
- `tournament_players` links players to tournaments
- `seasons` table tracks active season

### Data Flow

**Tournament Creation (Admin):**
1. Admin submits form from Seasons tab
2. Validate: active season exists, player count correct
3. Create tournament record with `status='setup'`, `season_id=current_season.id`
4. Parse player names, create/find in `player_registry`
5. Link players to tournament via `tournament_players`
6. Redirect to `/tournament/{id}/courts` to start Round 1
7. (Round 1 creation changes status to `active`)

**Home Page Load (Public):**
1. Query: `SELECT * FROM tournaments WHERE status IN ('active', 'setup')`
2. Count results
3. Route based on count (redirect, selection, or empty message)

**No migration needed** - just route and template changes

---

## Implementation Plan

### Phase 1: Admin Side (Low Risk) ✅

**Tasks:**
1. Add tournament list query to `GET /admin` route
2. Update `admin_dashboard.html`:
   - Add tournaments table to Seasons tab (after current season card)
   - Add create tournament form (after tournaments table)
   - Use same CSS classes as archived seasons table
3. Create new route: `POST /admin/tournaments/create`
   - Copy logic from existing `POST /setup`
   - Keep validation, player registry logic
   - Redirect to `/tournament/{id}/courts` on success
4. Test: Create tournament from admin, verify redirect works

**Validation:**
- Admin can create tournament from Seasons tab ✅
- Tournament appears in tournaments table ✅
- Redirect to court selection works ✅
- Form validation works (player count, season check) ✅

### Phase 2: New Templates (Preparation) ✅

**Tasks:**
5. Create `templates/tournament_selection.html`
   - Card layout for multiple tournaments
   - "Enter Scores" button per tournament
   - Black/yellow theme (use `style.css`)
6. Create `templates/no_active_tournament.html`
   - Centered message layout
   - "View Leaderboard" button
   - Season info display
7. Test: Manually visit these templates with mock data

**Validation:**
- Templates render correctly with sample data ✅
- Styling matches public pages (not admin theme) ✅
- Mobile responsive ✅

### Phase 3: Home Page Smart Redirect (Breaking Change) ⚠️

**Tasks:**
8. Update `GET /` route:
   - Query active tournaments: `WHERE status IN ('active', 'setup')`
   - Implement 3-way logic (redirect, selection, empty)
9. Keep old `GET /setup` route temporarily (safety fallback)
10. Test thoroughly:
    - 0 active tournaments → no_active_tournament.html
    - 1 active tournament → redirect to courts
    - 2+ active tournaments → tournament_selection.html
    - Each selection option works correctly

**Validation:**
- All 3 home page states work correctly ✅
- Auto-redirect is instant (no delay) ✅
- Tournament selection links work ✅
- No active tournament message is clear ✅

### Phase 4: Cleanup 🧹

**Tasks:**
11. Remove old `GET /setup` route (tournament creation form)
12. Keep `POST /setup` temporarily as redirect to admin (backward compatibility)
13. Remove `templates/setup_tournament.html` (no longer used)
14. Search codebase for any links to `/setup` → update to `/admin`
15. Update tests that reference `/setup` route

**Validation:**
- No broken links in app ✅
- Tests pass ✅
- Old `/setup` POST redirects to admin (graceful deprecation) ✅

---

## Testing Checklist

**Admin Tournament Creation:**
- [ ] Create tournament from admin → appears in tournaments table
- [ ] Create tournament → redirects to court selection (Round 1)
- [ ] Create with invalid player count → shows error
- [ ] Create without active season → shows error message
- [ ] Tournament status badges display correctly (Setup/Active/Completed)
- [ ] "View" button navigates to correct page
- [ ] "Archive" button only shows for completed tournaments

**Home Page Smart Redirect:**
- [ ] 0 active tournaments → shows "No active tournament" message
- [ ] 0 active tournaments → "View Leaderboard" button works
- [ ] 1 active tournament → auto-redirects to court selection
- [ ] 2+ active tournaments → shows selection page
- [ ] Tournament selection cards display correctly
- [ ] "Enter Scores" button navigates to correct tournament

**Authentication:**
- [ ] Non-admin cannot access `/admin/tournaments/create`
- [ ] Session timeout during creation → redirects to login
- [ ] Public can access home page, score entry, leaderboards

**Edge Cases:**
- [ ] Multiple tournaments (1 completed, 1 active) → redirects to active only
- [ ] Create tournament while player on home → refresh shows new tournament
- [ ] Delete current season → tournament creation form hidden

**Data Integrity:**
- [ ] Tournament creation failure → no partial data
- [ ] Player registry errors → transaction rollback
- [ ] Season/tournament relationships maintained correctly

---

## Benefits

**Security:**
- Tournament creation now requires admin authentication ✅
- Prevents accidental/unauthorized tournament creation
- Separates admin functions from public scoring

**User Experience:**
- **At venue**: Players get instant access to scoring (auto-redirect)
- **For admin**: All management in one place (seasons + tournaments)
- **Clear workflow**: Admin prepares → Players execute

**Code Organization:**
- Tournament creation logic stays in admin routes
- Home page simplified to smart entry point
- Consistent with season management pattern (admin-controlled)

**Operational:**
- Admin creates tournaments beforehand (not rushed at venue)
- Players/scorekeepers don't see admin UI clutter
- Home page optimized for quick access during games

---

## Risks and Mitigation

**Risk: Breaking existing workflow**
- Mitigation: Phase 3 is clearly marked as breaking change
- Mitigation: Keep old routes temporarily for testing
- Mitigation: Thorough testing checklist before cleanup

**Risk: Scorekeepers can't find how to enter scores**
- Mitigation: Auto-redirect removes navigation (instant access)
- Mitigation: Clear "No active tournament" message if admin forgot to create one

**Risk: Admin forgets to create tournament before event**
- Mitigation: Tournament creation is quick (now in admin dashboard)
- Mitigation: Can create on mobile at venue if needed (admin login on phone)

**Risk: Multiple active tournaments confuse users**
- Mitigation: Clear selection page with tournament names/dates
- Mitigation: Most common case (1 tournament) auto-redirects

---

## Future Enhancements (Out of Scope)

**Not included in this design:**
- Tournament scheduling/calendar
- Tournament templates (save common configurations)
- Bulk tournament creation
- Tournament cloning (copy settings from previous)
- Real-time tournament status updates (websockets)
- Tournament deletion from admin (use archive instead)

**These can be added later if needed.**

---

**End of Design**
