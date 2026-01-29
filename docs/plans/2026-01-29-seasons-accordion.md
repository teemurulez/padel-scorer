# Seasons Accordion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace cluttered Seasons tab with expandable accordion where each season shows its tournaments.

**Architecture:** Modify admin_dashboard.html Seasons tab to use accordion pattern (already exists in season_leaderboard.html). Each season row expands to show info, tournaments table, and actions. CSS uses existing admin.css variables.

**Tech Stack:** Flask/Jinja2, vanilla JavaScript, CSS

---

## Task 1: Add Accordion CSS to admin.css

**Files:**
- Modify: `static/css/admin.css` (append at end)

**Step 1: Add accordion styles**

Add to end of `static/css/admin.css`:

```css
/* Season Accordion */
.season-accordion {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
}

.season-row {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
}

.season-row.current {
    border-color: var(--accent);
    border-width: 2px;
}

.season-header {
    display: flex;
    align-items: center;
    padding: 1rem;
    cursor: pointer;
    gap: 1rem;
    transition: background 0.2s;
}

.season-header:hover {
    background: var(--bg-surface-alt);
}

.season-toggle-icon {
    font-size: 0.8rem;
    color: var(--text-muted);
    min-width: 15px;
    transition: transform 0.2s;
}

.season-name {
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
}

.season-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}

.season-badge.current {
    background: var(--accent);
    color: var(--on-accent);
}

.season-badge.ended {
    background: var(--bg-surface-alt);
    color: var(--text-muted);
    border: 1px solid var(--border-color);
}

.season-tournament-count {
    color: var(--text-muted);
    font-size: 0.9rem;
}

.season-details {
    display: none;
    padding: 0 1rem 1rem 1rem;
    border-top: 1px solid var(--border-color);
}

.season-details.show {
    display: block;
}

.season-meta {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-bottom: 1rem;
}

.season-tournaments-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
    font-size: 0.9rem;
}

.season-tournaments-table th,
.season-tournaments-table td {
    padding: 0.5rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.season-tournaments-table th {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
}

.season-tournaments-table .actions {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
}

.season-tournaments-table .btn-small {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
}

.season-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.create-season-inline {
    display: none;
    padding: 1rem;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-top: 0.5rem;
}

.create-season-inline.show {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
}

.create-season-inline input {
    flex: 1;
    min-width: 200px;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
}
```

**Step 2: Commit**

```bash
git add static/css/admin.css
git commit -m "feat: add accordion CSS for seasons tab"
```

---

## Task 2: Update Backend to Include Season Tournaments

**Files:**
- Modify: `app.py` (admin_dashboard function, around line 2555)

**Step 1: Check current admin_dashboard query**

The backend already fetches `current_season_tournaments` and `archived_seasons`. We need to add tournaments to each archived season.

Find the `admin_dashboard` function and update it to include tournaments per archived season.

**Step 2: Modify admin_dashboard to include archived season tournaments**

In `app.py`, find the archived_seasons query (around line 2610) and update to fetch tournaments:

```python
    # Get archived seasons with their tournaments
    archived_seasons_raw = db.execute('''
        SELECT s.*, COUNT(t.id) as tournament_count
        FROM seasons s
        LEFT JOIN tournaments t ON t.season_id = s.id
        WHERE s.is_current = 0
        GROUP BY s.id
        ORDER BY s.created_at DESC
    ''').fetchall()

    # Build archived seasons with tournaments
    archived_seasons = []
    for season in archived_seasons_raw:
        season_dict = dict(season)
        season_dict['tournaments'] = db.execute('''
            SELECT id, name, status, created_at
            FROM tournaments
            WHERE season_id = ?
            ORDER BY created_at DESC
        ''', (season['id'],)).fetchall()
        archived_seasons.append(season_dict)
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: include tournaments in archived seasons data"
```

---

## Task 3: Rewrite Seasons Tab HTML

**Files:**
- Modify: `templates/admin_dashboard.html` (lines 54-188, the seasons tab content)

**Step 1: Replace seasons tab content**

Replace the entire `<div id="seasons" class="tab-content ...>` content with the accordion structure:

```html
<div id="seasons" class="tab-content {{ 'active' if active_tab == 'seasons' or not active_tab else '' }}">
    <div class="tab-panel">
        <h2>Kausien hallinta</h2>

        {% if not current_season and not archived_seasons %}
        <div class="empty-state">
            <p>Ei kausia. Luo ensimmäinen kausi aloittaaksesi.</p>
        </div>
        {% else %}
        <div class="season-accordion">
            <!-- Current Season -->
            {% if current_season %}
            <div class="season-row current">
                <div class="season-header" onclick="toggleSeason('current')">
                    <span class="season-toggle-icon" id="season-icon-current">▶</span>
                    <span class="season-name">{{ current_season.name }}</span>
                    <span class="season-badge current">Nykyinen</span>
                    <span class="season-tournament-count">{{ current_tournament_count }} turnausta</span>
                </div>
                <div class="season-details" id="season-details-current">
                    <p class="season-meta">Luotu: {{ current_season.created_at[:10] }}</p>

                    {% if current_season_tournaments %}
                    <table class="season-tournaments-table">
                        <thead>
                            <tr>
                                <th>Turnaus</th>
                                <th>Pvm</th>
                                <th>Tila</th>
                                <th>Toiminnot</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for tournament in current_season_tournaments %}
                            <tr>
                                <td>{{ tournament['name'] }}</td>
                                <td>{{ tournament['created_at'][:10] }}</td>
                                <td>
                                    {% if tournament['status'] == 'active' %}
                                    <span class="status-badge active-badge">Käynnissä</span>
                                    {% elif tournament['status'] == 'completed' %}
                                    <span class="status-badge completed-badge">Päättynyt</span>
                                    {% else %}
                                    <span class="status-badge setup-badge">Valmistelu</span>
                                    {% endif %}
                                </td>
                                <td class="actions">
                                    {% if tournament['status'] == 'setup' %}
                                    <form method="POST" action="{{ url_for('start_round', tournament_id=tournament['id']) }}" style="display:inline;">
                                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                        <button type="submit" class="btn-primary btn-small">Aloita</button>
                                    </form>
                                    <a href="{{ url_for('admin_tournament_edit_page', tournament_id=tournament['id']) }}" class="btn-secondary btn-small">Muokkaa</a>
                                    {% elif tournament['status'] == 'active' %}
                                    <a href="{{ url_for('active_tournament', tournament_id=tournament['id']) }}" class="btn-secondary btn-small">Näytä</a>
                                    <form method="POST" action="{{ url_for('end_tournament', tournament_id=tournament['id']) }}" style="display:inline;" class="confirm-form" data-confirm="Lopeta turnaus '{{ tournament['name'] }}'?">
                                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                        <button type="submit" class="btn-warning btn-small">Lopeta</button>
                                    </form>
                                    {% else %}
                                    <a href="{{ url_for('leaderboard', tournament_id=tournament['id']) }}" class="btn-secondary btn-small">Näytä</a>
                                    {% endif %}
                                    <form method="POST" action="{{ url_for('admin_delete_tournament', tournament_id=tournament['id']) }}" style="display:inline;" class="confirm-form" data-confirm="Poista turnaus '{{ tournament['name'] }}'? Tätä ei voi perua.">
                                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                        <button type="submit" class="btn-danger btn-small">Poista</button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <p class="season-meta">Ei vielä turnauksia.</p>
                    {% endif %}

                    <div class="season-actions">
                        <button type="button" id="open-create-tournament-btn" class="btn-primary">+ Luo turnaus</button>
                        <form method="POST" action="/admin/seasons/end-current" class="confirm-form" data-confirm="Lopeta {{ current_season.name }}?">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <button type="submit" class="btn-warning">Lopeta kausi</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- Archived Seasons -->
            {% for season in archived_seasons %}
            <div class="season-row">
                <div class="season-header" onclick="toggleSeason({{ season.id }})">
                    <span class="season-toggle-icon" id="season-icon-{{ season.id }}">▶</span>
                    <span class="season-name">{{ season.name }}</span>
                    <span class="season-badge ended">Päättynyt</span>
                    <span class="season-tournament-count">{{ season.tournament_count }} turnausta</span>
                </div>
                <div class="season-details" id="season-details-{{ season.id }}">
                    <p class="season-meta">Luotu: {{ season.created_at[:10] }} | Päättynyt: {{ season.ended_at[:10] if season.ended_at else '-' }}</p>

                    {% if season.tournaments %}
                    <table class="season-tournaments-table">
                        <thead>
                            <tr>
                                <th>Turnaus</th>
                                <th>Pvm</th>
                                <th>Tila</th>
                                <th>Toiminnot</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for tournament in season.tournaments %}
                            <tr>
                                <td>{{ tournament['name'] }}</td>
                                <td>{{ tournament['created_at'][:10] }}</td>
                                <td><span class="status-badge completed-badge">Päättynyt</span></td>
                                <td class="actions">
                                    <a href="{{ url_for('leaderboard', tournament_id=tournament['id']) }}" class="btn-secondary btn-small">Näytä</a>
                                    <form method="POST" action="{{ url_for('admin_delete_tournament', tournament_id=tournament['id']) }}" style="display:inline;" class="confirm-form" data-confirm="Poista turnaus '{{ tournament['name'] }}'? Tätä ei voi perua.">
                                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                        <button type="submit" class="btn-danger btn-small">Poista</button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <p class="season-meta">Ei turnauksia.</p>
                    {% endif %}

                    <div class="season-actions">
                        <form method="POST" action="/admin/seasons/{{ season.id }}/activate" class="confirm-form" data-confirm="Aseta {{ season.name }} nykyiseksi kaudeksi?">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <button type="submit" class="btn-secondary">Aseta nykyiseksi</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Create Season -->
        <button type="button" id="toggle-create-season-btn" class="btn-primary">+ Luo uusi kausi</button>
        <div class="create-season-inline" id="create-season-form">
            <form method="POST" action="/admin/seasons/create" style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;width:100%;">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <input type="text" name="season_name" placeholder="Kauden nimi (esim. Kevät 2026)" maxlength="100" required style="flex:1;min-width:200px;">
                <button type="submit" class="btn-primary">Luo</button>
                <button type="button" id="cancel-create-season-btn" class="btn-secondary">Peruuta</button>
            </form>
        </div>
    </div>
</div>
```

**Step 2: Commit**

```bash
git add templates/admin_dashboard.html
git commit -m "feat: replace seasons tab with accordion layout"
```

---

## Task 4: Add JavaScript for Accordion Toggle

**Files:**
- Modify: `templates/admin_dashboard.html` (add to script section at bottom)

**Step 1: Add toggleSeason function and create-season handlers**

Find the `<script nonce="{{ csp_nonce }}">` block in admin_dashboard.html and add:

```javascript
// Season accordion toggle
function toggleSeason(seasonId) {
    const details = document.getElementById('season-details-' + seasonId);
    const icon = document.getElementById('season-icon-' + seasonId);

    if (details.classList.contains('show')) {
        details.classList.remove('show');
        icon.textContent = '▶';
    } else {
        details.classList.add('show');
        icon.textContent = '▼';
    }
}

// Create season form toggle
document.getElementById('toggle-create-season-btn')?.addEventListener('click', function() {
    document.getElementById('create-season-form').classList.add('show');
    this.style.display = 'none';
});

document.getElementById('cancel-create-season-btn')?.addEventListener('click', function() {
    document.getElementById('create-season-form').classList.remove('show');
    document.getElementById('toggle-create-season-btn').style.display = '';
});
```

**Step 2: Commit**

```bash
git add templates/admin_dashboard.html
git commit -m "feat: add accordion toggle JavaScript"
```

---

## Task 5: Test Manually and Fix Issues

**Step 1: Start the dev server**

```bash
cd .worktrees/seasons-accordion
python3 -m flask run --port 5001
```

**Step 2: Test in browser**

1. Go to http://localhost:5001/admin
2. Log in
3. Check Seasons tab:
   - Current season shows with gold border
   - Click to expand - tournaments appear
   - Archived seasons expand with their tournaments
   - "Luo uusi kausi" shows inline form
   - All buttons work (Aloita, Muokkaa, Lopeta, Näytä, Poista)

**Step 3: Fix any issues found**

**Step 4: Run tests**

```bash
python3 -m pytest --tb=short -q
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "fix: address issues from manual testing"
```

---

## Task 6: Merge and Cleanup

**Step 1: Merge to main**

```bash
cd /Users/teemu/Documents/Teemu/Code/tennis-scorer
git merge feature/seasons-accordion
```

**Step 2: Push**

```bash
git push
```

**Step 3: Remove worktree**

```bash
git worktree remove .worktrees/seasons-accordion
git branch -d feature/seasons-accordion
```
