# Daily Summary — 2026-03-10

## Changes Made

### 1. Extract score entry flow into Flask Blueprint
**Commit:** `9935203`
**Files:** `helpers.py` (NEW), `play_routes.py` (NEW), `app.py`, 8 templates

Major refactoring of `app.py` (~4330 lines → ~3340 lines) by extracting the tournament-critical score entry flow into a Flask Blueprint.

**New files:**
- **`helpers.py`** (266 lines) — Shared helpers extracted from app.py: `get_db_connection`, `get_player`, `get_result_correction_scenario`, `get_court_labels`, `validate_round1_pairings`, `validate_saved_pairings_still_valid`, `block_in_demo_mode`
- **`play_routes.py`** (788 lines) — Flask Blueprint "play" with 8 routes: `active_tournament`, `active_round`, `confirm_match_teams`, `score_entry`, `start_round`, `sse_round_stream`, `active_round_matches_partial`, `api_tournament_pairings_text`

**Blueprint pattern:**
- Routes registered with `play.` prefix: `url_for('play.active_round', ...)`
- Within blueprint, relative prefix: `url_for('.active_round', ...)`
- SSE broadcaster passed via `init_play_routes(sse_broadcaster)`
- Helpers re-exported from `app.py` for backward compatibility with existing test imports

**Bug fix included:**
- Added `winning_team` validation in `score_entry` POST — now rejects values other than 1 or 2

**Consolidation:**
- Extracted `_load_match_player_names()` helper to replace 4 repeated get_player loops
- Extracted `_check_tournament_playable()` helper to replace 3 repeated status checks

**Templates updated (url_for → play. prefix):**
- `active_round.html`, `_matches_partial.html`, `confirm_match.html`, `score_entry.html`, `home.html`, `leaderboard.html`, `admin_dashboard.html`, `start_round.html`

**Verification:**
- All 218 tests pass (0 test changes needed — URLs unchanged, imports backward compatible)
- CLI simulation validates correctly
- Manual testing confirmed score entry flow + drag-and-drop team shuffle working

## Lessons Learned
- When committing, always verify pre-existing unstaged changes in the working directory — `confirm_match.html` had unrelated WIP changes that accidentally got included
- `confirm_match.html` drag-and-drop styles live in `static/css/shuffle.css` (blue theme) — the inline CSS in the template was a yellow WIP that conflicted
