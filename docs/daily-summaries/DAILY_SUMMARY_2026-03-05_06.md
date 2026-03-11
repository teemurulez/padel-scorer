# Daily Summary - 2026-03-05 & 2026-03-06

## Session Focus

### March 5: 6-Court Testing Infrastructure
Comprehensive testing suite for 6-court tournaments — parameterized tests, simulation scripts, and test data seeder.

### March 6: Bug Fixes & Admin Features
Pre-tournament preparation session. Fixed several bugs found during real data import and tournament setup, added admin quality-of-life features.

## Changes - March 5

### Testing Infrastructure (6 commits)
- **Parameterized court movement test** covering 3, 4, 5, 6, 8 courts (`test_court_movement.py`)
- **Multi-round stability test**: 6 courts, 7 rounds with random winners
- **6-court seeded pairing tests**: all-assigned + skill-tier distribution
- **CLI simulation script** (`simulate_tournament.py`): tracks 3 players (top/mid/low seed) across rounds
- **Test data seeder** (`seed_test_tournament.py`): creates 24 Finnish test players + tournament in local DB
- **Design doc**: `docs/plans/2026-03-05-6-court-testing-implementation.md`

## Changes - March 6

### Bug Fixes (3 commits)

1. **Player profile season ranking ignored imported points** (`app.py`)
   - Root cause: `player_profile()` ranking query didn't join `player_points_adjustment`
   - Players with imported points showed wrong rank (e.g. #1 instead of #21)
   - Fixed both the per-player stats query and the all-standings ranking query to mirror the leaderboard query

2. **Tournament edit page showed seeding rank instead of leaderboard rank** (`app.py`, `admin_tournament_edit.html`)
   - The `#N` badge showed win-rate-based seeding rank, not total-points-based leaderboard rank
   - Season leader Tuukka showed as #4 (by win rate) instead of #1 (by points)
   - Now uses the same ranking logic as the season leaderboard

3. **"Aloita turnaus" button caused 404** (`static/js/tournament_edit.js`)
   - JS posted to `/start-round/<id>` which doesn't exist
   - Correct route is `/tournament/<id>/start_round`
   - Also added missing CSRF token to the dynamically created form

### New Features (2 commits)

4. **Empty database button** (`app.py`, `admin_dashboard.html`)
   - Added "Tyhjennä tietokanta" to admin Data tab
   - Requires typing "TYHJENNÄ" to confirm
   - Auto-downloads backup before emptying
   - Deletes all tables (old route was missing many tables)

5. **Copy pairings from season management** (`app.py`, `admin_dashboard.html`)
   - New API endpoint `/api/tournament/<id>/pairings-text`
   - "Kopioi parit" button on active tournaments in Kausien hallinta
   - Same `Kenttä N: A & B vs C & D` format as the edit page copy

## Files Changed
- `app.py` — 4 fixes/features (ranking queries, empty DB route, pairings API)
- `templates/admin_dashboard.html` — empty DB button + copy pairings button + JS
- `templates/admin_tournament_edit.html` — leaderboard rank badges
- `static/js/tournament_edit.js` — start tournament URL fix
- `court_movement.py` — (no changes, tested only)
- `simulate_tournament.py` — new CLI script
- `seed_test_tournament.py` — new test data seeder
- `tests/test_court_movement.py` — parameterized tests
- `tests/test_seeded_pairing.py` — 6-court tests

## Test Results
- 217 passed, 3 skipped (unchanged count, all existing tests still pass)

## Open Issues (Todo List)
1. Player slot styling breaks after manual drag-and-drop pair changes
2. Pair creation algorithm may produce suboptimal results — needs review
3. Page header font size changes when entering standings view

## Deployment
- All changes pushed to `main` and deployed to Railway
