// API base URL
const API_BASE = '/api';

// Genre presets
const GENRE_PRESETS = [
    'مواليد وأفراح',
    'لطميات',
    'شعر',
    'قرآن',
    'أدعية'
];

// State
let pendingItems = [];
let selectedGenres = {}; // itemId -> genre
let customGenreVisible = {}; // itemId -> boolean
let sseConnection = null;
let pendingPollTimer = null;
const appLogs = [];
const MAX_LOG_ENTRIES = 800;

function timestampNow() {
    return new Date().toISOString();
}

function logEvent(level, message, context = null) {
    const entry = {time: timestampNow(), level, message, context};
    appLogs.push(entry);
    if (appLogs.length > MAX_LOG_ENTRIES) {
        appLogs.shift();
    }

    const consoleFn = level === 'error' ? console.error : (level === 'warn' ? console.warn : console.log);
    consoleFn(`[${entry.time}] ${message}`, context || '');
    renderLogPanel();
}

function renderLogPanel() {
    const output = document.getElementById('logOutput');
    if (!output) return;
    const lines = appLogs.map(entry => {
        const ctx = entry.context ? ` | ${JSON.stringify(entry.context, null, 0)}` : '';
        return `[${entry.time}] [${entry.level.toUpperCase()}] ${entry.message}${ctx}`;
    });
    output.textContent = lines.join('\n') || 'لا توجد سجلات بعد.';
    output.scrollTop = output.scrollHeight;
}

function downloadLogs() {
    const lines = appLogs.map(entry => {
        const ctx = entry.context ? ` | ${JSON.stringify(entry.context)}` : '';
        return `[${entry.time}] [${entry.level.toUpperCase()}] ${entry.message}${ctx}`;
    });
    const blob = new Blob([lines.join('\n')], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `muharrir-alaswat-logs-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

function showAlert(message, type = 'info', timeout = 5000) {
    const alertEl = document.getElementById('globalAlert');
    if (!alertEl) return;
    alertEl.textContent = message;
    alertEl.className = `global-alert ${type}`;
    alertEl.style.display = 'block';

    if (timeout > 0) {
        setTimeout(() => {
            if (alertEl.textContent === message) {
                alertEl.style.display = 'none';
            }
        }, timeout);
    }
}

async function parseApiError(response, fallbackMessage) {
    try {
        const body = await response.json();
        return body.detail || fallbackMessage;
    } catch {
        return fallbackMessage;
    }
}

function setupGlobalUI() {
    const refreshBtn = document.getElementById('refreshPendingBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadPendingItems({showLoading: true}));
    }

    const toggleLogsBtn = document.getElementById('toggleLogsBtn');
    const logPanel = document.getElementById('logPanel');
    if (toggleLogsBtn && logPanel) {
        toggleLogsBtn.addEventListener('click', () => {
            const visible = logPanel.style.display === 'block';
            logPanel.style.display = visible ? 'none' : 'block';
            toggleLogsBtn.textContent = visible ? 'إظهار السجلات' : 'إخفاء السجلات';
            if (!visible) {
                renderLogPanel();
            }
        });
    }

    const downloadLogsBtn = document.getElementById('downloadLogsBtn');
    if (downloadLogsBtn) {
        downloadLogsBtn.addEventListener('click', downloadLogs);
    }
}

// Initialize app
async function init() {
    setupGlobalUI();
    await loadPendingItems({showLoading: true});
    setupSSE();
    if (pendingPollTimer) {
        clearInterval(pendingPollTimer);
    }
    pendingPollTimer = setInterval(() => {
        loadPendingItems({silent: true});
    }, 15000);
}

// Load pending items from API
async function loadPendingItems(options = {}) {
    const {showLoading = false, silent = false} = options;
    try {
        const container = document.getElementById('pendingItems');
        if (showLoading && container) {
            container.innerHTML = '<div class="loading"><span class="spinning">🔄</span> جاري تحميل الملفات...</div>';
        }

        const response = await fetch(`${API_BASE}/pending`);
        if (!response.ok) {
            const detail = await parseApiError(response, 'فشل تحميل قائمة الانتظار');
            throw new Error(detail);
        }
        
        pendingItems = await response.json();
        pendingItems.forEach(item => {
            if (item.genre && item.genre.trim()) {
                selectedGenres[item.id] = item.genre.trim();
            }
        });

        renderItems();
        if (!silent) {
            logEvent('info', `تم تحميل قائمة الانتظار (${pendingItems.length}) عنصر`);
        }
    } catch (error) {
        logEvent('error', 'فشل تحميل قائمة الانتظار', {error: error.message});
        showAlert(`فشل تحميل قائمة الانتظار: ${error.message}`, 'error');
    }
}

// Render all items
function renderItems() {
    const container = document.getElementById('pendingItems');
    const emptyState = document.getElementById('emptyState');
    const itemCount = document.getElementById('itemCount');
    const badge = document.getElementById('pendingBadge');
    
    // Update Badge
    if (badge) {
        if (pendingItems.length > 0) {
            badge.textContent = pendingItems.length;
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }
    
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
        updateConfirmButton(item.id);
    });
}

// Create item card HTML
function createItemCard(item) {
    const hasError = item.status === 'error';
    const isManual = item.status === 'needs_manual';
    const artworkUrl = item.artwork_url || null;
    const currentGenre = (item.genre || '').trim();
    const isCustomGenre = currentGenre && !GENRE_PRESETS.includes(currentGenre);
    
    return `
        <div class="item-card" data-id="${item.id}">
            ${hasError ? `<div class="error-badge">⚠️ خطأ: ${item.error_message}</div>` : ''}
            ${isManual ? '<div class="warning-badge">⚠️ يحتاج مراجعة يدوية</div>' : ''}
            
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
                            data-id="${item.id}"
                            placeholder="العنوان (مطلوب)"
                        >
                    </div>
                    
                    <div class="field-group">
                        <label class="field-label">الفنان</label>
                        <input 
                            type="text" 
                            class="field-input artist-input" 
                            value="${item.current_artist || item.inferred_artist || ''}"
                            data-id="${item.id}"
                            placeholder="الفنان (مطلوب)"
                        >
                    </div>
                    
                    <div class="source-text">
                        المصدر: ${item.video_title} • ${item.channel}
                    </div>
                </div>
            </div>
            
            <div class="genre-section">
                <label class="genre-label">اختر النوع الموسيقي</label>
                <div class="genre-buttons">
                    ${GENRE_PRESETS.map(genre => `
                        <button class="genre-btn ${currentGenre === genre ? 'selected' : ''}" data-id="${item.id}" data-genre="${genre}">
                            ${genre}
                        </button>
                    `).join('')}
                    <button class="genre-btn ${isCustomGenre ? 'selected' : ''}" data-id="${item.id}" data-genre="custom">
                        أخرى…
                    </button>
                </div>
                <div class="custom-genre-wrapper">
                    <input 
                        type="text" 
                        class="custom-genre-input ${isCustomGenre ? 'show' : ''}" 
                        placeholder="أدخل النوع الموسيقي"
                        value="${isCustomGenre ? currentGenre : ''}"
                        data-id="${item.id}"
                    >
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="btn-secondary dry-run-btn" data-id="${item.id}">
                    معاينة (Dry Run)
                </button>
                <button class="confirm-btn" data-id="${item.id}" disabled>
                    ✓ تأكيد ونقل إلى المكتبة
                </button>
                <div class="item-status" id="itemStatus-${item.id}"></div>
                ${(hasError || isManual) ? `
                <button class="btn-secondary delete-btn" style="margin-top: 1rem; width: 100%; border-color: var(--error); color: var(--error);" onclick="deleteItem('${item.id}')">
                    حذف الملف
                </button>
                ` : ''}
            </div>
        </div>
    `;
}

// Attach event listeners for an item
function attachItemListeners(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    const item = pendingItems.find(p => p.id === itemId);
    
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
        let debounceTimer;
        
        // Input event: update local state and debounce backend update
        customInput.addEventListener('input', () => {
            const value = customInput.value.trim();
            selectedGenres[itemId] = value;
            updateConfirmButton(itemId);
            
            // Debounce: send to backend after 500ms of no typing
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                if (value.length > 0) {
                    updateField(itemId, 'genre', value);
                }
            }, 500);
        });
        
        // Blur event: immediately send to backend when field loses focus
        // This ensures genre is saved even if user clicks Confirm quickly
        customInput.addEventListener('blur', () => {
            clearTimeout(debounceTimer); // Cancel pending debounce
            const value = customInput.value.trim();
            if (value.length > 0) {
                updateField(itemId, 'genre', value);
            }
        });
    }
    
    // Confirm button
    const confirmBtn = card.querySelector('.confirm-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => confirmItem(itemId));
    }

    // Dry run button
    const dryRunBtn = card.querySelector('.dry-run-btn');
    if (dryRunBtn) {
        dryRunBtn.addEventListener('click', () => previewItem(itemId));
    }

    if (item && item.genre && item.genre.trim()) {
        selectedGenres[itemId] = item.genre.trim();
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
        selectedGenres[itemId] = customInput.value.trim() || '';
        // DON'T send to backend yet - wait for user to type
        // Only send if there's already a value in the input
        if (customInput.value.trim().length > 0) {
            updateField(itemId, 'genre', customInput.value.trim());
        }
    } else {
        customInput.classList.remove('show');
        customGenreVisible[itemId] = false;
        selectedGenres[itemId] = genre;
        // Preset genre - send immediately
        updateField(itemId, 'genre', genre);
    }
    
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
        payload[field] = typeof value === 'string' ? value.trim() : value;
        
        const response = await fetch(`${API_BASE}/pending/${itemId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const detail = await parseApiError(response, `فشل تحديث ${field}`);
            throw new Error(detail);
        }
        
        // Update local state
        const item = pendingItems.find(i => i.id === itemId);
        if (item) {
            if (field === 'title') item.current_title = payload[field];
            if (field === 'artist') item.current_artist = payload[field];
            if (field === 'genre') item.genre = payload[field];
        }
        
        updateConfirmButton(itemId);
        setItemStatus(itemId, 'تم حفظ التعديل', 'success');
        
    } catch (error) {
        logEvent('error', `فشل تحديث ${field}`, {itemId, error: error.message});
        showAlert(`فشل تحديث ${field}: ${error.message}`, 'error');
        setItemStatus(itemId, `فشل تحديث ${field}`, 'error');
    }
}

function setItemStatus(itemId, message, type = 'info') {
    const statusEl = document.getElementById(`itemStatus-${itemId}`);
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = `item-status ${type}`;
}

async function fetchDryRun(itemId) {
    const response = await fetch(`${API_BASE}/pending/${itemId}/dry-run`);
    if (!response.ok) {
        const detail = await parseApiError(response, 'فشل إنشاء المعاينة');
        throw new Error(detail);
    }
    return response.json();
}

function formatDryRunMessage(dryRun) {
    const missing = dryRun.missing_fields?.length ? dryRun.missing_fields.join(', ') : 'لا يوجد';
    const move = dryRun.move_preview || {};
    const meta = dryRun.metadata_preview || {};
    return [
        'معاينة العملية (Dry Run):',
        `- قابل للتأكيد: ${dryRun.can_confirm ? 'نعم' : 'لا'}`,
        `- الحقول الناقصة: ${missing}`,
        `- العنوان: ${meta.title || '-'}`,
        `- الفنان: ${meta.artist || '-'}`,
        `- الألبوم: ${meta.album || '-'}`,
        `- النوع: ${meta.genre || '-'}`,
        `- المسار النهائي: ${move.destination_path || '-'}`,
        `- صلاحية كتابة جذر Navidrome: ${move.navidrome_root_writable ? 'نعم' : 'لا'}`,
        `- صلاحية كتابة المجلد الهدف: ${move.destination_parent_writable ? 'نعم' : 'لا'}`
    ].join('\n');
}

async function previewItem(itemId) {
    const btn = document.querySelector(`.dry-run-btn[data-id="${itemId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'جاري إنشاء المعاينة...';
    }

    try {
        const dryRun = await fetchDryRun(itemId);
        const message = formatDryRunMessage(dryRun);
        logEvent('info', 'Dry-run preview generated', {itemId, dryRun});
        showAlert(dryRun.can_confirm ? 'تم إنشاء المعاينة بنجاح' : 'المعاينة تُظهر مشاكل يجب إصلاحها', dryRun.can_confirm ? 'success' : 'warn', 7000);
        window.alert(message);
        setItemStatus(itemId, dryRun.can_confirm ? 'المعاينة جاهزة للتأكيد' : 'المعاينة: هناك مشاكل', dryRun.can_confirm ? 'success' : 'warn');
    } catch (error) {
        logEvent('error', 'Dry-run preview failed', {itemId, error: error.message});
        showAlert(`فشل إنشاء المعاينة: ${error.message}`, 'error');
        setItemStatus(itemId, 'فشل إنشاء المعاينة', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'معاينة (Dry Run)';
        }
    }
}

// Confirm item
async function confirmItem(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const confirmBtn = document.querySelector(`.confirm-btn[data-id="${itemId}"]`);
    if (!card || !confirmBtn) return;
    
    const title = (card.querySelector('.title-input')?.value || '').trim();
    const artist = (card.querySelector('.artist-input')?.value || '').trim();
    const genre = (selectedGenres[itemId] || '').trim();

    if (!title || !artist || !genre) {
        showAlert('لا يمكن التأكيد: العنوان والفنان والنوع مطلوبة.', 'warn');
        setItemStatus(itemId, 'أكمل الحقول المطلوبة أولاً', 'warn');
        return;
    }
    
    // Disable button
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'جاري النقل...';
    setItemStatus(itemId, 'التحقق من المعاينة...', 'info');
    
    try {
        const dryRun = await fetchDryRun(itemId);
        if (!dryRun.can_confirm) {
            throw new Error(`المعاينة فشلت: ${dryRun.missing_fields.join(', ') || 'صلاحيات/مسار غير صالح'}`);
        }

        setItemStatus(itemId, 'جاري كتابة البيانات الوصفية...', 'info');
        const response = await fetch(`${API_BASE}/pending/${itemId}/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const detail = await parseApiError(response, 'فشل التأكيد');
            throw new Error(detail);
        }
        
        // Remove item from list
        pendingItems = pendingItems.filter(i => i.id !== itemId);
        delete selectedGenres[itemId];
        delete customGenreVisible[itemId];
        
        // Re-render
        renderItems();
        showAlert('تم حفظ البيانات ونقل الملف بنجاح.', 'success');
        logEvent('info', 'Item confirmed and moved', {itemId});
        
    } catch (error) {
        logEvent('error', 'Error confirming item', {itemId, error: error.message});
        showAlert(`فشل التأكيد: ${error.message}`, 'error');
        confirmBtn.disabled = false;
        confirmBtn.textContent = '✗ فشل - حاول مرة أخرى';
        confirmBtn.style.background = 'var(--error)';
        setItemStatus(itemId, `فشل التأكيد: ${error.message}`, 'error');
    }
}

// Delete item
async function deleteItem(itemId) {
    if (!confirm('هل أنت متأكد من حذف هذا الملف نهائياً؟')) return;
    
    const deleteBtn = document.querySelector(`.item-card[data-id="${itemId}"] .delete-btn`);
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = 'جاري الحذف...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/pending/${itemId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const detail = await parseApiError(response, 'فشل حذف الملف');
            throw new Error(detail);
        }
        
        // Remove item from list (optimistic update)
        pendingItems = pendingItems.filter(i => i.id !== itemId);
        renderItems();
        showAlert('تم حذف الملف من قائمة الانتظار.', 'success');
        logEvent('info', 'Pending item deleted', {itemId});
        
    } catch (error) {
        logEvent('error', 'Delete item failed', {itemId, error: error.message});
        showAlert(`فشل حذف الملف: ${error.message}`, 'error');
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'فشل الحذف - حاول مرة أخرى';
        }
    }
}

// Setup Server-Sent Events
function setupSSE() {
    if (sseConnection) {
        sseConnection.close();
    }
    const eventSource = new EventSource(`${API_BASE}/events`);
    sseConnection = eventSource;
    
    eventSource.onopen = () => {
        logEvent('info', 'SSE connected');
    };
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        logEvent('info', `SSE event: ${data.type}`, data);
        
        if (['item_confirmed', 'new_item', 'item_deleted', 'item_updated', 'item_error'].includes(data.type)) {
            loadPendingItems({silent: true});
        }
    };
    
    eventSource.onerror = (error) => {
        logEvent('warn', 'SSE error (browser will retry automatically)', {error: String(error)});
        // Reconnect automatically handled by browser
    };
}

//=============================================================================
// Library Editor Features
//=============================================================================

// Library State
const libraryState = {
    currentView: 'artists',
    currentSort: 'name-asc',
    searchQuery: '',
    currentPage: 1,
    itemsPerPage: 50,
    totalItems: 0,
    selectedTracks: new Set(),
    multiSelectMode: false,
    currentData: {
        artists: [],
        albums: [],
        genres: [],
        tracks: []
    },
    detailContext: null // {type: 'artist', name: 'Artist Name'}
};

// Track Cache for Batch Editing
libraryState.trackMap = new Map();

// Helper to cache tracks
function cacheTracks(tracks) {
    tracks.forEach(track => libraryState.trackMap.set(track.id, track));
}

// Router
function initRouter() {
    function handleRoute() {
        const hash = window.location.hash || '#/pending';
        const route = hash.replace('#/', '');
        
        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.route === route);
        });
        
        // Show/hide pages
        const pendingPage = document.getElementById('pendingPage');
        const libraryPage = document.getElementById('libraryPage');
        
        if (route === 'library') {
            pendingPage.style.display = 'none';
            libraryPage.style.display = 'block';
            
            // Initial load only if empty
            if (libraryState.totalItems === 0 && libraryState.currentData.tracks.length === 0) {
                initLibrary();
            }
        } else {
            pendingPage.style.display = 'block';
            libraryPage.style.display = 'none';
        }
    }
    
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
}

// Initialize Library
async function initLibrary() {
    // Load stats
    await loadLibraryStats();
    
    // Load current view data
    await loadViewData();
    
    // Setup library event listeners (only once)
    if (!window.libraryListenersAttached) {
        setupLibraryListeners();
        window.libraryListenersAttached = true;
    }
}

// Setup Library Event Listeners
function setupLibraryListeners() {
    // View tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            libraryState.currentView = btn.dataset.view;
            libraryState.currentPage = 1; // Reset page on view change
            
            // Reset detail view state
            document.getElementById('detailView').style.display = 'none';
            libraryState.detailContext = null;
            
            updateViewTabs();
            updateSortOptions();
            loadViewData();
        });
    });
    
    // Search
    const searchInput = document.getElementById('librarySearch');
    let searchDebounce;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => {
            libraryState.searchQuery = searchInput.value.trim();
            libraryState.currentPage = 1; // Reset page on search
            loadViewData();
        }, 300);
    });
    
    // Sort
    const sortSelect = document.getElementById('librarySort');
    sortSelect.addEventListener('change', () => {
        libraryState.currentSort = sortSelect.value;
        libraryState.currentPage = 1; // Reset page on sort
        loadViewData();
    });
    
    // Pagination
    document.getElementById('prevPageBtn').addEventListener('click', () => {
        if (libraryState.currentPage > 1) {
            libraryState.currentPage--;
            loadViewData();
        }
    });
    
    document.getElementById('nextPageBtn').addEventListener('click', () => {
        const maxPage = Math.ceil(libraryState.totalItems / libraryState.itemsPerPage);
        if (libraryState.currentPage < maxPage) {
            libraryState.currentPage++;
            loadViewData();
        }
    });
    
    // Rescan button
    const rescanBtn = document.getElementById('rescanBtn');
    if (rescanBtn) rescanBtn.addEventListener('click', startRescan);
    
    // Multi-select toggle button
    const multiSelectBtn = document.getElementById('multiSelectBtn');
    if (multiSelectBtn) multiSelectBtn.addEventListener('click', toggleMultiSelectMode);
    
    // Selection actions
    const editSelectedBtn = document.getElementById('editSelectedBtn');
    if (editSelectedBtn) editSelectedBtn.addEventListener('click', () => showEditModal('batch'));
    
    const clearSelectionBtn = document.getElementById('clearSelectionBtn');
    if (clearSelectionBtn) clearSelectionBtn.addEventListener('click', clearSelection);
    
    // Edit modal
    const batchEditForm = document.getElementById('batchEditForm');
    if (batchEditForm) {
        batchEditForm.addEventListener('submit', handleEditSubmit);
    }
    
    const cancelBatchEdit = document.getElementById('cancelBatchEdit');
    if (cancelBatchEdit) {
        cancelBatchEdit.addEventListener('click', closeEditModal);
    }
    
    // Back button
    const backBtn = document.getElementById('backBtn');
    if (backBtn) backBtn.addEventListener('click', () => {
        document.getElementById('detailView').style.display = 'none';
        const mainView = document.querySelector(`#${libraryState.currentView}View`);
        if (mainView) {
            mainView.classList.add('active');
        } else {
            logEvent('warn', `Main view #${libraryState.currentView}View not found`);
        }
        libraryState.detailContext = null;
    });

    // Global Key Listener (Escape)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (document.getElementById('batchEditModal').style.display === 'flex') {
                closeEditModal();
            } else if (document.getElementById('detailView').style.display === 'block') {
                document.getElementById('backBtn').click();
            }
        }
    });
}

// Load Library Stats
async function loadLibraryStats() {
    try {
        const response = await fetch('/api/library/stats');
        if (!response.ok) return;
        
        const stats = await response.json();
        const statsEl = document.getElementById('libraryStats');
        statsEl.innerHTML = `
            <span class="stat-item">${stats.total_tracks} أغنية</span>
            <span class="stat-item">${stats.total_artists} فنان</span>
            <span class="stat-item">${stats.total_albums} ألبوم</span>
        `;
    } catch (error) {
        logEvent('warn', 'Error loading library stats', {error: error.message});
    }
}

// Load View Data
async function loadViewData() {
    const view = libraryState.currentView;
    const [sortBy, sortOrder] = libraryState.currentSort.split('-');
    const search = libraryState.searchQuery;
    
    // Pagination params
    const limit = libraryState.itemsPerPage;
    const offset = (libraryState.currentPage - 1) * limit;
    
    try {
        // Show loading state
        const container = document.getElementById(`${view}List`) || document.getElementById('tracksList');
        if (container) container.innerHTML = '<div class="loading"><span class="spinning">🔄</span> جاري التحميل...</div>';
        
        let endpoint = `/api/library/${view}`;
        const params = new URLSearchParams();
        
        if (search) params.append('search', search);
        params.append('sort_by', sortBy);
        params.append('sort_order', sortOrder);
        
        // Only sending paging for tracks view currently, but other views support simple client-side paging or full load
        // Actually, API supports limit/offset for tracks.
        // For artists/albums/genres, we might need client-side pagination if list is huge,
        // or update API to support it. The plan said "pagination (or virtualization)".
        // Current API implementation for tracks supports limit/offset.
        // Other endpoints return all data. Let's do client-side pagination for others for now.
        
        if (view === 'tracks') {
            params.append('limit', limit);
            params.append('offset', offset);
        }
        
        const response = await fetch(`${endpoint}?${params}`);
        if (!response.ok) throw new Error('Failed to load data');
        
        const data = await response.json();
        
        libraryState.totalItems = data.total;
        updatePaginationUI();
        
        if (view === 'artists') {
            // Client-side pagination for artists
            libraryState.totalItems = data.artists.length; // Override total
            updatePaginationUI();
            
            // Slice for current page
            const pagedArtists = data.artists.slice(offset, offset + limit);
            
            libraryState.currentData.artists = data.artists;
            renderArtists(pagedArtists);
        } else if (view === 'albums') {
             // Client-side pagination for albums
            libraryState.totalItems = data.albums.length;
            updatePaginationUI();
            
            const pagedAlbums = data.albums.slice(offset, offset + limit);
            
            libraryState.currentData.albums = data.albums;
            renderAlbums(pagedAlbums);
        } else if (view === 'genres') {
            // Client-side pagination for genres
            libraryState.totalItems = data.genres.length;
            updatePaginationUI();
            
            const pagedGenres = data.genres.slice(offset, offset + limit);
            
            libraryState.currentData.genres = data.genres;
            renderGenres(pagedGenres);
        } else if (view === 'tracks') {
            // Server-side pagination for tracks
            libraryState.totalItems = data.total;
            updatePaginationUI();
            
            cacheTracks(data.tracks);
            libraryState.currentData.tracks = data.tracks;
            renderTracks(data.tracks);
        }
    } catch (error) {
        logEvent('error', 'Error loading library view data', {view, error: error.message});
        showAlert(`فشل تحميل بيانات المكتبة: ${error.message}`, 'error');
        const container = document.getElementById(`${view}List`) || document.getElementById('tracksList');
        if (container) container.innerHTML = `<div class="error-message">حدث خطأ في تحميل البيانات: ${error.message}</div>`;
    }
}

// Update Pagination UI
function updatePaginationUI() {
    const pagination = document.getElementById('libraryPagination');
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    
    // Only show pagination if detail view is NOT active
    if (document.getElementById('detailView').style.display === 'block') {
        pagination.style.display = 'none';
        return;
    }
    
    if (libraryState.totalItems === 0) {
        pagination.style.display = 'none';
        return;
    }
    
    const totalPages = Math.ceil(libraryState.totalItems / libraryState.itemsPerPage);
    
    if (totalPages <= 1) {
        pagination.style.display = 'none';
        return;
    }
    
    pagination.style.display = 'flex';
    pageInfo.textContent = `صفحة ${libraryState.currentPage} من ${totalPages} (${libraryState.totalItems} عنصر)`;
    
    prevBtn.disabled = libraryState.currentPage <= 1;
    nextBtn.disabled = libraryState.currentPage >= totalPages;
}

// Update View Tabs
function updateViewTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === libraryState.currentView);
    });
    
    document.querySelectorAll('.view-content').forEach(view => {
        view.classList.remove('active');
    });
    
    // Only show the main list view if detail view is NOT active
    if (!libraryState.detailContext) {
        document.getElementById(`${libraryState.currentView}View`).classList.add('active');
    }
}

// Update Sort Options
function updateSortOptions() {
    const sortSelect = document.getElementById('librarySort');
    const view = libraryState.currentView;
    
    const options = {
        artists: [
            {value: 'name-asc', label: 'الاسم (أ - ي)'},
            {value: 'name-desc', label: 'الاسم (ي - أ)'},
            {value: 'track_count-desc', label: 'عدد الأغاني'},
            {value: 'album_count-desc', label: 'عدد الألبومات'}
        ],
        albums: [
            {value: 'name-asc', label: 'الاسم (أ - ي)'},
            {value: 'name-desc', label: 'الاسم (ي - أ)'},
            {value: 'year-desc', label: 'السنة (الأحدث)'},
            {value: 'track_count-desc', label: 'عدد الأغاني'}
        ],
        genres: [
            {value: 'name-asc', label: 'الاسم (أ - ي)'},
            {value: 'name-desc', label: 'الاسم (ي - أ)'},
            {value: 'track_count-desc', label: 'عدد الأغاني'}
        ],
        tracks: [
            {value: 'artist-asc', label: 'الفنان'},
            {value: 'album-asc', label: 'الألبوم'},
            {value: 'title-asc', label: 'العنوان'},
            {value: 'year-desc', label: 'السنة'}
        ]
    };
    
    sortSelect.innerHTML = options[view].map(opt =>
        `<option value="${opt.value}">${opt.label}</option>`
    ).join('');
    
    sortSelect.value = libraryState.currentSort;
}

// Render Artists
function renderArtists(artists) {
    const container = document.getElementById('artistsList');
    
    if (artists.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = artists.map(artist => `
        <div class="list-item" onclick="viewArtistAlbums('${encodeURIComponent(artist.name)}')">
            <div class="list-item-content">
                <div class="list-item-title">${artist.name}</div>
                <div class="list-item-meta">${artist.track_count} أغنية • ${artist.album_count} ألبوم</div>
            </div>
        </div>
    `).join('');
}

// Render Albums
function renderAlbums(albums) {
    const container = document.getElementById('albumsList');
    
    if (albums.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = albums.map(album => `
        <div class="album-card" onclick="viewAlbumTracks('${encodeURIComponent(album.name)}')">
            <div class="album-artwork">
                ${album.artwork_id 
                    ? `<img src="/api/library/tracks/${album.artwork_id}/artwork?t=${Date.now()}" alt="Cover">` 
                    : '🎵'}
            </div>
            <div class="album-name">${album.name || 'بدون اسم'}</div>
            <div class="album-artist">${album.album_artist || 'غير معروف'}</div>
            <div class="list-item-meta">${album.track_count} أغنية${album.year ? ' • ' + album.year : ''}</div>
        </div>
    `).join('');
}

// Render Genres
function renderGenres(genres) {
    const container = document.getElementById('genresList');
    
    if (genres.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = genres.map(genre => `
        <div class="list-item" onclick="viewGenreTracks('${encodeURIComponent(genre.name)}')">
            <div class="list-item-content">
                <div class="list-item-title">${genre.name}</div>
                <div class="list-item-meta">${genre.track_count} أغنية</div>
            </div>
        </div>
    `).join('');
}

// Render Tracks
function renderTracks(tracks, showCheckboxes = true) {
    const container = libraryState.detailContext 
        ? document.getElementById('detailContent')
        : document.getElementById('tracksList');
    
    if (tracks.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>لا توجد أغاني</p></div>';
        return;
    }
    
    // Helper to escape JSON for attribute
    const escapeAttr = (str) => (str || '').replace(/"/g, '&quot;');
    
    container.innerHTML = tracks.map(track => {
        // Safe JSON stringify for data attribute
        const trackJson = JSON.stringify(track).replace(/'/g, "&#39;");
        const isSelected = libraryState.selectedTracks.has(track.id);
        
        return `
        <div class="list-item ${isSelected ? 'selected' : ''}" data-track-id="${track.id}" data-track-json='${trackJson}' onclick="handleTrackClick(event, this)">
            ${libraryState.multiSelectMode ? `<input type="checkbox" class="list-item-checkbox" data-track-id="${track.id}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation()">` : ''}
            <div class="list-item-content">
                <div class="list-item-title">${track.title || 'بدون عنوان'}</div>
                <div class="list-item-meta">
                    ${track.artist || 'غير معروف'} • 
                    ${track.album || 'غير معروف'}
                    ${track.year ? ' • ' + track.year : ''}
                </div>
            </div>
            ${isSelected && libraryState.multiSelectMode ? '<span class="selection-check">✓</span>' : ''}
        </div>
        `;
    }).join('');
    
    // Checkbox listeners now inline to stop propagation
    container.querySelectorAll('.list-item-checkbox').forEach(cb => {
        cb.addEventListener('change', handleTrackSelection);
    });
}

// Handle Track Click (Single Edit or Selection Toggle)
function handleTrackClick(event, element) {
    // If clicking checkbox, ignore (handled by its own listener)
    if (event.target.classList.contains('list-item-checkbox')) return;
    
    const trackId = parseInt(element.dataset.trackId);
    const trackData = JSON.parse(element.dataset.trackJson || '{}');
    
    if (libraryState.multiSelectMode) {
        // In multi-select mode, toggle selection
        if (libraryState.selectedTracks.has(trackId)) {
            libraryState.selectedTracks.delete(trackId);
        } else {
            libraryState.selectedTracks.add(trackId);
        }
        updateSelectionBar();
        // Re-render to update visual state
        const tracks = libraryState.detailContext 
            ? libraryState.currentData.tracks 
            : libraryState.currentData.tracks;
        if (libraryState.detailContext) {
            // In detail view, we need to get the tracks from the API cache
            renderTracks(Array.from(libraryState.trackMap.values()).filter(t => 
                libraryState.currentData.tracks.some(ct => ct.id === t.id)
            ));
        } else {
            renderTracks(libraryState.currentData.tracks);
        }
    } else {
        // Not in multi-select mode, open edit modal
        showEditModal('single', trackData);
    }
}

// View Artist Albums
async function viewArtistAlbums(artistName) {
    const name = decodeURIComponent(artistName);
    
    try {
        const response = await fetch(`/api/library/albums?artist=${encodeURIComponent(name)}`);
        if (!response.ok) throw new Error('Failed to load albums');
        
        const data = await response.json();
        
        libraryState.detailContext = {type: 'artist', name: name};
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `ألبومات ${name}`;
        
        const detailContent = document.getElementById('detailContent');
        // Use album-card layout with artwork (same as main Albums view)
        detailContent.className = 'albums-grid';
        detailContent.innerHTML = data.albums.map(album => `
            <div class="album-card" onclick="viewAlbumTracks('${encodeURIComponent(album.name)}')">
                <div class="album-artwork">
                    ${album.artwork_id 
                        ? `<img src="/api/library/tracks/${album.artwork_id}/artwork?t=${Date.now()}" alt="Cover">` 
                        : '🎵'}
                </div>
                <div class="album-name">${album.name || 'بدون اسم'}</div>
                <div class="list-item-meta">${album.track_count} أغنية</div>
            </div>
        `).join('');
    } catch (error) {
        logEvent('error', 'Error loading artist albums', {artist: name, error: error.message});
        showAlert(`فشل تحميل ألبومات الفنان: ${error.message}`, 'error');
    }
}

// View Album Tracks
async function viewAlbumTracks(albumName) {
    const name = decodeURIComponent(albumName);
    
    try {
        const response = await fetch(`/api/library/tracks?album=${encodeURIComponent(name)}&limit=500`);
        if (!response.ok) throw new Error('Failed to load tracks');
        
        const data = await response.json();
        
        libraryState.detailContext = {type: 'album', name: name};
        libraryState.currentData.tracks = data.tracks; // Store for select all
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `أغاني ألبوم ${name}`;
        
        const detailContent = document.getElementById('detailContent');
        detailContent.className = 'items-list'; // Reset to list layout
        
        cacheTracks(data.tracks);
        
        // Add "Select All Album" button before tracks
        const selectAllBtn = `
            <button id="selectAlbumBtn" class="btn-secondary" style="margin-bottom: 12px; width: 100%;">
                تحديد جميع الأغاني (${data.tracks.length})
            </button>
        `;
        
        // Render tracks then prepend button
        renderTracks(data.tracks);
        detailContent.insertAdjacentHTML('afterbegin', selectAllBtn);
        
        // Attach select all handler
        document.getElementById('selectAlbumBtn').addEventListener('click', () => {
            selectAllAlbumTracks(data.tracks);
        });
    } catch (error) {
        logEvent('error', 'Error loading album tracks', {album: name, error: error.message});
        showAlert(`فشل تحميل أغاني الألبوم: ${error.message}`, 'error');
    }
}

// Select All Album Tracks
function selectAllAlbumTracks(tracks) {
    // Enable multi-select mode if not already
    if (!libraryState.multiSelectMode) {
        libraryState.multiSelectMode = true;
        const btn = document.getElementById('multiSelectBtn');
        if (btn) {
            btn.textContent = 'إلغاء التحديد';
            btn.classList.add('active');
        }
    }
    
    // Clear previous selection and select all tracks in this album
    libraryState.selectedTracks.clear();
    tracks.forEach(track => libraryState.selectedTracks.add(track.id));
    
    updateSelectionBar();
    renderTracks(tracks);
    
    // Re-add select all button
    const detailContent = document.getElementById('detailContent');
    const selectAllBtn = `
        <button id="selectAlbumBtn" class="btn-secondary" style="margin-bottom: 12px; width: 100%;">
            تحديد جميع الأغاني (${tracks.length})
        </button>
    `;
    detailContent.insertAdjacentHTML('afterbegin', selectAllBtn);
    document.getElementById('selectAlbumBtn').addEventListener('click', () => {
        selectAllAlbumTracks(tracks);
    });
}

// View Genre Tracks
async function viewGenreTracks(genreName) {
    const name = decodeURIComponent(genreName);
    
    try {
        const response = await fetch(`/api/library/tracks?genre=${encodeURIComponent(name)}&limit=500`);
        if (!response.ok) throw new Error('Failed to load tracks');
        
        const data = await response.json();
        
        libraryState.detailContext = {type: 'genre', name: name};
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `أغاني نوع ${name}`;
        
        cacheTracks(data.tracks);
        renderTracks(data.tracks);
    } catch (error) {
        logEvent('error', 'Error loading genre tracks', {genre: name, error: error.message});
        showAlert(`فشل تحميل أغاني النوع: ${error.message}`, 'error');
    }
}

// Handle Track Selection
function handleTrackSelection(event) {
    const trackId = parseInt(event.target.dataset.trackId);
    
    if (event.target.checked) {
        libraryState.selectedTracks.add(trackId);
    } else {
        libraryState.selectedTracks.delete(trackId);
    }
    
    updateSelectionBar();
}

// Update Selection Bar
function updateSelectionBar() {
    const selectionBar = document.getElementById('selectionBar');
    const libraryPage = document.getElementById('libraryPage');
    const count = libraryState.selectedTracks.size;
    
    if (count === 0 && !libraryState.multiSelectMode) {
        selectionBar.style.display = 'none';
        if (libraryPage) libraryPage.style.paddingBottom = '';
        return;
    }
    
    selectionBar.style.display = 'flex';
    // Add padding to prevent selection bar from overlaying content
    if (libraryPage) libraryPage.style.paddingBottom = '80px';
    document.getElementById('selectionCount').textContent = count > 0 ? `${count} محدد` : 'اختر العناصر';
    document.getElementById('selectionDetails').textContent = '';
}

// Toggle Multi-Select Mode
function toggleMultiSelectMode() {
    libraryState.multiSelectMode = !libraryState.multiSelectMode;
    
    // Update button text
    const btn = document.getElementById('multiSelectBtn');
    if (btn) {
        btn.textContent = libraryState.multiSelectMode ? 'إلغاء التحديد' : 'تحديد متعدد';
        btn.classList.toggle('active', libraryState.multiSelectMode);
    }
    
    // Update selection bar visibility
    updateSelectionBar();
    
    // Re-render current tracks to show/hide checkboxes
    if (libraryState.currentView === 'tracks' || libraryState.detailContext) {
        if (libraryState.detailContext) {
            renderTracks(Array.from(libraryState.trackMap.values()).filter(t => 
                libraryState.currentData.tracks.some(ct => ct.id === t.id)
            ));
        } else {
            renderTracks(libraryState.currentData.tracks);
        }
    }
}

// Clear Selection
function clearSelection() {
    libraryState.selectedTracks.clear();
    libraryState.multiSelectMode = false;
    
    // Reset button text
    const btn = document.getElementById('multiSelectBtn');
    if (btn) {
        btn.textContent = 'تحديد متعدد';
        btn.classList.remove('active');
    }
    
    document.querySelectorAll('.list-item-checkbox').forEach(cb => cb.checked = false);
    updateSelectionBar();
    
    // Re-render to remove checkboxes
    if (libraryState.currentView === 'tracks' || libraryState.detailContext) {
        if (libraryState.detailContext) {
            renderTracks(Array.from(libraryState.trackMap.values()).filter(t => 
                libraryState.currentData.tracks.some(ct => ct.id === t.id)
            ));
        } else {
            renderTracks(libraryState.currentData.tracks);
        }
    }
}

// Show Edit Modal
function showEditModal(mode, trackData = null) {
    libraryState.editMode = mode;
    libraryState.editTrackData = trackData;
    
    // Reset form
    document.getElementById('batchEditForm').reset();
    
    const modal = document.getElementById('batchEditModal');
    const title = modal.querySelector('h3');
    const keepCheckboxes = modal.querySelectorAll('input[type="checkbox"][id$="Keep"]');
    
    // Artwork UI Container (Dynamically added if missing)
    let artworkSection = document.getElementById('editArtworkSection');
    if (!artworkSection) {
        artworkSection = document.createElement('div');
        artworkSection.id = 'editArtworkSection';
        artworkSection.className = 'form-group artwork-upload-section';
        // Insert before the first form group
        const firstGroup = modal.querySelector('.form-group');
        firstGroup.parentNode.insertBefore(artworkSection, firstGroup);
    }
    
    if (mode === 'single' && trackData) {
        title.textContent = 'تعديل الملف';
        
        // Hide "Keep" checkboxes
        keepCheckboxes.forEach(cb => {
            cb.checked = false;
            cb.parentElement.style.display = 'none';
        });
        
        // Show Artwork Section
        artworkSection.style.display = 'block';
        artworkSection.innerHTML = `
            <label>صورة الغلاف</label>
            <div class="artwork-preview-container">
                <div class="artwork-preview">
                    ${trackData.has_artwork 
                        ? `<img src="/api/library/tracks/${trackData.id}/artwork?t=${Date.now()}" alt="Cover">` 
                        : '<span class="artwork-placeholder">🎵</span>'}
                </div>
                <div class="artwork-upload-controls">
                    <input type="file" id="artworkUpload" accept="image/jpeg,image/png" style="display: none;">
                    <button type="button" class="btn-secondary" onclick="document.getElementById('artworkUpload').click()">
                        تغيير الصورة
                    </button>
                    <span id="artworkFileName" class="file-name"></span>
                </div>
            </div>
        `;
        
        // Handle file selection display
        setTimeout(() => {
            const fileInput = document.getElementById('artworkUpload');
            if (fileInput) {
                fileInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        document.getElementById('artworkFileName').textContent = file.name;
                        // Preview
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            const container = document.querySelector('.artwork-preview');
                            container.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
                        };
                        reader.readAsDataURL(file);
                    }
                });
            }
        }, 0);
        
        // Pre-fill fields
        document.getElementById('batchTitle').value = trackData.title || '';
        document.getElementById('batchArtist').value = trackData.artist || '';
        document.getElementById('batchAlbum').value = trackData.album || '';
        document.getElementById('batchGenre').value = trackData.genre || '';
        document.getElementById('batchYear').value = trackData.year || '';
        
    } else {
        title.textContent = 'تعديل الميتاداتا (متعدد)';
        
        // Hide Artwork Section for batch
        artworkSection.style.display = 'none';
        
        // Smart Batch Logic
        const trackIds = Array.from(libraryState.selectedTracks);
        const tracks = trackIds.map(id => libraryState.trackMap.get(id)).filter(t => t);
        
        // Initialize common values with the first track
        const common = {
            Title: tracks[0]?.title,
            Artist: tracks[0]?.artist,
            Album: tracks[0]?.album,
            Genre: tracks[0]?.genre,
            Year: tracks[0]?.year
        };
        
        // Check for consistency across all tracks
        // distinctNull means we found a conflict (different values)
        const conflict = {Title: false, Artist: false, Album: false, Genre: false, Year: false};
        
        for (let i = 1; i < tracks.length; i++) {
            if (tracks[i].title !== common.Title) conflict.Title = true;
            if (tracks[i].artist !== common.Artist) conflict.Artist = true;
            if (tracks[i].album !== common.Album) conflict.Album = true;
            if (tracks[i].genre !== common.Genre) conflict.Genre = true;
            if (tracks[i].year !== common.Year) conflict.Year = true;
        }
        
        // Apply to form
        const applyField = (field) => {
             const input = document.getElementById('batch' + field);
             const keepCb = document.getElementById('batch' + field + 'Keep');
             const hasConflict = conflict[field];
             const val = common[field];
             
             if (!hasConflict && val !== undefined && val !== null) {
                 // All tracks have same value
                 input.value = val;
                 input.placeholder = '';
                 // "Grayed out text" request usually implies disabled, but we want to allow editing.
                 // "put the fields that are the same... in their respective fields" matches this.
                 // We uncheck "Keep" so it's active for editing, or keep it checked if user wants?
                 // Usually if it's filled, it's ready. If I want to change all artists, I type new one.
                 // If I leave it as is, it updates all to the SAME value (no change).
                 keepCb.checked = false; 
             } else {
                 // Multiple values or all empty
                 input.value = '';
                 input.placeholder = hasConflict ? 'قيم متعددة (لن يتم التغيير)' : '';
                 keepCb.checked = true;
             }
             
             keepCb.parentElement.style.display = 'inline-block';
        };

        ['Title', 'Artist', 'Album', 'Genre', 'Year'].forEach(f => applyField(f));
    }
    
    modal.style.display = 'flex';
}

// Close Edit Modal
function closeEditModal() {
    document.getElementById('batchEditModal').style.display = 'none';
    libraryState.editMode = null;
    libraryState.editTrackData = null;
}

// Handle All Edit Submissions
async function handleEditSubmit(event) {
    event.preventDefault();
    
    if (libraryState.editMode === 'single') {
        await handleSingleEdit();
    } else {
        await handleBatchEdit();
    }
}

// Handle Single Edit
async function handleSingleEdit() {
    const trackId = libraryState.editTrackData.id;
    
    // 1. Upload Artwork if selected
    const fileInput = document.getElementById('artworkUpload');
    if (fileInput && fileInput.files.length > 0) {
        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            const response = await fetch(`/api/library/tracks/${trackId}/artwork`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Artwork upload failed');
        } catch (error) {
            logEvent('error', 'Error uploading artwork', {trackId, error: error.message});
            showAlert('فشل رفع صورة الغلاف', 'error');
            // Don't return, try to save other metadata
        }
    }
    
    // 2. Update Metadata
    const payload = {
        title: document.getElementById('batchTitle').value,
        artist: document.getElementById('batchArtist').value,
        album: document.getElementById('batchAlbum').value,
        genre: document.getElementById('batchGenre').value,
        year: parseInt(document.getElementById('batchYear').value) || null
    };
    
    try {
        const response = await fetch(`/api/library/tracks/${trackId}/update`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Update failed');
        
        closeEditModal();
        loadViewData(); // Refresh view
        
    } catch (error) {
        logEvent('error', 'Error updating track', {trackId, error: error.message});
        showAlert('خطأ في تحديث الملف', 'error');
    }
}

// Handle Batch Edit
async function handleBatchEdit() {
    const trackIds = Array.from(libraryState.selectedTracks);
    if (trackIds.length === 0) return;
    
    const payload = {track_ids: trackIds};
    
    // Only include fields that are not marked as "keep unchanged"
    if (!document.getElementById('batchTitleKeep').checked) {
        payload.title = document.getElementById('batchTitle').value;
    }
    if (!document.getElementById('batchArtistKeep').checked) {
        payload.artist = document.getElementById('batchArtist').value;
    }
    if (!document.getElementById('batchAlbumKeep').checked) {
        payload.album = document.getElementById('batchAlbum').value;
    }
    if (!document.getElementById('batchGenreKeep').checked) {
        payload.genre = document.getElementById('batchGenre').value;
    }
    if (!document.getElementById('batchYearKeep').checked) {
        payload.year = parseInt(document.getElementById('batchYear').value) || null;
    }
    
    try {
        const response = await fetch('/api/library/tracks/batch-update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Batch update failed');
        
        const result = await response.json();
        showAlert(`تم التحديث: ${result.successful} نجح، ${result.failed} فشل`, 'success');
        logEvent('info', 'Batch update completed', result);
        
        closeEditModal();
        clearSelection();
        loadViewData();
        
    } catch (error) {
        logEvent('error', 'Error in batch update', {error: error.message});
        showAlert('خطأ في تحديث الملفات', 'error');
    }
}

// Start Rescan
async function startRescan() {
    const btn = document.getElementById('rescanBtn');
    const icon = document.getElementById('rescanIcon');
    
    btn.disabled = true;
    icon.classList.add('spinning');
    
    try {
        const response = await fetch('/api/library/rescan', {method: 'POST'});
        if (!response.ok) throw new Error('Failed to start rescan');
        
        // Status is shown via spinning icon - no popup needed
        
        // Poll for status
        const checkStatus = async () => {
            const statusResponse = await fetch('/api/library/rescan/status');
            const status = await statusResponse.json();
            
            if (status.is_scanning) {
                setTimeout(checkStatus, 2000);
            } else {
                btn.disabled = false;
                icon.classList.remove('spinning');
                await loadLibraryStats();
                await loadViewData();
            }
        };
        
        checkStatus();
        
    } catch (error) {
        logEvent('error', 'Error starting library rescan', {error: error.message});
        showAlert('خطأ في بدء المسح', 'error');
        btn.disabled = false;
        icon.classList.remove('spinning');
    }
}

// Start app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        init();
        initRouter();
    });
} else {
    init();
    initRouter();
}
