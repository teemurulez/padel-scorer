# Padel Paroni - King of the Court Tournament Manager

A mobile-optimized web application for managing "King of the Court" style Padel tournaments. Features dynamic court movement based on match results, season management, admin dashboard, and production-ready security.

## Features

### Tournament Management
- **Multi-court tournaments** - Support for 1-10 courts (4 players per court)
- **Round 1: Random pairing** - Initial round with random player distribution
- **Round 2+: Court movement** - Automatic result-based court assignment
  - Winners move UP to higher courts
  - Losers move DOWN to lower courts
  - Previous teammates are separated when possible
- **Real-time scoring** - Mobile-optimized score entry interface
- **Live leaderboard** - Dynamic standings with match statistics

### Season & Player Management
- **Season tracking** - Organize tournaments into seasons
- **Season leaderboard** - Cumulative points across tournaments
- **Player registry** - Persistent player database with name matching
- **Player points adjustment** - Manual point corrections when needed

### Admin Dashboard
- **Password protected** - Secure admin area with session management
- **Tournament lifecycle** - Create, edit, start, end, delete tournaments
- **Full-screen tournament editor** - Edit players, preview pairings, search players
- **Season management** - Create seasons, archive old ones, view history

### Security (Production Ready)
- **CSRF protection** - All forms protected against cross-site request forgery
- **Rate limiting** - Brute force protection on login (5/min) and password reset (3/hr)
- **Secure sessions** - HTTPOnly, SameSite, and Secure cookie flags
- **SECRET_KEY enforcement** - Required environment variable in production

### User Experience
- **Mobile-first design** - Optimized for outdoor tournament use
- **Finnish UI** - Full Finnish language interface
- **Visual indicators** - Clear movement notes, status badges
- **Watermark branding** - Padel Paroni logo background

## Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/teemurulez/padel-scorer.git
cd padel-scorer

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run in development mode
FLASK_DEBUG=1 python app.py
```

Open your browser to: `http://localhost:5001`

### Production Deployment

```bash
# Generate a secure secret key
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Run the application
python app.py
```

**Important:** In production, `SECRET_KEY` environment variable is required. The app will refuse to start without it.

## Usage

### First Time Setup

1. Navigate to `/admin/setup`
2. Create admin password (minimum 8 characters)
3. Log in at `/admin/login`

### Running a Tournament

1. **Create Season** (if needed) - Admin → Seasons tab → Create new season
2. **Create Tournament** - Admin → Enter name, select courts, add players
3. **Edit Tournament** (optional) - Adjust players, preview Round 1 pairings
4. **Start Tournament** - Click "Aloita turnaus"
5. **Enter Scores** - Players tap their court, select winner
6. **Next Round** - Once all scores entered, start next round
7. **End Tournament** - When finished, end and view final results

### Public Views

- `/` - Tournament selection (for players)
- `/tournament/<id>` - Active tournament view
- `/season/leaderboard` - Current season standings

### Admin Views

- `/admin` - Dashboard with all management features
- `/admin/tournament/<id>/edit` - Full-screen tournament editor

## Project Structure

```
padel-scorer/
├── app.py                      # Flask application (2700+ lines)
├── database.py                 # Database schema and initialization
├── config.py                   # Configuration with security settings
├── court_movement.py           # Court movement algorithm
├── migration.py                # Database migrations
├── requirements.txt            # Python dependencies
├── TODO.md                     # Current status and next steps
│
├── templates/                  # 17 Jinja2 templates
│   ├── admin_*.html           # Admin pages (6)
│   ├── active_round.html      # Match view
│   ├── score_entry.html       # Score input
│   ├── leaderboard.html       # Tournament standings
│   ├── season_*.html          # Season pages (2)
│   └── ...
│
├── static/
│   ├── css/
│   │   ├── style.css          # Main styles
│   │   └── admin_edit.css     # Tournament editor styles
│   ├── js/
│   │   └── tournament_edit.js # Editor JavaScript
│   └── images/
│       └── padel-paroni-logo.png
│
├── tests/                      # 40 test files, 155 tests
│   ├── conftest.py            # Test configuration
│   ├── test_court_movement.py
│   ├── test_admin_auth.py
│   └── ...
│
├── docs/
│   ├── COURT_MOVEMENT.md      # Algorithm documentation
│   ├── daily-summaries/       # Development logs
│   └── plans/                 # Design documents
│
└── instance/
    └── padel.db               # SQLite database (auto-created)
```

## Technologies

- **Backend:** Python 3.9, Flask 3.1.2
- **Database:** SQLite3
- **Security:** Flask-WTF 1.2.1 (CSRF), Flask-Limiter 3.5.0 (rate limiting)
- **Templates:** Jinja2
- **Testing:** pytest 8.4.2
- **Frontend:** Vanilla HTML/CSS/JS (mobile-first)

## Court Movement Algorithm

The King of the Court movement system:

1. **Round 1:** Players randomly distributed across courts
2. **Round 2+:** Based on previous results
   - All winners collected, sorted by court (high to low)
   - All losers collected, sorted by court (high to low)
   - Players redistributed: top 4 → Court 1, next 4 → Court 2, etc.
   - Within each court, previous teammates are separated

```
Round 1 Results:
Court 1: (A+B) beat (C+D)  →  Winners: A, B  |  Losers: C, D
Court 2: (E+F) lost to (G+H)  →  Winners: G, H  |  Losers: E, F

Round 2 Pairings:
Court 1: (A+G) vs (B+H)  ←  All winners, teammates separated
Court 2: (C+E) vs (D+F)  ←  All losers, teammates separated
```

For details, see [docs/COURT_MOVEMENT.md](docs/COURT_MOVEMENT.md)

## Testing

```bash
# Run all tests
TESTING=1 pytest

# Run with verbose output
TESTING=1 pytest -v

# Run specific test file
TESTING=1 pytest tests/test_court_movement.py
```

**Current status:** 142 passing, 10 failing (pre-existing schema issues), 3 skipped

## Development Phases

### ✅ Phase 1 (Dec 2025)
- Basic tournament setup, player management
- Random pairing for Round 1
- Score entry, simple leaderboard

### ✅ Phase 2 (Dec 2025)
- Court movement algorithm
- Winner/loser movement logic
- Teammate separation
- Enhanced leaderboard with statistics

### ✅ Phase 3 (Dec 2025 - Jan 2026)
- Admin dashboard with authentication
- Season management
- Player registry with name matching
- Tournament editor with live preview
- Finnish language UI
- Mobile-optimized design refresh

### ✅ Security Hardening (Jan 2026)
- CSRF protection on all forms
- Rate limiting on authentication
- Secure session cookies
- SECRET_KEY enforcement

## Contributing

This is a personal project, but suggestions and bug reports are welcome! Please open an issue to discuss proposed changes.

## License

MIT License - See LICENSE file for details

## Author

Created by Teemu

Built with assistance from Claude (Anthropic)

---

**Status:** Production Ready 🎾

For questions or issues, please open a GitHub issue.
