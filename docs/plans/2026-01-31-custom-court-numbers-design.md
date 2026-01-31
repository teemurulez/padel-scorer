# Custom Court Numbers Design

> **Date:** 2026-01-31
> **Status:** Approved

## Problem

Real venues have specific court numbers that may not be sequential (e.g., 1, 2, 3, 4, 5, 6, 8, 9 - skipping 7). Currently, courts are numbered 1, 2, 3... based on `num_courts`. Users need to display actual venue court numbers.

## Solution

Allow custom court numbers per tournament, configurable during setup phase.

## User Input

Tournament setup/edit will have:
- **Number of courts** (existing field)
- **Starting court number** (new, default: 1)
- **Courts to skip** (new, optional, comma-separated)

Examples:
- 8 courts, start 1, skip 7 → Courts: 1, 2, 3, 4, 5, 6, 8, 9
- 4 courts, start 5, skip none → Courts: 5, 6, 7, 8
- 6 courts, start 1, skip "3, 7" → Courts: 1, 2, 4, 5, 6, 8

Validation:
- Skip numbers must be within the potential range
- Display preview of actual court numbers

## Data Storage

**Database change:**
- Add `court_labels` column to `tournaments` table (TEXT, JSON array like `[1,2,3,4,5,6,8,9]`)
- If NULL, fall back to sequential 1...num_courts (backwards compatible)

**No change to matches table** - `court_number` already stores the actual displayed number.

## Where Court Numbers Appear

**Admin (tournament setup/edit):**
- Input fields with preview

**Public pages (actual court numbers):**
- Active round view (court headers)
- Score entry page
- Match confirmation page
- Tournament results

**Player profile stats:**
- Keep showing actual court numbers (even though they vary across tournaments)

**Pairing algorithm:**
- Uses court position (0, 1, 2...) internally for winner-moves-up logic
- Stores actual court number in database for display

## Implementation

### Files to Modify

1. **`database.py`** - Add `court_labels` column migration
2. **`app.py`** - Tournament create/edit: parse inputs, generate court list, store JSON
3. **`templates/admin_dashboard.html`** - Add start_from and skip_courts fields
4. **`templates/admin_tournament_edit.html`** - Same fields for editing
5. **`court_movement.py` / `seeded_pairing.py`** - Use court labels when generating pairings
6. **`scripts/generate_test_data.py`** - Use realistic court numbers (e.g., skip 7)

### Helper Function

```python
def generate_court_labels(num_courts, start_from=1, skip_courts=None):
    """Generate list of court numbers.

    Args:
        num_courts: Number of courts needed
        start_from: Starting court number (default 1)
        skip_courts: List of court numbers to skip

    Returns:
        List of court numbers, e.g., [1, 2, 3, 4, 5, 6, 8, 9]
    """
    skip_courts = skip_courts or []
    courts = []
    current = start_from
    while len(courts) < num_courts:
        if current not in skip_courts:
            courts.append(current)
        current += 1
    return courts
```

### Backwards Compatibility

- Existing tournaments have NULL `court_labels`
- When NULL, generate sequential [1, 2, ..., num_courts] on the fly
- No data migration needed for existing data
