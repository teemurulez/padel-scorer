# Database Restore Feature Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add database restore functionality to Admin Data view

**Architecture:** File upload with strong confirmation, automatic backup before restore, full database replacement within transaction

**Tech Stack:** Flask, SQLite, JavaScript

---

## UI Design

Data-näkymään lisätään "Palauta varmuuskopiosta" -osio:

**Elementit:**
- Otsikko "Palauta varmuuskopiosta"
- Varoitusteksti punaisella: "Tämä korvaa KAIKEN nykyisen datan. Toimintoa ei voi peruuttaa."
- Tiedoston valinta (file input, hyväksyy vain .json)
- Tekstikenttä: "Kirjoita PALAUTA vahvistaaksesi"
- Palauta-nappi (disabled kunnes teksti on oikein JA tiedosto valittu)

**JavaScript-logiikka:**
- Tarkkailee tekstikenttää ja tiedostovalintaa
- Aktivoi napin vasta kun molemmat ehdot täyttyvät
- Ennen lähetystä: lataa automaattinen varmuuskopio

## Backend Design

**Route:** `POST /admin/restore/database`

**Validointi:**
1. Tarkista JSON-rakenne
2. Tarkista että sisältää taulut: `seasons`, `tournaments`, `player_registry`, `tournament_players`, `rounds`, `games`

**Poistojärjestys (foreign keys):**
1. `games` → `rounds` → `tournament_players` → `tournaments` → `seasons` → `player_registry`

**Lisäysjärjestys:**
1. `seasons` → `player_registry` → `tournaments` → `tournament_players` → `rounds` → `games`

**Huom:** `admin_users`-taulu jätetään koskemattomaksi.

## Error Handling

**Tiedoston validointi:**
- Ei tiedostoa → "Valitse JSON-tiedosto"
- Virheellinen JSON → "Virheellinen JSON-tiedosto"
- Puuttuvat taulut → "Varmuuskopio on puutteellinen: puuttuu [taulu]"

**Tietokantavirheet:**
- Kaikki virheet → rollback, flash-virheviesti

**Onnistuminen:**
- Flash: "Tietokanta palautettu onnistuneesti. Palautettu: X kautta, Y turnausta, Z pelaajaa."

**Automaattinen varmuuskopio:**
- JavaScript lataa `/admin/export/database.json` ennen lomakkeen lähetystä
- Jos epäonnistuu → keskeytä, näytä virhe
