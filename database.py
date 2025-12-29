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
    conn = sqlite3.connect(db_path, uri=uri_mode)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionaries
    return conn

def init_db():
    """Initialize database with schema"""
    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)

    conn = get_db()
    cursor = conn.cursor()

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
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        )
    ''')

    # Create index for player name lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_player_registry_name
        ON player_registry(last_name, first_name)
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

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tournaments_season_id ON tournaments(season_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_seasons_is_current ON seasons(is_current)')

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
