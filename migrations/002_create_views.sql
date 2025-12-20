-- Phase 3 Database Views
-- Complex queries exposed as views for easy access

-- 1. Player Seeding View (for Round 1)
CREATE VIEW IF NOT EXISTS player_seeding AS
SELECT
    pr.id as player_id,
    pr.first_name,
    pr.last_name,
    COALESCE(SUM(tp.total_points), 0) as seed_points,
    COUNT(DISTINCT tp.tournament_id) as recent_tournaments
FROM player_registry pr
LEFT JOIN tournament_players tp ON pr.id = tp.player_id
LEFT JOIN tournaments t ON tp.tournament_id = t.id
    AND t.status IN ('completed', 'archived')
    AND t.completed_at >= datetime('now', '-180 days')
GROUP BY pr.id, pr.first_name, pr.last_name
ORDER BY seed_points DESC;

-- 2. Season Standings View
CREATE VIEW IF NOT EXISTS season_standings AS
SELECT
    s.year,
    pr.id as player_id,
    pr.first_name,
    pr.last_name,

    -- PRIMARY RANKING METRIC
    COALESCE(SUM(tp.match_wins), 0) as total_match_wins,

    -- Supporting metrics
    COUNT(DISTINCT tp.tournament_id) as tournaments_played,
    ROUND(CAST(COALESCE(SUM(tp.match_wins), 0) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 2) as wins_per_tournament,

    -- Secondary statistics
    COUNT(CASE WHEN tp.final_rank = 1 THEN 1 END) as tournament_wins,
    COALESCE(SUM(tp.total_points), 0) as total_points,
    ROUND(CAST(COALESCE(SUM(tp.match_wins), 0) AS FLOAT) /
          NULLIF(COALESCE(SUM(tp.match_wins), 0) + COALESCE(SUM(tp.match_losses), 0), 0) * 100, 1)
          as win_percentage

FROM seasons s
CROSS JOIN player_registry pr
LEFT JOIN tournaments t ON t.season_id = s.id AND t.status IN ('completed', 'archived')
LEFT JOIN tournament_players tp ON tp.tournament_id = t.id AND tp.player_id = pr.id
GROUP BY s.year, pr.id, pr.first_name, pr.last_name
HAVING total_match_wins > 0 OR tournaments_played > 0
ORDER BY s.year DESC, total_match_wins DESC, wins_per_tournament DESC;

-- 3. Player Career Statistics View
CREATE VIEW IF NOT EXISTS player_career_stats AS
SELECT
    pr.id as player_id,
    pr.first_name,
    pr.last_name,

    -- Career totals
    COALESCE(SUM(tp.match_wins), 0) as career_match_wins,
    COALESCE(SUM(tp.match_losses), 0) as career_match_losses,
    COUNT(DISTINCT tp.tournament_id) as career_tournaments,
    COUNT(CASE WHEN tp.final_rank = 1 THEN 1 END) as career_tournament_wins,
    COALESCE(SUM(tp.total_points), 0) as career_total_points,

    -- Averages
    ROUND(CAST(COALESCE(SUM(tp.match_wins), 0) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 2) as avg_wins_per_tournament,
    ROUND(CAST(COALESCE(SUM(tp.total_points), 0) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 1) as avg_points_per_tournament,

    -- Win rate
    ROUND(CAST(COALESCE(SUM(tp.match_wins), 0) AS FLOAT) /
          NULLIF(COALESCE(SUM(tp.match_wins), 0) + COALESCE(SUM(tp.match_losses), 0), 0) * 100, 1)
          as career_win_percentage,

    -- Best/worst finishes
    MIN(tp.final_rank) as best_finish,
    MAX(tp.final_rank) as worst_finish

FROM player_registry pr
LEFT JOIN tournament_players tp ON pr.id = tp.player_id
LEFT JOIN tournaments t ON tp.tournament_id = t.id
    AND t.status IN ('completed', 'archived')
GROUP BY pr.id, pr.first_name, pr.last_name;

-- Performance indexes for views
CREATE INDEX IF NOT EXISTS idx_tournaments_completed_at ON tournaments(completed_at);
