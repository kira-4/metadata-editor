// API base URL
const API_BASE = '/api';

// Genre presets
const GENRE_PRESETS = [
    'مواليد وأفراح',
    'لطميات',
    'شعر',
    'قرآن'
];

// State
let pendingItems = [];
let selectedGenres = {}; // itemId -> genre
let customGenreVisible = {}; // itemId -> boolean

// Initialize app
async function init() {
    await loadPendingItems();
    setupSSE();
}

// Load pending items from API
async function loadPendingItems() {
    try {
        const response = await fetch(`${API_BASE}/pending`);
        if (!response.ok) throw new Error('Failed to load items');
        
        pendingItems = await response.json();
        renderItems();
    } catch (error) {
        console.error('Error loading pending items:', error);
    }
}

// Render all items
function renderItems() {
    const container = document.getElementById('pendingItems');
    const emptyState = document.getElementById('emptyState');
    const itemCount = document.getElementById('itemCount');
    
    if (pendingItems.length === 0) {
        container.innerHTML = '';
        emptyState.classList.add('show');
        itemCount.textContent = '0 ملف';
        return;
    }
    
    emptyState.classList.remove('show');
    itemCount.textContent = `${pendingItems.length} ملف`;
    
    container.innerHTML = pendingItems.map(item => createItemCard(item)).join('');
    
    // Attach event listeners
    pendingItems.forEach(item => {
        attachItemListeners(item.id);
    });
}

// Create item card HTML
function createItemCard(item) {
    const hasError = item.status === 'error';
    const artworkUrl = item.artwork_url || null;
    
    return `
        <div class="item-card" data-id="${item.id}">
            ${hasError ? '<div class="error-badge">⚠️ خطأ</div>' : ''}
            
            <div class="item-header">
                ${artworkUrl 
                    ? `<img src="${artworkUrl}" alt="Artwork" class="artwork">`
                    : '<div class="artwork-placeholder">🎵</div>'
                }
                
                <div class="item-info">
                    <div class="field-group">
                        <label class="field-label">العنوان</label>
                        <input 
                            type="text" 
                            class="field-input title-input" 
                            value="${item.current_title || item.inferred_title || ''}"
                            ${hasError ? 'disabled' : ''}
                            data-id="${item.id}"
                        >
                    </div>
                    
                    <div class="field-group">
                        <label class="field-label">الفنان</label>
                        <input 
                            type="text" 
                            class="field-input artist-input" 
                            value="${item.current_artist || item.inferred_artist || ''}"
                            ${hasError ? 'disabled' : ''}
                            data-id="${item.id}"
                        >
                    </div>
                    
                    <div class="source-text">
                        المصدر: ${item.video_title} • ${item.channel}
                    </div>
                </div>
            </div>
            
            ${hasError 
                ? `<div class="error-message">${item.error_message}</div>`
                : `
                    <div class="genre-section">
                        <label class="genre-label">اختر النوع الموسيقي</label>
                        <div class="genre-buttons">
                            ${GENRE_PRESETS.map(genre => `
                                <button class="genre-btn" data-id="${item.id}" data-genre="${genre}">
                                    ${genre}
                                </button>
                            `).join('')}
                            <button class="genre-btn" data-id="${item.id}" data-genre="custom">
                                أخرى…
                            </button>
                        </div>
                        <div class="custom-genre-wrapper">
                            <input 
                                type="text" 
                                class="custom-genre-input" 
                                placeholder="أدخل النوع الموسيقي"
                                data-id="${item.id}"
                            >
                        </div>
                    </div>
                    
                    <button class="confirm-btn" data-id="${item.id}" disabled>
                        ✓ تأكيد ونقل إلى المكتبة
                    </button>
                `
            }
        </div>
    `;
}

// Attach event listeners for an item
function attachItemListeners(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    
    // Title/Artist input listeners
    const titleInput = card.querySelector('.title-input');
    const artistInput = card.querySelector('.artist-input');
    
    if (titleInput) {
        titleInput.addEventListener('blur', () => updateField(itemId, 'title', titleInput.value));
    }
    
    if (artistInput) {
        artistInput.addEventListener('blur', () => updateField(itemId, 'artist', artistInput.value));
    }
    
    // Genre button listeners
    const genreButtons = card.querySelectorAll('.genre-btn');
    genreButtons.forEach(btn => {
        btn.addEventListener('click', () => handleGenreClick(itemId, btn.dataset.genre));
    });
    
    // Custom genre input
    const customInput = card.querySelector('.custom-genre-input');
    if (customInput) {
        customInput.addEventListener('input', () => {
            selectedGenres[itemId] = customInput.value;
            updateConfirmButton(itemId);
        });
    }
    
    // Confirm button
    const confirmBtn = card.querySelector('.confirm-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => confirmItem(itemId));
    }
}

// Handle genre button click
function handleGenreClick(itemId, genre) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    
    // Update button states
    const buttons = card.querySelectorAll('.genre-btn');
    buttons.forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.genre === genre);
    });
    
    // Handle custom genre
    const customInput = card.querySelector('.custom-genre-input');
    if (genre === 'custom') {
        customInput.classList.add('show');
        customGenreVisible[itemId] = true;
        selectedGenres[itemId] = customInput.value || '';
    } else {
        customInput.classList.remove('show');
        customGenreVisible[itemId] = false;
        selectedGenres[itemId] = genre;
    }
    
    updateField(itemId, 'genre', selectedGenres[itemId]);
    updateConfirmButton(itemId);
}

// Update confirm button state
function updateConfirmButton(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    
    const confirmBtn = card.querySelector('.confirm-btn');
    const titleInput = card.querySelector('.title-input');
    const artistInput = card.querySelector('.artist-input');
    
    if (!confirmBtn || !titleInput || !artistInput) return;
    
    const hasGenre = selectedGenres[itemId] && selectedGenres[itemId].trim().length > 0;
    const hasTitle = titleInput.value.trim().length > 0;
    const hasArtist = artistInput.value.trim().length > 0;
    
    confirmBtn.disabled = !(hasGenre && hasTitle && hasArtist);
}

// Update field via API
async function updateField(itemId, field, value) {
    try {
        const payload = {};
        payload[field] = value;
        
        const response = await fetch(`${API_BASE}/pending/${itemId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Failed to update field');
        
        // Update local state
        const item = pendingItems.find(i => i.id === itemId);
        if (item) {
            if (field === 'title') item.current_title = value;
            if (field === 'artist') item.current_artist = value;
            if (field === 'genre') item.genre = value;
        }
        
        updateConfirmButton(itemId);
        
    } catch (error) {
        console.error(`Error updating ${field}:`, error);
    }
}

// Confirm item
async function confirmItem(itemId) {
    const confirmBtn = document.querySelector(`.confirm-btn[data-id="${itemId}"]`);
    if (!confirmBtn) return;
    
    // Disable button
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'جاري النقل...';
    
    try {
        const response = await fetch(`${API_BASE}/pending/${itemId}/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to confirm');
        }
        
        // Remove item from list
        pendingItems = pendingItems.filter(i => i.id !== itemId);
        delete selectedGenres[itemId];
        delete customGenreVisible[itemId];
        
        // Re-render
        renderItems();
        
    } catch (error) {
        console.error('Error confirming item:', error);
        confirmBtn.disabled = false;
        confirmBtn.textContent = '✗ فشل - حاول مرة أخرى';
        confirmBtn.style.background = 'var(--error)';
    }
}

// Setup Server-Sent Events
function setupSSE() {
    const eventSource = new EventSource(`${API_BASE}/events`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'item_confirmed') {
            // Item was confirmed, refresh list
            loadPendingItems();
        } else if (data.type === 'new_item') {
            // New item added, refresh list
            loadPendingItems();
        }
    };
    
    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        // Reconnect automatically handled by browser
    };
}

// Start app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
