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
