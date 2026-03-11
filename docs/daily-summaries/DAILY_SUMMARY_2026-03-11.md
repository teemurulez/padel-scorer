# Daily Summary — 2026-03-11

## Changes Made

### 1. Auto-calculate courts from player count
**Files:** `templates/admin_dashboard.html`, `static/css/admin.css`

Replaced the manual courts dropdown in the tournament creation modal with automatic calculation from the player list.

- Courts = floor(player_count / 4), updated live as players are typed
- Green hint when count is divisible by 4, amber when remainder exists
- Hidden input for `num_courts` (no dropdown)
- Court label preview still updates based on auto-calculated count

### 2. Admin: edit matches played per player
**Files:** `app.py`, `templates/admin_dashboard.html`

Extended the existing player points editing in the admin Players tab to also allow editing matches played.

- Added `matches_adjustment` as a selected column in the admin dashboard query
- Extended `admin_edit_player_points` route to parse `new_total_matches`, calculate `matches_adjustment`, and UPSERT it
- Edit row now shows both points and matches inputs side by side
- Matches column shows adjustment indicator (green/red) when `matches_adjustment != 0`
- Live JS update of matches adjustment display on input change
- Flash message includes both points and matches when changed

### 3. Algorithm cleanup and test updates
**Files:** `court_movement.py`, `seeded_pairing.py`, `tests/test_court_movement.py`, `tests/test_seeded_pairing.py`

- Cleaned up court movement algorithm code
- Added zero-player validation to seeded pairing
- Updated and consolidated tests for court movement and seeded pairing

### 4. Season leaderboard fix
**Files:** `templates/season_leaderboard.html`

- Minor template fix in season leaderboard display

### 5. Tournament edit JS improvements
**Files:** `static/js/tournament_edit.js`

- Improvements to tournament edit page JavaScript

### 6. TODO updates
**Files:** `TODO.md`

- Marked completed: auto-calculate courts, edit matches played, algorithm cleanup, 6-court testing, various bug fixes
- Added new feature requests: player edit row vertical alignment, editable player name
- Updated project status and test count

## Verification

- All 218 tests pass (3 skipped)
