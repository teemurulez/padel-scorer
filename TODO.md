# Padel Paroni - Current Status & Next Steps

> **Last updated:** 2026-02-08

## Project Status

**PUBLIC BETA** - App released for club-wide testing. All 209 tests pass.

## Completed Items

- [x] Fix pre-existing test failures (done 2026-01-18)
- [x] Admin UI polish - light theme conversion (done 2026-01-21)
- [x] Player name validation for tournament creation (done 2026-01-18)
- [x] Database restore functionality (done 2026-01-21)
- [x] Prevent orphaned tournaments when changing seasons (done 2026-01-21)
- [x] Extended player profile statistics (done 2026-01-21)
- [x] Win/loss per court vertical bar chart (done 2026-01-22)
- [x] Player points editing in admin (done 2026-01-23)
- [x] Clickable logo/title navigation (done 2026-01-23)
- [x] Medal emojis in standings (done 2026-01-23)
- [x] Railway deployment configuration (done 2026-01-24)
- [x] Match result correction feature (done 2026-01-26)
- [x] Mobile drag feedback with floating clone (done 2026-01-27)
- [x] Demo mode for admin (done 2026-01-27)
- [x] Content-Security-Policy headers with nonces (done 2026-01-27)
- [x] Database connection management cleanup (done 2026-01-27)
- [x] Live score updates via SSE (done 2026-01-27)
- [x] Bulk import player points from external tournaments (done 2026-01-27)
- [x] Fix season standings for players with only imported points (done 2026-01-28)
- [x] Railway persistent volume with DATABASE_PATH config (done 2026-01-29)
- [x] Seasons tab accordion redesign (done 2026-01-29)
- [x] SSE blocking fix with DISABLE_SSE env var (done 2026-01-30)
- [x] Rolling pool randomization for Round 1 (done 2026-01-30)
- [x] Consistent main page (no auto-redirect) (done 2026-01-31)
- [x] Custom court numbers per tournament (done 2026-01-31)
- [x] Player profile chart fix (done 2026-01-31)
- [x] Player profile watermark background (done 2026-01-31)
- [x] Copy pairings export button for round 1 (done 2026-02-07)
- [x] Fix imported matches not showing in season standings (done 2026-02-07)
- [x] Fix tournament count for imported tournaments (done 2026-02-07)
- [x] Fix court movement algorithm for 3+ courts (done 2026-02-08)

## Known Bugs

- [ ] Tournament creation modal closes on validation error (wrong player count) - should stay open and preserve data

## Feature Requests

- [ ] Auto-calculate number of courts from player list (player count / 4) in tournament creation modal

## Technical Debt

- [ ] Extract tournament count fallback logic to helper function (duplicated in index and season_leaderboard routes) and add test
- [ ] Review all features that were only tested with 2 courts — verify they work correctly with 4-8 courts (the court movement bug went unnoticed because tests only covered 2 courts)

## Code Review Backlog

**High Impact (tournament-critical):**
- [x] Pairing algorithm - rolling pool randomization, seeded pairing (reviewed 2026-02-07)
  - [ ] **Critical:** Add validation/truncation when extra players exist (design with user)
  - [ ] **Important:** Add tests for larger tournaments 6+ courts (design with user)
  - [ ] **Minor:** Add zero courts validation
  - [ ] **Minor:** Clarify docstring about pool boundaries (design with user)
- [ ] Score entry flow - entering results, team shuffling, result correction
- [ ] Tournament lifecycle - Setup → Active → Completed transitions

**Security-focused:**
- [ ] Admin authentication - login, session handling, CSRF protection
- [ ] Bulk import - user input handling, data validation

**Complex logic:**
- [ ] Leaderboard calculations - season stats, player rankings, win rates
- [ ] Player seeding view - SQL view that calculates seed scores

## Edge Cases Handled (2026-02-07)

- No pairings generated → shows alert "Ei kopioitavia pareja"
- Clipboard API failure → fallback alert with copyable text
- No actual tournaments (only imported) → falls back to MAX(tournaments_adjustment)
- NULL adjustment values → COALESCE handles gracefully
- Zero matches (for win_rate) → NULLIF prevents division by zero

## Next Steps

### 1. Monitor Public Beta

- Gather feedback from club testers
- Monitor Railway logs for errors
- Fix any issues reported by users

### 2. Optional Improvements

**Performance:**
- Consider polling-based alternative to SSE for live updates
- Set up UptimeRobot (free) to ping app every 5 min to prevent cold starts

**UX Ideas:**
- Move tournament edit flash messages into "Viimeisimmät muutokset" expandable area
- Reduce visual clutter in seasons accordion (simplify tournament table, compact layout)

### 3. Deployment Notes

**Railway (deployed):**
- `DISABLE_SSE=1` and `SKIP_MIGRATIONS=1` set
- Persistent volume at `/data/padel.db`

**PythonAnywhere (alternative):**
- See **[docs/PYTHONANYWHERE_DEPLOYMENT.md](docs/PYTHONANYWHERE_DEPLOYMENT.md)** for setup

## Recent Changes (2026-02-08)

**Critical Bug Fix - Court Movement Algorithm:**
- Players were jumping multiple courts instead of moving one court up/down
- Root cause: algorithm concatenated all winners + all losers, then distributed sequentially
- Only worked correctly with 2 courts; with 3+ courts players skipped courts
- Fix: proper interleaving — winners move up 1, losers move down 1, boundary courts stay
- Added 4 new tests (3, 4, 6 courts, mixed winners) — 209 tests total
- Bug discovered during first real tournament with 5 courts

**Admin Password Reset:**
- Reset Railway admin password via `railway ssh`

---

## Recent Changes (2026-02-07)

**Copy Pairings Export:**
- Added "Kopioi parit" button to tournament edit page
- Copies round 1 pairings to clipboard: `Kenttä X: Name & Name vs Name & Name`
- Visual feedback shows "Kopioitu!" after copying

**Bug Fixes:**
- Season standings now correctly shows imported match counts
- Win rate calculation includes imported matches
- Tournament count shows imported tournaments when no actual tournaments exist

**Production:**
- Initialized Railway database for February tournament
- Imported January tournament results

---

## Recent Changes (2026-01-31)

**PUBLIC BETA RELEASE**

**Custom Court Numbers:**
- Tournaments can now have custom court numbers (e.g., 1,2,3,4,5,6,8,9 - skipping 7)
- UI fields: "Aloitusnumero" (start from) and "Ohita kentät" (skip courts)
- Live preview of court numbers in creation form
- Backwards compatible (existing tournaments unaffected)

**Player Profile Improvements:**
- Fixed bar chart showing equal heights for different values
- Added logo watermark background (consistent with other public pages)

**UI Polish:**
- Fixed form field heights (number inputs match text inputs)
- Fixed button alignment in modal footer
- Consistent main page (no auto-redirect to single tournament)

---

## Recent Changes (2026-01-30)

**SSE Blocking Fix:**
- Root cause: SSE held single worker indefinitely on Railway/PythonAnywhere
- Solution: Added `DISABLE_SSE=1` env var to disable SSE on single-worker hosts

**Rolling Pool Randomization:**
- New algorithm for Round 1 pairings adds randomness within skill tiers
- Prevents "always same partners" problem

**Authentication & Import Fixes:**
- Fixed session key mismatch (`is_admin` vs `logged_in_as_admin`)
- Extended bulk import to 4 columns (Name, Wins, Tournaments, Matches)

---

## Recent Changes (2026-01-29)

**Railway Deployment Fixes:**
- Fixed missing `tournaments_adjustment` column in migration
- Made `DATABASE_PATH` configurable via environment variable
- Fixed migrations to handle fresh/empty databases
- Fixed `init_db()` to run in Flask app context for correct path
- Railway now uses persistent volume at `/data/padel.db`

**Admin Seasons Tab Redesign:**
- Replaced cluttered layout with accordion list
- Each season expands to show tournaments and actions
- Current season highlighted with gold border at top
- Tournament actions (Aloita, Muokkaa, Näytä, Lopeta, Poista) in compact rows
- Inline "Luo uusi kausi" form
- CSP-compliant event handling

---

## Recent Changes (2026-01-28)

**Tournament Edit Page UX:**
- Changed buttons to primary gold style (was gray/secondary)
- Tiimi 2 background changed to green (visual distinction from Tiimi 1 blue)
- Empty court slots now shown when no pairings exist
- All players shown in unassigned pool when no pairings
- Players removed from pool when placed on court
- Dynamic count of unassigned players (updates in real-time)

**Bug Fix:**
- Season standings now includes players with only imported points (no tournament matches)

**Security Improvements:**
- Admin setup requires `ADMIN_SETUP_TOKEN` env var in production
- Session invalidated when database is wiped (prevents stale session access)
- Only admins can start tournaments in setup mode
- Players registered in setup tournaments now show in admin Players tab

**Performance:**
- Added `SKIP_MIGRATIONS=1` env var to skip startup DB operations
- Optimized Gunicorn settings for slow volume I/O
- Added `/health` and `/health/db` diagnostic endpoints

**Railway Deployment:**
- Upgraded to Hobby plan with persistent volume
- Volume mounted at `/data` for SQLite database

**Tests:** 199 passed (was 196)

---

## Recent Changes (2026-01-27)

**Mobile Drag Feedback:**
- Added floating clone that follows finger when dragging players
- Original slot shows faded placeholder during drag
- Drop targets highlighted with dashed border
- Team cards centered and wider on mobile (95% width)
- Fixed missing shuffle.css link in template

**Demo Mode:**
- Read-only admin access for demonstrations
- Set `DEMO_PASSWORD` env var to enable
- Orange banner shows when in demo mode
- All write operations blocked with friendly message

**Content-Security-Policy:**
- Strict CSP with nonces for inline scripts
- Prevents XSS and unauthorized script execution
- Unique nonce generated per request

**Database Connection Cleanup:**
- All routes now use `get_db_connection()` consistently
- Connections properly closed at request end via Flask's `g` object

**Live Score Updates (SSE):**
- Active round page now updates in real-time
- Uses Server-Sent Events (no WebSocket complexity)
- Auto-reconnects on connection drops
- Next round button enables automatically when all matches complete

**Bulk Import Player Points:**
- New feature in Players tab to import wins from external tournaments
- Paste from Excel (Name, Wins, Tournaments columns)
- Preview parsed data before importing
- Adds to existing points and tournaments (doesn't replace)
- Creates new players if needed
- Players with 0 wins are imported (added to registry)
- 8 new tests added (195 total)

**CSP Inline Handler Fixes:**
- Removed all inline onclick/onchange/onsubmit handlers
- Replaced with event delegation in nonced script blocks
- Fixed buttons in admin dashboard (create tournament, import points, player edit)
- Added disabled button styling for import confirm

---

## Recent Changes (2026-01-26)

**Match Result Correction Feature:**
- Scenario detection: blocks regular users when next round started, allows admin
- Admin recalculate round: regenerates pairings based on corrected results
- Red warning banner when previous round was edited
- Round navigation for admins (switch between rounds)
- Yellow background indicator for admin mode
- Info banner showing current winner when editing
- Audit logging for all result corrections

**Bug Fixes:**
- Fixed CSRF token missing in team shuffle form

**Testing:**
- Added 16 new tests for result correction feature
- Test count: 173 → 187

---

## Recent Changes (2026-01-24)

**Deployment:**
- Added Railway deployment configuration (runtime.txt, Procfile)
- Project ready for cloud deployment

---

## Recent Changes (2026-01-23)

**Admin Features:**
- Player points editing in admin Players tab (inline edit with adjustment tracking)

**UI/Navigation:**
- Clickable logo and titles on all public pages (link to main view)
- Fixed expand/collapse arrows in season standings
- Added medal emojis (🥇🥈🥉) for top 3 players
- Improved back navigation buttons in tournament views

**Development:**
- Added `scripts/generate_test_data.py` for diverse test data generation

**Security Testing:**
- Added 14 security tests covering CSRF, rate limiting, SQL injection, XSS
- Test count: 159 → 173

**Testing:**
- Added 4 new tests for player profile statistics
- Test count: 155 → 159

---

## Recent Changes (2026-01-22)

**Player Profile Statistics:**
- Reordered stats cards: moved "Voitot" before "Voittoja/turnaus"
- Added vertical bar chart showing wins/losses per court (green/red bars)

---

## Recent Changes (2026-01-21)

**Admin UI:**
- Converted admin UI from dark theme to light theme with gold accents
- Added tournament creation modal popup
- Added Data tab with JSON database export and restore
- Added validation to prevent orphaned tournaments when changing seasons

**Player Profile Statistics:**
- Added "Paritilastot" section: Paras pari, Yleisin pari, Yleisin vastustaja, Vaikein vastustaja
- Added "Turnaukset" section: Pisin voittoputki, Paras/Huonoin turnaus, Comeback-%, kierroskohtaiset voittoprosentit
- Added court statistics bar chart (ottelut per kenttä)
- Added season progress chart (voitot turnauksissa)
- Added current form display (viimeiset 10 ottelua)
- Added medal emojis for top 3 rankings
- Fixed points calculation (3 -> 1 point per win)

## Recent Changes (2026-01-18)

- Fixed all test failures (152 passed, 3 skipped)
- Changed scoring system to wins-only
- Added statistics columns to season standings
- Added CSV export for season standings
- Added player name validation with typo detection

## Recent Changes (2026-01-17)

- Security hardening: CSRF, rate limiting, SECRET_KEY, session cookies
- Tournament edit page UX improvements
- Finnish character fixes
- Court Hub feature attempted and rolled back (list view better for mobile)
- Documentation cleanup: updated README, removed outdated docs, fixed references

## Documentation Status

| File | Status |
|------|--------|
| `README.md` | ✅ Updated - current with all features |
| `TODO.md` | ✅ Current - tracking next steps |
| `docs/COURT_MOVEMENT.md` | ✅ Updated - fixed broken reference |
| `docs/daily-summaries/` | ✅ Clean - dated files only |
| `docs/plans/` | 📁 Historical - design documents |

## Key Files

- `README.md` - Project overview and setup instructions
- `TODO.md` - Current status and next steps (this file)
- `docs/daily-summaries/` - Daily work logs
- `docs/plans/` - Historical design documents
- `config.py` - App configuration (security settings)
- `app.py` - Main Flask application
