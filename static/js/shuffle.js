/**
 * TeamShuffler - Handles drag-and-drop team shuffling on mobile and desktop
 */
class TeamShuffler {
    constructor() {
        this.playerSlots = document.querySelectorAll('.player-slot');
        this.draggedElement = null;
        this.originalConfiguration = this.saveConfiguration();
        this.initDragAndDrop();
    }

    initDragAndDrop() {
        this.playerSlots.forEach(slot => {
            // Desktop drag events
            slot.addEventListener('dragstart', (e) => this.handleDragStart(e));
            slot.addEventListener('dragover', (e) => this.handleDragOver(e));
            slot.addEventListener('drop', (e) => this.handleDrop(e));
            slot.addEventListener('dragend', (e) => this.handleDragEnd(e));

            // Mobile touch events
            slot.addEventListener('touchstart', (e) => this.handleTouchStart(e), {passive: false});
            slot.addEventListener('touchmove', (e) => this.handleTouchMove(e), {passive: false});
            slot.addEventListener('touchend', (e) => this.handleTouchEnd(e), {passive: false});
        });
    }

    // Desktop Drag Handlers
    handleDragStart(e) {
        this.draggedElement = e.target.closest('.player-slot');
        this.draggedElement.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', this.draggedElement.innerHTML);
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        return false;
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();

        const targetSlot = e.target.closest('.player-slot');

        if (targetSlot && this.draggedElement !== targetSlot) {
            this.swapPlayers(this.draggedElement, targetSlot);
        }

        return false;
    }

    handleDragEnd(e) {
        this.draggedElement.classList.remove('dragging');
        this.draggedElement = null;
    }

    // Mobile Touch Handlers
    handleTouchStart(e) {
        this.draggedElement = e.target.closest('.player-slot');
        this.draggedElement.classList.add('dragging');
        e.preventDefault();
    }

    handleTouchMove(e) {
        e.preventDefault();
        // Optional: show visual feedback of drag position
    }

    handleTouchEnd(e) {
        const touch = e.changedTouches[0];
        const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
        const targetSlot = targetElement?.closest('.player-slot');

        if (targetSlot && this.draggedElement && this.draggedElement !== targetSlot) {
            this.swapPlayers(this.draggedElement, targetSlot);
        }

        if (this.draggedElement) {
            this.draggedElement.classList.remove('dragging');
            this.draggedElement = null;
        }
    }

    // Core Swap Logic
    swapPlayers(slot1, slot2) {
        // Swap player IDs
        const temp_id = slot1.dataset.playerId;
        slot1.dataset.playerId = slot2.dataset.playerId;
        slot2.dataset.playerId = temp_id;

        // Swap player names
        const name1 = slot1.querySelector('.player-name').textContent;
        const name2 = slot2.querySelector('.player-name').textContent;
        slot1.querySelector('.player-name').textContent = name2;
        slot2.querySelector('.player-name').textContent = name1;

        // Visual feedback
        this.flashSwap([slot1, slot2]);
    }

    flashSwap(slots) {
        slots.forEach(slot => {
            slot.classList.add('swapped');
            setTimeout(() => slot.classList.remove('swapped'), 400);
        });
    }

    // Configuration Management
    saveConfiguration() {
        const config = [];
        this.playerSlots.forEach(slot => {
            config.push({
                playerId: slot.dataset.playerId,
                playerName: slot.querySelector('.player-name').textContent
            });
        });
        return config;
    }

    getCurrentConfiguration() {
        const team1Slots = document.querySelectorAll('.team-1 .player-slot');
        const team2Slots = document.querySelectorAll('.team-2 .player-slot');

        return {
            team1_player1: team1Slots[0].dataset.playerId,
            team1_player2: team1Slots[1].dataset.playerId,
            team2_player1: team2Slots[0].dataset.playerId,
            team2_player2: team2Slots[1].dataset.playerId
        };
    }

    resetToOriginal() {
        const slots = Array.from(this.playerSlots);
        this.originalConfiguration.forEach((config, index) => {
            slots[index].dataset.playerId = config.playerId;
            slots[index].querySelector('.player-name').textContent = config.playerName;
        });

        // Flash all slots
        this.flashSwap(slots);
    }
}

// Global Functions
let teamShuffler;

function confirmAndStartMatch() {
    const config = teamShuffler.getCurrentConfiguration();

    // Validate 4 unique players
    const playerIds = Object.values(config);
    const uniquePlayers = new Set(playerIds);

    if (uniquePlayers.size !== 4) {
        alert('Error: All 4 players must be unique. Please check your team configuration.');
        return;
    }

    // Disable button to prevent double-submit
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Starting...';

    // Create and submit form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.pathname;

    Object.entries(config).forEach(([key, value]) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = value;
        form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
}

function resetToOriginal() {
    if (confirm('Reset teams to original pairing?')) {
        teamShuffler.resetToOriginal();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    teamShuffler = new TeamShuffler();
});
