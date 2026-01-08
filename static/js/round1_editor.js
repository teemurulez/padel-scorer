/**
 * Round 1 Court Assignment Editor
 *
 * Manages state and interaction for manually adjusting Round 1 court assignments
 * in the Admin Dashboard.
 */

// Global state per tournament (keyed by tournament ID)
// Exposed on window for form submission handler
window.round1States = window.round1States || {};

/**
 * Initialize state for a tournament
 */
function initRound1State(tournamentId) {
    if (!window.round1States[tournamentId]) {
        window.round1States[tournamentId] = {
            pairingsData: [],
            originalPairingsData: [],
            playersData: {},
            selectedPlayer: null,
            modified: false
        };
    }
    return window.round1States[tournamentId];
}

/**
 * Get state for a tournament
 */
function getRound1State(tournamentId) {
    return window.round1States[tournamentId] || initRound1State(tournamentId);
}

/**
 * Update state modified flag
 */
function updateModifiedState(tournamentId, isModified) {
    const state = getRound1State(tournamentId);
    state.modified = isModified;
    // Note: Pairings will be saved when the form's "Save Changes" button is clicked
}

/**
 * Deep clone pairings data
 */
function clonePairings(pairings) {
    return JSON.parse(JSON.stringify(pairings));
}

/**
 * Check if pairings have been modified
 */
function checkIfModified(tournamentId) {
    const state = getRound1State(tournamentId);
    const original = JSON.stringify(state.originalPairingsData);
    const current = JSON.stringify(state.pairingsData);
    return original !== current;
}

/**
 * Render courts display
 */
function renderCourts(tournamentId) {
    const state = getRound1State(tournamentId);
    const container = document.getElementById(`round1-courts-${tournamentId}`);

    if (!container) return;

    // Clear container
    container.innerHTML = '';

    // Show container
    container.style.display = 'block';

    // Render each court
    state.pairingsData.forEach(court => {
        const courtCard = createCourtCard(tournamentId, court);
        container.appendChild(courtCard);
    });

    // Show reset button
    const resetBtn = document.getElementById(`reset-round1-btn-${tournamentId}`);
    if (resetBtn) {
        resetBtn.style.display = 'inline-block';
    }
}

/**
 * Create court card HTML element
 */
function createCourtCard(tournamentId, court) {
    const state = getRound1State(tournamentId);
    const card = document.createElement('div');
    card.className = 'court-card';

    const header = document.createElement('div');
    header.className = 'court-header';
    header.textContent = `Court ${court.court} (4 players)`;
    card.appendChild(header);

    const teamsContainer = document.createElement('div');
    teamsContainer.className = 'court-teams';

    // Team 1 column
    const team1Col = createTeamColumn(
        tournamentId,
        'Team 1',
        court.team1,
        court.court,
        'team1',
        state.playersData
    );
    teamsContainer.appendChild(team1Col);

    // Team 2 column
    const team2Col = createTeamColumn(
        tournamentId,
        'Team 2',
        court.team2,
        court.court,
        'team2',
        state.playersData
    );
    teamsContainer.appendChild(team2Col);

    card.appendChild(teamsContainer);

    return card;
}

/**
 * Create team column with player boxes
 */
function createTeamColumn(tournamentId, teamLabel, playerIds, courtNum, teamKey, playersData) {
    const col = document.createElement('div');
    col.className = 'team-column';

    const header = document.createElement('h5');
    header.textContent = teamLabel;
    col.appendChild(header);

    playerIds.forEach((playerId, position) => {
        const playerBox = createPlayerBox(
            tournamentId,
            playerId,
            courtNum,
            teamKey,
            position,
            playersData
        );
        col.appendChild(playerBox);
    });

    return col;
}

/**
 * Create player box element
 */
function createPlayerBox(tournamentId, playerId, courtNum, team, position, playersData) {
    const box = document.createElement('div');
    box.className = 'player-box';
    box.dataset.playerId = playerId;
    box.dataset.courtNum = courtNum;
    box.dataset.team = team;
    box.dataset.position = position;

    const player = playersData[playerId];
    if (player) {
        const name = document.createElement('div');
        name.className = 'player-name';
        name.textContent = `${player.first_name} ${player.last_name}`;
        box.appendChild(name);
    } else {
        box.textContent = `Player ${playerId}`;
    }

    // Click handler (will be implemented in next task)
    box.onclick = () => handlePlayerClick(tournamentId, playerId, courtNum, team, position);

    return box;
}

/**
 * Handle player box click (click-then-click swap)
 */
function handlePlayerClick(tournamentId, playerId, courtNum, team, position) {
    const state = getRound1State(tournamentId);

    if (!state.selectedPlayer) {
        // First click: Select player
        selectPlayer(tournamentId, playerId, courtNum, team, position);
    } else if (state.selectedPlayer.playerId === playerId) {
        // Clicked same player: Deselect
        deselectPlayer(tournamentId);
    } else {
        // Second click: Swap players
        swapPlayers(
            tournamentId,
            state.selectedPlayer,
            {playerId, courtNum, team, position}
        );
        deselectPlayer(tournamentId);
    }
}

/**
 * Select a player (first click)
 */
function selectPlayer(tournamentId, playerId, courtNum, team, position) {
    const state = getRound1State(tournamentId);

    state.selectedPlayer = {playerId, courtNum, team, position};

    // Add visual highlight
    const allBoxes = document.querySelectorAll(`#round1-courts-${tournamentId} .player-box`);
    allBoxes.forEach(box => {
        if (parseInt(box.dataset.playerId) === playerId) {
            box.classList.add('selected');
        }
    });
}

/**
 * Deselect player
 */
function deselectPlayer(tournamentId) {
    const state = getRound1State(tournamentId);
    state.selectedPlayer = null;

    // Remove all highlights
    const allBoxes = document.querySelectorAll(`#round1-courts-${tournamentId} .player-box`);
    allBoxes.forEach(box => box.classList.remove('selected'));
}

/**
 * Swap two players
 */
function swapPlayers(tournamentId, player1, player2) {
    const state = getRound1State(tournamentId);

    // Find courts in pairings data
    const p1Court = state.pairingsData.find(c => c.court === player1.courtNum);
    const p2Court = state.pairingsData.find(c => c.court === player2.courtNum);

    if (!p1Court || !p2Court) {
        console.error('Court not found for swap');
        return;
    }

    // Swap player IDs in data structure
    const temp = p1Court[player1.team][player1.position];
    p1Court[player1.team][player1.position] = p2Court[player2.team][player2.position];
    p2Court[player2.team][player2.position] = temp;

    // Add swap animation class
    const allBoxes = document.querySelectorAll(`#round1-courts-${tournamentId} .player-box`);
    allBoxes.forEach(box => {
        const boxPlayerId = parseInt(box.dataset.playerId);
        if (boxPlayerId === player1.playerId || boxPlayerId === player2.playerId) {
            box.classList.add('swapping');
            setTimeout(() => box.classList.remove('swapping'), 500);
        }
    });

    // Re-render courts after animation
    setTimeout(() => {
        renderCourts(tournamentId);
        updateModifiedState(tournamentId, checkIfModified(tournamentId));
    }, 500);
}

/**
 * Preview Round 1 - fetch seeded pairings from backend
 * @param {number} tournamentId - The tournament ID
 * @param {boolean} force - If true, force regeneration (for Reset button)
 */
async function previewRound1(tournamentId, force = false) {
    const state = initRound1State(tournamentId);

    // Disable button during request
    const previewBtn = document.getElementById(`preview-round1-btn-${tournamentId}`);
    if (previewBtn) {
        previewBtn.disabled = true;
        previewBtn.textContent = 'Loading...';
    }

    try {
        const response = await fetch(`/admin/tournaments/${tournamentId}/preview-round1`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ force: force })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to preview Round 1');
        }

        const data = await response.json();

        // Update state
        state.pairingsData = data.pairings;
        state.originalPairingsData = clonePairings(data.pairings);
        state.playersData = data.players;
        state.modified = false;

        // Render courts
        renderCourts(tournamentId);

        // Show success message
        const message = force ? 'Round 1 pairings reset to algorithm-generated!' : 'Round 1 preview loaded!';
        showSuccessMessage(tournamentId, message);

    } catch (error) {
        console.error('Preview Round 1 error:', error);
        showErrorMessage(tournamentId, error.message);
    } finally {
        // Re-enable button
        if (previewBtn) {
            previewBtn.disabled = false;
            previewBtn.textContent = 'Preview Round 1';
        }
    }
}

/**
 * Save custom Round 1 pairings
 */
async function saveRound1Pairings(tournamentId) {
    const state = getRound1State(tournamentId);

    if (!state.modified) {
        showErrorMessage(tournamentId, 'No changes to save');
        return;
    }

    // Disable button during request
    const saveBtn = document.getElementById(`save-round1-btn-${tournamentId}`);
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
    }

    try {
        const response = await fetch(`/admin/tournaments/${tournamentId}/save-round1-pairings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pairings: state.pairingsData
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.errors ? error.errors.join(', ') : 'Failed to save pairings');
        }

        // Update original to match current (no longer modified)
        state.originalPairingsData = clonePairings(state.pairingsData);
        updateModifiedState(tournamentId, false);

        showSuccessMessage(tournamentId, 'Round 1 pairings saved successfully!');

    } catch (error) {
        console.error('Save pairings error:', error);
        showErrorMessage(tournamentId, error.message);
    } finally {
        // Re-enable button
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Round 1 Pairings';
        }
    }
}

/**
 * Reset to algorithm-generated pairings
 */
async function resetRound1(tournamentId) {
    if (!confirm('Reset to algorithm-generated pairings? Your changes will be lost.')) {
        return;
    }

    // Force regeneration by passing force=true
    await previewRound1(tournamentId, true);
}

/**
 * Show success message
 */
function showSuccessMessage(tournamentId, message) {
    // Create flash-style message
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'flash success';
    messageDiv.textContent = message;
    flashContainer.appendChild(messageDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => messageDiv.remove(), 5000);
}

/**
 * Show error message
 */
function showErrorMessage(tournamentId, message) {
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'flash error';
    messageDiv.textContent = message;
    flashContainer.appendChild(messageDiv);

    setTimeout(() => messageDiv.remove(), 5000);
}

/**
 * Create flash message container if doesn't exist
 */
function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.querySelector('.admin-container').prepend(container);
    return container;
}
