/**
 * Round 1 Court Assignment Editor
 *
 * Manages state and interaction for manually adjusting Round 1 court assignments
 * in the Admin Dashboard.
 */

// Global state per tournament (keyed by tournament ID)
const round1State = {};

/**
 * Initialize state for a tournament
 */
function initRound1State(tournamentId) {
    if (!round1State[tournamentId]) {
        round1State[tournamentId] = {
            pairingsData: [],
            originalPairingsData: [],
            playersData: {},
            selectedPlayer: null,
            modified: false
        };
    }
    return round1State[tournamentId];
}

/**
 * Get state for a tournament
 */
function getRound1State(tournamentId) {
    return round1State[tournamentId] || initRound1State(tournamentId);
}

/**
 * Update state modified flag and button visibility
 */
function updateModifiedState(tournamentId, isModified) {
    const state = getRound1State(tournamentId);
    state.modified = isModified;

    // Show/hide save button based on modified state
    const saveBtn = document.getElementById(`save-round1-btn-${tournamentId}`);
    if (saveBtn) {
        saveBtn.style.display = isModified ? 'inline-block' : 'none';
    }
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
