# Admin Player Points Management - Design Document

**Date:** 2026-01-10
**Status:** Approved
**Priority:** Post-MVP (Admin improvement)

---

## Overview

Add a new "Pelaajat" (Players) tab to the admin dashboard where admins can view and edit player season points. Points are calculated automatically from match wins, but admins can override/adjust them manually.

---

## Requirements

1. New "Pelaajat" tab in admin panel (alongside Kaudet/Seasons)
2. Show all players with their current season total points
3. "Muokkaa" (Edit) button per player opens a form
4. Admin can set new point total (system calculates adjustment)
5. Automatic points from wins remain intact; adjustment stored separately

---

## User Interface

### Players Tab Layout

```
[Kaudet] [Pelaajat]
─────────────────────────────────────────
Kausi: Kevät 2026

| Pelaaja          | Pisteet | Toiminnot    |
|------------------|---------|--------------|
| Matti Virtanen   | 12      | [Muokkaa]    |
| Anna Korhonen    | 10      | [Muokkaa]    |
| Pekka Nieminen   | 8       | [Muokkaa]    |
```

### Edit Form (opens on button click)

```
┌─────────────────────────────────────┐
│ Muokkaa pisteitä: Matti Virtanen    │
│                                     │
│ Automaattiset pisteet: 10           │
│ Nykyinen korjaus: +2                │
│ Yhteensä: 12                        │
│                                     │
│ Uudet kokonaispisteet: [____]       │
│                                     │
│ [Tallenna]  [Peruuta]               │
└─────────────────────────────────────┘
```

---

## Data Model

### New Table: player_points_adjustment

```sql
CREATE TABLE IF NOT EXISTS player_points_adjustment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    adjustment INTEGER DEFAULT 0,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    UNIQUE(player_id, season_id)
);
```

### Points Calculation Logic

```
Total Season Points = Automatic Points (from wins) + Adjustment
```

**Automatic points query:**
```sql
SELECT player_id, SUM(total_points) as auto_points
FROM tournament_players tp
JOIN tournaments t ON tp.tournament_id = t.id
WHERE t.season_id = :season_id
  AND t.status IN ('completed', 'archived')
GROUP BY player_id
```

**Final points with adjustment:**
```sql
SELECT
    pr.id,
    pr.first_name,
    pr.last_name,
    COALESCE(auto.auto_points, 0) as auto_points,
    COALESCE(adj.adjustment, 0) as adjustment,
    COALESCE(auto.auto_points, 0) + COALESCE(adj.adjustment, 0) as total_points
FROM player_registry pr
LEFT JOIN (
    SELECT player_id, SUM(total_points) as auto_points
    FROM tournament_players tp
    JOIN tournaments t ON tp.tournament_id = t.id
    WHERE t.season_id = :season_id
      AND t.status IN ('completed', 'archived')
    GROUP BY player_id
) auto ON pr.id = auto.player_id
LEFT JOIN player_points_adjustment adj
    ON pr.id = adj.player_id AND adj.season_id = :season_id
WHERE auto.auto_points > 0 OR adj.adjustment IS NOT NULL
ORDER BY total_points DESC
```

---

## Routes

### GET /admin/players

**Purpose:** Display players tab with season points

**Logic:**
1. Get current season
2. Query all players with points (auto + adjustment)
3. Sort by total points descending
4. Render admin_dashboard.html with players tab active

### POST /admin/players/<player_id>/edit

**Purpose:** Save point adjustment

**Request body:**
- `new_total_points` (integer)

**Logic:**
1. Get player's current auto_points
2. Calculate: `adjustment = new_total_points - auto_points`
3. INSERT or UPDATE player_points_adjustment
4. Flash success message
5. Redirect to /admin/players

---

## Implementation Steps

### Step 1: Database Migration
- Add `player_points_adjustment` table in database.py
- Add migration in app.py startup

### Step 2: Backend Routes
- Add `admin_players()` route for GET /admin/players
- Add `admin_edit_player_points()` route for POST

### Step 3: Template Updates
- Add "Pelaajat" tab to admin_dashboard.html
- Add players list table
- Add edit form (inline or modal)
- Add JavaScript for form toggle

### Step 4: Testing
- Test points display
- Test edit functionality
- Test with no adjustments (pure auto)
- Test adjustment persistence

---

## Files to Modify

- `database.py` - Add new table
- `app.py` - Add routes, add migration
- `templates/admin_dashboard.html` - Add tab and UI
- `static/css/admin.css` - Styling if needed

---

## Future Enhancements (Out of Scope)

- Per-tournament point editing
- Adjustment history/audit log
- Bulk point import/export
- Point decay over time

---

## Notes

- This feature is NOT MVP-critical
- Designed for post-tournament corrections
- Keeps automatic calculation intact
- Clear separation between auto and manual points
