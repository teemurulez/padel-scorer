# Daily Summary - 2026-01-10

## Overview

Major UI redesign and UX improvements across all player-facing views, plus admin enhancements for player points management.

## Features Implemented

### Admin Player Points Management
- Added "Pelaajat" (Players) tab to admin dashboard
- View and edit individual player points with admin adjustments
- Points now correctly calculated from scores table to match public leaderboard

### Season Leaderboard Improvements
- Added "Pisteet" (Points) column showing total points including admin adjustments
- Added "Turnaukset" (Tournaments) column showing participation count
- Removed duplicate "Wins" column
- Removed "Clear all data" button from public view (admin-only)

### UI Redesign - Round View (active_round.html)
- New clean design: white background, black text, yellow (#FFD700) accent buttons
- Header with Padel Paroni logo, bold title, tournament subtitle
- Movement badge for rounds 2+ showing team movement rules
- Match cards with stacked buttons (56px primary, 48px secondary)
- Completed matches now clickable to edit winner (with "Muokkaa tulosta" hint)
- Progress indicator showing X/Y matches completed
- "Aloita seuraava kierros" button always visible (disabled with count when not all complete)

### UI Redesign - Score Entry (score_entry.html)
- Matching header with logo and bold title
- Yellow primary button for confirming winner
- Team selection cards with yellow highlight when selected
- Consistent styling with round view

### UI Redesign - Team Confirmation (confirm_match.html)
- Matching header with logo and bold title
- Yellow-bordered draggable player cards
- Yellow primary button, white secondary button
- Fixed bug where team changes weren't saving (missing .team-1/.team-2 classes)

### Watermark Pattern
- Tilted (15-degree) repeating logo pattern in gray background areas
- Visible on sides outside the white content container
- Applied to all three main views

### Navigation & UX
- Admin footer link added to all views (opens in new tab)
- Removed intermediate start_round confirmation view (direct action)
- Tournament end now redirects users to home with message "Turnaus on päättynyt"

## Bug Fixes

- Fixed team shuffle save not working (missing CSS classes for JavaScript selectors)
- Fixed admin player points not matching public leaderboard (query discrepancy)
- Fixed duplicate `id="players"` causing empty admin tab
- Added tournament completion checks to prevent actions on ended tournaments

## Files Modified

### Templates (Major Changes)
- `templates/active_round.html` - Complete redesign
- `templates/score_entry.html` - Complete redesign
- `templates/confirm_match.html` - Complete redesign
- `templates/tournament_selection.html` - Added logo, simplified layout
- `templates/season_leaderboard.html` - Added columns, removed clear button
- `templates/admin_dashboard.html` - Added Pelaajat tab

### Backend
- `app.py` - Tournament completion checks, redirect fixes, query updates

### Assets
- `static/images/padel-paroni-logo.png` - Club logo (added)
- `static/css/style.css` - Transparent background logo

### Documentation
- `docs/plans/2026-01-10-round-view-ui-redesign.md` - Design document
- `docs/plans/2026-01-10-admin-player-points-design.md` - Feature design

## Technical Notes

- Jinja2 `url_for()` in CSS `background-image: url()` doesn't work - use inline styles or actual elements
- CSS pseudo-element `::before` can conflict with linked stylesheets - use explicit elements for complex watermarks
- JavaScript class selectors (`.team-1`, `.team-2`) must match HTML - removing classes breaks functionality

## Next Steps

- Consider applying watermark pattern to other views (leaderboard, season results)
- Test all flows on mobile devices
- Consider adding tournament results summary after ending tournament
