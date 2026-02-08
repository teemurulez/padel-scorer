# Daily Summary - 2026-02-08

## Session Focus
Critical bug fix discovered during first real tournament. Court movement algorithm broken for 3+ courts.

## Bug Report
**Reported by:** User during live tournament with 5 courts
**Symptom:** Player won on court 4, moved to court 2 instead of court 3
**Expected:** Winners move up exactly 1 court, losers move down exactly 1 court

## Root Cause Analysis

**Location:** `court_movement.py:167`

**The bug:** The algorithm concatenated all winners followed by all losers into a flat list, then distributed them in groups of 4 to courts:
```python
sorted_players = all_winners + all_losers  # WRONG
```

With 5 courts (20 players), this produced:
- Courts 1-2: all 10 winners (packed together)
- Courts 3-5: all 10 losers (packed together)

Court 4 winners jumped to court 2 instead of moving up one to court 3.

**Why it wasn't caught:** The only test (`test_generate_next_round_pairings_moves_winners_up`) used 2 courts — the one case where the broken algorithm coincidentally produces the correct result (all winners → court 1, all losers → court 2 = same as move-up-one).

## Fix Applied

Replaced flat concatenation with proper King of the Court interleaving:
- **Court 1:** Court 1 winners (stay) + Court 2 winners (up 1)
- **Court K:** Court K-1 losers (down 1) + Court K+1 winners (up 1)
- **Last court:** Court N-1 losers (down 1) + Court N losers (stay)

## Files Changed
- `court_movement.py` - Rewrote `generate_next_round_pairings()` step 2 (interleaving logic)
- `tests/test_court_movement.py` - Added 4 new tests (3, 4, 6 courts + mixed winners)
- `TODO.md` - Updated status, added feature request, added tech debt item
- `docs/daily-summaries/DAILY_SUMMARY_2026-02-08.md` - This file

## New Tests Added
1. `test_movement_3_courts_winners_move_up_one` - 3-court movement
2. `test_movement_4_courts_winners_move_up_one` - 4-court movement
3. `test_movement_6_courts_court4_winner_goes_to_court3` - 6-court regression test
4. `test_movement_mixed_winners_across_courts` - Different teams winning on different courts

## Test Results
- 209 passed, 3 skipped (was 205 + 4 new)

## Other Issues
- Railway admin login password not working — reset via `railway ssh`
- Multiple stale Flask server processes caused confusion during local testing

## Lessons Learned
- **Test with realistic court counts.** The app was developed and tested with 2 courts but used in production with 5+. The algorithm was fundamentally broken for the real use case.
- **Added tech debt item:** Review all features tested with only 2 courts

## Feature Requests Captured
- Auto-calculate court count from player list in tournament creation modal

## Deployment
- Fix needs to be deployed to Railway (pending push)
