#!/usr/bin/env python3
"""
Generate diverse test data for Padel Paroni.
Creates 3 tournaments with different player counts and 5+ rounds each.
"""
import sqlite3
import random
from datetime import datetime, timedelta

DATABASE = 'instance/padel.db'

def clear_data(conn):
    """Clear existing tournament data but keep admin users"""
    cursor = conn.cursor()
    # Delete in order respecting foreign keys
    cursor.execute('DELETE FROM scores')
    cursor.execute('DELETE FROM matches')
    cursor.execute('DELETE FROM rounds')
    cursor.execute('DELETE FROM tournament_players')
    cursor.execute('DELETE FROM round1_preview_pairings')
    cursor.execute('DELETE FROM tournaments')
    cursor.execute('DELETE FROM player_registry')
    cursor.execute('DELETE FROM seasons')
    conn.commit()
    print("Cleared existing data")

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

def main():
    conn = sqlite3.connect(DATABASE)

    # Clear existing data
    clear_data(conn)

    # Create season
    season_id = create_season(conn, "Kevat 2026")
    print(f"Created season 'Kevat 2026' (ID: {season_id})")

    # Create diverse set of players with Finnish names
    all_players_data = [
        # Strong players
        ("Mikko", "Virtanen"),    # Dominant player
        ("Anni", "Korhonen"),     # Strong player
        ("Jukka", "Makinen"),     # Strong player
        # Medium players
        ("Sari", "Nieminen"),
        ("Timo", "Heikkinen"),
        ("Laura", "Hamalainen"),
        ("Petri", "Laine"),
        ("Minna", "Koskinen"),
        # Casual players
        ("Kari", "Jarvinen"),
        ("Tiina", "Lehtonen"),
        ("Antti", "Saarinen"),
        ("Hanna", "Tuominen"),
        # Newer players
        ("Ville", "Rantanen"),
        ("Elina", "Salonen"),
        ("Juha", "Lahtinen"),
        ("Riikka", "Ahonen"),
        # Additional for variety
        ("Markku", "Ojala"),
        ("Kirsi", "Maki"),
        ("Seppo", "Lindqvist"),
        ("Anne", "Karjalainen"),
    ]

    all_players = create_players(conn, all_players_data)
    print(f"Created {len(all_players)} players")

    # Assign skill levels (higher = better)
    skill_map = {
        all_players[0][0]: 0.85,   # Mikko - dominant
        all_players[1][0]: 0.80,   # Anni - strong
        all_players[2][0]: 0.75,   # Jukka - strong
        all_players[3][0]: 0.65,   # Sari - medium-high
        all_players[4][0]: 0.60,   # Timo - medium
        all_players[5][0]: 0.58,   # Laura - medium
        all_players[6][0]: 0.55,   # Petri - medium
        all_players[7][0]: 0.52,   # Minna - medium
        all_players[8][0]: 0.48,   # Kari - medium-low
        all_players[9][0]: 0.45,   # Tiina - casual
        all_players[10][0]: 0.42,  # Antti - casual
        all_players[11][0]: 0.40,  # Hanna - casual
        all_players[12][0]: 0.35,  # Ville - newer
        all_players[13][0]: 0.33,  # Elina - newer
        all_players[14][0]: 0.30,  # Juha - newer
        all_players[15][0]: 0.28,  # Riikka - newer
        all_players[16][0]: 0.50,  # Markku - average
        all_players[17][0]: 0.47,  # Kirsi - average
        all_players[18][0]: 0.55,  # Seppo - medium
        all_players[19][0]: 0.38,  # Anne - lower
    }

    # Tournament 1: Big tournament - 16 players, 3 courts, 6 rounds
    t1_players = [p[0] for p in all_players[:16]]
    create_tournament(conn, "Tammikuun Mestaruus", season_id, t1_players,
                     num_courts=3, num_rounds=6, skill_levels=skill_map)

    # Tournament 2: Medium tournament - 12 players, 2 courts, 5 rounds
    # Mix of skill levels - some new players, some experienced
    t2_players = [all_players[i][0] for i in [0, 3, 5, 7, 9, 11, 12, 14, 16, 17, 18, 19]]
    create_tournament(conn, "Helmikuun Haaste", season_id, t2_players,
                     num_courts=2, num_rounds=5, skill_levels=skill_map)

    # Tournament 3: Small intense tournament - 8 players, 2 courts, 7 rounds
    # More competitive - top players battle it out
    t3_players = [all_players[i][0] for i in [0, 1, 2, 3, 4, 5, 6, 7]]
    create_tournament(conn, "Mestarin Cup", season_id, t3_players,
                     num_courts=2, num_rounds=7, skill_levels=skill_map)

    # Tournament 4: Active tournament - 12 players, 3 courts, round 1 in progress
    t4_players = [all_players[i][0] for i in [1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17]]
    create_active_tournament(conn, "Illan Peli", season_id, t4_players, num_courts=3)

    conn.close()
    print("\nTest data generation complete!")
    print("- 1 season")
    print("- 20 players with varying skill levels")
    print("- 3 completed tournaments (16p/6r, 12p/5r, 8p/7r)")
    print("- 1 active tournament (12p, 3 courts, round 1 in progress)")

if __name__ == '__main__':
    main()
