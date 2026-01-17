/**
 * Tournament Edit Page JavaScript
 * Handles player editing, validation, and pairing interactions
 */

// State
let currentPlayers = [];
let validationResults = [];
let selectedSlot = null;
let pairingsModified = false;

// Player Editor
function showPlayerEditor() {
    document.getElementById('player-list-view').style.display = 'none';
    document.getElementById('player-editor').style.display = 'block';
    document.getElementById('edit-players-btn').style.display = 'none';
}

function cancelPlayerEdit() {
    document.getElementById('player-list-view').style.display = 'block';
    document.getElementById('player-editor').style.display = 'none';
    document.getElementById('edit-players-btn').style.display = 'inline-block';
    // Hide warning indicator
    const warningIndicator = document.getElementById('validation-warning');
    if (warningIndicator) warningIndicator.style.display = 'none';
}

function backToEditor() {
    document.getElementById('validation-results').style.display = 'none';
    document.getElementById('player-editor').style.display = 'block';
    // Hide warning indicator when going back to edit
    const warningIndicator = document.getElementById('validation-warning');
    if (warningIndicator) warningIndicator.style.display = 'none';
}

// Validation
async function validatePlayers() {
    const textarea = document.getElementById('players-textarea');
    const playersText = textarea.value.trim();

    if (!playersText) {
        alert('Syötä pelaajien nimet');
        return;
    }

    // Check player count - must be divisible by 4
    const lines = playersText.split('\n').filter(l => l.trim());

    if (lines.length < 4) {
        alert('Vähintään 4 pelaajaa tarvitaan (1 kenttä).');
        return;
    }

    if (lines.length % 4 !== 0) {
        const nearestLower = Math.floor(lines.length / 4) * 4;
        const nearestHigher = nearestLower + 4;
        alert(`Pelaajien määrän täytyy olla jaollinen 4:llä. Syötit ${lines.length} pelaajaa. Lisää ${nearestHigher - lines.length} tai poista ${lines.length - nearestLower} pelaajaa.`);
        return;
    }

    // Calculate new number of courts from player count
    const newNumCourts = lines.length / 4;

    try {
        const response = await fetch('/admin/validate-players', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ players: playersText })
        });

        const data = await response.json();
        validationResults = data.results;

        displayValidationResults(data);

        document.getElementById('player-editor').style.display = 'none';
        document.getElementById('validation-results').style.display = 'block';

    } catch (error) {
        console.error('Validation error:', error);
        alert('Virhe tarkistuksessa. Yritä uudelleen.');
    }
}

function displayValidationResults(data) {
    const container = document.getElementById('validation-list');
    const summary = document.getElementById('validation-summary');
    const applyBtn = document.getElementById('apply-btn');

    container.innerHTML = '';

    data.results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = `validation-item ${result.status}`;
        item.dataset.index = index;

        let icon, content;

        switch (result.status) {
            case 'exact':
                icon = '✓';
                content = `<span class="player-name">${result.name}</span>`;
                break;
            case 'similar':
                icon = '⚠';
                content = `
                    <span class="player-name">${result.name}</span>
                    <span class="validation-suggestion">
                        → ${result.suggestion}?
                        <button onclick="acceptSuggestion(${index})" class="btn-link">Kyllä</button>
                        <button onclick="rejectSuggestion(${index})" class="btn-link">Ei, uusi pelaaja</button>
                    </span>
                `;
                break;
            case 'new':
                icon = '★';
                content = `<span class="player-name">${result.name}</span> <span class="tag">uusi pelaaja</span>`;
                break;
            case 'duplicate':
                icon = '✕';
                content = `<span class="player-name">${result.name}</span> <span class="error">duplikaatti</span>`;
                break;
        }

        item.innerHTML = `<span class="validation-icon">${icon}</span>${content}`;
        container.appendChild(item);
    });

    // Summary
    summary.innerHTML = `
        <strong>Yhteenveto:</strong>
        ${data.summary.exact} tunnettua ·
        ${data.summary.similar} tarkistettavaa ·
        ${data.summary.new} uutta
        ${data.summary.duplicate > 0 ? ` · <span class="error">${data.summary.duplicate} duplikaattia</span>` : ''}
    `;

    // Enable/disable apply button
    const hasUnresolvedSimilar = data.results.some(r => r.status === 'similar');
    const hasDuplicates = data.summary.duplicate > 0;
    applyBtn.disabled = hasUnresolvedSimilar || hasDuplicates;

    // Show/hide warning indicator in header
    const warningIndicator = document.getElementById('validation-warning');
    if (warningIndicator) {
        warningIndicator.style.display = (hasUnresolvedSimilar || hasDuplicates) ? 'inline' : 'none';
    }
}

function acceptSuggestion(index) {
    // Update the textarea with the suggested name
    const textarea = document.getElementById('players-textarea');
    const lines = textarea.value.split('\n');
    const result = validationResults[index];

    // Find the line index for this result
    let nonEmptyIndex = 0;
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].trim()) {
            if (nonEmptyIndex === index) {
                lines[i] = result.suggestion;
                break;
            }
            nonEmptyIndex++;
        }
    }

    textarea.value = lines.join('\n');

    // Re-validate
    validatePlayers();
}

function rejectSuggestion(index) {
    // Mark as confirmed new player
    validationResults[index].status = 'new';
    validationResults[index].confirmed_new = true;

    // Re-render without re-fetching
    const data = {
        results: validationResults,
        summary: {
            exact: validationResults.filter(r => r.status === 'exact').length,
            similar: validationResults.filter(r => r.status === 'similar').length,
            new: validationResults.filter(r => r.status === 'new').length,
            duplicate: validationResults.filter(r => r.status === 'duplicate').length
        }
    };
    displayValidationResults(data);
}

async function applyPlayerChanges() {
    // Players validated, now save and reload
    saveTournament();
}

// Pairings
function selectPlayer(element) {
    const playerId = element.dataset.playerId;

    if (selectedSlot) {
        // Second click - swap
        if (selectedSlot !== element) {
            swapPlayers(selectedSlot, element);
        }
        selectedSlot.classList.remove('selected');
        selectedSlot = null;
    } else {
        // First click - select
        selectedSlot = element;
        element.classList.add('selected');
    }
}

function swapPlayers(slot1, slot2) {
    const id1 = slot1.dataset.playerId;
    const id2 = slot2.dataset.playerId;
    const name1 = slot1.textContent;
    const name2 = slot2.textContent;

    slot1.dataset.playerId = id2;
    slot1.textContent = name2;
    slot2.dataset.playerId = id1;
    slot2.textContent = name1;

    // Handle empty slot styling
    slot1.classList.toggle('empty', !id2 || id2 === 'null' || id2 === '');
    slot2.classList.toggle('empty', !id1 || id1 === 'null' || id1 === '');

    pairingsModified = true;
}

async function regeneratePairings() {
    if (!confirm('Luo uudet parit algoritmilla? Nykyiset parit korvataan.')) {
        return;
    }

    try {
        const response = await fetch(`/admin/tournaments/${tournamentId}/preview-round1`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });

        if (response.ok) {
            location.reload();
        } else {
            const error = await response.json();
            alert('Virhe: ' + (error.error || 'Tuntematon virhe'));
        }
    } catch (error) {
        console.error('Regenerate error:', error);
        alert('Virhe parien luomisessa');
    }
}

// Save
function saveTournament() {
    const form = document.getElementById('save-form');

    // Tournament name
    document.getElementById('form-tournament-name').value =
        document.getElementById('tournament-name').value;

    // Players
    const playersText = document.getElementById('players-textarea').value;
    document.getElementById('form-players').value = playersText;

    // Calculate and update num_courts from player count
    const lines = playersText.split('\n').filter(l => l.trim());
    if (lines.length >= 4 && lines.length % 4 === 0) {
        document.getElementById('form-num-courts').value = lines.length / 4;
    }

    // Pairings
    if (pairingsModified) {
        const pairings = collectPairingsData();
        document.getElementById('form-pairings').value = JSON.stringify(pairings);
    }

    form.submit();
}

function collectPairingsData() {
    const courts = document.querySelectorAll('.court-card');
    const pairings = [];

    courts.forEach(court => {
        const courtNumber = parseInt(court.dataset.court);
        const slots = court.querySelectorAll('.player-slot');

        pairings.push({
            court: courtNumber,
            team1: [
                parseInt(slots[0].dataset.playerId) || null,
                parseInt(slots[1].dataset.playerId) || null
            ],
            team2: [
                parseInt(slots[2].dataset.playerId) || null,
                parseInt(slots[3].dataset.playerId) || null
            ]
        });
    });

    return pairings;
}

// Start Tournament
async function startTournament() {
    // Validate: no empty slots, no unassigned players
    const emptySlots = document.querySelectorAll('.player-slot.empty');
    const unassigned = document.querySelectorAll('.unassigned-player');

    if (emptySlots.length > 0) {
        alert('Täytä kaikki tyhjät paikat ennen aloittamista.');
        return;
    }

    if (unassigned.length > 0) {
        alert('Sijoita kaikki pelaajat ennen aloittamista.');
        return;
    }

    if (confirm('Aloita turnaus? Pelaajia ja pareja ei voi enää muokata.')) {
        // Save first, then start
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/start-round/${tournamentId}`;
        document.body.appendChild(form);
        form.submit();
    }
}

// History toggle (expand/collapse)
function toggleHistory() {
    const content = document.getElementById('history-content');
    const icon = document.getElementById('history-toggle-icon');
    if (content && icon) {
        const isHidden = content.style.display === 'none';
        content.style.display = isHidden ? 'block' : 'none';
        icon.textContent = isHidden ? '▼' : '▶';
    }
}

// Player search in pairings
function searchPlayers(query) {
    const slots = document.querySelectorAll('.player-slot, .unassigned-player');
    const normalizedQuery = query.toLowerCase().trim();

    slots.forEach(slot => {
        slot.classList.remove('search-highlight');

        if (normalizedQuery && slot.textContent.toLowerCase().includes(normalizedQuery)) {
            slot.classList.add('search-highlight');
        }
    });
}

function clearSearch() {
    const searchInput = document.getElementById('player-search');
    if (searchInput) {
        searchInput.value = '';
        searchPlayers('');
    }
}

// Initialize empty slots
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.player-slot').forEach(slot => {
        const text = slot.textContent.trim();
        if (text === '[TYHJÄ]' || !slot.dataset.playerId || slot.dataset.playerId === 'None' || slot.dataset.playerId === '') {
            slot.classList.add('empty');
        }
    });
});
