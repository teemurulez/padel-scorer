# Daily Summary - December 22, 2025

## Session Overview

**Date:** December 22, 2025
**Focus:** Manual testing and bug fixing for manual team shuffling feature (Phase 3)
**Status:** 8 critical bugs found and fixed, feature partially tested, needs continued manual testing tomorrow
**Branch:** main
**Total Commits:** 10 bug fix commits

---

## Morning Session: Implementation Complete

The manual team shuffling feature was implemented earlier today following the plan from `docs/plans/2025-12-21-manual-team-shuffling.md`. All code was written, reviewed, and committed with 46/46 tests passing.

---

## Afternoon Session: Manual Testing & Bug Fixes

Started manual end-to-end testing of the feature. Discovered that the application had **8 critical bugs** that prevented basic functionality, despite all automated tests passing. This revealed significant gaps between Phase 2 and Phase 3 schema migrations.

---

## Bugs Found and Fixed

### Bug 1: Tournament ID Filter in Players Queries ❌→✅
**Symptom:** `sqlite3.OperationalError: no such column: tournament_id`

**Issue:** Code was filtering players by `tournament_id` in start_round route, but the `players` table doesn't have this column. Players are global across tournaments, not tournament-specific.

**Location:** `app.py:177, 185`

**Fix:** Removed `WHERE p.tournament_id = ?` and `WHERE tournament_id = ?` clauses from both queries

**Commit:** `8b8d7e9` - "fix: remove non-existent tournament_id filter from players queries"

---

### Bug 2: Incorrect Join Column in player_seeding View ❌→✅
**Symptom:** `sqlite3.OperationalError: no such column: ps.player_id`

**Issue:** Query was joining `p.id = ps.player_id`, but the `player_seeding` view exposes the column as `id`, not `player_id`.

**Location:** `app.py:176`

**Fix:** Changed join to `p.id = ps.id`

**Commit:** `1cd2fba` - "fix: correct player_seeding view join column"

---

### Bug 3: Inactive Leaderboard Button Was Clickable ❌→✅
**Symptom:** Clicking "View Leaderboard" before any matches led to error page

**Issue:** Button was always rendered as clickable link, even when there was no match data to display.

**Fix:**
- Added database query to check for completed matches
- Pass `has_leaderboard_data` boolean flag to template
- Conditionally render as disabled button with "(No data yet)" text when inactive
- Button becomes clickable only after first match is completed

**Location:** `app.py:248-255`, `templates/start_round.html:41-49`

**Commit:** `332c396` - "fix: make inactive leaderboard button non-clickable"

---

### Bug 4: Test Data Pollution in Player Names ❌→✅
**Symptom:** After creating tournament with player names, games showed old test data instead of entered names

**Issue:** Setup flow was using Phase 2 `players` table, which accumulated players from all tournaments. When `start_round` pulled players, it got ALL players from database history instead of just the ones for the current tournament.

**Root Cause:** Phase 2 schema had global `players` table, but the app was designed for single-tournament usage. With multiple tournaments, players from all tournaments mixed together.

**Fix:**
- Updated `setup_tournament` to add players to `player_registry` (Phase 3) instead of `players` table
- Split "First Last" format into `first_name` and `last_name` columns
- Updated `start_round` to pull from `player_registry` instead of `players`
- The `players` table is now only used for backward compatibility

**Location:** `app.py:111-128, 146`

**Commit:** `74bc6cf` - "fix: use player_registry instead of players table in setup flow"

---

### Bug 5: Round 1 Seeded Pairing Used Empty Players Table ❌→✅
**Symptom:** "No matches found for this round" error after starting Round 1

**Issue:** Round 1 seeded pairing query was still querying the old `players` table (from Phase 2), which was now empty because setup was adding to `player_registry`. No players found = no matches created.

**Fix:** Updated both primary and fallback queries in Round 1 seeded pairing to use `player_registry` instead of `players`

**Location:** `app.py:179-192`

**Commit:** `f60b4f1` - "fix: use player_registry in Round 1 seeded pairing query"

---

### Bug 6: Wrong Redirect After Team Confirmation ❌→✅
**Symptom:** After clicking "Start Match", redirected to round overview instead of score entry screen

**Issue:** The `confirm_match_teams` POST handler redirected to `active_tournament` which then redirected to round view, not to the match scoring screen.

**Expected Flow:** Court selection → Team confirmation → **Score entry screen**
**Actual Flow:** Court selection → Team confirmation → **Round overview** ❌

**Fix:**
- Changed redirect from `url_for('active_tournament')` to `url_for('score_entry', match_id=match['id'])`
- Updated test assertions to expect `/match/{id}/score` instead of `/tournament/{id}`

**Location:** `app.py:463`, `tests/test_team_shuffling.py:208, 332`

**Commit:** `d9a2a00` - "fix: redirect to score entry screen after team confirmation"

---

### Bug 7: Score Entry Route Couldn't Find Matches ❌→✅
**Symptom:** "Match not found" error when accessing score entry screen

**Issue:** The `score_entry` route was joining matches with the `players` table to get player names:
```sql
JOIN players p1 ON m.player1_id = p1.id
JOIN players p2 ON m.player2_id = p2.id
...
```
Since the `players` table is empty (we use `player_registry`), the JOIN failed and returned no match.

**Fix:**
- Removed all JOINs with `players` table
- Query now only joins matches with rounds
- Use `get_player()` helper function to fetch player details from `player_registry`
- Construct `player{1-4}_name` fields from `first_name + last_name`

**Location:** `app.py:606-627`

**Commit:** `fdadc39` - "fix: use player_registry in score_entry route"

---

### Bug 8: Score Recording Tried to Update Non-Existent Column ❌→✅
**Symptom:** 500 error with `sqlite3.OperationalError: no such column: total_points`

**Issue:** When submitting match scores, code tried to:
```python
UPDATE players SET total_points = total_points + 1 WHERE id = ?
```
But:
1. The `players` table is empty (we use `player_registry`)
2. The `total_points` column doesn't exist in Phase 3 schema

**Root Cause:** Phase 2 stored denormalized `total_points` in players table for leaderboard performance. Phase 3 calculates points from `scores` table on-the-fly.

**Fix:** Removed the UPDATE to `players.total_points`. Scores are already recorded in `scores` table (lines 646-649), which is sufficient for calculating standings.

**Location:** `app.py:650-654` (deleted these lines)

**Commit:** `78e3b0f` - "fix: remove players.total_points update from score recording"

---

## Root Cause Analysis

### The Core Problem: Incomplete Phase 2 → Phase 3 Migration

All 8 bugs stemmed from the same root cause: **incomplete migration from Phase 2 to Phase 3 database schema**.

#### Phase 2 Schema (Old)
- **players table:** `id, name, total_points`
- Players were global (no tournament association)
- Denormalized `total_points` for performance
- Designed for single-tournament usage

#### Phase 3 Schema (New)
- **player_registry table:** `id, first_name, last_name`
- **player_seeding view:** Calculates standings from scores
- Players are truly global across tournaments
- Normalized design, calculate points on-the-fly

#### What Went Wrong
- Some routes were updated to Phase 3 (player registry)
- Other routes still used Phase 2 patterns (players table)
- Tests passed because they set up data in ways that worked with both schemas
- Manual testing revealed the inconsistencies

---

## Technical Details

### The get_player() Helper Function

**Location:** `app.py:32-68`

Provides backward compatibility between Phase 2 and Phase 3:

```python
def get_player(player_id):
    """
    Three-tier fallback:
    1. Try player_registry (Phase 3)
    2. Fall back to players table with name splitting (Phase 2)
    3. Return placeholder for deleted players
    """
```

This helper is now used consistently across all routes that need player data.

---

## Manual Testing Progress

### ✅ Completed Today

1. **Tournament Setup**
   - Enter tournament name
   - Set number of courts
   - Enter player names (one per line)
   - Create tournament

2. **Start Round 1**
   - Click "Start First Round"
   - Court selection screen appears with all courts
   - Player names display correctly

3. **Court Selection**
   - All courts shown with algorithm-generated pairings
   - Player names render correctly (Phase 3 player_registry)

4. **Team Confirmation Screen**
   - Drag-and-drop interface loads
   - Can drag players to swap between teams
   - Visual feedback works (flash animation on swap)
   - "Reset to Original" button works

5. **Navigate to Score Entry**
   - Click "Start Match" button
   - Successfully redirects to score entry screen
   - Player names display correctly
   - Form renders with Team 1 / Team 2 radio buttons

### ⏳ Needs Testing Tomorrow

6. **Submit Match Scores**
   - Select winning team
   - Submit scores
   - Verify scores recorded in database
   - Check redirect after submission

7. **View Round Results**
   - Navigate to round overview
   - Verify all matches show correct status
   - Check that completed matches are marked

8. **Start Round 2**
   - Verify court movement algorithm works
   - Winners move up, losers move down
   - No duplicate pairings with previous teammates

9. **Multiple Courts**
   - Complete matches on multiple courts
   - Verify all scores recorded correctly
   - Check leaderboard calculations

10. **Leaderboard**
    - Verify standings calculated correctly from scores table
    - Check player statistics display
    - Test CSV export (if implemented)

11. **Complete Tournament**
    - Play through 3-4 rounds
    - Verify final standings
    - Test tournament completion workflow

---

## Files Modified Today

### Source Code
- **app.py** - 8 bug fixes across multiple routes:
  - `start_round()` - 2 fixes (tournament_id, player_seeding join)
  - `setup_tournament()` - 1 fix (use player_registry)
  - `confirm_match_teams()` - 1 fix (redirect to score_entry)
  - `score_entry()` - 2 fixes (use player_registry, remove total_points update)
  - Added `has_leaderboard_data` check

- **templates/start_round.html** - Conditional leaderboard button rendering

- **tests/test_team_shuffling.py** - Updated redirect expectations (2 tests)

### Database
- Multiple resets during testing
- All Phase 3 migrations applied and working
- Schema validated against expected structure

---

## Test Results

### Automated Tests
**Status:** ✅ **46/46 passing** (after each bug fix)

### Manual Tests
**Status:** ⏳ **Partially complete** (5/11 test scenarios completed)

---

## Key Insights

### 1. Test Coverage Gaps
Despite 46 passing unit tests, the application had 8 critical bugs that prevented basic functionality. The tests didn't catch these because:
- Tests set up data in artificial ways
- Tests didn't go through complete user flows
- Integration between routes wasn't tested

**Lesson:** Need more end-to-end integration tests.

### 2. Schema Migration Complexity
Migrating from Phase 2 to Phase 3 required updating dozens of implicit dependencies:
- Database queries
- Route handlers
- Template rendering
- Helper functions

**Lesson:** Schema migrations need comprehensive audit of all code paths.

### 3. Manual Testing Is Essential
Even with excellent unit test coverage, manual testing found issues that automated tests missed. The user experience perspective caught problems that code-level tests couldn't see.

**Lesson:** Always do manual testing for user-facing features.

### 4. Incremental Deployment Strategy
If this had been deployed to production incrementally, the bugs would have been catastrophic. The all-at-once Phase 3 migration approach prevented partial failures.

**Lesson:** Big schema changes should be deployed atomically with feature flags for rollback.

---

## Commands for Tomorrow

### Start Server
```bash
cd /Users/teemu/Documents/Teemu/Code/tennis-scorer
source venv/bin/activate
python app.py
```

Server runs at: **http://localhost:5001**

### Reset Database (if needed)
```bash
sqlite3 instance/padel.db << 'EOF'
DELETE FROM scores;
DELETE FROM matches;
DELETE FROM rounds;
DELETE FROM tournaments;
DELETE FROM players;
DELETE FROM player_registry;
DELETE FROM sqlite_sequence WHERE name IN ('tournaments', 'rounds', 'matches', 'scores', 'players', 'player_registry');
EOF
```

### Run Tests
```bash
source venv/bin/activate
pytest -v
```

### Check Git Status
```bash
git status
git log --oneline -10
```

---

## Next Steps for Tomorrow

### Priority 1: Complete Manual Testing
Continue where we left off:
1. Submit match scores (step 6)
2. View round results (step 7)
3. Start Round 2 with court movement (step 8)
4. Test multiple courts simultaneously (step 9)
5. Verify leaderboard calculations (step 10)
6. Complete full tournament workflow (step 11)

### Priority 2: Edge Cases
- Try to shuffle teams after scores are entered (should be prevented)
- Navigate back to previous rounds
- Test with odd number of players
- Test with maximum courts (depends on player count)

### Priority 3: Performance Testing
- Test with larger tournaments (12+ players, 3+ courts)
- Check query performance on leaderboard
- Verify UI remains responsive

### Priority 4: Production Readiness
- Backup database before deployment
- Test migrations on production-like data
- Create rollback plan
- Document user-facing changes

---

## Statistics

- **Session Duration:** ~3 hours
- **Commits:** 10 bug fix commits
- **Bugs Fixed:** 8 critical bugs
- **Tests Passing:** 46/46 (100%)
- **Lines Changed:** ~100 lines across multiple files
- **Manual Test Progress:** 5/11 scenarios (45%)

---

## Git Log (Today's Commits)

```
78e3b0f fix: remove players.total_points update from score recording
fdadc39 fix: use player_registry in score_entry route
d9a2a00 fix: redirect to score entry screen after team confirmation
f60b4f1 fix: use player_registry in Round 1 seeded pairing query
74bc6cf fix: use player_registry instead of players table in setup flow
332c396 fix: make inactive leaderboard button non-clickable
1cd2fba fix: correct player_seeding view join column
8b8d7e9 fix: remove non-existent tournament_id filter from players queries
```

---

## Summary

Today was a **critical bug-fixing session** that revealed significant gaps in our Phase 2 → Phase 3 migration. Despite having 46 passing automated tests, manual testing uncovered 8 critical bugs that prevented the feature from working at all.

All bugs have been fixed and the application is now much more stable. The feature has passed the first half of manual testing and is ready for continued testing tomorrow to complete the end-to-end workflow.

**Key Achievement:** The foundation is now solid. All routes consistently use Phase 3 schema (`player_registry`) and the `get_player()` helper provides backward compatibility.

**Tomorrow's Goal:** Complete manual testing through full tournament workflow and verify all functionality works correctly.
