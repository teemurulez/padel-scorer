# Season Leaderboard - Design Document

**Date:** December 23, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

Add a season-wide leaderboard accessible from the home page that shows aggregated player statistics across all tournaments in the current calendar year, plus expandable individual tournament leaderboards. Includes ability to clear all data to start a fresh season.

## Problem Statement

Currently, leaderboards are only accessible within individual tournaments. Users need a way to:
1. View season-wide standings across all tournaments
2. Compare player performance across the entire year
3. Access individual tournament results from a central location
4. Reset all data at the end of a season to start fresh

## Proposed Solution

### Home Page Integration

**Button Visibility:**
- Show "View Season Leaderboard" button when at least one tournament exists
- Hide button if no tournaments have been created yet
- Secondary button styling (not primary action)

**Placement:**
- Below "Setup New Tournament" button on home page
- Centered, full-width on mobile, auto-width on desktop

**Route Update:**
```python
@app.route('/')
def index():
    db = get_db_connection()
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE status = "active" LIMIT 1'
    ).fetchone()

    # Check if any tournaments exist
    has_tournaments = db.execute(
        'SELECT COUNT(*) as count FROM tournaments'
    ).fetchone()['count'] > 0

    if tournament:
        return redirect(url_for('active_tournament', tournament_id=tournament['id']))

    return render_template('index.html', has_tournaments=has_tournaments)
```

### Season Definition

**Calendar Year:**
- Season = January 1 to December 31 of current year
- Automatically filters tournaments by created_at year
- No manual season management needed

**Year Determination:**
```sql
WHERE strftime('%Y', t.created_at) = strftime('%Y', 'now')
```

### Season Leaderboard Page Structure

**1. Season Header**
```
Season 2025 Leaderboard
Jan 1, 2025 - Dec 31, 2025
12 Tournaments

[Clear All Data] (right-aligned, danger button)
```

**2. Season-Wide Standings Table**

Aggregates statistics across ALL tournaments in current year:

| Rank | Player Name | Total Wins | Total Matches | Win Rate % |
|------|-------------|------------|---------------|------------|
| 1    | John Smith  | 45         | 60            | 75.0%      |
| 2    | Jane Doe    | 42         | 58            | 72.4%      |
| ...  | ...         | ...        | ...           | ...        |

- Sorted by: Total Wins DESC, then Win Rate DESC
- Only shows players with at least 1 completed match
- Empty state if no completed matches in current year

**3. Individual Tournament Sections**

Collapsed by default, expandable on click:

```
▶ Summer Tournament 2025 • June 15, 2025 • 4 Rounds • 3 Courts • [Completed]
  (collapsed - click to expand)

▼ Spring Championship • May 20, 2025 • 5 Rounds • 2 Courts • [Active]
  (expanded - showing full leaderboard table)
  | Rank | Player | Wins | Matches | Win % |
  |------|--------|------|---------|-------|
  | ...  | ...    | ...  | ...     | ...   |
```

- Tournaments sorted by date DESC (most recent first)
- Click tournament header to toggle expand/collapse
- ▶ icon when collapsed, ▼ when expanded
- Shows tournament metadata in collapsed view
- Shows full leaderboard table when expanded

### Technical Design

#### New Route: Season Leaderboard

**Endpoint:** `GET /leaderboard/season`

```python
@app.route('/leaderboard/season')
def season_leaderboard():
    """Show season-wide leaderboard plus individual tournaments"""
    db = get_db_connection()

    # Get current year
    current_year = datetime.now().year

    # Get season-wide player statistics
    season_stats = db.execute(
        '''SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as total_wins,
            COUNT(DISTINCT m.id) as total_matches,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate
           FROM player_registry pr
           LEFT JOIN matches m ON (
               pr.id = m.player1_id OR
               pr.id = m.player2_id OR
               pr.id = m.player3_id OR
               pr.id = m.player4_id
           )
           LEFT JOIN rounds r ON m.round_id = r.id
           LEFT JOIN tournaments t ON r.tournament_id = t.id
           LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
           WHERE strftime('%Y', t.created_at) = ?
             AND m.completed = 1
           GROUP BY pr.id, pr.first_name, pr.last_name
           HAVING total_matches > 0
           ORDER BY total_wins DESC, win_rate DESC, pr.last_name ASC''',
        (str(current_year),)
    ).fetchall()

    # Get all tournaments in current year
    tournaments = db.execute(
        '''SELECT * FROM tournaments
           WHERE strftime('%Y', created_at) = ?
           ORDER BY created_at DESC''',
        (str(current_year),)
    ).fetchall()

    # For each tournament, get its leaderboard
    tournaments_with_stats = []
    for tournament in tournaments:
        # Get tournament stats (same query as individual tournament leaderboard)
        tournament_stats = get_tournament_leaderboard(tournament['id'])
        tournaments_with_stats.append({
            'tournament': tournament,
            'stats': tournament_stats
        })

    tournament_count = len(tournaments)

    return render_template('season_leaderboard.html',
                          current_year=current_year,
                          season_stats=season_stats,
                          tournaments=tournaments_with_stats,
                          tournament_count=tournament_count)
```

#### Helper Function: Get Tournament Leaderboard

```python
def get_tournament_leaderboard(tournament_id):
    """Get player standings for a specific tournament"""
    db = get_db_connection()

    players = db.execute(
        '''SELECT
            pr.id,
            pr.first_name,
            pr.last_name,
            COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) as wins,
            COUNT(DISTINCT m.id) as matches_played,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN m.id END) AS FLOAT) /
                NULLIF(COUNT(DISTINCT m.id), 0) * 100,
                1
            ) as win_rate
           FROM player_registry pr
           LEFT JOIN matches m ON (
               pr.id = m.player1_id OR
               pr.id = m.player2_id OR
               pr.id = m.player3_id OR
               pr.id = m.player4_id
           )
           LEFT JOIN rounds r ON m.round_id = r.id
           LEFT JOIN scores s ON (s.match_id = m.id AND s.player_id = pr.id)
           WHERE r.tournament_id = ? AND m.completed = 1
           GROUP BY pr.id, pr.first_name, pr.last_name
           HAVING matches_played > 0
           ORDER BY wins DESC, win_rate DESC, pr.last_name ASC''',
        (tournament_id,)
    ).fetchall()

    # Get tournament metadata
    tournament_info = db.execute(
        '''SELECT
            COUNT(DISTINCT r.id) as total_rounds
           FROM rounds r
           WHERE r.tournament_id = ?''',
        (tournament_id,)
    ).fetchone()

    return {
        'players': players,
        'rounds': tournament_info['total_rounds']
    }
```

#### New Route: Clear All Data

**Endpoint:** `POST /leaderboard/clear-all`

```python
@app.route('/leaderboard/clear-all', methods=['POST'])
def clear_all_data():
    """Clear all tournament and player data - complete reset"""
    db = get_db_connection()

    # Delete in correct order (foreign key constraints)
    db.execute('DELETE FROM scores')
    db.execute('DELETE FROM matches')
    db.execute('DELETE FROM rounds')
    db.execute('DELETE FROM tournaments')
    db.execute('DELETE FROM player_registry')

    # Reset auto-increment counters
    db.execute('''DELETE FROM sqlite_sequence
                  WHERE name IN ('tournaments', 'rounds', 'matches', 'scores', 'player_registry')''')

    db.commit()

    flash('All data cleared successfully! Starting fresh season.')
    return redirect(url_for('index'))
```

### Template: season_leaderboard.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Season {{ current_year }} Leaderboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .season-header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 8px;
            position: relative;
        }
        .season-meta {
            color: #666;
            font-size: 14px;
            margin: 5px 0;
        }
        .clear-data-btn {
            position: absolute;
            top: 20px;
            right: 20px;
        }
        .btn-danger {
            background: #dc3545;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .tournaments-section {
            margin-top: 40px;
        }
        .tournament-card {
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
        }
        .tournament-header {
            padding: 15px;
            background: #f8f9fa;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tournament-header:hover {
            background: #e9ecef;
        }
        .toggle-icon {
            font-size: 14px;
            transition: transform 0.2s;
        }
        .toggle-icon.expanded {
            transform: rotate(90deg);
        }
        .tournament-details {
            padding: 15px;
            display: none;
        }
        .tournament-details.show {
            display: block;
        }
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-left: auto;
        }
        .badge.active {
            background: #22c55e;
            color: white;
        }
        .badge.completed {
            background: #6b7280;
            color: white;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="season-header">
            <h1>Season {{ current_year }} Leaderboard</h1>
            <div class="season-meta">Jan 1 - Dec 31, {{ current_year }}</div>
            <div class="season-meta">{{ tournament_count }} Tournament{{ 's' if tournament_count != 1 else '' }}</div>

            {% if tournament_count > 0 %}
            <form method="POST"
                  action="{{ url_for('clear_all_data') }}"
                  onsubmit="return confirm('⚠️ WARNING: This will permanently delete ALL tournaments, matches, scores, and players from the database. This cannot be undone. Are you absolutely sure?')"
                  class="clear-data-btn">
                <button type="submit" class="btn-danger">Clear All Data</button>
            </form>
            {% endif %}
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="messages">
                    {% for message in messages %}
                        <div class="message">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Season-Wide Standings -->
        <h2>Season Standings</h2>
        {% if season_stats %}
        <table class="leaderboard">
            <thead>
                <tr>
                    <th class="rank">Rank</th>
                    <th>Player</th>
                    <th class="wins">Total Wins</th>
                    <th class="matches">Total Matches</th>
                    <th class="win-rate">Win %</th>
                </tr>
            </thead>
            <tbody>
                {% for player in season_stats %}
                <tr>
                    <td class="rank">{{ loop.index }}</td>
                    <td class="player-name">{{ player['first_name'] }} {{ player['last_name'] }}</td>
                    <td class="wins">{{ player['total_wins'] }}</td>
                    <td class="matches">{{ player['total_matches'] }}</td>
                    <td class="win-rate">
                        {% if player['win_rate'] %}
                            {{ player['win_rate'] }}%
                        {% else %}
                            -
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty-state">
            <p>No completed matches yet this season.</p>
        </div>
        {% endif %}

        <!-- Individual Tournaments -->
        {% if tournaments %}
        <div class="tournaments-section">
            <h2>Individual Tournaments</h2>
            {% for item in tournaments %}
            {% set tournament = item['tournament'] %}
            {% set stats = item['stats'] %}
            <div class="tournament-card">
                <div class="tournament-header" onclick="toggleTournament({{ tournament['id'] }})">
                    <span class="toggle-icon" id="icon-{{ tournament['id'] }}">▶</span>
                    <span><strong>{{ tournament['name'] }}</strong></span>
                    <span>{{ tournament['created_at'][:10] }}</span>
                    <span>{{ stats['rounds'] }} Round{{ 's' if stats['rounds'] != 1 else '' }}</span>
                    <span>{{ tournament['num_courts'] }} Court{{ 's' if tournament['num_courts'] != 1 else '' }}</span>
                    <span class="badge {{ 'active' if tournament['status'] == 'active' else 'completed' }}">
                        {{ tournament['status']|capitalize }}
                    </span>
                </div>
                <div id="tournament-{{ tournament['id'] }}" class="tournament-details">
                    {% if stats['players'] %}
                    <table class="leaderboard">
                        <thead>
                            <tr>
                                <th class="rank">Rank</th>
                                <th>Player</th>
                                <th class="wins">Wins</th>
                                <th class="matches">Matches</th>
                                <th class="win-rate">Win %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for player in stats['players'] %}
                            <tr>
                                <td class="rank">{{ loop.index }}</td>
                                <td class="player-name">{{ player['first_name'] }} {{ player['last_name'] }}</td>
                                <td class="wins">{{ player['wins'] }}</td>
                                <td class="matches">{{ player['matches_played'] }}</td>
                                <td class="win-rate">
                                    {% if player['win_rate'] %}
                                        {{ player['win_rate'] }}%
                                    {% else %}
                                        -
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty-state">No completed matches in this tournament.</div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="actions">
            <a href="/" class="btn btn-secondary">Back to Home</a>
        </div>
    </div>

    <script>
        function toggleTournament(tournamentId) {
            const details = document.getElementById('tournament-' + tournamentId);
            const icon = document.getElementById('icon-' + tournamentId);

            if (details.classList.contains('show')) {
                details.classList.remove('show');
                icon.classList.remove('expanded');
                icon.textContent = '▶';
            } else {
                details.classList.add('show');
                icon.classList.add('expanded');
                icon.textContent = '▼';
            }
        }
    </script>
</body>
</html>
```

### Home Page Template Update (index.html)

Add button after setup tournament section:

```html
{% if has_tournaments %}
<div class="actions">
    <a href="{{ url_for('season_leaderboard') }}" class="btn btn-secondary">
        View Season Leaderboard
    </a>
</div>
{% endif %}
```

### CSS Updates (style.css)

Add danger button styling:

```css
.btn-danger {
    background: #dc3545;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    transition: background 0.2s;
}

.btn-danger:hover {
    background: #c82333;
}
```

## Edge Cases

### 1. No Tournaments in Current Year
- Show empty state: "No tournaments yet this season"
- Provide link to create first tournament
- Hide "Clear All Data" button

### 2. No Completed Matches
- Show season standings table with empty state
- Individual tournaments show "No completed matches" when expanded

### 3. Player with 0 Matches
- Don't show in season leaderboard (HAVING clause filters)
- Prevents cluttering with inactive players

### 4. Active Tournament in Season View
- Show with "Active" badge in green
- Still expandable to view current standings
- Included in season-wide stats for completed matches

### 5. Clear All Data Confirmation
- Strong warning message mentioning irreversibility
- Mentions number of tournaments that will be deleted
- Warns if any active tournaments exist

### 6. Year Boundary
- On January 1, automatically shows new year
- Previous year's data not visible (could add year selector in future)
- Consider adding export feature before clearing

## Testing Checklist

- [ ] Home page shows leaderboard button when tournaments exist
- [ ] Home page hides button when no tournaments
- [ ] Season leaderboard shows correct current year
- [ ] Season stats aggregate correctly across multiple tournaments
- [ ] Individual tournaments are sorted by date DESC
- [ ] Tournament cards are collapsed by default
- [ ] Clicking tournament header toggles expand/collapse
- [ ] Icon rotates when expanding/collapsing
- [ ] Clear All Data shows confirmation dialog
- [ ] Clear All Data removes all records
- [ ] Redirect to home after clearing data
- [ ] Empty states show when no data
- [ ] Win rates calculate correctly in season view
- [ ] Active tournaments show with correct badge
- [ ] Players with 0 matches don't appear in standings

## Implementation Steps

1. Add `has_tournaments` check to home route
2. Add "View Season Leaderboard" button to index.html
3. Create `season_leaderboard` route with queries
4. Create `get_tournament_leaderboard` helper function
5. Create `clear_all_data` route
6. Create season_leaderboard.html template
7. Add JavaScript for toggle functionality
8. Add danger button CSS
9. Test complete flow
10. Test edge cases

## Benefits

- **Seasonal Tracking:** View year-long competition standings
- **Central Hub:** All tournament results accessible from one place
- **Comparison:** Easy to compare performance across tournaments
- **Data Management:** Clean slate for new season with Clear All Data
- **User-Friendly:** Collapsed/expandable keeps page manageable
- **Mobile-Friendly:** Works well on all screen sizes

## Related Files

- `app.py` - New routes: `season_leaderboard`, `clear_all_data`; helper: `get_tournament_leaderboard`; updated: `index`
- `templates/index.html` - Add season leaderboard button
- `templates/season_leaderboard.html` - New comprehensive template
- `static/css/style.css` - Add danger button styling
