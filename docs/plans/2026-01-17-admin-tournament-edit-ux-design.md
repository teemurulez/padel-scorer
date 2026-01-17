# Admin Tournament Edit UX Design

**Date:** 2026-01-17
**Status:** Draft

## Problem Statement

The admin tournament editing experience has usability challenges:

1. **Too many things on screen** - Seasons, tournaments, and forms all visible at once
2. **Edit form is confusing** - Inline edit form cramped inside table row
3. **Workflow is unclear** - Not obvious what steps to take
4. **Pairings get lost** - Player list changes reset carefully arranged pairings
5. **No visibility of changes** - Hard to see what changed since last edit
6. **Typo risk** - Can't tell if a player name is a typo or genuinely new player

## User Workflow Context

- Tournaments are edited **multiple times over several days** before starting
- Player list changes frequently as people confirm/cancel
- Players are entered by **pasting from Excel** (bulk text)
- Pairings: Algorithm generates initial, user makes **manual adjustments**
- Rule: `courts × 4 = players` (always, no exceptions)

## Design Overview

### 1. Full-Screen Edit Mode

Replace inline table row editing with dedicated full-screen edit view.

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Takaisin                    Muokkaa turnausta                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Perjantai-illan padel                          [Valmistelu]    │
│  3 kenttää · 12 pelaajaa · Luotu 15.1.2026                      │
│                                                                 │
├────────────────────┬────────────────────────────────────────────┤
│                    │                                            │
│  PELAAJAT          │  KIERROS 1 - PARIT                         │
│  ────────────      │  ─────────────────                         │
│                    │                                            │
│  ┌──────────────┐  │  ┌─ Kenttä 1 ─┐  ┌─ Kenttä 2 ─┐           │
│  │ Matti V.     │  │  │ T1  │ T2   │  │ T1  │ T2   │           │
│  │ Anna K.      │  │  │Matti│Anna  │  │Liisa│Mikko │           │
│  │ Pekka S.     │  │  │Pekka│Sanna │  │Ville│Jussi │           │
│  │ Sanna L.     │  │  └─────┴──────┘  └─────┴──────┘           │
│  │ ...          │  │                                            │
│  └──────────────┘  │  ┌─ Kenttä 3 ─┐                            │
│                    │  │ T1  │ T2   │                            │
│  [Muokkaa]         │  │Kaisa│ Juha │                            │
│                    │  │Tiina│ Antti│                            │
│                    │  └─────┴──────┘                            │
│                    │                                            │
│                    │  [Luo uudet parit]                         │
│                    │                                            │
├────────────────────┴────────────────────────────────────────────┤
│  [Tallenna]                              [Aloita turnaus]       │
└─────────────────────────────────────────────────────────────────┘
```

**Layout:**
- Two-column: Players on left, pairings on right
- Both visible simultaneously
- Pairings always visible (no "Preview" button needed)
- Clear action bar at bottom

### 2. Player Entry with Validation

Support paste-from-Excel workflow with post-paste validation.

**Step 1: Paste names (textarea)**
```
┌─────────────────────────────────────────────────────────────────┐
│ Pelaajat (12 vaaditaan 3 kentälle)                              │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Matti Virtanen                                              │ │
│ │ Anna Korhonen                                               │ │
│ │ Matti Meikalainen                                           │ │
│ │ Liisa Nieminen                                              │ │
│ │ ...                                                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ [Tarkista nimet]                                                │
└─────────────────────────────────────────────────────────────────┘
```

**Step 2: Validation results**
```
┌─────────────────────────────────────────────────────────────────┐
│ Pelaajat - Tarkistus                                            │
│                                                                 │
│  ✓ Matti Virtanen                                               │
│  ✓ Anna Korhonen                                                │
│  ⚠ Matti Meikalainen       → Matti Meikäläinen? [Kyllä] [Ei]   │
│  ★ Liisa Nieminen          (uusi pelaaja)                       │
│                                                                 │
│  10 tunnettua · 1 tarkistettava · 1 uusi                        │
│                                                                 │
│ [Takaisin muokkaukseen]                    [Hyväksy ja jatka]   │
└─────────────────────────────────────────────────────────────────┘
```

**Validation indicators:**
- ✓ **Green** = Exact match in player registry
- ⚠ **Yellow** = No exact match, similar name found (fuzzy match suggestion)
- ★ **Blue** = Confirmed as new player (user clicked "Ei" on suggestion)

**Fuzzy matching:** Use simple algorithm (Levenshtein distance or similar) to suggest potential matches for unrecognized names.

### 3. Pairings Preservation

Identity-based pairings that survive player list changes.

**When players change (same court count):**
```
┌─────────────────────────────────────────────────────────────────┐
│ Kierros 1 - Kenttäjaot                                          │
│                                                                 │
│ ┌─── Kenttä 1 ───┐    ┌─── Kenttä 2 ───┐                       │
│ │ Tiimi 1│Tiimi 2│    │ Tiimi 1│Tiimi 2│                       │
│ │ Matti  │ Anna  │    │ Liisa  │ [TYHJÄ]│ ← player removed     │
│ │ Pekka  │ Sanna │    │ Mikko  │ Jussi  │                       │
│ └────────┴───────┘    └────────┴────────┘                       │
│                                                                 │
│ ┌─ Sijoittamattomat pelaajat ─────────────────────────────────┐ │
│ │  Ville Uusi    Kaisa Uusi     ← new players                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Klikkaa pelaajaa, sitten tyhjää paikkaa sijoittaaksesi          │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Player removed → Slot shows `[TYHJÄ]`, structure preserved
- Player added → Goes to "Sijoittamattomat" pool
- Click unassigned player, then empty slot to assign
- Click two assigned players to swap

**Preservation logic:**

| Change | Pairings behavior |
|--------|-------------------|
| Same players, same courts | Fully preserved |
| Different players, same courts | Preserved with empty slots + unassigned pool |
| Court count changes | Regenerate (try to keep existing pairs together) |

### 4. Court/Player Count Mismatch Handling

When player count doesn't match `courts × 4`:

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠ Pelaajamäärä ei täsmää                                        │
│                                                                 │
│ 3 kenttää vaatii 12 pelaajaa, nyt 10.                           │
│                                                                 │
│ [Lisää 2 pelaajaa]  tai  [Vaihda 2 kenttään]                    │
└─────────────────────────────────────────────────────────────────┘
```

- System detects mismatch after player validation
- User chooses: add more players OR reduce court count
- Reducing courts triggers pairing regeneration (structure change)
- Adding players puts them in unassigned pool

### 5. Change History

Show what changed since last edit session.

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌─ Viimeisimmät muutokset (15.1.2026 klo 14:30) ─────────────┐  │
│ │                                                            │  │
│ │  Pelaajat:                                                 │  │
│ │   + Ville Virtanen (lisätty)                               │  │
│ │   − Kaisa Korhonen (poistettu)                             │  │
│ │   ~ Matti Meikalainen → Matti Meikäläinen (korjattu)       │  │
│ │                                                            │  │
│ │  Parit:                                                    │  │
│ │   Kenttä 2: Matti siirretty Tiimi 1 → Tiimi 2              │  │
│ │                                                            │  │
│ │                                         [Piilota historia] │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Tracked changes:**
- Player additions
- Player removals
- Name corrections (typo fixes)
- Pairing changes (swaps, reassignments)
- Timestamp of each edit session

**Storage:** New `tournament_edit_history` table with JSON change log.

### 6. Complete Edit Flow

```
Tournament List
      │
      ▼ click "Muokkaa"
┌─────────────────────────────────────┐
│  EDIT SCREEN                        │
│                                     │
│  1. See change history (if any)     │
│  2. View players + pairings         │
│                                     │
│     ┌──────────────────────┐        │
│     │ Click "Muokkaa"      │        │
│     │ pelaajia             │        │
│     └──────────┬───────────┘        │
│                ▼                    │
│     ┌──────────────────────┐        │
│     │ Paste/edit textarea  │        │
│     │ Click "Tarkista"     │        │
│     └──────────┬───────────┘        │
│                ▼                    │
│     ┌──────────────────────┐        │
│     │ Review validation    │        │
│     │ Fix typos / confirm  │        │
│     │ Click "Hyväksy"      │        │
│     └──────────┬───────────┘        │
│                ▼                    │
│  3. Pairings auto-adjust:           │
│     - Removed → empty slots         │
│     - Added → unassigned pool       │
│                                     │
│  4. Manually assign/swap as needed  │
│                                     │
│  5. "Tallenna" to save progress     │
│     (can return another day)        │
│                                     │
│  6. "Aloita turnaus" when ready     │
│                                     │
└─────────────────────────────────────┘
```

**Blocked from starting tournament:**
- Empty slots in pairings
- Unassigned players in pool
- Unresolved name warnings (potential typos not confirmed)

## Technical Implementation Notes

### New Database Table

```sql
CREATE TABLE tournament_edit_history (
    id INTEGER PRIMARY KEY,
    tournament_id INTEGER NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_type TEXT NOT NULL,  -- 'player_added', 'player_removed', 'player_renamed', 'pairing_changed'
    change_data JSON NOT NULL,  -- Details of the change
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
);
```

### New Routes

- `GET /admin/tournaments/<id>/edit` - Full-screen edit page
- `POST /admin/tournaments/<id>/validate-players` - Validate player names against registry
- `POST /admin/tournaments/<id>/update-players` - Save player changes with pairing preservation
- `GET /admin/tournaments/<id>/edit-history` - Fetch change history

### Fuzzy Matching

Use Python's `difflib.SequenceMatcher` for name similarity:
- Threshold: 0.8 similarity ratio for suggestions
- Compare against all players in registry
- Return top match if above threshold

### Pairing Preservation Algorithm

```python
def update_pairings_for_player_changes(tournament_id, old_players, new_players):
    # 1. Find removed players (in old, not in new)
    removed = old_players - new_players

    # 2. Find added players (in new, not in old)
    added = new_players - old_players

    # 3. Mark removed player slots as empty (NULL)
    for player_id in removed:
        clear_player_from_pairings(tournament_id, player_id)

    # 4. Added players go to unassigned pool (not in pairings yet)
    # They will be stored separately until user assigns them

    # 5. Return state for UI
    return {
        'pairings': get_pairings_with_empty_slots(tournament_id),
        'unassigned': list(added)
    }
```

## Out of Scope

- Drag-and-drop player assignment (click-to-assign is sufficient)
- Mobile-optimized layout (admin is desktop-first)
- Undo/redo for individual changes (history is view-only)

## Success Criteria

1. User can paste player list from Excel and see validation immediately
2. Typos are caught before creating duplicate players
3. Pairings survive player list edits (same court count)
4. User can see what changed since last edit session
5. Clear workflow from edit → validate → pair → start
