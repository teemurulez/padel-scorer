# Daily Summary - 2026-01-27

## Overview

Fixed mobile drag feedback with floating clone approach. Started implementing demo mode for admin.

## Completed Tasks

### Mobile Drag Feedback
Fixed the issue where there was no visual feedback when dragging players on mobile:

**Implementation:**
- Floating clone follows finger during drag with shadow and slight rotation
- Original slot shows faded placeholder with dashed border
- Other player slots highlighted as drop targets
- Hover state shows darker highlight when over a target
- Team cards centered and 95% width on mobile

**Bug Fix:**
- shuffle.css was not linked in confirm_match.html template

**Files Changed:**
- `static/css/shuffle.css` - Added floating clone styles, drop target styles, mobile centering
- `static/js/shuffle.js` - Implemented floating clone creation/movement/cleanup
- `templates/confirm_match.html` - Added missing shuffle.css link

## In Progress

### Demo Mode for Admin
Designed read-only admin mode for showing the app to friends:

- Same login form, separate `DEMO_PASSWORD` env var
- Banner: "👾 Demo-tila – muutoksia ei tallenneta 👾"
- `@block_in_demo_mode` decorator blocks all POST/DELETE routes
- Users can explore but not modify data

Design doc: `docs/plans/2026-01-27-demo-mode-design.md`

## Test Results

- 187 tests passing
- 3 skipped (expected)

## Commits

- `d806478` feat: add mobile drag feedback with in-place highlighting
- `1973a33` feat: improve mobile drag with floating clone
- `186449c` docs: add demo mode design
