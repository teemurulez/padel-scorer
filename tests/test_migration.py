"""
Tests for Phase 3 database migration helper functions
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path to import migrate module
sys.path.insert(0, str(Path(__file__).parent.parent / 'migrations'))
from migrate import column_exists, table_exists


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    # Create a temporary file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize with a simple schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE another_table (
            id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)


def test_column_exists_returns_true_for_existing_column(test_db):
    """Test that column_exists returns True for an existing column"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    assert column_exists(cursor, 'test_table', 'name') is True
    assert column_exists(cursor, 'test_table', 'age') is True
    assert column_exists(cursor, 'test_table', 'id') is True

    conn.close()


def test_column_exists_returns_false_for_nonexistent_column(test_db):
    """Test that column_exists returns False for a non-existent column"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    assert column_exists(cursor, 'test_table', 'email') is False
    assert column_exists(cursor, 'test_table', 'nonexistent') is False

    conn.close()


def test_column_exists_handles_different_tables(test_db):
    """Test that column_exists works correctly for different tables"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Columns in test_table
    assert column_exists(cursor, 'test_table', 'name') is True
    assert column_exists(cursor, 'test_table', 'data') is False

    # Columns in another_table
    assert column_exists(cursor, 'another_table', 'data') is True
    assert column_exists(cursor, 'another_table', 'name') is False

    conn.close()


def test_table_exists_returns_true_for_existing_table(test_db):
    """Test that table_exists returns True for an existing table"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    assert table_exists(cursor, 'test_table') is True
    assert table_exists(cursor, 'another_table') is True

    conn.close()


def test_table_exists_returns_false_for_nonexistent_table(test_db):
    """Test that table_exists returns False for a non-existent table"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    assert table_exists(cursor, 'nonexistent_table') is False
    assert table_exists(cursor, 'missing_table') is False

    conn.close()


def test_table_exists_case_sensitive(test_db):
    """Test that table_exists is case-sensitive"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # SQLite table names are case-sensitive in queries
    assert table_exists(cursor, 'test_table') is True
    assert table_exists(cursor, 'TEST_TABLE') is False
    assert table_exists(cursor, 'Test_Table') is False

    conn.close()


def test_column_exists_with_added_column(test_db):
    """Test that column_exists detects newly added columns"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Initially, column doesn't exist
    assert column_exists(cursor, 'test_table', 'email') is False

    # Add the column
    cursor.execute("ALTER TABLE test_table ADD COLUMN email TEXT")

    # Now it should exist
    assert column_exists(cursor, 'test_table', 'email') is True

    conn.close()


def test_table_exists_with_created_table(test_db):
    """Test that table_exists detects newly created tables"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Initially, table doesn't exist
    assert table_exists(cursor, 'new_table') is False

    # Create the table
    cursor.execute("CREATE TABLE new_table (id INTEGER PRIMARY KEY)")

    # Now it should exist
    assert table_exists(cursor, 'new_table') is True

    conn.close()
