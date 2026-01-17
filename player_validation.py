"""
Player name validation with fuzzy matching against registry.
"""
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.8


def normalize_name(name):
    """Normalize name for comparison (lowercase, strip whitespace)"""
    return ' '.join(name.lower().split())


def similarity_ratio(name1, name2):
    """Calculate similarity ratio between two names"""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()


def find_similar_player(name, registry):
    """
    Find matching or similar player in registry.

    Returns dict with:
    - status: 'exact', 'similar', or 'new'
    - player_id: ID if exact/similar match, None if new
    - suggestion: suggested name if similar match
    - similarity: similarity score if similar match
    """
    name = name.strip()
    if not name:
        return {'status': 'invalid', 'player_id': None}

    # Check for exact match first
    for player in registry:
        full_name = f"{player['first_name']} {player['last_name']}"
        if normalize_name(name) == normalize_name(full_name):
            return {
                'status': 'exact',
                'player_id': player['id'],
                'name': full_name
            }

    # Look for similar matches
    best_match = None
    best_score = 0

    for player in registry:
        full_name = f"{player['first_name']} {player['last_name']}"
        score = similarity_ratio(name, full_name)

        if score > best_score and score >= SIMILARITY_THRESHOLD:
            best_score = score
            best_match = player

    if best_match:
        full_name = f"{best_match['first_name']} {best_match['last_name']}"
        return {
            'status': 'similar',
            'player_id': best_match['id'],
            'suggestion': full_name,
            'similarity': best_score
        }

    # No match found - new player
    return {
        'status': 'new',
        'player_id': None,
        'name': name
    }


def validate_player_names(names, registry):
    """
    Validate a list of player names against registry.

    Returns list of validation results, one per non-empty name.
    Detects duplicates within the input list.
    """
    results = []
    seen_names = {}  # normalized name -> index

    for name in names:
        name = name.strip()
        if not name:
            continue

        normalized = normalize_name(name)

        # Check for duplicate within this list
        if normalized in seen_names:
            results.append({
                'status': 'duplicate',
                'name': name,
                'duplicate_of_index': seen_names[normalized],
                'player_id': None
            })
            continue

        # Validate against registry
        result = find_similar_player(name, registry)
        result['name'] = name
        result['index'] = len(results)
        results.append(result)

        seen_names[normalized] = len(results) - 1

    return results
