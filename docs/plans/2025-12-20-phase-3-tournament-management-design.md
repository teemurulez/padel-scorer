# Phase 3: Tournament Management & Player Tracking - Design Document

**Date:** December 20, 2025
**Author:** Design session with Teemu
**Status:** Design Complete - Ready for Implementation Planning

---

## Table of Contents

1. [Overview](#overview)
2. [Competition Model](#competition-model)
3. [Architecture & Database](#architecture--database)
4. [Stage 1: Tournament Lifecycle](#stage-1-tournament-lifecycle)
5. [Stage 2: Global Player Registry](#stage-2-global-player-registry)
6. [Stage 3: Player Profiles](#stage-3-player-profiles)
7. [Stage 4: CSV Exports](#stage-4-csv-exports)
8. [Testing Strategy](#testing-strategy)
9. [Implementation Rollout](#implementation-rollout)
10. [Success Criteria](#success-criteria)

---

## Overview

### Goals

Phase 3 transforms the Padel scorer from a single-tournament application into a **comprehensive season-based competition management system** with:

- **Seasonal Competition** - Track 10-11 tournaments per calendar year
- **Player Persistence** - Global player registry across all tournaments
- **Performance Tracking** - Player statistics and history
- **Data Export** - CSV exports for analysis

### Key Features

1. **Tournament Lifecycle Management** - Archive completed tournaments, manage active/upcoming
2. **Global Player Registry** - Players tracked across all tournaments with first/last name
3. **Seeded Round 1** - Weighted pairing based on recent performance (last 6 tournaments)
4. **Player Profiles** - Individual statistics and tournament history
5. **CSV Exports** - Season standings, tournament results, player statistics

### Implementation Approach

**Incremental rollout** across 4 stages:
- Stage 1: Tournament Lifecycle (Week 1-2)
- Stage 2: Global Player Registry (Week 3)
- Stage 3: Player Profiles (Week 4)
- Stage 4: CSV Exports (Week 5)

---

## Competition Model

### Seasonal Structure

**Season Definition:**
- One **Season** = Calendar year (January - December)
- **10-11 Tournaments** per season (one per month, summer break)
- Summer break = One month off (June, July, or August)

**Tournament Schedule Example:**
```
2025 Season:
Jan ✓ Feb ✓ Mar ✓ Apr ✓ May ✓ [Jun - Break] Jul ✓ Aug ✓ Sep ✓ Oct ✓ Nov ✓ Dec ✓
└─────────────────────────────────────────────────────────────────────────────┘
                        10-11 tournaments total
```

### Ranking System

**Season Champion Determination:**

**PRIMARY METRIC:** Total individual match wins across all tournaments in the season

- Player with most **match wins** = Season Champion
- Tournament placement (1st, 2nd, 3rd) = Secondary statistic
- Total points = Informational metric

**Example:**
```
Season 2025 Final Standings:
1. Anna Berg        - 45 match wins (10 tournaments, 4.5 wins/tournament)
2. Erik Andersson   - 42 match wins (10 tournaments, 4.2 wins/tournament)
3. Maria Carlsson   - 38 match wins (9 tournaments, 4.2 wins/tournament)

Tournament wins (informational):
- Anna Berg: 3 tournament wins (1st place finishes)
- Erik Andersson: 2 tournament wins
- Maria Carlsson: 1 tournament win
```

### Seeded Round 1 Logic

**Current State (Phase 2):**
- Round 1 uses pure random pairing
- All players have equal chance regardless of skill

**Phase 3 Enhancement:**
- Round 1 uses **weighted/seeded pairing** based on recent performance
- Better players start on higher courts (Court 1)
- Similar-skill players matched against each other

**Seeding Calculation:**
```
Player Seed = Total points from last 6 tournaments

Rules:
- Include tournaments from current season
- If player has <6 tournaments this season, include previous season
- New players (no history) = 0 seed points → start on lowest court
- Players sorted by seed points (high to low)
```

**Pairing Strategy:**
```
Sorted by seed: [P1: 850] [P2: 820] [P3: 780] [P4: 750] [P5: 680] [P6: 650] [P7: 620] [P8: 580]

Court 1 (highest): P1, P2, P3, P4 → Top 4 players
Court 2 (lowest):  P5, P6, P7, P8 → Bottom 4 players

Within Court 1:
- Team 1: P1 + P3
- Team 2: P2 + P4
(Alternate to balance)
```

**Round 2+ Behavior:**
- Unchanged - uses existing court movement algorithm
- Winners move up, losers move down
- Teammate separation applies

---

## Architecture & Database

### High-Level Architecture

```
┌─────────────────────────────────────────────┐
│           Season (Calendar Year)            │
│  ┌────────────────────────────────────────┐ │
│  │ Tournament 1 │ Tournament 2 │ ... │ T10│ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│         Global Player Registry              │
│  Erik Andersson │ Anna Berg │ Maria C. │ ...│
└─────────────────────────────────────────────┘
              ↓
      Participation Links
   (tournament_players table)
```

### Database Schema Changes

#### New Tables

**1. Seasons Table**
```sql
CREATE TABLE seasons (
    id INTEGER PRIMARY KEY,
    year INTEGER UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',  -- 'active', 'completed'
    total_tournaments INTEGER DEFAULT 10,
    summer_break_month INTEGER,  -- 6, 7, or 8 (June/July/August)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_seasons_year ON seasons(year);
CREATE INDEX idx_seasons_status ON seasons(status);
```

**2. Player Registry Table**
```sql
CREATE TABLE player_registry (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(first_name, last_name)  -- Prevent exact duplicates
);

-- Indexes
CREATE INDEX idx_player_registry_name ON player_registry(last_name, first_name);
```

**3. Tournament Players Table (Junction)**
```sql
CREATE TABLE tournament_players (
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    final_rank INTEGER,  -- 1st, 2nd, 3rd, etc. (set when tournament completes)
    total_points INTEGER,
    match_wins INTEGER,  -- Count of matches won in this tournament
    match_losses INTEGER,
    PRIMARY KEY (tournament_id, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE RESTRICT
);

-- Indexes
CREATE INDEX idx_tournament_players_tournament ON tournament_players(tournament_id);
CREATE INDEX idx_tournament_players_player ON tournament_players(player_id);
```

#### Modified Tables

**Tournaments Table**
```sql
-- Add new columns to existing tournaments table
ALTER TABLE tournaments ADD COLUMN season_id INTEGER;
ALTER TABLE tournaments ADD COLUMN month INTEGER;  -- 1-12
ALTER TABLE tournaments ADD COLUMN status TEXT DEFAULT 'active';
  -- Status values: 'setup', 'active', 'completed', 'archived'
ALTER TABLE tournaments ADD COLUMN completed_at TIMESTAMP;
ALTER TABLE tournaments ADD COLUMN archived_at TIMESTAMP;

-- Add foreign key
ALTER TABLE tournaments ADD FOREIGN KEY (season_id) REFERENCES seasons(id);

-- Add indexes
CREATE INDEX idx_tournaments_season ON tournaments(season_id);
CREATE INDEX idx_tournaments_status ON tournaments(status);
CREATE INDEX idx_tournaments_month ON tournaments(month);
```

**Players Table (Backward Compatibility)**
```sql
-- Link existing players to new registry
ALTER TABLE players ADD COLUMN registry_id INTEGER;
ALTER TABLE players ADD FOREIGN KEY (registry_id) REFERENCES player_registry(id);

-- Add index
CREATE INDEX idx_players_registry ON players(registry_id);

-- Note: Keep old players table for backward compatibility during migration
-- Eventually this table becomes legacy/read-only
```

### Database Views

**1. Player Seeding View (for Round 1)**
```sql
CREATE VIEW player_seeding AS
SELECT
    pr.id as player_id,
    pr.first_name,
    pr.last_name,
    COALESCE(SUM(tp.total_points), 0) as seed_points,
    COUNT(tp.tournament_id) as recent_tournaments
FROM player_registry pr
LEFT JOIN tournament_players tp ON pr.id = tp.player_id
LEFT JOIN tournaments t ON tp.tournament_id = t.id
WHERE t.status IN ('completed', 'archived')
  AND t.completed_at >= date('now', '-6 months')  -- Last 6 tournaments
GROUP BY pr.id, pr.first_name, pr.last_name
ORDER BY seed_points DESC;
```

**2. Season Standings View**
```sql
CREATE VIEW season_standings AS
SELECT
    s.year,
    pr.id as player_id,
    pr.first_name,
    pr.last_name,

    -- PRIMARY RANKING METRIC
    SUM(tp.match_wins) as total_match_wins,

    -- Supporting metrics
    COUNT(DISTINCT tp.tournament_id) as tournaments_played,
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 2) as wins_per_tournament,

    -- Secondary statistics
    COUNT(CASE WHEN tp.final_rank = 1 THEN 1 END) as tournament_wins,
    SUM(tp.total_points) as total_points,
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(SUM(tp.match_wins) + SUM(tp.match_losses), 0) * 100, 1)
          as win_percentage

FROM seasons s
JOIN tournaments t ON t.season_id = s.id
JOIN tournament_players tp ON tp.tournament_id = t.id
JOIN player_registry pr ON tp.player_id = pr.id
WHERE t.status IN ('completed', 'archived')
GROUP BY s.year, pr.id, pr.first_name, pr.last_name
ORDER BY s.year DESC, total_match_wins DESC, wins_per_tournament DESC;
```

**3. Player Career Statistics View**
```sql
CREATE VIEW player_career_stats AS
SELECT
    pr.id as player_id,
    pr.first_name,
    pr.last_name,

    -- Career totals
    SUM(tp.match_wins) as career_match_wins,
    SUM(tp.match_losses) as career_match_losses,
    COUNT(DISTINCT tp.tournament_id) as career_tournaments,
    COUNT(CASE WHEN tp.final_rank = 1 THEN 1 END) as career_tournament_wins,
    SUM(tp.total_points) as career_total_points,

    -- Averages
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 2) as avg_wins_per_tournament,
    ROUND(CAST(SUM(tp.total_points) AS FLOAT) /
          NULLIF(COUNT(DISTINCT tp.tournament_id), 0), 1) as avg_points_per_tournament,

    -- Win rate
    ROUND(CAST(SUM(tp.match_wins) AS FLOAT) /
          NULLIF(SUM(tp.match_wins) + SUM(tp.match_losses), 0) * 100, 1)
          as career_win_percentage,

    -- Best/worst finishes
    MIN(tp.final_rank) as best_finish,
    MAX(tp.final_rank) as worst_finish

FROM player_registry pr
LEFT JOIN tournament_players tp ON pr.id = tp.player_id
LEFT JOIN tournaments t ON tp.tournament_id = t.id
WHERE t.status IN ('completed', 'archived')
GROUP BY pr.id, pr.first_name, pr.last_name;
```

### Migration Strategy

**Phase 2 → Phase 3 Data Migration**

```python
def migrate_to_phase3():
    """
    One-time migration script to convert Phase 2 data to Phase 3 schema.
    Safe to run - preserves all existing data.
    """

    # Step 1: Create current season
    current_year = datetime.now().year
    season = create_or_get_season(year=current_year)

    # Step 2: Migrate existing tournaments to season
    for tournament in get_all_tournaments():
        tournament.season_id = season.id
        tournament.month = extract_month_from_tournament_name(tournament.name)
        tournament.status = 'active' if is_active(tournament) else 'completed'
        save(tournament)

    # Step 3: Migrate players to registry
    player_mapping = {}  # old_player_id -> registry_id

    for old_player in get_all_old_players():
        # Parse first_name, last_name from old name field
        # Assuming format: "FirstName LastName" or prompt user
        first_name, last_name = parse_name(old_player.name)

        # Check if player already exists in registry
        registry_player = find_player_in_registry(first_name, last_name)

        if not registry_player:
            # Create new registry entry
            registry_player = create_player_registry(
                first_name=first_name,
                last_name=last_name
            )

        # Link old player record to registry
        old_player.registry_id = registry_player.id
        save(old_player)

        player_mapping[old_player.id] = registry_player.id

    # Step 4: Create tournament_players records
    for tournament in get_all_tournaments():
        tournament_players_for_tournament = get_players_for_tournament(tournament.id)

        for old_player in tournament_players_for_tournament:
            registry_id = player_mapping[old_player.id]

            # Calculate final rank and stats for this tournament
            final_rank = calculate_final_rank(tournament.id, old_player.id)
            match_wins, match_losses = calculate_match_record(tournament.id, old_player.id)

            # Create tournament_players link
            create_tournament_player(
                tournament_id=tournament.id,
                player_id=registry_id,
                final_rank=final_rank,
                total_points=old_player.total_points,
                match_wins=match_wins,
                match_losses=match_losses
            )

    # Step 5: Verify migration
    verify_all_players_migrated()
    verify_all_tournaments_have_season()
    verify_all_stats_match()

    print("✅ Migration complete!")
```

**Handling Name Conflicts:**

If duplicate names found during migration:
```
Found potential duplicate: "Erik Andersson"
1. Existing in registry: Erik Andersson (created 2024-01-15)
2. Found in tournament: Erik Andersson (Tournament: March 2025)

Are these the same person?
[Y] Yes - Merge
[N] No - Keep separate (will need disambiguation)
```

---

## Stage 1: Tournament Lifecycle

### Goals
- Add tournament status management (setup, active, completed, archived)
- Link tournaments to seasons
- Provide UI to view/manage multiple tournaments

### Tournament Status Flow

```
   Setup
     ↓
  (Adding players, not started)
     ↓
   Active ←─────────┐
     ↓              │
  (Rounds playing)  │ (Can resume if needed)
     ↓              │
  Completed         │
     ↓
  (All rounds done, finalize results)
     ↓
  Archived
     ↓
  (Historical record, read-only)
```

**Status Definitions:**

- **Setup** - Tournament created, adding players, not started
- **Active** - Rounds in progress, can add/complete rounds
- **Completed** - All rounds finished, results finalized, still editable
- **Archived** - Historical record, read-only, cannot modify

### UI Changes

**Home Page Layout:**

```html
<div class="tournament-manager">

  <!-- Active Tournament -->
  <section class="current-tournament">
    <h2>Current Tournament</h2>
    <div class="tournament-card active">
      <h3>May 2025 Tournament</h3>
      <span class="status-badge active">Active - Round 3</span>
      <div class="actions">
        <a href="/tournament/5/active" class="btn-primary">Continue</a>
        <a href="/tournament/5/leaderboard" class="btn-secondary">Leaderboard</a>
      </div>
    </div>
  </section>

  <!-- Upcoming Tournaments -->
  <section class="upcoming">
    <h2>Upcoming</h2>
    <div class="tournament-card setup">
      <h3>June 2025 Tournament</h3>
      <span class="status-badge setup">Setup - 6 players</span>
      <div class="actions">
        <a href="/tournament/6/setup" class="btn-primary">Continue Setup</a>
        <button onclick="startTournament(6)" class="btn-success">Start Tournament</button>
      </div>
    </div>
  </section>

  <!-- Recent Tournaments -->
  <section class="recent">
    <h2>Recent Tournaments (2025)</h2>
    <div class="tournament-list">
      <div class="tournament-card completed">
        <h3>April 2025</h3>
        <span class="winner">🏆 Winner: Anna Berg</span>
        <a href="/tournament/4/results">View Results</a>
      </div>
      <div class="tournament-card completed">
        <h3>March 2025</h3>
        <span class="winner">🏆 Winner: Erik Andersson</span>
        <a href="/tournament/3/results">View Results</a>
      </div>
    </div>
    <a href="/season/2025/standings" class="btn-secondary">View Full Season Standings</a>
  </section>

  <!-- Create New -->
  <section class="create-new">
    <button onclick="createNewTournament()" class="btn-large btn-primary">
      + Create New Tournament
    </button>
  </section>

</div>
```

### New Routes

```python
# Season management
@app.route('/season/<int:year>/standings')
def season_standings(year):
    """Show season leaderboard"""

@app.route('/season/create', methods=['POST'])
def create_season():
    """Create new season (usually auto-created)"""

# Tournament lifecycle
@app.route('/tournament/<int:id>/complete', methods=['POST'])
def complete_tournament(id):
    """Mark tournament as completed, calculate final ranks"""

@app.route('/tournament/<int:id>/archive', methods=['POST'])
def archive_tournament(id):
    """Archive tournament (read-only)"""

@app.route('/tournament/<int:id>/results')
def tournament_results(id):
    """View historical tournament results"""
```

### Complete Tournament Logic

```python
def complete_tournament(tournament_id):
    """
    Finalize tournament results.
    1. Verify all rounds completed
    2. Calculate final rankings
    3. Update tournament_players with final_rank, match_wins, match_losses
    4. Set tournament status to 'completed'
    """
    tournament = get_tournament(tournament_id)

    # Verify all rounds complete
    incomplete_rounds = get_incomplete_rounds(tournament_id)
    if incomplete_rounds:
        flash("Cannot complete: Some rounds have incomplete matches")
        return redirect(back)

    # Calculate final rankings (based on total points)
    players_ranked = calculate_final_rankings(tournament_id)

    # Update tournament_players table
    for rank, player_id, points, wins, losses in players_ranked:
        update_tournament_player(
            tournament_id=tournament_id,
            player_id=player_id,
            final_rank=rank,
            total_points=points,
            match_wins=wins,
            match_losses=losses
        )

    # Update tournament status
    tournament.status = 'completed'
    tournament.completed_at = datetime.now()
    save(tournament)

    flash(f"Tournament completed! Winner: {players_ranked[0].name}")
    return redirect(f'/tournament/{tournament_id}/results')
```

### Season Auto-Creation

```python
@app.route('/tournament/create', methods=['GET', 'POST'])
def create_tournament():
    if request.method == 'POST':
        tournament_name = request.form['name']
        num_courts = request.form['num_courts']
        month = request.form['month']  # 1-12

        # Get or create current season
        current_year = datetime.now().year
        season = Season.query.filter_by(year=current_year).first()

        if not season:
            # Prompt user or auto-create
            flash(f"Creating new season for {current_year}")
            season = Season(year=current_year, status='active')
            db.session.add(season)
            db.session.commit()

        # Create tournament linked to season
        tournament = Tournament(
            name=tournament_name,
            num_courts=num_courts,
            season_id=season.id,
            month=month,
            status='setup'
        )
        db.session.add(tournament)
        db.session.commit()

        return redirect(f'/tournament/{tournament.id}/setup')
```

---

## Stage 2: Global Player Registry

### Goals
- Create global player pool (first_name + last_name)
- Link players to tournaments via junction table
- Implement seeded Round 1 based on recent performance

### Player Registry Features

**Player Creation:**
```html
<form action="/player/create" method="POST">
  <label>First Name:</label>
  <input type="text" name="first_name" required>

  <label>Last Name:</label>
  <input type="text" name="last_name" required>

  <button type="submit">Add Player to Registry</button>
</form>
```

**Duplicate Detection:**
```python
@app.route('/player/create', methods=['POST'])
def create_player():
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()

    # Check for exact duplicate
    existing = PlayerRegistry.query.filter_by(
        first_name=first_name,
        last_name=last_name
    ).first()

    if existing:
        flash(f"⚠️ {first_name} {last_name} already exists in registry")
        return redirect(f'/player/{existing.id}/profile')

    # Create new player
    player = PlayerRegistry(
        first_name=first_name,
        last_name=last_name
    )
    db.session.add(player)
    db.session.commit()

    flash(f"✅ Added {first_name} {last_name} to player registry")
    return redirect('/players')
```

### Tournament Setup with Player Selection

**Player Selection UI:**

```html
<div class="tournament-setup">
  <h2>May 2025 Tournament - Select Players</h2>

  <div class="player-search">
    <input type="text" id="search" placeholder="Search players...">
    <button onclick="showAddPlayerForm()">+ Add New Player</button>
  </div>

  <div class="player-list">
    <h3>Available Players (Sorted by seed)</h3>

    <label class="player-option">
      <input type="checkbox" name="players[]" value="1">
      <div class="player-info">
        <span class="name">Andersson, Erik</span>
        <span class="seed">Seed: 850 pts</span>
        <span class="last-played">Last: April 2025</span>
        <span class="predicted-court">→ Court 1 (est.)</span>
      </div>
    </label>

    <label class="player-option">
      <input type="checkbox" name="players[]" value="2">
      <div class="player-info">
        <span class="name">Berg, Anna</span>
        <span class="seed">Seed: 820 pts</span>
        <span class="last-played">Last: April 2025</span>
        <span class="predicted-court">→ Court 1 (est.)</span>
      </div>
    </label>

    <!-- More players... -->

    <label class="player-option new-player">
      <input type="checkbox" name="players[]" value="15">
      <div class="player-info">
        <span class="name">Nilsson, Gustav</span>
        <span class="seed">Seed: 0 pts (New Player)</span>
        <span class="last-played">First tournament</span>
        <span class="predicted-court">→ Court 2 (est.)</span>
      </div>
    </label>

  </div>

  <div class="selected-count">
    Selected: <span id="count">0</span> players
    (Need: <span id="required">8</span> for 2 courts)
  </div>

  <button type="submit" class="btn-primary btn-large">
    Start Tournament with Selected Players
  </button>
</div>
```

### Seeded Round 1 Implementation

**Algorithm:**

```python
def generate_seeded_round1_pairings(tournament_id, num_courts):
    """
    Generate Round 1 pairings based on player seeding.
    Top players on Court 1, bottom players on last court.
    """
    tournament = get_tournament(tournament_id)

    # Get players for this tournament with their seeds
    players_with_seeds = db.session.query(
        PlayerRegistry.id,
        PlayerRegistry.first_name,
        PlayerRegistry.last_name,
        player_seeding.c.seed_points
    ).join(
        tournament_players,
        tournament_players.c.player_id == PlayerRegistry.id
    ).outerjoin(
        player_seeding,
        player_seeding.c.player_id == PlayerRegistry.id
    ).filter(
        tournament_players.c.tournament_id == tournament_id
    ).order_by(
        player_seeding.c.seed_points.desc().nullslast()
    ).all()

    # Sort: High seed → Low seed
    # players_with_seeds is already sorted by query

    players_per_court = 4
    court_assignments = []

    for court_idx in range(num_courts):
        start = court_idx * players_per_court
        end = start + players_per_court

        if end > len(players_with_seeds):
            break

        # Get 4 players for this court
        court_players = players_with_seeds[start:end]
        player_ids = [p.id for p in court_players]

        # Assign teams (alternate to balance)
        # Team 1: P1 + P3
        # Team 2: P2 + P4
        court_assignment = [
            player_ids[0],  # P1
            player_ids[2],  # P3
            player_ids[1],  # P2
            player_ids[3]   # P4
        ]

        court_assignments.append(court_assignment)

    return court_assignments
```

**Modified start_round Route:**

```python
@app.route('/tournament/<int:tournament_id>/start_round', methods=['POST'])
def start_round(tournament_id):
    tournament = get_tournament(tournament_id)
    num_courts = tournament.num_courts

    # Create new round
    round_number = get_next_round_number(tournament_id)
    new_round = Round(
        tournament_id=tournament_id,
        round_number=round_number
    )
    db.session.add(new_round)
    db.session.commit()

    if round_number == 1:
        # SEEDED ROUND 1
        court_assignments = generate_seeded_round1_pairings(tournament_id, num_courts)

        flash(f"Round 1 started with seeded pairings (based on recent performance)")
    else:
        # ROUND 2+: Use existing movement algorithm
        previous_matches = get_previous_round_matches(tournament_id, round_number - 1)
        court_assignments = generate_next_round_pairings(previous_matches, num_courts)

        flash(f"Round {round_number} started! Winners moved up, losers moved down.")

    # Create matches from assignments
    for court_num, player_ids in enumerate(court_assignments, start=1):
        match = Match(
            round_id=new_round.id,
            court_number=court_num,
            player1_id=player_ids[0],
            player2_id=player_ids[1],
            player3_id=player_ids[2],
            player4_id=player_ids[3]
        )
        db.session.add(match)

    db.session.commit()
    return redirect(f'/tournament/{tournament_id}/active')
```

---

## Stage 3: Player Profiles

### Goals
- Individual player profile pages
- Statistics across all tournaments
- Tournament history view

### Player Profile Page

**URL Structure:**
```
/player/<int:player_id>/profile
```

**Profile Template:**

```html
<div class="player-profile">

  <!-- Header -->
  <div class="profile-header">
    <h1>{{ player.first_name }} {{ player.last_name }}</h1>
  </div>

  <!-- Current Season Stats -->
  <section class="season-stats">
    <h2>Current Season ({{ current_season.year }})</h2>
    <div class="stat-grid">
      <div class="stat-card primary">
        <span class="value">{{ season_stats.total_match_wins }}</span>
        <span class="label">Match Wins</span>
      </div>
      <div class="stat-card">
        <span class="value">#{{ season_stats.rank }}</span>
        <span class="label">Season Rank</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ season_stats.tournaments_played }} / {{ current_season.total_tournaments }}</span>
        <span class="label">Tournaments</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ season_stats.wins_per_tournament }}</span>
        <span class="label">Wins/Tournament</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ season_stats.total_points }}</span>
        <span class="label">Total Points</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ season_stats.win_percentage }}%</span>
        <span class="label">Win Rate</span>
      </div>
    </div>
  </section>

  <!-- Tournament History (Current Season) -->
  <section class="tournament-history">
    <h2>Tournament History ({{ current_season.year }})</h2>
    <table class="history-table">
      <thead>
        <tr>
          <th>Month</th>
          <th>Rank</th>
          <th>Points</th>
          <th>Wins</th>
          <th>Losses</th>
        </tr>
      </thead>
      <tbody>
        {% for tournament in tournament_history %}
        <tr>
          <td>
            <a href="/tournament/{{ tournament.id }}/results">
              {{ tournament.month_name }} {{ tournament.year }}
            </a>
          </td>
          <td>
            <span class="rank-badge rank-{{ tournament.final_rank }}">
              {{ tournament.final_rank }}{{ tournament.rank_suffix }}
            </span>
          </td>
          <td>{{ tournament.total_points }}</td>
          <td>{{ tournament.match_wins }}</td>
          <td>{{ tournament.match_losses }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <!-- Career Stats -->
  <section class="career-stats">
    <h2>Career Statistics (All Seasons)</h2>
    <div class="stat-grid">
      <div class="stat-card">
        <span class="value">{{ career.total_matches }}</span>
        <span class="label">Total Matches</span>
        <span class="detail">{{ career.match_wins }}W - {{ career.match_losses }}L</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ career.tournament_wins }}</span>
        <span class="label">Tournament Wins</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ career.tournaments_played }}</span>
        <span class="label">Tournaments Played</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ career.avg_wins_per_tournament }}</span>
        <span class="label">Avg Wins/Tournament</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ career.best_finish }}{{ career.best_finish_suffix }}</span>
        <span class="label">Best Finish</span>
      </div>
      <div class="stat-card">
        <span class="value">{{ career.win_percentage }}%</span>
        <span class="label">Career Win Rate</span>
      </div>
    </div>
  </section>

  <!-- Actions -->
  <div class="profile-actions">
    <a href="/player/{{ player.id }}/export" class="btn-secondary">
      Export Player History (CSV)
    </a>
    <a href="/season/{{ current_season.year }}/standings" class="btn-secondary">
      Back to Season Standings
    </a>
  </div>

</div>
```

### Profile Route Implementation

```python
@app.route('/player/<int:player_id>/profile')
def player_profile(player_id):
    player = PlayerRegistry.query.get_or_404(player_id)
    current_season = get_current_season()

    # Current season stats
    season_stats = db.session.query(
        season_standings
    ).filter(
        season_standings.c.player_id == player_id,
        season_standings.c.year == current_season.year
    ).first()

    # Tournament history (current season)
    tournament_history = db.session.query(
        Tournament.id,
        Tournament.month,
        TournamentPlayers.final_rank,
        TournamentPlayers.total_points,
        TournamentPlayers.match_wins,
        TournamentPlayers.match_losses
    ).join(
        TournamentPlayers, Tournament.id == TournamentPlayers.tournament_id
    ).filter(
        TournamentPlayers.player_id == player_id,
        Tournament.season_id == current_season.id,
        Tournament.status.in_(['completed', 'archived'])
    ).order_by(
        Tournament.month.asc()
    ).all()

    # Career stats
    career = db.session.query(
        player_career_stats
    ).filter(
        player_career_stats.c.player_id == player_id
    ).first()

    return render_template(
        'player_profile.html',
        player=player,
        current_season=current_season,
        season_stats=season_stats,
        tournament_history=tournament_history,
        career=career
    )
```

### Navigation to Profiles

**Clickable Names in Leaderboard:**

```html
<!-- season_standings.html -->
<table class="leaderboard">
  <thead>
    <tr>
      <th>Rank</th>
      <th>Player</th>
      <th>Match Wins</th>
      <th>Tournaments</th>
      <th>Wins/Tournament</th>
      <th>Points</th>
    </tr>
  </thead>
  <tbody>
    {% for player in standings %}
    <tr>
      <td class="rank">{{ loop.index }}</td>
      <td class="player-name">
        <a href="/player/{{ player.player_id }}/profile">
          {{ player.last_name }}, {{ player.first_name }}
        </a>
      </td>
      <td class="primary-metric">{{ player.total_match_wins }}</td>
      <td>{{ player.tournaments_played }}</td>
      <td>{{ player.wins_per_tournament }}</td>
      <td>{{ player.total_points }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

**Clickable Names in Tournament Results:**

```html
<!-- tournament_results.html -->
<h2>March 2025 Tournament - Final Results</h2>
<ol class="final-standings">
  {% for player in results %}
  <li class="rank-{{ player.final_rank }}">
    <span class="rank">{{ player.final_rank }}</span>
    <a href="/player/{{ player.player_id }}/profile" class="player-name">
      {{ player.first_name }} {{ player.last_name }}
    </a>
    <span class="stats">
      {{ player.total_points }} pts |
      {{ player.match_wins }}W-{{ player.match_losses }}L
    </span>
  </li>
  {% endfor %}
</ol>
```

---

## Stage 4: CSV Exports

### Goals
- Export season standings
- Export tournament results
- Export player statistics
- Export match details

### Export Types

#### 1. Season Standings Export

**Route:**
```python
@app.route('/export/season/<int:year>/standings')
def export_season_standings(year):
    # Query season standings
    standings = db.session.query(season_standings).filter(
        season_standings.c.year == year
    ).all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        'Rank',
        'First Name',
        'Last Name',
        'Match Wins',
        'Tournaments Played',
        'Wins per Tournament',
        'Total Points',
        'Win Percentage',
        'Tournament Wins'
    ])

    # Data rows
    for rank, player in enumerate(standings, start=1):
        writer.writerow([
            rank,
            player.first_name,
            player.last_name,
            player.total_match_wins,
            player.tournaments_played,
            player.wins_per_tournament,
            player.total_points,
            player.win_percentage,
            player.tournament_wins
        ])

    # Return as download
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'season_{year}_standings.csv'
    )
```

**Sample Output:**
```csv
Rank,First Name,Last Name,Match Wins,Tournaments Played,Wins per Tournament,Total Points,Win Percentage,Tournament Wins
1,Anna,Berg,45,10,4.50,1050,72.5,3
2,Erik,Andersson,42,10,4.20,1020,68.5,2
3,Maria,Carlsson,38,9,4.22,890,65.2,1
```

#### 2. Player Statistics Export

**Route:**
```python
@app.route('/export/players/stats')
def export_player_stats():
    # Query all players with career stats
    players = db.session.query(player_career_stats).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Player ID',
        'First Name',
        'Last Name',
        'Career Match Wins',
        'Career Match Losses',
        'Career Tournaments',
        'Career Tournament Wins',
        'Avg Wins per Tournament',
        'Avg Points per Tournament',
        'Career Win Percentage',
        'Best Finish',
        'Worst Finish'
    ])

    for player in players:
        writer.writerow([
            player.player_id,
            player.first_name,
            player.last_name,
            player.career_match_wins,
            player.career_match_losses,
            player.career_tournaments,
            player.career_tournament_wins,
            player.avg_wins_per_tournament,
            player.avg_points_per_tournament,
            player.career_win_percentage,
            player.best_finish,
            player.worst_finish
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='player_statistics.csv'
    )
```

#### 3. Tournament Results Export

**Route:**
```python
@app.route('/export/tournament/<int:tournament_id>/results')
def export_tournament_results(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)

    # Get final results
    results = db.session.query(
        TournamentPlayers.final_rank,
        PlayerRegistry.first_name,
        PlayerRegistry.last_name,
        TournamentPlayers.total_points,
        TournamentPlayers.match_wins,
        TournamentPlayers.match_losses
    ).join(
        PlayerRegistry, TournamentPlayers.player_id == PlayerRegistry.id
    ).filter(
        TournamentPlayers.tournament_id == tournament_id
    ).order_by(
        TournamentPlayers.final_rank.asc()
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Rank',
        'First Name',
        'Last Name',
        'Total Points',
        'Match Wins',
        'Match Losses',
        'Win Percentage'
    ])

    for result in results:
        total_matches = result.match_wins + result.match_losses
        win_pct = round(result.match_wins / total_matches * 100, 1) if total_matches > 0 else 0

        writer.writerow([
            result.final_rank,
            result.first_name,
            result.last_name,
            result.total_points,
            result.match_wins,
            result.match_losses,
            win_pct
        ])

    output.seek(0)
    month_name = get_month_name(tournament.month)
    filename = f'tournament_{month_name}_{tournament.season.year}_results.csv'

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )
```

#### 4. Match-by-Match Export (Detailed)

**Route:**
```python
@app.route('/export/tournament/<int:tournament_id>/matches')
def export_tournament_matches(tournament_id):
    # Get all matches with player names
    matches = db.session.query(
        Round.round_number,
        Match.court_number,
        PlayerRegistry1.first_name.label('p1_first'),
        PlayerRegistry1.last_name.label('p1_last'),
        PlayerRegistry2.first_name.label('p2_first'),
        PlayerRegistry2.last_name.label('p2_last'),
        PlayerRegistry3.first_name.label('p3_first'),
        PlayerRegistry3.last_name.label('p3_last'),
        PlayerRegistry4.first_name.label('p4_first'),
        PlayerRegistry4.last_name.label('p4_last'),
        Score1.points.label('p1_score'),
        Score2.points.label('p2_score'),
        Score3.points.label('p3_score'),
        Score4.points.label('p4_score'),
        Match.winning_team
    ).join(
        Round, Match.round_id == Round.id
    ).join(
        PlayerRegistry1, Match.player1_id == PlayerRegistry1.id
    ).join(
        PlayerRegistry2, Match.player2_id == PlayerRegistry2.id
    ).join(
        PlayerRegistry3, Match.player3_id == PlayerRegistry3.id
    ).join(
        PlayerRegistry4, Match.player4_id == PlayerRegistry4.id
    ).outerjoin(
        Score1, (Score.match_id == Match.id) & (Score.player_id == Match.player1_id)
    )  # ... (similar for Score2-4)
    .filter(
        Round.tournament_id == tournament_id
    ).order_by(
        Round.round_number.asc(),
        Match.court_number.asc()
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Round',
        'Court',
        'Team 1 Player 1',
        'Team 1 Player 2',
        'Team 1 Score',
        'Team 2 Player 1',
        'Team 2 Player 2',
        'Team 2 Score',
        'Winner'
    ])

    for match in matches:
        team1_score = (match.p1_score or 0) + (match.p2_score or 0)
        team2_score = (match.p3_score or 0) + (match.p4_score or 0)

        writer.writerow([
            match.round_number,
            match.court_number,
            f"{match.p1_first} {match.p1_last}",
            f"{match.p2_first} {match.p2_last}",
            team1_score,
            f"{match.p3_first} {match.p3_last}",
            f"{match.p4_first} {match.p4_last}",
            team2_score,
            f"Team {match.winning_team}" if match.winning_team else "Incomplete"
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'tournament_{tournament_id}_matches.csv'
    )
```

### Export UI Integration

**Season Standings Page:**
```html
<div class="season-header">
  <h1>Season {{ season.year }} Standings</h1>
  <div class="export-options">
    <button class="btn-secondary" onclick="exportDropdown()">
      Export ▼
    </button>
    <div class="dropdown-menu">
      <a href="/export/season/{{ season.year }}/standings">
        Season Standings (CSV)
      </a>
      <a href="/export/players/stats">
        All Player Stats (CSV)
      </a>
    </div>
  </div>
</div>
```

**Tournament Results Page:**
```html
<div class="tournament-header">
  <h1>{{ tournament.name }} - Results</h1>
  <div class="export-options">
    <a href="/export/tournament/{{ tournament.id }}/results" class="btn-secondary">
      Export Results (CSV)
    </a>
    <a href="/export/tournament/{{ tournament.id }}/matches" class="btn-secondary">
      Export Match Details (CSV)
    </a>
  </div>
</div>
```

**Player Profile Page:**
```html
<div class="profile-actions">
  <a href="/export/player/{{ player.id }}/history" class="btn-secondary">
    Export Player History (CSV)
  </a>
</div>
```

---

## Testing Strategy

### Unit Tests

#### Database Models
```python
# test_models.py
def test_season_creation():
    season = Season(year=2025, status='active')
    assert season.year == 2025
    assert season.status == 'active'

def test_player_registry_unique_constraint():
    player1 = PlayerRegistry(first_name="Erik", last_name="Andersson")
    db.session.add(player1)
    db.session.commit()

    # Should raise error on duplicate
    player2 = PlayerRegistry(first_name="Erik", last_name="Andersson")
    with pytest.raises(IntegrityError):
        db.session.add(player2)
        db.session.commit()

def test_tournament_status_transitions():
    tournament = Tournament(status='setup')
    assert tournament.status == 'setup'

    tournament.status = 'active'
    assert tournament.status == 'active'

    tournament.status = 'completed'
    assert tournament.completed_at is not None
```

#### Business Logic
```python
# test_seeding.py
def test_player_seeding_calculation():
    # Create test data: player with 3 tournaments in last 6 months
    player = create_test_player("Erik", "Andersson")

    tournament1 = create_test_tournament(month=1, year=2025)
    add_tournament_result(tournament1, player, points=100, rank=2)

    tournament2 = create_test_tournament(month=2, year=2025)
    add_tournament_result(tournament2, player, points=120, rank=1)

    tournament3 = create_test_tournament(month=3, year=2025)
    add_tournament_result(tournament3, player, points=95, rank=3)

    # Calculate seed
    seed = calculate_player_seed(player.id)
    assert seed == 315  # 100 + 120 + 95

def test_seeded_round1_pairings():
    tournament = create_test_tournament(num_courts=2)

    # Add 8 players with different seeds
    players = [
        create_player_with_seed("P1", 850),
        create_player_with_seed("P2", 820),
        create_player_with_seed("P3", 780),
        create_player_with_seed("P4", 750),
        create_player_with_seed("P5", 680),
        create_player_with_seed("P6", 650),
        create_player_with_seed("P7", 620),
        create_player_with_seed("P8", 580),
    ]

    # Generate pairings
    pairings = generate_seeded_round1_pairings(tournament.id, num_courts=2)

    # Verify Court 1 has top 4 players
    court1 = pairings[0]
    assert set(court1) == {players[0].id, players[1].id, players[2].id, players[3].id}

    # Verify Court 2 has bottom 4
    court2 = pairings[1]
    assert set(court2) == {players[4].id, players[5].id, players[6].id, players[7].id}

def test_season_standings_calculation():
    season = create_test_season(2025)
    player = create_test_player("Erik", "Andersson")

    # Create multiple tournaments with results
    for month in range(1, 11):
        tournament = create_test_tournament(season_id=season.id, month=month)
        add_tournament_result(
            tournament,
            player,
            match_wins=5,
            match_losses=2,
            points=100
        )

    # Calculate standings
    standings = get_season_standings(2025)

    player_standing = next(s for s in standings if s.player_id == player.id)
    assert player_standing.total_match_wins == 50  # 5 wins * 10 tournaments
    assert player_standing.tournaments_played == 10
    assert player_standing.wins_per_tournament == 5.0
```

#### CSV Export
```python
# test_exports.py
def test_season_standings_csv_export():
    # Setup test season with data
    season = setup_test_season_with_results()

    # Export CSV
    response = client.get(f'/export/season/{season.year}/standings')

    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/csv'

    # Parse CSV
    csv_data = response.data.decode('utf-8')
    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)

    # Verify headers
    assert 'Rank' in rows[0]
    assert 'Match Wins' in rows[0]
    assert 'Wins per Tournament' in rows[0]

    # Verify data
    assert len(rows) > 0
    assert rows[0]['Rank'] == '1'
```

### Integration Tests

#### Tournament Lifecycle Flow
```python
def test_complete_tournament_lifecycle():
    # Create season
    season = create_season(2025)

    # Create tournament
    tournament = create_tournament(
        name="March 2025",
        season_id=season.id,
        month=3,
        num_courts=2
    )
    assert tournament.status == 'setup'

    # Add players
    players = add_players_to_tournament(tournament.id, count=8)

    # Start tournament (Round 1 - seeded)
    start_round(tournament.id)
    assert tournament.status == 'active'

    # Complete all rounds
    for round_num in range(1, 8):
        complete_round_matches(tournament.id, round_num)
        if round_num < 7:
            start_round(tournament.id)

    # Complete tournament
    complete_tournament(tournament.id)
    assert tournament.status == 'completed'

    # Verify final rankings calculated
    results = get_tournament_results(tournament.id)
    assert all(r.final_rank is not None for r in results)

    # Archive
    archive_tournament(tournament.id)
    assert tournament.status == 'archived'
```

#### Player Migration
```python
def test_phase2_to_phase3_migration():
    # Setup Phase 2 data
    old_tournament = create_old_style_tournament()
    old_players = create_old_style_players(
        names=["Erik Andersson", "Anna Berg", "Maria Carlsson"]
    )

    # Run migration
    migrate_to_phase3()

    # Verify registry created
    assert PlayerRegistry.query.count() == 3

    # Verify names split correctly
    erik = PlayerRegistry.query.filter_by(
        first_name="Erik",
        last_name="Andersson"
    ).first()
    assert erik is not None

    # Verify tournament_players created
    tp_count = TournamentPlayers.query.filter_by(
        tournament_id=old_tournament.id
    ).count()
    assert tp_count == 3

    # Verify old players linked
    old_erik = Players.query.filter_by(name="Erik Andersson").first()
    assert old_erik.registry_id == erik.id
```

### Manual Testing Checklist

**Stage 1: Tournament Lifecycle**
- [ ] Create new season (2025)
- [ ] Create tournament in new season
- [ ] Complete tournament → verify status = 'completed'
- [ ] Archive tournament → verify read-only
- [ ] Home page shows correct tournament states
- [ ] Cannot start round in archived tournament

**Stage 2: Player Registry**
- [ ] Add new player with first/last name
- [ ] Attempt duplicate player → see warning
- [ ] Select existing players for tournament
- [ ] Add new player during tournament setup
- [ ] Verify seeding shown in player list
- [ ] Start Round 1 → verify seeded pairing (top players on Court 1)

**Stage 3: Player Profiles**
- [ ] Click player name from leaderboard → profile loads
- [ ] Profile shows current season stats
- [ ] Profile shows tournament history
- [ ] Profile shows career statistics
- [ ] Stats match database queries

**Stage 4: CSV Exports**
- [ ] Export season standings → verify CSV format
- [ ] Export tournament results → verify data
- [ ] Export player history → verify calculations
- [ ] Open CSV in Excel/Google Sheets → verify readable

---

## Implementation Rollout

### Week 1-2: Stage 1 - Tournament Lifecycle

**Tasks:**
1. Create database migration script
   - Add seasons table
   - Add player_registry table
   - Add tournament_players table
   - Alter tournaments table (add season_id, month, status)
   - Alter players table (add registry_id)

2. Run data migration
   - Create 2025 season (or current year)
   - Link existing tournaments to season
   - Migrate existing players to registry
   - Create tournament_players records
   - Verify data integrity

3. Implement tournament status management
   - Add complete_tournament() function
   - Add archive_tournament() function
   - Update routes to handle status

4. Update home page UI
   - Show current/upcoming/recent tournaments
   - Filter by status
   - Add "Complete Tournament" button

5. Test tournament lifecycle
   - Create → Start → Complete → Archive flow
   - Verify status transitions
   - Verify cannot modify archived tournaments

**Deployment:**
- Run migration in production
- Test with current active tournament
- Archive old completed tournaments

---

### Week 3: Stage 2 - Player Registry

**Tasks:**
1. Implement player selection UI
   - Player list with search
   - Show seed points
   - Add new player form during setup

2. Implement seeded Round 1
   - Calculate player seeds (last 6 tournaments)
   - Generate seeded pairings
   - Modify start_round() to use seeding for Round 1

3. Update tournament setup flow
   - Select players from registry
   - Preview starting courts based on seeds
   - Validate player count

4. Test seeded Round 1
   - Create tournament with mix of experienced/new players
   - Verify top players on Court 1
   - Verify new players on lower courts
   - Verify Round 2+ still uses movement algorithm

**Deployment:**
- Deploy seeded Round 1 feature
- Test with real tournament
- Gather user feedback on seeding

---

### Week 4: Stage 3 - Player Profiles

**Tasks:**
1. Create player profile template
   - Design profile layout
   - Implement stat cards
   - Add tournament history table

2. Implement profile routes
   - /player/<id>/profile
   - Calculate season stats
   - Calculate career stats

3. Add navigation links
   - Make player names clickable in leaderboard
   - Make names clickable in tournament results
   - Add breadcrumbs

4. Test player profiles
   - Click various players from different pages
   - Verify stats calculations
   - Verify tournament history accurate

**Deployment:**
- Deploy player profiles
- Add links throughout existing pages
- Test on mobile devices

---

### Week 5: Stage 4 - CSV Exports

**Tasks:**
1. Implement CSV export routes
   - Season standings export
   - Tournament results export
   - Player statistics export
   - Match details export

2. Add export UI
   - Export buttons on season page
   - Export buttons on tournament results page
   - Export button on player profile

3. Test CSV exports
   - Export each type
   - Open in Excel/Google Sheets
   - Verify data accuracy
   - Test with special characters in names

4. Documentation
   - Add export instructions to README
   - Document CSV format
   - Add usage examples

**Deployment:**
- Deploy CSV exports
- Test all export types
- Provide sample CSV to users

---

### Post-Rollout

**Week 6: Monitoring & Refinement**
- Monitor for bugs
- Gather user feedback
- Fix any issues
- Optimize slow queries
- Add indexes if needed

**Week 7: Documentation & Cleanup**
- Update README with Phase 3 features
- Create user guide
- Update daily summary
- Clean up any dead code
- Remove old migration scripts if safe

---

## Success Criteria

### Phase 3 Complete When:

**Functional Requirements:**
- ✅ Can create and manage multiple tournaments per season
- ✅ Can archive completed tournaments
- ✅ Players persist across all tournaments with first/last name
- ✅ Round 1 uses seeded pairing based on last 6 tournaments
- ✅ Player profiles show statistics across all tournaments
- ✅ Season standings show match wins (primary metric)
- ✅ Can export CSV data (season, tournaments, players)

**Technical Requirements:**
- ✅ All database migrations complete without data loss
- ✅ All tests passing (unit + integration)
- ✅ Performance acceptable (<2s page loads)
- ✅ Mobile-responsive (all new pages)
- ✅ Backward compatible with Phase 2 data

**User Experience:**
- ✅ Can navigate between tournaments easily
- ✅ Can view player history and stats
- ✅ Can export data for external analysis
- ✅ Seeded Round 1 feels fair to players
- ✅ Tournament lifecycle is clear and intuitive

---

## Future Enhancements (Phase 4+)

**Not included in Phase 3:**

1. **Tournament Templates**
   - Save tournament configurations for reuse
   - Quick-create tournaments from template

2. **Player Check-in**
   - Mark players present before tournament
   - Replace absent players

3. **Match Timer**
   - Countdown timer per match
   - Automatic alerts when time up

4. **Advanced Algorithms**
   - Graph-based teammate separation
   - Multi-round history tracking
   - Weighted court movement by score margin

5. **Admin Features**
   - Admin password protection
   - User roles and permissions
   - Tournament settings configuration

6. **Mobile App**
   - Native iOS/Android app
   - Offline support
   - Push notifications

---

## Appendix

### Database Schema Diagram

```
seasons
├── id (PK)
├── year
├── status
├── total_tournaments
└── summer_break_month

player_registry
├── id (PK)
├── first_name
├── last_name
└── created_at

tournaments
├── id (PK)
├── name
├── num_courts
├── season_id (FK → seasons)
├── month
├── status
├── completed_at
└── archived_at

tournament_players (junction)
├── tournament_id (FK → tournaments)
├── player_id (FK → player_registry)
├── final_rank
├── total_points
├── match_wins
└── match_losses

players (legacy - Phase 2)
├── id (PK)
├── name
├── total_points
└── registry_id (FK → player_registry)

rounds
├── id (PK)
└── tournament_id (FK → tournaments)

matches
├── id (PK)
├── round_id (FK → rounds)
├── court_number
├── player1_id (FK → players)
├── player2_id (FK → players)
├── player3_id (FK → players)
├── player4_id (FK → players)
├── winning_team
└── completed

scores
├── id (PK)
├── match_id (FK → matches)
├── player_id (FK → players)
└── points
```

### Key Metrics Reference

**Primary Ranking Metric:**
- **Match Wins** - Total individual matches won in the season
- Season champion = Most match wins

**Secondary Metrics:**
- **Wins per Tournament** - Normalizes for different participation levels
- **Tournament Wins** - Number of 1st place finishes (informational)
- **Total Points** - Accumulated points (informational)
- **Win Percentage** - Match wins / total matches

**Seeding Metric:**
- **Seed Points** - Total points from last 6 tournaments
- Used only for Round 1 court assignments

---

**End of Design Document**
