# Daily Summary - 2026-01-31

## Session Focus
Custom court numbers feature, player profile chart fix, UI polish, and public beta release preparation.

## Completed Work

### Custom Court Numbers Feature
- Implemented custom court numbering per tournament (e.g., courts 1,2,3,4,5,6,8,9 - skipping 7)
- Added `court_labels` column to tournaments table (JSON array storage)
- Added UI fields: "Aloitusnumero" (start from) and "Ohita kentät" (skip courts)
- Live preview of court numbers in tournament creation form
- Helper functions: `generate_court_labels()` and `get_court_labels()`
- Full backwards compatibility (NULL = sequential 1...num_courts)
- Design document: `docs/plans/2026-01-31-custom-court-numbers-design.md`

### Player Profile Chart Fix
- Fixed "Wins per Tournament" bar chart showing equal heights for different values
- Root cause: Percentage heights don't work reliably in flex containers
- Solution: Added wrapper div with `position: relative` and bar uses `position: absolute`
- Bars now correctly scale proportionally (e.g., 5,6,5 shows as 83%, 100%, 83%)

### Player Profile Watermark Background
- Added logo watermark background to match other public pages
- Consistent visual design across all public-facing pages

### UI Polish
- Fixed form field heights: number inputs now match text inputs
- Fixed button heights: "Peruuta" and "Luo turnaus" now aligned correctly
- Added proper CSS class to tournament creation form
- Consistent button styling with transparent borders for equal heights

### Consistent Main Page Design
- Implemented unified home page (no auto-redirect to single tournament)
- Shows active tournament with status badge, or "Kauden tulokset" as primary action
- Design document: `docs/plans/2026-01-31-consistent-main-page-design.md`

## Files Changed
- `static/css/admin.css` - Button styling fixes, number input support
- `templates/admin_dashboard.html` - Court numbering fields, form class, button fixes
- `templates/player_profile.html` - Chart fix, watermark background

## Technical Notes
- Changed `input[type="number"]` to `input[type="text"]` with `inputmode="numeric"` for consistent styling
- Buttons now use `border: 2px solid transparent` base style for equal heights
- Progress chart uses absolute positioning for reliable percentage heights

## Milestone
**Public Beta Release** - Application opened for club-wide testing.

## Next Steps
- Gather feedback from public beta testers
- Monitor for any issues in production
- Consider implementing polling-based alternative to SSE for live updates

