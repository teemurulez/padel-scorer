# Round View UI Redesign

**Date:** 2026-01-10
**Status:** Approved

---

## Overview

Redesign the active round view (`active_round.html`) with cleaner branding, improved mobile UX, and better touch targets.

---

## Design Decisions

- **Color theme:** Clean white background, black text, yellow (#FFD700) accent buttons
- **Header:** Bold title with small logo, tournament subtitle
- **Mobile-first:** 56px minimum button height, stacked buttons, larger fonts

---

## Header Design

```
┌─────────────────────────────────────┐
│  [Logo 40px]                        │
│                                     │
│        KIERROS 3                    │
│     (bold, large, black)            │
│                                     │
│   Tournament Name • 8 kenttää       │
│     (gray subtitle)                 │
└─────────────────────────────────────┘
```

**Specs:**
- Clean white background with subtle bottom border (#e0e0e0)
- Padel Paroni logo: 40px height, centered
- "KIERROS X": Bold, 2rem, black (#1a1a1a)
- Subtitle: Tournament name + court count, gray (#666), 0.95rem
- Padding: 1.5rem

**Movement note (round 2+):**
- Yellow pill badge: "↑ Voittajat ylös • ↓ Häviäjät alas"
- Background: #FFF3CD, text: #856404

---

## Match Card Design

```
┌─────────────────────────────────────┐
│  KENTTÄ 1                           │
│  ─────────────────────────────────  │
│                                     │
│  Joukkue 1          Joukkue 2       │
│  Matti M.     vs    Pekka P.        │
│  Anna K.            Liisa L.        │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      ⚡ SYÖTÄ TULOS         │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │    ✏️ Muokkaa joukkueita    │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

**Specs:**
- White background, subtle shadow, 12px border-radius
- Court number: Bold header with divider line below
- Teams: Side-by-side on desktop, readable on mobile
- Player names: 1.1rem font
- Card spacing: 1.25rem gap

**Buttons:**
- Primary (Syötä tulos): Yellow (#FFD700), black text, 56px height, full width
- Secondary (Muokkaa): White, gray border, smaller text, 48px height

**Completed card:**
- 4px green left border (#22c55e)
- "✓ Joukkue X voitti" text badge
- Slightly grayed (opacity 0.9)

---

## Bottom Actions

```
┌─────────────────────────────────────┐
│       3/8 ottelua valmis            │
│                                     │
│  ┌─────────────────────────────┐    │
│  │    📊 NÄYTÄ TULOKSET        │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  ▶️ Aloita seuraava kierros │    │
│  └─────────────────────────────┘    │
│                                     │
│         ← Takaisin                  │
└─────────────────────────────────────┘
```

**Specs:**
- Progress text: Gray, centered, 0.9rem
- "Näytä tulokset": Yellow background, black text, 56px height
- "Aloita seuraava kierros": White, black border (only when all complete)
- "Takaisin": Text link, gray, centered
- Bottom padding: 2rem

---

## Files to Modify

- `templates/active_round.html` - Complete template rewrite

---

## Implementation Notes

- Remove purple gradient
- Add logo image reference
- Need tournament name passed to template (check if already available)
- Keep existing JavaScript for next round form submission
