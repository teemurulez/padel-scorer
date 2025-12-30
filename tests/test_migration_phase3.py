import sqlite3
from database import get_db


def test_parse_player_name_standard_format():
    """Test parsing standard 'FirstName LastName' format"""
    from migration_phase3 import parse_player_name

    first, last = parse_player_name("John Doe")
    assert first == "John"
    assert last == "Doe"
