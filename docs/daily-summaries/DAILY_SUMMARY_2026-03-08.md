# Daily Summary - 2026-03-08

## Session Focus
First real tournament of the season ("Maaliskuu 2026") — 24 players, 6 courts, 8 rounds. Production incident response: wrong round result caused cascading team assignment errors.

## Production Incident

### What happened
1. In round 6 Kenttä 5, the wrong team was marked as winner (Teemu Salonen & Anrietta Kuosku marked as winners, but they actually lost)
2. Round 7 was generated from the wrong results — Teemu & Anrietta were placed on Kenttä 4 (moved up) instead of Kenttä 6 (should have moved down)
3. Susanna Rasimus & Miika Liukkonen were placed on Kenttä 6 instead of Kenttä 4
4. Round 7 scores were entered with the wrong teams on courts 4 and 6
5. Admin manually corrected round 6 Kenttä 5 result, but round 7 teams remained wrong

### How it was fixed
1. Downloaded JSON backup from Railway admin panel
2. Analyzed round 6 corrected results and calculated correct round 7 pairings
3. Removed round 7 matches and scores from backup JSON
4. Generated new round 7 matches with correct court assignments based on court movement algorithm
5. Restored fixed backup to Railway via admin panel
6. User re-entered round 7 scores manually from screenshots

### Key finding
- `railway run` executes commands locally with Railway env vars, NOT on the server — cannot access volume-mounted production DB
- JSON backup/restore via admin panel is the reliable way to modify production data

## Feature Request (Highest Priority)
**Recalculate Round button** — When a previous round's result is corrected after the next round has started, the admin needs a button to regenerate the current round's pairings. This would have prevented the manual backup/restore workflow.

## Open Issues (Todo List)
1. **[HIGH]** Add "recalculate round" button for admin when previous round results are corrected
2. Fix player slot styling after manual drag-and-drop pair changes
3. Review and fix pair creation algorithm
4. Fix page header font size inconsistency on standings view

## Tournament Outcome
- Tournament completed successfully after the fix
- App worked well otherwise for 24 players across 8 rounds on 6 courts

## Lessons Learned
- Result correction after next round starts is a real-world scenario that needs first-class support
- `railway run` is not equivalent to SSH — volume data is inaccessible
- JSON backup/restore is a reliable emergency recovery mechanism
