# Demo Mode Design

## Overview

A read-only admin mode that allows friends to explore the admin interface without making actual changes. Activated by a separate demo password.

## Authentication

- Same `/admin` login form handles both passwords
- `DEMO_PASSWORD` environment variable (disabled if not set)
- If demo password matches: `session['demo_mode'] = True`
- Demo users can access all admin pages but cannot write

## Visual Indicator

Fixed banner at top of all admin pages when in demo mode:
- Yellow/orange background
- Text: "👾 Demo-tila – muutoksia ei tallenneta 👾"
- Stays visible while scrolling

## Write Blocking

Decorator `@block_in_demo_mode` on all POST/DELETE admin routes:
- Checks `session.get('demo_mode')`
- For AJAX: returns `{success: false, demo: true, message: "Demo-tila: toimintoa ei suoritettu"}`
- For forms: redirects back with flash message

## Routes to Protect

All admin write operations:
- Tournament: create, edit, delete, start round, recalculate round
- Players: edit points, merge players
- Seasons: create, edit, change active season
- Matches: enter scores, edit results, shuffle teams
- Database: backup restore
- Settings: any config changes

GET requests (viewing) remain unrestricted.

## Configuration

In `config.py`:
```python
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD')  # None = demo disabled
```
