# Player Stats Expansion Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add detailed player statistics to player_profile.html

**Architecture:** Expand existing profile page with new stats section, calculate stats in backend

**Tech Stack:** Flask, SQLite, Jinja2

**Rollback:** `git reset --hard pre-player-stats`

---

## UI Design

Lisätään player_profile.html-sivulle "Lisätilastot" -osio nykyisen stats-grid:in jälkeen:

**Tilastot:**
1. **Paras pari** - "Matti Meikäläinen - 8 voittoa yhdessä"
2. **Voittoputki** - "5 peräkkäistä voittoa"
3. **Paras turnaus** - "Tammikuu 1 - 4 voittoa"
4. **Huonoin turnaus** - "Helmikuu 2 - 0 voittoa"

**Tyyli:**
- Sama stat-card tyyli kuin nykyiset tilastot
- 2x2 grid mobiilissa, 4 vierekkäin desktopilla
- Näytetään vain jos pelaajalla on dataa

**Reunatapaukset:**
- Jos vain 1 turnaus → paras ja huonoin sama, näytetään vain "paras"
- Jos 0 voittoa → voittoputki = 0

## Backend Design

**Laskennat player_profile() routessa:**

**1. Paras pari:**
- Hae voitetut ottelut nykyiseltä kaudelta
- Tunnista pari (team1: player1+player2, team2: player3+player4)
- Ryhmittele parin mukaan, laske voitot
- Palauta: partner_name, wins_together

**2. Pisin voittoputki:**
- Hae kaikki ottelut aikajärjestyksessä (round_id, created_at)
- Käy läpi, laske pisin peräkkäinen voittosarja
- Palauta: numero

**3. Paras turnaus:**
- Ryhmittele voitot turnauksen mukaan
- ORDER BY wins DESC LIMIT 1
- Palauta: tournament_name, wins

**4. Huonoin turnaus:**
- Sama, ORDER BY wins ASC LIMIT 1
- Palauta: tournament_name, wins

## Data Flow

1. `player_profile()` route hakee neljä tilastoa
2. Välitetään templatelle: `best_partner`, `longest_streak`, `best_tournament`, `worst_tournament`
3. Template näyttää ne ehdollisesti

## Scope

- Vain nykyinen kausi (yhtenäinen muun profiilin kanssa)
- Koko historia voidaan lisätä myöhemmin
