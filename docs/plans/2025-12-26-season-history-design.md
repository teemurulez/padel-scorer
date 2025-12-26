# Season History View - Design Document

**Date:** December 26, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

Add a historical seasons view that displays all previous years' tournament data in one long scrollable page, with each season showing aggregated player statistics and expandable individual tournaments.

## Problem Statement

Currently, users can only view the current year's season leaderboard. There's no way to view data from previous years. Users need a way to:
1. Access historical season standings from past years
2. Compare performance across different years
3. Review individual tournament results from previous seasons
4. Maintain a complete archive of all seasons

## Proposed Solution

### Access & Navigation

**Link Location:**
- Season leaderboard page (`/leaderboard/season`)
- Button at bottom: "View Previous Seasons"
- Secondary button styling
- Only visible if previous seasons exist

**Visibility Logic:**
```python
has_previous_seasons = db.execute(
    '''SELECT COUNT(DISTINCT strftime('%Y', created_at)) as count
       FROM tournaments
       WHERE strftime('%Y', created_at) < strftime('%Y', 'now')'''
).fetchone()['count'] > 0
```

**When to show:**
- Hide link if no tournaments from previous years exist
- Show link if any tournaments exist with year < current year

### Page Structure

**URL:** `GET /leaderboard/history`

**Layout:**
```
┌──────────────────────────────────────┐
│ Season History                       │
│ All seasons from previous years      │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Season 2024                          │
│ Jan 1 - Dec 31, 2024 • 8 Tournaments│
├──────────────────────────────────────┤
│ Season Standings                     │
│ (Table: Rank, Player, Wins, etc.)   │
├──────────────────────────────────────┤
│ Individual Tournaments               │
│ ▶ Tournament A • 2024-06-15 • ...   │
│ ▶ Tournament B • 2024-05-20 • ...   │
└──────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────────────────────┐
│ Season 2023                          │
│ Jan 1 - Dec 31, 2023 • 6 Tournaments│
├──────────────────────────────────────┤
│ Season Standings                     │
├──────────────────────────────────────┤
│ Individual Tournaments               │
└──────────────────────────────────────┘

... (continues for all previous years)

[Back to Current Season] [Back to Home]
```

**Key Features:**
- Seasons sorted newest to oldest (2024, 2023, 2022...)
- Each season section has same structure as current season leaderboard
- Horizontal dividers separate seasons
- Expandable individual tournaments (collapsed by default)
- Gray/neutral header styling (vs current year's highlighted header)

### Data Scope

**Included:**
- All years where `year < current_year`
- Complete season statistics for each year
- All tournaments from those years
- Full player leaderboards per season and tournament

**Excluded:**
- Current year (already shown on main season leaderboard)
- Future years (shouldn't exist)

**Example:** If current year is 2025, show 2024, 2023, 2022, etc.

## Technical Design

### New Route: Season History

**Endpoint:** `GET /leaderboard/history`

```python
@app.route('/leaderboard/history')
def season_history():
    """Show all previous seasons (excluding current year)"""
    from datetime import datetime
    db = get_db_connection()

    current_year = datetime.now().year

    # Get all years with tournaments (excluding current year)
    years = db.execute(
        '''SELECT DISTINCT strftime('%Y', created_at) as year
           FROM tournaments
           WHERE strftime('%Y', created_at) < ?
           ORDER BY year DESC''',
        (str(current_year),)
    ).fetchall()

    # For each year, get season stats and tournaments
    seasons = []
    for year_row in years:
        year = year_row['year']

        # Get season-wide stats for this year (same query as season_leaderboard)
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
            (year,)
        ).fetchall()

        # Get tournaments for this year
        tournaments = db.execute(
            '''SELECT * FROM tournaments
               WHERE strftime('%Y', created_at) = ?
               ORDER BY created_at DESC''',
            (year,)
        ).fetchall()

        # Get leaderboard for each tournament (reuse helper function)
        tournaments_with_stats = []
        for tournament in tournaments:
            stats = get_tournament_leaderboard(tournament['id'])
            tournaments_with_stats.append({
                'tournament': tournament,
                'stats': stats
            })

        seasons.append({
            'year': year,
            'season_stats': season_stats,
            'tournaments': tournaments_with_stats,
            'tournament_count': len(tournaments)
        })

    return render_template('season_history.html', seasons=seasons)
```

### Update: Season Leaderboard Route

Add check for previous seasons:

```python
@app.route('/leaderboard/season')
def season_leaderboard():
    # ... existing code ...

    # Check if there are previous seasons
    has_previous_seasons = db.execute(
        '''SELECT COUNT(DISTINCT strftime('%Y', created_at)) as count
           FROM tournaments
           WHERE strftime('%Y', created_at) < ?''',
        (str(current_year),)
    ).fetchone()['count'] > 0

    return render_template('season_leaderboard.html',
                          current_year=current_year,
                          season_stats=season_stats,
                          tournaments=tournaments_with_stats,
                          tournament_count=tournament_count,
                          has_previous_seasons=has_previous_seasons)
```

### Template: season_history.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Season History</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .page-header {
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 8px;
        }
        .page-header h1 {
            margin: 0 0 10px 0;
        }
        .info-text {
            color: #666;
            font-size: 16px;
        }
        .season-section {
            margin-bottom: 60px;
            padding: 30px;
            background: #fafafa;
            border-radius: 8px;
        }
        .season-header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #ddd;
        }
        .season-header h2 {
            margin: 0 0 10px 0;
            color: #2c3e50;
        }
        .season-meta {
            color: #666;
            font-size: 14px;
            margin: 5px 0;
        }
        .season-divider {
            margin: 60px 0;
            border: none;
            border-top: 2px solid #ddd;
        }
        /* Reuse tournament card styles from season_leaderboard.html */
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
            flex-wrap: wrap;
        }
        .tournament-header:hover {
            background: #e9ecef;
        }
        .toggle-icon {
            font-size: 14px;
            transition: transform 0.2s;
            min-width: 15px;
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
        <div class="page-header">
            <h1>Season History</h1>
            <p class="info-text">All seasons from previous years</p>
        </div>

        {% if seasons %}
        {% for season in seasons %}
        <div class="season-section">
            <div class="season-header">
                <h2>Season {{ season['year'] }}</h2>
                <div class="season-meta">Jan 1 - Dec 31, {{ season['year'] }}</div>
                <div class="season-meta">{{ season['tournament_count'] }} Tournament{{ 's' if season['tournament_count'] != 1 else '' }}</div>
            </div>

            <!-- Season Standings -->
            <h3>Season Standings</h3>
            {% if season['season_stats'] %}
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
                    {% for player in season['season_stats'] %}
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
                <p>No completed matches in this season.</p>
            </div>
            {% endif %}

            <!-- Individual Tournaments -->
            {% if season['tournaments'] %}
            <h3 style="margin-top: 40px;">Individual Tournaments</h3>
            {% for item in season['tournaments'] %}
            {% set tournament = item['tournament'] %}
            {% set stats = item['stats'] %}
            <div class="tournament-card">
                <div class="tournament-header" onclick="toggleTournament({{ season['year'] }}, {{ tournament['id'] }})">
                    <span class="toggle-icon" id="icon-{{ season['year'] }}-{{ tournament['id'] }}">▶</span>
                    <span><strong>{{ tournament['name'] }}</strong></span>
                    <span>{{ tournament['created_at'][:10] }}</span>
                    <span>{{ stats['rounds'] }} Round{{ 's' if stats['rounds'] != 1 else '' }}</span>
                    <span>{{ tournament['num_courts'] }} Court{{ 's' if tournament['num_courts'] != 1 else '' }}</span>
                    <span class="badge {{ 'active' if tournament['status'] == 'active' else 'completed' }}">
                        {{ tournament['status']|capitalize }}
                    </span>
                </div>
                <div id="tournament-{{ season['year'] }}-{{ tournament['id'] }}" class="tournament-details">
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
            {% endif %}
        </div>

        {% if not loop.last %}
        <hr class="season-divider">
        {% endif %}
        {% endfor %}
        {% else %}
        <div class="empty-state">
            <p>No previous seasons found.</p>
        </div>
        {% endif %}

        <div class="actions">
            <a href="{{ url_for('season_leaderboard') }}" class="btn btn-secondary">
                Back to Current Season
            </a>
            <a href="/" class="btn btn-secondary">Back to Home</a>
        </div>
    </div>

    <script>
        function toggleTournament(year, tournamentId) {
            const details = document.getElementById('tournament-' + year + '-' + tournamentId);
            const icon = document.getElementById('icon-' + year + '-' + tournamentId);

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

### Update: season_leaderboard.html

Add "View Previous Seasons" button:

```html
<div class="actions">
    {% if has_previous_seasons %}
    <a href="{{ url_for('season_history') }}" class="btn btn-secondary">
        View Previous Seasons
    </a>
    {% endif %}
    <a href="/" class="btn btn-secondary">Back to Home</a>
</div>
```

## Edge Cases

### 1. No Previous Seasons
- "View Previous Seasons" link hidden on season leaderboard
- If user somehow accesses `/leaderboard/history`, show empty state

### 2. Single Previous Year
- Works same as multiple years
- Still shows proper formatting with single season section

### 3. Many Years (10+)
- Page may be long but remains scrollable
- Each season remains independently expandable
- Performance should be acceptable (database queries are efficient)

### 4. Empty Season (No Completed Matches)
- Show season header and metadata
- Display empty state: "No completed matches in this season"
- Still show tournament list (even if no completed matches)

### 5. JavaScript Toggle
- Use unique IDs with year prefix: `tournament-2024-1`, `tournament-2023-5`
- Prevents ID collisions between seasons
- Toggle function includes year parameter

## Testing Checklist

- [ ] "View Previous Seasons" link appears on season leaderboard when previous seasons exist
- [ ] Link hidden when no previous seasons exist
- [ ] History page shows all years < current year
- [ ] Seasons sorted newest to oldest
- [ ] Each season shows correct aggregated stats
- [ ] Individual tournaments are collapsed by default
- [ ] Clicking tournament header toggles expand/collapse
- [ ] No ID collisions between different years' tournaments
- [ ] Empty states show when no data
- [ ] Navigation buttons work correctly
- [ ] Page handles 1, 5, 10+ previous years gracefully

## Implementation Steps

1. Update `season_leaderboard` route to check for previous seasons
2. Add "View Previous Seasons" button to season_leaderboard.html
3. Create `season_history` route with year iteration logic
4. Create season_history.html template
5. Update JavaScript toggle function to handle year-prefixed IDs
6. Test with multiple previous years
7. Test edge cases (no previous years, single year, empty data)

## Benefits

- **Complete Archive:** Access all historical season data
- **Comparison:** Compare performance across different years
- **Single Page:** All history in one scrollable view
- **Consistent UI:** Same structure as current season leaderboard
- **Expandable Detail:** Drill into any tournament from any year
- **Clean Navigation:** Only show when relevant (previous seasons exist)

## Related Files

- `app.py` - New route: `season_history`; updated: `season_leaderboard`
- `templates/season_history.html` - New comprehensive template
- `templates/season_leaderboard.html` - Add link to history view
