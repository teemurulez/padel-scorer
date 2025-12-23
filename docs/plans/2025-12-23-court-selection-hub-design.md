# Court Selection as Central Hub - Design Document

**Date:** December 23, 2025
**Status:** Approved
**Implementation:** Pending

## Overview

Make the court selection screen the central hub during a round, where users can see all courts, their completion status, and enter/edit scores for multiple courts in sequence.

## Problem Statement

Current flow redirects to the active round view after submitting scores, which shows a list of all matches. This requires additional navigation to enter scores for multiple courts. Users want a more efficient workflow where they can quickly move between courts from a single overview screen.

## Proposed Solution

### Navigation Flow

**Current:**
```
Court selection → Confirm teams → Enter score → Active round view
```

**New:**
```
Court selection → Confirm teams → Enter score → Court selection (hub)
                ↑_______________________________________________|
```

Court selection becomes the central hub where users return after each score submission.

## Design Details

### 1. Visual Indicators on Court Cards

**Uncompleted Match Card:**
- Standard appearance
- Button text: "Go to Court N"
- No completion indicator

**Completed Match Card:**
- Green checkmark (✓) badge in top-right corner
- "Winner: Team X" text displayed below team names
- Button text changes to "Edit Score"
- Optional: Light green background tint
- Card remains fully interactive (can edit score)

### 2. Technical Implementation

#### Route Changes

**score_entry route (app.py:660-662):**
```python
# Change from:
return redirect(url_for('active_round',
                       tournament_id=match['tournament_id'],
                       round_id=match['round_id']))

# To:
return redirect(url_for('court_selection',
                       tournament_id=match['tournament_id'],
                       round_id=match['round_id']))
```

**court_selection route:**
- No backend changes needed
- Already fetches matches with `completed` flag and `winning_team` data
- Template will handle conditional rendering

#### Template Changes (court_selection.html)

**Add conditional rendering for match cards:**
```html
<div class="match-card {% if match['completed'] %}completed{% endif %}">
    {% if match['completed'] %}
        <span class="completed-badge">✓</span>
    {% endif %}

    <div class="court-number">Court {{ match['court_number'] }}</div>

    <!-- Team display (unchanged) -->
    <div class="teams">...</div>

    {% if match['completed'] %}
        <p class="winner-text">Winner: Team {{ match['winning_team'] }}</p>
        <a href="..." class="btn-secondary">Edit Score</a>
    {% else %}
        <a href="..." class="btn-primary">Go to Court {{ match['court_number'] }}</a>
    {% endif %}
</div>
```

**CSS additions:**
```css
.completed-badge {
    /* Green checkmark styling */
    color: #22c55e;
    font-size: 1.5em;
    position: absolute;
    top: 10px;
    right: 10px;
}

.winner-text {
    /* Winner announcement styling */
    font-weight: bold;
    color: #22c55e;
    margin: 10px 0;
}

.match-card.completed {
    /* Optional: light green background tint */
    background-color: #f0fdf4;
}
```

### 3. Edge Cases

#### All Matches Completed
- Court selection still shows all matches with edit capability
- Add "Start Next Round" button at bottom
- Shows completion status for all courts

#### Editing Completed Matches
- Click "Edit Score" on completed match
- Navigate directly to score_entry (skip confirm_match)
- Score entry form can pre-select current winner (future enhancement)
- Updating score updates existing database records

#### Navigation Consistency
- Add "Back to Court Selection" button on score_entry page
- Allows canceling without submitting and returning to overview

### 4. Additional Features

#### Round Progress Indicator
- Display "X/Y matches completed" at top of court selection
- Helps users track progress at a glance

#### Flash Messages
- After score submission: "Score recorded for Court N!"
- Confirms which court was just completed
- User-friendly feedback

## Testing Checklist

- [ ] Submit score → redirects to court selection
- [ ] Completed match shows checkmark and winner
- [ ] Completed match shows "Edit Score" button
- [ ] Can click "Edit Score" on completed match
- [ ] Score entry allows updating completed match
- [ ] Can enter scores for multiple courts in sequence
- [ ] All matches completed → shows appropriate next action
- [ ] Flash messages appear after score submission
- [ ] Visual styling matches design mockup

## Implementation Steps

1. Update score_entry redirect destination
2. Add conditional rendering to court_selection.html
3. Add CSS for completion indicators
4. Add round progress indicator
5. Test flow with multiple courts
6. Verify editing completed matches works

## Benefits

- **Efficiency:** Faster workflow for entering multiple scores
- **Clarity:** See all court statuses at a glance
- **Flexibility:** Easy to edit scores without deep navigation
- **Progress tracking:** Clear visual feedback on completion status
- **User experience:** Single hub for all round management

## Related Files

- `app.py` - Route changes (score_entry, court_selection)
- `templates/court_selection.html` - UI updates
- `static/css/style.css` - New completion styling
