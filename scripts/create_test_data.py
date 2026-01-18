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


def create_tournament(db, season_id, player_ids, name, num_courts=2):
    """Create a tournament with rounds and matches"""
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

    # Create 3 rounds
    for round_num in range(1, 4):
        db.execute(
            "INSERT INTO rounds (tournament_id, round_number, status) VALUES (?, ?, ?)",
            (tournament_id, round_num, "completed")
        )
        round_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create matches for this round (2 courts = 2 matches)
        # Rotate players for variety
        for court in range(num_courts):
            base_idx = (round_num - 1 + court * 4) % len(player_ids)
            p1 = player_ids[base_idx % len(player_ids)]
            p2 = player_ids[(base_idx + 1) % len(player_ids)]
            p3 = player_ids[(base_idx + 2) % len(player_ids)]
            p4 = player_ids[(base_idx + 3) % len(player_ids)]

            # Alternate which team wins
            team1_won = (round_num + court) % 2 == 0
            winning_team = 1 if team1_won else 2

            db.execute(
                """INSERT INTO matches
                   (round_id, court_number, player1_id, player2_id, player3_id, player4_id,
                    winning_team, completed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (round_id, court + 1, p1, p2, p3, p4, winning_team, 1)
            )
            match_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Add scores (winners get 3 points, losers get 1)
            db.execute(
                "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                (match_id, p1, 3 if team1_won else 1)
            )
            db.execute(
                "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                (match_id, p2, 3 if team1_won else 1)
            )
            db.execute(
                "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                (match_id, p3, 1 if team1_won else 3)
            )
            db.execute(
                "INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)",
                (match_id, p4, 1 if team1_won else 3)
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

        # Create 2 tournaments
        t1_id = create_tournament(db, season_id, player_ids, "Tammikuun turnaus", num_courts=2)
        print(f"  Tournament 1 ID: {t1_id}")

        t2_id = create_tournament(db, season_id, player_ids, "Helmikuun turnaus", num_courts=2)
        print(f"  Tournament 2 ID: {t2_id}")

        # Add a manual adjustment for one player
        add_point_adjustment(db, season_id, player_ids[0], 5, "Bonus for organizing")
        print(f"  Added +5 adjustment for {TEST_PLAYERS[0][0]} {TEST_PLAYERS[0][1]}")

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
        print()
        print("You can now test at: http://127.0.0.1:5050/admin")


if __name__ == "__main__":
    main()
