# Phase 3 Stage 3a: Minimal Player Profiles - Design Document

**Date:** December 31, 2025
**Author:** Design session with Teemu
**Status:** Design Complete - Ready for Implementation
**Scope:** Minimal MVP - Season stats + basic navigation only

---

## Overview

### Goal
Create individual player profile pages showing current season statistics, accessible via clickable names in the season leaderboard.

### Scope (Minimal Version)
- Single profile page at `/player/<int:player_id>/profile`
- Displays current season stats for players who have participated
- Handles edge case: shows friendly message for players with no season data
- Makes player names clickable in the existing season leaderboard
- Basic navigation (back to leaderboard)

### Out of Scope (for later stages)
- Tournament history table
- Career statistics (all-time)
- Previous seasons data
- Export functionality
- Player editing/management

---

## Profile Page Structure

### URL Structure
```
/player/<int:player_id>/profile
```

### Data to Display

**When player HAS season data:**
- **Player Name** (header): "FirstName LastName"
- **Current Season Year**: e.g., "2025 Season"
- **Season Rank**: "#3" (their position in season standings)
- **Match Wins**: Total individual match wins (PRIMARY metric)
- **Tournaments Played**: Count of tournaments participated in
- **Wins per Tournament**: Average (match_wins / tournaments_played)
- **Total Points**: Sum of points across all season tournaments
- **Win Percentage**: Match wins / (wins + losses) × 100

**When player has NO season data:**
- **Player Name** (header)
- **Current Season Year**
- **Message**: "No tournaments played this season yet"

### Navigation
- "← Back to Season Leaderboard" button/link
- Link to home page (optional)

---

## Implementation Details

### Route Implementation

**New Route:**
```python
@app.route('/player/<int:player_id>/profile')
def player_profile(player_id):
    """Display player profile with current season statistics"""

    # Get player from registry
    player = db.execute(
        'SELECT * FROM player_registry WHERE id = ?',
        (player_id,)
    ).fetchone()

    if not player:
        flash('Player not found')
        return redirect('/leaderboard')

    # Get current year
    current_year = datetime.now().year

    # Get season stats from season_standings view
    # Note: This view already exists from Phase 3 design
    season_stats = db.execute('''
        SELECT * FROM season_standings
        WHERE player_id = ? AND year = ?
    ''', (player_id, current_year)).fetchone()

    # Calculate rank if stats exist
    rank = None
    if season_stats:
        all_standings = db.execute('''
            SELECT player_id FROM season_standings
            WHERE year = ?
            ORDER BY total_match_wins DESC, wins_per_tournament DESC
        ''', (current_year,)).fetchall()

        rank = next(
            (i + 1 for i, row in enumerate(all_standings)
             if row['player_id'] == player_id),
            None
        )

    return render_template(
        'player_profile.html',
        player=player,
        season_stats=season_stats,
        current_year=current_year,
        rank=rank
    )
```

### Template Structure

**New Template:** `templates/player_profile.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="player-profile">
    <!-- Header -->
    <div class="profile-header">
        <h1>{{ player.first_name }} {{ player.last_name }}</h1>
        <p class="season-label">{{ current_year }} Season</p>
    </div>

    {% if season_stats %}
        <!-- Season Statistics -->
        <div class="stats-grid">
            <div class="stat-card rank">
                <span class="label">Season Rank</span>
                <span class="value">#{{ rank }}</span>
            </div>

            <div class="stat-card primary">
                <span class="label">Match Wins</span>
                <span class="value">{{ season_stats.total_match_wins }}</span>
            </div>

            <div class="stat-card">
                <span class="label">Tournaments</span>
                <span class="value">{{ season_stats.tournaments_played }}</span>
            </div>

            <div class="stat-card">
                <span class="label">Wins/Tournament</span>
                <span class="value">{{ season_stats.wins_per_tournament }}</span>
            </div>

            <div class="stat-card">
                <span class="label">Total Points</span>
                <span class="value">{{ season_stats.total_points }}</span>
            </div>

            <div class="stat-card">
                <span class="label">Win Rate</span>
                <span class="value">{{ season_stats.win_percentage }}%</span>
            </div>
        </div>
    {% else %}
        <!-- No Data Message -->
        <div class="no-data">
            <p>No tournaments played this season yet.</p>
        </div>
    {% endif %}

    <!-- Navigation -->
    <div class="profile-actions">
        <a href="/leaderboard" class="btn btn-secondary">← Back to Season Leaderboard</a>
    </div>
</div>
{% endblock %}
```

### Modified Template: Season Leaderboard

**Update:** `templates/season_leaderboard.html`

Make player names clickable:
```html
<td class="player-name">
    <a href="/player/{{ player.player_id }}/profile">
        {{ player.last_name }}, {{ player.first_name }}
    </a>
</td>
```

### Styling

Add to `static/css/style.css`:
```css
/* Player Profile */
.player-profile {
    max-width: 1000px;
    margin: 0 auto;
}

.profile-header {
    text-align: center;
    margin-bottom: 2rem;
}

.profile-header h1 {
    margin-bottom: 0.5rem;
}

.season-label {
    color: #666;
    font-size: 1.1rem;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: #f5f5f5;
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
}

.stat-card.primary {
    background: #fff3cd;
    border: 2px solid #ffc107;
}

.stat-card.rank {
    background: #d4edda;
    border: 2px solid #28a745;
}

.stat-card .label {
    display: block;
    font-size: 0.9rem;
    color: #666;
    margin-bottom: 0.5rem;
}

.stat-card .value {
    display: block;
    font-size: 2rem;
    font-weight: bold;
    color: #333;
}

.no-data {
    text-align: center;
    padding: 3rem;
    background: #f8f9fa;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.no-data p {
    font-size: 1.2rem;
    color: #666;
}

.profile-actions {
    text-align: center;
    margin-top: 2rem;
}
```

---

## Database Dependencies

### Required Tables/Views
- `player_registry` - Already exists from Stage 2
- `season_standings` - View defined in Phase 3 design document (needs to be created)

### season_standings View
```sql
CREATE VIEW season_standings AS
SELECT
    s.year,
    pr.id as player_id,
    pr.first_name,
    pr.last_name,

    -- PRIMARY RANKING METRIC
    SUM(tp.match_wins) as total_match_wins,

    -- Supporting metrics
    COUNT(DISTINCT tp.tournament_id) as tournaments_played,
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 2) as wins_per_tournament,

    -- Secondary statistics
    COUNT(CASE WHEN tp.final_rank = 1 THEN 1 END) as tournament_wins,
    SUM(tp.total_points) as total_points,
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(SUM(tp.match_wins) + SUM(tp.match_losses), 0) * 100, 1)
          as win_percentage

FROM seasons s
JOIN tournaments t ON t.season_id = s.id
JOIN tournament_players tp ON tp.tournament_id = t.id
JOIN player_registry pr ON tp.player_id = pr.id
WHERE t.status IN ('completed', 'archived')
GROUP BY s.year, pr.id, pr.first_name, pr.last_name
ORDER BY s.year DESC, total_match_wins DESC, wins_per_tournament DESC;
```

**Note:** This view may already exist from Phase 3 implementation. Verify before creating.

---

## Testing Strategy

### Manual Testing Checklist
- [ ] Navigate to `/player/1/profile` - verify profile loads
- [ ] Click player name from season leaderboard - verify navigation works
- [ ] View profile for player with season data - verify all stats display correctly
- [ ] View profile for player with NO season data - verify "No data yet" message shows
- [ ] Click "Back to Season Leaderboard" - verify returns to leaderboard
- [ ] Verify rank calculation is correct (matches leaderboard position)
- [ ] Test on mobile - verify responsive layout

### Unit Tests
```python
# tests/test_player_profile.py
def test_player_profile_with_data(client, db):
    """Test profile displays correctly for player with season data"""
    # Setup: Create player and tournament data
    player_id = create_test_player("Erik", "Andersson")
    create_season_data(player_id, match_wins=25, tournaments=5)

    # Test: Visit profile
    response = client.get(f'/player/{player_id}/profile')

    assert response.status_code == 200
    assert b'Erik Andersson' in response.data
    assert b'25' in response.data  # match wins
    assert b'5' in response.data   # tournaments

def test_player_profile_no_data(client, db):
    """Test profile shows message for player with no season data"""
    player_id = create_test_player("New", "Player")

    response = client.get(f'/player/{player_id}/profile')

    assert response.status_code == 200
    assert b'New Player' in response.data
    assert b'No tournaments played' in response.data

def test_player_not_found(client, db):
    """Test 404 or redirect for non-existent player"""
    response = client.get('/player/99999/profile')

    assert response.status_code == 302  # Redirect
    # Follow redirect
    response = client.get('/player/99999/profile', follow_redirects=True)
    assert b'Player not found' in response.data
```

---

## Implementation Tasks

### Task 1: Verify season_standings View Exists
- Check if view already created in database
- If not, create the view using SQL from design document
- Test view returns correct data

### Task 2: Create Profile Route
- Add `/player/<int:player_id>/profile` route to `app.py`
- Query player from registry
- Query season stats from view
- Calculate rank
- Handle edge cases (player not found, no season data)

### Task 3: Create Profile Template
- Create `templates/player_profile.html`
- Implement stats grid layout
- Add "No data" message section
- Add navigation links

### Task 4: Update Season Leaderboard
- Modify `templates/season_leaderboard.html`
- Make player names clickable (link to profile)
- Test navigation works

### Task 5: Add Styling
- Add CSS to `static/css/style.css`
- Style stats grid (responsive)
- Style stat cards (primary/rank highlighting)
- Test responsive layout on mobile

### Task 6: Testing
- Write unit tests
- Run manual testing checklist
- Verify all edge cases handled

---

## Success Criteria

**Feature complete when:**
- ✅ Can navigate to player profile from season leaderboard
- ✅ Profile displays all season stats correctly
- ✅ Profile handles players with no data gracefully
- ✅ Navigation back to leaderboard works
- ✅ Layout is responsive on mobile
- ✅ All tests passing

---

## Future Enhancements (Stage 3b+)

**Not included in this minimal version:**
- Tournament history table (show each tournament with rank/stats)
- Career statistics (all-time totals)
- Previous seasons selector
- Match-by-match history
- Export player data to CSV
- Player comparison feature

These will be added in future stages as needed.

---

**End of Design Document**
