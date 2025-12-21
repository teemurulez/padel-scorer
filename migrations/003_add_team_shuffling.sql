-- Migration: Add team shuffling support to matches table
-- Date: 2025-12-21

-- Add new columns to track team shuffling
ALTER TABLE matches ADD COLUMN teams_shuffled BOOLEAN DEFAULT 0;
ALTER TABLE matches ADD COLUMN original_player1_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player2_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player3_id INTEGER;
ALTER TABLE matches ADD COLUMN original_player4_id INTEGER;

-- Create index for querying shuffled matches (optional, for analytics)
CREATE INDEX IF NOT EXISTS idx_matches_shuffled ON matches(teams_shuffled) WHERE teams_shuffled = 1;
