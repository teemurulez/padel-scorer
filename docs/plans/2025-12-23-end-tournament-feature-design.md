# End Tournament Feature - Design Document

**Date:** December 23, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

Add an "End Tournament" button that allows users to complete a tournament after any round (since round count is not predetermined), with confirmation and a comprehensive final leaderboard showing tournament statistics.

## Problem Statement

The current system requires tournaments to continue indefinitely or be manually abandoned. Users need a clean way to formally end a tournament after the desired number of rounds, view final standings, and preserve the tournament results while keeping everything editable in case of mistakes.

## Proposed Solution

### Button Placement

**Location:** Both court selection and round overview screens

**Visibility conditions:**
- All matches in the current round are completed
- Appears alongside "Start Next Round" button
- Distinguished by warning/secondary styling

**Screens:**
- Court selection (`court_selection.html`)
- Round overview (`active_round.html`)

### User Flow

1. User completes all matches in a round
2. Two options appear:
   - "Start Next Round" (continue tournament)
   - "End Tournament" (finish tournament)
3. Click "End Tournament"
4. JavaScript confirmation dialog: "Are you sure you want to end this tournament? You can still view and edit results after ending."
5. If confirmed → POST to `/tournament/<id>/end`
6. Tournament status updated to "completed"
7. Redirect to comprehensive leaderboard

### Post-Tournament Behavior

**Tournament Status:** `completed`

**Functionality preserved:**
- Can view all rounds and matches
- Can edit match scores
- Can view leaderboard
- Cannot start new rounds

**This allows fixing mistakes while preventing accidental round creation.**

## Technical Design

### New Route

**Endpoint:** `POST /tournament/<int:tournament_id>/end`

```python
@app.route('/tournament/<int:tournament_id>/end', methods=['POST'])
def end_tournament(tournament_id):
    """
    End tournament and mark as completed.

    Updates tournament status to 'completed' and redirects to final leaderboard.
    Tournament remains editable for corrections.
    """
    db = get_db_connection()

    # Verify tournament exists
    tournament = db.execute(
        'SELECT * FROM tournaments WHERE id = ?',
        (tournament_id,)
    ).fetchone()

    if not tournament:
        flash('Tournament not found')
        return redirect(url_for('index'))

    # Update status to completed
    db.execute(
        'UPDATE tournaments SET status = ? WHERE id = ?',
        ('completed', tournament_id)
    )
    db.commit()

    flash('Tournament ended successfully!')
    return redirect(url_for('leaderboard', tournament_id=tournament_id))
```

### Updated Route: Leaderboard

**Issue:** Current leaderboard uses Phase 2 schema (`players` table with `total_points`)

**Solution:** Update to Phase 3 schema using `player_registry` and calculate stats from `scores` table

**Updated Query:**
```sql
SELECT
    pr.id,
    pr.first_name,
    pr.last_name,
    COUNT(DISTINCT CASE WHEN s.points > 0 THEN s.match_id END) as wins,
    COUNT(DISTINCT s.match_id) as matches_played,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN s.points > 0 THEN s.match_id END) AS FLOAT) /
        NULLIF(COUNT(DISTINCT s.match_id), 0) * 100,
        1
    ) as win_rate
FROM player_registry pr
LEFT JOIN scores s ON pr.id = s.player_id
LEFT JOIN matches m ON s.match_id = m.id
LEFT JOIN rounds r ON m.round_id = r.id
WHERE r.tournament_id = ?
GROUP BY pr.id, pr.first_name, pr.last_name
ORDER BY wins DESC, win_rate DESC, pr.last_name ASC
```

**Additional tournament metadata:**
```sql
SELECT
    t.name,
    t.created_at,
    t.num_courts,
    COUNT(DISTINCT r.id) as total_rounds
FROM tournaments t
LEFT JOIN rounds r ON t.id = r.tournament_id
WHERE t.id = ?
GROUP BY t.id, t.name, t.created_at, t.num_courts
```

### Template Updates

#### 1. court_selection.html

Add "End Tournament" button in the actions section:

```html
<div class="actions">
    {% if all_completed %}
    <form action="{{ url_for('start_round', tournament_id=tournament.id) }}"
          method="POST"
          style="display: inline;">
        <button type="submit" class="btn btn-primary">Start Next Round</button>
    </form>

    <form action="{{ url_for('end_tournament', tournament_id=tournament.id) }}"
          method="POST"
          onsubmit="return confirm('Are you sure you want to end this tournament? You can still view and edit results after ending.')"
          style="display: inline;">
        <button type="submit" class="btn btn-warning">End Tournament</button>
    </form>
    {% endif %}
    <a href="/" class="btn btn-secondary">Back to Home</a>
</div>
```

#### 2. active_round.html

Add same "End Tournament" button in round-actions section:

```html
<div class="round-actions">
    <a href="{{ url_for('leaderboard', tournament_id=tournament_id) }}"
       class="btn-secondary">View Leaderboard</a>

    {% if all_completed %}
    <a href="{{ url_for('start_round', tournament_id=tournament_id) }}"
       class="btn-primary">Start Next Round</a>

    <form action="{{ url_for('end_tournament', tournament_id=tournament_id) }}"
          method="POST"
          onsubmit="return confirm('Are you sure you want to end this tournament? You can still view and edit results after ending.')"
          style="display: inline;">
        <button type="submit" class="btn btn-warning">End Tournament</button>
    </form>
    {% endif %}
</div>
```

#### 3. leaderboard.html

Update to show comprehensive tournament summary:

**Tournament Header:**
- Tournament name (large, prominent)
- Status badge ("Active" or "Completed")
- Date (created_at)
- Total rounds played
- Number of courts used

**Player Standings Table:**

| Rank | Player Name | Wins | Matches Played | Win Rate % |
|------|-------------|------|----------------|------------|
| 1    | John Smith  | 8    | 10             | 80.0%      |
| 2    | Jane Doe    | 7    | 10             | 70.0%      |
| ...  | ...         | ...  | ...            | ...        |

**Actions:**
- "Back to Tournament" (if active)
- "Back to Home"
- "Start New Tournament"

### Preventing New Rounds on Completed Tournaments

**Update both templates to check tournament status:**

```html
{% if all_completed and tournament.status != 'completed' %}
    <!-- Show "Start Next Round" button -->
{% endif %}

<!-- Always show "End Tournament" if matches completed and not already ended -->
{% if all_completed and tournament.status != 'completed' %}
    <!-- Show "End Tournament" button -->
{% endif %}
```

## CSS Styling

**Button styling for "End Tournament":**

```css
.btn-warning {
    background-color: #f59e0b;
    color: white;
    border: 2px solid #d97706;
}

.btn-warning:hover {
    background-color: #d97706;
}
```

**Tournament status badge:**

```css
.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: bold;
}

.status-badge.active {
    background-color: #22c55e;
    color: white;
}

.status-badge.completed {
    background-color: #6b7280;
    color: white;
}
```

## Edge Cases

### 1. Tournament Already Completed
- Button should not appear if tournament status is already "completed"
- Template conditionals prevent this

### 2. No Matches Played
- User ends tournament with 0 completed matches
- Leaderboard shows empty state: "No matches played yet"

### 3. Mid-Round Tournament End
- User can only end tournament when all matches in current round are complete
- "End Tournament" button only appears when `all_completed == True`

### 4. Accidental Click
- JavaScript confirmation prevents accidental ending
- User can still edit results after ending

### 5. Completed Tournament Navigation
- Landing on a completed tournament redirects to leaderboard (not round view)
- Update `active_tournament` route to check status

## Testing Checklist

- [ ] "End Tournament" button appears on court selection when all matches complete
- [ ] "End Tournament" button appears on active_round when all matches complete
- [ ] Confirmation dialog shows before ending
- [ ] Tournament status updates to "completed"
- [ ] Redirects to comprehensive leaderboard
- [ ] Leaderboard shows correct Phase 3 player stats
- [ ] Leaderboard shows tournament metadata (name, date, rounds, courts)
- [ ] Can still view rounds after ending
- [ ] Can still edit scores after ending
- [ ] Cannot start new rounds after ending
- [ ] "End Tournament" button hidden after tournament ended

## Implementation Steps

1. Create `end_tournament` route (POST handler)
2. Update `leaderboard` route with Phase 3 query
3. Add tournament metadata query to leaderboard
4. Update `leaderboard.html` template with comprehensive layout
5. Add "End Tournament" button to `court_selection.html`
6. Add "End Tournament" button to `active_round.html`
7. Add CSS for warning button and status badges
8. Update `active_tournament` route to handle completed tournaments
9. Test complete flow

## Benefits

- **Flexibility:** End tournament after any number of rounds
- **Data preservation:** All results remain accessible and editable
- **Clear finality:** Explicit tournament completion with confirmation
- **Comprehensive reporting:** Final leaderboard shows complete tournament summary
- **Error tolerance:** Can still fix mistakes after ending

## Related Files

- `app.py` - New route: `end_tournament`, updated: `leaderboard`
- `templates/court_selection.html` - Add end button
- `templates/active_round.html` - Add end button
- `templates/leaderboard.html` - Comprehensive update
- `static/css/style.css` - Warning button and status badge styles
