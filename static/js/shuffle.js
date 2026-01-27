/**
 * TeamShuffler - Handles drag-and-drop team shuffling on mobile and desktop
 */
class TeamShuffler {
    constructor() {
        this.playerSlots = document.querySelectorAll('.player-slot');
        this.draggedElement = null;
        this.floatingClone = null;
        this.touchOffsetX = 0;
        this.touchOffsetY = 0;
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
        this.highlightDropTargets(true);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', this.draggedElement.innerHTML);
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const targetSlot = e.target.closest('.player-slot');
        // Update hover state for desktop
        this.playerSlots.forEach(slot => {
            if (slot !== this.draggedElement) {
                slot.classList.toggle('drop-target-hover', slot === targetSlot);
            }
        });
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
        this.highlightDropTargets(false);
    }

    // Mobile Touch Handlers
    handleTouchStart(e) {
        this.draggedElement = e.target.closest('.player-slot');
        this.draggedElement.classList.add('dragging');
        this.highlightDropTargets(true);

        // Create floating clone
        const touch = e.touches[0];
        const rect = this.draggedElement.getBoundingClientRect();
        this.touchOffsetX = touch.clientX - rect.left;
        this.touchOffsetY = touch.clientY - rect.top;

        this.floatingClone = this.draggedElement.cloneNode(true);
        this.floatingClone.classList.remove('dragging');
        this.floatingClone.classList.add('floating-clone');
        this.floatingClone.style.width = rect.width + 'px';
        this.floatingClone.style.left = (touch.clientX - this.touchOffsetX) + 'px';
        this.floatingClone.style.top = (touch.clientY - this.touchOffsetY) + 'px';
        document.body.appendChild(this.floatingClone);

        e.preventDefault();
    }

    handleTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];

        // Move floating clone
        if (this.floatingClone) {
            this.floatingClone.style.left = (touch.clientX - this.touchOffsetX) + 'px';
            this.floatingClone.style.top = (touch.clientY - this.touchOffsetY) + 'px';
        }

        // Update drop target highlight based on finger position
        // Temporarily hide clone to find element underneath
        if (this.floatingClone) {
            this.floatingClone.style.display = 'none';
        }
        const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
        if (this.floatingClone) {
            this.floatingClone.style.display = '';
        }
        const targetSlot = targetElement?.closest('.player-slot');

        this.playerSlots.forEach(slot => {
            if (slot !== this.draggedElement) {
                slot.classList.toggle('drop-target-hover', slot === targetSlot);
            }
        });
    }

    handleTouchEnd(e) {
        const touch = e.changedTouches[0];

        // Hide clone to find element underneath
        if (this.floatingClone) {
            this.floatingClone.style.display = 'none';
        }
        const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
        const targetSlot = targetElement?.closest('.player-slot');

        if (targetSlot && this.draggedElement && this.draggedElement !== targetSlot) {
            this.swapPlayers(this.draggedElement, targetSlot);
        }

        // Clean up
        if (this.floatingClone) {
            this.floatingClone.remove();
            this.floatingClone = null;
        }
        if (this.draggedElement) {
            this.draggedElement.classList.remove('dragging');
            this.draggedElement = null;
        }
        this.highlightDropTargets(false);
    }

    // Highlight/unhighlight potential drop targets
    highlightDropTargets(show) {
        this.playerSlots.forEach(slot => {
            if (slot !== this.draggedElement) {
                slot.classList.toggle('drop-target', show);
            }
            slot.classList.remove('drop-target-hover');
        });
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

async function confirmAndStartMatch() {
    const config = teamShuffler.getCurrentConfiguration();

    // Validate 4 unique players
    const playerIds = Object.values(config);
    const uniquePlayers = new Set(playerIds);

    if (uniquePlayers.size !== 4) {
        alert('Virhe: Kaikki 4 pelaajaa täytyy olla eri henkilöitä.');
        return;
    }

    // Check network
    if (!navigator.onLine) {
        alert('Ei verkkoyhteyttä. Tarkista yhteys ja yritä uudelleen.');
        return;
    }

    // Disable button to prevent double-submit
    const btn = event.target;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Tallennetaan...';

    try {
        // Create form data
        const formData = new FormData();
        Object.entries(config).forEach(([key, value]) => {
            formData.append(key, value);
        });
        // Add CSRF token
        if (typeof CSRF_TOKEN !== 'undefined') {
            formData.append('csrf_token', CSRF_TOKEN);
        }

        const response = await fetch(window.location.pathname, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            // Success - follow redirect
            window.location.href = response.url;
        } else {
            // Server error
            alert('Palvelinvirhe. Yritä uudelleen hetken kuluttua.');
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (error) {
        // Network error
        if (!navigator.onLine) {
            alert('Verkkoyhteys katkesi. Tarkista yhteys ja yritä uudelleen.');
        } else {
            alert('Yhteysvirhe. Tarkista verkko ja yritä uudelleen.');
        }
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

function resetToOriginal() {
    if (confirm('Palauta alkuperäiset joukkueet?')) {
        teamShuffler.resetToOriginal();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    teamShuffler = new TeamShuffler();
});
