# Daily Summary - 2026-01-30

## Session Focus
Enhanced bulk import, improved pairing randomization, fixed authentication bugs, and diagnosed critical SSE blocking issue on single-worker hosts.

## Completed Work

### Bulk Import Enhancement
- Extended bulk import to 4 columns: Name, Wins, Tournaments, Matches
- Added `matches_adjustment` column to `player_points_adjustment` table
- Import now stores match counts for accurate win percentage calculation
- Added `/admin/players/fix-matches` endpoint for bulk-fixing missing matches data
- Updated import modal UI with new column labels and preview

### Rolling Pool Randomization
- Implemented rolling pool algorithm for Round 1 pairings
- Players are pooled in groups of ~6, 4 randomly selected per court
- Overflow players move to next court's pool
- Maintains skill-based seeding while adding randomness within tiers
- Prevents predictable "always same partners" problem

### Authentication Fixes
- Fixed session key mismatch: code checked `is_admin` but login set `logged_in_as_admin`
- This caused "Aloita" button to redirect to public site with auth error
- Updated all 8 test files to use correct session key

### Win Percentage Display Fixes
- Fixed admin Pelaajat view to include `matches_adjustment` in calculations
- Query now uses: `COUNT(DISTINCT m.id) + COALESCE(adj.matches_adjustment, 0)`
- Win rate calculation properly accounts for historical match data

### CSP Fix for Team Editing
- Fixed "Tallenna" button not working when editing teams after score entry
- CSP blocked inline `onclick` handlers
- Converted to addEventListener approach (CSP compliant)

### Critical: SSE Blocking Fix
- **Root cause found:** Server-Sent Events (SSE) endpoint `/sse/round/<id>` held the single worker indefinitely
- With 1 worker (PythonAnywhere free, Railway), SSE blocked ALL other requests
- Symptoms: First page load fast, subsequent navigation slow (15-20s)
- **Solution:** Added `DISABLE_SSE=1` environment variable to disable SSE on single-worker hosts
- Both Railway and PythonAnywhere now fast with SSE disabled

### Infrastructure Improvements
- Lazy database initialization (faster worker startup)
- SQLite timeout (10s) to prevent indefinite blocking
- WAL mode for better concurrency (set once in init_db)
- Request timing logs for debugging

## Files Changed
- `app.py` - SSE disable flag, lazy init, timing logs, CSP fixes
- `database.py` - SQLite timeout, WAL mode in init
- `seeded_pairing.py` - Rolling pool randomization
- `templates/admin_dashboard.html` - 4-column import UI
- `templates/confirm_match.html` - CSP-compliant event handlers
- `static/js/shuffle.js` - addEventListener instead of onclick
- `Procfile` - Preload and longer timeout for Railway
- Multiple test files - Session key fixes

## Technical Notes
- SSE is incompatible with single-worker deployments (blocks the only worker)
- Set `DISABLE_SSE=1` on Railway and PythonAnywhere
- All 203 tests passing

## Deployment
- **Railway:** Set `DISABLE_SSE=1` and `SKIP_MIGRATIONS=1` in environment variables
- **PythonAnywhere:** Add `os.environ['DISABLE_SSE'] = '1'` to WSGI config file

## Next Steps
- Consider polling-based alternative to SSE for live updates
- Monitor performance on both platforms

