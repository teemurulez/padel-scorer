# Admin Seasons View Redesign

## Problem

The current Seasons tab has visual clutter and unclear hierarchy:
- Current season card, tournaments table, create buttons, and archived seasons all shown at once
- Hard to see relationship between seasons and their tournaments

## Solution

Replace with an accordion list where each season is an expandable row.

## Design

### Season List (Collapsed)

```
┌─────────────────────────────────────────────────────────┐
│ ▶ Talvi 2025          🏆 Nykyinen    3 turnausta       │
├─────────────────────────────────────────────────────────┤
│ ▶ Syksy 2024          Päättynyt      5 turnausta       │
├─────────────────────────────────────────────────────────┤
│ ▶ Kevät 2024          Päättynyt      4 turnausta       │
└─────────────────────────────────────────────────────────┘

[ + Luo uusi kausi ]
```

- Current season always at top with highlighted background
- Arrow indicates expandable (▶ collapsed, ▼ expanded)
- Status badge: "Nykyinen" or "Päättynyt"
- Tournament count shown inline

### Expanded Season View

```
┌─────────────────────────────────────────────────────────┐
│ ▼ Talvi 2025          🏆 Nykyinen    3 turnausta       │
│ ─────────────────────────────────────────────────────── │
│   Luotu: 2025-01-15                                     │
│                                                         │
│   Turnaukset:                                           │
│   ┌─────────────────────────────────────────────────┐   │
│   │ Turnaus 3  2025-01-28  Valmistelu  [Aloita][Muokkaa][Poista] │
│   │ Turnaus 2  2025-01-21  Käynnissä   [Näytä][Lopeta][Poista]   │
│   │ Turnaus 1  2025-01-14  Päättynyt   [Näytä][Poista]           │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
│   [ + Luo turnaus ]        [ Lopeta kausi ]            │
└─────────────────────────────────────────────────────────┘
```

### Tournament Actions by Status

| Status | Actions |
|--------|---------|
| Valmistelu (setup) | Aloita, Muokkaa, Poista |
| Käynnissä (active) | Näytä, Lopeta, Poista |
| Päättynyt (completed) | Näytä, Poista |

### Season Actions

- Current season: "Luo turnaus", "Lopeta kausi"
- Archived season: "Aseta nykyiseksi"

### Create Season (Inline Form)

Clicking "+ Luo uusi kausi" expands inline form:

```
┌─────────────────────────────────────────────────────────┐
│  Kauden nimi: [___________________]  [Luo] [Peruuta]   │
└─────────────────────────────────────────────────────────┘
```

### Edge Cases

**No seasons exist:**
- Show message: "Ei kausia. Luo ensimmäinen kausi aloittaaksesi."
- Show "+ Luo uusi kausi" button

**No current season (all archived):**
- List shows all archived seasons
- User can create new or activate an archived one

## Implementation Notes

- Reuse existing accordion/expandable CSS patterns from player stats
- Tournament action forms already exist, just need new layout
- Remove tournament creation modal, use existing flow from season accordion
