# Padel King of the Court Scorer

A mobile-optimized web application for managing "King of the Court" style Padel tournaments. Features dynamic court movement based on match results, ensuring winners move up and losers move down while preventing previous teammates from being paired together.

## Features

### Core Functionality
- **Tournament Management** - Create tournaments with configurable number of courts
- **Player Management** - Add and manage players for each tournament
- **Round 1: Random Pairing** - Initial round with random player distribution
- **Round 2+: Court Movement** - Automatic result-based court assignment
  - Winners move UP to higher courts
  - Losers move DOWN to lower courts
  - Previous teammates are separated when possible
- **Real-time Scoring** - Mobile-optimized score entry interface
- **Live Leaderboard** - Dynamic standings with match statistics

### User Experience
- **Visual Indicators** - Clear movement notes ("Winners moved up • Losers moved down")
- **Flash Messages** - Real-time feedback on round starts and actions
- **Enhanced Statistics** - Leaderboard shows points, matches played, and win percentage
- **Mobile-First Design** - Optimized for outdoor tournament use on phones/tablets

### Technical Features
- **Comprehensive Testing** - 8 unit tests covering all movement logic
- **Edge Case Handling** - Validates incomplete matches before generating pairings
- **Clean Architecture** - Separated algorithm module for testability
- **Professional Setup** - pytest configuration, proper package structure

## Screenshots

> Add screenshots here of:
> - Tournament setup
> - Active round view
> - Score entry
> - Leaderboard

## Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/teemurulez/padel-scorer.git
cd padel-scorer
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Open your browser to:
```
http://localhost:5001
```

## Usage

### Setting Up a Tournament

1. **Create Tournament**
   - Navigate to the home page
   - Click "Setup New Tournament"
   - Enter tournament name and number of courts
   - Add players (minimum 4 per court)

2. **Start Round 1**
   - Click "Start Round 1"
   - Players are randomly paired across all courts
   - Each court has 4 players (2 vs 2)

3. **Enter Scores**
   - Click "Enter Score" on each match
   - Select winning team
   - Click "Submit Score"

4. **Start Round 2+**
   - Once all matches are complete, click "Start Next Round"
   - Winners automatically move to higher courts
   - Losers move to lower courts
   - Previous teammates are separated

5. **View Leaderboard**
   - Click "Leaderboard" to see current standings
   - View points, matches played, and win percentage

## How Court Movement Works

### Algorithm Overview

The King of the Court movement system follows these rules:

1. **Round 1:** Players are randomly distributed across courts
2. **Round 2+:** Court assignments are based on previous round results

#### Movement Logic
```
For each completed round:
1. Separate all winners and losers by court
2. Sort: [All Winners] + [All Losers]
3. Redistribute: Top 4 → Court 1, Next 4 → Court 2, etc.
4. Within each court, avoid pairing previous teammates
```

#### Example
```
Round 1 Results:
Court 1: (A+B) beat (C+D)  →  Winners: A, B  |  Losers: C, D
Court 2: (E+F) lost to (G+H)  →  Winners: G, H  |  Losers: E, F

Round 2 Pairings:
Court 1: (A+G) vs (B+H)  ←  All winners, teammates separated
Court 2: (C+E) vs (D+F)  ←  All losers, teammates separated
```

### Teammate Separation

The system uses a simple swap strategy:
- Check if p1 and p2 were previous teammates
- If yes, swap p2 with p3
- This works for the majority of tournament scenarios
- Natural rotation over multiple rounds provides additional separation

For more details, see [docs/COURT_MOVEMENT.md](docs/COURT_MOVEMENT.md)

## Project Structure

```
padel-scorer/
├── app.py                      # Flask application and routes
├── database.py                 # Database initialization and schema
├── config.py                   # Application configuration
├── court_movement.py           # Court movement algorithm ⭐
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test configuration
│
├── templates/                  # Jinja2 HTML templates
│   ├── index.html             # Landing page
│   ├── setup.html             # Tournament setup
│   ├── active_round.html      # Current round view
│   ├── score_entry.html       # Score input form
│   └── leaderboard.html       # Standings table
│
├── static/css/
│   └── style.css              # Mobile-first styles
│
├── tests/
│   ├── __init__.py
│   └── test_court_movement.py # Unit tests (8 tests)
│
├── docs/
│   ├── COURT_MOVEMENT.md      # Algorithm documentation
│   ├── test-results.md        # Integration test results
│   └── plans/
│       └── 2025-12-19-phase-2-court-movement.md
│
└── instance/
    └── padel.db               # SQLite database (auto-created)
```

## Technologies Used

- **Backend:** Python 3.9, Flask 3.1.2
- **Database:** SQLite3
- **Templates:** Jinja2
- **Testing:** pytest 8.4.2
- **Frontend:** Vanilla HTML/CSS (mobile-first)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_court_movement.py
```

### Database

The application uses SQLite with the following schema:

- **tournaments** - Tournament metadata
- **players** - Player information and total points
- **rounds** - Round tracking
- **matches** - Match records with court assignments
- **scores** - Individual player scores per match

Database is automatically initialized on first run.

## Development Phases

### ✅ Phase 1 (Completed Dec 12, 2025)
- Basic tournament setup
- Player management
- Random pairing for Round 1
- Score entry
- Simple leaderboard

### ✅ Phase 2 (Completed Dec 20, 2025)
- Court movement algorithm
- Winner/loser movement logic
- Teammate separation
- Visual indicators
- Enhanced leaderboard with statistics
- Comprehensive testing
- Edge case handling

### 🚧 Phase 3 (Planned)
Potential future enhancements:
- Match timer functionality
- Tournament history/archive
- CSV export for results
- Admin password protection
- Player check-in system
- Advanced teammate separation (graph-based matching)
- Multi-round history tracking
- Weighted court movement based on score margin

## Contributing

This is a personal project, but suggestions and bug reports are welcome! Please open an issue to discuss proposed changes.

## Implementation Notes

### Design Decisions

**Simple Teammate Separation:**
The algorithm uses a simple swap strategy rather than comprehensive graph-based matching. This is intentional - the King of the Court format naturally rotates players over multiple rounds, providing separation over time. For typical 8-16 player tournaments, this approach is sufficient.

**Separate Algorithm Module:**
Court movement logic is isolated in `court_movement.py` for:
- Clean separation of concerns
- Easy unit testing without Flask context
- Potential reusability in other interfaces (CLI, API)

**Mobile-First Design:**
The interface is optimized for outdoor use on mobile devices, with large touch targets and high-contrast colors for sunlight visibility.

## Testing

The project includes comprehensive test coverage:

- **Unit Tests:** 8 tests covering all court movement logic
- **Integration Tests:** Manual test scenarios documented
- **Edge Cases:** Incomplete match validation, empty rounds, multi-court scenarios

All tests pass with 100% success rate.

## License

MIT License - See LICENSE file for details

## Author

Created by Teemu

## Acknowledgments

Built with assistance from Claude (Anthropic) using:
- Test-Driven Development (TDD)
- Systematic implementation planning
- Code review at each step

---

**Status:** Production Ready 🎾

For questions or issues, please open a GitHub issue.
