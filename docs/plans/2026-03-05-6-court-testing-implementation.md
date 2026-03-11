# 6-Court Tournament Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build layered testing (automated + CLI simulation + in-app seeder) to verify 6-court tournament correctness before Sunday's tournament.

**Architecture:** Three independent deliverables: (1) new pytest tests in existing test files, (2) standalone CLI simulation script using court_movement.py and seeded_pairing.py directly, (3) standalone database seeder script using database.py.

**Tech Stack:** Python, pytest, court_movement.py, seeded_pairing.py, SQLite

---

### Task 1: Parameterized Court Movement Tests

**Files:**
- Modify: `tests/test_court_movement.py:261+` (append new tests)

**Step 1: Write the parameterized movement validation test**

Add at end of `tests/test_court_movement.py`:

```python
import random

@pytest.mark.parametrize("num_courts", [3, 4, 5, 6, 8])
def test_movement_rules_hold_for_n_courts(num_courts):
    """Every winner moves up exactly 1 court (or stays at court 1).
    Every loser moves down exactly 1 court (or stays at last court)."""
    num_players = num_courts * 4
    # All team 1 wins for predictable validation
    matches = [
        _make_match(c + 1, c*4+1, c*4+2, c*4+3, c*4+4, winning_team=1)
        for c in range(num_courts)
    ]

    result = generate_next_round_pairings(matches, num_courts=num_courts)

    assert len(result) == num_courts

    all_assigned = set()
    for court in result:
        assert len(court) == 4
        all_assigned.update(court)

    # All players assigned exactly once
    assert len(all_assigned) == num_players
    assert all_assigned == set(range(1, num_players + 1))

    # Court 1: winners from court 1 (stay) + winners from court 2 (up 1)
    assert set(result[0]) == {1, 2, 5, 6}

    # Last court: losers from court N-1 (down 1) + losers from court N (stay)
    last = num_courts - 1
    last_c = num_courts
    prev_c = num_courts - 1
    expected_last = {prev_c*4-1, prev_c*4, last_c*4-1, last_c*4}
    assert set(result[last]) == expected_last

    # Middle courts: losers from above + winners from below
    for k in range(1, num_courts - 1):
        above = k  # court above (0-indexed k corresponds to court k+1)
        below = k + 1
        expected = {
            above*4+3, above*4+4,       # losers from court above (1-indexed: court k)
            (below)*4+1, (below)*4+2     # winners from court below (1-indexed: court k+2)
        }
        assert set(result[k]) == expected, f"Court {k+1} mismatch"
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_movement_rules_hold_for_n_courts -v`
Expected: PASS for all 5 parameterizations (3, 4, 5, 6, 8 courts)

**Step 3: Commit**

```bash
git add tests/test_court_movement.py
git commit -m "test: add parameterized court movement test for 3-8 courts"
```

---

### Task 2: Multi-Round Stability Test

**Files:**
- Modify: `tests/test_court_movement.py` (append)

**Step 1: Write the multi-round simulation test**

```python
def test_multi_round_stability_6_courts_7_rounds():
    """Simulate 7 rounds with 6 courts. Every round must satisfy movement rules."""
    num_courts = 6
    num_players = num_courts * 4  # 24
    random.seed(42)

    # Round 1: arbitrary initial placement
    player_ids = list(range(1, num_players + 1))
    current_matches = []
    for c in range(num_courts):
        p = player_ids[c*4:(c+1)*4]
        winning_team = random.choice([1, 2])
        current_matches.append(_make_match(c + 1, p[0], p[1], p[2], p[3], winning_team=winning_team))

    for round_num in range(2, 8):  # Rounds 2-7
        result = generate_next_round_pairings(current_matches, num_courts=num_courts)

        assert len(result) == num_courts, f"Round {round_num}: expected {num_courts} courts"

        # All players assigned exactly once
        all_players = set()
        for court in result:
            assert len(court) == 4, f"Round {round_num}: court has {len(court)} players"
            all_players.update(court)
        assert len(all_players) == num_players, f"Round {round_num}: {len(all_players)} players instead of {num_players}"
        assert all_players == set(range(1, num_players + 1)), f"Round {round_num}: wrong player set"

        # Verify movement rules: check each player moved correctly
        # Build lookup: player -> court in previous round, and win/loss status
        prev_court = {}
        prev_won = {}
        for match in current_matches:
            court_num = match['court_number']
            if match['winning_team'] == 1:
                winners = {match['player1_id'], match['player2_id']}
                losers = {match['player3_id'], match['player4_id']}
            else:
                winners = {match['player3_id'], match['player4_id']}
                losers = {match['player1_id'], match['player2_id']}
            for pid in winners:
                prev_court[pid] = court_num
                prev_won[pid] = True
            for pid in losers:
                prev_court[pid] = court_num
                prev_won[pid] = False

        for court_idx, court_players in enumerate(result):
            new_court = court_idx + 1
            for pid in court_players:
                old_court = prev_court[pid]
                won = prev_won[pid]
                if won:
                    if old_court == 1:
                        assert new_court == 1, f"Round {round_num}: player {pid} won on court 1 but moved to court {new_court}"
                    else:
                        assert new_court == old_court - 1, f"Round {round_num}: player {pid} won on court {old_court} but moved to court {new_court} (expected {old_court - 1})"
                else:
                    if old_court == num_courts:
                        assert new_court == num_courts, f"Round {round_num}: player {pid} lost on court {num_courts} but moved to court {new_court}"
                    else:
                        assert new_court == old_court + 1, f"Round {round_num}: player {pid} lost on court {old_court} but moved to court {new_court} (expected {old_court + 1})"

        # Prepare matches for next round with random winners
        current_matches = []
        for c_idx, court in enumerate(result):
            winning_team = random.choice([1, 2])
            current_matches.append(_make_match(c_idx + 1, court[0], court[1], court[2], court[3], winning_team=winning_team))
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_court_movement.py::test_multi_round_stability_6_courts_7_rounds -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_court_movement.py
git commit -m "test: add multi-round stability test for 6 courts over 7 rounds"
```

---

### Task 3: Seeded Pairing Test for 6 Courts

**Files:**
- Modify: `tests/test_seeded_pairing.py:101+` (append)

**Step 1: Write the 6-court seeded pairing test**

```python
def test_seeded_pairing_6_courts_all_players_assigned():
    """Test seeded pairing with 24 players for 6 courts (base_overflow=2 branch)."""
    players_with_seeds = [
        {'id': i, 'seed_points': 1000 - i * 30}
        for i in range(1, 25)
    ]

    pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=6)

    assert len(pairings) == 6

    all_assigned = set()
    for court in pairings:
        assert len(court) == 4
        court_set = set(court)
        assert len(court_set) == 4, f"Duplicate player on court: {court}"
        assert court_set.isdisjoint(all_assigned), f"Player assigned to multiple courts"
        all_assigned.update(court_set)

    assert all_assigned == set(range(1, 25))


def test_seeded_pairing_6_courts_skill_tiers_respected():
    """Top seeds should end up on higher courts, bottom seeds on lower courts."""
    players_with_seeds = [
        {'id': i, 'seed_points': 1000 - i * 30}
        for i in range(1, 25)
    ]

    # Run multiple times to account for randomization
    top_4_on_court1_count = 0
    bottom_4_on_last_court_count = 0
    trials = 20

    for _ in range(trials):
        pairings = generate_seeded_round1_pairings(players_with_seeds, num_courts=6)
        court1_players = set(pairings[0])
        court6_players = set(pairings[5])

        # At least 3 of top 4 should be on court 1
        if len(court1_players & {1, 2, 3, 4}) >= 3:
            top_4_on_court1_count += 1
        # At least 3 of bottom 4 should be on court 6
        if len(court6_players & {21, 22, 23, 24}) >= 3:
            bottom_4_on_last_court_count += 1

    # Should hold in most trials (allow some randomization variance)
    assert top_4_on_court1_count >= trials * 0.7, f"Top seeds on court 1 only {top_4_on_court1_count}/{trials} times"
    assert bottom_4_on_last_court_count >= trials * 0.7, f"Bottom seeds on court 6 only {bottom_4_on_last_court_count}/{trials} times"
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_seeded_pairing.py -v`
Expected: All 6 tests PASS (4 existing + 2 new)

**Step 3: Commit**

```bash
git add tests/test_seeded_pairing.py
git commit -m "test: add 6-court seeded pairing tests"
```

---

### Task 4: CLI Simulation Script

**Files:**
- Create: `simulate_tournament.py` (project root)

**Step 1: Create the simulation script**

```python
#!/usr/bin/env python3
"""
Tournament Simulation Script

Simulates a full King of the Court tournament and displays
round-by-round results with player movement tracking.

Usage:
    python simulate_tournament.py --courts 6 --rounds 7
    python simulate_tournament.py --courts 6 --rounds 7 --seed 42
"""

import argparse
import random
import sys

from court_movement import generate_next_round_pairings
from seeded_pairing import generate_seeded_round1_pairings

# Finnish first and last names for realistic player generation
FIRST_NAMES = [
    "Matti", "Jussi", "Pekka", "Timo", "Antti", "Mikko", "Jari", "Ville",
    "Sami", "Tommi", "Lauri", "Olli", "Eero", "Kari", "Heikki", "Tuomas",
    "Liisa", "Sanna", "Kaisa", "Anna", "Minna", "Tiina", "Hanna", "Elina",
    "Riikka", "Jenni", "Päivi", "Maria", "Laura", "Johanna", "Satu", "Noora",
]

LAST_NAMES = [
    "Virtanen", "Korhonen", "Nieminen", "Mäkinen", "Hämäläinen",
    "Laine", "Heikkinen", "Koskinen", "Järvinen", "Lehtinen",
    "Salminen", "Heinonen", "Niemi", "Heikkilä", "Kinnunen",
    "Salonen", "Turunen", "Saarinen", "Lahtinen", "Leinonen",
    "Hiltunen", "Pitkänen", "Mäkelä", "Ojala", "Rantanen",
    "Savolainen", "Mattila", "Aaltonen", "Repo", "Miettinen",
    "Peltonen", "Toivonen",
]


def generate_players(num_players):
    """Generate fictional players with varied seed scores."""
    players = []
    used_names = set()
    for i in range(num_players):
        while True:
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[i % len(LAST_NAMES)]
            name = f"{first} {last}"
            if name not in used_names:
                used_names.add(name)
                break
            # Append number if name collision
            name = f"{first} {last}{i}"
            used_names.add(name)
            break

        # Spread seed scores: top players ~900, bottom ~300
        seed = max(100, 900 - i * (600 // max(1, num_players - 1)))
        players.append({
            'id': i + 1,
            'name': name,
            'seed_points': seed,
        })
    return players


def format_player(player_id, players_by_id):
    """Format player name with fixed width."""
    p = players_by_id[player_id]
    return f"{p['name'][:12]:>12}"


def find_player_court(player_id, courts):
    """Return (court_index, team) for a player, or None."""
    for court_idx, court in enumerate(courts):
        if player_id in court:
            pos = court.index(player_id)
            team = 1 if pos < 2 else 2
            return court_idx, team
    return None, None


def print_round(round_num, courts, winners_by_court, players_by_id):
    """Print a round summary."""
    print(f"\n{'='*60}")
    print(f"  ROUND {round_num}")
    print(f"{'='*60}")
    for court_idx, court in enumerate(courts):
        winner_team = winners_by_court[court_idx]
        t1 = f"{format_player(court[0], players_by_id)} + {format_player(court[1], players_by_id)}"
        t2 = f"{format_player(court[2], players_by_id)} + {format_player(court[3], players_by_id)}"
        marker = ""
        if winner_team == 1:
            marker = " << WIN"
        result_1 = f"[{t1}]{marker}"
        marker2 = ""
        if winner_team == 2:
            marker2 = " << WIN"
        result_2 = f"[{t2}]{marker2}"
        print(f"  Court {court_idx + 1}: {result_1}  vs  {result_2}")


def print_player_tracker(player_id, players_by_id, history, num_courts):
    """Print movement tracker for a single player."""
    p = players_by_id[player_id]
    print(f"\n  Player: {p['name']} (seed: {p['seed_points']})")

    courts_visited = []
    for round_num, (court_idx, team, won) in enumerate(history, 1):
        court_num = court_idx + 1
        courts_visited.append(court_num)

        if won is None:
            # Last round, no result yet
            arrow = " "
        elif won:
            if court_num == 1:
                arrow = "\u25cf"  # ● stays at top
            else:
                arrow = "\u2b06"  # ⬆
        else:
            if court_num == num_courts:
                arrow = "\u25cf"  # ● stays at bottom
            else:
                arrow = "\u2b07"  # ⬇

        result_str = "WON " if won else ("LOST" if won is not None else "    ")
        print(f"    Round {round_num}: Court {court_num} (Team {team}) \u2192 {result_str} {arrow}")

    # Movement line
    movement = " \u2192 ".join(f"[{c}]" for c in courts_visited)
    print(f"    Movement: {movement}")


def run_validation(all_rounds_data, num_courts, num_players):
    """Run automated validation checks and print results."""
    print(f"\n{'='*60}")
    print("  VALIDATION")
    print(f"{'='*60}")

    all_ok = True

    # Check 1: every player assigned exactly once per round
    for round_num, (courts, _) in enumerate(all_rounds_data, 1):
        all_players = set()
        for court in courts:
            all_players.update(court)
        if len(all_players) != num_players:
            print(f"  \u2718 Round {round_num}: {len(all_players)} players instead of {num_players}")
            all_ok = False
    if all_ok:
        print(f"  \u2714 All rounds: every player assigned exactly once")

    # Check 2: movement rules (rounds 2+)
    movement_ok = True
    for round_idx in range(1, len(all_rounds_data)):
        prev_courts, prev_winners = all_rounds_data[round_idx - 1]
        curr_courts, _ = all_rounds_data[round_idx]

        # Build player -> previous court mapping
        prev_court_map = {}
        prev_won_map = {}
        for court_idx, court in enumerate(prev_courts):
            court_num = court_idx + 1
            winner_team = prev_winners[court_idx]
            if winner_team == 1:
                winners = {court[0], court[1]}
                losers = {court[2], court[3]}
            else:
                winners = {court[2], court[3]}
                losers = {court[0], court[1]}
            for pid in winners:
                prev_court_map[pid] = court_num
                prev_won_map[pid] = True
            for pid in losers:
                prev_court_map[pid] = court_num
                prev_won_map[pid] = False

        for court_idx, court in enumerate(curr_courts):
            new_court = court_idx + 1
            for pid in court:
                old_court = prev_court_map[pid]
                won = prev_won_map[pid]
                if won:
                    expected = max(1, old_court - 1)
                    if new_court != expected:
                        print(f"  \u2718 Round {round_idx + 1}: player {pid} won on court {old_court}, moved to {new_court} (expected {expected})")
                        movement_ok = False
                else:
                    expected = min(num_courts, old_court + 1)
                    if new_court != expected:
                        print(f"  \u2718 Round {round_idx + 1}: player {pid} lost on court {old_court}, moved to {new_court} (expected {expected})")
                        movement_ok = False

    if movement_ok:
        print(f"  \u2714 All movements \u2264 1 court")
        print(f"  \u2714 All winners moved up (or stayed at court 1)")
        print(f"  \u2714 All losers moved down (or stayed at court {num_courts})")

    # Check 3: no repeat teammates in consecutive rounds
    teammate_ok = True
    for round_idx in range(1, len(all_rounds_data)):
        prev_courts, _ = all_rounds_data[round_idx - 1]
        curr_courts, _ = all_rounds_data[round_idx]

        # Build prev teammate map
        prev_teammates = {}
        for court in prev_courts:
            prev_teammates.setdefault(court[0], set()).add(court[1])
            prev_teammates.setdefault(court[1], set()).add(court[0])
            prev_teammates.setdefault(court[2], set()).add(court[3])
            prev_teammates.setdefault(court[3], set()).add(court[2])

        for court in curr_courts:
            # Team 1: court[0], court[1]
            if court[1] in prev_teammates.get(court[0], set()):
                teammate_ok = False
            # Team 2: court[2], court[3]
            if court[3] in prev_teammates.get(court[2], set()):
                teammate_ok = False

    if teammate_ok:
        print(f"  \u2714 No repeat teammates in consecutive rounds")
    else:
        print(f"  \u26a0 Some repeat teammates detected (may be unavoidable at boundaries)")

    return all_ok and movement_ok


def main():
    parser = argparse.ArgumentParser(description="Simulate a King of the Court tournament")
    parser.add_argument("--courts", type=int, default=6, help="Number of courts (default: 6)")
    parser.add_argument("--rounds", type=int, default=7, help="Number of rounds (default: 7)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    num_courts = args.courts
    num_rounds = args.rounds
    num_players = num_courts * 4

    if args.seed is not None:
        random.seed(args.seed)

    # Generate players
    players = generate_players(num_players)
    players_by_id = {p['id']: p for p in players}

    print(f"\n{'='*60}")
    print(f"  TOURNAMENT SIMULATION")
    print(f"  Courts: {num_courts} | Players: {num_players} | Rounds: {num_rounds}")
    if args.seed is not None:
        print(f"  Random seed: {args.seed}")
    print(f"{'='*60}")

    print(f"\n  Players (by seed):")
    for p in players:
        print(f"    #{p['id']:2d}  {p['name']:<20s}  seed: {p['seed_points']}")

    # Select 3 players to track: top, mid, low seed
    tracked_ids = [players[0]['id'], players[num_players // 2]['id'], players[-1]['id']]
    tracked_history = {pid: [] for pid in tracked_ids}

    all_rounds_data = []  # [(courts, winners_by_court), ...]

    # Round 1: seeded pairing
    round1_pairings = generate_seeded_round1_pairings(
        [{'id': p['id'], 'seed_points': p['seed_points']} for p in players],
        num_courts=num_courts
    )
    current_courts = round1_pairings

    for round_num in range(1, num_rounds + 1):
        # Simulate random winners
        winners_by_court = [random.choice([1, 2]) for _ in range(num_courts)]

        # Print round
        print_round(round_num, current_courts, winners_by_court, players_by_id)

        # Track selected players
        for pid in tracked_ids:
            court_idx, team = find_player_court(pid, current_courts)
            won = None
            if court_idx is not None:
                winner_team = winners_by_court[court_idx]
                won = (team == winner_team)
            tracked_history[pid].append((court_idx, team, won))

        # Save round data for validation
        all_rounds_data.append((current_courts, winners_by_court))

        # Generate next round pairings (except after last round)
        if round_num < num_rounds:
            prev_matches = []
            for court_idx, court in enumerate(current_courts):
                prev_matches.append({
                    'id': court_idx + 1,
                    'court_number': court_idx + 1,
                    'player1_id': court[0],
                    'player2_id': court[1],
                    'player3_id': court[2],
                    'player4_id': court[3],
                    'winning_team': winners_by_court[court_idx],
                    'completed': 1,
                })
            current_courts = generate_next_round_pairings(prev_matches, num_courts=num_courts)

    # Print player movement trackers
    print(f"\n{'='*60}")
    print(f"  PLAYER MOVEMENT TRACKER")
    print(f"{'='*60}")
    for pid in tracked_ids:
        print_player_tracker(pid, players_by_id, tracked_history[pid], num_courts)

    # Run validation
    ok = run_validation(all_rounds_data, num_courts, num_players)

    print()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
```

**Step 2: Run the script and verify output**

Run: `python simulate_tournament.py --courts 6 --rounds 7 --seed 42`
Expected: Full tournament output with all validation checks passing

**Step 3: Commit**

```bash
git add simulate_tournament.py
git commit -m "feat: add CLI tournament simulation script with player movement tracking"
```

---

### Task 5: In-App Test Data Seeder

**Files:**
- Create: `seed_test_tournament.py` (project root)

**Step 1: Create the seeder script**

This script uses the same database functions as the app. Key tables:
- `player_registry` (first_name, last_name)
- `tournaments` (name, num_courts, status, season_id)
- `tournament_players` (tournament_id, player_id)
- `seasons` (name, is_current)

```python
#!/usr/bin/env python3
"""
Test Tournament Seeder

Creates 24 test players and a 6-court tournament in the local database
for manual testing of the tournament UI flow.

Usage:
    python seed_test_tournament.py
    python seed_test_tournament.py --db /path/to/padel.db
"""

import argparse
import os
import sqlite3
import sys


# 24 Finnish player names
TEST_PLAYERS = [
    ("Matti", "Virtanen"), ("Jussi", "Korhonen"), ("Pekka", "Nieminen"),
    ("Timo", "Mäkinen"), ("Antti", "Hämäläinen"), ("Mikko", "Laine"),
    ("Jari", "Heikkinen"), ("Ville", "Koskinen"), ("Sami", "Järvinen"),
    ("Tommi", "Lehtinen"), ("Lauri", "Salminen"), ("Olli", "Heinonen"),
    ("Liisa", "Niemi"), ("Sanna", "Heikkilä"), ("Kaisa", "Kinnunen"),
    ("Anna", "Salonen"), ("Minna", "Turunen"), ("Tiina", "Saarinen"),
    ("Hanna", "Lahtinen"), ("Elina", "Leinonen"), ("Riikka", "Hiltunen"),
    ("Jenni", "Pitkänen"), ("Päivi", "Mäkelä"), ("Maria", "Ojala"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed test tournament data")
    parser.add_argument(
        "--db",
        default=os.path.join("instance", "padel.db"),
        help="Path to database file (default: instance/padel.db)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database file not found: {args.db}")
        print("Start the app first to initialize the database, or specify --db path.")
        sys.exit(1)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check for current season
        cursor.execute("SELECT id, name FROM seasons WHERE is_current = 1")
        season = cursor.fetchone()
        if not season:
            print("Error: No current season found. Create a season in the admin dashboard first.")
            sys.exit(1)

        print(f"Using season: {season['name']} (id: {season['id']})")

        # Insert players into player_registry (skip if name exists)
        player_ids = []
        for first, last in TEST_PLAYERS:
            cursor.execute(
                "SELECT id FROM player_registry WHERE first_name = ? AND last_name = ?",
                (first, last)
            )
            existing = cursor.fetchone()
            if existing:
                player_ids.append(existing['id'])
                print(f"  Existing player: {first} {last} (id: {existing['id']})")
            else:
                cursor.execute(
                    "INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
                    (first, last)
                )
                player_ids.append(cursor.lastrowid)
                print(f"  Created player: {first} {last} (id: {cursor.lastrowid})")

        # Create tournament
        num_courts = 6
        cursor.execute(
            "INSERT INTO tournaments (name, num_courts, status, season_id) VALUES (?, ?, 'setup', ?)",
            ("Testiturnaus", num_courts, season['id'])
        )
        tournament_id = cursor.lastrowid
        print(f"\nCreated tournament: Testiturnaus (id: {tournament_id}, courts: {num_courts})")

        # Add players to tournament
        for pid in player_ids:
            cursor.execute(
                "INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
                (tournament_id, pid)
            )

        conn.commit()

        print(f"\nAdded {len(player_ids)} players to tournament.")
        print(f"\nDone! Open the app and navigate to the admin dashboard.")
        print(f"Find 'Testiturnaus' in the tournaments list to start testing.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

**Step 2: Test the script**

Run: `python seed_test_tournament.py`
Expected: 24 players created, tournament created, no errors

**Step 3: Commit**

```bash
git add seed_test_tournament.py
git commit -m "feat: add test tournament seeder for manual UI testing"
```

---

### Task 6: Run Full Test Suite

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass (209 existing + ~9 new = ~218 total)

**Step 2: Run simulation script as final verification**

Run: `python simulate_tournament.py --courts 6 --rounds 7 --seed 42`
Expected: All validation checks pass
