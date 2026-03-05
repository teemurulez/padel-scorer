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
    assignment_ok = True
    for round_num, (courts, _) in enumerate(all_rounds_data, 1):
        all_players = []
        for court in courts:
            all_players.extend(court)
        if len(all_players) != num_players:
            print(f"  \u2718 Round {round_num}: {len(all_players)} players instead of {num_players}")
            assignment_ok = False
            all_ok = False
        elif len(set(all_players)) != num_players:
            print(f"  \u2718 Round {round_num}: duplicate player assignments detected")
            assignment_ok = False
            all_ok = False
    if assignment_ok:
        print(f"  \u2714 All rounds: every player assigned exactly once")

    # Check 2: movement rules (rounds 2+)
    movement_ok = True
    winner_ok = True
    loser_ok = True
    for round_idx in range(1, len(all_rounds_data)):
        prev_courts, prev_winners = all_rounds_data[round_idx - 1]
        curr_courts, _ = all_rounds_data[round_idx]

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
                diff = abs(new_court - old_court)
                if diff > 1:
                    print(f"  \u2718 Round {round_idx + 1}: player {pid} moved {diff} courts ({old_court} -> {new_court})")
                    movement_ok = False
                    all_ok = False
                if won:
                    expected = max(1, old_court - 1)
                    if new_court != expected:
                        print(f"  \u2718 Round {round_idx + 1}: player {pid} won on court {old_court}, moved to {new_court} (expected {expected})")
                        winner_ok = False
                        all_ok = False
                else:
                    expected = min(num_courts, old_court + 1)
                    if new_court != expected:
                        print(f"  \u2718 Round {round_idx + 1}: player {pid} lost on court {old_court}, moved to {new_court} (expected {expected})")
                        loser_ok = False
                        all_ok = False

    if movement_ok:
        print(f"  \u2714 All movements \u2264 1 court")
    if winner_ok:
        print(f"  \u2714 All winners moved up (or stayed at court 1)")
    if loser_ok:
        print(f"  \u2714 All losers moved down (or stayed at court {num_courts})")

    # Check 3: no repeat teammates in consecutive rounds
    teammate_repeats = 0
    for round_idx in range(1, len(all_rounds_data)):
        prev_courts, _ = all_rounds_data[round_idx - 1]
        curr_courts, _ = all_rounds_data[round_idx]

        prev_teammates = {}
        for court in prev_courts:
            prev_teammates.setdefault(court[0], set()).add(court[1])
            prev_teammates.setdefault(court[1], set()).add(court[0])
            prev_teammates.setdefault(court[2], set()).add(court[3])
            prev_teammates.setdefault(court[3], set()).add(court[2])

        for court in curr_courts:
            if court[1] in prev_teammates.get(court[0], set()):
                teammate_repeats += 1
            if court[3] in prev_teammates.get(court[2], set()):
                teammate_repeats += 1

    if teammate_repeats == 0:
        print(f"  \u2714 No repeat teammates in consecutive rounds")
    else:
        print(f"  \u26a0 {teammate_repeats} repeat teammate pair(s) detected (may be unavoidable at boundaries)")

    return all_ok


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

    all_rounds_data = []

    # Round 1: seeded pairing
    round1_pairings = generate_seeded_round1_pairings(
        [{'id': p['id'], 'seed_points': p['seed_points']} for p in players],
        num_courts=num_courts
    )
    current_courts = round1_pairings

    for round_num in range(1, num_rounds + 1):
        winners_by_court = [random.choice([1, 2]) for _ in range(num_courts)]

        print_round(round_num, current_courts, winners_by_court, players_by_id)

        for pid in tracked_ids:
            court_idx, team = find_player_court(pid, current_courts)
            won = None
            if court_idx is not None:
                winner_team = winners_by_court[court_idx]
                won = (team == winner_team)
            tracked_history[pid].append((court_idx, team, won))

        all_rounds_data.append((current_courts, winners_by_court))

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

    print(f"\n{'='*60}")
    print(f"  PLAYER MOVEMENT TRACKER")
    print(f"{'='*60}")
    for pid in tracked_ids:
        print_player_tracker(pid, players_by_id, tracked_history[pid], num_courts)

    ok = run_validation(all_rounds_data, num_courts, num_players)

    print()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
