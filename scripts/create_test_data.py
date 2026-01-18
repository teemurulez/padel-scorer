#!/usr/bin/env python3
"""
Create test data for development and testing.

Run from project root:
    python scripts/create_test_data.py

This creates:
- 1 active season "Kevät 2026"
- 8 players in the registry
- 2 completed tournaments with matches and scores
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, init_db

# Test players (Finnish names)
TEST_PLAYERS = [
    ("Matti", "Virtanen"),
    ("Anna", "Korhonen"),
    ("Jussi", "Mäkinen"),
    ("Laura", "Nieminen"),
    ("Mikko", "Heikkinen"),
    ("Sanna", "Laine"),
    ("Petri", "Koskinen"),
    ("Tiina", "Järvinen"),
]


def clear_test_data(db):
    """Clear existing test data"""
    print("Clearing existing data...")

    # Delete in order to respect foreign keys
    db.execute("DELETE FROM scores")
    db.execute("DELETE FROM matches")
    db.execute("DELETE FROM rounds")
    db.execute("DELETE FROM round1_preview_pairings")
    db.execute("DELETE FROM tournament_players")
    db.execute("DELETE FROM tournament_edit_history")
    db.execute("DELETE FROM tournaments")
    db.execute("DELETE FROM player_points_adjustment")
    db.execute("DELETE FROM player_registry")
    db.execute("DELETE FROM seasons")
    db.commit()


def create_season(db):
    """Create test season"""
    print("Creating season...")
    db.execute(
        "INSERT INTO seasons (name, is_current) VALUES (?, ?)",
        ("Kevät 2026", 1)
    )
    db.commit()
    return db.execute("SELECT id FROM seasons WHERE is_current = 1").fetchone()['id']


def create_players(db):
    """Create test players"""
    print("Creating players...")
    player_ids = []
    for first_name, last_name in TEST_PLAYERS:
        db.execute(
            "INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)",
            (first_name, last_name)
        )
        player_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    db.commit()
    return player_ids


def create_tournament(db, season_id, player_ids, name, num_courts=2, match_results=None):
    """Create a tournament with rounds and matches.

    match_results: list of (round, court, winning_team) tuples for predetermined outcomes
    """
    print(f"Creating tournament: {name}...")

    # Create tournament
    db.execute(
        "INSERT INTO tournaments (name, num_courts, season_id, status) VALUES (?, ?, ?, ?)",
        (name, num_courts, season_id, "completed")
    )
    tournament_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Add players to tournament
    for player_id in player_ids:
        db.execute(
            "INSERT INTO tournament_players (tournament_id, player_id) VALUES (?, ?)",
            (tournament_id, player_id)
        )

    # Realistic pairings - mix up partners each round
    # Players: 0=Matti, 1=Anna, 2=Jussi, 3=Laura, 4=Mikko, 5=Sanna, 6=Petri, 7=Tiina
    round_pairings = [
        # Round 1: Court 1: 0,1 vs 2,3 | Court 2: 4,5 vs 6,7
        [(0, 1, 2, 3), (4, 5, 6, 7)],
        # Round 2: Court 1: 0,2 vs 4,6 | Court 2: 1,3 vs 5,7
        [(0, 2, 4, 6), (1, 3, 5, 7)],
        # Round 3: Court 1: 0,4 vs 1,5 | Court 2: 2,6 vs 3,7
        [(0, 4, 1, 5), (2, 6, 3, 7)],
    ]

    # Default results if not specified - varied outcomes
    if match_results is None:
        match_results = [
            (1, 1, 1), (1, 2, 2),  # Round 1: Team1 wins C1, Team2 wins C2
            (2, 1, 2), (2, 2, 1),  # Round 2: Team2 wins C1, Team1 wins C2
            (3, 1, 1), (3, 2, 2),  # Round 3: Team1 wins C1, Team2 wins C2
        ]

    # Create rounds and matches
    for round_num in range(1, 4):
        db.execute(
            "INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, ?, ?)",
            (tournament_id, round_num, "completed")
        )
        round_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        pairings = round_pairings[round_num - 1]

        for court_idx, (p1_idx, p2_idx, p3_idx, p4_idx) in enumerate(pairings):
            court = court_idx + 1
            p1 = player_ids[p1_idx]
            p2 = player_ids[p2_idx]
            p3 = player_ids[p3_idx]
            p4 = player_ids[p4_idx]

            # Find the result for this match
            winning_team = 1
            for r, c, w in match_results:
                if r == round_num and c == court:
                    winning_team = w
                    break

            team1_won = winning_team == 1

            db.execute(
                """INSERT INTO matches
                   (round_id, court_number, player1_id, player2_id, player3_id, player4_id,
                    winning_team, completed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (round_id, court, p1, p2, p3, p4, winning_team, 1)
            )
            match_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Add scores for winners only (3 points per win)
            if team1_won:
                db.execute(
                    "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                    (match_id, p1, 3)
                )
                db.execute(
                    "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                    (match_id, p2, 3)
                )
            else:
                db.execute(
                    "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                    (match_id, p3, 3)
                )
                db.execute(
                    "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                    (match_id, p4, 3)
                )

    db.commit()
    return tournament_id


def add_point_adjustment(db, season_id, player_id, adjustment, note):
    """Add a manual point adjustment"""
    db.execute(
        """INSERT INTO player_points_adjustment (player_id, season_id, adjustment, note)
           VALUES (?, ?, ?, ?)""",
        (player_id, season_id, adjustment, note)
    )
    db.commit()


def main():
    print("=" * 50)
    print("Creating test data for Tennis Scorer")
    print("=" * 50)

    # Initialize database connection
    import flask
    from app import app

    with app.app_context():
        db = get_db()

        # Clear and create fresh data
        clear_test_data(db)

        # Create season
        season_id = create_season(db)
        print(f"  Season ID: {season_id}")

        # Create players
        player_ids = create_players(db)
        print(f"  Created {len(player_ids)} players")

        # Create 2 tournaments with different results for variety
        # Tournament 1: Default results
        t1_results = [
            (1, 1, 1), (1, 2, 2),  # R1: Matti/Anna win, Petri/Tiina win
            (2, 1, 2), (2, 2, 1),  # R2: Mikko/Petri win, Anna/Laura win
            (3, 1, 1), (3, 2, 2),  # R3: Matti/Mikko win, Laura/Tiina win
        ]
        t1_id = create_tournament(db, season_id, player_ids, "Tammikuun turnaus",
                                  num_courts=2, match_results=t1_results)
        print(f"  Tournament 1 ID: {t1_id}")

        # Tournament 2: Different results - mix it up
        t2_results = [
            (1, 1, 2), (1, 2, 1),  # R1: Jussi/Laura win, Mikko/Sanna win
            (2, 1, 1), (2, 2, 2),  # R2: Matti/Jussi win, Sanna/Tiina win
            (3, 1, 2), (3, 2, 1),  # R3: Anna/Sanna win, Jussi/Petri win
        ]
        t2_id = create_tournament(db, season_id, player_ids, "Helmikuun turnaus",
                                  num_courts=2, match_results=t2_results)
        print(f"  Tournament 2 ID: {t2_id}")

        print()
        print("=" * 50)
        print("Test data created successfully!")
        print("=" * 50)
        print()
        print("Summary:")
        print(f"  - Season: Kevät 2026")
        print(f"  - Players: {len(player_ids)}")
        print(f"  - Tournaments: 2 (completed)")
        print(f"  - Rounds per tournament: 3")
        print(f"  - Matches per round: 2")
        print(f"  - Scoring: Wins only (no participation points)")
        print()
        print("You can now test at: http://127.0.0.1:5050/admin")


if __name__ == "__main__":
    main()
