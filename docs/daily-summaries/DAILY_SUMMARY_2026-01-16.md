# Daily Summary - 2026-01-16

## Overview

Improved admin tournament editing UX with focus on preserving manual Round 1 pairings when editing player names, and streamlined the tournament start flow.

## Features Implemented

### Admin Edit Mode Persistence
- Edit form stays open after clicking "Tallenna muutokset" (Save Changes)
- URL includes `?edit={tournament_id}#tournament-{id}` for scroll position
- Round 1 preview auto-loads when returning to edit mode

### Smart Pairing Preservation on Player Name Edits
- When editing player names (same count), pairings are now preserved
- System maps old player IDs to new IDs by position in the list
- Mapping logic:
  - Players listed alphabetically in textarea
  - Position-by-position mapping: old_id[i] → new_id[i]
  - Pairings table updated with new IDs
- Form's JavaScript state (with old IDs) is skipped when mapping is used
- Pairings only cleared when:
  - Court count changes
  - Player count changes

### Streamlined Tournament Start
- "Aloita" button now starts Round 1 immediately (POST instead of GET)
- Skips the intermediate start_round.html preview page
- Redirects directly to public active round view

## Bug Fixes

### Finnish Character Fix
- Fixed "Yllapito" → "Ylläpito" in footer links
- Affected files: no_active_tournament.html, tournament_selection.html

### Test Fixes
- Fixed test_home_page_has_admin_dashboard_link (Finnish encoding)
- Skipped test_complete_shuffle_workflow (requires unimplemented Court Selection Hub feature)
- Updated test_edit_players_clears_saved_pairings → test_edit_players_updates_pairings_by_position

## Technical Details

### Player ID Mapping Algorithm (app.py)
```python
# Get current players in alphabetical order (same as shown in edit textarea)
current_players_ordered = db.execute(
    '''SELECT tp.player_id, pr.first_name, pr.last_name
       FROM tournament_players tp
       JOIN player_registry pr ON tp.player_id = pr.id
       WHERE tp.tournament_id = ?
       ORDER BY pr.first_name, pr.last_name''',
    (tournament_id,)
).fetchall()

# Build mapping after new players are created
for i, old_player in enumerate(current_players_ordered):
    if i < len(final_player_ids_ordered):
        old_id = old_player['player_id']
        new_id = final_player_ids_ordered[i]
        if old_id != new_id:
            player_id_mapping[old_id] = new_id

# Update pairings with new IDs
for col in ['team1_player1_id', 'team1_player2_id', ...]:
    if pairing[col] in player_id_mapping:
        updates[col] = player_id_mapping[pairing[col]]
```

## Files Changed

- `app.py` - Player ID mapping logic, edit redirect with anchor
- `templates/admin_dashboard.html` - Auto-open edit form, Aloita button as POST form
- `templates/no_active_tournament.html` - Finnish character fix
- `templates/tournament_selection.html` - Finnish character fix
- `tests/test_edit_clears_pairings.py` - Updated test for new behavior
- `tests/test_team_shuffling.py` - Skip unimplemented feature test

## Test Status

- 132 passed, 3 skipped
- All admin editing tests pass

## Next Steps (Pending Features)

1. **Court Selection Hub** - Design exists (2025-12-23), not implemented
2. **Admin UI refresh** - Apply new design system to admin pages
3. **Additional admin features** - As needed based on usage
