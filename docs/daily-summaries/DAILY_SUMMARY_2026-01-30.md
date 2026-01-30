# Daily Summary - 2026-01-30

## Session Focus
Enhanced bulk import with matches column, improved pairing randomization, and fixed authentication bugs.

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

### Safari CSRF Fix
- Identified Safari-specific SESSION_COOKIE_SECURE issue on HTTP localhost
- Cookies blocked when SECURE=True on non-HTTPS connection
- Solution: Use FLASK_DEBUG=1 to disable secure cookie requirement locally

## Files Changed
- `app.py` - Import enhancement, fix-matches endpoint, session key fixes, Pelaajat query fix
- `database.py` - Added `matches_adjustment` column migration
- `seeded_pairing.py` - Rolling pool randomization algorithm
- `templates/admin_dashboard.html` - 4-column import UI, fix-matches section
- `tests/test_import_points.py` - New tests for matches import
- `tests/test_seeded_pairing.py` - Updated for probabilistic randomization
- 7 other test files - Session key fixes (`is_admin` → `logged_in_as_admin`)

## Technical Notes
- Rolling pool overflow: 2 players for 6+ courts, 1 for 2 or fewer courts
- All 203 tests passing
- Project now at ~4,600 lines of Python code

## Next Steps
- Continue with any remaining UX improvements
- Monitor Safari behavior in production

