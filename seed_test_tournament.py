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
