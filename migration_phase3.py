import sqlite3
from database import get_db


def parse_player_name(full_name):
    """Parse 'FirstName LastName' into components"""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = ' '.join(parts[1:])
    else:
        first_name = parts[0] if parts else 'Unknown'
        last_name = 'Player'
    return first_name, last_name
