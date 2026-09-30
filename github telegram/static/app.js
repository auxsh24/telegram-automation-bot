// ========== DOM Elements ==========
const $ = (id) => document.getElementById(id);
const themeToggle = $('btn-theme-toggle');
const themeColorMeta = document.querySelector('meta[name="theme-color"]');

// ========== Theme ==========
// The page background of each theme (mirrors --bg-page) so the browser chrome
// follows the dashboard, plus the key the inline head script reads.
const THEME_STORAGE_KEY = 'telegram-relay-theme';
const THEME_PAGE_COLOR = { light: '#edf2ef', dark: '#0a0e0d' };
const THEME_TRANSITION_MS = 320;
const THEME_ICON_ANIMATION_MS = 520;

let themeTransitionTimer = null;
let themeIconTimer = null;

function prefersReducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

function storedTheme() {
    try {
        const value = localStorage.getItem(THEME_STORAGE_KEY);
        return value === 'dark' || value === 'light' ? value : null;
    } catch (e) {
        return null;
    }
}

function systemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// The head script resolved the first paint from the same two sources; this
// mirrors that decision, and falls back to the system preference if the head
// script never ran (for example when storage is blocked).
const initialTheme = document.documentElement?.dataset.theme === 'dark'
    ? 'dark'
    : document.documentElement?.dataset.theme === 'light'
        ? 'light'
        : systemTheme();

function applyTheme(theme, persist = false, animate = false) {
    const root = document.documentElement;
    if (!root) return;

    const isDark = theme === 'dark';

    // Cross-fade the surfaces for a moment so switching themes never snaps.
    if (animate) {
        root.classList.add('theme-transition');
        window.clearTimeout(themeTransitionTimer);
        themeTransitionTimer = window.setTimeout(() => {
            root.classList.remove('theme-transition');
        }, THEME_TRANSITION_MS);

        if (themeToggle) {
            themeToggle.classList.remove('is-switching');
            void themeToggle.offsetWidth;
            themeToggle.classList.add('is-switching');
            window.clearTimeout(themeIconTimer);
            themeIconTimer = window.setTimeout(() => {
                themeToggle.classList.remove('is-switching');
            }, THEME_ICON_ANIMATION_MS);
        }
    }

    root.dataset.theme = isDark ? 'dark' : 'light';

    if (themeColorMeta) {
        themeColorMeta.setAttribute('content', isDark ? THEME_PAGE_COLOR.dark : THEME_PAGE_COLOR.light);
    }

    if (themeToggle) {
        const label = isDark ? 'Switch to light theme' : 'Switch to dark theme';
        themeToggle.setAttribute?.('aria-label', label);
        themeToggle.setAttribute?.('aria-pressed', String(isDark));
        themeToggle.title = label;
    }

    if (persist) {
        try {
            localStorage.setItem(THEME_STORAGE_KEY, isDark ? 'dark' : 'light');
        } catch (e) {
            // Theme switching still works for this page when storage is unavailable.
        }
    }
}

// The head script already resolved and painted a theme; re-applying it here
// keeps the toggle state, meta colour and icon in sync.
applyTheme(initialTheme);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const isDark = document.documentElement?.dataset.theme === 'dark';
        applyTheme(isDark ? 'light' : 'dark', true, true);
    });
}

// Follow the operating system while the user has not chosen a theme.
if (window.matchMedia) {
    const systemPreference = window.matchMedia('(prefers-color-scheme: dark)');
    const onSystemThemeChange = (event) => {
        if (storedTheme()) return; // an explicit choice always wins
        applyTheme(event.matches ? 'dark' : 'light', false, true);
    };
    if (systemPreference.addEventListener) systemPreference.addEventListener('change', onSystemThemeChange);
    else if (systemPreference.addListener) systemPreference.addListener(onSystemThemeChange);
}


const statusText = $('status-text');
const statusDot = $('status-dot');
const statusBadge = $('status-badge');
const workspaceNav = $('workspace-nav');
const monitorState = $('monitor-state');
const monitorStateLabel = $('monitor-state-label');
const authSection = $('auth-section');
const mainContent = $('main-content');
const authFeedback = $('auth-feedback');

const apiIdInput = $('api-id');
const apiHashInput = $('api-hash');
const phoneInput = $('phone');
const verificationCodeInput = $('verification-code');
const twofaPasswordInput = $('twofa-password');

const stepSetup = $('step-setup');
const stepPhone = $('step-phone');
const stepCode = $('step-code');
const step2fa = $('step-2fa');
const authProgress = $('auth-progress');
const authProgressItems = authProgress ? Array.from(authProgress.querySelectorAll('.auth-progress-step')) : [];

const btnSetup = $('btn-setup');
const btnSendCode = $('btn-send-code');
const btnVerifyCode = $('btn-verify-code');
const btnVerify2fa = $('btn-verify-2fa');
const btnBackPhone = $('btn-back-phone');
const btnBackCode = $('btn-back-code');
const btnBack2fa = $('btn-back-2fa');
const btnDisconnect = $('btn-disconnect');
const btnDisconnectMain = $('btn-disconnect-main');

const accountInfo = $('account-info');
const statusBar = $('status-bar');
const statusBarText = $('status-bar-text');
const statusBarIcon = $('status-bar-icon');

const statProcessed = $('stat-processed');
const statSent = $('stat-sent');
const statFailed = $('stat-failed');
const btnRefreshStats = $('btn-refresh-stats');

const btnAnalyze = $('btn-analyze');
const btnStart = $('btn-start');
const btnStop = $('btn-stop');
const actionMessage = $('action-message');

const btnTestSend = $('btn-test-send');
const testStatus = $('test-status');

const converterBotInput = $('converter-bot');
const channelsContainer = $('channels');
const btnAddChannel = $('btn-add-channel');
const addChannelInput = $('add-channel-input');
const duplicateTTLSelect = $('duplicate-ttl');
const retryAttemptsSelect = $('retry-attempts');
const retryDelaySelect = $('retry-delay');
const logRetentionDays = $('log-retention-days');
const autoResumeToggle = $('auto-resume');
const clearLogsBtn = $('btn-clear-logs');
const btnSaveSettings = $('btn-save-settings');
const settingsMessage = $('settings-message');

const activityContainer = $('activity');
const btnRefreshActivity = $('btn-refresh-activity');

const relayHealth = $('relay-health');
const relayAlert = $('relay-alert');
const healthConnection = $('health-connection');
const healthUptime = $('health-uptime');
const healthCounters = $('health-counters');
const healthLastSent = $('health-last-sent');

const offlineBanner = $('offline-banner');
const offlineBannerText = $('offline-banner-text');
const footerVersion = $('footer-version');

const confirmModal = $('confirm-modal');
const confirmTitle = $('confirm-title');
const confirmBody = $('confirm-body');
const confirmCancel = $('confirm-cancel');
const confirmAccept = $('confirm-accept');

// ========== State ==========
const MAX_ACTIVITY_ITEMS = 200;
const POLL_INTERVAL_MS = 2000;
// A backgrounded tab does not need a two-second feed, and the server is a
// single small instance.
const POLL_INTERVAL_SLOW_MS = 15000;
// How long a freshly polled log row keeps its "new" highlight.
const NEW_ROW_FLASH_MS = 1800;

let pollingTimer = null;
let lastLogId = 0;
let isPolling = false;
let isFetching = false;
let sessioncheckTimer = null;
let relayMonitoring = false;

if (workspaceNav) {
    workspaceNav.addEventListener('click', (event) => {
        const link = event.target.closest && event.target.closest('a[href^="#"]');
        if (!link) return;

        workspaceNav.querySelectorAll('a').forEach(item => {
            item.classList.remove('active');
            item.removeAttribute?.('aria-current');
        });
        link.classList.add('active');
        link.setAttribute?.('aria-current', 'location');
    });
}

// ========== Utilities ==========
function showFeedback(el, text, type) {
    if (!el) return;
    el.textContent = text;
    el.className = 'feedback-msg show ' + (type || '');
}

function clearFeedback(el) {
    if (!el) return;
    el.textContent = '';
    el.className = 'feedback-msg';
}

function showStep(step, focusInput = true) {
    [stepSetup, stepPhone, stepCode, step2fa].forEach(s => s && s.classList.remove('active'));
    step && step.classList.add('active');

    const activeIndex = step === stepPhone ? 1 : step === stepCode || step === step2fa ? 2 : 0;
    authProgressItems.forEach((item, index) => {
        item.classList.toggle('active', index === activeIndex);
        item.classList.toggle('complete', index < activeIndex);
        if (index === activeIndex) item.setAttribute?.('aria-current', 'step');
        else item.removeAttribute?.('aria-current');
    });

    if (step && focusInput) {
        const firstInput = step.querySelector('.form-input');
        if (firstInput) firstInput.focus();
    }
}

function setStatus(text, connected) {
    if (!statusText) return;
    statusText.textContent = text;
    if (statusDot) {
        statusDot.style.background = connected ? 'var(--success)' : 'var(--text-dim)';
    }
    if (statusBadge) {
        statusBadge.classList.toggle('is-online', !!connected);
        statusBadge.classList.toggle('is-offline', !connected);
    }
}

function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function levelClassFor(level) {
    if (level === 'error') return 'error';
    if (level === 'success') return 'success';
    if (level === 'warning') return 'warning';
    return 'info';
}

// Every button toggling disabled + loading in one place, so no button can be
// left permanently disabled when a request succeeds.
function updateRelayButtonAvailability() {
    const actionLoading = [btnStart, btnStop].some(btn => btn && btn.classList.contains('loading'));
    if (btnStart) btnStart.disabled = actionLoading || relayMonitoring;
    if (btnStop) btnStop.disabled = actionLoading || !relayMonitoring;
}

function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    const loading = !!isLoading;
    btn.classList.toggle('loading', loading);
    if (btn === btnStart || btn === btnStop) updateRelayButtonAvailability();
    else btn.disabled = loading;
}

// ========== Network Layer ==========
// Every request goes through apiFetch so a dropped connection, an expired
// session or a server restart produces one consistent message instead of a
// different raw error per call site.

let offlineSince = null;
let unauthorizedNotified = false;

function setOffline(isOffline) {
    if (offlineBanner) offlineBanner.hidden = !isOffline;

    if (isOffline && !offlineSince) {
        offlineSince = Date.now();
    } else if (!isOffline && offlineSince) {
        offlineSince = null;
        unauthorizedNotified = false;
    }
}

async function apiFetch(path, options = {}) {
    // A stalled request on a dead connection would otherwise hang the UI
    // until the browser gives up, which can take minutes.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeout || 15000);

    try {
        const response = await fetch(path, {
            ...options,
            signal: controller.signal,
            headers: {
                ...(options.body ? { 'Content-Type': 'application/json' } : {}),
                ...(options.headers || {})
            }
        });

        setOffline(false);

        if (response.status === 401) {
            // Basic auth failures make the browser show its own prompt, so the
            // dashboard only has to explain the lockout case.
            if (!unauthorizedNotified && response.headers.get('Retry-After')) {
                unauthorizedNotified = true;
                showStatusError('Too many failed sign-in attempts. Wait a few minutes and reload.');
            }
            throw new ApiError('Authentication required.', 401);
        }

        let data = null;

        try {
            data = await response.json();
        } catch (e) {
            // A non-JSON body on an error response is still an error, and the
            // status line is the most useful thing we can show.
            if (!response.ok) {
                throw new ApiError('Server returned an error (' + response.status + ').', response.status);
            }
            return null;
        }

        if (!response.ok) {
            throw new ApiError(
                data && (data.detail || data.error) ? (data.detail || data.error) : 'Request failed (' + response.status + ').',
                response.status
            );
        }

        return data;

    } catch (error) {
        if (error.name === 'AbortError') {
            setOffline(true);
            throw new ApiError('The server did not respond. It may be restarting.', 0);
        }

        // A failed connection is the one case that also flips the banner.
        if (error instanceof TypeError) {
            setOffline(true);
            throw new ApiError('Cannot reach the server. Check your connection.', 0);
        }

        throw error;

    } finally {
        clearTimeout(timeout);
    }
}

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
    }
}

function formatDuration(totalSeconds) {
    const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    if (seconds === 0) return '—';

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return days + 'd ' + hours + 'h';
    if (hours > 0) return hours + 'h ' + minutes + 'm';
    return minutes + 'm';
}

function formatTimestamp(unixSeconds) {
    if (!unixSeconds) return 'Never';
    try {
        return new Date(unixSeconds * 1000).toLocaleString();
    } catch (e) {
        return 'Unknown';
    }
}

function setHealthValue(el, text, state) {
    if (!el) return;
    el.textContent = text;
    el.classList.remove('is-ok', 'is-bad', 'is-warn');
    if (state) el.classList.add(state);
}

// The relay status carries connection health, runtime counters and the last
// error. Rendering all of it here means a silent failure is visible on the
// card instead of only in the log.
function renderRelayHealth(data) {
    if (!relayHealth || !data) return;

    relayHealth.hidden = false;

    setHealthValue(
        healthConnection,
        data.connected ? 'Connected' : 'Disconnected',
        data.connected ? 'is-ok' : 'is-bad'
    );

    setHealthValue(healthUptime, formatDuration(data.uptime_seconds));

    const sent = Number(data.sent_this_run) || 0;
    const failed = Number(data.failed_this_run) || 0;

    setHealthValue(
        healthCounters,
        sent + ' / ' + failed,
        failed > 0 ? 'is-warn' : null
    );

    setHealthValue(healthLastSent, formatTimestamp(data.last_sent_at));

    if (data.last_error && data.last_error.message) {
        if (relayAlert) {
            relayAlert.hidden = false;
            relayAlert.textContent = 'Last error: ' + data.last_error.message;
        }
    } else if (relayAlert) {
        relayAlert.hidden = true;
        relayAlert.textContent = '';
    }
}

// ========== Confirm Dialog ==========
// Replaces window.confirm: it does not block the event loop, and it can name
// the action and its consequence.

let confirmResolver = null;

function askConfirm({ title, body, confirmLabel }) {
    return new Promise((resolve) => {
        if (!confirmModal || !confirmTitle || !confirmBody) {
            resolve(window.confirm(body || ''));
            return;
        }

        confirmTitle.textContent = title || 'Are you sure?';
        confirmBody.textContent = body || '';
        if (confirmAccept) confirmAccept.textContent = confirmLabel || 'Confirm';

        confirmModal.hidden = false;
        confirmResolver = resolve;

        // Move focus into the dialog so keyboard and screen-reader users are
        // not left behind on the page behind the backdrop.
        (confirmCancel || confirmAccept)?.focus();
    });
}

function closeConfirm(result) {
    if (confirmModal) confirmModal.hidden = true;
    if (typeof confirmResolver === 'function') confirmResolver(result);
    confirmResolver = null;
}

if (confirmCancel) confirmCancel.addEventListener('click', () => closeConfirm(false));
if (confirmAccept) confirmAccept.addEventListener('click', () => closeConfirm(true));

if (confirmModal) {
    confirmModal.addEventListener('click', (event) => {
        // A click on the backdrop itself cancels; a click inside the panel
        // must not, otherwise the dialog closes while the user is reading it.
        if (event.target === confirmModal) closeConfirm(false);
    });
}

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && confirmModal && !confirmModal.hidden) {
        closeConfirm(false);
    }
});

// ========== Status Bar ==========
function showStatus(message, type) {
    if (!statusBar) return;
    statusBar.classList.remove('hidden', 'processing', 'success', 'error');
    statusBar.classList.add(type || 'processing');
    if (statusBarText) statusBarText.textContent = message || 'Processing...';
}

function hideStatus() {
    if (!statusBar) return;
    statusBar.classList.add('hidden');
    statusBar.classList.remove('processing', 'success', 'error');
}

function showStatusSuccess(message) {
    showStatus(message || 'Done!', 'success');
}

function showStatusError(message) {
    showStatus(message || 'Failed!', 'error');
}

// ========== Polling (optimized) ==========
// A hidden tab does not need a two-second feed, and a server that goes away
// should not be hammered by every open tab at once.
function startPolling() {
    if (isPolling && pollingTimer) return;
    isPolling = true;
    pollingTimer = setInterval(fetchNewLogs, document.hidden ? POLL_INTERVAL_SLOW_MS : POLL_INTERVAL_MS);
}

function stopPolling() {
    isPolling = false;
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
}

// Switching tabs changes how often polling is worth doing, so the interval is
// rebuilt instead of left at whatever the last visibility was.
document.addEventListener('visibilitychange', () => {
    if (!isPolling) return;
    if (pollingTimer) clearInterval(pollingTimer);
    pollingTimer = setInterval(fetchNewLogs, document.hidden ? POLL_INTERVAL_SLOW_MS : POLL_INTERVAL_MS);

    // Coming back to the tab should show current data immediately rather than
    // after the next tick.
    if (!document.hidden) {
        fetchNewLogs();
        loadStats();
    }
});

async function fetchNewLogs() {
    if (!isPolling || isFetching) return;
    isFetching = true;
    try {
        // Poll by log id: the server clock is the source of truth here, so a
        // skewed browser clock can never skip entries.
        const data = await apiFetch('/api/activity?after_id=' + lastLogId);
        if (data && data.logs && data.logs.length > 0) {
            if (typeof data.logs[0].id === 'number') lastLogId = data.logs[0].id;
            prependLogs(data.logs);
        }
    } catch (e) {
        // apiFetch already raised the offline banner if the server is gone.
    } finally {
        isFetching = false;
    }
}

// Batch DOM update for logs
function prependLogs(logs) {
    const frag = document.createDocumentFragment();
    const freshRows = [];

    // The API returns newest first, so appending in this order keeps the
    // newest entry directly under the header.
    for (const log of logs) {
        const item = document.createElement('div');
        // The level class tints failures and warnings; "is-new" plays the
        // entry flash for rows that arrive while the page is open.
        item.className = 'activity-item is-new ' + levelClassFor(log.level);

        const date = new Date(log.created_at * 1000).toLocaleTimeString();
        const level = escapeHtml(String(log.level || 'info'));
        const safeMessage = escapeHtml(log.message || '');

        item.innerHTML =
            '<span class="activity-time">' + escapeHtml(date) + '</span>' +
            '<span class="activity-level-pill ' + levelClassFor(log.level) + '">' + level + '</span>' +
            '<p class="activity-message">' + safeMessage + '</p>';

        freshRows.push(item);
        frag.appendChild(item);
    }

    // Insert after header
    const header = activityContainer.querySelector('.activity-header');
    if (header) {
        activityContainer.insertBefore(frag, header.nextSibling);
    } else {
        activityContainer.insertBefore(frag, activityContainer.firstChild);
    }

    // The flash is a one-off: dropping the class afterwards keeps row hover
    // and the level tint working normally.
    if (freshRows.length > 0) {
        window.setTimeout(() => {
            freshRows.forEach(item => item.classList.remove('is-new'));
        }, NEW_ROW_FLASH_MS);
    }

    // Trim the oldest rows (they sit at the end of the list), never the new ones.
    const items = activityContainer.querySelectorAll('.activity-item');
    if (items.length > MAX_ACTIVITY_ITEMS) {
        const excess = items.length - MAX_ACTIVITY_ITEMS;
        for (let i = 0; i < excess; i++) {
            items[items.length - 1 - i].remove();
        }
    }
}

// ========== Auth Functions ==========
async function setupCredentials() {
    const apiId = apiIdInput.value.trim();
    const apiHash = apiHashInput.value.trim();

    if (!apiId || !apiHash) {
        showFeedback(authFeedback, 'Both API ID and API Hash are required.', 'error');
        return;
    }

    if (!btnSetup) return;
    setButtonLoading(btnSetup, true);

    try {
        await apiFetch('/api/setup', {
            method: 'POST',
            body: JSON.stringify({ api_id: Number(apiId), api_hash: apiHash })
        });

        showFeedback(authFeedback, 'Credentials saved. Enter phone number.', 'success');
        setButtonLoading(btnSetup, false);
        showStep(stepPhone);
    } catch (e) {
        showFeedback(authFeedback, e.message, 'error');
        setButtonLoading(btnSetup, false);
    }
}

async function sendCode() {
    const phone = phoneInput.value.trim();
    if (!phone) {
        showFeedback(authFeedback, 'Phone number is required.', 'error');
        return;
    }

    if (!btnSendCode) return;
    setButtonLoading(btnSendCode, true);

    try {
        await apiFetch('/api/telegram/send-code', {
            method: 'POST',
            body: JSON.stringify({ phone: phone })
        });

        showFeedback(authFeedback, 'Code sent successfully. Enter verification code.', 'success');
        setButtonLoading(btnSendCode, false);
        showStep(stepCode);
    } catch (e) {
        showFeedback(authFeedback, e.message, 'error');
        setButtonLoading(btnSendCode, false);
    }
}

async function verifyCode() {
    const code = verificationCodeInput.value.trim();
    if (!code) {
        showFeedback(authFeedback, 'Verification code is required.', 'error');
        return;
    }

    if (!btnVerifyCode) return;
    setButtonLoading(btnVerifyCode, true);

    try {
        const data = await apiFetch('/api/telegram/verify-code', {
            method: 'POST',
            body: JSON.stringify({ code: code })
        });

        if (data && data.requires_2fa) {
            showFeedback(authFeedback, '2FA enabled. Enter your password.', 'success');
            setButtonLoading(btnVerifyCode, false);
            showStep(step2fa);
        } else {
            showFeedback(authFeedback, 'Authenticated successfully!', 'success');
            setButtonLoading(btnVerifyCode, false);
            showMainContent();
        }
    } catch (e) {
        showFeedback(authFeedback, e.message, 'error');
        setButtonLoading(btnVerifyCode, false);
    }
}

async function verify2fa() {
    const password = twofaPasswordInput.value.trim();
    if (!password) {
        showFeedback(authFeedback, '2FA password is required.', 'error');
        return;
    }

    if (!btnVerify2fa) return;
    setButtonLoading(btnVerify2fa, true);

    try {
        await apiFetch('/api/telegram/verify-2fa', {
            method: 'POST',
            body: JSON.stringify({ password: password })
        });

        showFeedback(authFeedback, 'Authenticated successfully!', 'success');
        setButtonLoading(btnVerify2fa, false);
        showMainContent();
    } catch (e) {
        showFeedback(authFeedback, e.message, 'error');
        setButtonLoading(btnVerify2fa, false);
    }
}

async function disconnectAccount() {
    if (!btnDisconnect && !btnDisconnectMain) return;

    const confirmed = await askConfirm({
        title: 'Disconnect Telegram account?',
        body: 'Monitoring stops immediately. The saved login stays on the server, so you can reconnect without a new verification code.',
        confirmLabel: 'Disconnect'
    });

    if (!confirmed) return;

    setButtonLoading(btnDisconnect, true);
    setButtonLoading(btnDisconnectMain, true);

    try {
        await apiFetch('/api/telegram/disconnect', { method: 'POST' });

        // Re-enable before the auth panel becomes visible again, otherwise the
        // buttons would stay disabled and spinning on screen.
        setButtonLoading(btnDisconnect, false);
        setButtonLoading(btnDisconnectMain, false);

        showFeedback(authFeedback, 'Disconnected. The saved session can be reused.', 'success');
        resetAuth();
    } catch (e) {
        showFeedback(authFeedback, e.message, 'error');
        setButtonLoading(btnDisconnect, false);
        setButtonLoading(btnDisconnectMain, false);
    }
}

function resetAuth() {
    stopPolling();
    hideStatus();
    stopSessionWatch();

    // Every auth button must be usable again after a session reset.
    setButtonLoading(btnSetup, false);
    setButtonLoading(btnSendCode, false);
    setButtonLoading(btnVerifyCode, false);
    setButtonLoading(btnVerify2fa, false);
    setButtonLoading(btnDisconnect, false);
    setButtonLoading(btnDisconnectMain, false);

    if (mainContent) mainContent.classList.add('hidden');
    if (authSection) authSection.classList.remove('hidden');
    setStatus('Not connected', false);
    clearFeedback(authFeedback);
    showStep(stepSetup);
    lastLogId = 0;
    if (apiIdInput) apiIdInput.value = '';
    if (apiHashInput) apiHashInput.value = '';
    if (phoneInput) phoneInput.value = '';
    if (verificationCodeInput) verificationCodeInput.value = '';
    if (twofaPasswordInput) twofaPasswordInput.value = '';
}

// ========== Session Watch ==========
function startSessionWatch() {
    stopSessionWatch();
    sessioncheckTimer = setInterval(checkSession, 30000);
}

function stopSessionWatch() {
    if (sessioncheckTimer) {
        clearInterval(sessioncheckTimer);
        sessioncheckTimer = null;
    }
}

// ========== Relay Status ==========
function setRelayMonitoring(monitoring) {
    relayMonitoring = !!monitoring;
    setStatus(relayMonitoring ? 'Live monitoring' : 'Telegram connected', true);

    if (monitorState) {
        monitorState.classList.toggle('is-running', relayMonitoring);
        monitorState.classList.toggle('is-idle', !relayMonitoring);
    }
    if (monitorStateLabel) {
        monitorStateLabel.textContent = relayMonitoring ? 'Live monitoring' : 'Monitoring paused';
    }

    setButtonLoading(btnStart, btnStart && btnStart.classList.contains('loading'));
    setButtonLoading(btnStop, btnStop && btnStop.classList.contains('loading'));
}

async function loadRelayStatus() {
    try {
        const data = await apiFetch('/api/relay/status');
        if (!data) return;
        renderRelayHealth(data);
        if (typeof data.monitoring === 'boolean') {
            setRelayMonitoring(data.monitoring);
        }
    } catch (e) {
        // apiFetch has already surfaced a connection problem.
    }
}

// ========== Main Content ==========
async function showMainContent() {
    if (authSection) authSection.classList.add('hidden');
    if (mainContent) mainContent.classList.remove('hidden');
    setStatus('Loading...', false);

    startSessionWatch();

    loadSettings();
    loadStats();

    // Load the feed before polling starts so the id cursor is initialized.
    await loadActivity();

    // Load the account last so the status badge ends up showing the real
    // monitoring state instead of being overwritten.
    await loadAccount();
    loadRelayStatus();

    startPolling();
}

// ========== Account ==========
async function loadAccount() {
    try {
        const data = await apiFetch('/api/telegram/account');

        if (!data) {
            setStatus('Not authenticated', false);
            if (accountInfo) {
                accountInfo.innerHTML = '<div class="account-placeholder is-error">Not authenticated</div>';
            }
            return;
        }

        const username = data.username ? '@' + data.username : data.first_name || 'Telegram account';
        const fullName = [data.first_name, data.last_name].filter(Boolean).join(' ') || username;

        // Profile names come from Telegram and can contain markup, so escape
        // everything before it goes into innerHTML.
        const safeId = escapeHtml(String(data.id === null || data.id === undefined ? '' : data.id));
        const safeName = escapeHtml(fullName);
        const safeUsername = escapeHtml(username);

        if (accountInfo) {
            accountInfo.innerHTML =
                '<div style="display:flex;flex-direction:column;gap:0;padding:4px 0;">' +
                    '<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">' +
                        '<span style="color:var(--text-muted);font-size:13px;">ID</span>' +
                        '<span style="color:var(--text-primary);font-size:13px;font-weight:500;text-align:right;">' + safeId + '</span>' +
                    '</div>' +
                    '<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">' +
                        '<span style="color:var(--text-muted);font-size:13px;">Name</span>' +
                        '<span style="color:var(--text-primary);font-size:13px;font-weight:500;text-align:right;">' + safeName + '</span>' +
                    '</div>' +
                    '<div style="display:flex;justify-content:space-between;padding:8px 0;">' +
                        '<span style="color:var(--text-muted);font-size:13px;">Username</span>' +
                        '<span style="color:var(--text-primary);font-size:13px;font-weight:500;text-align:right;">' + safeUsername + '</span>' +
                    '</div>' +
                '</div>';
        }

        setStatus('Telegram connected', true);
    } catch (e) {
        setStatus('Error loading account', false);
        if (accountInfo) {
            accountInfo.innerHTML = '<div class="account-placeholder is-error">' + escapeHtml(e.message) + '</div>';
        }
    }
}

// ========== Stats ==========
// Counters tick from their previous value to the new one instead of jumping.
// The tween is short enough to read as a tick rather than a loading state, and
// it is skipped completely when the user prefers reduced motion.
function renderStatValue(el, value) {
    if (!el) return;

    const next = Number(value);

    // Not a number (the "-" error state) is printed as-is.
    if (!Number.isFinite(next)) {
        el.textContent = '-';
        delete el.dataset.currentValue;
        return;
    }

    const previous = el.dataset.currentValue === undefined
        ? Number(el.textContent)
        : Number(el.dataset.currentValue);

    el.dataset.currentValue = String(next);

    if (!Number.isFinite(previous) || previous === next || prefersReducedMotion()) {
        el.textContent = next.toLocaleString();
        return;
    }

    const duration = 520;
    const startedAt = performance.now();

    // Re-adding the class restarts the colour flash from the beginning.
    el.classList.remove('is-bumping');
    void el.offsetWidth;
    el.classList.add('is-bumping');

    function step(now) {
        const progress = Math.min((now - startedAt) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(previous + (next - previous) * eased).toLocaleString();

        if (progress < 1) window.requestAnimationFrame(step);
        else el.textContent = next.toLocaleString();
    }

    window.requestAnimationFrame(step);
}

async function loadStats() {
    const statCard = statProcessed?.closest('.stat-card');
    const allCards = statCard ? statCard.parentElement?.querySelectorAll('.stat-card') : null;

    if (allCards && !allCards[0].classList.contains('refreshing')) {
        allCards.forEach(c => c.classList.add('refreshing'));
    }

    try {
        const data = await apiFetch('/api/stats');

        renderStatValue(statProcessed, data.processed || 0);
        renderStatValue(statSent, data.sent || 0);
        renderStatValue(statFailed, data.failed || 0);

        if (allCards) {
            allCards.forEach(c => {
                c.classList.remove('refreshing');
                c.classList.add('flash-updated');
                setTimeout(() => c.classList.remove('flash-updated'), 400);
            });
        }
    } catch (e) {
        renderStatValue(statProcessed, '-');
        renderStatValue(statSent, '-');
        renderStatValue(statFailed, '-');

        if (allCards) {
            allCards.forEach(c => c.classList.remove('refreshing'));
        }
    }
}

if (btnRefreshStats) btnRefreshStats.addEventListener('click', loadStats);

// ========== Relay Control ==========
async function analyzeToday() {
    if (!btnAnalyze) return;

    // A full scan of today's history can take minutes, so the UI must be clear
    // that this is not instant and that the button stays busy meanwhile.
    const confirmed = await askConfirm({
        title: 'Analyze today\'s messages?',
        body: 'Every message published today in the source channels is checked. Already-forwarded messages are skipped, and live monitoring starts afterwards.',
        confirmLabel: 'Start analysis'
    });

    if (!confirmed) return;

    setButtonLoading(btnAnalyze, true);
    showStatus("Analyzing today's messages...", 'processing');
    startPolling();

    try {
        const data = await apiFetch('/api/relay/analyze', {
            method: 'POST',
            // A long scan must not be cut off by the default request timeout.
            timeout: 10 * 60 * 1000
        });

        let message = 'Total: ' + data.total + ' | Sent: ' + data.sent + ' | Duplicates: ' + data.duplicate + ' | Failed: ' + data.failed;
        if (data.monitoring) message += ' | Live monitoring started';
        if (typeof data.monitoring === 'boolean') setRelayMonitoring(data.monitoring);

        showStatusSuccess(message);
        loadStats();
        loadRelayStatus();
        setTimeout(() => {
            hideStatus();
            setButtonLoading(btnAnalyze, false);
        }, 3000);
    } catch (e) {
        showStatusError(e.message);
        hideStatus();
        setButtonLoading(btnAnalyze, false);
    }
}

async function startMonitoring() {
    if (!btnStart) return;

    const confirmed = await askConfirm({
        title: 'Start live monitoring?',
        body: 'New messages in the configured source channels will be forwarded to your converter bot as soon as they are published.',
        confirmLabel: 'Start monitoring'
    });

    if (!confirmed) return;

    setButtonLoading(btnStart, true);
    showStatus('Starting live monitoring...', 'processing');
    startPolling();

    try {
        const data = await apiFetch('/api/relay/start', { method: 'POST' });

        showStatusSuccess(data.already_running ? 'Monitoring already running.' : 'Monitoring started.');
        setRelayMonitoring(true);
        loadRelayStatus();
        setTimeout(() => {
            hideStatus();
            setButtonLoading(btnStart, false);
        }, 2000);
    } catch (e) {
        showStatusError(e.message);
        setButtonLoading(btnStart, false);
    }
}

async function stopMonitoring() {
    if (!btnStop) return;

    const confirmed = await askConfirm({
        title: 'Stop live monitoring?',
        body: 'Messages published after this moment will not be forwarded until monitoring is started again.',
        confirmLabel: 'Stop monitoring'
    });

    if (!confirmed) return;

    setButtonLoading(btnStop, true);
    showStatus('Stopping monitoring...', 'processing');

    try {
        await apiFetch('/api/relay/stop', { method: 'POST' });

        showStatusSuccess('Monitoring stopped.');
        setRelayMonitoring(false);
        loadRelayStatus();
        setTimeout(() => {
            hideStatus();
            setButtonLoading(btnStop, false);
        }, 2000);
    } catch (e) {
        showStatusError(e.message);
        setButtonLoading(btnStop, false);
    }
}

if (btnAnalyze) btnAnalyze.addEventListener('click', analyzeToday);
if (btnStart) btnStart.addEventListener('click', startMonitoring);
if (btnStop) btnStop.addEventListener('click', stopMonitoring);

// ========== Test Send ==========
async function sendTestMessage() {
    if (!btnTestSend) return;
    setButtonLoading(btnTestSend, true);
    showStatus('Sending test message...', 'processing');
    startPolling();

    try {
        const data = await apiFetch('/api/relay/send-test', { method: 'POST' });

        if (data.success) {
            showStatusSuccess(data.message);
            setTimeout(() => {
                hideStatus();
                setButtonLoading(btnTestSend, false);
            }, 2000);
        } else {
            showStatusError(data.message || 'Test send failed.');
            hideStatus();
            setButtonLoading(btnTestSend, false);
        }
    } catch (e) {
        showStatusError(e.message);
        hideStatus();
        setButtonLoading(btnTestSend, false);
    }
}

if (btnTestSend) btnTestSend.addEventListener('click', sendTestMessage);

// ========== Settings ==========
function addChannel(value, focusInput) {
    if (!channelsContainer) return;
    value = value || '';
    const row = document.createElement('div');
    row.className = 'channel-row';
    row.innerHTML =
        '<input type="text" placeholder="@channel_username" aria-label="Source channel" value="' + escapeHtml(value) + '">' +
        '<button type="button" class="remove-channel" aria-label="Remove channel" title="Remove channel">&times;</button>';

    row.querySelector('.remove-channel').addEventListener('click', () => row.remove());
    channelsContainer.appendChild(row);

    // Only steal focus when the user added the channel themselves.
    const input = row.querySelector('input');
    if (input && focusInput !== false) {
        input.focus();
        input.select();
    }
}

function getChannels() {
    if (!channelsContainer) return [];
    return Array.from(channelsContainer.querySelectorAll('input'))
        .map(input => input.value.trim())
        .filter(Boolean);
}

async function loadSettings() {
    try {
        const data = await apiFetch('/api/settings');

        if (converterBotInput) converterBotInput.value = data.converter_bot || '';
        if (duplicateTTLSelect) duplicateTTLSelect.value = data.duplicate_ttl_days || 1;
        if (retryAttemptsSelect) retryAttemptsSelect.value = data.retry_attempts || 3;
        if (retryDelaySelect) retryDelaySelect.value = data.retry_delay_seconds || 2;
        if (logRetentionDays) {
            logRetentionDays.value = String(
                data.log_retention_days === null || data.log_retention_days === undefined
                    ? 1
                    : data.log_retention_days
            );
        }
        if (autoResumeToggle) autoResumeToggle.checked = !!data.auto_resume;

        if (channelsContainer) {
            channelsContainer.innerHTML = '';
            if (data.source_channels && data.source_channels.length > 0) {
                // false = do not steal focus while the list is rendered.
                data.source_channels.forEach(ch => addChannel(ch, false));
            } else {
                addChannel('', false);
            }
        }

        clearFeedback(settingsMessage);
    } catch (e) {
        showFeedback(settingsMessage, e.message || 'Could not load settings.', 'error');
    }
}

function handleAddChannel() {
    if (!addChannelInput || !channelsContainer) return;
    const value = addChannelInput.value.trim();
    if (value) {
        addChannel(value);
        addChannelInput.value = '';
    }
}

if (btnAddChannel) btnAddChannel.addEventListener('click', handleAddChannel);
if (addChannelInput) addChannelInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleAddChannel();
});

async function saveSettings() {
    if (!btnSaveSettings) return;

    const converterBot = (converterBotInput && converterBotInput.value || '').trim();

    if (!converterBot) {
        showFeedback(settingsMessage, 'Converter bot username is required.', 'error');
        if (converterBotInput) converterBotInput.focus();
        return;
    }

    setButtonLoading(btnSaveSettings, true);

    const payload = {
        converter_bot: converterBot,
        source_channels: getChannels(),
        duplicate_ttl_days: Number(duplicateTTLSelect ? duplicateTTLSelect.value : 1),
        retry_attempts: Number(retryAttemptsSelect ? retryAttemptsSelect.value : 3),
        retry_delay_seconds: Number(retryDelaySelect ? retryDelaySelect.value : 2),
        log_retention_days: Number(logRetentionDays ? logRetentionDays.value : 1),
        auto_resume: !!(autoResumeToggle && autoResumeToggle.checked)
    };

    try {
        const data = await apiFetch('/api/settings', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        // A running monitor keeps the channels it resolved when it started.
        const message = data.restart_required
            ? 'Settings saved. Restart monitoring so the new channels take effect.'
            : 'Settings saved.';

        showFeedback(settingsMessage, message, 'success');
        setButtonLoading(btnSaveSettings, false);
    } catch (e) {
        showFeedback(settingsMessage, e.message || 'Could not connect to server. Please try again.', 'error');
        setButtonLoading(btnSaveSettings, false);
    }
}

if (btnSaveSettings) btnSaveSettings.addEventListener('click', saveSettings);

// Clear old logs
async function clearOldLogs() {
    if (!clearLogsBtn) return;

    const confirmed = await askConfirm({
        title: 'Clear old log entries?',
        body: 'Activity log entries older than the retention period are deleted permanently. Statistics and forwarded messages are not affected.',
        confirmLabel: 'Clear logs'
    });

    if (!confirmed) return;

    setButtonLoading(clearLogsBtn, true);
    showStatus('Clearing old logs...', 'processing');

    try {
        const data = await apiFetch('/api/logs/cleanup', { method: 'POST' });

        const deleted = typeof data.deleted_count === 'number' ? data.deleted_count : 0;
        const retention = typeof data.retention_days === 'number' ? data.retention_days : 0;

        if (data.skipped || retention <= 0) {
            showStatusSuccess('Log retention is set to keep every log, so nothing was deleted.');
        } else {
            showStatusSuccess('Deleted ' + deleted + ' old log(s). Retention: ' + retention + ' day(s).');
        }

        loadActivity();
        setTimeout(() => {
            hideStatus();
            setButtonLoading(clearLogsBtn, false);
        }, 2500);
    } catch (e) {
        showStatusError(e.message);
        hideStatus();
        setButtonLoading(clearLogsBtn, false);
    }
}

if (clearLogsBtn) clearLogsBtn.addEventListener('click', clearOldLogs);

// ========== Activity Log ==========
function renderLogs(logs) {
    if (!activityContainer) return;

    if (!logs || logs.length === 0) {
        activityContainer.innerHTML =
            '<div class="activity-header">' +
                '<span>Time</span><span>Status</span><span>Message</span>' +
            '</div>' +
            '<div class="activity-empty" style="grid-column:1/-1;padding:32px 16px;">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:32px;height:32px;color:var(--text-muted);opacity:0.4;">' +
                    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
                    '<polyline points="14 2 14 8 20 8"/>' +
                    '<line x1="16" y1="13" x2="8" y2="13"/>' +
                    '<line x1="16" y1="17" x2="8" y2="17"/>' +
                '</svg>' +
                '<p style="font-size:13px;font-weight:500;color:var(--text-muted);margin:0;">No activity recorded yet</p>' +
                '<span style="font-size:12px;color:var(--text-dim);">Messages will appear here as they are processed</span>' +
            '</div>';
        return;
    }

    let itemsHtml = '';
    for (const log of logs) {
        const date = new Date(log.created_at * 1000).toLocaleTimeString();
        const level = escapeHtml(String(log.level || 'info'));
        const safeMsg = escapeHtml(log.message || '');
        itemsHtml +=
            '<div class="activity-item ' + levelClassFor(log.level) + '">' +
                '<span class="activity-time">' + escapeHtml(date) + '</span>' +
                '<span class="activity-level-pill ' + levelClassFor(log.level) + '">' + level + '</span>' +
                '<p class="activity-message">' + safeMsg + '</p>' +
            '</div>';
    }

    activityContainer.innerHTML =
        '<div class="activity-header">' +
            '<span>Time</span><span>Status</span><span>Message</span>' +
        '</div>' +
        itemsHtml;
}

async function loadActivity() {
    const activityEl = activityContainer;
    const isRefreshing = activityEl && activityEl.classList.contains('refreshing');

    if (activityEl && !isRefreshing) {
        activityEl.classList.add('refreshing');
    }

    try {
        const data = await apiFetch('/api/activity');
        const logs = data.logs || [];
        renderLogs(logs);

        if (logs.length > 0 && typeof logs[0].id === 'number') {
            lastLogId = logs[0].id;
        }

        if (activityEl) {
            activityEl.classList.remove('refreshing');
            activityEl.classList.add('flash-updated');
            setTimeout(() => activityEl.classList.remove('flash-updated'), 400);
        }
    } catch (e) {
        if (activityEl) {
            activityEl.classList.remove('refreshing');
        }

        activityContainer.innerHTML =
            '<div class="activity-header">' +
                '<span>Time</span><span>Status</span><span>Message</span>' +
            '</div>' +
            '<div class="activity-empty" style="grid-column:1/-1;padding:32px 16px;">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:32px;height:32px;color:var(--danger);opacity:0.6;">' +
                    '<circle cx="12" cy="12" r="10"/>' +
                    '<line x1="12" y1="16" x2="12" y2="12"/>' +
                    '<line x1="12" y1="8" x2="12.01" y2="8"/>' +
                '</svg>' +
                '<p style="font-size:13px;font-weight:500;color:var(--danger);margin:0;">Error loading activity</p>' +
                '<span style="font-size:12px;color:var(--text-dim);">Please try refreshing</span>' +
            '</div>';
    }
}

if (btnRefreshActivity) btnRefreshActivity.addEventListener('click', loadActivity);

// ========== Auth Event Listeners ==========
if (btnSetup) btnSetup.addEventListener('click', setupCredentials);
if (btnSendCode) btnSendCode.addEventListener('click', sendCode);
if (btnVerifyCode) btnVerifyCode.addEventListener('click', verifyCode);
if (btnVerify2fa) btnVerify2fa.addEventListener('click', verify2fa);
if (btnBackPhone) btnBackPhone.addEventListener('click', () => showStep(stepSetup));
if (btnBackCode) btnBackCode.addEventListener('click', () => showStep(stepPhone));
if (btnBack2fa) btnBack2fa.addEventListener('click', () => showStep(stepCode));
if (btnDisconnect) btnDisconnect.addEventListener('click', disconnectAccount);
if (btnDisconnectMain) btnDisconnectMain.addEventListener('click', disconnectAccount);

if (verificationCodeInput) verificationCodeInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') verifyCode();
});
if (twofaPasswordInput) twofaPasswordInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') verify2fa();
});
// The credentials and phone steps are the ones a keyboard user hits most, and
// both were click-only before.
if (apiIdInput) apiIdInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') setupCredentials();
});
if (apiHashInput) apiHashInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') setupCredentials();
});
if (phoneInput) phoneInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCode();
});

// ========== Init ==========
async function checkSession() {
    try {
        const status = await apiFetch('/api/status');

        if (!status || !status.telegram_authorized) {
            // Session expired — redirect to auth
            if (mainContent) mainContent.classList.add('hidden');
            if (authSection) authSection.classList.remove('hidden');
            setStatus('Session expired — please reconnect', false);
            showStep(stepSetup, false);

            // The auth buttons may still be disabled from the previous login,
            // which would make the first step impossible to use.
            setButtonLoading(btnSetup, false);
            setButtonLoading(btnSendCode, false);
            setButtonLoading(btnVerifyCode, false);
            setButtonLoading(btnVerify2fa, false);

            clearFeedback(authFeedback);
            showFeedback(authFeedback, 'Your session has expired. Please reconnect your Telegram account.', 'error');
            stopPolling();
            stopSessionWatch();
            hideStatus();
            lastLogId = 0;
            return false;
        }

        // The relay status doubles as the health check, so the uptime, the
        // connection state and the counters stay fresh without another timer.
        await loadRelayStatus();
        return true;
    } catch (e) {
        // A network blip is not a session expiry; the offline banner already
        // explains what happened, and the next tick will retry.
        return true;
    }
}

(async function init() {
    // The version is public and needs no credentials, so the footer never
    // disagrees with the running server.
    apiFetch('/api/health')
        .then((health) => {
            if (health && health.version && footerVersion) {
                footerVersion.textContent = 'v' + health.version;
            }
        })
        .catch(() => {});

    try {
        const status = await apiFetch('/api/status');

        if (status && status.telegram_authorized) {
            showMainContent();
        } else {
            setStatus('Not connected', false);
        }
    } catch (e) {
        setStatus('Connection error', false);
    }
})();
