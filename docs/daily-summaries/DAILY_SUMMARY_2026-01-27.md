# Daily Summary - 2026-01-27

## Overview

Major productivity day: mobile drag feedback, demo mode, CSP headers, SSE live updates, and bulk import feature for player points from external tournaments.

## Completed Tasks

### Mobile Drag Feedback
Fixed the issue where there was no visual feedback when dragging players on mobile:

**Implementation:**
- Floating clone follows finger during drag with shadow and slight rotation
- Original slot shows faded placeholder with dashed border
- Other player slots highlighted as drop targets
- Hover state shows darker highlight when over a target
- Team cards centered and 95% width on mobile

**Bug Fix:**
- shuffle.css was not linked in confirm_match.html template

**Files Changed:**
- `static/css/shuffle.css` - Added floating clone styles, drop target styles, mobile centering
- `static/js/shuffle.js` - Implemented floating clone creation/movement/cleanup
- `templates/confirm_match.html` - Added missing shuffle.css link

### Demo Mode for Admin
Implemented read-only admin mode for showing the app to friends:

- Same login form, separate `DEMO_PASSWORD` env var
- Orange banner: "👾 Demo-tila – muutoksia ei tallenneta 👾"
- `@block_in_demo_mode` decorator blocks all POST/DELETE routes
- Users can explore but not modify data
- Flash message shown when action is blocked

**Files Changed:**
- `config.py` - Added DEMO_PASSWORD config
- `app.py` - Login handling, decorator, applied to all write routes
- `static/css/admin.css` - Demo banner styles
- `templates/admin_dashboard.html` - Demo banner
- `templates/admin_tournament_edit.html` - Demo banner

Design doc: `docs/plans/2026-01-27-demo-mode-design.md`

### Content-Security-Policy Headers
Implemented strict CSP with nonces for XSS protection:

- Unique nonce generated per request via `@app.before_request`
- CSP header added via `@app.after_request`
- Context processor injects nonce into all templates
- Updated all script tags with `nonce="{{ csp_nonce }}"`
- Removed all inline `onclick`, `onchange`, `onsubmit` handlers
- Replaced with event delegation in nonced script blocks

**Policy:**
```
default-src 'self'; script-src 'self' 'nonce-...';
style-src 'self' 'unsafe-inline'; img-src 'self' data:;
form-action 'self'; frame-ancestors 'none'
```

### Database Connection Cleanup
Fixed inconsistent database connection handling:
- Replaced all `get_db()` calls with `get_db_connection()`
- Ensures connections are properly closed at request end via Flask's `g` object

### Live Score Updates (SSE)
Implemented Server-Sent Events for real-time score updates on active round page:

- SSE broadcaster class for in-memory event distribution
- `/sse/round/<round_id>` endpoint streams events to connected browsers
- `/tournament/.../matches-partial` returns HTML for AJAX refresh
- EventSource client with auto-reconnect on connection drops
- Next round button automatically enables when all matches complete

**Files Changed:**
- `app.py` - SSE broadcaster, endpoints, score broadcast on submit
- `templates/active_round.html` - EventSource client, partial include
- `templates/_matches_partial.html` - New partial for matches section

### Bulk Import Player Points
Added feature to import player wins and tournament counts from external tournaments (e.g., Excel):

- Button "Tuo puuttuvat pisteet" in Players tab
- Modal with textarea for pasting Excel data (Name, Wins, Tournaments columns)
- Preview table showing parsed data and player status (new/existing)
- Case-insensitive player matching
- Points and tournaments added to existing totals (not replaced)
- Creates new players in registry if needed
- Players with 0 wins are now imported (added to registry)
- Disabled button styling for import confirm button

**Database Changes:**
- Added `tournaments_adjustment` column to `player_points_adjustment` table
- Updated admin dashboard query to include imported tournaments in totals

**Files Changed:**
- `app.py` - POST `/admin/players/import-points` endpoint with tournaments support
- `database.py` - Schema and migration for tournaments_adjustment
- `templates/admin_dashboard.html` - Modal, JavaScript functions, CSP-compliant event handlers
- `static/css/admin.css` - Disabled button styling

**Tests:**
- 8 new tests covering import functionality

## Test Results

- 195 tests passing
- 3 skipped (expected)

## Restore Points Created

- `instance/padel_backup_before_import_test.db` - Before clearing for import testing
- `instance/padel_restore_point_2026-01-27_imported_data.db` - Real data with 32 players, 127 wins, 32 tournaments

## Known Issues

- ~~Season standings page not working when only imported points exist (no tournament matches)~~ **Fixed 2026-01-28**

## Commits

- `d806478` feat: add mobile drag feedback with in-place highlighting
- `1973a33` feat: improve mobile drag with floating clone
- `186449c` docs: add demo mode design
- `763240d` docs: add daily summary and update TODO for 2026-01-27
- `4dd0b69` feat: add demo mode for admin
- `9a4135b` docs: update TODO and daily summary with demo mode completion
- `a27efb2` feat: add Content-Security-Policy with nonces
- `cf29c1e` docs: update TODO with CSP implementation
- `c4ae28c` fix: use get_db_connection() consistently
- `ce1664c` docs: update TODO with database connection cleanup
- `39c506a` feat: add live score updates via Server-Sent Events
