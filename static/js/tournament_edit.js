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
        // Get CSRF token from the form
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;

        const response = await fetch('/admin/validate-players', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
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
                        <span>→ ${result.suggestion}?</span>
                        <span class="suggestion-links">
                            <button class="btn-link accept-suggestion" data-index="${index}">Kyllä</button>
                            <button class="btn-link reject-suggestion" data-index="${index}">Ei, uusi pelaaja</button>
                        </span>
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

    // Add event listeners to dynamically created buttons
    container.querySelectorAll('.accept-suggestion').forEach(btn => {
        btn.addEventListener('click', function() {
            acceptSuggestion(parseInt(this.dataset.index));
        });
    });
    container.querySelectorAll('.reject-suggestion').forEach(btn => {
        btn.addEventListener('click', function() {
            rejectSuggestion(parseInt(this.dataset.index));
        });
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
    const name1 = slot1.textContent.trim();
    const name2 = slot2.textContent.trim();

    const isSlot1Unassigned = slot1.classList.contains('unassigned-player');
    const isSlot2Unassigned = slot2.classList.contains('unassigned-player');
    const isSlot1Empty = !id1 || id1 === 'null' || id1 === '';
    const isSlot2Empty = !id2 || id2 === 'null' || id2 === '';

    // Case: Moving unassigned player to empty court slot
    if (isSlot1Unassigned && isSlot2Empty) {
        // Fill the court slot with the player
        slot2.dataset.playerId = id1;
        slot2.textContent = name1;
        slot2.classList.remove('empty');
        // Remove from unassigned pool
        slot1.remove();
        updateUnassignedPoolVisibility();
    } else if (isSlot2Unassigned && isSlot1Empty) {
        // Fill the court slot with the player
        slot1.dataset.playerId = id2;
        slot1.textContent = name2;
        slot1.classList.remove('empty');
        // Remove from unassigned pool
        slot2.remove();
        updateUnassignedPoolVisibility();
    } else if (isSlot1Unassigned || isSlot2Unassigned) {
        // Swapping unassigned player with assigned player - do a full swap
        slot1.dataset.playerId = id2;
        slot1.textContent = name2;
        slot2.dataset.playerId = id1;
        slot2.textContent = name1;
        slot1.classList.toggle('empty', isSlot2Empty);
        slot2.classList.toggle('empty', isSlot1Empty);
    } else {
        // Normal swap between two court slots
        slot1.dataset.playerId = id2;
        slot1.textContent = name2;
        slot2.dataset.playerId = id1;
        slot2.textContent = name1;
        slot1.classList.toggle('empty', isSlot2Empty);
        slot2.classList.toggle('empty', isSlot1Empty);
    }

    pairingsModified = true;
}

function updateUnassignedPoolVisibility() {
    const pool = document.getElementById('unassigned-pool');
    const unassignedPlayers = document.querySelectorAll('.unassigned-player');
    const countSpan = document.getElementById('unassigned-count');
    if (countSpan) {
        countSpan.textContent = unassignedPlayers.length;
    }
    if (pool) {
        pool.style.display = unassignedPlayers.length > 0 ? 'block' : 'none';
    }
}

async function regeneratePairings() {
    if (!confirm('Luo uudet parit algoritmilla? Nykyiset parit korvataan.')) {
        return;
    }

    try {
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;

        const response = await fetch(`/admin/tournaments/${tournamentId}/preview-round1`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
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

// Copy pairings to clipboard in text format
function copyPairingsToClipboard() {
    const courts = document.querySelectorAll('.court-card');
    const lines = [];

    courts.forEach(court => {
        const courtNumber = court.dataset.court;
        const team1Slots = court.querySelectorAll('.team1 .player-slot');
        const team2Slots = court.querySelectorAll('.team2 .player-slot');

        // Get player names (excluding seed badges)
        const getPlayerName = (slot) => {
            // Clone the slot to avoid modifying the original
            const clone = slot.cloneNode(true);
            // Remove seed badges
            const badges = clone.querySelectorAll('.seed-badge');
            badges.forEach(b => b.remove());
            // Clean up whitespace (tabs, newlines, multiple spaces)
            return clone.textContent.replace(/\s+/g, ' ').trim();
        };

        const team1Player1 = getPlayerName(team1Slots[0]);
        const team1Player2 = getPlayerName(team1Slots[1]);
        const team2Player1 = getPlayerName(team2Slots[0]);
        const team2Player2 = getPlayerName(team2Slots[1]);

        // Skip if any slot is empty
        if (team1Player1 === '[TYHJÄ]' || team1Player2 === '[TYHJÄ]' ||
            team2Player1 === '[TYHJÄ]' || team2Player2 === '[TYHJÄ]') {
            return;
        }

        const line = `Kenttä ${courtNumber}: ${team1Player1} & ${team1Player2} vs ${team2Player1} & ${team2Player2}`;
        lines.push(line);
    });

    if (lines.length === 0) {
        alert('Ei kopioitavia pareja. Luo ensin parit.');
        return;
    }

    const text = lines.join('\n');

    navigator.clipboard.writeText(text).then(() => {
        // Visual feedback
        const btn = document.getElementById('copy-pairings-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Kopioitu!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
        alert('Kopiointi epäonnistui. Kopioi manuaalisesti:\n\n' + text);
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize empty slots
    document.querySelectorAll('.player-slot').forEach(slot => {
        const text = slot.textContent.trim();
        if (text === '[TYHJÄ]' || !slot.dataset.playerId || slot.dataset.playerId === 'None' || slot.dataset.playerId === '') {
            slot.classList.add('empty');
        }
    });

    // Event listeners for buttons (CSP-compliant, no inline handlers)
    const editPlayersBtn = document.getElementById('edit-players-btn');
    if (editPlayersBtn) editPlayersBtn.addEventListener('click', showPlayerEditor);

    // Player editor buttons
    document.querySelectorAll('.editor-actions .btn-primary').forEach(btn => {
        if (btn.textContent.includes('Tarkista')) btn.addEventListener('click', validatePlayers);
    });
    document.querySelectorAll('.editor-actions .btn-secondary').forEach(btn => {
        if (btn.textContent.includes('Peruuta')) btn.addEventListener('click', cancelPlayerEdit);
    });

    // Validation actions
    document.querySelectorAll('.validation-actions .btn-secondary').forEach(btn => {
        if (btn.textContent.includes('Takaisin')) btn.addEventListener('click', backToEditor);
    });
    const applyBtn = document.getElementById('apply-btn');
    if (applyBtn) applyBtn.addEventListener('click', applyPlayerChanges);

    // Pairings panel - regenerate button
    const regenerateBtn = document.getElementById('regenerate-btn');
    if (regenerateBtn) regenerateBtn.addEventListener('click', regeneratePairings);

    // Copy pairings button
    const copyBtn = document.getElementById('copy-pairings-btn');
    if (copyBtn) copyBtn.addEventListener('click', copyPairingsToClipboard);

    // Search
    const searchInput = document.getElementById('player-search');
    if (searchInput) searchInput.addEventListener('input', function() { searchPlayers(this.value); });

    const searchClear = document.querySelector('.search-clear');
    if (searchClear) searchClear.addEventListener('click', clearSearch);

    // Player slots and unassigned players - click to select/swap
    document.querySelectorAll('.player-slot').forEach(slot => {
        slot.addEventListener('click', function() { selectPlayer(this); });
    });
    document.querySelectorAll('.unassigned-player').forEach(player => {
        player.addEventListener('click', function() { selectPlayer(this); });
    });

    // History toggle
    const historyHeader = document.querySelector('.history-header');
    if (historyHeader) historyHeader.addEventListener('click', toggleHistory);

    // Action bar buttons
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) saveBtn.addEventListener('click', saveTournament);

    const startBtn = document.getElementById('start-btn');
    if (startBtn) startBtn.addEventListener('click', startTournament);
});
