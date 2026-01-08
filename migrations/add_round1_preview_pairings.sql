-- Create round1_preview_pairings table
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
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_round1_preview_tournament
ON round1_preview_pairings(tournament_id);
