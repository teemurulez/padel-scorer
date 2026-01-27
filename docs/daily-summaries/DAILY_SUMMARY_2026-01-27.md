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

### Demo Mode for Admin
Implemented read-only admin mode for showing the app to friends:

- Same login form, separate `DEMO_PASSWORD` env var
- Orange banner: "👾 Demo-tila – muutoksia ei tallenneta 👾"
- `@block_in_demo_mode` decorator blocks all POST/DELETE routes
- Users can explore but not modify data
- Flash message shown when action is blocked

**Files Changed:**
- `config.py` - Added DEMO_PASSWORD config
- `app.py` - Login handling, decorator, applied to all write routes
- `static/css/admin.css` - Demo banner styles
- `templates/admin_dashboard.html` - Demo banner
- `templates/admin_tournament_edit.html` - Demo banner

Design doc: `docs/plans/2026-01-27-demo-mode-design.md`

### Content-Security-Policy Headers
Implemented strict CSP with nonces for XSS protection:

- Unique nonce generated per request via `@app.before_request`
- CSP header added via `@app.after_request`
- Context processor injects nonce into all templates
- Updated 9 script tags with `nonce="{{ csp_nonce }}"`

**Policy:**
```
default-src 'self'; script-src 'self' 'nonce-...';
style-src 'self' 'unsafe-inline'; img-src 'self' data:;
form-action 'self'; frame-ancestors 'none'
```

## Test Results

- 187 tests passing
- 3 skipped (expected)

## Commits

- `d806478` feat: add mobile drag feedback with in-place highlighting
- `1973a33` feat: improve mobile drag with floating clone
- `186449c` docs: add demo mode design
- `763240d` docs: add daily summary and update TODO for 2026-01-27
- `4dd0b69` feat: add demo mode for admin
- `9a4135b` docs: update TODO and daily summary with demo mode completion
- `a27efb2` feat: add Content-Security-Policy with nonces
