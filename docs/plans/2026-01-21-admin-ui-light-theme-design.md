# Admin UI Light Theme Design

## Overview

Convert all admin pages from dark theme to light theme while keeping yellow/gold (#FFD700) as the accent color.

## Color Palette

| Role | Variable | Color | Usage |
|------|----------|-------|-------|
| Background | `--bg-page` | `#f5f5f5` | Page background |
| Surface | `--bg-surface` | `#ffffff` | Cards, panels, inputs |
| Surface alt | `--bg-surface-alt` | `#fafafa` | Alternate surface |
| Border | `--border-color` | `#e0e0e0` | Subtle borders |
| Border strong | `--border-strong` | `#d0d0d0` | Emphasized borders |
| Text primary | `--text-primary` | `#1a1a2e` | Headings, important text |
| Text secondary | `--text-body` | `#333333` | Body text |
| Text muted | `--text-muted` | `#666666` | Hints, metadata |
| Accent | `--accent` | `#FFD700` | Primary buttons, highlights |
| Accent hover | `--accent-hover` | `#e6c200` | Button hover state |
| Accent dark | `--accent-dark` | `#b8960a` | Active/pressed state |
| On accent | `--on-accent` | `#1a1a2e` | Text on yellow buttons |
| Success | `--success` | `#16a34a` | Success states |
| Warning | `--warning` | `#f59e0b` | Warning states |
| Error | `--error` | `#dc2626` | Error states |

## Pages Affected

### 1. admin_login.html
- Remove all inline `<style>` block
- Add `<link>` to `admin.css`
- Add class `auth-page` to body
- Use shared `.auth-container`, `.auth-form` classes

### 2. admin_forgot_password.html
- Remove all inline `<style>` block
- Add `<link>` to `admin.css`
- Use shared auth classes

### 3. admin_setup.html
- Remove all inline `<style>` block
- Add `<link>` to `admin.css`
- Use shared auth classes

### 4. admin_dashboard.html
- Already uses `admin.css`
- Template stays the same, CSS changes handle styling

### 5. admin_tournament_edit.html
- Already light theme
- Update accent colors from blue (#007bff) to gold (#FFD700)

## CSS Changes

### admin.css
Complete rewrite with:
- CSS custom properties for theming
- Light background colors
- Dark text colors
- Gold accent color
- Shared auth page styles (new)
- Existing dashboard styles (updated colors)

### admin_edit.css
- Replace blue (#007bff) with gold (#FFD700)
- Adjust hover states accordingly
- Keep layout unchanged

## Visual Examples

### Buttons
```css
.btn-primary {
    background: #FFD700;
    color: #1a1a2e;
    border: none;
}
.btn-primary:hover {
    background: #e6c200;
}
```

### Auth Pages
- Centered card on light gray background
- White card with subtle shadow
- Gold accent on headings and buttons
- Clean, minimal look

### Dashboard
- Light gray page background
- White panel cards
- Gold tab indicator and headings
- Dark text for readability
