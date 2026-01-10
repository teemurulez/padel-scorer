# Phase 3 Stage 1: Tournament Lifecycle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add tournament lifecycle management (status tracking, completion, archiving) and global player registry foundation.

**Architecture:** Builds on Phase 2 season management. Adds player_registry table for persistent player tracking across tournaments, tournament_players junction table for stats, and tournament status flow (setup → active → completed → archived). Existing players table becomes legacy with registry_id link.

**Tech Stack:** Python 3.9, Flask 3.1, SQLite, pytest

---

## Task 1: Player Registry Schema

**Files:**
- Modify: `database.py` (add player_registry table creation)
- Create: `tests/test_player_registry_schema.py`

**Step 1: Write the failing test**

Create `tests/test_player_registry_schema.py`:

```python
import sqlite3
import pytest


def test_player_registry_table_exists():
    """Test that player_registry table exists with correct columns"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='player_registry'
    """)
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(player_registry)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'id' in columns
    assert 'first_name' in columns
    assert 'last_name' in columns
    assert 'created_at' in columns

    conn.close()


def test_player_registry_unique_constraint():
    """Test that duplicate first_name + last_name is prevented"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Insert first player
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("TestFirst", "TestLast"))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            """, ("TestFirst", "TestLast"))
            conn.commit()
    finally:
        # Cleanup
        cursor.execute("""
            DELETE FROM player_registry
            WHERE first_name = 'TestFirst' AND last_name = 'TestLast'
        """)
        conn.commit()
        conn.close()


def test_player_registry_indexes_exist():
    """Test that indexes are created for performance"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='player_registry'
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    # Should have index on name columns
    assert any('player_registry' in idx.lower() for idx in indexes)

    conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_player_registry_schema.py -v
```

Expected: FAIL with "no such table: player_registry"

**Step 3: Implement player_registry table in database.py**

Add to `database.py` after seasons table creation (around line 143):

```python
    # Player Registry table (Phase 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(first_name, last_name)
        )
    ''')

    # Create index for player name lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_player_registry_name
        ON player_registry(last_name, first_name)
    ''')
```

**Step 4: Run test to verify it passes**

Run:
```bash
rm -f instance/padel.db && source venv/bin/activate && python database.py && python -m pytest tests/test_player_registry_schema.py -v
```

Expected: 3/3 tests PASS

**Step 5: Commit**

```bash
git add database.py tests/test_player_registry_schema.py
git commit -m "feat: add player_registry table for persistent player tracking

Phase 3 Stage 1: Create player_registry table with first_name,
last_name, and unique constraint to prevent duplicates.

- Added player_registry table schema
- Added index on (last_name, first_name) for lookups
- Tests verify table structure and unique constraint

3/3 tests passing."
```

---

## Task 2: Tournament Players Junction Table

**Files:**
- Modify: `database.py` (add tournament_players table)
- Create: `tests/test_tournament_players_schema.py`

**Step 1: Write the failing test**

Create `tests/test_tournament_players_schema.py`:

```python
import sqlite3
import pytest


def test_tournament_players_table_exists():
    """Test that tournament_players junction table exists"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tournament_players'
    """)
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(tournament_players)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'tournament_id' in columns
    assert 'player_id' in columns
    assert 'final_rank' in columns
    assert 'total_points' in columns
    assert 'match_wins' in columns
    assert 'match_losses' in columns

    conn.close()


def test_tournament_players_foreign_keys():
    """Test that foreign keys are properly defined"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_key_list(tournament_players)")
    foreign_keys = cursor.fetchall()

    # Should have FK to tournaments and player_registry
    fk_tables = [fk[2] for fk in foreign_keys]
    assert 'tournaments' in fk_tables
    assert 'player_registry' in fk_tables

    conn.close()


def test_tournament_players_composite_primary_key():
    """Test that composite primary key prevents duplicate entries"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create test season, tournament, and player
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id)
            VALUES (?, ?, ?)
        """, ("Test Tournament", 2, season_id))
        tournament_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Test", "Player"))
        player_id = cursor.lastrowid

        conn.commit()

        # Insert first record
        cursor.execute("""
            INSERT INTO tournament_players (tournament_id, player_id, total_points)
            VALUES (?, ?, ?)
        """, (tournament_id, player_id, 100))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO tournament_players (tournament_id, player_id, total_points)
                VALUES (?, ?, ?)
            """, (tournament_id, player_id, 150))
            conn.commit()
    finally:
        # Cleanup
        cursor.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM player_registry WHERE id = ?", (player_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_tournament_players_schema.py -v
```

Expected: FAIL with "no such table: tournament_players"

**Step 3: Implement tournament_players table in database.py**

Add to `database.py` after player_registry table creation:

```python
    # Tournament Players junction table (Phase 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            final_rank INTEGER,
            total_points INTEGER DEFAULT 0,
            match_wins INTEGER DEFAULT 0,
            match_losses INTEGER DEFAULT 0,
            PRIMARY KEY (tournament_id, player_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES player_registry(id) ON DELETE RESTRICT
        )
    ''')

    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament
        ON tournament_players(tournament_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_player
        ON tournament_players(player_id)
    ''')
```

**Step 4: Run test to verify it passes**

Run:
```bash
rm -f instance/padel.db && source venv/bin/activate && python database.py && python -m pytest tests/test_tournament_players_schema.py -v
```

Expected: 3/3 tests PASS

**Step 5: Commit**

```bash
git add database.py tests/test_tournament_players_schema.py
git commit -m "feat: add tournament_players junction table

Phase 3 Stage 1: Create many-to-many relationship between tournaments
and players with statistics tracking.

- Added tournament_players junction table
- Composite primary key (tournament_id, player_id)
- Foreign keys with CASCADE/RESTRICT delete rules
- Stats columns: final_rank, total_points, match_wins, match_losses
- Indexes for query performance

3/3 tests passing."
```

---

## Task 3: Tournament Status Column

**Files:**
- Modify: `database.py` (add status, completed_at, archived_at to tournaments)
- Create: `tests/test_tournament_status.py`

**Step 1: Write the failing test**

Create `tests/test_tournament_status.py`:

```python
import sqlite3
import pytest


def test_tournaments_status_column_exists():
    """Test that tournaments table has status column"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(tournaments)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'status' in columns
    assert 'completed_at' in columns
    assert 'archived_at' in columns

    conn.close()


def test_tournament_status_default_value():
    """Test that new tournaments default to 'setup' status"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create tournament without specifying status
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id)
            VALUES (?, ?, ?)
        """, ("Test Tournament", 2, season_id))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Check default status
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status == 'setup'
    finally:
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()


def test_tournament_status_transitions():
    """Test that tournament status can transition through lifecycle"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season and tournament
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "setup"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Transition to active
        cursor.execute("UPDATE tournaments SET status = ? WHERE id = ?", ("active", tournament_id))
        conn.commit()

        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        assert cursor.fetchone()[0] == 'active'

        # Transition to completed
        cursor.execute("""
            UPDATE tournaments SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("completed", tournament_id))
        conn.commit()

        cursor.execute("SELECT status, completed_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'completed'
        assert row[1] is not None

        # Transition to archived
        cursor.execute("""
            UPDATE tournaments SET status = ?, archived_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("archived", tournament_id))
        conn.commit()

        cursor.execute("SELECT status, archived_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'archived'
        assert row[1] is not None
    finally:
        cursor.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        cursor.execute("DELETE FROM seasons WHERE id = ?", (season_id,))
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_tournament_status.py -v
```

Expected: FAIL with "no such column: status"

**Step 3: Add status columns to tournaments table in database.py**

Modify the tournaments table creation in `database.py` (around line 50-80) to add status columns:

```python
    # Check and add status column if it doesn't exist
    cursor.execute("PRAGMA table_info(tournaments)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'status' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN status TEXT DEFAULT 'setup'")

    if 'completed_at' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN completed_at TIMESTAMP NULL")

    if 'archived_at' not in columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN archived_at TIMESTAMP NULL")

    # Create index on status for filtering
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)')
```

**Step 4: Run test to verify it passes**

Run:
```bash
rm -f instance/padel.db && source venv/bin/activate && python database.py && python -m pytest tests/test_tournament_status.py -v
```

Expected: 3/3 tests PASS

**Step 5: Commit**

```bash
git add database.py tests/test_tournament_status.py
git commit -m "feat: add tournament status lifecycle columns

Phase 3 Stage 1: Add status tracking for tournament lifecycle
(setup → active → completed → archived).

- Added status column with 'setup' default
- Added completed_at timestamp
- Added archived_at timestamp
- Added index on status for filtering
- Migration-safe (checks column exists)

3/3 tests passing."
```

---

## Task 4: Link Players to Registry

**Files:**
- Modify: `database.py` (add registry_id to players table)
- Create: `tests/test_player_registry_link.py`

**Step 1: Write the failing test**

Create `tests/test_player_registry_link.py`:

```python
import sqlite3
import pytest


def test_players_table_has_registry_id():
    """Test that players table has registry_id foreign key"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert 'registry_id' in columns

    conn.close()


def test_players_registry_id_foreign_key():
    """Test that registry_id references player_registry"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_key_list(players)")
    foreign_keys = cursor.fetchall()

    # Find FK to player_registry
    registry_fks = [fk for fk in foreign_keys if fk[2] == 'player_registry']
    assert len(registry_fks) > 0

    conn.close()


def test_players_can_link_to_registry():
    """Test that players can be linked to registry entries"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create registry player
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Test", "LinkPlayer"))
        registry_id = cursor.lastrowid
        conn.commit()

        # Create old-style player linked to registry
        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Test LinkPlayer", 100, registry_id))
        player_id = cursor.lastrowid
        conn.commit()

        # Verify link
        cursor.execute("""
            SELECT p.name, pr.first_name, pr.last_name
            FROM players p
            JOIN player_registry pr ON p.registry_id = pr.id
            WHERE p.id = ?
        """, (player_id,))

        row = cursor.fetchone()
        assert row[0] == "Test LinkPlayer"
        assert row[1] == "Test"
        assert row[2] == "LinkPlayer"
    finally:
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
        cursor.execute("DELETE FROM player_registry WHERE id = ?", (registry_id,))
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_player_registry_link.py -v
```

Expected: FAIL with "no such column: registry_id"

**Step 3: Add registry_id to players table in database.py**

Add after player_registry table creation in `database.py`:

```python
    # Link legacy players table to registry (Phase 3)
    cursor.execute("PRAGMA table_info(players)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'registry_id' not in columns:
        cursor.execute('''
            ALTER TABLE players ADD COLUMN registry_id INTEGER
            REFERENCES player_registry(id)
        ''')

    # Create index for registry lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_players_registry
        ON players(registry_id)
    ''')
```

**Step 4: Run test to verify it passes**

Run:
```bash
rm -f instance/padel.db && source venv/bin/activate && python database.py && python -m pytest tests/test_player_registry_link.py -v
```

Expected: 3/3 tests PASS

**Step 5: Commit**

```bash
git add database.py tests/test_player_registry_link.py
git commit -m "feat: link legacy players table to player_registry

Phase 3 Stage 1: Add registry_id foreign key to players table for
backward compatibility during migration.

- Added registry_id column to players table
- Foreign key references player_registry(id)
- Index for efficient registry lookups
- Allows gradual migration from old to new schema

3/3 tests passing."
```

---

## Task 5: Migration Script Foundation

**Files:**
- Create: `migration_phase3.py`
- Create: `tests/test_migration_phase3.py`

**Step 1: Write the failing test**

Create `tests/test_migration_phase3.py`:

```python
import sqlite3
import pytest
from migration_phase3 import migrate_players_to_registry, parse_player_name


def test_parse_player_name_standard_format():
    """Test parsing 'First Last' format"""
    first, last = parse_player_name("John Smith")
    assert first == "John"
    assert last == "Smith"


def test_parse_player_name_multiple_words():
    """Test parsing names with multiple words"""
    first, last = parse_player_name("Mary Jane Watson")
    assert first == "Mary Jane"
    assert last == "Watson"


def test_parse_player_name_single_word():
    """Test parsing single word names (use as last name)"""
    first, last = parse_player_name("Madonna")
    assert first == ""
    assert last == "Madonna"


def test_migrate_players_to_registry_creates_registry_entries():
    """Test that migration creates player_registry entries"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create test players with old schema
        cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Alice Anderson", 100))
        player1_id = cursor.lastrowid
        cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Bob Brown", 150))
        player2_id = cursor.lastrowid
        conn.commit()

        # Run migration
        migrated_count = migrate_players_to_registry(conn)
        assert migrated_count == 2

        # Verify registry entries created
        cursor.execute("SELECT COUNT(*) FROM player_registry")
        assert cursor.fetchone()[0] >= 2

        # Verify players linked to registry
        cursor.execute("SELECT registry_id FROM players WHERE id = ?", (player1_id,))
        assert cursor.fetchone()[0] is not None

        cursor.execute("""
            SELECT pr.first_name, pr.last_name
            FROM players p
            JOIN player_registry pr ON p.registry_id = pr.id
            WHERE p.id = ?
        """, (player1_id,))
        row = cursor.fetchone()
        assert row[0] == "Alice"
        assert row[1] == "Anderson"
    finally:
        # Cleanup
        cursor.execute("DELETE FROM players WHERE id IN (?, ?)", (player1_id, player2_id))
        cursor.execute("DELETE FROM player_registry WHERE first_name IN (?, ?)", ("Alice", "Bob"))
        conn.commit()
        conn.close()


def test_migrate_players_handles_duplicates():
    """Test that migration reuses existing registry entries for duplicates"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create registry entry
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Charlie", "Chen"))
        registry_id = cursor.lastrowid
        conn.commit()

        # Create player with same name
        cursor.execute("INSERT INTO players (name, total_points) VALUES (?, ?)", ("Charlie Chen", 100))
        player_id = cursor.lastrowid
        conn.commit()

        # Run migration
        initial_count = cursor.execute("SELECT COUNT(*) FROM player_registry").fetchone()[0]
        migrate_players_to_registry(conn)
        final_count = cursor.execute("SELECT COUNT(*) FROM player_registry").fetchone()[0]

        # Should not create duplicate registry entry
        assert final_count == initial_count

        # Player should link to existing registry entry
        cursor.execute("SELECT registry_id FROM players WHERE id = ?", (player_id,))
        assert cursor.fetchone()[0] == registry_id
    finally:
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
        cursor.execute("DELETE FROM player_registry WHERE id = ?", (registry_id,))
        conn.commit()
        conn.close()


def test_migrate_players_skips_already_migrated():
    """Test that migration skips players already linked to registry"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create registry and linked player
        cursor.execute("""
            INSERT INTO player_registry (first_name, last_name)
            VALUES (?, ?)
        """, ("Diana", "Davis"))
        registry_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Diana Davis", 100, registry_id))
        player_id = cursor.lastrowid
        conn.commit()

        # Run migration
        migrated_count = migrate_players_to_registry(conn)

        # Should skip already migrated player
        assert migrated_count == 0
    finally:
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
        cursor.execute("DELETE FROM player_registry WHERE id = ?", (registry_id,))
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_migration_phase3.py -v
```

Expected: FAIL with "No module named 'migration_phase3'"

**Step 3: Create migration script**

Create `migration_phase3.py`:

```python
"""
Phase 3 Migration Script

Migrates Phase 2 data to Phase 3 schema:
1. Create player_registry entries from existing players table
2. Link players to registry via registry_id
3. Create tournament_players records from match history

Safe to run multiple times (idempotent).
"""

import sqlite3
from datetime import datetime


def parse_player_name(full_name):
    """
    Parse player name into first and last name.

    Assumes format: "FirstName LastName" or "FirstName MiddleNames LastName"
    If single word: use as last name with empty first name

    Examples:
        "John Smith" → ("John", "Smith")
        "Mary Jane Watson" → ("Mary Jane", "Watson")
        "Madonna" → ("", "Madonna")
    """
    parts = full_name.strip().split()

    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return "", parts[0]
    else:
        # Last word is last name, everything else is first name
        return " ".join(parts[:-1]), parts[-1]


def migrate_players_to_registry(conn):
    """
    Migrate existing players to player_registry.

    Returns: Number of players migrated
    """
    cursor = conn.cursor()
    migrated_count = 0

    # Get all players not yet linked to registry
    cursor.execute("""
        SELECT id, name FROM players WHERE registry_id IS NULL
    """)
    players = cursor.fetchall()

    for player_id, full_name in players:
        first_name, last_name = parse_player_name(full_name)

        # Check if registry entry already exists
        cursor.execute("""
            SELECT id FROM player_registry
            WHERE first_name = ? AND last_name = ?
        """, (first_name, last_name))

        existing = cursor.fetchone()

        if existing:
            # Reuse existing registry entry
            registry_id = existing[0]
        else:
            # Create new registry entry
            cursor.execute("""
                INSERT INTO player_registry (first_name, last_name)
                VALUES (?, ?)
            """, (first_name, last_name))
            registry_id = cursor.lastrowid

        # Link player to registry
        cursor.execute("""
            UPDATE players SET registry_id = ? WHERE id = ?
        """, (registry_id, player_id))

        migrated_count += 1

    conn.commit()
    return migrated_count


def run_migration_if_needed():
    """
    Run Phase 3 migration if needed.

    Returns: "migrated", "already_migrated", or "error"
    """
    try:
        conn = sqlite3.connect('instance/padel.db')

        # Check if migration needed
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players WHERE registry_id IS NULL")
        unmigrated = cursor.fetchone()[0]

        if unmigrated == 0:
            conn.close()
            return "already_migrated"

        # Run migration
        migrated_count = migrate_players_to_registry(conn)

        conn.close()
        return "migrated"

    except Exception as e:
        print(f"Migration error: {e}")
        return "error"


if __name__ == "__main__":
    result = run_migration_if_needed()

    if result == "migrated":
        print("✅ Phase 3 migration completed successfully")
    elif result == "already_migrated":
        print("✅ Data already migrated to Phase 3")
    else:
        print("❌ Migration failed")
```

**Step 4: Run test to verify it passes**

Run:
```bash
rm -f instance/padel.db && source venv/bin/activate && python database.py && python -m pytest tests/test_migration_phase3.py -v
```

Expected: 5/5 tests PASS

**Step 5: Commit**

```bash
git add migration_phase3.py tests/test_migration_phase3.py
git commit -m "feat: add Phase 3 player migration script

Phase 3 Stage 1: Create migration script to convert legacy players
table to player_registry.

- Parse player names into first_name + last_name
- Handle duplicates by reusing registry entries
- Skip already-migrated players (idempotent)
- Safe to run multiple times

5/5 tests passing."
```

---

## Task 6: Complete Tournament Function

**Files:**
- Modify: `app.py` (add complete_tournament route and logic)
- Create: `tests/test_complete_tournament.py`

**Step 1: Write the failing test**

Create `tests/test_complete_tournament.py`:

```python
import sqlite3
import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def setup_tournament():
    """Create a tournament with players and completed matches"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create tournament
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Tournament", 2, season_id, "active"))
        tournament_id = cursor.lastrowid

        # Create players in registry
        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Alice", "A"))
        alice_registry = cursor.lastrowid
        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Bob", "B"))
        bob_registry = cursor.lastrowid

        # Create legacy players linked to registry
        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Alice A", 0, alice_registry))
        alice_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Bob B", 0, bob_registry))
        bob_id = cursor.lastrowid

        # Create a round with completed match
        cursor.execute("""
            INSERT INTO rounds (tournament_id, round_number)
            VALUES (?, ?)
        """, (tournament_id, 1))
        round_id = cursor.lastrowid

        # Create completed match (Alice wins)
        cursor.execute("""
            INSERT INTO matches (
                round_id, court_number,
                player1_id, player2_id, player3_id, player4_id,
                winning_team, completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (round_id, 1, alice_id, bob_id, alice_id, bob_id, 1, 1))
        match_id = cursor.lastrowid

        # Add scores
        cursor.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)", (match_id, alice_id, 50))
        cursor.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)", (match_id, bob_id, 30))

        # Update player totals
        cursor.execute("UPDATE players SET total_points = 50 WHERE id = ?", (alice_id,))
        cursor.execute("UPDATE players SET total_points = 30 WHERE id = ?", (bob_id,))

        conn.commit()

        yield {
            'tournament_id': tournament_id,
            'season_id': season_id,
            'alice_id': alice_id,
            'bob_id': bob_id,
            'alice_registry': alice_registry,
            'bob_registry': bob_registry,
            'round_id': round_id,
            'match_id': match_id
        }
    finally:
        # Cleanup
        cursor.execute("DELETE FROM scores")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM rounds")
        cursor.execute("DELETE FROM players")
        cursor.execute("DELETE FROM tournament_players")
        cursor.execute("DELETE FROM tournaments")
        cursor.execute("DELETE FROM player_registry")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()


def test_complete_tournament_calculates_final_ranks(client, setup_tournament):
    """Test that completing tournament calculates and stores final rankings"""
    tournament_id = setup_tournament['tournament_id']
    alice_registry = setup_tournament['alice_registry']
    bob_registry = setup_tournament['bob_registry']

    # Complete the tournament
    response = client.post(f'/tournament/{tournament_id}/complete')
    assert response.status_code in [200, 302]  # OK or redirect

    # Verify tournament_players entries created with ranks
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT player_id, final_rank, total_points
        FROM tournament_players
        WHERE tournament_id = ?
        ORDER BY final_rank
    """, (tournament_id,))
    results = cursor.fetchall()

    assert len(results) == 2
    # Alice should be rank 1 (higher points)
    assert results[0][0] == alice_registry
    assert results[0][1] == 1
    assert results[0][2] == 50

    # Bob should be rank 2
    assert results[1][0] == bob_registry
    assert results[1][1] == 2
    assert results[1][2] == 30

    conn.close()


def test_complete_tournament_updates_status(client, setup_tournament):
    """Test that completing tournament updates status to 'completed'"""
    tournament_id = setup_tournament['tournament_id']

    response = client.post(f'/tournament/{tournament_id}/complete')
    assert response.status_code in [200, 302]

    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status, completed_at FROM tournaments WHERE id = ?", (tournament_id,))
    row = cursor.fetchone()

    assert row[0] == 'completed'
    assert row[1] is not None  # completed_at timestamp set

    conn.close()


def test_complete_tournament_calculates_match_wins(client, setup_tournament):
    """Test that match wins are counted correctly"""
    tournament_id = setup_tournament['tournament_id']
    alice_registry = setup_tournament['alice_registry']

    client.post(f'/tournament/{tournament_id}/complete')

    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT match_wins FROM tournament_players
        WHERE tournament_id = ? AND player_id = ?
    """, (tournament_id, alice_registry))

    match_wins = cursor.fetchone()[0]
    assert match_wins == 1  # Alice won 1 match

    conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_complete_tournament.py -v
```

Expected: FAIL with "404 NOT FOUND" (route doesn't exist)

**Step 3: Implement complete_tournament route in app.py**

Add to `app.py` after existing tournament routes (around line 600):

```python
@app.route('/tournament/<int:tournament_id>/complete', methods=['POST'])
def complete_tournament(tournament_id):
    """
    Complete a tournament by calculating final rankings and updating stats.

    Steps:
    1. Verify all rounds are complete
    2. Calculate final rankings based on total_points
    3. Calculate match wins/losses for each player
    4. Create tournament_players entries with stats
    5. Update tournament status to 'completed'
    """
    conn = get_db()
    cursor = conn.cursor()

    # Get tournament
    tournament = cursor.execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    # Verify tournament is active
    if tournament['status'] != 'active':
        flash(f"Cannot complete tournament in '{tournament['status']}' status")
        return redirect('/')

    # Get all players with their total points
    cursor.execute("""
        SELECT DISTINCT p.id, p.registry_id, p.total_points
        FROM players p
        JOIN matches m ON p.id IN (m.player1_id, m.player2_id, m.player3_id, m.player4_id)
        JOIN rounds r ON m.round_id = r.id
        WHERE r.tournament_id = ?
        ORDER BY p.total_points DESC
    """, (tournament_id,))

    players = cursor.fetchall()

    if not players:
        flash("No players found in tournament")
        return redirect('/')

    # Calculate match wins and losses for each player
    for rank, player_row in enumerate(players, start=1):
        player_id = player_row['id']
        registry_id = player_row['registry_id']
        total_points = player_row['total_points']

        # Count wins and losses
        cursor.execute("""
            SELECT
                COUNT(CASE
                    WHEN (m.winning_team = 1 AND (m.player1_id = ? OR m.player2_id = ?))
                      OR (m.winning_team = 2 AND (m.player3_id = ? OR m.player4_id = ?))
                    THEN 1 END) as wins,
                COUNT(CASE
                    WHEN m.completed = 1
                    THEN 1 END) as total_matches
            FROM matches m
            JOIN rounds r ON m.round_id = r.id
            WHERE r.tournament_id = ?
                AND (m.player1_id = ? OR m.player2_id = ? OR m.player3_id = ? OR m.player4_id = ?)
        """, (player_id, player_id, player_id, player_id, tournament_id, player_id, player_id, player_id, player_id))

        stats = cursor.fetchone()
        match_wins = stats[0] if stats[0] else 0
        total_matches = stats[1] if stats[1] else 0
        match_losses = total_matches - match_wins

        # Create or update tournament_players entry
        cursor.execute("""
            INSERT OR REPLACE INTO tournament_players
            (tournament_id, player_id, final_rank, total_points, match_wins, match_losses)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, registry_id, rank, total_points, match_wins, match_losses))

    # Update tournament status
    cursor.execute("""
        UPDATE tournaments
        SET status = 'completed', completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (tournament_id,))

    conn.commit()

    # Get winner name for flash message
    winner = players[0]
    cursor.execute("""
        SELECT first_name, last_name FROM player_registry WHERE id = ?
    """, (winner['registry_id'],))
    winner_row = cursor.fetchone()
    winner_name = f"{winner_row['first_name']} {winner_row['last_name']}" if winner_row else "Unknown"

    flash(f"Tournament completed! Winner: {winner_name}")
    return redirect(f'/tournament/{tournament_id}/results')
```

**Step 4: Add tournament results view route**

Add to `app.py`:

```python
@app.route('/tournament/<int:tournament_id>/results')
def tournament_results(tournament_id):
    """View completed tournament results"""
    conn = get_db()
    cursor = conn.cursor()

    # Get tournament
    tournament = cursor.execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
    ).fetchone()

    if not tournament:
        return "Tournament not found", 404

    # Get results from tournament_players
    cursor.execute("""
        SELECT
            tp.final_rank,
            pr.first_name,
            pr.last_name,
            tp.total_points,
            tp.match_wins,
            tp.match_losses
        FROM tournament_players tp
        JOIN player_registry pr ON tp.player_id = pr.id
        WHERE tp.tournament_id = ?
        ORDER BY tp.final_rank ASC
    """, (tournament_id,))

    results = cursor.fetchall()

    return render_template(
        'tournament_results.html',
        tournament=tournament,
        results=results
    )
```

**Step 5: Run test to verify it passes**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_complete_tournament.py -v
```

Expected: 3/3 tests PASS

**Step 6: Commit**

```bash
git add app.py tests/test_complete_tournament.py
git commit -m "feat: add complete tournament functionality

Phase 3 Stage 1: Implement tournament completion with final rankings
and statistics calculation.

- Calculate final ranks based on total_points
- Count match wins/losses for each player
- Create tournament_players entries with stats
- Update tournament status to 'completed'
- Set completed_at timestamp
- Add /tournament/<id>/results view route

3/3 tests passing."
```

---

## Task 7: Archive Tournament Function

**Files:**
- Modify: `app.py` (add archive route and read-only enforcement)
- Create: `tests/test_archive_tournament.py`

**Step 1: Write the failing test**

Create `tests/test_archive_tournament.py`:

```python
import sqlite3
import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def completed_tournament():
    """Create a completed tournament"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status, completed_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, ("Completed Tournament", 2, season_id, "completed"))
        tournament_id = cursor.lastrowid

        conn.commit()

        yield {'tournament_id': tournament_id, 'season_id': season_id}
    finally:
        cursor.execute("DELETE FROM tournaments")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()


def test_archive_tournament_updates_status(client, completed_tournament):
    """Test that archiving sets status to 'archived'"""
    tournament_id = completed_tournament['tournament_id']

    response = client.post(f'/tournament/{tournament_id}/archive')
    assert response.status_code in [200, 302]

    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status, archived_at FROM tournaments WHERE id = ?", (tournament_id,))
    row = cursor.fetchone()

    assert row[0] == 'archived'
    assert row[1] is not None

    conn.close()


def test_archive_requires_completed_status(client):
    """Test that only completed tournaments can be archived"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        # Create active tournament
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Active Tournament", 2, season_id, "active"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Try to archive
        response = client.post(f'/tournament/{tournament_id}/archive')

        # Should fail or redirect with error
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]
        assert status != 'archived'  # Should still be active
    finally:
        cursor.execute("DELETE FROM tournaments")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()


def test_archived_tournament_prevents_modifications(client, completed_tournament):
    """Test that archived tournaments are read-only"""
    tournament_id = completed_tournament['tournament_id']

    # Archive the tournament
    client.post(f'/tournament/{tournament_id}/archive')

    # Try to start a new round (should fail)
    response = client.post(f'/tournament/{tournament_id}/start_round')

    # Verify no new round was created
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM rounds WHERE tournament_id = ?", (tournament_id,))
    count = cursor.fetchone()[0]
    assert count == 0  # No rounds should exist

    conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_archive_tournament.py -v
```

Expected: FAIL with "404 NOT FOUND" (route doesn't exist)

**Step 3: Implement archive route in app.py**

Add to `app.py` after complete_tournament:

```python
@app.route('/tournament/<int:tournament_id>/archive', methods=['POST'])
def archive_tournament(tournament_id):
    """
    Archive a completed tournament (makes it read-only).

    Requirements:
    - Tournament must be in 'completed' status
    - Sets status to 'archived'
    - Sets archived_at timestamp
    """
    conn = get_db()
    cursor = conn.cursor()

    # Get tournament
    tournament = cursor.execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    # Verify tournament is completed
    if tournament['status'] != 'completed':
        flash(f"Can only archive completed tournaments (current status: {tournament['status']})")
        return redirect('/')

    # Archive the tournament
    cursor.execute("""
        UPDATE tournaments
        SET status = 'archived', archived_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (tournament_id,))

    conn.commit()

    flash(f"Tournament '{tournament['name']}' has been archived")
    return redirect('/')
```

**Step 4: Add read-only enforcement to start_round**

Modify the `start_round` route in `app.py` to check for archived status:

```python
@app.route('/tournament/<int:tournament_id>/start_round', methods=['POST'])
def start_round(tournament_id):
    """Start a new round in the tournament"""
    conn = get_db()
    cursor = conn.cursor()

    # Get tournament
    tournament = cursor.execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    # PHASE 3: Prevent modifications to archived tournaments
    if tournament['status'] == 'archived':
        flash("Cannot modify archived tournament")
        return redirect('/')

    # ... rest of existing start_round logic ...
```

**Step 5: Run test to verify it passes**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_archive_tournament.py -v
```

Expected: 3/3 tests PASS

**Step 6: Commit**

```bash
git add app.py tests/test_archive_tournament.py
git commit -m "feat: add tournament archive functionality

Phase 3 Stage 1: Implement tournament archiving with read-only
enforcement.

- Archive route sets status to 'archived'
- Sets archived_at timestamp
- Requires 'completed' status to archive
- Prevents round creation in archived tournaments
- Read-only enforcement in start_round

3/3 tests passing."
```

---

## Task 8: Tournament Results Template

**Files:**
- Create: `templates/tournament_results.html`

**Step 1: Create tournament results template**

Create `templates/tournament_results.html`:

```html
{% extends "base.html" %}

{% block title %}{{ tournament.name }} - Results{% endblock %}

{% block content %}
<div class="tournament-results">
    <div class="header">
        <h1>{{ tournament.name }}</h1>
        <p class="status-badge {{ tournament.status }}">
            Status: {{ tournament.status|capitalize }}
        </p>
        {% if tournament.completed_at %}
        <p class="completed-date">
            Completed: {{ tournament.completed_at }}
        </p>
        {% endif %}
    </div>

    <div class="final-standings">
        <h2>Final Standings</h2>

        {% if results %}
        <table class="results-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Player</th>
                    <th>Points</th>
                    <th>Wins</th>
                    <th>Losses</th>
                    <th>Win %</th>
                </tr>
            </thead>
            <tbody>
                {% for result in results %}
                <tr class="rank-{{ result.final_rank }}">
                    <td class="rank">
                        {% if result.final_rank == 1 %}
                        🏆 {{ result.final_rank }}
                        {% else %}
                        {{ result.final_rank }}
                        {% endif %}
                    </td>
                    <td class="player-name">
                        {{ result.last_name }}, {{ result.first_name }}
                    </td>
                    <td class="points">{{ result.total_points }}</td>
                    <td class="wins">{{ result.match_wins }}</td>
                    <td class="losses">{{ result.match_losses }}</td>
                    <td class="win-pct">
                        {% set total = result.match_wins + result.match_losses %}
                        {% if total > 0 %}
                        {{ ((result.match_wins / total) * 100)|round(1) }}%
                        {% else %}
                        0%
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-results">No results available. Tournament may not be completed.</p>
        {% endif %}
    </div>

    <div class="actions">
        <a href="/" class="btn-secondary">Back to Home</a>

        {% if tournament.status == 'completed' %}
        <form action="/tournament/{{ tournament.id }}/archive" method="POST" style="display: inline;">
            <button type="submit" class="btn-warning"
                    onclick="return confirm('Archive this tournament? It will become read-only.')">
                Archive Tournament
            </button>
        </form>
        {% endif %}
    </div>
</div>

<style>
.tournament-results {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    margin-bottom: 30px;
}

.status-badge {
    display: inline-block;
    padding: 5px 15px;
    border-radius: 20px;
    font-weight: bold;
    margin: 10px 0;
}

.status-badge.completed {
    background-color: #4CAF50;
    color: white;
}

.status-badge.archived {
    background-color: #9E9E9E;
    color: white;
}

.results-table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}

.results-table th,
.results-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

.results-table th {
    background-color: #f5f5f5;
    font-weight: bold;
}

.results-table tr.rank-1 {
    background-color: #fff9c4;
    font-weight: bold;
}

.results-table tr:hover {
    background-color: #f5f5f5;
}

.rank {
    font-size: 1.2em;
}

.actions {
    margin-top: 30px;
    text-align: center;
}

.btn-warning {
    background-color: #ff9800;
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    margin-left: 10px;
}

.btn-warning:hover {
    background-color: #f57c00;
}
</style>
{% endblock %}
```

**Step 2: Test template rendering**

Run:
```bash
source venv/bin/activate && python app.py
```

Visit: http://127.0.0.1:5001/tournament/1/results (if tournament exists)

Expected: Results page displays with standings table

**Step 3: Commit**

```bash
git add templates/tournament_results.html
git commit -m "feat: add tournament results template

Phase 3 Stage 1: Create results page showing final standings with
archive functionality.

- Display final rankings with trophy for 1st place
- Show points, wins, losses, win percentage
- Highlight 1st place with gold background
- Archive button for completed tournaments
- Responsive table design

Template ready for testing."
```

---

## Task 9: Update Setup Route for Tournament Status

**Files:**
- Modify: `app.py` (update /setup route to set initial status)
- Create: `tests/test_tournament_setup_status.py`

**Step 1: Write the failing test**

Create `tests/test_tournament_setup_status.py`:

```python
import sqlite3
import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_new_tournament_starts_in_setup_status(client):
    """Test that creating a new tournament sets status to 'setup'"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Ensure current season exists
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("2025 Season", 1))
        season_id = cursor.lastrowid
        conn.commit()

        # Create tournament via /setup route
        response = client.post('/setup', data={
            'tournament_name': 'Status Test Tournament',
            'num_courts': '2'
        })

        # Get the created tournament
        cursor.execute("""
            SELECT status FROM tournaments
            WHERE name = 'Status Test Tournament'
        """)
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == 'setup'
    finally:
        cursor.execute("DELETE FROM tournaments WHERE name = 'Status Test Tournament'")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()


def test_starting_round_changes_status_to_active(client):
    """Test that starting Round 1 changes status from 'setup' to 'active'"""
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # Create season and tournament
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("Test Season", 1))
        season_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Test Active Tournament", 2, season_id, "setup"))
        tournament_id = cursor.lastrowid

        # Add players
        for i in range(8):
            cursor.execute("""
                INSERT INTO players (name, total_points, tournament_id)
                VALUES (?, ?, ?)
            """, (f"Player{i}", 0, tournament_id))

        conn.commit()

        # Start round
        client.post(f'/tournament/{tournament_id}/start_round')

        # Check status changed to active
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        status = cursor.fetchone()[0]

        assert status == 'active'
    finally:
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM rounds")
        cursor.execute("DELETE FROM players")
        cursor.execute("DELETE FROM tournaments")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it fails**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_tournament_setup_status.py -v
```

Expected: FAIL (status not set properly)

**Step 3: Update /setup route to set status**

Modify the `/setup` POST handler in `app.py`:

```python
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        tournament_name = request.form['tournament_name']
        num_courts = int(request.form['num_courts'])

        conn = get_db()
        cursor = conn.cursor()

        # Get current season
        current_season = get_current_season(conn)

        if not current_season:
            flash("No active season found. Please create a season first.")
            return redirect('/seasons')

        # PHASE 3: Create tournament with 'setup' status
        cursor.execute('''
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        ''', (tournament_name, num_courts, current_season['id'], 'setup'))

        tournament_id = cursor.lastrowid
        conn.commit()

        flash(f"Tournament '{tournament_name}' created!")
        return redirect(f'/add_players/{tournament_id}')

    return render_template('setup.html')
```

**Step 4: Update start_round to set status to 'active'**

Modify the `start_round` route to update status:

```python
@app.route('/tournament/<int:tournament_id>/start_round', methods=['POST'])
def start_round(tournament_id):
    """Start a new round in the tournament"""
    conn = get_db()
    cursor = conn.cursor()

    # Get tournament
    tournament = cursor.execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
    ).fetchone()

    if not tournament:
        flash("Tournament not found")
        return redirect('/'), 404

    # PHASE 3: Prevent modifications to archived tournaments
    if tournament['status'] == 'archived':
        flash("Cannot modify archived tournament")
        return redirect('/')

    # PHASE 3: Set status to 'active' when starting first round
    if tournament['status'] == 'setup':
        cursor.execute("""
            UPDATE tournaments SET status = 'active' WHERE id = ?
        """, (tournament_id,))

    # ... rest of existing start_round logic ...

    conn.commit()
    return redirect(f'/tournament/{tournament_id}/active')
```

**Step 5: Run test to verify it passes**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_tournament_setup_status.py -v
```

Expected: 2/2 tests PASS

**Step 6: Commit**

```bash
git add app.py tests/test_tournament_setup_status.py
git commit -m "feat: implement tournament status lifecycle transitions

Phase 3 Stage 1: Set proper status at each lifecycle stage.

- New tournaments start in 'setup' status
- Starting Round 1 transitions to 'active'
- Completing tournament sets 'completed'
- Archiving sets 'archived'

Status flow: setup → active → completed → archived

2/2 tests passing."
```

---

## Task 10: Integration Test - Full Lifecycle

**Files:**
- Create: `tests/test_tournament_lifecycle.py`

**Step 1: Write comprehensive lifecycle test**

Create `tests/test_tournament_lifecycle.py`:

```python
import sqlite3
import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_complete_tournament_lifecycle():
    """
    Integration test for complete tournament lifecycle:
    setup → active → completed → archived
    """
    conn = sqlite3.connect('instance/padel.db')
    cursor = conn.cursor()

    try:
        # 1. CREATE SEASON
        cursor.execute("INSERT INTO seasons (name, is_current) VALUES (?, ?)", ("2025 Season", 1))
        season_id = cursor.lastrowid
        conn.commit()

        # 2. CREATE TOURNAMENT (should be 'setup' status)
        cursor.execute("""
            INSERT INTO tournaments (name, num_courts, season_id, status)
            VALUES (?, ?, ?, ?)
        """, ("Lifecycle Test Tournament", 2, season_id, "setup"))
        tournament_id = cursor.lastrowid
        conn.commit()

        # Verify setup status
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        assert cursor.fetchone()[0] == 'setup'

        # 3. ADD PLAYERS TO REGISTRY
        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Alice", "Anderson"))
        alice_registry = cursor.lastrowid
        cursor.execute("INSERT INTO player_registry (first_name, last_name) VALUES (?, ?)", ("Bob", "Brown"))
        bob_registry = cursor.lastrowid
        conn.commit()

        # Add legacy players
        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Alice Anderson", 0, alice_registry))
        alice_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO players (name, total_points, registry_id)
            VALUES (?, ?, ?)
        """, ("Bob Brown", 0, bob_registry))
        bob_id = cursor.lastrowid
        conn.commit()

        # 4. START ROUND (should change to 'active')
        cursor.execute("""
            INSERT INTO rounds (tournament_id, round_number) VALUES (?, ?)
        """, (tournament_id, 1))
        round_id = cursor.lastrowid

        cursor.execute("""
            UPDATE tournaments SET status = 'active' WHERE id = ?
        """, (tournament_id,))
        conn.commit()

        # Verify active status
        cursor.execute("SELECT status FROM tournaments WHERE id = ?", (tournament_id,))
        assert cursor.fetchone()[0] == 'active'

        # 5. PLAY MATCH
        cursor.execute("""
            INSERT INTO matches (
                round_id, court_number,
                player1_id, player2_id, player3_id, player4_id,
                winning_team, completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (round_id, 1, alice_id, bob_id, alice_id, bob_id, 1, 1))
        match_id = cursor.lastrowid

        # Add scores
        cursor.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)", (match_id, alice_id, 100))
        cursor.execute("INSERT INTO scores (match_id, player_id, points) VALUES (?, ?, ?)", (match_id, bob_id, 80))

        # Update totals
        cursor.execute("UPDATE players SET total_points = 100 WHERE id = ?", (alice_id,))
        cursor.execute("UPDATE players SET total_points = 80 WHERE id = ?", (bob_id,))
        conn.commit()

        # 6. COMPLETE TOURNAMENT
        # Calculate and insert tournament_players
        cursor.execute("""
            INSERT INTO tournament_players
            (tournament_id, player_id, final_rank, total_points, match_wins, match_losses)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, alice_registry, 1, 100, 1, 0))

        cursor.execute("""
            INSERT INTO tournament_players
            (tournament_id, player_id, final_rank, total_points, match_wins, match_losses)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_id, bob_registry, 2, 80, 0, 1))

        cursor.execute("""
            UPDATE tournaments
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (tournament_id,))
        conn.commit()

        # Verify completed status
        cursor.execute("SELECT status, completed_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'completed'
        assert row[1] is not None

        # Verify tournament_players created
        cursor.execute("""
            SELECT COUNT(*) FROM tournament_players WHERE tournament_id = ?
        """, (tournament_id,))
        assert cursor.fetchone()[0] == 2

        # 7. ARCHIVE TOURNAMENT
        cursor.execute("""
            UPDATE tournaments
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (tournament_id,))
        conn.commit()

        # Verify archived status
        cursor.execute("SELECT status, archived_at FROM tournaments WHERE id = ?", (tournament_id,))
        row = cursor.fetchone()
        assert row[0] == 'archived'
        assert row[1] is not None

        # 8. VERIFY FINAL STATE
        # Tournament should be archived with all data intact
        cursor.execute("""
            SELECT
                t.status,
                COUNT(DISTINCT r.id) as rounds,
                COUNT(DISTINCT m.id) as matches,
                COUNT(DISTINCT tp.player_id) as players
            FROM tournaments t
            LEFT JOIN rounds r ON t.id = r.tournament_id
            LEFT JOIN matches m ON r.id = m.round_id
            LEFT JOIN tournament_players tp ON t.id = tp.tournament_id
            WHERE t.id = ?
            GROUP BY t.status
        """, (tournament_id,))

        result = cursor.fetchone()
        assert result[0] == 'archived'  # status
        assert result[1] == 1  # 1 round
        assert result[2] == 1  # 1 match
        assert result[3] == 2  # 2 players

        print("✅ Complete tournament lifecycle test passed!")

    finally:
        # Cleanup
        cursor.execute("DELETE FROM scores")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM rounds")
        cursor.execute("DELETE FROM tournament_players")
        cursor.execute("DELETE FROM players")
        cursor.execute("DELETE FROM tournaments")
        cursor.execute("DELETE FROM player_registry")
        cursor.execute("DELETE FROM seasons")
        conn.commit()
        conn.close()
```

**Step 2: Run test to verify it passes**

Run:
```bash
source venv/bin/activate && python -m pytest tests/test_tournament_lifecycle.py -v
```

Expected: 1/1 test PASS with all lifecycle stages verified

**Step 3: Commit**

```bash
git add tests/test_tournament_lifecycle.py
git commit -m "test: add complete tournament lifecycle integration test

Phase 3 Stage 1: Comprehensive test covering full tournament flow.

Tests complete lifecycle:
1. Create season
2. Create tournament (setup status)
3. Add players to registry
4. Start round (active status)
5. Play matches
6. Complete tournament (completed status, stats calculated)
7. Archive tournament (archived status, read-only)
8. Verify all data integrity

1/1 integration test passing."
```

---

## Task 11: Run All Tests and Verify

**Step 1: Run complete test suite**

Run:
```bash
source venv/bin/activate && python -m pytest -v
```

Expected: All tests passing (should be 90+ tests now)

**Step 2: Manual verification**

```bash
# Clean database
rm -f instance/padel.db

# Initialize fresh
python database.py

# Start app
python app.py
```

Visit: http://127.0.0.1:5001

Manual checks:
- [ ] Create tournament → status = 'setup'
- [ ] Add players
- [ ] Start Round 1 → status = 'active'
- [ ] Complete matches
- [ ] Complete tournament → status = 'completed', results shown
- [ ] Archive tournament → status = 'archived'
- [ ] Try to start round in archived tournament → blocked

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Phase 3 Stage 1 - Tournament Lifecycle complete

Complete implementation of tournament lifecycle management with
player registry foundation.

Database changes:
- player_registry table (first_name, last_name, unique constraint)
- tournament_players junction table (stats tracking)
- Tournament status column (setup/active/completed/archived)
- Legacy players.registry_id link

Features:
- Tournament status flow (setup → active → completed → archived)
- Complete tournament (calculate ranks, stats, create tournament_players)
- Archive tournament (read-only enforcement)
- Migration script (parse names, create registry, link players)
- Tournament results view

All tests passing (90+ tests).
Ready for Stage 2: Seeded Round 1 pairing."
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2025-12-29-phase3-stage1-tournament-lifecycle.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
