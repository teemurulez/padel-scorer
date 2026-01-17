# Daily Summary - 2026-01-17

## Overview

Major UX polish for the full-screen tournament edit page. Focused on visibility, contrast, usability, and workflow improvements. Also attempted a Court Hub grid view feature but rolled it back after user testing showed the existing list view was better for mobile users.

## Features Implemented

### Tournament Edit Page UX Improvements

#### Contrast & Visibility Fixes
- Darkened change history text and border colors (#d4a800 border, #5c4a00 text)
- Added explicit dark text color (#1a1a2e) to panel headers ("Pelaajat", "Kierros 1 - Parit")
- Improved court header contrast with darker background (#e0e0e0)
- Added font-weight to team titles and player slots
- Darkened validation summary background (#e8e8e8)

#### Scrollbar Visibility
- Force scrollbars visible on macOS with `-webkit-appearance: none`
- Custom scrollbar styling (10px width, gray track #e0e0e0, darker thumb #888)
- Applied to both player list and textarea editor

#### Player Count Auto-Calculation
- Removed fixed court count enforcement
- Adding more players now automatically increases courts (players / 4)
- Validation ensures player count is divisible by 4
- Helpful error message shows how many to add/remove

#### Validation Results UX
- Warning indicator (⚠) appears next to "Pelaajat" title when issues exist
- Moved "Yhteenveto" summary above the player list
- Right-justified suggestion links ("Kyllä" / "Ei, uusi pelaaja")
- Improved text contrast in validation items

#### Player Search in Pairings
- Added search bar above court cards
- Yellow highlight with border on matching player names
- Searches both court slots and unassigned players
- Case-insensitive partial matching
- Clear button (×) to reset search

#### Change History Collapsible
- History section now starts collapsed by default
- Click header to expand/collapse
- Toggle icon (▶/▼) indicates state
- Hover effect on clickable header

#### Minor Fixes
- Changed "Piilota" to "Sulje" (history closes permanently)
- Made editor action buttons fit narrow panel with flex-wrap

### Court Hub Feature (Rolled Back)

Implemented a grid-based Court Hub view (`/tournament/<id>/round/<id>/courts`) with:
- Visual grid layout for all courts
- Progress bar showing completed matches
- Dark theme background
- Winner checkmarks on completed matches

**Rolled back** after user testing - the existing `active_round` list view is better suited for mobile users and already provides all needed functionality.

## Files Changed

- `static/css/admin_edit.css` - All contrast, scrollbar, search, and validation styling
- `static/js/tournament_edit.js` - Auto-calculate courts, search functions, collapsible history
- `templates/admin_tournament_edit.html` - Search bar, warning indicator, collapsible history markup

## Commits (21 ahead of origin/main)

Key commits from today:
- `fix: improve contrast and visibility in tournament edit page`
- `fix: improve tournament edit UX` (auto-calculate courts, Sulje button)
- `fix: make editor action buttons fit in narrow panel`
- `fix: force scrollbar visibility on macOS`
- `fix: improve validation results contrast and layout`
- `feat: improve validation UX with warning indicator and reordered summary`
- `feat: add player search bar in pairings area`
- `feat: make change history collapsible, hidden by default`

## Test Status

- 152 passed, 3 skipped
- All existing tests continue to pass

## Technical Notes

### Player Search Implementation
```javascript
function searchPlayers(query) {
    const slots = document.querySelectorAll('.player-slot, .unassigned-player');
    const normalizedQuery = query.toLowerCase().trim();

    slots.forEach(slot => {
        slot.classList.remove('search-highlight');
        if (normalizedQuery && slot.textContent.toLowerCase().includes(normalizedQuery)) {
            slot.classList.add('search-highlight');
        }
    });
}
```

### Auto-Calculate Courts
```javascript
// In validatePlayers()
if (lines.length % 4 !== 0) {
    const nearestLower = Math.floor(lines.length / 4) * 4;
    const nearestHigher = nearestLower + 4;
    alert(`Pelaajien määrän täytyy olla jaollinen 4:llä...`);
    return;
}
const newNumCourts = lines.length / 4;

// In saveTournament()
document.getElementById('form-num-courts').value = lines.length / 4;
```

## Next Steps

1. **Push commits** - 21 commits ahead of origin/main
2. **Admin UI refresh** - Apply consistent design to other admin pages
3. **Additional features** - Based on usage feedback

## Lessons Learned

- Grid layouts look nice on desktop but list views are often better for mobile-first apps
- Creating rollback points (git tags) before experimental features is valuable
- Small UX details (contrast, scrollbars, button sizing) significantly impact usability
