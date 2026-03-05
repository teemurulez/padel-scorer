# 6-Court Tournament Testing Design

**Date:** 2026-03-05
**Context:** Tournament on Sunday with 6 courts (24 players, 6+ rounds). Need confidence that court movement, seeded pairing, and full tournament flow work correctly.

## Goals

1. Automated regression tests for 6-court scenarios
2. Visual CLI simulation for quick sanity checks
3. In-app test data for manual UI walkthrough

## Layer 1: Automated Unit Tests

### test_court_movement.py additions

**Parameterized movement validation (3, 4, 5, 6, 8 courts):**
- For each court count, simulate a round and verify:
  - Winners move up exactly 1 court (or stay if court 1)
  - Losers move down exactly 1 court (or stay if last court)
  - All players assigned exactly once
  - No duplicates

**Multi-round stability test (6 courts, 7 rounds):**
- Simulate 7 consecutive rounds with random winners
- Assert movement rules hold every round
- Assert no player appears twice in any round
- Assert all 24 players present in every round

**Teammate separation across rounds:**
- Verify previous teammates are split when possible over multiple rounds

### test_seeded_pairing.py additions

**6-court seeded pairing:**
- Test with 24 players, verify `base_overflow = 2` branch
- Assert all players assigned, no duplicates, 4 per court

## Layer 2: CLI Simulation Script

**File:** `simulate_tournament.py`

**Usage:**
```bash
python simulate_tournament.py --courts 6 --rounds 7
python simulate_tournament.py --courts 6 --rounds 7 --seed 42
```

**No Flask/database dependency.** Uses `court_movement.py` and `seeded_pairing.py` directly.

**Output:**

1. Round-by-round summary: all courts with players, teams, simulated result
2. Player movement tracker: 3 auto-selected players (top/mid/low seed) with visual flow:
   ```
   Player: Matti V (seed: high)
   Round 1: Court 2 (Team 1) -> WON  arrow_up
   Round 2: Court 1 (Team 2) -> LOST bullet (boundary)
   ...
   Movement: [2] -> [1] -> [1] -> [2] -> ...
   ```
3. Validation summary: automated checks with pass/fail for each rule

## Layer 3: In-App Test Data Seeder

**File:** `seed_test_tournament.py`

**Usage:**
```bash
python seed_test_tournament.py
python seed_test_tournament.py --db /path/to.db
```

**Creates:**
- 24 fictional players with Finnish names and varied seed scores
- Tournament "Testiturnaus" in setup status, 6 courts
- All 24 players added to tournament

**Does not create** rounds or matches - user starts Round 1 in the UI and clicks through manually.

## Success Criteria

- All existing 209 tests still pass
- New parameterized tests pass for 3-8 courts
- Multi-round simulation test passes for 7 rounds
- CLI script shows correct movement for 6 courts with no validation failures
- Manual UI walkthrough completes successfully for 6 courts
