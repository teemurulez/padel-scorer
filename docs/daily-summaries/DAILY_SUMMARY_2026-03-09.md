# Daily Summary — 2026-03-09

## Changes Made

### 1. Allow round recalculation even when scores exist
**Files:** `app.py`, `templates/active_round.html`, `tests/test_result_correction.py`

The "Laske kierros uudelleen" (recalculate round) button was previously hidden when any matches in the round were completed. In the March 8 incident, round 7 had 5/6 matches completed with wrong teams, making the button useless.

**Fix:**
- **Backend (`app.py`):** Removed the check that blocked recalculation when completed matches exist. The existing code already handles deleting scores during recalculation.
- **Frontend (`active_round.html`):** Button now always shows when `needs_recalculation` is true. When completed matches exist, the confirmation dialog includes a stronger warning: "VAROITUS: Kierroksella on X valmista ottelua. Kaikki tulokset poistetaan!"
- **Tests:** Updated two tests — the backend test now verifies recalculation succeeds with completed matches (and scores are cleared), the frontend test verifies the button is visible with completed matches.

All 217 tests pass.

### 2. Data fix: Jari Lehto incorrect match count
**Root cause:** Data entry error in imported points (`player_points_adjustment` table). Jari Lehto had `matches_adjustment = 17` while all other 2-tournament imports had `matches_adjustment = 15`. This gave him 25 total games instead of 23.

**Fix:** Created `padel_backup_20260309_180825_fixed.json` with the corrected value (17 → 15). Restored to production.

## Verification
- Local testing with seeded data (2 rounds, result correction on court 2, recalculate button visible with 4/6 completed matches)
- Full test suite: 217 passed, 3 skipped
