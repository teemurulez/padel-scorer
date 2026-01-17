# Court Movement Algorithm

## Overview
The King of the Court tournament format uses dynamic court assignment based on match results. This document describes how players move between courts after each round.

## Rules

### Round 1: Random Pairing
- All players are randomly shuffled
- Players are assigned sequentially to courts (4 per court)
- No movement logic - this establishes the initial hierarchy

### Round 2+: Position-Based Pairing
- **Winners move UP** in court order (Court 1 is the highest court)
- **Losers move DOWN** in court order
- **Previous teammates are separated** when possible

## Algorithm Steps

The court movement algorithm (`generate_next_round_pairings`) follows these steps:

### 1. Validate Previous Round
```python
# Ensure all matches are complete
for match in previous_matches:
    if match.get('winning_team') is None:
        raise ValueError("Cannot generate pairings: incomplete matches")
```

### 2. Sort Players by Court Position
```python
# For each match, separate winners and losers
# Court hierarchy: Court 1 > Court 2 > Court 3, etc.
all_winners = []
all_losers = []

for match in sorted_by_court_number:
    if winning_team == 1:
        winners = [player1, player2]
        losers = [player3, player4]
    else:
        winners = [player3, player4]
        losers = [player1, player2]

    all_winners.extend(winners)
    all_losers.extend(losers)
```

### 3. Redistribute to New Courts
```python
# Combine winners first, then losers
# This puts all winners at top courts, all losers at bottom courts
sorted_players = all_winners + all_losers

# Distribute to courts
# Top 4 → Court 1
# Next 4 → Court 2
# etc.
```

### 4. Apply Teammate Separation
```python
# Within each court, avoid pairing previous teammates
for court in courts:
    p1, p2, p3, p4 = court_players

    # Check if p1 and p2 were teammates
    if p2 in get_previous_teammates(p1):
        # Swap p2 with p3 to separate
        p2, p3 = p3, p2
```

## Example Flow

### Round 1 Results
**Court 1:**
- Team 1: Alice + Bob (25 pts)
- Team 2: Carol + Dave (15 pts)
- **Winner:** Alice + Bob

**Court 2:**
- Team 1: Eve + Frank (20 pts)
- Team 2: Grace + Hank (25 pts)
- **Winner:** Grace + Hank

### Round 2 Pairings (After Movement)

**Step 1 - Separate winners and losers:**
- Winners: [Alice, Bob, Grace, Hank]
- Losers: [Carol, Dave, Eve, Frank]

**Step 2 - Redistribute:**
- Court 1 (top 4): Alice, Bob, Grace, Hank
- Court 2 (next 4): Carol, Dave, Eve, Frank

**Step 3 - Apply teammate separation:**

**Court 1:**
- Initial: (Alice + Bob) vs (Grace + Hank)
- Check: Alice & Bob WERE teammates → SWAP
- Final: (Alice + Grace) vs (Bob + Hank) ✓

**Court 2:**
- Initial: (Carol + Dave) vs (Eve + Frank)
- Check: Carol & Dave WERE teammates → SWAP
- Final: (Carol + Eve) vs (Dave + Frank) ✓

## Key Functions

### `get_previous_teammates(player_id, previous_matches)`
Returns a set of player IDs who were teammates with the given player in previous matches.

**Example:**
```python
# If player 1 was on Team 1 with player 2:
get_previous_teammates(1, previous_matches)
# Returns: {2}
```

### `sort_players_by_court_position(matches)`
Sorts all players by court hierarchy (winners before losers on each court).

**Example:**
```python
matches = [
    {'court_number': 1, 'winning_team': 2, 'player1_id': 1, ...},
    {'court_number': 2, 'winning_team': 1, 'player1_id': 5, ...}
]
# Returns: [3, 4, 1, 2, 5, 6, 7, 8]
#          Court 1    Court 2
#          W   L      W   L
```

### `generate_next_round_pairings(previous_matches, num_courts)`
Main orchestration function that generates complete pairings for the next round.

**Returns:** List of court assignments
```python
[
    [player1_id, player2_id, player3_id, player4_id],  # Court 1
    [player5_id, player6_id, player7_id, player8_id],  # Court 2
]
```

## Design Decisions

### Why Simple Swap Strategy?

The teammate separation uses a simple strategy: only check if p1 and p2 were teammates, and swap p2 with p3 if needed.

**Advantages:**
- ✅ Simple and fast (O(n) complexity)
- ✅ Easy to understand and debug
- ✅ Works for the majority of scenarios
- ✅ Court movement naturally rotates players over multiple rounds

**Limitations:**
- ⚠️ May not separate p3-p4 teammate pairs
- ⚠️ Complex multi-round histories might have edge cases

**Rationale:**
For typical 8-16 player tournaments, this approach is sufficient. The King of the Court format naturally rotates players through different positions, providing separation over time. Comprehensive graph-based matching would be overkill for this use case.

### Why Separate Module?

The court movement logic is in a separate `court_movement.py` module rather than embedded in `app.py`.

**Benefits:**
- **Single Responsibility:** Movement logic isolated from Flask routing
- **Testability:** Easy to unit test without Flask context
- **Reusability:** Could be used in CLI, API, or other interfaces
- **Maintainability:** Clear separation of concerns

## Error Handling

### Incomplete Matches
If any match from the previous round is incomplete (no winning_team set), the algorithm raises a `ValueError`:

```python
ValueError: Cannot generate pairings: Match {id} has incomplete matches
```

**User Impact:** Must complete all matches before starting the next round.

### Insufficient Players
If there aren't enough players for the requested number of courts (need 4 per court), the algorithm stops early and creates matches only for courts with sufficient players.

## Testing

### Unit Tests
See `tests/test_court_movement.py` for comprehensive test coverage:
- Empty match history
- Team 1 teammate identification
- Team 2 teammate identification
- Single-court winner/loser sorting
- Multi-court sorting
- Teammate separation
- Complete movement algorithm
- Incomplete match validation

### Integration Tests
See `docs/test-results.md` for manual integration test scenarios.

## Performance

- **Time Complexity:** O(n) where n = number of players
- **Space Complexity:** O(n) for storing sorted player lists
- **Typical Runtime:** <1ms for 16 players

## Future Enhancements (Phase 3)

Potential improvements not included in Phase 2:

1. **Comprehensive Teammate Separation**
   - Graph-based matching algorithm
   - Considers all teammate pairs (not just p1-p2)
   - Optimizes for maximum separation

2. **Multi-Round History**
   - Track teammate history over all rounds (not just previous)
   - Avoid re-pairing players who have been teammates multiple times

3. **Weighted Court Movement**
   - Consider margin of victory
   - Move players up/down by more than one court based on performance

4. **Configurable Rules**
   - Allow tournament organizer to configure movement strategy
   - Options: strict separation, balanced mixing, skill-based grouping

## Implementation Details

### File Structure
```
tennis-scorer/
├── court_movement.py           # Core algorithm (181 lines)
│   ├── get_previous_teammates()
│   ├── sort_players_by_court_position()
│   ├── assign_teams_with_separation()  (unused in final implementation)
│   └── generate_next_round_pairings()
│
├── app.py                      # Flask integration
│   └── start_round()           # Uses generate_next_round_pairings()
│
└── tests/
    └── test_court_movement.py  # 8 test cases
```

### Flask Integration
The `start_round()` function in `app.py` integrates the movement algorithm:

```python
if round_number == 1:
    # Random pairing for Round 1
    # ... existing logic ...
else:
    # Movement-based pairing for Round 2+
    previous_matches = db.execute(
        '''SELECT m.* FROM matches m
           JOIN rounds r ON m.round_id = r.id
           WHERE r.tournament_id = ?
           AND r.round_number = ?
           AND m.completed = 1''',
        (tournament_id, round_number - 1)
    ).fetchall()

    court_assignments = generate_next_round_pairings(
        [dict(m) for m in previous_matches],
        num_courts
    )

    # Create matches from assignments
    for court_num, players in enumerate(court_assignments, start=1):
        db.execute('''INSERT INTO matches ... ''')
```

## Troubleshooting

### Issue: "Cannot generate pairings: incomplete matches"
**Cause:** Not all matches from previous round have been completed.
**Solution:** Complete all matches before starting next round.

### Issue: Previous teammates still paired together
**Cause:** Simple swap strategy has limitations (see Design Decisions).
**Solution:** This is expected behavior for some edge cases. Court movement over multiple rounds will naturally separate players.

### Issue: Players missing from round
**Cause:** Likely a bug in player counting or court assignment logic.
**Solution:** Check that all players from previous round are included in winners + losers lists.

## References

- Implementation Plan: `docs/plans/2025-12-19-phase-2-court-movement.md`
- Daily Summary: `docs/daily-summaries/DAILY_SUMMARY_2025-12-19.md`
