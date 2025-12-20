-- Phase 3 Database Schema Migration
-- Creates new tables and modifies existing ones

-- 1. Seasons Table
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',
    total_tournaments INTEGER DEFAULT 10,
    summer_break_month INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_seasons_year ON seasons(year);
CREATE INDEX IF NOT EXISTS idx_seasons_status ON seasons(status);

-- 2. Player Registry Table
CREATE TABLE IF NOT EXISTS player_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(first_name, last_name)
);

CREATE INDEX IF NOT EXISTS idx_player_registry_name ON player_registry(last_name, first_name);

-- 3. Tournament Players Junction Table
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
);

CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id);

-- 4. Modify Tournaments Table (safe ALTER TABLE approach)
-- Check if columns exist before adding
-- Note: SQLite doesn't support conditional ALTER, so migration script will handle this

-- Create temporary columns tracking table
CREATE TABLE IF NOT EXISTS _migration_tracking (
    table_name TEXT,
    column_name TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (table_name, column_name)
);
