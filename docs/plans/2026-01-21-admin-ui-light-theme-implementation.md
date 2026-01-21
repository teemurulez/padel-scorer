# Admin UI Light Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert all admin pages from dark theme to light theme while keeping yellow/gold (#FFD700) as the accent color.

**Architecture:** Update CSS custom properties in admin.css to light colors, extract inline styles from auth pages to shared classes, update admin_edit.css accent from blue to gold.

**Tech Stack:** CSS, Jinja2 templates, Flask

---

### Task 1: Update admin.css CSS Variables

**Files:**
- Modify: `static/css/admin.css:1-20`

**Step 1: Replace dark theme variables with light theme**

Replace the `:root` block with:

```css
:root {
    /* Light theme backgrounds */
    --bg-page: #f5f5f5;
    --bg-surface: #ffffff;
    --bg-surface-alt: #fafafa;
    --bg-input: #ffffff;

    /* Borders */
    --border-color: #e0e0e0;
    --border-strong: #d0d0d0;

    /* Text colors */
    --text-primary: #1a1a2e;
    --text-body: #333333;
    --text-muted: #666666;
    --text-light: #888888;

    /* Accent colors (gold) */
    --accent: #FFD700;
    --accent-hover: #e6c200;
    --accent-dark: #b8960a;
    --on-accent: #1a1a2e;

    /* Status colors */
    --success: #16a34a;
    --success-light: #dcfce7;
    --warning: #f59e0b;
    --warning-light: #fef3c7;
    --error: #dc2626;
    --error-light: #fee2e2;

    /* Legacy mappings (for gradual migration) */
    --black: #1a1a2e;
    --dark-gray: #f5f5f5;
    --medium-gray: #ffffff;
    --light-gray: #fafafa;
    --yellow: #FFD700;
    --yellow-hover: #e6c200;
    --yellow-dark: #b8960a;
    --white: #1a1a2e;
    --neutral-gray: #666666;
    --empty-state-gray: #888888;
    --success-green: #16a34a;
    --warning-orange: #f59e0b;
    --warning-orange-dark: #d97706;
}
```

**Step 2: Verify server is running**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/admin/login`
Expected: 200 or 302

**Step 3: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update admin.css variables for light theme"
```

---

### Task 2: Update admin.css Body and Header Styles

**Files:**
- Modify: `static/css/admin.css:22-75`

**Step 1: Update body styles**

Replace:
```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background-color: var(--black);
    color: var(--text-light);
    min-height: 100vh;
}
```

With:
```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background-color: var(--bg-page);
    color: var(--text-body);
    min-height: 100vh;
}
```

**Step 2: Update header styles**

Replace:
```css
.admin-header {
    background-color: var(--dark-gray);
    border-bottom: 3px solid var(--yellow);
    padding: 1rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.admin-logo {
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--yellow);
    letter-spacing: 1px;
}
```

With:
```css
.admin-header {
    background-color: var(--bg-surface);
    border-bottom: 3px solid var(--accent);
    padding: 1rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.admin-logo {
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--text-primary);
    letter-spacing: 1px;
}
```

**Step 3: Update logout button**

Replace:
```css
.logout-btn {
    background-color: transparent;
    color: var(--yellow);
    border: 2px solid var(--yellow);
```

With:
```css
.logout-btn {
    background-color: transparent;
    color: var(--text-primary);
    border: 2px solid var(--border-strong);
```

**Step 4: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update admin header to light theme"
```

---

### Task 3: Update admin.css Tab and Panel Styles

**Files:**
- Modify: `static/css/admin.css:99-165`

**Step 1: Update tab navigation**

Replace:
```css
.tab-nav {
    background-color: var(--dark-gray);
    border-bottom: 2px solid var(--medium-gray);
```

With:
```css
.tab-nav {
    background-color: var(--bg-surface);
    border-bottom: 2px solid var(--border-color);
```

**Step 2: Update tab button styles**

Replace:
```css
.tab-btn {
    background-color: transparent;
    color: var(--text-light);
```

With:
```css
.tab-btn {
    background-color: transparent;
    color: var(--text-muted);
```

Replace:
```css
.tab-btn:hover {
    background-color: var(--medium-gray);
    color: var(--yellow);
}

.tab-btn.active {
    color: var(--yellow);
    border-bottom-color: var(--yellow);
    background-color: var(--medium-gray);
}
```

With:
```css
.tab-btn:hover {
    background-color: var(--bg-surface-alt);
    color: var(--text-primary);
}

.tab-btn.active {
    color: var(--text-primary);
    border-bottom-color: var(--accent);
    background-color: var(--bg-surface);
    font-weight: 600;
}
```

**Step 3: Update tab panel styles**

Replace:
```css
.tab-panel {
    background-color: var(--dark-gray);
    border-radius: 8px;
    padding: 2rem;
    min-height: 400px;
}

.tab-panel h2 {
    color: var(--yellow);
```

With:
```css
.tab-panel {
    background-color: var(--bg-surface);
    border-radius: 8px;
    padding: 2rem;
    min-height: 400px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.tab-panel h2 {
    color: var(--text-primary);
```

**Step 4: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update admin tabs and panels to light theme"
```

---

### Task 4: Update admin.css Cards, Tables, and Buttons

**Files:**
- Modify: `static/css/admin.css:246-400`

**Step 1: Update season card styles**

Replace:
```css
.season-card {
    background-color: var(--medium-gray);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    border-left: 4px solid var(--yellow);
}
```

With:
```css
.season-card {
    background-color: var(--bg-surface);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    border-left: 4px solid var(--accent);
    border: 1px solid var(--border-color);
    border-left: 4px solid var(--accent);
}
```

Replace:
```css
.season-card h3 {
    color: var(--yellow);
```

With:
```css
.season-card h3 {
    color: var(--text-primary);
```

**Step 2: Update table styles**

Replace:
```css
.admin-table {
    width: 100%;
    border-collapse: collapse;
    background-color: var(--medium-gray);
    border-radius: 8px;
    overflow: hidden;
}

.admin-table thead {
    background-color: var(--light-gray);
}

.admin-table th,
.admin-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--light-gray);
}

.admin-table th {
    color: var(--yellow);
    font-weight: 600;
}

.admin-table td {
    color: var(--text-light);
}

.admin-table tbody tr:hover {
    background-color: var(--light-gray);
}
```

With:
```css
.admin-table {
    width: 100%;
    border-collapse: collapse;
    background-color: var(--bg-surface);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
}

.admin-table thead {
    background-color: var(--bg-surface-alt);
}

.admin-table th,
.admin-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.admin-table th {
    color: var(--text-primary);
    font-weight: 600;
}

.admin-table td {
    color: var(--text-body);
}

.admin-table tbody tr:hover {
    background-color: var(--bg-surface-alt);
}
```

**Step 3: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update admin cards and tables to light theme"
```

---

### Task 5: Update admin.css Form Styles

**Files:**
- Modify: `static/css/admin.css:330-515`

**Step 1: Update create season form**

Replace:
```css
.create-season-form {
    background-color: var(--medium-gray);
```

With:
```css
.create-season-form {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
```

Replace:
```css
.create-season-form h3 {
    color: var(--yellow);
```

With:
```css
.create-season-form h3 {
    color: var(--text-primary);
```

Replace:
```css
.create-season-form input[type="text"] {
    flex: 1;
    padding: 0.75rem;
    background-color: var(--light-gray);
    border: 2px solid var(--light-gray);
    border-radius: 4px;
    color: var(--text-light);
    font-size: 1rem;
}

.create-season-form input[type="text"]:focus {
    outline: none;
    border-color: var(--yellow);
}
```

With:
```css
.create-season-form input[type="text"] {
    flex: 1;
    padding: 0.75rem;
    background-color: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-body);
    font-size: 1rem;
}

.create-season-form input[type="text"]:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.2);
}
```

**Step 2: Update create tournament form inputs**

Replace:
```css
.create-tournament-form label {
    display: block;
    color: var(--yellow);
```

With:
```css
.create-tournament-form label {
    display: block;
    color: var(--text-primary);
```

Replace:
```css
.create-tournament-form input[type="text"],
.create-tournament-form select,
.create-tournament-form textarea {
    width: 100%;
    padding: 1rem;
    font-size: 1rem;
    background-color: var(--medium-gray);
    border: 2px solid var(--light-gray);
    border-radius: 4px;
    color: var(--white);
```

With:
```css
.create-tournament-form input[type="text"],
.create-tournament-form select,
.create-tournament-form textarea {
    width: 100%;
    padding: 1rem;
    font-size: 1rem;
    background-color: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-body);
```

Replace:
```css
.create-tournament-form input:focus,
.create-tournament-form select:focus,
.create-tournament-form textarea:focus {
    outline: none;
    border-color: var(--yellow);
}
```

With:
```css
.create-tournament-form input:focus,
.create-tournament-form select:focus,
.create-tournament-form textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.2);
}
```

**Step 3: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update admin forms to light theme"
```

---

### Task 6: Add Auth Page Shared Styles to admin.css

**Files:**
- Modify: `static/css/admin.css` (add at end of file)

**Step 1: Add auth page styles**

Add at end of admin.css:

```css
/* Auth Pages (Login, Setup, Forgot Password) */
body.auth-page {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    margin: 0;
    background-color: var(--bg-page);
}

.auth-container {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 40px;
    max-width: 400px;
    width: 100%;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.auth-container.wide {
    max-width: 500px;
}

.auth-container h1 {
    color: var(--text-primary);
    margin-top: 0;
    margin-bottom: 1.5rem;
    text-align: center;
    font-size: 1.5rem;
}

.auth-container .subtitle {
    color: var(--text-muted);
    text-align: center;
    margin-bottom: 2rem;
}

.auth-form .form-group {
    margin-bottom: 1.25rem;
}

.auth-form label {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--text-primary);
    font-weight: 600;
    font-size: 0.9rem;
}

.auth-form input[type="password"],
.auth-form input[type="text"],
.auth-form input[type="email"] {
    width: 100%;
    padding: 12px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-input);
    color: var(--text-body);
    border-radius: 4px;
    font-size: 1rem;
    box-sizing: border-box;
}

.auth-form input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.2);
}

.auth-form .help-text {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-top: 0.5rem;
}

.auth-form .btn-primary {
    width: 100%;
    padding: 12px;
    margin-top: 0.5rem;
}

.auth-info-box {
    background-color: var(--bg-surface-alt);
    border: 1px solid var(--border-color);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    text-align: center;
}

.auth-info-box strong {
    color: var(--text-primary);
}

.auth-warning {
    background-color: var(--warning-light);
    border: 1px solid var(--warning);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
}

.auth-warning p {
    margin: 0;
    color: var(--text-body);
    font-size: 0.9rem;
}

.auth-links {
    text-align: center;
    margin-top: 1.5rem;
}

.auth-links a {
    color: var(--text-primary);
    text-decoration: none;
}

.auth-links a:hover {
    text-decoration: underline;
    color: var(--accent-dark);
}

.auth-links + .auth-links {
    margin-top: 0.75rem;
}

/* Flash messages for auth pages */
.auth-container .flash-messages {
    margin-bottom: 1.5rem;
    padding: 0;
    max-width: none;
}

.auth-container .flash-error {
    background-color: var(--error-light);
    color: var(--error);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border: 1px solid var(--error);
}

.auth-container .flash-success {
    background-color: var(--success-light);
    color: var(--success);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border: 1px solid var(--success);
}
```

**Step 2: Commit**

```bash
git add static/css/admin.css
git commit -m "feat: add shared auth page styles to admin.css"
```

---

### Task 7: Update admin_login.html Template

**Files:**
- Modify: `templates/admin_login.html`

**Step 1: Replace entire file content**

```html
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ylläpitäjän kirjautuminen</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
</head>
<body class="auth-page">
    <div class="auth-container">
        <h1>Ylläpito</h1>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        {% if 'success' in message.lower() or 'created' in message.lower() %}
                            <div class="flash-success">{{ message }}</div>
                        {% else %}
                            <div class="flash-error">{{ message }}</div>
                        {% endif %}
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <form method="POST" action="/admin/login" class="auth-form">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="form-group">
                <label for="password">Salasana</label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    required
                    placeholder="Syötä ylläpidon salasana"
                    autofocus
                >
            </div>

            <button type="submit" class="btn-primary">Kirjaudu</button>
        </form>

        <div class="auth-links">
            <a href="{{ url_for('admin_forgot_password') }}">Unohditko salasanan?</a>
        </div>

        <div class="auth-links">
            <a href="/">← Takaisin etusivulle</a>
        </div>
    </div>
</body>
</html>
```

**Step 2: Verify visually**

Open http://localhost:5050/admin/login in browser and verify:
- Light gray background
- White card with subtle shadow
- Dark text, gold button
- Clean, modern appearance

**Step 3: Commit**

```bash
git add templates/admin_login.html
git commit -m "refactor: update admin login to use shared light theme styles"
```

---

### Task 8: Update admin_setup.html Template

**Files:**
- Modify: `templates/admin_setup.html`

**Step 1: Replace entire file content**

```html
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ylläpidon asennus</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
</head>
<body class="auth-page">
    <div class="auth-container">
        <h1>Ylläpidon asennus</h1>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-error">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <p class="subtitle">
            Luo ylläpidon salasana suojataksesi ylläpitonäkymän.
        </p>

        <form method="POST" action="/admin/setup" class="auth-form">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="form-group">
                <label for="password">Salasana</label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    required
                    minlength="8"
                    placeholder="Syötä salasana (vähintään 8 merkkiä)"
                >
                <div class="help-text">Vähintään 8 merkkiä vaaditaan</div>
            </div>

            <div class="form-group">
                <label for="confirm_password">Vahvista salasana</label>
                <input
                    type="password"
                    id="confirm_password"
                    name="confirm_password"
                    required
                    minlength="8"
                    placeholder="Vahvista salasana"
                >
            </div>

            <button type="submit" class="btn-primary">Luo ylläpitotili</button>
        </form>
    </div>
</body>
</html>
```

**Step 2: Commit**

```bash
git add templates/admin_setup.html
git commit -m "refactor: update admin setup to use shared light theme styles"
```

---

### Task 9: Update admin_forgot_password.html Template

**Files:**
- Modify: `templates/admin_forgot_password.html`

**Step 1: Replace entire file content**

```html
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unohtunut salasana - Ylläpito</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
</head>
<body class="auth-page">
    <div class="auth-container wide">
        <h1>Nollaa salasana</h1>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        {% if 'success' in message.lower() or 'temporary' in message.lower() %}
                            <div class="flash-success">{{ message }}</div>
                        {% else %}
                            <div class="flash-error">{{ message }}</div>
                        {% endif %}
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <p class="subtitle">
            Napsauta alla olevaa painiketta luodaksesi uuden väliaikaisen salasanan.
            Salasana lähetetään rekisteröityyn sähköpostiosoitteeseesi.
        </p>

        <div class="auth-info-box">
            Sähköposti lähetetään osoitteeseen: <strong>teemu.sevon@gmail.com</strong>
        </div>

        <div class="auth-warning">
            <p>⚠️ Tämä korvaa nykyisen salasanasi välittömästi väliaikaisella salasanalla.</p>
        </div>

        <form method="POST" action="{{ url_for('admin_forgot_password') }}" class="auth-form">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit" class="btn-primary">Luo ja lähetä väliaikainen salasana</button>
        </form>

        <div class="auth-links">
            <a href="{{ url_for('admin_login') }}">← Takaisin kirjautumiseen</a>
        </div>
    </div>
</body>
</html>
```

**Step 2: Commit**

```bash
git add templates/admin_forgot_password.html
git commit -m "refactor: update forgot password to use shared light theme styles"
```

---

### Task 10: Update admin_edit.css Accent Colors

**Files:**
- Modify: `static/css/admin_edit.css`

**Step 1: Replace blue accent colors with gold**

Replace all occurrences of `#007bff` with `#FFD700`:
- Line 67: `.title-input:focus` border-bottom-color
- Line 345: `.pairings-search input:focus` border-color
- Line 419: `.player-slot.selected` background
- Line 465-466: `.unassigned-player:hover` border-color
- Line 468-470: `.unassigned-player.selected` background and border
- Line 503-513: `.edit-page .btn-primary` background

Replace `#0056b3` (hover blue) with `#e6c200`:
- Line 513: `.edit-page .btn-primary:hover`

Replace `#2563eb` with `#b8960a`:
- Line 304: `.validation-suggestion .btn-link:hover`

**Step 2: Update specific styles**

Replace:
```css
.edit-page .btn-primary {
    background: #007bff;
    color: white;
```

With:
```css
.edit-page .btn-primary {
    background: #FFD700;
    color: #1a1a2e;
```

Replace:
```css
.edit-page .btn-primary:hover { background: #0056b3; }
```

With:
```css
.edit-page .btn-primary:hover { background: #e6c200; }
```

Replace:
```css
.player-slot.selected {
    background: #007bff;
    color: white;
}
```

With:
```css
.player-slot.selected {
    background: #FFD700;
    color: #1a1a2e;
}
```

Replace:
```css
.unassigned-player:hover {
    border-color: #007bff;
}

.unassigned-player.selected {
    background: #007bff;
    color: white;
    border-color: #007bff;
}
```

With:
```css
.unassigned-player:hover {
    border-color: #FFD700;
}

.unassigned-player.selected {
    background: #FFD700;
    color: #1a1a2e;
    border-color: #FFD700;
}
```

Replace:
```css
.btn-link {
    background: none;
    border: none;
    color: #007bff;
```

With:
```css
.btn-link {
    background: none;
    border: none;
    color: #b8960a;
```

**Step 3: Commit**

```bash
git add static/css/admin_edit.css
git commit -m "refactor: update tournament edit accent from blue to gold"
```

---

### Task 11: Update Remaining admin.css Styles

**Files:**
- Modify: `static/css/admin.css`

**Step 1: Update edit form container styles**

Replace:
```css
.edit-form-container {
    padding: 2rem;
    background-color: var(--medium-gray);
```

With:
```css
.edit-form-container {
    padding: 2rem;
    background-color: var(--bg-surface-alt);
```

Replace:
```css
.edit-form-container h4 {
    color: var(--yellow);
```

With:
```css
.edit-form-container h4 {
    color: var(--text-primary);
```

Replace:
```css
.edit-form-container label {
    display: block;
    color: var(--white);
```

With:
```css
.edit-form-container label {
    display: block;
    color: var(--text-primary);
```

**Step 2: Update form input styles in edit container**

Replace:
```css
.edit-form-container .form-input,
.edit-form-container .form-textarea {
    width: 100%;
    padding: 0.75rem;
    font-size: 1rem;
    background-color: var(--dark-gray);
    border: 2px solid var(--light-gray);
    border-radius: 4px;
    color: var(--white);
```

With:
```css
.edit-form-container .form-input,
.edit-form-container .form-textarea {
    width: 100%;
    padding: 0.75rem;
    font-size: 1rem;
    background-color: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-body);
```

Replace:
```css
.edit-form-container .form-input:focus,
.edit-form-container .form-textarea:focus {
    outline: none;
    border-color: var(--yellow);
}
```

With:
```css
.edit-form-container .form-input:focus,
.edit-form-container .form-textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.2);
}
```

**Step 3: Update validation results for light theme**

Replace:
```css
.validation-results {
    margin-top: 1rem;
    background-color: var(--medium-gray);
```

With:
```css
.validation-results {
    margin-top: 1rem;
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
```

Replace:
```css
.validation-item {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--light-gray);
```

With:
```css
.validation-item {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
```

Replace:
```css
.validation-item .player-name {
    font-weight: 500;
    color: var(--white);
}
```

With:
```css
.validation-item .player-name {
    font-weight: 500;
    color: var(--text-primary);
}
```

Replace:
```css
.validation-summary {
    padding: 1rem;
    background: var(--light-gray);
    color: var(--text-light);
```

With:
```css
.validation-summary {
    padding: 1rem;
    background: var(--bg-surface-alt);
    color: var(--text-body);
```

**Step 4: Commit**

```bash
git add static/css/admin.css
git commit -m "refactor: update remaining admin.css styles to light theme"
```

---

### Task 12: Visual Testing and Final Adjustments

**Files:**
- May modify: `static/css/admin.css`, `static/css/admin_edit.css`

**Step 1: Test all admin pages visually**

Open each page and verify light theme:
1. http://localhost:5050/admin/login - Login page
2. http://localhost:5050/admin - Dashboard (after login)
3. Click on a tournament to open edit page

**Step 2: Check for any missed dark theme colors**

Look for:
- Dark backgrounds that should be light
- Light text that should be dark
- Blue accents that should be gold

**Step 3: Run the test suite**

Run: `cd /Users/teemu/Documents/Teemu/Code/tennis-scorer && python -m pytest -x -q`
Expected: All tests pass

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete admin UI light theme conversion"
```

---

### Task 13: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Step 1: Update the TODO file**

Mark admin UI polish as done and update last updated date.

**Step 2: Commit**

```bash
git add TODO.md
git commit -m "docs: update TODO.md - admin UI polish complete"
```
