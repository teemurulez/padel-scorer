# Consistent Main Page Design

> **Date:** 2026-01-31
> **Status:** Approved

## Problem

Currently, the main page (`/`) auto-redirects to the tournament page when exactly one active tournament exists. This creates unpredictable navigation - users don't have a consistent "home base" and the back button behavior is confusing.

## Solution

The main page always renders content - never redirects. Users consciously navigate to the tournament via a button.

## Design

### Core Behavior

```
/ (index)
├── Has active tournament(s)? → Show main page with tournament info + "Go" button
├── Has setup tournament(s) only? → Show main page with "coming soon" info
└── No tournaments? → Show main page with "no tournament" state
```

### Layout Structure

**Header** (unchanged)
- Logo + "Padel Paroni" / Season name

**Primary Section: Active Tournament Card**
```
┌─────────────────────────────────────┐
│  🟢 Käynnissä                       │
│  [Tournament Name]                  │
│  Kierros X/Y  •  N pelaajaa         │
│                                     │
│  [  Siirry turnaukseen  ]  (gold)   │
└─────────────────────────────────────┘
```

**Secondary Section: Other Tournaments** (muted, informational)
```
Muut turnaukset
┌─────────────────────────────────────┐
│  ⏳ Valmistelussa: [Name]           │
└─────────────────────────────────────┘
```

**Footer Actions**
- "Kauden tulokset" button (prominence varies by state)

### State Variations

| State | Primary Card | "Kauden tulokset" |
|-------|--------------|-------------------|
| Active tournament exists | Tournament info + "Siirry turnaukseen" | Secondary (gray) |
| Only setup tournaments | "Turnaus valmistelussa" info | **Primary (gold)** |
| No tournaments | "Ei aktiivista turnausta" | **Primary (gold)** |

### Data for Active Tournament Card

- Tournament name
- Current round number
- Total rounds (count of completed + 1, or "?" if not determinable)
- Player count (from tournament_players)

## Implementation

### Files to Modify

1. **`app.py`** - `index()` route
   - Remove auto-redirect logic (lines 608-610)
   - Query: current round number, player count
   - Always render template

2. **`templates/tournament_selection.html`** → Refactor to `home.html`
   - Unified template for all states
   - Active tournament card with round/player info
   - Muted section for setup tournaments
   - Dynamic button prominence

3. **`templates/no_active_tournament.html`** → Remove
   - Logic merged into unified home template

### No Database Changes

All required data already available in existing tables.
