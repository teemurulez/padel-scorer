#!/usr/bin/env python3
"""
Generate diverse test data for Padel Paroni.
Creates 3 tournaments with different player counts and 5+ rounds each.
"""
import sqlite3
import random
import os
from datetime import datetime, timedelta

DATABASE = os.environ.get('DATABASE_PATH', 'instance/padel.db')

def clear_data(conn, keep_players=True):
    """Clear existing tournament data but keep admin users and optionally players"""
    cursor = conn.cursor()
    # Delete in order respecting foreign keys
    cursor.execute('DELETE FROM scores')
    cursor.execute('DELETE FROM matches')
    cursor.execute('DELETE FROM rounds')
    cursor.execute('DELETE FROM tournament_players')
    cursor.execute('DELETE FROM round1_preview_pairings')
    cursor.execute('DELETE FROM tournaments')
    cursor.execute('DELETE FROM player_points_adjustment')
    if not keep_players:
        cursor.execute('DELETE FROM player_registry')
    cursor.execute('DELETE FROM seasons')
    conn.commit()
    print("Cleared existing data" + (" (kept players)" if keep_players else ""))

def create_season(conn, name):
    """Create a season and return its ID"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO seasons (name, is_current, created_at)
        VALUES (?, 1, ?)
    ''', (name, datetime.now().isoformat()))
    conn.commit()
    return cursor.lastrowid

def create_players(conn, players_data):
    """Create players in registry and return list of (id, name) tuples"""
    cursor = conn.cursor()
    player_ids = []
    for first_name, last_name in players_data:
        cursor.execute('''
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        ''', (first_name, last_name))
        player_ids.append((cursor.lastrowid, f"{first_name} {last_name}"))
    conn.commit()
    return player_ids

def create_tournament(conn, name, season_id, player_ids, num_courts, num_rounds, skill_levels):
    """
    Create a tournament with rounds and matches.
    skill_levels: dict mapping player_id to skill (0.0-1.0), higher = more likely to win
    """
    cursor = conn.cursor()

    # Create tournament
    cursor.execute('''
        INSERT INTO tournaments (name, num_courts, season_id, status, created_at)
        VALUES (?, ?, ?, 'completed', ?)
    ''', (name, num_courts, season_id, datetime.now().isoformat()))
    tournament_id = cursor.lastrowid

    # Add players to tournament
    for pid in player_ids:
        cursor.execute('''
            INSERT INTO tournament_players (tournament_id, player_id, total_points, match_wins, match_losses)
            VALUES (?, ?, 0, 0, 0)
        ''', (tournament_id, pid))

    conn.commit()

    # Track stats
    player_stats = {pid: {'wins': 0, 'losses': 0} for pid in player_ids}

    # Create rounds
    for round_num in range(1, num_rounds + 1):
        cursor.execute('''
            INSERT INTO rounds (tournament_id, round_number, status)
            VALUES (?, ?, 'completed')
        ''', (tournament_id, round_num))
        round_id = cursor.lastrowid

        # Shuffle players for this round
        shuffled = player_ids.copy()
        random.shuffle(shuffled)

        # Create matches for each court
        for court in range(1, num_courts + 1):
            base_idx = (court - 1) * 4
            if base_idx + 3 >= len(shuffled):
                # Not enough players for this court, wrap around
                match_players = [shuffled[i % len(shuffled)] for i in range(base_idx, base_idx + 4)]
            else:
                match_players = shuffled[base_idx:base_idx + 4]

            p1, p2, p3, p4 = match_players

            # Determine winner based on skill levels
            team1_skill = skill_levels.get(p1, 0.5) + skill_levels.get(p2, 0.5)
            team2_skill = skill_levels.get(p3, 0.5) + skill_levels.get(p4, 0.5)

            # Add randomness
            team1_score = team1_skill + random.uniform(-0.3, 0.3)
            team2_score = team2_skill + random.uniform(-0.3, 0.3)

            winning_team = 1 if team1_score > team2_score else 2

            # Create match
            cursor.execute('''
                INSERT INTO matches (round_id, court_number, player1_id, player2_id,
                                   player3_id, player4_id, winning_team, completed, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
            ''', (round_id, court, p1, p2, p3, p4, winning_team))
            match_id = cursor.lastrowid

            # Record scores - winners get 1 point
            if winning_team == 1:
                winners = [p1, p2]
                losers = [p3, p4]
            else:
                winners = [p3, p4]
                losers = [p1, p2]

            for pid in winners:
                cursor.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, 1)',
                             (match_id, pid))
                player_stats[pid]['wins'] += 1

            for pid in losers:
                cursor.execute('INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, 0)',
                             (match_id, pid))
                player_stats[pid]['losses'] += 1

    # Update tournament_players with final stats
    for pid, stats in player_stats.items():
        cursor.execute('''
            UPDATE tournament_players
            SET total_points = ?, match_wins = ?, match_losses = ?
            WHERE tournament_id = ? AND player_id = ?
        ''', (stats['wins'], stats['wins'], stats['losses'], tournament_id, pid))

    conn.commit()
    print(f"Created tournament '{name}' with {len(player_ids)} players, {num_rounds} rounds")
    return tournament_id

def create_active_tournament(conn, name, season_id, player_ids, num_courts):
    """
    Create an active tournament with round 1 in progress (matches not yet completed).
    """
    cursor = conn.cursor()

    # Create tournament with 'active' status
    cursor.execute('''
        INSERT INTO tournaments (name, num_courts, season_id, status, created_at)
        VALUES (?, ?, ?, 'active', ?)
    ''', (name, num_courts, season_id, datetime.now().isoformat()))
    tournament_id = cursor.lastrowid

    # Add players to tournament
    for pid in player_ids:
        cursor.execute('''
            INSERT INTO tournament_players (tournament_id, player_id, total_points, match_wins, match_losses)
            VALUES (?, ?, 0, 0, 0)
        ''', (tournament_id, pid))

    # Create round 1 with in_progress status
    cursor.execute('''
        INSERT INTO rounds (tournament_id, round_number, status)
        VALUES (?, 1, 'in_progress')
    ''', (tournament_id,))
    round_id = cursor.lastrowid

    # Create matches for each court (4 players per court)
    for court in range(1, num_courts + 1):
        base_idx = (court - 1) * 4
        if base_idx + 3 < len(player_ids):
            p1, p2, p3, p4 = player_ids[base_idx:base_idx + 4]
            cursor.execute('''
                INSERT INTO matches (round_id, court_number, player1_id, player2_id,
                                   player3_id, player4_id, completed, version)
                VALUES (?, ?, ?, ?, ?, ?, 0, 1)
            ''', (round_id, court, p1, p2, p3, p4))

    conn.commit()
    print(f"Created active tournament '{name}' with {len(player_ids)} players, {num_courts} courts, round 1 in progress")
    return tournament_id

def get_existing_players(conn):
    """Get existing players from the database"""
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name FROM player_registry ORDER BY id')
    rows = cursor.fetchall()
    return [(row[0], f"{row[1]} {row[2]}") for row in rows]


def main():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    # Clear existing tournament data but keep players
    clear_data(conn, keep_players=True)

    # Create season
    season_id = create_season(conn, "Kevat 2026")
    print(f"Created season 'Kevat 2026' (ID: {season_id})")

    # Use existing players from database
    all_players = get_existing_players(conn)

    if len(all_players) < 8:
        print(f"ERROR: Need at least 8 players in database, found {len(all_players)}")
        print("Add players via admin interface first, then run this script.")
        conn.close()
        return

    print(f"Using {len(all_players)} existing players:")
    for pid, name in all_players:
        print(f"  - {name} (ID: {pid})")

    # Assign random skill levels to players (higher = better)
    # This creates variety in match outcomes
    skill_map = {}
    for i, (pid, name) in enumerate(all_players):
        # Distribute skill levels somewhat randomly but spread out
        base_skill = 0.3 + (0.5 * (len(all_players) - i) / len(all_players))
        skill_map[pid] = base_skill + random.uniform(-0.1, 0.1)

    num_players = len(all_players)
    all_player_ids = [p[0] for p in all_players]

    # Tournament 1: Large tournament - use all players (or up to 16)
    t1_count = min(num_players, 16)
    t1_courts = max(2, t1_count // 4)
    t1_players = all_player_ids[:t1_count]
    create_tournament(conn, "Tammikuun Mestaruus", season_id, t1_players,
                     num_courts=t1_courts, num_rounds=6, skill_levels=skill_map)

    # Tournament 2: Medium tournament - mix of players
    t2_count = min(num_players, 12)
    t2_courts = max(2, t2_count // 4)
    # Take every other player for variety
    t2_players = [all_player_ids[i] for i in range(0, num_players, 2)][:t2_count]
    if len(t2_players) < 8:
        t2_players = all_player_ids[:8]
    create_tournament(conn, "Helmikuun Haaste", season_id, t2_players,
                     num_courts=t2_courts, num_rounds=5, skill_levels=skill_map)

    # Tournament 3: Small intense tournament - 8 players
    t3_players = all_player_ids[:8]
    create_tournament(conn, "Mestarin Cup", season_id, t3_players,
                     num_courts=2, num_rounds=7, skill_levels=skill_map)

    # Tournament 4: Active tournament - use different subset of players
    t4_count = min(num_players, 12)
    t4_courts = max(2, t4_count // 4)
    # Use players from the middle/end for variety
    t4_players = all_player_ids[2:2+t4_count] if num_players > 10 else all_player_ids[:t4_count]
    create_active_tournament(conn, "Marraskuu 2", season_id, t4_players, num_courts=t4_courts)

    conn.close()
    print("\nTest data generation complete!")
    print(f"- 1 season")
    print(f"- {num_players} players (existing)")
    print(f"- 3 completed tournaments")
    print(f"- 1 active tournament")

if __name__ == '__main__':
    main()
