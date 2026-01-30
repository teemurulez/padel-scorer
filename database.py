import sqlite3
import os

DATABASE = 'instance/padel.db'

def get_db():
    """Get database connection with row factory for dict-like access"""
    # Check if we're in a Flask app context with a custom DATABASE config
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE', DATABASE)
    except (ImportError, RuntimeError):
        # Not in Flask context or Flask not available
        db_path = DATABASE

    # Use URI mode if the path starts with 'file:'
    uri_mode = db_path.startswith('file:')
    conn = sqlite3.connect(db_path, uri=uri_mode, timeout=10.0)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionaries
    return conn

def init_db():
    """Initialize database with schema"""
    # Get the database path (uses Flask config if available)
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE', DATABASE)
    except (ImportError, RuntimeError):
        db_path = DATABASE

    # Ensure database directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = get_db()
    cursor = conn.cursor()

    # Enable WAL mode for better concurrency (only needs to be set once)
    cursor.execute('PRAGMA journal_mode=WAL')

    # Create players table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            total_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create tournaments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            num_courts INTEGER NOT NULL,
            status TEXT DEFAULT 'setup',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create rounds table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            status TEXT DEFAULT 'in_progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        )
    ''')

    # Create matches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            court_number INTEGER NOT NULL,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            player3_id INTEGER NOT NULL,
            player4_id INTEGER NOT NULL,
            winning_team INTEGER,
            completed BOOLEAN DEFAULT 0,
            teams_shuffled BOOLEAN DEFAULT 0,
            original_player1_id INTEGER,
            original_player2_id INTEGER,
            original_player3_id INTEGER,
            original_player4_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (round_id) REFERENCES rounds(id),
            FOREIGN KEY (player1_id) REFERENCES players(id),
            FOREIGN KEY (player2_id) REFERENCES players(id),
            FOREIGN KEY (player3_id) REFERENCES players(id),
            FOREIGN KEY (player4_id) REFERENCES players(id)
        )
    ''')

    # Create scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    ''')

    # Create admin_users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create player_registry table (Phase 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL CHECK(length(trim(first_name)) > 0 AND length(first_name) <= 100),
            last_name TEXT NOT NULL CHECK(length(trim(last_name)) > 0 AND length(last_name) <= 100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        )
    ''')

    # Link legacy players table to registry (Phase 3)
    cursor.execute("PRAGMA table_info(players)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'registry_id' not in columns:
        cursor.execute('''
            ALTER TABLE players ADD COLUMN registry_id INTEGER
            REFERENCES player_registry(id)
        ''')

    # Create index for registry lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_players_registry
        ON players(registry_id)
    ''')

    # Create seasons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_current BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP NULL
        )
    ''')

    # Add season_id column to tournaments table
    # Check if column exists first (for migration safety)
    cursor.execute("PRAGMA table_info(tournaments)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'season_id' not in columns:
        cursor.execute('ALTER TABLE tournaments ADD COLUMN season_id INTEGER REFERENCES seasons(id)')

    # Check and add status column if it doesn't exist
    cursor.execute("PRAGMA table_info(tournaments)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'status' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN status TEXT DEFAULT 'setup'")

    if 'completed_at' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN completed_at TIMESTAMP NULL")

    if 'archived_at' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN archived_at TIMESTAMP NULL")

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tournaments_season_id ON tournaments(season_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_seasons_is_current ON seasons(is_current)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)')

    # Tournament Players junction table (Phase 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            final_rank INTEGER,
            total_points INTEGER DEFAULT 0,
            match_wins INTEGER DEFAULT 0,
            match_losses INTEGER DEFAULT 0,
            PRIMARY KEY (tournament_id, player_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE RESTRICT
        )
    ''')

    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament
        ON tournament_players(tournament_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_player
        ON tournament_players(player_id)
    ''')

    # Create player_seeding view (calculates seed score from last 6 tournaments + adjustments)
    # seed_score = (wins + adjustment) / (matches + matches_adjustment) (higher is better)
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS player_seeding AS
        WITH recent_tournaments AS (
            -- Get last 6 completed tournaments per player
            SELECT
                tp.player_id,
                tp.tournament_id,
                tp.match_wins,
                tp.match_losses,
                ROW_NUMBER() OVER (
                    PARTITION BY tp.player_id
                    ORDER BY t.completed_at DESC
                ) as tournament_rank
            FROM tournament_players tp
            JOIN tournaments t ON tp.tournament_id = t.id
            WHERE t.status IN ('completed', 'archived')
        ),
        player_adjustments AS (
            -- Get adjustments for current season
            SELECT
                player_id,
                COALESCE(adjustment, 0) as wins_adj,
                COALESCE(matches_adjustment, 0) as matches_adj
            FROM player_points_adjustment adj
            JOIN seasons s ON adj.season_id = s.id AND s.is_current = 1
        )
        SELECT
            pr.id as player_id,
            pr.first_name,
            pr.last_name,
            COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) as total_wins,
            COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0) as total_matches,
            COUNT(rt.tournament_id) as recent_tournaments,
            CASE
                WHEN (COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0)) > 0
                THEN ROUND(
                    CAST(COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) AS FLOAT) /
                    (COALESCE(SUM(rt.match_wins + rt.match_losses), 0) + COALESCE(pa.matches_adj, 0)),
                    3
                )
                ELSE 0
            END as seed_score,
            -- Keep seed_points for backward compatibility
            COALESCE(SUM(rt.match_wins), 0) + COALESCE(pa.wins_adj, 0) as seed_points
        FROM player_registry pr
        LEFT JOIN recent_tournaments rt ON pr.id = rt.player_id AND rt.tournament_rank <= 6
        LEFT JOIN player_adjustments pa ON pr.id = pa.player_id
        GROUP BY pr.id, pr.first_name, pr.last_name, pa.wins_adj, pa.matches_adj
        ORDER BY seed_score DESC, total_wins DESC, last_name ASC, first_name ASC
    ''')

    # Create round1_preview_pairings table (Round 1 Court Assignment Editor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS round1_preview_pairings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            court_number INTEGER NOT NULL,
            team1_player1_id INTEGER NOT NULL,
            team1_player2_id INTEGER NOT NULL,
            team2_player1_id INTEGER NOT NULL,
            team2_player2_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (team1_player1_id) REFERENCES player_registry(id) ON DELETE RESTRICT,
            FOREIGN KEY (team1_player2_id) REFERENCES player_registry(id) ON DELETE RESTRICT,
            FOREIGN KEY (team2_player1_id) REFERENCES player_registry(id) ON DELETE RESTRICT,
            FOREIGN KEY (team2_player2_id) REFERENCES player_registry(id) ON DELETE RESTRICT,
            UNIQUE(tournament_id, court_number)
        )
    ''')

    # Create index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_round1_preview_tournament
        ON round1_preview_pairings(tournament_id)
    ''')

    # Add version column to matches table for concurrency control
    cursor.execute("PRAGMA table_info(matches)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'version' not in columns:
        cursor.execute("ALTER TABLE matches ADD COLUMN version INTEGER DEFAULT 1")

    # Player points adjustment table (for admin manual corrections)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_points_adjustment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            adjustment INTEGER DEFAULT 0,
            tournaments_adjustment INTEGER DEFAULT 0,
            matches_adjustment INTEGER DEFAULT 0,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE CASCADE,
            FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
            UNIQUE(player_id, season_id)
        )
    ''')

    # Migration: add tournaments_adjustment column if missing
    cursor.execute("PRAGMA table_info(player_points_adjustment)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'tournaments_adjustment' not in columns:
        cursor.execute("ALTER TABLE player_points_adjustment ADD COLUMN tournaments_adjustment INTEGER DEFAULT 0")
    if 'matches_adjustment' not in columns:
        cursor.execute("ALTER TABLE player_points_adjustment ADD COLUMN matches_adjustment INTEGER DEFAULT 0")

    # Tournament edit history table (for tracking changes across edit sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_edit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            change_type TEXT NOT NULL,
            change_data TEXT NOT NULL,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_edit_history_tournament
        ON tournament_edit_history(tournament_id)
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
