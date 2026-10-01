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

// Arabic names for the fields a pending card saves
const FIELD_LABELS = {title: 'العنوان', artist: 'الفنان', genre: 'النوع'};
// What each missing field asks of the operator, in the order the card shows them
const MISSING_FIELD_ACTIONS = {title: 'أضف العنوان', artist: 'أضف فنانًا', genre: 'اختر النوع'};
const CONFIRM_LABEL = '✓ تأكيد ونقل إلى المكتبة';
// The check beside each required field on a needs-review card: [missing, done]
const FIELD_CHECK_TEXT = {
    title: ['✗ مطلوب', '✓'],
    artist: ['✗ فنان واحد على الأقل', '✓'],
    genre: ['✗ اختر نوعًا', '✓'],
};

// State
let pendingItems = [];
let selectedGenres = {}; // itemId -> genre
let customGenreVisible = {}; // itemId -> boolean
const expandedCards = new Set(); // ready cards the user opened on a phone; they stay open
const openedGenres = new Set();  // needs-review cards whose folded genre the user opened
let confirmAllRunning = false;
const confirmedFolders = []; // the folder of every file confirmed since this page loaded, in order
let sseConnection = null;
let pendingPollTimer = null;
let debugEnabled = false;
const appLogs = [];
const MAX_LOG_ENTRIES = 800;
const ARTIST_SUGGEST_DEBOUNCE_MS = 220;
const ARTIST_SUGGEST_CACHE_TTL_MS = 60 * 1000;
const ARTIST_CREATE_THRESHOLD = 72;
const ARTIST_SUGGEST_LIMIT = 10;
const LIBRARY_MOBILE_BREAKPOINT_PX = 768;
const artistSuggestCache = new Map(); // `${query}|${limit}` -> {timestamp, data}
const artistComboboxState = new Map(); // rowId -> combobox state
const artistRowsMap = new Map(); // itemId -> array of artist strings
const artistDraftValues = new Map(); // itemId -> in-progress input value (joined artists)
const titleDraftValues = new Map(); // itemId -> in-progress title input value

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

// Fills an alert box: a human line, plus the technical text folded away when there is one
function fillAlert(alertEl, message, type, technical) {
    alertEl.className = `global-alert ${type}`;
    alertEl.replaceChildren(document.createTextNode(message));
    if (technical && technical !== message) {
        const details = document.createElement('details');
        details.className = 'alert-technical';
        const summary = document.createElement('summary');
        summary.textContent = 'التفاصيل التقنية';
        const code = document.createElement('code');
        code.dir = 'ltr';
        code.textContent = technical;
        details.append(summary, code);
        alertEl.append(details);
    }
    alertEl.style.display = 'block';
}

function showAlert(message, type = 'info', timeout, technical = '') {
    const alertEl = document.getElementById('globalAlert');
    if (!alertEl) return;
    // Errors stay until dismissed; everything else fades after 5s
    if (timeout === undefined) timeout = type === 'error' ? 0 : 5000;
    fillAlert(alertEl, message, type, technical);
    alertEl.title = 'اضغط للإغلاق';
    alertEl.onclick = event => {
        if (event.target.closest('details')) return;  // opening the details must not dismiss
        alertEl.style.display = 'none';
    };

    if (timeout > 0) {
        setTimeout(() => {
            if (alertEl.firstChild?.textContent === message) {
                alertEl.style.display = 'none';
            }
        }, timeout);
    }
}

// An error with a human Arabic message and the server's raw text kept for the details fold
class ApiError extends Error {
    constructor(message, technical = '') {
        super(message);
        this.technical = technical;
    }
}

// Server details that are still English, in the words the operator would use
const SERVER_ERROR_TEXT = {
    'Item not found': 'هذا الملف لم يعد في قائمة الانتظار. حدّث القائمة.',
    'File not found': 'الملف غير موجود في مجلد التجهيز. ربما نُقل أو حُذف.',
    'Failed to apply metadata': 'تعذّرت كتابة البيانات الوصفية في الملف.',
    'Failed to move file': 'تعذّر نقل الملف إلى المكتبة. تحقق من صلاحيات الكتابة في مجلد المكتبة.',
    'Artwork not found': 'لا توجد صورة غلاف لهذا الملف.',
    'Artwork file not found': 'صورة الغلاف غير موجودة على القرص.',
    'Track not found': 'هذه الصوتية لم تعد في المكتبة. حدّث الصفحة.',
    'Track file not found': 'ملف هذه الصوتية غير موجود على القرص. أعد مسح المكتبة.',
    'Nothing to change': 'لا يوجد تغيير لحفظه.',
    'Failed to update file metadata': 'تعذّرت كتابة البيانات الوصفية في ملف الصوتية.',
    'File must be a valid JPEG or PNG image': 'صورة الغلاف يجب أن تكون بصيغة JPEG أو PNG.',
    'Failed to embed artwork': 'تعذّر حفظ صورة الغلاف داخل الملف.',
    'No artwork in file': 'لا توجد صورة غلاف داخل الملف.',
    'Scan already in progress': 'المسح يعمل بالفعل.',
    'chat_id is required when a bot token is set': 'أدخل معرّف المحادثة مع رمز البوت.',
};
const ARABIC_LETTERS = /[؀-ۿ]/;

// Raw server text -> {message, technical}. Arabic details are kept (minus any English gloss);
// known English ones are translated; anything else gets the caller's fallback.
function humanizeServerDetail(raw, fallbackMessage) {
    const text = String(raw || '').trim();
    if (!text) return {message: fallbackMessage, technical: ''};
    if (SERVER_ERROR_TEXT[text]) return {message: SERVER_ERROR_TEXT[text], technical: text};
    if (text.startsWith('Item cannot be confirmed')) {
        return {message: 'لا يمكن تأكيد هذا الملف في حالته الحالية. حدّث القائمة.', technical: text};
    }
    if (ARABIC_LETTERS.test(text)) {
        const message = text.replace(/\s*\([A-Za-z][^)]*\)\s*$/, '');
        return {message, technical: message === text ? '' : text};
    }
    return {message: fallbackMessage, technical: text};
}

async function apiError(response, fallbackMessage) {
    let raw = '';
    try {
        const body = await response.json();
        // FastAPI validation errors (422) arrive as a list of {loc, msg}
        raw = Array.isArray(body.detail)
            ? body.detail.map(e => `${(e.loc || []).slice(-1)[0] || ''}: ${e.msg}`).join(' · ')
            : (typeof body.detail === 'string' ? body.detail : '');
    } catch {
        // Not JSON (proxy error page, empty body): only the status is known
    }
    const {message, technical} = humanizeServerDetail(raw, fallbackMessage);
    return new ApiError(message, technical || `HTTP ${response.status}`);
}

// Any thrown error -> what to show. fetch() rejects with a TypeError when the server is unreachable.
function describeError(error) {
    if (error instanceof ApiError) return {message: error.message, technical: error.technical};
    if (error instanceof TypeError) {
        return {message: 'تعذّر الاتصال بالخادم. تحقق من الشبكة ثم حاول مجددًا.', technical: error.message};
    }
    const {message, technical} = humanizeServerDetail(error?.message, 'حدث خطأ غير متوقع.');
    return {message, technical};
}

// "<what failed>: <why>" with the technical text folded underneath
function showError(what, error) {
    const {message, technical} = describeError(error);
    showAlert(`${what}: ${message}`, 'error', 0, technical);
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatArtistDisplay(artist) {
    if (!artist) return 'غير معروف';
    return artist.split(';').map(a => a.trim()).filter(Boolean).join(' / ');
}

function normalizeArtistClient(value) {
    if (!value) return '';
    const map = {
        'أ': 'ا',
        'إ': 'ا',
        'آ': 'ا',
        'ٱ': 'ا',
        'ى': 'ي',
        'ؤ': 'و',
        'ئ': 'ي',
        'ة': 'ه'
    };

    const diacritics = /[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g;
    const punctuation = /[^\w\s\u0600-\u06FF]/g;

    let normalized = String(value).toLowerCase().normalize('NFKC').replace(/ـ/g, '');
    normalized = normalized.replace(diacritics, '');
    normalized = normalized
        .split('')
        .map(char => map[char] || char)
        .join('');
    normalized = normalized.replace(punctuation, ' ');
    normalized = normalized.replace(/\s+/g, ' ').trim();
    return normalized;
}

function getArtistState(itemId) {
    if (!artistComboboxState.has(itemId)) {
        artistComboboxState.set(itemId, {
            isOpen: false,
            isLoading: false,
            suggestions: [],
            canCreate: false,
            createSuggestion: null,
            highlightedIndex: -1,
            requestToken: 0,
            debounceTimer: null,
            createArtistOnSave: false,
            selectedExistingName: null
        });
    }

    return artistComboboxState.get(itemId);
}

function cleanupArtistState() {
    const activeIds = new Set(pendingItems.map(item => item.id));
    // Combobox state is per row ("12_artist_0"), not per item
    for (const rowId of artistComboboxState.keys()) {
        if (!activeIds.has(getItemIdFromRowId(rowId))) {
            artistComboboxState.delete(rowId);
        }
    }

    for (const itemId of artistDraftValues.keys()) {
        if (!activeIds.has(itemId)) {
            artistDraftValues.delete(itemId);
        }
    }

    for (const itemId of titleDraftValues.keys()) {
        if (!activeIds.has(itemId)) {
            titleDraftValues.delete(itemId);
        }
    }
}

function captureFocusSnapshot() {
    const activeElement = document.activeElement;
    if (!activeElement) {
        return null;
    }

    if (activeElement.classList.contains('artist-input')) {
        return {
            type: 'artist',
            rowId: activeElement.dataset.rowId,
            selectionStart: activeElement.selectionStart,
            selectionEnd: activeElement.selectionEnd
        };
    }

    if (activeElement.classList.contains('title-input')) {
        return {
            type: 'title',
            itemId: Number(activeElement.dataset.id),
            selectionStart: activeElement.selectionStart,
            selectionEnd: activeElement.selectionEnd
        };
    }

    return null;
}

function restoreFocusSnapshot(snapshot) {
    if (!snapshot) {
        return;
    }

    if (snapshot.type === 'title') {
        const titleInput = document.querySelector(`.title-input[data-id="${snapshot.itemId}"]`);
        if (!titleInput) return;
        titleInput.focus();
        if (typeof snapshot.selectionStart === 'number' && typeof snapshot.selectionEnd === 'number') {
            titleInput.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
        }
        return;
    }

    if (snapshot.type !== 'artist') {
        return;
    }

    const artistInput = document.querySelector(`.artist-input[data-row-id="${snapshot.rowId}"]`);
    if (!artistInput) {
        return;
    }

    artistInput.focus();
    if (typeof snapshot.selectionStart === 'number' && typeof snapshot.selectionEnd === 'number') {
        artistInput.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
    }
}

const DEBUG_STORAGE_KEY = 'metadataEditor.debug';

// The genre confirmed last, overall and per channel. It only orders the chips:
// the suggestion goes first, but nothing is selected for the operator.
const GENRE_MEMORY_KEY = 'metadataEditor.genreMemory';

function readGenreMemory() {
    try {
        const memory = JSON.parse(localStorage.getItem(GENRE_MEMORY_KEY) || '{}');
        return {last: memory.last || '', byChannel: memory.byChannel || {}};
    } catch {
        return {last: '', byChannel: {}};  // blocked or corrupt storage: default order
    }
}

function rememberGenre(channel, genre) {
    if (!GENRE_PRESETS.includes(genre)) return;
    const memory = readGenreMemory();
    memory.last = genre;
    if (channel && channel !== 'Unknown') memory.byChannel[channel] = genre;
    try {
        localStorage.setItem(GENRE_MEMORY_KEY, JSON.stringify(memory));
    } catch {
        // Not persisted; the order falls back to the default next time
    }
}

// {genre, reason}: this channel's last genre, else the last genre confirmed at all
function suggestedGenre(item) {
    const memory = readGenreMemory();
    const byChannel = memory.byChannel[item.channel];
    if (GENRE_PRESETS.includes(byChannel)) return {genre: byChannel, reason: 'هذه القناة'};
    if (GENRE_PRESETS.includes(memory.last)) return {genre: memory.last, reason: 'آخر اختيار'};
    return {genre: '', reason: ''};
}

function readDebugPreference() {
    try {
        return localStorage.getItem(DEBUG_STORAGE_KEY) === '1';
    } catch {
        return false;  // private mode or blocked storage: debug simply starts off
    }
}

function setDebugEnabled(enabled) {
    debugEnabled = enabled;
    try {
        localStorage.setItem(DEBUG_STORAGE_KEY, enabled ? '1' : '0');
    } catch {
        // Not persisted; the toggle still works for this page load
    }
    applyDebugUIState();
    renderItems();
}

function setupGlobalUI() {
    const refreshBtn = document.getElementById('refreshPendingBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadPendingItems({showLoading: true}));
    }

    ['confirmAllReadyBtn', 'readyBarConfirmBtn'].forEach(id => {
        document.getElementById(id)?.addEventListener('click', onConfirmAllClick);
    });

    // Diagnostics live in Settings; the queue only shows their effect (the per-card preview button)
    debugEnabled = readDebugPreference();
    const debugToggle = document.getElementById('debugModeToggle');
    if (debugToggle) {
        debugToggle.addEventListener('change', () => setDebugEnabled(debugToggle.checked));
    }

    const toggleLogsBtn = document.getElementById('toggleLogsBtn');
    const logPanel = document.getElementById('logPanel');
    if (toggleLogsBtn && logPanel) {
        toggleLogsBtn.addEventListener('click', () => {
            logPanel.hidden = !logPanel.hidden;
            toggleLogsBtn.textContent = logPanel.hidden ? 'إظهار سجل العمليات' : 'إخفاء سجل العمليات';
            toggleLogsBtn.setAttribute('aria-expanded', String(!logPanel.hidden));
            if (!logPanel.hidden) {
                renderLogPanel();
            }
        });
    }

    const downloadLogsBtn = document.getElementById('downloadLogsBtn');
    if (downloadLogsBtn) {
        downloadLogsBtn.addEventListener('click', downloadLogs);
    }

    document.addEventListener('click', event => {
        if (!event.target.closest('.artist-combobox')) {
            closeAllArtistDropdowns();
        }
    });

    // Artwork that fails to load (file moved, unreadable) falls back to the placeholder
    document.addEventListener('error', event => {
        const img = event.target;
        if (!(img instanceof HTMLImageElement) || !img.closest('.item-card, .album-artwork, .artwork-preview')) return;
        const placeholder = document.createElement(img.classList.contains('artwork') ? 'div' : 'span');
        placeholder.className = img.classList.contains('artwork') ? 'artwork-placeholder' : 'artwork-missing';
        placeholder.setAttribute('aria-hidden', 'true');
        placeholder.textContent = '♪';
        img.replaceWith(placeholder);
    }, true);

    applyDebugUIState();
}

function applyDebugUIState() {
    const debugToggle = document.getElementById('debugModeToggle');
    const workflowSteps = document.getElementById('workflowSteps');
    if (debugToggle) debugToggle.checked = debugEnabled;
    if (workflowSteps) workflowSteps.hidden = !debugEnabled;
}

// Initialize app
async function init() {
    setupGlobalUI();
    pendingLoadedOnce = await loadPendingItems({showLoading: true});
    revealLinkedCard();
    setupSSE();
    if (pendingPollTimer) {
        clearInterval(pendingPollTimer);
    }
    pendingPollTimer = setInterval(() => {
        loadPendingItems({silent: true, smartUpdate: true});
    }, 15000);
}

// A Telegram message links to #/pending/<id>. Once the queue is loaded, that card opens
// (if collapsed), scrolls to the top and takes focus, with the arrival mark of a new file.
let pendingLoadedOnce = false;

function revealLinkedCard() {
    const match = (window.location.hash || '').match(/^#\/pending\/(\d+)$/);
    if (!match || !pendingLoadedOnce) return;
    history.replaceState(null, '', '#/pending');  // a reload or back doesn't jump again
    const card = document.querySelector(`.item-card[data-id="${match[1]}"]:not(.card-removing)`);
    if (!card) {
        showAlert('هذا الملف لم يعد في القائمة: أُكّد أو حُذف.', 'info', 8000);
        return;
    }
    card.querySelector('.card-summary[aria-expanded="false"]')?.click();
    card.scrollIntoView({block: 'start', behavior: reducedMotion.matches ? 'auto' : 'smooth'});
    card.focus({preventScroll: true});
    card.classList.remove('card-linked');
    void card.offsetWidth;  // restart the mark if the same link is opened twice
    card.classList.add('card-linked');
    setTimeout(() => card.classList.remove('card-linked'), 1600);
}

// Load pending items from API
async function loadPendingItems(options = {}) {
    const {showLoading = false, silent = false, smartUpdate = false} = options;
    const focusSnapshot = captureFocusSnapshot();

    try {
        const container = document.getElementById('pendingItems');
        if (showLoading && container) {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading';
            loadingDiv.textContent = 'جارٍ تحميل الملفات…';
            container.replaceChildren(loadingDiv);
        }

        const response = await fetch(`${API_BASE}/pending`);
        if (!response.ok) {
            throw await apiError(response, 'الخادم لم يُرجع القائمة.');
        }

        const freshItems = await response.json();

        if (smartUpdate) {
            smartUpdatePendingList(freshItems, focusSnapshot);
        } else {
            pendingItems = freshItems;
            pendingItems.forEach(item => {
                if (artistDraftValues.has(item.id)) {
                    item.current_artist = artistDraftValues.get(item.id);
                }
                if (titleDraftValues.has(item.id)) {
                    item.current_title = titleDraftValues.get(item.id);
                }
            });
            pendingItems.forEach(item => {
                if (item.genre && item.genre.trim()) {
                    selectedGenres[item.id] = item.genre.trim();
                }
            });
            renderItems({focusSnapshot});
        }

        if (!silent) {
            logEvent('info', `تم تحميل قائمة الانتظار (${pendingItems.length}) عنصر`);
        }
        return true;
    } catch (error) {
        logEvent('error', 'Loading the queue failed', {error: error.message});
        if (silent && error instanceof TypeError) {
            setConnectionOffline(true);  // a background poll while offline: the banner already says it
        } else {
            showError('تعذّر تحميل قائمة الانتظار', error);
        }
    }
}

// Cards that need the operator's attention go last, so a session starts with one-tap confirms
function needsReview(item) {
    return item.status === 'needs_manual' || item.status === 'error';
}

function sortQueue(items) {
    return items.slice().sort((a, b) => needsReview(a) - needsReview(b));  // stable: keeps server order within each group
}

// Surgically add/remove cards without touching existing ones
function smartUpdatePendingList(freshItems, focusSnapshot = null) {
    const container = document.getElementById('pendingItems');
    if (!container) return;

    const oldIds = new Set(pendingItems.map(i => i.id));
    const newIds = new Set(freshItems.map(i => i.id));

    // Apply draft values to fresh data
    freshItems.forEach(item => {
        if (artistDraftValues.has(item.id)) item.current_artist = artistDraftValues.get(item.id);
        if (titleDraftValues.has(item.id)) item.current_title = titleDraftValues.get(item.id);
        if (item.genre && item.genre.trim()) selectedGenres[item.id] = item.genre.trim();
    });

    pendingItems = sortQueue(freshItems);

    // Remove cards no longer in the list
    oldIds.forEach(id => {
        if (!newIds.has(id)) {
            removeItemCardFromDOM(id, container);
        }
    });

    // Add genuinely new cards at the top of their group: ready ones first, needs-review ones
    // above the older needs-review cards (createItemCard uses escapeHtml for all user data)
    // eslint-disable-next-line no-unsanitized/method
    freshItems.forEach(item => {
        if (!oldIds.has(item.id)) {
            const tmp = document.createElement('div');
            tmp.innerHTML = createItemCard(item); // createItemCard escapes all user-provided values
            const newCard = tmp.firstElementChild;
            newCard.classList.add('card-arriving');
            newCard.addEventListener('animationend', event => {
                if (event.animationName === 'card-arrive-mark') newCard.classList.remove('card-arriving');
            });
            if (needsReview(item)) {
                container.insertBefore(newCard, container.querySelector('.item-card.needs-review, .item-card.has-error'));
            } else {
                container.prepend(newCard);
            }
            attachItemListeners(item.id);
            updateConfirmButton(item.id);
        }
    });

    updatePendingCountUI();
    cleanupArtistState();

    if (focusSnapshot) {
        restoreFocusSnapshot(focusSnapshot);
    }
}

// Motion (DESIGN.md → Motion). The exit matches --dur-base in style.css; the timer, not
// animationend, removes the card, because a hidden page runs no animations.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const CARD_EXIT_MS = 200;
const CARD_SETTLE_MS = 240;
const EASE_OUT = 'cubic-bezier(0.16, 1, 0.3, 1)';

// Remove a card and slide the cards after it into the gap (FLIP: measure, remove, then
// animate each card from its old spot with a transform, so nothing re-lays out per frame)
function removeCardAndCloseGap(card) {
    const parent = card.parentNode;
    if (!parent) return;
    const after = [];
    for (let el = card.nextElementSibling; el; el = el.nextElementSibling) {
        if (!el.classList.contains('card-removing')) after.push(el);
    }
    const before = after.map(el => el.getBoundingClientRect());
    card.remove();
    if (!reducedMotion.matches) {
        after.forEach((el, i) => {
            const now = el.getBoundingClientRect();
            const dx = before[i].left - now.left;
            const dy = before[i].top - now.top;
            if (!dx && !dy) return;
            el.animate(
                [{transform: `translate(${dx}px, ${dy}px)`}, {transform: 'none'}],
                {duration: CARD_SETTLE_MS, easing: EASE_OUT}
            );
        });
    }
    updatePendingCountUI();
}

function nextQueueCard(card) {
    const live = el => el && !el.classList.contains('card-removing');
    let el = card.nextElementSibling;
    while (el && !live(el)) el = el.nextElementSibling;
    if (el) return el;
    el = card.previousElementSibling;
    while (el && !live(el)) el = el.previousElementSibling;
    return el;
}

// Remove a single item card from the DOM: it fades out, then the rest close the gap.
// Safe to call twice (the confirm response and its SSE event both land here).
function removeItemCardFromDOM(itemId, container) {
    const card = (container || document).querySelector(`.item-card[data-id="${itemId}"]`);
    if (card && !card.classList.contains('card-removing')) {
        card.classList.add('card-removing');
        setTimeout(() => {
            // Focus was on this card (or dropped to the page when its button disabled):
            // hand it to the card that takes its place, so a keyboard session carries on
            const focusHere = card.contains(document.activeElement) || document.activeElement === document.body;
            const next = nextQueueCard(card);
            removeCardAndCloseGap(card);
            if (focusHere && next) next.focus({preventScroll: true});
        }, CARD_EXIT_MS);
    }
    pendingItems = pendingItems.filter(i => i.id !== itemId);
    albumArtistChoice.delete(itemId);
    shownAlbumArtist.delete(itemId);
    cleanupArtistState();
    artistDraftValues.delete(itemId);
    titleDraftValues.delete(itemId);
    delete selectedGenres[itemId];
    delete customGenreVisible[itemId];
    expandedCards.delete(itemId);
    openedGenres.delete(itemId);
    updatePendingCountUI();
}

// The empty queue says what happened: nothing yet, or the files reviewed since the page loaded
// went to the library. `arriving` plays the one-time fade and check draw (the last card just left).
function showEmptyState({arriving = false} = {}) {
    const emptyState = document.getElementById('emptyState');
    if (!emptyState) return;
    const cleared = confirmedFolders.length > 0;
    emptyState.classList.toggle('is-cleared', cleared);
    document.getElementById('emptyTitle').textContent = cleared ? 'اكتملت المراجعة' : 'لا ملفات في الانتظار';
    document.getElementById('emptyText').textContent = cleared
        ? `نُقل ${arabicCount(confirmedFolders.length, FILE_FORMS)} إلى المكتبة منذ فتح الصفحة. تظهر الملفات الجديدة هنا تلقائيًا بعد تنزيلها.`
        : 'تظهر الملفات الجديدة هنا تلقائيًا بعد تنزيلها.';
    document.getElementById('emptyLibraryLink').hidden = !cleared;
    if (arriving && !emptyState.classList.contains('show')) {
        emptyState.classList.add('is-arriving');
        setTimeout(() => emptyState.classList.remove('is-arriving'), 600);
    }
    emptyState.classList.add('show');
}

// Update badge, count, and empty-state without touching item cards
function updatePendingCountUI() {
    const badge = document.getElementById('pendingBadge');
    const itemCount = document.getElementById('itemCount');
    const emptyState = document.getElementById('emptyState');
    const container = document.getElementById('pendingItems');

    if (badge) {
        if (pendingItems.length > 0) {
            badge.textContent = pendingItems.length;
            badge.setAttribute('aria-label', `${arabicCount(pendingItems.length, FILE_FORMS)} في الانتظار`);
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }
    if (pendingItems.length === 0) {
        if (itemCount) itemCount.textContent = 'فارغة';
        // The last card is still leaving: the empty state appears once it is gone
        if (!container?.querySelector('.card-removing')) {
            if (container) container.replaceChildren();
            showEmptyState({arriving: true});
        }
    } else {
        if (emptyState) emptyState.classList.remove('show');
        if (itemCount) itemCount.textContent = arabicCount(pendingItems.length, FILE_FORMS);
    }
    updateConfirmAllButton();
}

// Render all items
function renderItems(options = {}) {
    const {focusSnapshot = null} = options;
    const container = document.getElementById('pendingItems');
    const emptyState = document.getElementById('emptyState');
    const itemCount = document.getElementById('itemCount');
    const badge = document.getElementById('pendingBadge');
    cleanupArtistState();
    
    // Update Badge
    if (badge) {
        if (pendingItems.length > 0) {
            badge.textContent = pendingItems.length;
            badge.setAttribute('aria-label', `${arabicCount(pendingItems.length, FILE_FORMS)} في الانتظار`);
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }
    
    if (pendingItems.length === 0) {
        container.innerHTML = '';
        showEmptyState();
        itemCount.textContent = 'فارغة';
        updateConfirmAllButton();
        return;
    }
    
    emptyState.classList.remove('show');
    itemCount.textContent = arabicCount(pendingItems.length, FILE_FORMS);

    pendingItems = sortQueue(pendingItems);
    container.innerHTML = pendingItems.map(item => createItemCard(item)).join('');
    
    // Attach event listeners
    pendingItems.forEach(item => {
        attachItemListeners(item.id);
        updateConfirmButton(item.id);
    });

    if (focusSnapshot) {
        restoreFocusSnapshot(focusSnapshot);
    }
}

// The artist rows of one card. Row ids carry the index, so the rows are rebuilt together.
function renderArtistRowsHtml(itemId, artistList) {
    return artistList.map((artist, index) => `
        <div class="artist-row" data-item-id="${itemId}" data-row-index="${index}">
            <div class="artist-combobox" data-row-id="${itemId}_artist_${index}">
                <input
                    type="text"
                    class="field-input artist-input"
                    value="${escapeHtml(artist)}"
                    data-row-id="${itemId}_artist_${index}"
                    data-item-id="${itemId}"
                    data-combobox-input="true"
                    placeholder="الفنان (مطلوب)"
                    autocomplete="off"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded="false"
                    aria-haspopup="listbox"
                    aria-controls="artist-suggestions-${itemId}-${index}"
                >
                <button type="button" class="artist-dropdown-toggle" data-row-id="${itemId}_artist_${index}" aria-label="اقتراحات الفنان">
                    <span class="artist-dropdown-icon">▾</span>
                </button>
                <div class="artist-suggestions" id="artist-suggestions-${itemId}-${index}" role="listbox"></div>
            </div>
            ${artistList.length > 1 ? `<button type="button" class="btn-remove-artist" data-item-id="${itemId}" data-row-index="${index}" aria-label="إزالة فنان">×</button>` : ''}
        </div>
    `).join('');
}

// Artist inputs and their remove buttons (they are rebuilt on add/remove, the card is not)
function attachArtistRowListeners(itemId, card) {
    card.querySelectorAll('.artist-input').forEach(input => {
        setupArtistInput(input.dataset.rowId, input, card);
    });
    card.querySelectorAll('.btn-remove-artist').forEach(btn => {
        btn.addEventListener('click', () => removeArtistRow(itemId, parseInt(btn.dataset.rowIndex, 10)));
    });
}

// Create item card HTML
function createItemCard(item) {
    const hasError = item.status === 'error';
    const isManual = item.status === 'needs_manual';
    const artworkUrl = item.artwork_url || null;
    const currentGenre = (item.genre || '').trim();
    const isCustomGenre = currentGenre && !GENRE_PRESETS.includes(currentGenre);
    const titleValue = item.current_title || item.inferred_title || '';
    const hasArtistDraft = artistDraftValues.has(item.id);
    const artistValue = hasArtistDraft ? artistDraftValues.get(item.id) : (item.current_artist || item.inferred_artist || '');
    const artistList = artistValue.split(';').map(a => a.trim());
    if (artistList.length === 0 || artistList.every(a => a === '')) {
        artistList.length = 0;
        artistList.push('');
    }
    artistRowsMap.set(item.id, artistList);

    const artistRowsHtml = renderArtistRowsHtml(item.id, artistList);

    const problem = (hasError || isManual) ? describeItemProblem(item) : null;
    // Needs-review cards mark each required field beside its label; updateConfirmButton keeps them current
    const fieldCheck = key => isManual
        ? `<span class="field-check" data-check="${key}">${FIELD_CHECK_TEXT[key][0]}</span>`
        : '';
    const suggestion = suggestedGenre(item);
    const orderedGenres = suggestion.genre
        ? [suggestion.genre, ...GENRE_PRESETS.filter(g => g !== suggestion.genre)]
        : GENRE_PRESETS;

    // A complete suggestion collapses to a summary on phones: read it, confirm it, or open it to edit
    const artistNames = artistList.filter(Boolean);
    const collapsible = item.status === 'pending' && Boolean(titleValue.trim()) && artistNames.length > 0 && Boolean(currentGenre);
    const collapsed = collapsible && !expandedCards.has(item.id);
    // A genre decided before review (from the file) folds to one line on needs-review cards;
    // title and artists stay open, since the banner asks the operator to check them
    const genreFolded = isManual && Boolean(currentGenre) && !openedGenres.has(item.id);
    const technical = `
                <details class="alert-technical source-details">
                    <summary>التفاصيل التقنية</summary>
                    <dl class="source-list">${formatItemSource(item)}</dl>
                    ${item.error_message ? `<code dir="ltr">${escapeHtml(item.error_message)}</code>` : ''}
                </details>`;
    // With no artwork, the header row would hold only a placeholder; the fold joins the banner
    const technicalInProblem = Boolean(problem) && !artworkUrl;

    return `
        <div class="item-card ${isManual ? 'needs-review' : ''} ${hasError ? 'has-error' : ''} ${collapsed ? 'is-collapsed' : ''}" data-id="${item.id}" tabindex="-1">
            ${collapsible ? `
            <button type="button" class="card-summary" aria-expanded="${!collapsed}">
                <span class="card-summary-title">${escapeHtml(titleValue)}</span>
                <span class="card-summary-edit">تعديل</span>
                <span class="card-summary-meta">${artistNames.map(a => `<bdi>${escapeHtml(a)}</bdi>`).join('، ')} · ${escapeHtml(currentGenre)}</span>
                <span class="card-summary-path" id="summary-path-${item.id}"></span>
            </button>` : ''}
            ${problem ? `
            <div class="item-problem ${hasError ? 'error' : 'warn'}" role="note">
                <strong>${hasError ? 'تعذّرت معالجة هذا الملف' : 'يحتاج مراجعة'}</strong>
                <p>${escapeHtml(problem.text)}</p>
                ${technicalInProblem ? technical : ''}
            </div>` : ''}

            ${technicalInProblem ? '' : `
            <div class="item-header">
                ${artworkUrl
                    ? `<img src="${artworkUrl}" alt="" class="artwork">`
                    : '<div class="artwork-placeholder" aria-hidden="true">♪</div>'
                }
                ${technical}
            </div>`}

            <section class="card-group card-group-identity" aria-label="العنوان والفنانون">
                <div class="field-group">
                    <div class="field-head">
                        <label class="field-label" for="title-${item.id}">العنوان</label>
                        ${fieldCheck('title')}
                    </div>
                    <textarea
                        id="title-${item.id}"
                        class="field-input title-input"
                        rows="1"
                        data-id="${item.id}"
                        placeholder="العنوان (مطلوب)"
                    >${escapeHtml(titleValue)}</textarea>
                </div>

                <div class="field-group">
                    <div class="field-head">
                        <span class="field-label" id="artists-label-${item.id}">الفنانون</span>
                        ${fieldCheck('artist')}
                        <button type="button" class="btn-add-artist" data-id="${item.id}">+ إضافة فنان</button>
                    </div>
                    <div class="multi-artist-list" data-id="${item.id}" role="group" aria-labelledby="artists-label-${item.id}">
                        ${artistRowsHtml}
                    </div>
                    <p class="artist-hint" aria-live="polite"></p>
                </div>
            </section>

            <section class="card-group card-group-destination" aria-labelledby="destination-label-${item.id}">
                <h3 class="field-label group-label" id="destination-label-${item.id}">الوجهة</h3>
                <div class="destination-preview" id="destination-${item.id}" aria-live="polite"></div>
                <p class="destination-pending">يظهر المجلد والمسار بعد كتابة العنوان والفنان.</p>
            </section>

            <section class="card-group genre-section ${genreFolded ? 'is-folded' : ''}" aria-labelledby="genre-label-${item.id}">
                <div class="field-head">
                    <h3 class="field-label group-label" id="genre-label-${item.id}">النوع</h3>
                    ${genreFolded ? `<span class="genre-current">${escapeHtml(currentGenre)}</span>` : ''}
                    ${fieldCheck('genre')}
                    ${genreFolded ? `<button type="button" class="genre-change" aria-expanded="false" aria-controls="genre-buttons-${item.id}">تغيير</button>` : ''}
                </div>
                <div class="genre-buttons" id="genre-buttons-${item.id}" role="group" aria-labelledby="genre-label-${item.id}">
                    ${orderedGenres.map(genre => `
                        <button type="button" class="genre-btn ${currentGenre === genre ? 'selected' : ''}" data-id="${item.id}" data-genre="${genre}" aria-pressed="${currentGenre === genre}">
                            ${genre}${genre === suggestion.genre ? `<small class="genre-hint">${suggestion.reason}</small>` : ''}
                        </button>
                    `).join('')}
                    <button type="button" class="genre-btn ${isCustomGenre ? 'selected' : ''}" data-id="${item.id}" data-genre="custom" aria-pressed="${Boolean(isCustomGenre)}">
                        أخرى…
                    </button>
                </div>
                <div class="custom-genre-wrapper">
                    <input
                        type="text"
                        class="custom-genre-input ${isCustomGenre ? 'show' : ''}"
                        placeholder="أدخل النوع الموسيقي"
                        aria-label="نوع آخر"
                        value="${isCustomGenre ? escapeHtml(currentGenre) : ''}"
                        data-id="${item.id}"
                    >
                </div>
            </section>

            <div class="action-buttons">
                ${debugEnabled ? `
                <button class="btn-secondary dry-run-btn" data-id="${item.id}">
                    معاينة دون كتابة
                </button>
                ` : ''}
                <button class="confirm-btn" data-id="${item.id}" aria-disabled="true">${CONFIRM_LABEL}</button>
                <div class="item-status" id="itemStatus-${item.id}"></div>
                <button type="button" class="btn-secondary btn-danger-quiet delete-btn" data-id="${item.id}">حذف الملف</button>
            </div>
        </div>
    `;
}

// Why a card needs review, from the scanner's error_message (English, internal)
const ITEM_PROBLEMS = [
    ['Failed to parse filename', 'اسم الملف لا يحمل اسم القناة، فلم يُقترح فنان. العنوان مأخوذ من اسم الملف.'],
    ['Metadata detection failed', 'لم يكتمل الاقتراح الآلي، فالعنوان والفنان مأخوذان من عنوان الفيديو واسم القناة. راجعهما.'],
    ['Failed to apply metadata tags', 'تعذّرت كتابة الوسوم في النسخة المؤقتة. راجع الحقول ثم أكّد؛ وإن تكرر الخطأ فالملف نفسه قد يكون تالفًا.'],
    ['Interrupted while moving', 'انقطع النقل قبل اكتماله. أكّد مجددًا لإعادة المحاولة.'],
    ['Processing error', 'حدث خطأ أثناء تجهيز الملف. يمكنك إكمال الحقول وتأكيده، أو حذفه.'],
];

function describeItemProblem(item) {
    const raw = String(item.error_message || '');
    const match = ITEM_PROBLEMS.find(([prefix]) => raw.startsWith(prefix));
    return {text: match ? match[1] : 'أكمل الحقول الناقصة قبل التأكيد.'};
}

// "Unknown" is the scanner's placeholder when the filename had no "###channel" part.
// The source (and the scanner's raw error, if any) is reference, so it stays folded.
function formatItemSource(item) {
    const unknownChannel = !item.channel || item.channel === 'Unknown';
    return `
        <div><dt>${unknownChannel ? 'اسم الملف' : 'عنوان الفيديو'}</dt><dd><bdi>${escapeHtml(item.video_title)}</bdi></dd></div>
        <div><dt>القناة</dt><dd>${unknownChannel ? 'غير معروفة' : `<bdi>${escapeHtml(item.channel)}</bdi>`}</dd></div>
    `;
}

function getItemIdFromRowId(rowId) {
    // rowId format: itemId_artist_index
    const parts = String(rowId).split('_artist_');
    return Number(parts[0]);
}

function rebuildArtistValue(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return '';
    const inputs = card.querySelectorAll('.artist-input');
    const values = [];
    inputs.forEach(input => {
        const v = input.value.trim();
        if (v) values.push(v);
    });
    const joined = values.join('; ');
    const item = pendingItems.find(entry => entry.id === itemId);
    if (item) {
        item.current_artist = joined;
    }
    artistDraftValues.set(itemId, joined);
    return joined;
}

// Rows as the user sees them right now (the DOM is the truth while they type)
function readArtistRows(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const rows = card ? Array.from(card.querySelectorAll('.artist-input'), input => input.value) : [];
    return rows.length ? rows : (artistRowsMap.get(itemId) || ['']);
}

// Rebuild only the artist rows of a card. Replacing the whole card used to drop the status
// line, the destination preview and a typed custom genre, and left confirm disabled.
function renderArtistRows(itemId, rows, focusIndex = null) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const list = card?.querySelector('.multi-artist-list');
    if (!list) return;
    artistRowsMap.set(itemId, rows);
    const joined = rows.join('; ');
    const item = pendingItems.find(entry => entry.id === itemId);
    if (item) item.current_artist = joined;
    artistDraftValues.set(itemId, joined);

    // Row ids shift with the indexes: drop the old rows' combobox state with them
    list.querySelectorAll('.artist-input').forEach(input => {
        const state = artistComboboxState.get(input.dataset.rowId);
        if (state) clearTimeout(state.debounceTimer);
        artistComboboxState.delete(input.dataset.rowId);
    });
    // renderArtistRowsHtml escapes every artist value
    // eslint-disable-next-line no-unsanitized/property
    list.innerHTML = renderArtistRowsHtml(itemId, rows);
    attachArtistRowListeners(itemId, card);
    updateConfirmButton(itemId);
    if (focusIndex !== null) list.querySelectorAll('.artist-input')[focusIndex]?.focus();
}

function addArtistRow(itemId) {
    const rows = readArtistRows(itemId);
    rows.push('');
    renderArtistRows(itemId, rows, rows.length - 1);
}

function removeArtistRow(itemId, rowIndex) {
    const rows = readArtistRows(itemId);
    if (rows.length <= 1) return;
    rows.splice(rowIndex, 1);
    renderArtistRows(itemId, rows, Math.min(rowIndex, rows.length - 1));
    updateField(itemId, 'artist', rows.map(r => r.trim()).filter(Boolean).join('; '));
}

async function fetchArtistSuggestions(query, limit = ARTIST_SUGGEST_LIMIT) {
    const trimmedQuery = String(query || '').trim();
    const cacheKey = `${trimmedQuery}|${limit}`;
    const now = Date.now();
    const cached = artistSuggestCache.get(cacheKey);
    if (cached && (now - cached.timestamp) < ARTIST_SUGGEST_CACHE_TTL_MS) {
        return cached.data;
    }

    const params = new URLSearchParams();
    params.set('q', trimmedQuery);
    params.set('limit', String(limit));
    const response = await fetch(`${API_BASE}/artists/suggest?${params.toString()}`);
    if (!response.ok) {
        throw await apiError(response, 'تعذّر جلب اقتراحات الفنان.');
    }

    const data = await response.json();
    artistSuggestCache.set(cacheKey, {timestamp: now, data});
    return data;
}

function getArtistOptionList(itemId, currentInputValue) {
    const state = getArtistState(itemId);
    const options = (state.suggestions || []).map(suggestion => ({
        type: 'existing',
        id: suggestion.id,
        name: suggestion.name,
        score: Number(suggestion.score || 0)
    }));

    const trimmedInput = String(currentInputValue || '').trim();
    if (state.canCreate && trimmedInput.length > 0) {
        const normalizedInput = normalizeArtistClient(trimmedInput);
        const hasEquivalent = options.some(option => normalizeArtistClient(option.name) === normalizedInput);
        if (!hasEquivalent) {
            options.push({
                type: 'create',
                id: null,
                name: trimmedInput,
                score: 0
            });
        }
    }

    return options;
}

function renderArtistSuggestions(rowId) {
    const input = document.querySelector(`.artist-input[data-row-id="${rowId}"]`);
    const suggestionsEl = document.getElementById(`artist-suggestions-${rowId.replace('_artist_', '-')}`);
    const toggleBtn = document.querySelector(`.artist-dropdown-toggle[data-row-id="${rowId}"]`);
    if (!input || !suggestionsEl || !toggleBtn) return;

    const state = getArtistState(rowId);
    const options = getArtistOptionList(rowId, input.value);

    if (!state.isOpen) {
        suggestionsEl.classList.remove('show');
        suggestionsEl.innerHTML = '';
        input.setAttribute('aria-expanded', 'false');
        toggleBtn.classList.remove('open');
        return;
    }

    suggestionsEl.classList.add('show');
    input.setAttribute('aria-expanded', 'true');
    toggleBtn.classList.add('open');

    if (state.isLoading) {
        suggestionsEl.innerHTML = '<div class="artist-suggestion-empty">جارٍ البحث…</div>';
        return;
    }

    if (options.length === 0) {
        suggestionsEl.innerHTML = '<div class="artist-suggestion-empty">لا يوجد اسم مشابه في المكتبة</div>';
        return;
    }

    if (state.highlightedIndex < 0 || state.highlightedIndex >= options.length) {
        state.highlightedIndex = 0;
    }

    suggestionsEl.innerHTML = options.map((option, index) => `
        <div
            class="artist-suggestion-item ${index === state.highlightedIndex ? 'active' : ''} ${option.type === 'create' ? 'create-option' : ''}"
            role="option"
            aria-selected="${index === state.highlightedIndex}"
            data-index="${index}"
        >
            <span class="artist-suggestion-name">
                ${option.type === 'create' ? `اسم جديد غير موجود في المكتبة: ${escapeHtml(option.name)}` : escapeHtml(option.name)}
            </span>
            ${option.type === 'existing' ? formatArtistScore(option.score) : ''}
        </div>
    `).join('');

    suggestionsEl.querySelectorAll('.artist-suggestion-item').forEach(optionEl => {
        optionEl.addEventListener('mousedown', event => {
            // Keep focus on input while selecting with mouse.
            event.preventDefault();
        });
        optionEl.addEventListener('click', () => {
            const index = Number(optionEl.dataset.index);
            const selected = options[index];
            if (selected) {
                selectArtistOption(rowId, selected);
            }
        });
    });
}

// The score is how close a library name is to what was typed (0–100). With an empty query
// the list is "most used artists" and every score is 0, so nothing is shown.
function formatArtistScore(score) {
    const value = Math.round(Number(score) || 0);
    if (value <= 0) return '';
    const tone = value >= ARTIST_CREATE_THRESHOLD ? 'close' : 'far';
    return `<span class="artist-suggestion-score ${tone}" title="مدى تشابه هذا الاسم مع ما كتبته">تشابه <bdi>${value}٪</bdi></span>`;
}

function closeArtistDropdown(itemId) {
    // Closing must not create state: a removed row's delayed blur would bring it back
    const state = artistComboboxState.get(itemId);
    if (!state) return;
    state.isOpen = false;
    state.highlightedIndex = -1;
    renderArtistSuggestions(itemId);
}

function closeAllArtistDropdowns(exceptItemId = null) {
    for (const itemId of artistComboboxState.keys()) {
        if (exceptItemId !== null && itemId === exceptItemId) {
            continue;
        }
        closeArtistDropdown(itemId);
    }
}

async function requestArtistSuggestions(itemId, query) {
    const state = getArtistState(itemId);
    state.requestToken += 1;
    const currentToken = state.requestToken;
    state.isLoading = true;
    renderArtistSuggestions(itemId);

    try {
        const data = await fetchArtistSuggestions(query, ARTIST_SUGGEST_LIMIT);
        if (state.requestToken !== currentToken) {
            return;
        }

        state.suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
        state.canCreate = Boolean(data.canCreate);
        state.createSuggestion = data.createSuggestion || null;

        if (query && state.suggestions.length > 0 && Number(state.suggestions[0].score || 0) < ARTIST_CREATE_THRESHOLD) {
            state.canCreate = true;
        }

        state.highlightedIndex = state.suggestions.length > 0 ? 0 : -1;
    } catch (error) {
        logEvent('warn', 'Artist suggestion lookup failed', {itemId, error: error.message});
        state.suggestions = [];
        state.canCreate = false;
        state.createSuggestion = null;
        state.highlightedIndex = -1;
    } finally {
        if (state.requestToken === currentToken) {
            state.isLoading = false;
            renderArtistSuggestions(itemId);
        }
    }
}

function queueArtistSuggestions(itemId, query) {
    const state = getArtistState(itemId);
    clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(() => {
        requestArtistSuggestions(itemId, query);
    }, ARTIST_SUGGEST_DEBOUNCE_MS);
}

function openArtistDropdown(rowId) {
    const state = getArtistState(rowId);
    const input = document.querySelector(`.artist-input[data-row-id="${rowId}"]`);
    if (!input) return;

    closeAllArtistDropdowns(rowId);
    state.isOpen = true;
    renderArtistSuggestions(rowId);
    queueArtistSuggestions(rowId, input.value);
}

function navigateArtistSuggestions(rowId, direction) {
    const state = getArtistState(rowId);
    const input = document.querySelector(`.artist-input[data-row-id="${rowId}"]`);
    if (!input) return;

    const options = getArtistOptionList(rowId, input.value);
    if (options.length === 0) return;

    if (state.highlightedIndex < 0) {
        state.highlightedIndex = 0;
    } else {
        state.highlightedIndex = (state.highlightedIndex + direction + options.length) % options.length;
    }

    renderArtistSuggestions(rowId);
}

function selectArtistOption(rowId, option) {
    const input = document.querySelector(`.artist-input[data-row-id="${rowId}"]`);
    if (!input || !option) return;

    const itemId = getItemIdFromRowId(rowId);
    input.value = option.name;
    const state = getArtistState(rowId);
    if (option.type === 'existing') {
        state.createArtistOnSave = false;
        state.selectedExistingName = option.name;
        setItemStatus(itemId, 'اخترت اسمًا موجودًا في المكتبة.', 'success');
    } else {
        state.createArtistOnSave = true;
        state.selectedExistingName = null;
        setItemStatus(itemId, 'سيظهر هذا الفنان في المكتبة لأول مرة بعد التأكيد.', 'info');
    }

    const joined = rebuildArtistValue(itemId);
    const item = pendingItems.find(entry => entry.id === itemId);
    if (item) {
        item.create_artist_on_save = state.createArtistOnSave;
        item.selected_existing_artist = state.selectedExistingName;
    }

    closeArtistDropdown(rowId);
    updateConfirmButton(itemId);
    updateField(itemId, 'artist', joined);
}

function handleArtistInputKeydown(rowId, event) {
    const state = getArtistState(rowId);
    const input = document.querySelector(`.artist-input[data-row-id="${rowId}"]`);
    if (!input) return;

    const options = getArtistOptionList(rowId, input.value);

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!state.isOpen) {
            openArtistDropdown(rowId);
            return;
        }
        navigateArtistSuggestions(rowId, 1);
        return;
    }

    if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!state.isOpen) {
            openArtistDropdown(rowId);
            return;
        }
        navigateArtistSuggestions(rowId, -1);
        return;
    }

    if ((event.key === 'Enter' || event.key === 'Tab') && state.isOpen && options.length > 0) {
        const optionIndex = state.highlightedIndex >= 0 ? state.highlightedIndex : 0;
        const option = options[optionIndex];
        if (option) {
            event.preventDefault();
            selectArtistOption(rowId, option);
        }
        return;
    }

    if (event.key === 'Escape' && state.isOpen) {
        event.preventDefault();
        closeArtistDropdown(rowId);
    }
}

function setupArtistInput(rowId, artistInput, card) {
    if (!artistInput || !card) return;

    const itemId = getItemIdFromRowId(rowId);
    const toggleBtn = card.querySelector(`.artist-dropdown-toggle[data-row-id="${rowId}"]`);
    const state = getArtistState(rowId);

    artistInput.addEventListener('focus', () => {
        openArtistDropdown(rowId);
    });

    artistInput.addEventListener('click', () => {
        openArtistDropdown(rowId);
    });

    artistInput.addEventListener('input', () => {
        rebuildArtistValue(itemId);
        state.selectedExistingName = null;
        state.createArtistOnSave = false;
        updateConfirmButton(itemId);
        queueArtistSuggestions(rowId, artistInput.value);
    });

    artistInput.addEventListener('keydown', (event) => {
        handleArtistInputKeydown(rowId, event);
    });

    artistInput.addEventListener('blur', () => {
        rebuildArtistValue(itemId);
        const joined = artistDraftValues.get(itemId) || '';
        updateField(itemId, 'artist', joined);
        setTimeout(() => {
            closeArtistDropdown(rowId);
        }, 120);
    });

    if (toggleBtn) {
        toggleBtn.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            if (state.isOpen) {
                closeArtistDropdown(rowId);
            } else {
                openArtistDropdown(rowId);
            }
        });
    }
}

// Attach event listeners for an item
function attachItemListeners(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    const item = pendingItems.find(p => p.id === itemId);
    
    // Title input listener
    const titleInput = card.querySelector('.title-input');

    const summary = card.querySelector('.card-summary');
    if (summary) {
        summary.addEventListener('click', () => {
            expandedCards.add(itemId);
            card.classList.remove('is-collapsed');
            card.classList.add('card-expanding');
            setTimeout(() => card.classList.remove('card-expanding'), CARD_SETTLE_MS);
            summary.setAttribute('aria-expanded', 'true');
            if (titleInput) autosizeTitle(titleInput);
            card.focus({preventScroll: true});  // the summary hides; keep focus on this card
        });
    }

    if (titleInput) {
        // A title is one line of metadata: Enter must not add a newline, and the box grows to show it all
        autosizeTitle(titleInput);
        titleInput.addEventListener('keydown', event => {
            if (event.key === 'Enter') event.preventDefault();
        });
        titleInput.addEventListener('input', () => {
            if (titleInput.value.includes('\n')) titleInput.value = titleInput.value.replace(/\s*\n\s*/g, ' ');
            autosizeTitle(titleInput);
            titleDraftValues.set(itemId, titleInput.value);
            const item = pendingItems.find(entry => entry.id === itemId);
            if (item) {
                item.current_title = titleInput.value;
            }
            updateConfirmButton(itemId);
        });
        titleInput.addEventListener('blur', () => updateField(itemId, 'title', titleInput.value));
    }

    attachArtistRowListeners(itemId, card);

    // Add artist button
    const addArtistBtn = card.querySelector('.btn-add-artist');
    if (addArtistBtn) {
        addArtistBtn.addEventListener('click', () => addArtistRow(itemId));
    }

    // A folded genre opens in place, focused on the chosen genre
    card.querySelector('.genre-change')?.addEventListener('click', () => openGenreFold(itemId));

    // Genre button listeners
    const genreButtons = card.querySelectorAll('.genre-btn');
    genreButtons.forEach(btn => {
        btn.addEventListener('click', () => handleGenreClick(itemId, btn.dataset.genre, {offer: true}));
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
            renderChannelGenreOffer(itemId);
        });
    }
    
    // Confirm button
    const confirmBtn = card.querySelector('.confirm-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            if (confirmBtn.getAttribute('aria-disabled') === 'true') focusFirstMissing(itemId);
            else confirmItem(itemId);
        });
    }

    const deleteBtn = card.querySelector('.delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => deleteItem(itemId));
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

function autosizeTitle(textarea) {
    if (!textarea.offsetParent) return;  // hidden page: measured again when the queue is shown
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight + 2}px`;
}

// Handle genre button click. offer: the operator picked it here, so offer it to the channel.
function handleGenreClick(itemId, genre, {offer = false} = {}) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    
    // Update button states
    const buttons = card.querySelectorAll('.genre-btn');
    buttons.forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.genre === genre);
        btn.setAttribute('aria-pressed', String(btn.dataset.genre === genre));
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
    if (offer) renderChannelGenreOffer(itemId);
}

// One channel usually means one genre. Picking a genre offers it to the other cards from the
// same channel that have none yet: one tap selects it there too (and saves it as a draft on
// each card, like a tap would). Nothing is confirmed, and a genre already chosen is never replaced.
const CARD_FORMS_OTHER = ['بطاقة واحدة أخرى', 'بطاقتين أخريين', 'بطاقات أخرى', 'بطاقة أخرى', 'بطاقة أخرى'];  // after «على» / «في»

function channelCardsWithoutGenre(itemId) {
    const channel = pendingItems.find(i => i.id === itemId)?.channel;
    if (!channel || channel === 'Unknown') return [];
    return pendingItems
        .filter(other => other.id !== itemId && other.channel === channel && !(selectedGenres[other.id] || '').trim())
        .map(other => other.id)
        .filter(id => document.querySelector(`.item-card[data-id="${id}"]:not(.card-removing)`));
}

function renderChannelGenreOffer(itemId) {
    const section = document.querySelector(`.item-card[data-id="${itemId}"] .genre-section`);
    if (!section) return;
    section.querySelector('.channel-genre-offer, .channel-genre-done')?.remove();
    const genre = (selectedGenres[itemId] || '').trim();
    const others = genre ? channelCardsWithoutGenre(itemId) : [];
    if (others.length === 0) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'channel-genre-offer';
    btn.textContent = `طبّق «${genre}» على ${arabicCount(others.length, CARD_FORMS_OTHER)} من القناة`;
    btn.addEventListener('click', () => applyGenreToChannel(itemId, genre));
    section.appendChild(btn);
}

function applyGenreToChannel(itemId, genre) {
    const others = channelCardsWithoutGenre(itemId);  // counted again: some may have been filled meanwhile
    others.forEach(id => {
        if (GENRE_PRESETS.includes(genre)) {
            handleGenreClick(id, genre);
            return;
        }
        const customInput = document.querySelector(`.item-card[data-id="${id}"] .custom-genre-input`);
        if (customInput) customInput.value = genre;
        handleGenreClick(id, 'custom');
    });
    const section = document.querySelector(`.item-card[data-id="${itemId}"] .genre-section`);
    const offer = section?.querySelector('.channel-genre-offer');
    if (!offer) return;
    const done = document.createElement('p');
    done.className = 'channel-genre-done';
    done.setAttribute('role', 'status');
    done.textContent = others.length
        ? `اختير «${genre}» في ${arabicCount(others.length, CARD_FORMS_OTHER)} من القناة.`
        : 'لم تبقَ بطاقات من القناة بلا نوع.';
    offer.replaceWith(done);
    section.querySelector('.genre-btn.selected, .custom-genre-input.show')?.focus();  // the button left; focus stays in the group
    setTimeout(() => done.remove(), 6000);
}

// Update confirm button state
function updateConfirmButton(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;

    const confirmBtn = card.querySelector('.confirm-btn');
    const titleInput = card.querySelector('.title-input');
    const artistInputs = card.querySelectorAll('.artist-input');

    if (!confirmBtn || !titleInput || artistInputs.length === 0) return;

    const present = {
        title: titleInput.value.trim().length > 0,
        artist: Array.from(artistInputs).some(input => input.value.trim().length > 0),
        genre: Boolean(selectedGenres[itemId] && selectedGenres[itemId].trim().length > 0),
    };
    const missing = Object.keys(MISSING_FIELD_ACTIONS).filter(key => !present[key]);

    // Waiting is aria-disabled, not disabled: a tap still lands and leads to the missing field
    confirmBtn.setAttribute('aria-disabled', String(missing.length > 0));
    confirmBtn.dataset.missing = missing.join(' ');
    // A failed attempt keeps its "retry" look until the card stops being confirmable
    if (missing.length > 0) confirmBtn.classList.remove('is-failed');
    // A disabled confirm says what it is waiting for ("أضف فنانًا واختر النوع")
    if (!confirmBtn.dataset.busy && !confirmBtn.classList.contains('is-failed')) {
        confirmBtn.textContent = missing.length
            ? missing.map(key => MISSING_FIELD_ACTIONS[key]).join(' و')
            : CONFIRM_LABEL;
    }
    card.querySelectorAll('.field-check[data-check]').forEach(chip => {
        const done = present[chip.dataset.check];
        chip.classList.toggle('done', done);
        chip.textContent = FIELD_CHECK_TEXT[chip.dataset.check][done ? 1 : 0];
    });

    // Many artists usually means the suggestion split one name (or a title) into several
    const artistCount = Array.from(artistInputs).filter(input => input.value.trim()).length;
    const artistHint = card.querySelector('.artist-hint');
    if (artistHint) {
        artistHint.textContent = artistCount >= 4
            ? `في هذه البطاقة ${artistCount} فنانين. تأكد أن الاقتراح لم يقسم اسمًا واحدًا إلى عدة أسماء.`
            : '';
    }
    updateConfirmAllButton();
    queueDestinationPreview(itemId);
}

function openGenreFold(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const section = card?.querySelector('.genre-section.is-folded');
    if (!section) return;
    openedGenres.add(itemId);
    section.classList.remove('is-folded');
    section.querySelectorAll('.genre-current, .genre-change').forEach(el => el.remove());
    (section.querySelector('.genre-btn.selected') || section.querySelector('.genre-btn'))?.focus();
}

// A waiting confirm is not a dead end: a tap takes the operator to the first missing field
function focusFirstMissing(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const first = (card?.querySelector('.confirm-btn')?.dataset.missing || '').split(' ')[0];
    if (first === 'genre') openGenreFold(itemId);
    const target = {
        title: () => card.querySelector('.title-input'),
        artist: () => Array.from(card.querySelectorAll('.artist-input')).find(input => !input.value.trim()),
        genre: () => card.querySelector('.genre-btn'),
    }[first]?.();
    if (!target) return;
    target.scrollIntoView({block: 'center', behavior: reducedMotion.matches ? 'auto' : 'smooth'});
    target.focus({preventScroll: true});
}

// Album artist (the folder) and destination: the server resolves them from the draft,
// so the card shows exactly what confirm will do.
const albumArtistChoice = new Map();      // itemId -> artist the user picked
const shownAlbumArtist = new Map();       // itemId -> album artist in the last preview
const destinationPreviewTimers = new Map();
const destinationPreviewSeq = new Map();

function draftArtists(itemId) {
    return rebuildArtistValue(itemId).split(';').map(a => a.trim()).filter(Boolean);
}

function queueDestinationPreview(itemId) {
    clearTimeout(destinationPreviewTimers.get(itemId));
    destinationPreviewTimers.set(itemId, setTimeout(() => refreshDestinationPreview(itemId), 350));
}

async function refreshDestinationPreview(itemId) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const el = document.getElementById(`destination-${itemId}`);
    if (!card || !el) return;

    const title = (card.querySelector('.title-input')?.value || '').trim();
    const artist = rebuildArtistValue(itemId);
    if (!title || !artist) {
        el.innerHTML = '';
        shownAlbumArtist.delete(itemId);
        return;
    }

    const params = new URLSearchParams({title, artist});
    const chosen = albumArtistChoice.get(itemId);
    if (chosen) params.set('album_artist', chosen);
    const seq = (destinationPreviewSeq.get(itemId) || 0) + 1;
    destinationPreviewSeq.set(itemId, seq);

    try {
        const response = await fetch(`${API_BASE}/pending/${itemId}/dry-run?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const dryRun = await response.json();
        if (destinationPreviewSeq.get(itemId) !== seq) return;  // a newer draft is on its way
        renderDestinationPreview(itemId, dryRun);
    } catch (error) {
        logEvent('warn', 'Destination preview failed', {itemId, error: error.message});
    }
}

// Arabic path segments read right-to-left; each is isolated and the extension kept as one LTR unit.
// The dot stays outside the extension's isolate so it sits between name and extension
// («mp3.العنوان»); inside it, the dot ended up on the far side («.mp3العنوان»).
// Folder and file on one line: the title folder in between repeats the file name, and the
// file name repeats the title above it, so its stem truncates while the extension stays
function formatLibraryPath(relativePath) {
    const parts = relativePath.split('/').filter(Boolean);
    if (!parts.length) return '';
    const file = parts[parts.length - 1];
    const dot = file.lastIndexOf('.');
    const stem = dot > 0 ? file.slice(0, dot) : file;
    const folder = parts.length > 1 ? `<bdi class="path-folder">${escapeHtml(parts[0])}</bdi><span class="path-sep">/</span>` : '';
    const ext = dot > 0 ? `<span>.</span><bdi dir="ltr">${escapeHtml(file.slice(dot + 1))}</bdi>` : '';
    return `<span class="path-line">${folder}<bdi class="path-stem">${escapeHtml(stem)}</bdi>${ext}</span>`;
}

function renderDestinationPreview(itemId, dryRun) {
    const el = document.getElementById(`destination-${itemId}`);
    if (!el) return;
    const albumArtist = dryRun.metadata_preview?.album_artist || '';
    const move = dryRun.move_preview || {};
    const artists = draftArtists(itemId);
    shownAlbumArtist.set(itemId, albumArtist);

    const folder = artists.length > 1
        ? `<select class="album-artist-select" aria-label="فنان المجلد">${artists.map(a =>
            `<option value="${escapeHtml(a)}" ${a === albumArtist ? 'selected' : ''}>${escapeHtml(a)}</option>`).join('')}</select>`
        : `<span class="visually-hidden">المجلد: </span><bdi>${escapeHtml(albumArtist)}</bdi>`;
    // The shelf label: the folder names the shelf, the file sits beneath it (full path on hover)
    const fileName = String(move.relative_path || '').split('/').pop();

    el.innerHTML = `
        <div class="shelf-label" title="${escapeHtml(move.destination_path || '')}">
            <div class="shelf-folder">${folder}</div>
            <div class="shelf-file">${formatLibraryPath(fileName)}</div>
        </div>
        ${move.destination_exists ? '<div class="destination-warning">يوجد ملف بهذا الاسم في المكتبة، وسيُطلب منك الاختيار عند التأكيد</div>' : ''}
    `;

    const summaryPath = document.getElementById(`summary-path-${itemId}`);
    if (summaryPath) summaryPath.innerHTML = formatLibraryPath(move.relative_path || '');

    const select = el.querySelector('.album-artist-select');
    if (select) {
        select.addEventListener('change', () => {
            albumArtistChoice.set(itemId, select.value);
            refreshDestinationPreview(itemId);
        });
    }
}

// A card on its way out still has its button for a moment; it is not "ready"
const CONFIRMABLE = '.confirm-btn:not(:disabled):not([aria-disabled="true"])';
const READY_CONFIRM_SELECTOR = `.item-card:not(.card-removing) ${CONFIRMABLE}`;

// Show/hide the "confirm all ready" button based on how many cards are ready
// (toolbar on wider screens, the sticky bar at the bottom on phones)
function updateConfirmAllButton() {
    const readyCount = document.querySelectorAll(READY_CONFIRM_SELECTOR).length;
    // The header count says how many are ready, in the same words as the phone's ready bar
    const itemCount = document.getElementById('itemCount');
    if (itemCount && pendingItems.length > 0) {
        itemCount.textContent = readyCount > 0
            ? `${readyCount} من ${pendingItems.length} جاهزة`
            : arabicCount(pendingItems.length, FILE_FORMS);
    }
    if (confirmAllRunning) return;
    const btn = document.getElementById('confirmAllReadyBtn');
    const bar = document.getElementById('readyBar');
    if (btn) {
        btn.hidden = readyCount < 2;
        btn.disabled = false;
        setConfirmAllIdle(btn, `✓ تأكيد ونقل الجاهزة (${readyCount})`, readyCount);
    }
    if (bar) {
        bar.hidden = readyCount < 2;
        document.getElementById('readyBarCount').textContent = `${readyCount} من ${pendingItems.length} جاهزة`;
        const barBtn = document.getElementById('readyBarConfirmBtn');
        barBtn.disabled = false;
        setConfirmAllIdle(barBtn, '✓ تأكيد ونقل الجاهزة', readyCount);
    }
}

// An armed confirm-all keeps its message while the ready count it named still holds.
// If the count changes (SSE, an edit), it disarms: a second tap must move what it said.
function setConfirmAllIdle(btn, idleText, readyCount) {
    if (btn.classList.contains('armed')) {
        if (Number(btn.dataset.armedCount) === readyCount) return;
        disarmTwoTap(btn);
    }
    btn.textContent = idleText;
}

// Confirm-all moves every ready file into the library, so it takes two taps;
// the first names how many files will move.
function onConfirmAllClick(event) {
    if (confirmAllRunning) return;
    const btn = event.currentTarget;
    const readyCount = document.querySelectorAll(READY_CONFIRM_SELECTOR).length;
    if (!armTwoTap(btn, `اضغط مجددًا لنقل ${arabicCount(readyCount, FILE_FORMS_GENITIVE)}`)) {
        btn.dataset.armedCount = readyCount;
        return;
    }
    confirmAllReady();
}

// Confirm all ready items sequentially
async function confirmAllReady() {
    confirmAllRunning = true;
    ['confirmAllReadyBtn', 'readyBarConfirmBtn'].forEach(id => {
        const btn = document.getElementById(id);
        if (!btn) return;
        btn.disabled = true;
        btn.textContent = 'جارٍ نقل الجاهزة…';
    });

    // Collect IDs of ready items at the moment the button is clicked
    const readyIds = Array.from(document.querySelectorAll(READY_CONFIRM_SELECTOR))
        .map(el => Number(el.dataset.id))
        .filter(Boolean);

    const firstConfirmed = confirmedFolders.length;
    let successCount = 0;
    let failCount = 0;

    for (const itemId of readyIds) {
        // Re-check: the item may have left meanwhile (SSE from another tab, a failed earlier pass)
        const stillExists = document.querySelector(`.item-card:not(.card-removing) ${CONFIRMABLE}[data-id="${itemId}"]`);
        if (!stillExists) continue;

        if (await confirmItem(itemId)) {
            successCount++;
        } else {
            failCount++;
        }
    }

    confirmAllRunning = false;

    const moved = `نُقل ${arabicCount(successCount, FILE_FORMS)}${describeFolders(confirmedFolders.slice(firstConfirmed))}`;
    if (failCount === 0) {
        showAlert(`${moved}.`, 'success', 8000);
    } else {
        showAlert(`${moved}، وبقي ${arabicCount(failCount, FILE_FORMS)} في القائمة بسبب خطأ.`, 'warn');
    }

    updateConfirmAllButton();
}

// Where a batch went: up to three folders by name, more as a count
function describeFolders(folders) {
    const names = [...new Set(folders.filter(Boolean))];
    if (!names.length) return ' إلى المكتبة';
    if (names.length > 3) return ` إلى ${arabicCount(names.length, FOLDER_FORMS_GENITIVE)} في المكتبة`;
    const quoted = names.map(name => `«${name}»`);
    const list = quoted.length === 1 ? quoted[0] : `${quoted.slice(0, -1).join('، ')} و${quoted.at(-1)}`;
    return names.length === 1 ? ` إلى مجلد ${list}` : ` إلى ${list}`;  // 2–3 folders: the names say it
}

// Update field via API
async function updateField(itemId, field, value) {
    const label = FIELD_LABELS[field] || field;
    setItemStatus(itemId, `جارٍ حفظ ${label}…`, 'saving');
    try {
        const payload = {};
        payload[field] = typeof value === 'string' ? value.trim() : value;
        
        const response = await fetch(`${API_BASE}/pending/${itemId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw await apiError(response, 'الخادم رفض التعديل.');
        }
        
        // Update local state
        const item = pendingItems.find(i => i.id === itemId);
        if (item) {
            if (field === 'title') item.current_title = payload[field];
            if (field === 'artist') item.current_artist = payload[field];
            if (field === 'genre') item.genre = payload[field];
        }

        if (field === 'artist') {
            artistDraftValues.delete(itemId);
        }
        if (field === 'title') {
            titleDraftValues.delete(itemId);
        }
        
        updateConfirmButton(itemId);
        setItemStatus(itemId, `حُفظ ${label}`, 'success', 3000);
        
    } catch (error) {
        logEvent('error', `Update ${field} failed`, {itemId, error: error.message});
        showError(`لم يُحفظ ${label}`, error);
        setItemStatus(itemId, `لم يُحفظ ${label}. عدّله مجددًا أو أكّد مباشرة.`, 'error');
    }
}

// fadeAfter (ms): routine confirmations clear themselves; errors and warnings stay
function setItemStatus(itemId, message, type = 'info', fadeAfter = 0) {
    const statusEl = document.getElementById(`itemStatus-${itemId}`);
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = `item-status ${type}`;
    if (fadeAfter > 0) {
        setTimeout(() => {
            if (statusEl.textContent === message) {
                statusEl.textContent = '';
                statusEl.className = 'item-status';
            }
        }, fadeAfter);
    }
}

async function fetchDryRun(itemId) {
    const response = await fetch(`${API_BASE}/pending/${itemId}/dry-run`);
    if (!response.ok) {
        throw await apiError(response, 'تعذّر إنشاء المعاينة.');
    }
    return response.json();
}

function formatDryRunMessage(dryRun) {
    const missing = dryRun.missing_fields?.length ? dryRun.missing_fields.join(', ') : 'لا يوجد';
    const move = dryRun.move_preview || {};
    const meta = dryRun.metadata_preview || {};
    return [
        'معاينة العملية (لا شيء يُكتب):',
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
    if (!debugEnabled) {
        return;
    }

    const btn = document.querySelector(`.dry-run-btn[data-id="${itemId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'جارٍ إنشاء المعاينة…';
    }

    try {
        const dryRun = await fetchDryRun(itemId);
        const message = formatDryRunMessage(dryRun);
        logEvent('info', 'Dry-run preview generated', {itemId, dryRun});
        // Shown in the card, not a native alert(): it stays readable next to the fields it describes
        const statusEl = document.getElementById(`itemStatus-${itemId}`);
        if (statusEl) {
            statusEl.className = `item-status ${dryRun.can_confirm ? 'success' : 'warn'}`;
            const pre = document.createElement('pre');
            pre.className = 'dry-run-output';
            pre.textContent = message;
            statusEl.replaceChildren(pre);
        }
    } catch (error) {
        logEvent('error', 'Dry-run preview failed', {itemId, error: error.message});
        showError('تعذّر إنشاء المعاينة', error);
        setItemStatus(itemId, 'فشل إنشاء المعاينة', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'معاينة دون كتابة';
        }
    }
}

// Confirm item
async function confirmItem(itemId, onConflict) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    const confirmBtn = document.querySelector(`.confirm-btn[data-id="${itemId}"]`);
    if (!card || !confirmBtn) return false;
    
    const title = (card.querySelector('.title-input')?.value || '').trim();
    const artist = rebuildArtistValue(itemId);  // all artist rows, joined
    const genre = (selectedGenres[itemId] || '').trim();
    const shown = shownAlbumArtist.get(itemId);
    const albumArtist = shown && draftArtists(itemId).includes(shown) ? shown : null;

    if (!title || !artist || !genre) {
        setItemStatus(itemId, 'أكمل العنوان والفنان والنوع أولًا.', 'warn');
        return false;
    }
    
    // Disable button
    confirmBtn.disabled = true;
    confirmBtn.dataset.busy = '1';
    confirmBtn.classList.remove('is-failed');
    confirmBtn.classList.add('is-saving');
    confirmBtn.textContent = 'جارٍ الحفظ والنقل…';
    setItemStatus(itemId, 'تُكتب البيانات الوصفية ثم يُنقل الملف…', 'info');

    try {
        // Send exactly what the user sees; the server saves it and confirms in one step
        const response = await fetch(`${API_BASE}/pending/${itemId}/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title, artist, genre,
                ...(albumArtist ? { album_artist: albumArtist } : {}),
                ...(onConflict ? { on_conflict: onConflict } : {})
            })
        });

        if (response.status === 409) {
            const body = await response.json().catch(() => ({}));
            if (body.detail?.code === 'destination_exists') {
                showDestinationChoice(itemId, body.detail.existing_path);
                delete confirmBtn.dataset.busy;
                confirmBtn.classList.remove('is-saving');
                confirmBtn.disabled = false;
                confirmBtn.textContent = CONFIRM_LABEL;
                return false;
            }
            const {message, technical} = humanizeServerDetail(body.detail, 'الملف مشغول حاليًا.');
            throw new ApiError(message, technical);
        }
        
        if (!response.ok) {
            throw await apiError(response, 'الخادم لم يُكمل التأكيد.');
        }
        const {new_path: newPath} = await response.json().catch(() => ({}));
        // {album artist}/{title}/{file}: the folder is the third part from the end
        confirmedFolders.push(String(newPath || '').split('/').slice(-3)[0] || shown || '');
        rememberGenre(pendingItems.find(entry => entry.id === itemId)?.channel, genre);
        
        // The file left the queue: its card leaves, the others close the gap
        removeItemCardFromDOM(itemId);
        showAlert(`نُقل «${title}»${describeFolders(confirmedFolders.slice(-1))}.`, 'success');
        logEvent('info', 'Item confirmed and moved', {itemId});
        libraryState.stale = true;
        return true;
        
    } catch (error) {
        logEvent('error', 'Error confirming item', {itemId, error: error.message});
        showError('لم يُنقل الملف', error);
        delete confirmBtn.dataset.busy;
        confirmBtn.classList.remove('is-saving');
        confirmBtn.classList.add('is-failed');
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'أعد محاولة النقل';
        setItemStatus(itemId, `لم يُنقل: ${describeError(error).message}`, 'error');
        return false;
    }
}

// The library already has this title for this artist: let the user decide
function showDestinationChoice(itemId, existingPath) {
    const statusEl = document.getElementById(`itemStatus-${itemId}`);
    if (!statusEl) return;
    // Artist / album / file — each segment isolated so Arabic and ".mp3" keep their order
    const segments = String(existingPath || '').split('/').slice(-3)
        .map(part => `<bdi>${escapeHtml(part)}</bdi>`).join(' / ');
    statusEl.className = 'item-status warn';
    statusEl.innerHTML = `
        <div class="destination-choice" role="group" aria-label="ملف مكرر">
            <p>يوجد ملف بنفس الاسم في المكتبة:</p>
            <p class="destination-path">${segments}</p>
            <div class="destination-choice-actions">
                <button type="button" class="btn-secondary" data-conflict="replace">استبدال الموجود</button>
                <button type="button" class="btn-secondary" data-conflict="keep_both">الاحتفاظ بالاثنين</button>
            </div>
        </div>`;
    statusEl.querySelectorAll('[data-conflict]').forEach(btn => {
        btn.addEventListener('click', () => confirmItem(itemId, btn.dataset.conflict));
    });
}

// Destructive actions take two taps instead of a native confirm(): the first arms the button
// and says what will happen, a second tap within 4s does it. Returns true on the second tap.
const armTimers = new WeakMap();

function armTwoTap(btn, armedText) {
    if (btn.classList.contains('armed')) {
        disarmTwoTap(btn);
        return true;
    }
    btn.dataset.idleText = btn.textContent.trim();
    btn.classList.add('armed');
    btn.textContent = armedText;
    armTimers.set(btn, setTimeout(() => disarmTwoTap(btn), 4000));
    return false;
}

function disarmTwoTap(btn) {
    clearTimeout(armTimers.get(btn));
    btn.classList.remove('armed');
    btn.textContent = btn.dataset.idleText;
}

// Delete item (the original goes to the trash folder and can be restored from there)
async function deleteItem(itemId) {
    const deleteBtn = document.querySelector(`.item-card[data-id="${itemId}"] .delete-btn`);
    if (deleteBtn && !armTwoTap(deleteBtn, 'اضغط مجددًا لنقله إلى سلة المهملات')) return;

    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = 'جارٍ النقل إلى السلة…';
    }
    
    try {
        const response = await fetch(`${API_BASE}/pending/${itemId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw await apiError(response, 'الخادم لم يحذف الملف.');
        }
        
        removeItemCardFromDOM(itemId);
        showAlert('نُقل الملف إلى سلة المهملات. يمكنك استعادته من مجلد السلة قبل حذفه التلقائي.', 'success');
        logEvent('info', 'Pending item deleted', {itemId});
        
    } catch (error) {
        logEvent('error', 'Delete item failed', {itemId, error: error.message});
        showError('لم يُحذف الملف', error);
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'حذف الملف';
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
        setConnectionOffline(false);
    };
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        logEvent('info', `SSE event: ${data.type}`, data);

        if (data.type === 'item_confirmed') {
            libraryState.stale = true;
        }
        if (data.type === 'item_confirmed' || data.type === 'item_deleted') {
            // Card is gone — remove it directly, no API call needed
            removeItemCardFromDOM(data.id);
        } else if (data.type === 'item_updated') {
            // Local state already updated by updateField — nothing to do
        } else if (data.type === 'new_item' || data.type === 'item_error') {
            // Need fresh server data: add new card or refresh error badge
            loadPendingItems({silent: true, smartUpdate: true});
        }
    };
    
    eventSource.onerror = (error) => {
        logEvent('warn', 'SSE error', {error: String(error), readyState: eventSource.readyState});
        // A short blip reconnects on its own; only a drop that lasts gets the banner
        clearTimeout(connection.graceTimer);
        connection.graceTimer = setTimeout(() => {
            if (eventSource.readyState !== EventSource.OPEN) setConnectionOffline(true);
        }, 3000);
        // CLOSED means the browser gave up (e.g. the server answered with an error): retry ourselves
        if (eventSource.readyState === EventSource.CLOSED) {
            clearTimeout(connection.retryTimer);
            connection.retryTimer = setTimeout(setupSSE, 10000);
        }
    };
}

// Live-update connection: a banner while it is down, and a catch-up reload when it returns
const connection = {offline: false, graceTimer: null, retryTimer: null};

function setConnectionOffline(offline) {
    const banner = document.getElementById('connectionStatus');
    const wasOffline = connection.offline;
    connection.offline = offline;
    if (offline) clearTimeout(connection.graceTimer);
    if (!banner) return;

    if (offline) {
        banner.innerHTML = `<span>انقطع الاتصال بالخادم. ما كتبته في البطاقات باقٍ، والقائمة لا تتحدث حتى يعود الاتصال.</span>
            <button type="button" class="batch-state-btn" id="reconnectBtn">أعد الاتصال</button>`;
        banner.hidden = false;
        document.getElementById('reconnectBtn').addEventListener('click', () => {
            setupSSE();
            loadPendingItems({silent: true, smartUpdate: true});
        });
    } else {
        banner.hidden = true;
        banner.replaceChildren();
        // Events may have been missed while away: pick up cards added or confirmed elsewhere
        if (wasOffline) loadPendingItems({silent: true, smartUpdate: true});
    }
}

window.addEventListener('offline', () => setConnectionOffline(true));
window.addEventListener('online', () => setupSSE());

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
    isMobileViewport: false,
    totalItems: 0,
    selectedTracks: new Set(),
    expandedTrackCards: new Set(),
    multiSelectMode: false,
    currentData: {
        artists: [],
        albums: [],
        genres: [],
        tracks: []
    },
    detailContext: null, // {type: 'artist', name: 'Artist Name'}
    navigationStack: [] // stack of back-navigation targets
};

// Track Cache for Batch Editing
libraryState.trackMap = new Map();

// Helper to cache tracks
function cacheTracks(tracks) {
    tracks.forEach(track => libraryState.trackMap.set(track.id, track));
}

function isMobileLibraryViewport() {
    return window.innerWidth < LIBRARY_MOBILE_BREAKPOINT_PX;
}

function getLibraryItemsPerPage() {
    return isMobileLibraryViewport() ? 20 : 50;
}

function formatTrackDuration(seconds) {
    const totalSeconds = Number(seconds);
    if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) return '';
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = Math.floor(totalSeconds % 60);
    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
}

function formatTrackTertiaryMeta(track) {
    const parts = [];
    if (track.year) parts.push(String(track.year));
    if (track.track_number) parts.push(`#${track.track_number}`);
    const durationLabel = formatTrackDuration(track.duration);
    if (durationLabel) parts.push(durationLabel);
    return parts.join(' • ');
}

function isTrackContextActive() {
    return (
        libraryState.currentView === 'tracks' ||
        (libraryState.detailContext && ['album', 'genre'].includes(libraryState.detailContext.type))
    );
}

function rerenderActiveTrackContext() {
    if (!isTrackContextActive()) return;
    renderTracks(libraryState.currentData.tracks);
    if (libraryState.detailContext?.type === 'album') {
        injectSelectAlbumButton(libraryState.currentData.tracks);
    }
}

// Router
function initRouter() {
    function handleRoute() {
        const hash = window.location.hash || '#/pending';
        const route = hash.replace('#/', '').split('/')[0];  // "pending/12" is the queue
        
        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.route === route);
        });
        
        // Show/hide pages
        const pendingPage = document.getElementById('pendingPage');
        const libraryPage = document.getElementById('libraryPage');
        const settingsPage = document.getElementById('settingsPage');

        if (route === 'library') {
            pendingPage.style.display = 'none';
            libraryPage.style.display = 'block';
            if (settingsPage) settingsPage.style.display = 'none';

            // Initial load only if empty
            if (libraryState.totalItems === 0 && libraryState.currentData.tracks.length === 0) {
                initLibrary();
            } else if (libraryState.stale && !libraryState.detailContext) {
                // Tracks were confirmed since the last visit: refresh counts and the list
                libraryState.stale = false;
                loadLibraryStats();
                loadViewData();
            } else {
                updateSelectionBar();
                rerenderActiveTrackContext();
            }
        } else if (route === 'settings') {
            pendingPage.style.display = 'none';
            libraryPage.style.display = 'none';
            if (settingsPage) settingsPage.style.display = 'block';
            initSettingsPage();
        } else {
            pendingPage.style.display = 'block';
            libraryPage.style.display = 'none';
            if (settingsPage) settingsPage.style.display = 'none';
            document.querySelectorAll('.title-input').forEach(autosizeTitle);
            revealLinkedCard();
        }
    }
    
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
}

// Initialize Library
async function initLibrary() {
    libraryState.isMobileViewport = isMobileLibraryViewport();
    libraryState.itemsPerPage = getLibraryItemsPerPage();

    // Load stats
    await loadLibraryStats();
    // Reconnect to a scan started before this page load
    pollRescanStatus(false);
    
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
            libraryState.navigationStack = [];
            
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
        const backTarget = libraryState.navigationStack.pop();
        if (backTarget?.type === 'artist') {
            // Go back to the artist's album list (don't push to stack again)
            viewArtistAlbums(encodeURIComponent(backTarget.name), false);
        } else {
            // Go back to the main list view
            document.getElementById('detailView').style.display = 'none';
            const mainView = document.querySelector(`#${libraryState.currentView}View`);
            if (mainView) {
                mainView.classList.add('active');
            } else {
                logEvent('warn', `Main view #${libraryState.currentView}View not found`);
            }
            libraryState.detailContext = null;
            libraryState.loadSeq = (libraryState.loadSeq || 0) + 1;
            if (libraryState.stale) {
                libraryState.stale = false;
                loadLibraryStats();
                loadViewData();
            }
        }
    });

    const reviewVariantsBtn = document.getElementById('reviewVariantsBtn');
    if (reviewVariantsBtn) reviewVariantsBtn.addEventListener('click', showArtistVariants);

    let libraryResizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(libraryResizeTimer);
        libraryResizeTimer = setTimeout(() => {
            const wasMobile = libraryState.isMobileViewport;
            const isMobile = isMobileLibraryViewport();
            libraryState.isMobileViewport = isMobile;
            libraryState.itemsPerPage = getLibraryItemsPerPage();

            updateSelectionBar();

            if (wasMobile !== isMobile && document.getElementById('libraryPage')?.style.display === 'block') {
                libraryState.currentPage = 1;
                loadViewData();
            } else if (isTrackContextActive()) {
                rerenderActiveTrackContext();
            }
        }, 150);
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
        statsEl.textContent = [
            arabicCount(stats.total_tracks, TRACK_FORMS),
            arabicCount(stats.total_artists, ARTIST_FORMS),
            arabicCount(stats.total_albums, ALBUM_FORMS),
        ].join(' · ');
        loadArtistVariants();
    } catch (error) {
        logEvent('warn', 'Error loading library stats', {error: error.message});
    }
}

// Arabic number agreement: forms = [one, two (dual), 3–10 (plural), 11–99 (acc. singular), hundreds (gen. singular)]
function arabicCount(n, [one, two, few, many, hundred]) {
    if (n === 1) return one;
    if (n === 2) return two;
    const mod100 = n % 100;
    if (mod100 === 0) return `${n} ${hundred}`;
    return `${n} ${mod100 >= 3 && mod100 <= 10 ? few : many}`;
}

// ---- Artist spelling variants (e.g. الأكرف / الاكرف) ----

async function loadArtistVariants() {
    try {
        const response = await fetch('/api/library/artist-variants');
        if (!response.ok) return;
        const {groups} = await response.json();
        libraryState.variantGroups = groups;
        const notice = document.getElementById('artistVariantsNotice');
        if (!notice) return;
        notice.style.display = groups.length ? 'flex' : 'none';
        document.getElementById('artistVariantsText').textContent =
            `${arabicCount(groups.length, ['فنان واحد مكتوب', 'فنانان مكتوبان', 'فنانين مكتوبين', 'فنانًا مكتوبًا', 'فنان مكتوب'])} بأكثر من تهجئة`;
    } catch (error) {
        logEvent('warn', 'Error loading artist variants', {error: error.message});
    }
}

function showArtistVariants() {
    const groups = libraryState.variantGroups || [];
    libraryState.navigationStack.push(null);
    libraryState.detailContext = {type: 'variants'};

    document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
    document.getElementById('detailView').style.display = 'block';
    document.getElementById('detailTitle').textContent = 'توحيد أسماء الفنانين';

    const detailContent = document.getElementById('detailContent');
    detailContent.className = 'variants-list';
    if (!groups.length) {
        detailContent.innerHTML = '<div class="empty-state show"><p>لا توجد أسماء مكررة.</p></div>';
        return;
    }
    detailContent.innerHTML = groups.map((group, gi) => `
        <div class="variant-group" data-group="${gi}">
            <p class="variant-hint">اختر الاسم الصحيح، وستُنقل بقية الصوتيات إليه:</p>
            ${group.variants.map(v => `
                <label class="variant-option">
                    <input type="radio" name="variant-${gi}" value="${escapeHtml(v.name)}" ${v.name === group.suggested ? 'checked' : ''}>
                    <bdi>${escapeHtml(v.name)}</bdi>
                    <span class="variant-count">${arabicCount(v.track_count, TRACK_FORMS)}</span>
                </label>
            `).join('')}
            <div class="variant-preview" aria-live="polite"></div>
            <div class="variant-actions">
                <button type="button" class="btn-secondary" data-variant-action="preview">معاينة الدمج</button>
                <button type="button" class="btn-primary" data-variant-action="apply" disabled>دمج</button>
            </div>
        </div>
    `).join('');

    detailContent.querySelectorAll('.variant-group').forEach(groupEl => {
        const group = groups[Number(groupEl.dataset.group)];
        const applyBtn = groupEl.querySelector('[data-variant-action="apply"]');
        // Changing the chosen name invalidates the preview
        groupEl.querySelectorAll('input[type="radio"]').forEach(radio => radio.addEventListener('change', () => {
            applyBtn.disabled = true;
            groupEl.querySelector('.variant-preview').textContent = '';
        }));
        groupEl.querySelector('[data-variant-action="preview"]').addEventListener('click', () => runArtistMerge(groupEl, group, false));
        applyBtn.addEventListener('click', () => runArtistMerge(groupEl, group, true));
    });
}

async function runArtistMerge(groupEl, group, apply) {
    const target = groupEl.querySelector('input[type="radio"]:checked')?.value;
    const sources = group.variants.map(v => v.name).filter(name => name !== target);
    const previewEl = groupEl.querySelector('.variant-preview');
    const buttons = groupEl.querySelectorAll('button');
    buttons.forEach(b => b.disabled = true);
    previewEl.textContent = apply ? 'جارٍ الدمج…' : 'جارٍ الحساب…';

    try {
        const response = await fetch('/api/library/artist-merge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sources, target, apply})
        });
        if (!response.ok) throw await apiError(response, 'الخادم لم يُكمل الدمج.');
        const body = await response.json();

        if (!apply) {
            const lines = [`ستُعدَّل ${arabicCount(body.track_count, TRACK_FORMS)} لتصبح باسم «${target}».`];
            if (body.move_count) lines.push(`سيُنقل ${arabicCount(body.move_count, FILE_FORMS)} إلى مجلد «${target}».`);
            if (body.blocked_count) lines.push(`${body.blocked_count} ملف له نسخة بنفس الاسم في المجلد، سيُعدَّل دون نقل.`);
            previewEl.textContent = lines.join(' ');
            buttons.forEach(b => b.disabled = false);
            groupEl.querySelector('[data-variant-action="apply"]').disabled = body.track_count === 0;
            return;
        }

        const r = body.results;
        libraryState.stale = true;
        if (r.failed) {
            showAlert(`دُمجت ${arabicCount(r.successful, TRACK_FORMS)}، وتعذّر دمج ${arabicCount(r.failed, TRACK_FORMS)}. أعد المحاولة بعد مسح المكتبة.`,
                'warn', 0, r.errors.map(e => e.error).join('\n'));
        } else {
            showAlert(`تم توحيد ${arabicCount(r.successful, TRACK_FORMS)} باسم «${target}».`, 'success');
        }
        groupEl.remove();
        libraryState.variantGroups = (libraryState.variantGroups || []).filter(g => g !== group);
        loadArtistVariants();
    } catch (error) {
        previewEl.textContent = `تعذّر الدمج: ${describeError(error).message}`;
        buttons.forEach(b => b.disabled = false);
    }
}

// Load View Data
async function loadViewData() {
    // Only the newest request may render; a slow older response is discarded
    const requestSeq = libraryState.loadSeq = (libraryState.loadSeq || 0) + 1;
    const view = libraryState.currentView;
    const [sortBy, sortOrder] = libraryState.currentSort.split('-');
    const search = libraryState.searchQuery;
    libraryState.itemsPerPage = getLibraryItemsPerPage();
    
    // Pagination params
    const limit = libraryState.itemsPerPage;
    const offset = (libraryState.currentPage - 1) * limit;
    
    try {
        // Show loading state
        const container = document.getElementById(`${view}List`) || document.getElementById('tracksList');
        if (container) container.innerHTML = '<div class="loading">جارٍ التحميل…</div>';
        
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
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع البيانات.');
        
        const data = await response.json();
        if (requestSeq !== libraryState.loadSeq) return;
        
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
        if (requestSeq !== libraryState.loadSeq) return;
        logEvent('error', 'Error loading library view data', {view, error: error.message});
        showError('تعذّر تحميل المكتبة', error);
        const container = document.getElementById(`${view}List`) || document.getElementById('tracksList');
        if (container) container.innerHTML = `<div class="error-message">تعذّر تحميل هذه القائمة: ${escapeHtml(describeError(error).message)}</div>`;
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
            {value: 'track_count-desc', label: 'عدد الصوتيات'},
            {value: 'album_count-desc', label: 'عدد الألبومات'}
        ],
        albums: [
            {value: 'name-asc', label: 'الاسم (أ - ي)'},
            {value: 'name-desc', label: 'الاسم (ي - أ)'},
            {value: 'year-desc', label: 'السنة (الأحدث)'},
            {value: 'track_count-desc', label: 'عدد الصوتيات'}
        ],
        genres: [
            {value: 'name-asc', label: 'الاسم (أ - ي)'},
            {value: 'name-desc', label: 'الاسم (ي - أ)'},
            {value: 'track_count-desc', label: 'عدد الصوتيات'}
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

    // A sort from another tab (e.g. name-asc on tracks) isn't valid here: fall back to the first
    if (!options[view].some(opt => opt.value === libraryState.currentSort)) {
        libraryState.currentSort = options[view][0].value;
    }
    sortSelect.value = libraryState.currentSort;
}

function renderLibraryEmpty(container, emptyMessage) {
    const query = libraryState.searchQuery;
    container.innerHTML = query
        ? `<div class="empty-state show">
               <p>لا توجد نتائج مطابقة لـ «${escapeHtml(query)}». جرّب اسمًا آخر.</p>
               <button type="button" class="btn-secondary" data-empty-action="clear-search">مسح البحث</button>
           </div>`
        : `<div class="empty-state show">
               <p>${emptyMessage}</p>
               <button type="button" class="btn-secondary" data-empty-action="rescan">فحص المكتبة</button>
           </div>`;
}

document.addEventListener('click', event => {
    const action = event.target.closest('[data-empty-action]')?.dataset.emptyAction;
    if (action === 'clear-search') {
        const searchInput = document.getElementById('librarySearch');
        if (searchInput) searchInput.value = '';
        libraryState.searchQuery = '';
        libraryState.currentPage = 1;
        loadViewData();
    } else if (action === 'rescan') {
        startRescan();
    }
});

// Render Artists
function renderArtists(artists) {
    const container = document.getElementById('artistsList');
    
    if (artists.length === 0) {
        renderLibraryEmpty(container, 'لا يوجد فنانون في المكتبة بعد.');
        return;
    }
    
    container.innerHTML = artists.map(artist => `
        <div class="list-item" role="button" tabindex="0" data-nav="artist" data-name="${escapeHtml(artist.name)}">
            <div class="list-item-content">
                <div class="list-item-title">${escapeHtml(artist.name)}</div>
                <div class="list-item-meta">${arabicCount(artist.track_count, TRACK_FORMS)} · ${arabicCount(artist.album_count, ALBUM_FORMS)}</div>
            </div>
        </div>
    `).join('');
}

// Render Albums
function renderAlbums(albums) {
    const container = document.getElementById('albumsList');
    
    if (albums.length === 0) {
        renderLibraryEmpty(container, 'لا توجد ألبومات في المكتبة بعد.');
        return;
    }
    
    container.innerHTML = albums.map(album => `
        <div class="album-card" role="button" tabindex="0" data-nav="album" data-name="${escapeHtml(album.name)}" data-album-artist="${escapeHtml(album.album_artist)}">
            <div class="album-artwork">
                ${album.artwork_id 
                    ? `<img src="/api/library/tracks/${album.artwork_id}/artwork?t=${Date.now()}" alt="">` 
                    : '<span class="artwork-missing" aria-hidden="true">♪</span>'}
            </div>
            <div class="album-name">${escapeHtml(album.name) || 'بدون اسم'}</div>
            <div class="album-artist">${escapeHtml(album.album_artist) || 'غير معروف'}</div>
            <div class="list-item-meta">${arabicCount(album.track_count, TRACK_FORMS)}${album.year ? ' · ' + album.year : ''}</div>
        </div>
    `).join('');
}

// Render Genres
function renderGenres(genres) {
    const container = document.getElementById('genresList');
    
    if (genres.length === 0) {
        renderLibraryEmpty(container, 'لا توجد أنواع في المكتبة بعد.');
        return;
    }
    
    container.innerHTML = genres.map(genre => `
        <div class="list-item" role="button" tabindex="0" data-nav="genre" data-name="${escapeHtml(genre.name)}">
            <div class="list-item-content">
                <div class="list-item-title">${escapeHtml(genre.name)}</div>
                <div class="list-item-meta">${arabicCount(genre.track_count, TRACK_FORMS)}</div>
            </div>
        </div>
    `).join('');
}

function renderDesktopTrackList(tracks) {
    return tracks.map(track => {
        const isSelected = libraryState.selectedTracks.has(track.id);
        return `
        <div class="list-item ${isSelected ? 'selected' : ''}" data-track-id="${track.id}" onclick="handleTrackClick(event, this)">
            ${libraryState.multiSelectMode ? `<input type="checkbox" class="list-item-checkbox" data-track-id="${track.id}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation()">` : ''}
            <div class="list-item-content">
                <div class="list-item-title">${escapeHtml(track.title) || 'بدون عنوان'}</div>
                <div class="list-item-meta">
                    ${escapeHtml(formatArtistDisplay(track.artist))} •
                    ${escapeHtml(track.album) || 'غير معروف'}
                    ${track.year ? ' • ' + track.year : ''}
                </div>
            </div>
        </div>
        `;
    }).join('');
}

function renderMobileTrackCards(tracks) {
    return tracks.map(track => {
        const isSelected = libraryState.selectedTracks.has(track.id);
        const isExpanded = libraryState.expandedTrackCards.has(track.id);
        const tertiaryMeta = formatTrackTertiaryMeta(track) || 'بدون بيانات إضافية';
        const fileName = String(track.file_path || '').split('/').pop() || '';

        return `
        <div class="list-item track-mobile-card ${isSelected ? 'selected' : ''}" data-track-id="${track.id}" onclick="handleTrackClick(event, this)">
            <div class="track-mobile-main">
                <div class="track-mobile-title-row">
                    <div class="list-item-title">${escapeHtml(track.title) || 'بدون عنوان'}</div>
                    ${libraryState.multiSelectMode ? `<input type="checkbox" class="list-item-checkbox track-mobile-checkbox" data-track-id="${track.id}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation()">` : ''}
                </div>
                <div class="track-mobile-secondary">${escapeHtml(formatArtistDisplay(track.artist))}</div>
                <div class="track-mobile-secondary">${escapeHtml(track.album) || 'غير معروف'}</div>
                <div class="track-mobile-tertiary">${tertiaryMeta}</div>
                ${isExpanded ? `
                <div class="track-mobile-details">
                    <div>${escapeHtml(track.genre) || 'بدون نوع'}</div>
                    <div>${escapeHtml(fileName)}</div>
                </div>
                ` : ''}
            </div>
            ${libraryState.multiSelectMode ? '' : `
            <div class="track-mobile-actions">
                <button type="button" class="btn-secondary track-mobile-action" data-action="edit" data-track-id="${track.id}">
                    تعديل
                </button>
                <button type="button" class="btn-secondary track-mobile-action" data-action="more" data-track-id="${track.id}">${isExpanded ? 'أقل' : 'المزيد'}</button>
            </div>`}
        </div>
        `;
    }).join('');
}

// Render Tracks
function renderTracks(tracks) {
    const container = libraryState.detailContext
        ? document.getElementById('detailContent')
        : document.getElementById('tracksList');

    if (!container) return;

    const activeTrackIds = new Set(tracks.map(track => track.id));
    for (const trackId of Array.from(libraryState.expandedTrackCards)) {
        if (!activeTrackIds.has(trackId)) {
            libraryState.expandedTrackCards.delete(trackId);
        }
    }

    if (tracks.length === 0) {
        if (libraryState.detailContext) {
            container.innerHTML = '<div class="empty-state show"><p>لا توجد صوتيات هنا.</p></div>';
        } else {
            renderLibraryEmpty(container, 'لا توجد صوتيات في المكتبة بعد.');
        }
        return;
    }

    container.classList.add('items-list');
    const useMobileCards = isMobileLibraryViewport();
    container.classList.toggle('tracks-mobile-list', useMobileCards);
    container.classList.toggle('tracks-desktop-list', !useMobileCards);
    container.innerHTML = useMobileCards ? renderMobileTrackCards(tracks) : renderDesktopTrackList(tracks);

    container.querySelectorAll('.list-item-checkbox').forEach(cb => {
        cb.addEventListener('change', handleTrackSelection);
    });

    container.querySelectorAll('.track-mobile-action').forEach(btn => {
        btn.addEventListener('click', handleTrackMobileAction);
    });
}

function toggleTrackSelection(trackId) {
    if (libraryState.selectedTracks.has(trackId)) {
        libraryState.selectedTracks.delete(trackId);
    } else {
        libraryState.selectedTracks.add(trackId);
    }
}

function getTrackDataById(trackId) {
    return libraryState.trackMap.get(trackId) || libraryState.currentData.tracks.find(track => track.id === trackId) || null;
}

function handleTrackMobileAction(event) {
    event.preventDefault();
    event.stopPropagation();

    const action = event.currentTarget.dataset.action;
    const trackId = parseInt(event.currentTarget.dataset.trackId, 10);
    if (!Number.isInteger(trackId)) return;

    if (action === 'edit') {
        const trackData = getTrackDataById(trackId);
        if (trackData) {
            showEditModal('single', trackData);
        }
        return;
    }

    if (action === 'more') {
        if (libraryState.expandedTrackCards.has(trackId)) {
            libraryState.expandedTrackCards.delete(trackId);
        } else {
            libraryState.expandedTrackCards.add(trackId);
        }
        rerenderActiveTrackContext();
    }
}

// Handle Track Click (Single Edit or Selection Toggle)
function handleTrackClick(event, element) {
    // If clicking checkbox, ignore (handled by its own listener)
    if (event.target.classList.contains('list-item-checkbox')) return;
    
    const trackId = parseInt(element.dataset.trackId);
    const trackData = getTrackDataById(trackId);
    if (!trackData) return;
    
    if (libraryState.multiSelectMode) {
        toggleTrackSelection(trackId);
        updateSelectionBar();
        rerenderActiveTrackContext();
    } else {
        libraryState.expandedTrackCards.delete(trackId);
        showEditModal('single', trackData);
    }
}

// Library navigation cards: one delegated handler, names travel as data, never as code
const LIBRARY_NAV_HANDLERS = {
    artist: name => viewArtistAlbums(encodeURIComponent(name)),
    album: (name, target) => viewAlbumTracks(encodeURIComponent(name), true, target.dataset.albumArtist),
    genre: name => viewGenreTracks(encodeURIComponent(name)),
};

function handleLibraryNav(event) {
    const target = event.target.closest('[data-nav]');
    if (!target) return;
    if (event.type === 'keydown') {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
    }
    LIBRARY_NAV_HANDLERS[target.dataset.nav]?.(target.dataset.name || '', target);
}

document.addEventListener('click', handleLibraryNav);
document.addEventListener('keydown', handleLibraryNav);

// After an edit, reload what the user is looking at (detail identity, filter, page),
// not the top-level list. The main list is marked stale and reloads on the way back.
async function refreshLibraryContext() {
    loadLibraryStats();
    const ctx = libraryState.detailContext;
    if (!ctx) return loadViewData();

    libraryState.stale = true;
    if (ctx.type === 'artist') {
        await viewArtistAlbums(encodeURIComponent(ctx.name), false);
    } else if (ctx.type === 'album') {
        await viewAlbumTracks(encodeURIComponent(ctx.name), false, ctx.albumArtist);
    } else if (ctx.type === 'genre') {
        await viewGenreTracks(encodeURIComponent(ctx.name), false);
    } else {
        return;
    }

    // The edit moved every track out of this album/genre: step back instead of showing an empty page
    const now = libraryState.detailContext;
    if (now && now.type === ctx.type && now.name === ctx.name
        && ['album', 'genre'].includes(ctx.type) && libraryState.currentData.tracks.length === 0) {
        document.getElementById('backBtn').click();
    }
}

// View Artist Albums
async function viewArtistAlbums(artistName, pushToStack = true) {
    const name = decodeURIComponent(artistName);
    const requestSeq = libraryState.loadSeq = (libraryState.loadSeq || 0) + 1;

    try {
        const response = await fetch(`/api/library/albums?artist=${encodeURIComponent(name)}`);
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع الألبومات.');

        const data = await response.json();
        if (requestSeq !== libraryState.loadSeq) return;  // a newer view was requested

        if (pushToStack) {
            libraryState.navigationStack.push(null); // back leads to main list
        }
        libraryState.detailContext = {type: 'artist', name: name};
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `ألبومات ${name}`;
        
        const detailContent = document.getElementById('detailContent');
        // Use album-card layout with artwork (same as main Albums view)
        detailContent.className = 'albums-grid';
        detailContent.innerHTML = data.albums.map(album => `
            <div class="album-card" role="button" tabindex="0" data-nav="album" data-name="${escapeHtml(album.name)}" data-album-artist="${escapeHtml(album.album_artist)}">
                <div class="album-artwork">
                    ${album.artwork_id 
                        ? `<img src="/api/library/tracks/${album.artwork_id}/artwork?t=${Date.now()}" alt="">` 
                        : '<span class="artwork-missing" aria-hidden="true">♪</span>'}
                </div>
                <div class="album-name">${escapeHtml(album.name) || 'بدون اسم'}</div>
                <div class="list-item-meta">${arabicCount(album.track_count, TRACK_FORMS)}</div>
            </div>
        `).join('');
    } catch (error) {
        logEvent('error', 'Error loading artist albums', {artist: name, error: error.message});
        showError('تعذّر تحميل ألبومات الفنان', error);
    }
}

function injectSelectAlbumButton(tracks) {
    if (libraryState.detailContext?.type !== 'album') return;
    const detailContent = document.getElementById('detailContent');
    if (!detailContent) return;

    const existingBtn = document.getElementById('selectAlbumBtn');
    if (existingBtn) {
        existingBtn.remove();
    }

    detailContent.insertAdjacentHTML('afterbegin', `
        <button id="selectAlbumBtn" class="btn-secondary select-album-btn" type="button">
            تحديد جميع الصوتيات (${tracks.length})
        </button>
    `);

    const selectAlbumBtn = document.getElementById('selectAlbumBtn');
    if (selectAlbumBtn) {
        selectAlbumBtn.addEventListener('click', () => {
            selectAllAlbumTracks(tracks);
        });
    }
}

// View Album Tracks
async function viewAlbumTracks(albumName, pushToStack = true, albumArtist) {
    const name = decodeURIComponent(albumName);
    const requestSeq = libraryState.loadSeq = (libraryState.loadSeq || 0) + 1;

    try {
        // Album identity = name + album artist, so same-named albums don't mix
        const params = new URLSearchParams({album: name, sort_by: 'track_number', limit: '500'});
        if (albumArtist !== undefined) params.set('album_artist', albumArtist);
        const response = await fetch(`/api/library/tracks?${params}`);
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع الصوتيات.');

        const data = await response.json();
        if (requestSeq !== libraryState.loadSeq) return;

        if (pushToStack) {
            // If we came from an artist's album list, save that context for back navigation
            if (libraryState.detailContext?.type === 'artist') {
                libraryState.navigationStack.push({type: 'artist', name: libraryState.detailContext.name});
            } else {
                libraryState.navigationStack.push(null);
            }
        }
        libraryState.detailContext = {type: 'album', name: name, albumArtist};
        libraryState.currentData.tracks = data.tracks; // Store for select all
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `صوتيات ألبوم ${name}`;
        
        const detailContent = document.getElementById('detailContent');
        detailContent.className = 'items-list'; // Reset to list layout
        
        cacheTracks(data.tracks);
        renderTracks(data.tracks);
        injectSelectAlbumButton(data.tracks);
    } catch (error) {
        logEvent('error', 'Error loading album tracks', {album: name, error: error.message});
        showError('تعذّر تحميل صوتيات الألبوم', error);
    }
}

// Select All Album Tracks
function selectAllAlbumTracks(tracks) {
    // Enable multi-select mode if not already
    if (!libraryState.multiSelectMode) {
        libraryState.multiSelectMode = true;
        setMultiSelectButton(true);
    }
    
    // Clear previous selection and select all tracks in this album
    libraryState.selectedTracks.clear();
    tracks.forEach(track => libraryState.selectedTracks.add(track.id));
    libraryState.currentData.tracks = tracks;
    
    updateSelectionBar();
    rerenderActiveTrackContext();
}

// View Genre Tracks
async function viewGenreTracks(genreName, pushToStack = true) {
    const name = decodeURIComponent(genreName);
    const requestSeq = libraryState.loadSeq = (libraryState.loadSeq || 0) + 1;

    try {
        const response = await fetch(`/api/library/tracks?genre=${encodeURIComponent(name)}&limit=500`);
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع الصوتيات.');

        const data = await response.json();
        if (requestSeq !== libraryState.loadSeq) return;

        if (pushToStack) {
            libraryState.navigationStack.push(null);
        }
        libraryState.detailContext = {type: 'genre', name: name};
        libraryState.currentData.tracks = data.tracks;
        
        document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
        const detailView = document.getElementById('detailView');
        detailView.style.display = 'block';
        document.getElementById('detailTitle').textContent = `صوتيات نوع ${name}`;
        
        cacheTracks(data.tracks);
        renderTracks(data.tracks);
    } catch (error) {
        logEvent('error', 'Error loading genre tracks', {genre: name, error: error.message});
        showError('تعذّر تحميل صوتيات النوع', error);
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
    rerenderActiveTrackContext();
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
    if (libraryPage) libraryPage.style.paddingBottom = isMobileLibraryViewport() ? '132px' : '80px';
    document.getElementById('selectionCount').textContent = count > 0
        ? `المحدد: ${arabicCount(count, TRACK_FORMS)}`
        : 'اضغط على الصوتيات لتحديدها';
    document.getElementById('selectionDetails').textContent = '';
}

// One selection model: «تحديد متعدد» is a pressed/unpressed toggle with a fixed label,
// and the selection bar's «إنهاء التحديد» is the one labelled way out
function setMultiSelectButton(active) {
    const btn = document.getElementById('multiSelectBtn');
    if (!btn) return;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
}

// Toggle Multi-Select Mode
function toggleMultiSelectMode() {
    libraryState.multiSelectMode = !libraryState.multiSelectMode;
    if (!libraryState.multiSelectMode) {
        libraryState.selectedTracks.clear();
    }
    
    setMultiSelectButton(libraryState.multiSelectMode);
    
    // Update selection bar visibility
    updateSelectionBar();
    
    // Re-render current tracks to show/hide checkboxes
    rerenderActiveTrackContext();
}

// Clear Selection
function clearSelection() {
    libraryState.selectedTracks.clear();
    libraryState.multiSelectMode = false;
    
    setMultiSelectButton(false);
    
    document.querySelectorAll('.list-item-checkbox').forEach(cb => cb.checked = false);
    updateSelectionBar();
    
    // Re-render to remove checkboxes
    rerenderActiveTrackContext();
}

// Batch edit: every field starts as 'keep'. Typing makes it 'set'; the clear button makes it 'clear'.
const BATCH_FIELDS = [
    {key: 'title', input: 'batchTitle', label: 'العنوان'},
    {key: 'artist', input: 'batchArtist', label: 'الفنانون'},
    {key: 'album_artist', input: 'batchAlbumArtist', label: 'فنان الألبوم', clearable: true},
    {key: 'album', input: 'batchAlbum', label: 'الألبوم', clearable: true},
    {key: 'genre', input: 'batchGenre', label: 'النوع', clearable: true},
    {key: 'year', input: 'batchYear', label: 'السنة', clearable: true},
];
const batchEdit = {states: {}, failures: [], saving: false};
// Queue items are ملفات (files waiting to move); library items are صوتيات (tracks)
const TRACK_FORMS = ['صوتية واحدة', 'صوتيتان', 'صوتيات', 'صوتيةً', 'صوتية'];
const FILE_FORMS = ['ملف واحد', 'ملفان', 'ملفات', 'ملفًا', 'ملف'];
const FILE_FORMS_GENITIVE = ['ملف واحد', 'ملفين', 'ملفات', 'ملفًا', 'ملف'];  // after «لنقل»
const ARTIST_FORMS = ['فنان واحد', 'فنانان', 'فنانين', 'فنانًا', 'فنان'];
const ALBUM_FORMS = ['ألبوم واحد', 'ألبومان', 'ألبومات', 'ألبومًا', 'ألبوم'];
const FOLDER_FORMS_GENITIVE = ['مجلد واحد', 'مجلدين', 'مجلدات', 'مجلدًا', 'مجلد'];  // after «إلى»

function setupBatchFieldControls() {
    if (window.batchFieldControlsAttached) return;
    BATCH_FIELDS.forEach(field => {
        const input = document.getElementById(field.input);
        input.addEventListener('input', () => {
            if (libraryState.editMode !== 'batch') return;
            setBatchFieldState(field.key, input.value.trim() === '' ? 'keep' : 'set');
        });
    });
    document.getElementById('batchEditForm').addEventListener('click', event => {
        const btn = event.target.closest('.batch-field-state button');
        if (!btn) return;
        setBatchFieldState(btn.closest('.batch-field-state').dataset.field, btn.dataset.action);
    });
    window.batchFieldControlsAttached = true;
}

function setBatchFieldState(key, state) {
    const field = BATCH_FIELDS.find(f => f.key === key);
    const input = document.getElementById(field.input);
    batchEdit.states[key] = state;
    if (state !== 'set') input.value = '';
    input.disabled = state === 'clear';
    renderBatchFieldState(field);
    renderBatchSummary();
}

function renderBatchFieldState(field) {
    const el = document.querySelector(`.batch-field-state[data-field="${field.key}"]`);
    const state = batchEdit.states[field.key];
    el.closest('.form-group').classList.toggle('batch-changed', state !== 'keep');
    if (state === 'keep') {
        el.innerHTML = '<span class="batch-state">بدون تغيير</span>'
            + (field.clearable ? '<button type="button" class="batch-state-btn" data-action="clear">مسح من الكل</button>' : '');
    } else {
        const text = state === 'set' ? 'ستتغير القيمة في كل الصوتيات المحددة' : 'سيُمسح من كل الصوتيات المحددة';
        el.innerHTML = `<span class="batch-state ${state}">${text}</span>`
            + '<button type="button" class="batch-state-btn" data-action="keep">تراجع</button>';
    }
}

function batchChangedFields() {
    return BATCH_FIELDS.filter(f => batchEdit.states[f.key] !== 'keep');
}

function renderBatchSummary() {
    const summary = document.getElementById('batchSummary');
    const saveBtn = document.getElementById('saveBatchEdit');
    const changed = batchChangedFields();
    const count = libraryState.selectedTracks.size;

    let html = '';
    if (batchEdit.failures.length > 0) {
        html += `<div class="batch-failures"><strong>تعذّر تعديل ${arabicCount(batchEdit.failures.length, TRACK_FORMS)}، وما زالت محددة لإعادة المحاولة:</strong><ul>`
            + batchEdit.failures.map(e => `<li>${escapeHtml(e.title || `#${e.track_id}`)}: ${escapeHtml(humanizeServerDetail(e.error, 'تعذّرت الكتابة في الملف.').message)}</li>`).join('')
            + '</ul></div>';
    }
    if (changed.length === 0) {
        html += '<span class="batch-summary-idle">لم يتغير أي حقل بعد</span>';
    } else {
        const names = changed.map(f => batchEdit.states[f.key] === 'clear' ? `${f.label} (مسح)` : f.label);
        html += `ستُعدَّل ${arabicCount(count, TRACK_FORMS)} · الحقول: ${escapeHtml(names.join('، '))}`;
    }
    summary.innerHTML = html;
    saveBtn.disabled = batchEdit.saving || changed.length === 0;
    saveBtn.textContent = batchEdit.saving ? 'جارٍ الحفظ…' : 'حفظ';
}

// Show Edit Modal
function showEditModal(mode, trackData = null) {
    libraryState.editMode = mode;
    libraryState.editTrackData = trackData;
    
    // Reset form
    document.getElementById('batchEditForm').reset();
    
    const modal = document.getElementById('batchEditModal');
    const title = modal.querySelector('h3');
    const batchOnly = modal.querySelectorAll('.batch-field-state, #batchSummary');
    batchOnly.forEach(el => { el.style.display = mode === 'batch' ? '' : 'none'; });
    BATCH_FIELDS.forEach(f => {
        const input = document.getElementById(f.input);
        input.disabled = false;
        input.placeholder = '';
        input.closest('.form-group').classList.remove('batch-changed');
    });
    const saveBtn = document.getElementById('saveBatchEdit');
    saveBtn.disabled = false;
    saveBtn.textContent = 'حفظ';
    
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
        title.textContent = 'تعديل الصوتية';
        
        // Show Artwork Section
        artworkSection.style.display = 'block';
        artworkSection.innerHTML = `
            <label>صورة الغلاف</label>
            <div class="artwork-preview-container">
                <div class="artwork-preview">
                    ${trackData.has_artwork 
                        ? `<img src="/api/library/tracks/${trackData.id}/artwork?t=${Date.now()}" alt="">` 
                        : '<span class="artwork-missing" aria-hidden="true">♪</span>'}
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
                            container.innerHTML = `<img src="${e.target.result}" alt="معاينة صورة الغلاف">`;
                        };
                        reader.readAsDataURL(file);
                    }
                });
            }
        }, 0);
        
        // Pre-fill fields
        document.getElementById('batchTitle').value = trackData.title || '';
        document.getElementById('batchArtist').value = trackData.artist || '';
        document.getElementById('batchAlbumArtist').value = trackData.album_artist || '';
        document.getElementById('batchAlbum').value = trackData.album || '';
        document.getElementById('batchGenre').value = trackData.genre || '';
        document.getElementById('batchYear').value = trackData.year || '';
        
    } else {
        title.textContent = 'تعديل البيانات الوصفية لعدة صوتيات';
        
        // Hide Artwork Section for batch
        artworkSection.style.display = 'none';
        
        // Every field starts as 'keep'; the current value is shown as a hint only
        setupBatchFieldControls();
        batchEdit.failures = [];
        batchEdit.saving = false;
        const tracks = Array.from(libraryState.selectedTracks)
            .map(id => libraryState.trackMap.get(id)).filter(t => t);

        BATCH_FIELDS.forEach(field => {
            const values = new Set(tracks.map(t => t[field.key] ?? ''));
            const input = document.getElementById(field.input);
            if (values.size > 1) {
                input.placeholder = 'قيم متعددة';
            } else {
                const [value] = values;
                input.placeholder = value === '' || value === undefined ? 'فارغ' : `الحالي: ${value}`;
            }
            batchEdit.states[field.key] = 'keep';
            renderBatchFieldState(field);
        });
        renderBatchSummary();
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
    const saveBtn = document.getElementById('saveBatchEdit');
    if (saveBtn.disabled) return;  // a save is already running
    saveBtn.disabled = true;
    saveBtn.textContent = 'جارٍ الحفظ…';
    try {
        await saveSingleTrack(trackId);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ';
    }
}

async function saveSingleTrack(trackId) {
    
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
            
            if (!response.ok) throw await apiError(response, 'الخادم لم يقبل الصورة.');
        } catch (error) {
            logEvent('error', 'Error uploading artwork', {trackId, error: error.message});
            showError('لم تُحفظ صورة الغلاف', error);
            // Don't return, try to save other metadata
        }
    }
    
    // 2. Update Metadata: the form shows every field, so an emptied field is cleared (sent as null)
    const text = id => document.getElementById(id).value.trim() || null;
    const payload = {
        title: text('batchTitle'),
        artist: text('batchArtist'),
        album_artist: text('batchAlbumArtist'),
        album: text('batchAlbum'),
        genre: text('batchGenre'),
        year: parseInt(document.getElementById('batchYear').value, 10) || null
    };
    if (!payload.title || !payload.artist) {
        showAlert('أضف العنوان والفنان قبل الحفظ.', 'warn');
        return;
    }
    
    try {
        const response = await fetch(`/api/library/tracks/${trackId}/update`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw await apiError(response, 'الخادم لم يحفظ التعديل.');
        
        closeEditModal();
        showAlert('حُفظت الصوتية.', 'success');
        refreshLibraryContext();

    } catch (error) {
        logEvent('error', 'Error updating track', {trackId, error: error.message});
        showError('تعذّر حفظ الصوتية', error);
    }
}

// Handle Batch Edit
async function handleBatchEdit() {
    const trackIds = Array.from(libraryState.selectedTracks);
    const changed = batchChangedFields();
    if (trackIds.length === 0 || changed.length === 0 || batchEdit.saving) return;

    const payload = {track_ids: trackIds, clear_fields: []};
    changed.forEach(field => {
        if (batchEdit.states[field.key] === 'clear') {
            payload.clear_fields.push(field.key);
            return;
        }
        const raw = document.getElementById(field.input).value.trim();
        payload[field.key] = field.key === 'year' ? parseInt(raw, 10) : raw;
    });

    batchEdit.saving = true;
    batchEdit.failures = [];
    renderBatchSummary();

    try {
        const response = await fetch('/api/library/tracks/batch-update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw await apiError(response, 'الخادم لم يحفظ التعديل.');
        }
        
        const result = await response.json();
        logEvent('info', 'Batch update completed', result);

        if (result.failed === 0) {
            showAlert(`تم تعديل ${arabicCount(result.successful, TRACK_FORMS)}`, 'success');
            closeEditModal();
            clearSelection();
        } else {
            // Keep only the failed tracks selected so the same edit can be retried
            batchEdit.failures = result.errors;
            libraryState.selectedTracks = new Set(result.errors.map(e => e.track_id));
            updateSelectionBar();
            showAlert(`نجح ${result.successful} وتعذّر ${result.failed}`, 'error');
            renderBatchSummary();
            document.getElementById('batchSummary').scrollIntoView({block: 'center'});
        }
        refreshLibraryContext();
        
    } catch (error) {
        logEvent('error', 'Error in batch update', {error: error.message});
        showError('تعذّر تعديل الصوتيات', error);
    } finally {
        batchEdit.saving = false;
        if (libraryState.editMode === 'batch') renderBatchSummary();
    }
}

// Rescan: progress comes from /rescan/status; a failed poll never leaves the button stuck
const ERROR_FORMS = ['خطأ واحد', 'خطآن', 'أخطاء', 'خطأً', 'خطأ'];
let rescanPollTimer = null;

function setRescanBusy(busy) {
    document.getElementById('rescanBtn').disabled = busy;
    document.getElementById('rescanIcon').classList.toggle('spinning', busy);
}

function renderRescanStatus(status, {failed = null} = {}) {
    const el = document.getElementById('rescanStatus');
    const errors = status?.errors || [];
    let html;
    if (failed) {
        html = `<span class="rescan-error">تعذّرت متابعة المسح: ${escapeHtml(failed)}</span>`
            + '<button type="button" class="batch-state-btn" id="rescanRetryBtn">تحقق مجددًا</button>';
    } else if (status.is_scanning) {
        html = status.total > 0
            ? `جارٍ المسح: <bdi>${status.processed} / ${status.total}</bdi>`
            : 'جارٍ البحث عن الملفات…';
        if (errors.length) html += ` · <span class="rescan-error">${arabicCount(errors.length, ERROR_FORMS)}</span>`;
    } else {
        html = `اكتمل المسح: <bdi>${status.processed} / ${status.total}</bdi>`;
        if (errors.length) {
            html += ` · <details class="rescan-errors"><summary>${arabicCount(errors.length, ERROR_FORMS)}</summary><ul>`
                + errors.map(e => `<li dir="ltr">${escapeHtml(e)}</li>`).join('') + '</ul></details>';
        }
    }
    el.innerHTML = html;
    el.style.display = '';
    const retry = document.getElementById('rescanRetryBtn');
    if (retry) retry.addEventListener('click', () => pollRescanStatus(true));
}

// watching=false: just check on page load whether a scan is already running
async function pollRescanStatus(watching = true) {
    clearTimeout(rescanPollTimer);
    try {
        const response = await fetch('/api/library/rescan/status');
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع حالة المسح.');
        const status = await response.json();

        if (status.is_scanning) {
            setRescanBusy(true);
            renderRescanStatus(status);
            rescanPollTimer = setTimeout(() => pollRescanStatus(true), 2000);
            return;
        }
        setRescanBusy(false);
        if (!watching) return;
        renderRescanStatus(status);
        if (!status.errors?.length) {
            setTimeout(() => {
                const el = document.getElementById('rescanStatus');
                if (!document.getElementById('rescanBtn').disabled) el.style.display = 'none';
            }, 8000);
        }
        await refreshLibraryContext();
    } catch (error) {
        logEvent('error', 'Error polling rescan status', {error: error.message});
        setRescanBusy(false);
        renderRescanStatus(null, {failed: describeError(error).message});
    }
}

// Start Rescan
async function startRescan() {
    setRescanBusy(true);
    renderRescanStatus({is_scanning: true, processed: 0, total: 0, errors: []});
    try {
        const response = await fetch('/api/library/rescan', {method: 'POST'});
        // 409 means a scan is already running: just follow it
        if (!response.ok && response.status !== 409) throw await apiError(response, 'الخادم لم يبدأ المسح.');
        pollRescanStatus(true);
    } catch (error) {
        logEvent('error', 'Error starting library rescan', {error: error.message});
        setRescanBusy(false);
        renderRescanStatus(null, {failed: describeError(error).message});
    }
}

// ==========================================
// Settings page (Telegram notifications)
// ==========================================

let settingsListenersAttached = false;
const TELEGRAM_TOKEN_PLACEHOLDER = '••••••••';

function showSettingsAlert(message, type = 'info', timeout = 5000, technical = '') {
    const alertEl = document.getElementById('settingsAlert');
    if (!alertEl) return;
    fillAlert(alertEl, message, type, technical);

    if (timeout > 0) {
        setTimeout(() => {
            if (alertEl.firstChild?.textContent === message) {
                alertEl.style.display = 'none';
            }
        }, timeout);
    }
}

function showSettingsError(what, error) {
    const {message, technical} = describeError(error);
    showSettingsAlert(`${what}: ${message}`, 'error', 0, technical);
}

// Last saved settings, so the on/off switch can re-save without the form's unsaved edits
let telegramSaved = null;

function renderTelegramStatus() {
    const box = document.getElementById('telegramStatus');
    const text = document.getElementById('telegramStatusText');
    const toggle = document.getElementById('telegramEnabled');
    const disconnectBtn = document.getElementById('telegramDisconnectBtn');
    const connected = Boolean(telegramSaved?.bot_token_set && telegramSaved?.chat_id);

    box.style.display = connected ? '' : 'none';
    disconnectBtn.style.display = telegramSaved?.bot_token_set || telegramSaved?.chat_id ? '' : 'none';
    if (!connected) return;
    toggle.checked = telegramSaved.enabled;
    text.textContent = telegramSaved.enabled ? 'متصل · الإشعارات تعمل' : 'متصل · الإشعارات موقوفة';
    box.classList.toggle('paused', !telegramSaved.enabled);
}

async function setTelegramEnabled(enabled) {
    const toggle = document.getElementById('telegramEnabled');
    toggle.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                chat_id: telegramSaved.chat_id,
                message_thread_id: telegramSaved.message_thread_id,
                enabled
            })
        });
        if (!response.ok) throw await apiError(response, 'الخادم لم يحفظ الإعدادات.');
        telegramSaved = await response.json();
        showSettingsAlert(enabled ? 'تم تشغيل الإشعارات' : 'تم إيقاف الإشعارات', 'success');
    } catch (error) {
        showSettingsError(enabled ? 'لم تُشغَّل الإشعارات' : 'لم تُوقَف الإشعارات', error);
    } finally {
        toggle.disabled = false;
        renderTelegramStatus();
    }
}

async function disconnectTelegram() {
    const btn = document.getElementById('telegramDisconnectBtn');
    if (!armTwoTap(btn, 'اضغط مجددًا لحذف الرمز والمحادثة')) return;
    btn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {method: 'DELETE'});
        if (!response.ok) throw await apiError(response, 'الخادم لم يقطع الاتصال.');
        showSettingsAlert('تم قطع الاتصال وحذف بيانات البوت', 'success');
        await loadTelegramSettings();
    } catch (error) {
        showSettingsError('لم يُقطع الاتصال', error);
    } finally {
        btn.disabled = false;
    }
}

function updateTelegramTestButtonState() {
    const chatInput = document.getElementById('telegramChatId');
    const testBtn = document.getElementById('telegramTestBtn');
    if (!chatInput || !testBtn) return;
    testBtn.disabled = !chatInput.value.trim();
}

async function loadTelegramSettings() {
    const tokenInput = document.getElementById('telegramBotToken');
    const chatInput = document.getElementById('telegramChatId');
    const threadInput = document.getElementById('telegramThreadId');
    if (!tokenInput || !chatInput || !threadInput) return;

    try {
        const response = await fetch(`${API_BASE}/settings/telegram`);
        if (!response.ok) throw await apiError(response, 'الخادم لم يُرجع الإعدادات.');
        const data = await response.json();

        // Keep the token input empty — blank on save preserves the stored token.
        tokenInput.value = '';
        tokenInput.placeholder = data.bot_token_set
            ? (data.bot_token_masked || TELEGRAM_TOKEN_PLACEHOLDER)
            : TELEGRAM_TOKEN_PLACEHOLDER;

        chatInput.value = data.chat_id || '';
        threadInput.value = data.message_thread_id ?? '';
        // No saved address yet: offer the one this browser is using, saved with the form
        const appUrlInput = document.getElementById('telegramAppUrl');
        appUrlInput.value = data.app_url || browserAppUrl();
        document.getElementById('telegramAppUrlHint').textContent = data.app_url
            ? 'يفتح زر «افتح البطاقة» في كل إشعار البطاقة نفسها على هذا العنوان.'
            : 'هذا عنوان التطبيق في هذا المتصفح، ويُحفظ مع الإعدادات. يفتح زر «افتح البطاقة» في كل إشعار البطاقة نفسها عليه.';

        telegramSaved = data;
        renderTelegramStatus();
        updateTelegramTestButtonState();
    } catch (error) {
        logEvent('error', 'Failed to load Telegram settings', {error: error.message});
        showSettingsError('تعذّر تحميل إعدادات Telegram', error);
    }
}

function collectTelegramFormPayload() {
    const tokenInput = document.getElementById('telegramBotToken');
    const chatInput = document.getElementById('telegramChatId');
    const threadInput = document.getElementById('telegramThreadId');

    const threadRaw = (threadInput.value || '').trim();
    let threadId = null;
    if (threadRaw !== '') {
        const parsed = parseInt(threadRaw, 10);
        threadId = Number.isFinite(parsed) ? parsed : null;
    }

    return {
        bot_token: tokenInput.value || '',
        chat_id: (chatInput.value || '').trim(),
        message_thread_id: threadId,
        app_url: (document.getElementById('telegramAppUrl')?.value || '').trim()
    };
}

// Where this page is open (e.g. the Tailscale name), without the route
function browserAppUrl() {
    return `${window.location.origin}${window.location.pathname}`.replace(/\/$/, '');
}

async function saveTelegramSettings(event) {
    event.preventDefault();

    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const payload = collectTelegramFormPayload();

    if (submitBtn) submitBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw await apiError(response, 'الخادم لم يحفظ الإعدادات.');

        showSettingsAlert('تم حفظ الإعدادات', 'success');
        await loadTelegramSettings();
    } catch (error) {
        logEvent('error', 'Failed to save Telegram settings', {error: error.message});
        showSettingsError('لم تُحفظ الإعدادات', error);
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

async function sendTelegramTestMessage() {
    const payload = collectTelegramFormPayload();
    if (!payload.chat_id) {
        showSettingsAlert('أدخل معرّف المحادثة أولًا، ثم أرسل رسالة الاختبار.', 'warn');
        return;
    }

    const testBtn = document.getElementById('telegramTestBtn');
    if (testBtn) testBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/settings/telegram/test`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw await apiError(response, 'الخادم لم يُرسل الرسالة.');
        const data = await response.json().catch(() => null);

        if (data && data.ok) {
            showSettingsAlert('وصلت رسالة الاختبار. تحقق منها في Telegram.', 'success');
        } else {
            // Telegram's own wording ("Bad Request: chat not found") goes in the details
            showSettingsAlert('رفض Telegram رسالة الاختبار. تحقق من رمز البوت ومعرّف المحادثة.', 'error', 0,
                (data && data.error) || '');
        }
    } catch (error) {
        logEvent('error', 'Failed to send Telegram test message', {error: error.message});
        showSettingsError('لم تُرسل رسالة الاختبار', error);
    } finally {
        if (testBtn) testBtn.disabled = false;
        updateTelegramTestButtonState();
    }
}

function toggleTelegramTokenVisibility() {
    const tokenInput = document.getElementById('telegramBotToken');
    const toggle = document.getElementById('telegramTokenToggle');
    if (!tokenInput) return;
    const isHidden = tokenInput.type === 'password';
    tokenInput.type = isHidden ? 'text' : 'password';
    if (toggle) {
        toggle.textContent = isHidden ? 'إخفاء' : 'إظهار';
        toggle.setAttribute('aria-pressed', String(isHidden));
    }
}

function initSettingsPage() {
    if (!settingsListenersAttached) {
        const form = document.getElementById('telegramSettingsForm');
        const testBtn = document.getElementById('telegramTestBtn');
        const toggleBtn = document.getElementById('telegramTokenToggle');
        const chatInput = document.getElementById('telegramChatId');

        if (form) form.addEventListener('submit', saveTelegramSettings);
        if (testBtn) testBtn.addEventListener('click', sendTelegramTestMessage);
        if (toggleBtn) toggleBtn.addEventListener('click', toggleTelegramTokenVisibility);
        if (chatInput) chatInput.addEventListener('input', updateTelegramTestButtonState);
        document.getElementById('telegramEnabled')
            .addEventListener('change', event => setTelegramEnabled(event.target.checked));
        document.getElementById('telegramDisconnectBtn').addEventListener('click', disconnectTelegram);

        settingsListenersAttached = true;
    }

    loadTelegramSettings();
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
