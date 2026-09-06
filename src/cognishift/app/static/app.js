/**
 * COGNISHIFT // SECURE INDUSTRIAL OPERATIONS CONSOLE
 * Client Application Logic — 100% Offline & Strict CSP Compliant
 *
 * SECURITY GUARANTEES:
 * 1. Zero external requests / zero CDNs (strict localhost / 127.0.0.1 loopback).
 * 2. Zero hardcoded tokens or secrets in frontend code.
 * 3. Auth credentials stored strictly in sessionStorage (never localStorage).
 * 4. User identity, role, and workspace permissions resolved via GET /api/v1/auth/me.
 * 5. State machines driven exclusively by live backend database and run events.
 */

'use strict';

// Global Sovereign State
const STATE = {
    currentUser: null,       // { user_id, role, allowed_workspace_ids }
    workspaceId: 1,
    activeNav: 'dashboard',
    consolePaused: false,
    workflowStep: 0,
    activeRunId: null,
    currentTargetApproval: null,
    demoMode: false,
    conversationHistory: []  // Rolling multi-turn dialogue context
};

function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Central Authenticated API Client
const api = {
    getToken() {
        return sessionStorage.getItem('cognishift_token') || '';
    },
    setToken(token) {
        if (token) {
            sessionStorage.setItem('cognishift_token', token.trim());
        }
    },
    clearToken() {
        sessionStorage.removeItem('cognishift_token');
    },
    async fetch(url, options = {}) {
        const apiBase = (window.location.port === '8000' || window.location.protocol === 'file:') ? '' : 'http://127.0.0.1:8000';
        const targetUrl = url.startsWith('http') ? url : `${apiBase}${url}`;
        options.headers = options.headers || {};

        const token = this.getToken();
        if (token && !options.headers['Authorization']) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        const res = await fetch(targetUrl, options);
        if (res.status === 401) {
            this.clearToken();
            STATE.currentUser = null;
            updateAuthUI();
            appendConsole('AUTH:401', 'Credential not recognized by the current local credential store.', 'tag-network');
            openAuthModal();
        }
        return res;
    }
};

// Console Log Stream Management
function appendConsole(tag, message, tagClass = 'tag-system') {
    if (STATE.consolePaused) return;
    const stream = document.getElementById('consoleStream');
    if (!stream) return;

    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const timeStr = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

    const div = document.createElement('div');
    div.className = 'flex items-start gap-2 py-0.2';
    for (const [className, text] of [
        ['text-dark select-none', timeStr],
        [`console-tag ${tagClass}`, `[${tag}]`],
        ['text-slate-300 break-words whitespace-pre-wrap', message]
    ]) {
        const span = document.createElement('span');
        span.className = className;
        span.textContent = String(text);
        div.appendChild(span);
    }
    stream.appendChild(div);
    stream.scrollTop = stream.scrollHeight;
}

function toggleConsolePause() {
    STATE.consolePaused = !STATE.consolePaused;
    const btn = document.getElementById('consolePauseBtn');
    const badge = document.getElementById('consoleLiveBadge');
    if (btn && badge) {
        if (STATE.consolePaused) {
            btn.innerText = '▶ Resume';
            badge.className = 'bg-amber-tint text-amber px-2 py-0.5 rounded text-[10px] font-bold border border-amber flex items-center gap-1.5';
            badge.innerHTML = '⏸ Paused';
        } else {
            btn.innerText = '⏸ Pause';
            badge.className = 'bg-green-tint text-green px-2 py-0.5 rounded text-[10px] font-bold border border-green flex items-center gap-1.5';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-green beacon-active"></span> Live';
        }
    }
}

function clearConsole() {
    const stream = document.getElementById('consoleStream');
    if (stream) stream.innerHTML = '';
    STATE.conversationHistory = [];
}

// Live Clock
function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const d = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
    const t = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const el = document.getElementById('liveTimestamp');
    if (el) el.innerText = `${d} ${t} IST`;
}

// Authentication & Persona Management
function updateAuthUI() {
    const nameEl = document.getElementById('activeUserName');
    const roleEl = document.getElementById('activeUserRole');
    const dropdownUser = document.getElementById('dropdownUserId');
    const switchIdentity = document.getElementById('switchIdentityBtn');

    if (STATE.currentUser) {
        if (nameEl) nameEl.innerText = STATE.currentUser.user_id;
        if (dropdownUser) dropdownUser.innerText = STATE.currentUser.user_id;
        if (roleEl) {
            const role = (STATE.currentUser.role || 'operator').toUpperCase();
            roleEl.innerText = `ROLE: ${role}`;
            if (role === 'ADMINISTRATOR' || role === 'ADMIN') {
                roleEl.className = 'text-green text-[9px] font-semibold leading-tight';
            } else if (role === 'SUPERVISOR') {
                roleEl.className = 'text-amber text-[9px] font-semibold leading-tight';
            } else {
                roleEl.className = 'text-muted text-[9px] font-semibold leading-tight';
            }
        }
    } else {
        if (nameEl) nameEl.innerText = 'unauthenticated';
        if (roleEl) {
            roleEl.innerText = 'NO ACTIVE TOKEN';
            roleEl.className = 'text-red text-[9px] font-semibold leading-tight';
        }
    }
    if (switchIdentity) switchIdentity.classList.remove('hidden');
}

async function checkAuth() {
    const token = api.getToken();
    if (!token) {
        updateAuthUI();
        openAuthModal();
        return false;
    }

    try {
        const res = await api.fetch('/api/v1/auth/me');
        if (res.ok) {
            STATE.currentUser = await res.json();
            updateAuthUI();
            closeAuthModal();
            appendConsole('AUTH', `Active session verified: ${STATE.currentUser.user_id} (${(STATE.currentUser.role || '').toUpperCase()})`, 'tag-system');
            refreshDashboardData();
            return true;
        } else {
            api.clearToken();
            STATE.currentUser = null;
            updateAuthUI();
            openAuthModal();
            return false;
        }
    } catch (err) {
        console.error('Auth verification error:', err);
        openAuthModal();
        return false;
    }
}

function toggleTokenVisibility() {
    const input = document.getElementById('authModalTokenInput');
    const btn = document.getElementById('toggleTokenVisibilityBtn');
    if (!input || !btn) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = 'HIDE';
        btn.title = 'Mask token value';
    } else {
        input.type = 'password';
        btn.innerHTML = 'SHOW';
        btn.title = 'Reveal token value';
    }
}

async function pasteTokenFromClipboard() {
    const input = document.getElementById('authModalTokenInput');
    if (!input) return;
    try {
        if (navigator.clipboard && navigator.clipboard.readText) {
            const text = await navigator.clipboard.readText();
            if (text) {
                input.value = text.trim();
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.focus();
                return;
            }
        }
    } catch (e) {
        // Fallback to focusing if clipboard permission is not granted
    }
    input.focus();
    input.select();
}

function updateTokenCharCount() {
    const input = document.getElementById('authModalTokenInput');
    const countEl = document.getElementById('tokenCharCount');
    if (input && countEl) {
        const len = (input.value || '').length;
        countEl.innerText = `${len} character${len === 1 ? '' : 's'} detected`;
        if (len > 0) {
            countEl.className = 'text-green font-semibold font-mono';
        } else {
            countEl.className = 'text-dark font-semibold font-mono';
        }
    }
}

async function authenticateWithToken(rawToken) {
    const trimmed = (rawToken || '').trim();
    const errBox = document.getElementById('authModalError');
    const statusEl = document.getElementById('authModalStatus');
    const submitBtn = document.getElementById('authModalSubmitBtn');
    const spinner = document.getElementById('authSubmitSpinner');
    const btnText = document.getElementById('authSubmitBtnText');

    if (errBox) errBox.classList.add('hidden');

    if (!trimmed) {
        if (errBox) {
            errBox.innerText = 'Please enter or paste your sovereign Bearer token.';
            errBox.classList.remove('hidden');
        }
        if (statusEl) {
                statusEl.innerHTML = '[AUTH] <span class="text-amber font-semibold">Awaiting local bearer token</span>';
        }
        const input = document.getElementById('authModalTokenInput');
        if (input) input.focus();
        return false;
    }

    // Indicate authentication in progress
    if (statusEl) {
        statusEl.innerHTML = '[AUTH] <span class="text-amber font-semibold animate-pulse">Validating session...</span>';
    }
    if (submitBtn) submitBtn.disabled = true;
    if (spinner) spinner.classList.remove('hidden');
    if (btnText) btnText.innerText = 'Verifying Token...';

    try {
        const res = await fetch('/api/v1/auth/me', {
            headers: { 'Authorization': `Bearer ${trimmed}` }
        });

        if (res.ok) {
            const user = await res.json();
            api.setToken(trimmed);
            STATE.currentUser = user;
            updateAuthUI();

            if (statusEl) {
            statusEl.innerHTML = `[AUTH] <span class="text-green font-bold">Authenticated as ${user.user_id} / ${user.role.toUpperCase()}</span>`;
            }
            if (btnText) btnText.innerText = 'AUTHENTICATED';

            appendConsole('AUTH', `Authenticated successfully as ${user.user_id} (${user.role.toUpperCase()})`, 'tag-system');
            refreshDashboardData();

            setTimeout(() => {
                closeAuthModal();
                if (submitBtn) submitBtn.disabled = false;
                if (spinner) spinner.classList.add('hidden');
                if (btnText) btnText.innerText = 'AUTHENTICATE LOCAL SESSION';
            }, 250);

            return true;
        } else {
            api.clearToken();
            STATE.currentUser = null;
            updateAuthUI();
            const err = await res.json().catch(() => ({ detail: 'Authentication failed' }));
            if (statusEl) {
                statusEl.innerHTML = '[AUTH:401] <span class="text-red font-bold">Credential rejected</span>';
            }
            if (errBox) {
                errBox.innerText = res.status === 401
                    ? '[AUTH:401] Credential not recognized by current local credential store. This credential may be stale. Generate a fresh credential or verify that bootstrap and the running server use the same data directory.'
                    : `[AUTH:${res.status}] ${err.detail || 'Authentication failed'}`;
                errBox.classList.remove('hidden');
            }
            if (submitBtn) submitBtn.disabled = false;
            if (spinner) spinner.classList.add('hidden');
            if (btnText) btnText.innerText = 'AUTHENTICATE LOCAL SESSION';

            appendConsole(`AUTH:${res.status}`, err.detail || 'Credential rejected', 'tag-network');

            const input = document.getElementById('authModalTokenInput');
            if (input) {
                input.focus();
                input.select();
            }
            return false;
        }
    } catch (err) {
        if (statusEl) {
            statusEl.innerHTML = '[AUTH] <span class="text-red font-bold">Connection error</span>';
        }
        if (errBox) {
            errBox.innerText = `Local connection error: ${err.message}`;
            errBox.classList.remove('hidden');
        }
        if (submitBtn) submitBtn.disabled = false;
        if (spinner) spinner.classList.add('hidden');
        if (btnText) btnText.innerText = 'AUTHENTICATE LOCAL SESSION';
        return false;
    }
}

function logout() {
    api.clearToken();
    STATE.currentUser = null;
    updateAuthUI();
    appendConsole('AUTH', 'Sovereign session terminated. Credentials purged from sessionStorage.', 'tag-system');
    openAuthModal();
}

function openAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.classList.remove('hidden');

    const statusEl = document.getElementById('authModalStatus');
    if (statusEl) {
        statusEl.innerHTML = '[AUTH] <span class="text-amber font-semibold">Awaiting local identity</span>';
    }

    const errBox = document.getElementById('authModalError');
    if (errBox) errBox.classList.add('hidden');

    const input = document.getElementById('authModalTokenInput');
    const toggleBtn = document.getElementById('toggleTokenVisibilityBtn');
    if (input) {
        input.type = 'password';
        if (toggleBtn) {
            toggleBtn.innerHTML = 'SHOW';
            toggleBtn.title = 'Reveal token value';
        }
        updateTokenCharCount();
        setTimeout(() => input.focus(), 60);
    }

    loadAuthenticationOptions();
}

function closeAuthModal() {
    if (!STATE.currentUser) return; // Prevent closing if not authenticated
    const modal = document.getElementById('authModal');
    if (modal) modal.classList.add('hidden');
    const errBox = document.getElementById('authModalError');
    if (errBox) errBox.classList.add('hidden');
}

async function loadAuthenticationOptions() {
    const demoSection = document.getElementById('demoPersonaSection');
    const demoBadge = document.getElementById('demoModeBadge');
    const manualDetails = document.getElementById('manualAuthDetails');
    try {
        const res = await fetch('/api/v1/auth/demo-status');
        if (res.ok) {
            const status = await res.json();
            STATE.demoMode = Boolean(status.enabled);
        }
    } catch (e) {
        STATE.demoMode = false;
    }
    if (demoSection) demoSection.classList.toggle('hidden', !STATE.demoMode);
    if (demoBadge) demoBadge.classList.toggle('hidden', !STATE.demoMode);
    if (manualDetails) manualDetails.open = !STATE.demoMode;
    updateAuthUI();
}

async function authenticateDemoPersona(personaId) {
    const statusEl = document.getElementById('authModalStatus');
    const errBox = document.getElementById('authModalError');
    if (statusEl) statusEl.innerHTML = '[AUTH] <span class="text-amber font-semibold animate-pulse">Creating local demo session...</span>';
    if (errBox) errBox.classList.add('hidden');
    document.querySelectorAll('[data-persona]').forEach(button => { button.disabled = true; });

    try {
        const sessionResponse = await fetch('/api/v1/auth/demo-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ persona_id: personaId })
        });
        if (!sessionResponse.ok) {
            const error = await sessionResponse.json().catch(() => ({ detail: 'Demo session rejected' }));
            throw new Error(error.detail || 'Demo session rejected');
        }
        const session = await sessionResponse.json();
        api.setToken(session.session_token);
        const profileResponse = await fetch('/api/v1/auth/me', {
            headers: { 'Authorization': `Bearer ${api.getToken()}` }
        });
        if (!profileResponse.ok) throw new Error('Ephemeral session could not be verified');

        STATE.currentUser = await profileResponse.json();
        updateAuthUI();
        if (statusEl) statusEl.innerHTML = `[AUTH] <span class="text-green font-bold">Authenticated as ${STATE.currentUser.user_id} / ${STATE.currentUser.role.toUpperCase()}</span>`;
        appendConsole('AUTH', `Session changed: ${STATE.currentUser.user_id}`, 'tag-system');
        const dd = document.getElementById('userDropdown');
        if (dd) dd.classList.add('hidden');
        switchNav(STATE.activeNav);
        setTimeout(closeAuthModal, 200);
        return true;
    } catch (error) {
        api.clearToken();
        STATE.currentUser = null;
        updateAuthUI();
        if (errBox) {
            errBox.innerText = `[AUTH] ${error.message}`;
            errBox.classList.remove('hidden');
        }
        return false;
    } finally {
        document.querySelectorAll('[data-persona]').forEach(button => { button.disabled = false; });
    }
}

function toggleUserDropdown() {
    const dd = document.getElementById('userDropdown');
    if (dd) dd.classList.toggle('hidden');
}

// Navigation Switcher
function switchNav(viewName) {
    STATE.activeNav = viewName;
    const views = ['dashboard', 'workspaces', 'documents', 'agents', 'approvals', 'artifacts', 'audit', 'sandbox', 'sovereignty'];
    views.forEach(v => {
        const el = document.getElementById(`view-${v}`);
        const btn = document.getElementById(`nav-${v}`);
        if (el) el.classList.add('hidden');
        if (btn) btn.classList.remove('active');
    });

    const targetView = document.getElementById(`view-${viewName}`);
    const targetBtn = document.getElementById(`nav-${viewName}`);
    const globalCommandDock = document.getElementById('globalCommandDock');
    if (targetView) targetView.classList.remove('hidden');
    if (targetBtn) targetBtn.classList.add('active');
    if (globalCommandDock) globalCommandDock.classList.toggle('hidden', viewName === 'dashboard');

    if (viewName === 'dashboard') refreshDashboardData();
    if (viewName === 'workspaces') loadWorkspacesView();
    if (viewName === 'documents') loadDocumentsView();
    if (viewName === 'agents') loadAgentsView();
    if (viewName === 'approvals') loadApprovalsView();
    if (viewName === 'artifacts') loadArtifactsView();
    if (viewName === 'audit') loadAuditView();
    if (viewName === 'sandbox') loadSandboxView();
    if (viewName === 'sovereignty') loadSovereigntyView();
}

// Dynamic Route-Aware Workflow Stepper Controller
function resetWorkflowStepper() {
    STATE.workflowStep = 0;
    const container = document.getElementById('workflowStepperContainer');
    if (container) {
        container.className = 'grid grid-cols-8 gap-1.5 items-center font-mono text-[10px] select-none py-1';
        const defaultStages = [
            { id: 1, name: '1 UPLOAD', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>' },
            { id: 2, name: '2 OCR', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>' },
            { id: 3, name: '3 VISION', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>' },
            { id: 4, name: '4 RETRIEVE', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>' },
            { id: 5, name: '5 REASON', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>' },
            { id: 6, name: '6 APPROVAL', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>' },
            { id: 7, name: '7 ACTION', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' },
            { id: 8, name: '8 ARTIFACT', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>' }
        ];
        container.innerHTML = defaultStages.map(st => `
            <div id="step-${st.id}" class="step-card step-pending">
                <div class="flex items-center gap-1 text-slate-400 font-semibold mb-1">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">${st.icon}</svg>
                    <span>${st.name}</span>
                </div>
                <div class="text-[9px] text-dark">Pending</div>
            </div>
        `).join('');
    }
    const prog = document.getElementById('stepProgressBar');
    const progText = document.getElementById('stepProgressText');
    if (prog) prog.style.width = '0%';
    if (progText) progText.innerHTML = '<b class="text-muted">0 / 8</b> steps completed';

    const badge = document.getElementById('workflowStatusBadge');
    const est = document.getElementById('stepEstimateText');
    if (badge) {
        badge.className = 'bg-surface text-muted border border-subtle px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase';
        badge.innerText = 'STANDBY';
    }
    if (est) est.innerHTML = '<svg class="w-3 h-3 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> System Ready';
}

function renderWorkflowStepper(run) {
    if (!run) return;
    const container = document.getElementById('workflowStepperContainer');
    if (!container) return;

    let steps = [];
    if (run.structured_plan) {
        try {
            const plan = typeof run.structured_plan === 'string' ? JSON.parse(run.structured_plan) : run.structured_plan;
            if (plan && Array.isArray(plan.steps) && plan.steps.length > 0) {
                steps = plan.steps;
            }
        } catch (e) {
            console.error('Error parsing plan:', e);
        }
    }

    if (steps.length === 0) {
        return;
    }

    const total = steps.length;
    let completedCount = 0;
    let skippedCount = 0;
    let hasRunning = false;
    let hasPaused = false;
    let hasFailed = false;

    steps.forEach(s => {
        if (s.status === 'completed') completedCount++;
        else if (s.status === 'skipped') skippedCount++;
        else if (s.status === 'running') hasRunning = true;
        else if (s.status === 'waiting_for_approval') hasPaused = true;
        else if (s.status === 'failed') hasFailed = true;
    });

    const cols = Math.min(Math.max(total, 2), 8);
    container.className = `grid grid-cols-${cols} gap-1.5 items-center font-mono text-[10px] select-none py-1`;
    container.innerHTML = '';

    steps.forEach(s => {
        let shortLabel = `${s.id} STEP`;
        const desc = (s.description || '').toUpperCase();
        if (desc.includes('ROUTE')) shortLabel = `${s.id} ROUTE`;
        else if (desc.includes('RETRIEVE') || desc.includes('KNOWLEDGE')) shortLabel = `${s.id} RETRIEVE`;
        else if (desc.includes('RESOLVE')) shortLabel = `${s.id} RESOLVE`;
        else if (desc.includes('READ')) shortLabel = `${s.id} READ`;
        else if (desc.includes('PREPARE')) shortLabel = `${s.id} PREPARE`;
        else if (desc.includes('EXECUTE')) shortLabel = `${s.id} EXECUTE`;
        else if (desc.includes('PROPOSE')) shortLabel = `${s.id} PROPOSE`;
        else if (desc.includes('POLICY') || desc.includes('EVALUATE')) shortLabel = `${s.id} POLICY`;
        else if (desc.includes('APPROVAL') || desc.includes('FOUR-EYES')) shortLabel = `${s.id} APPROVAL`;
        else if (desc.includes('REASON') || desc.includes('SYNTHESIZE DIRECT') || desc.includes('ANALYZE')) shortLabel = `${s.id} REASON`;
        else if (desc.includes('ANSWER') || desc.includes('PRESENT') || desc.includes('DELIVER') || desc.includes('CONFIRM')) shortLabel = `${s.id} ANSWER`;
        else if (desc.includes('NAVIGAT')) shortLabel = `${s.id} NAV`;
        else {
            const firstWord = desc.split(' ')[0];
            shortLabel = `${s.id} ${firstWord}`;
        }

        let cardClass = 'step-card step-pending';
        let iconHtml = '';
        let headerClass = 'flex items-center gap-1 text-slate-400 font-semibold mb-1';
        let statusText = 'Pending';
        let statusClass = 'text-[9px] text-dark';

        if (s.status === 'completed') {
            cardClass = 'step-card step-completed';
            iconHtml = '<span class="step-indicator-check text-green font-bold mr-1">✓</span>';
            headerClass = 'flex items-center gap-1 text-green font-bold mb-1';
            statusText = 'Completed';
            statusClass = 'text-[9px] text-muted';
        } else if (s.status === 'running') {
            cardClass = 'step-card step-running';
            iconHtml = '<span class="step-indicator-spinner mr-1"></span>';
            headerClass = 'flex items-center gap-1 text-amber font-bold mb-1';
            statusText = 'In Progress';
            statusClass = 'text-[9px] text-amber font-medium';
        } else if (s.status === 'waiting_for_approval') {
            cardClass = 'step-card step-running border-amber';
            iconHtml = '<span class="text-amber font-bold mr-1">!</span>';
            headerClass = 'flex items-center gap-1 text-amber font-bold mb-1';
            statusText = 'Waiting Approval';
            statusClass = 'text-[9px] text-amber font-medium';
        } else if (s.status === 'failed') {
            cardClass = 'step-card border-red bg-red-tint/30';
            iconHtml = '<span class="text-red font-bold mr-1">✕</span>';
            headerClass = 'flex items-center gap-1 text-red font-bold mb-1';
            statusText = 'Failed';
            statusClass = 'text-[9px] text-red font-medium';
        } else if (s.status === 'skipped') {
            cardClass = 'step-card opacity-60 border-slate-700 bg-slate-900/40';
            iconHtml = '<span class="text-muted font-bold mr-1">~</span>';
            headerClass = 'flex items-center gap-1 text-slate-500 font-normal mb-1';
            statusText = 'Skipped';
            statusClass = 'text-[9px] text-slate-500 italic';
        }

        const card = document.createElement('div');
        card.id = `step-${s.id}`;
        card.className = cardClass;
        card.innerHTML = `
            <div class="${headerClass}">
                ${iconHtml}
                <span>${shortLabel}</span>
            </div>
            <div class="${statusClass}">${statusText}</div>
        `;
        container.appendChild(card);
    });

    const prog = document.getElementById('stepProgressBar');
    const progText = document.getElementById('stepProgressText');
    const percent = Math.min(100, Math.round(((completedCount + skippedCount) / total) * 100));
    if (prog) prog.style.width = `${percent}%`;
    if (progText) {
        let skipNote = skippedCount > 0 ? ` <span class="text-slate-500">(${skippedCount} skipped)</span>` : '';
        progText.innerHTML = `<b class="${completedCount > 0 ? 'text-green' : 'text-muted'}">${completedCount} / ${total}</b> steps completed${skipNote}`;
    }

    const badge = document.getElementById('workflowStatusBadge');
    const est = document.getElementById('stepEstimateText');
    if (badge) {
        if (run.status === 'paused' || hasPaused) {
            badge.className = 'bg-amber-tint text-amber border border-amber px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase';
            badge.innerText = 'PAUSED (AWAITING APPROVAL)';
            if (est) est.innerHTML = '<svg class="w-3 h-3 text-amber" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg> Interlock Active';
        } else if (run.status === 'completed' || (!hasRunning && completedCount + skippedCount === total)) {
            badge.className = 'bg-green-tint text-green border border-green px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase';
            badge.innerText = 'COMPLETED';
            if (est) est.innerHTML = '<svg class="w-3 h-3 text-green" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Workflow Done';
        } else if (run.status === 'failed' || hasFailed) {
            badge.className = 'bg-red-tint text-red border border-red px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase';
            badge.innerText = 'FAILED';
            if (est) est.innerHTML = '<svg class="w-3 h-3 text-red" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg> Execution Error';
        } else {
            badge.className = 'bg-green-tint text-green border border-green px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase';
            badge.innerText = 'ACTIVE WORKFLOW';
            if (est) est.innerHTML = '<svg class="w-3 h-3 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> In Progress';
        }
    }
}

function setWorkflowStep(stepNum) {
    STATE.workflowStep = stepNum;
}

// Active run polling with duplicate suppression
let activePollTimer = null;
const seenRunEventIds = new Set();

async function startRunPolling(runId, userCmd = null) {
    if (activePollTimer) clearInterval(activePollTimer);
    STATE.activeRunId = runId;

    async function checkRunStatus() {
        try {
            const [runRes, eventsRes] = await Promise.all([
                api.fetch(`/api/v1/runs/${runId}`),
                api.fetch(`/api/v1/runs/${runId}/events`)
            ]);

            if (eventsRes.ok) {
                const events = await eventsRes.json();
                events.forEach(e => {
                    if (!seenRunEventIds.has(e.id)) {
                        seenRunEventIds.add(e.id);
                        let tag = 'EXEC';
                        let tagClass = 'tag-tool';
                        const type = (e.event_type || '').toLowerCase();
                        if (type.includes('retrieval') || type.includes('rag')) {
                            tag = 'RAG'; tagClass = 'tag-rag'; setWorkflowStep(4);
                        } else if (type.includes('model') || type.includes('generation') || type.includes('reason')) {
                            tag = 'REASON'; tagClass = 'tag-reason'; setWorkflowStep(5);
                        } else if (type.includes('approval') || type.includes('interlock')) {
                            tag = 'POLICY'; tagClass = 'tag-policy'; setWorkflowStep(6);
                        } else if (type.includes('action') || type.includes('tool')) {
                            tag = 'ACTION'; tagClass = 'tag-tool'; setWorkflowStep(7);
                        } else if (type.includes('artifact')) {
                            tag = 'ARTIFACT'; tagClass = 'tag-done'; setWorkflowStep(8);
                        } else if (type.includes('completed')) {
                            tag = 'DONE'; tagClass = 'tag-done'; setWorkflowStep(8);
                        } else if (type.includes('failed') || type.includes('error')) {
                            tag = 'ERROR'; tagClass = 'tag-network';
                        }
                        appendConsole(tag, e.message, tagClass);
                    }
                });
            }

            if (runRes.ok) {
                const run = await runRes.json();
                renderWorkflowStepper(run);
                if (run.status === 'paused') {
                    clearInterval(activePollTimer);
                    activePollTimer = null;
                    appendConsole('ACTION PROPOSAL', `HIGH-RISK action proposed: ${run.result_text}`, 'tag-policy');
                    appendConsole('POLICY', 'Action paused awaiting Four-Eyes supervisor interlock authorization.', 'tag-policy');
                    refreshDashboardData();
                } else if (run.status === 'completed') {
                    renderWorkflowStepper(run);
                    clearInterval(activePollTimer);
                    activePollTimer = null;
                    if (run.result_text) {
                        if (userCmd) {
                            STATE.conversationHistory.push({ role: 'user', text: userCmd });
                            STATE.conversationHistory.push({ role: 'assistant', text: run.result_text });
                            if (STATE.conversationHistory.length > 6) {
                                STATE.conversationHistory = STATE.conversationHistory.slice(-6);
                            }
                        }
                        if (run.result_text.startsWith('Goal Execution Summary:') || run.result_text.startsWith('Execution encountered failures')) {
                            appendConsole('EXECUTION SUMMARY', run.result_text, 'tag-done');
                        } else {
                            appendConsole('ASSISTANT', run.result_text, 'tag-done');
                        }
                    }
                    if (run.sources_used && !run.sources_used.startsWith('None')) {
                        appendConsole('CITATIONS', run.sources_used, 'tag-rag');
                    }
                    refreshDashboardData();
                    if (STATE.activeNav === 'artifacts') loadArtifactsView();
                } else if (run.status === 'failed') {
                    clearInterval(activePollTimer);
                    activePollTimer = null;
                    appendConsole('ERROR', `Run #${run.id} failed: ${run.error_message || 'Model protocol failure'}`, 'tag-network');
                    refreshDashboardData();
                }
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }

    await checkRunStatus();
    activePollTimer = setInterval(checkRunStatus, 1500);
}

// Console Command Dispatcher
function handleConsoleControlCommand(command) {
    const normalized = (command || '').toLowerCase().replace(/\s+/g, ' ').replace(/[\.\?\!\,\;]+$/, '').trim();

    // 1. Strict isolated greeting (only if ENTIRE input is the greeting)
    const GREETINGS = new Set(['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']);
    if (GREETINGS.has(normalized)) {
        const identity = STATE.currentUser ? STATE.currentUser.user_id : 'operator';
        appendConsole(
            'ASSISTANT',
            `Hello ${identity}. I can open and control CogniShift views, explain system status, or dispatch a free-form task to the local agent. Type "help" for examples.`,
            'tag-done'
        );
        return true;
    }

    // 2. Deterministic Help & Status Commands
    if (normalized === '/help' || normalized === 'help' || normalized === 'available commands') {
        appendConsole(
            'ASSISTANT',
            'Try: what can you do, open documents, upload a document, show agents, show pending approvals, list artifacts, show audit logs, open sandbox, show sovereignty, system status, who am I, switch identity, analyze p101a, reset, or clear. Any other non-empty request is sent to the local agent.',
            'tag-system'
        );
        return true;
    }

    if (normalized === '/whoami' || normalized === 'whoami' || normalized === 'who am i' || normalized === 'my role') {
        const user = STATE.currentUser;
        appendConsole(
            'ASSISTANT',
            user
                ? `You are ${user.user_id} with role ${(user.role || 'operator').toUpperCase()}. Authorized workspaces: ${(user.allowed_workspace_ids || []).join(', ') || 'none'}.`
                : 'No local identity is authenticated. Opening sovereign authentication.',
            'tag-system'
        );
        if (!user) openAuthModal();
        return true;
    }

    if (normalized === '/status' || normalized === 'status' || normalized === 'system status' || normalized === 'is the system ready') {
        refreshDashboardData();
        appendConsole(
            'ASSISTANT',
            'Refreshing local readiness: LLM, OCR, vision, Docker isolation, approval queue, artifacts, and sovereignty telemetry.',
            'tag-system'
        );
        return true;
    }

    if (normalized === '/policy' || normalized === 'policy' || normalized === 'show policy' || normalized === 'security policy' || normalized === 'network policy') {
        appendConsole('POLICY', 'Active Policy: STRICT ZERO EGRESS | Blocked: public internet, OpenAI, Gemini | Allowed: local runtime 127.0.0.1 (Ollama, SQLite, Chroma)', 'tag-policy');
        return true;
    }

    if (normalized === '/switch' || normalized === 'switch identity' || normalized === 'switch user' || normalized === 'change user' || normalized === 'login') {
        openAuthModal();
        appendConsole('ASSISTANT', 'Opened local identity selection. No credential will leave this workstation.', 'tag-system');
        return true;
    }

    if (normalized === '/logout' || normalized === 'logout' || normalized === 'terminate session') {
        logout();
        return true;
    }

    // 3. Exact deterministic view navigation (ONLY if entire input matches command or alias)
    const EXACT_NAV_RULES = [
        { view: 'dashboard', label: 'dashboard', commands: ['/dashboard', 'dashboard', 'open dashboard', 'go to dashboard', 'overview', 'home'] },
        { view: 'workspaces', label: 'isolated workspaces', commands: ['/workspaces', 'workspaces', 'open workspaces', 'show workspaces', 'list workspaces'] },
        { view: 'documents', label: 'document ingestion and provenance', commands: ['/documents', 'documents', 'open documents', 'show documents', 'list documents', 'upload a document'] },
        { view: 'agents', label: 'agent orchestrators', commands: ['/agents', 'agents', 'open agents', 'show agents', 'list agents'] },
        { view: 'approvals', label: 'pending approvals', commands: ['/approvals', 'approvals', 'open approvals', 'show approvals', 'list approvals', 'show pending approvals'] },
        { view: 'artifacts', label: 'artifact vault', commands: ['/artifacts', 'artifacts', 'open artifacts', 'show artifacts', 'list artifacts'] },
        { view: 'audit', label: 'audit and traceability logs', commands: ['/audit', 'audit', 'audit logs', 'open audit', 'show audit', 'show audit logs', 'list audit logs'] },
        { view: 'sandbox', label: 'Docker sandbox', commands: ['/sandbox', 'sandbox', 'open sandbox', 'show sandbox'] },
        { view: 'sovereignty', label: 'sovereignty and network controls', commands: ['/sovereignty', 'sovereignty', 'open sovereignty', 'show sovereignty', 'network monitor'] }
    ];

    for (const rule of EXACT_NAV_RULES) {
        if (rule.commands.includes(normalized)) {
            switchNav(rule.view);
            appendConsole('ASSISTANT', `Opened ${rule.label}.`, 'tag-done');
            return true;
        }
    }

    return false;
}

async function executeConsoleCommand(inputId = 'consoleCmdInput') {
    const input = document.getElementById(inputId);
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    input.value = '';

    appendConsole('OPERATOR', cmd, 'tag-upload');

    const lower = cmd.toLowerCase();
    if (lower === 'clear') {
        clearConsole();
        return;
    }
    if (lower === 'reset') {
        resetWorkflowStepper();
        const titleEl = document.getElementById('workflowTitle');
        const idEl = document.getElementById('workflowIdPill');
        const timeEl = document.getElementById('workflowStartTime');
        if (titleEl) titleEl.innerText = 'Awaiting Operational Command';
        if (idEl) idEl.innerText = 'IDLE';
        if (timeEl) timeEl.innerHTML = 'Status: <b class="text-green">READY</b>';
        STATE.activeRunId = null;
        STATE.conversationHistory = [];
        appendConsole('SYSTEM', 'Console and workflow state reset to STANDBY.', 'tag-system');
        refreshDashboardData();
        return;
    }
    if (handleConsoleControlCommand(cmd)) {
        return;
    }

    appendConsole('AGENT', 'Sending request to local agent...', 'tag-system');
    appendConsole('MODEL', 'Local inference in progress...', 'tag-router');
    setWorkflowStep(3);
    const titleEl = document.getElementById('workflowTitle');
    const idEl = document.getElementById('workflowIdPill');
    const timeEl = document.getElementById('workflowStartTime');
    if (titleEl) titleEl.innerText = cmd.length > 35 ? cmd.slice(0, 35) + '...' : cmd;
    if (idEl) idEl.innerText = 'DISPATCHING';
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const nowTime = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    if (timeEl) timeEl.innerHTML = `Started: <b class="text-slate-300">${nowTime} IST</b>`;

    try {
        const payload = {
            workspace_id: STATE.workspaceId,
            agent_id: 1,
            input_text: cmd,
            user_id: STATE.currentUser ? STATE.currentUser.user_id : 'operator',
            conversation_history: (STATE.conversationHistory || []).map(h => ({
                role: h.role,
                content: h.text
            }))
        };

        const res = await api.fetch('/api/v1/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const run = await res.json();
            STATE.activeRunId = run.id;
            if (idEl) idEl.innerText = `RUN-${run.id}`;

            // Router Observability Badge
            if (run.routing_info) {
                const ri = run.routing_info;
                const method = ri.decision_method || (ri.confidence === null || ri.confidence === undefined ? 'RULE' : 'SEMANTIC');
                let badgeText = `Intent: ${ri.intent} | Decision: ${method}`;
                if (method === 'RULE') {
                    if (ri.references && ri.references.files && ri.references.files.length > 0) {
                        badgeText += ` | Reference: ${ri.references.files[0]}`;
                    } else if (ri.details && ri.details.target) {
                        badgeText += ` | Target: ${ri.details.target}`;
                    } else if (ri.details && ri.details.phrase) {
                        badgeText += ` | Phrase: ${ri.details.phrase}`;
                    }
                } else if (method === 'SEMANTIC') {
                    const simStr = ri.confidence !== null && ri.confidence !== undefined ? ` | Similarity: ${ri.confidence}` : '';
                    const marginStr = ri.margin !== null && ri.margin !== undefined ? ` | Margin: ${ri.margin}` : '';
                    badgeText += `${simStr}${marginStr}`;
                } else if (method === 'ABSTAIN') {
                    const candStr = ri.details && ri.details.candidate ? ` | Candidate: ${ri.details.candidate}` : '';
                    const reasonStr = ri.details && ri.details.reason ? ` | Reason: ${ri.details.reason}` : '';
                    badgeText += `${candStr}${reasonStr}`;
                }
                const ctxLabel = ri.intent === 'CONVERSATION' ? 'SKIPPED' : (ri.intent === 'ARTIFACT_INSPECTION' ? 'TARGETED' : 'STANDARD');
                badgeText += ` | Context: ${ctxLabel}`;
                appendConsole('ROUTER', badgeText, 'tag-router');
            }

            renderWorkflowStepper(run);
            if (run.status === 'paused') {
                appendConsole('ACTION PROPOSAL', `HIGH-RISK action proposed: ${run.result_text}`, 'tag-policy');
                appendConsole('POLICY', 'Action paused awaiting Four-Eyes supervisor interlock authorization.', 'tag-policy');
                refreshDashboardData();
            } else if (run.status === 'completed') {
                renderWorkflowStepper(run);
                if (run.result_text) {
                    STATE.conversationHistory.push({ role: 'user', text: cmd });
                    STATE.conversationHistory.push({ role: 'assistant', text: run.result_text });
                    if (STATE.conversationHistory.length > 8) {
                        STATE.conversationHistory = STATE.conversationHistory.slice(-8);
                    }
                    if (run.result_text.startsWith('Goal Execution Summary:') || run.result_text.startsWith('Execution encountered failures')) {
                        appendConsole('EXECUTION SUMMARY', run.result_text, 'tag-done');
                    } else {
                        appendConsole('ASSISTANT', run.result_text, 'tag-done');
                    }
                }
                if (run.sources_used && !run.sources_used.startsWith('None')) {
                    appendConsole('CITATIONS', run.sources_used, 'tag-rag');
                }
                refreshDashboardData();
            } else if (run.status === 'failed') {
                setWorkflowStep(0);
                appendConsole('ERROR', `Run #${run.id} failed: ${run.error_message || 'Model protocol failure'}`, 'tag-network');
                refreshDashboardData();
            } else {
                setWorkflowStep(4);
                startRunPolling(run.id, cmd);
            }
        } else {
            const err = await res.json().catch(() => ({ detail: 'Execution rejected' }));
            appendConsole('ERROR', err.detail || 'Execution rejected', 'tag-network');
            setWorkflowStep(0);
        }
    } catch (err) {
        appendConsole('NETWORK', 'Local connection error or engine busy: ' + err.message, 'tag-network');
        setWorkflowStep(0);
    }
}

// Modals Management
async function openApprovalModal(specificId = null) {
    const modal = document.getElementById('approvalModal');
    if (modal) modal.classList.remove('hidden');

    const errBox = document.getElementById('modalApprovalError');
    if (errBox) errBox.classList.add('hidden');

    const signerName = document.getElementById('modalSignerName');
    if (signerName) {
        const user = STATE.currentUser ? `${STATE.currentUser.user_id} (${STATE.currentUser.role.toUpperCase()})` : 'Unauthenticated';
        signerName.innerText = user;
    }

    function populateModal(target) {
        if (!target) return;
        STATE.currentTargetApproval = target;
        if (modal) modal.setAttribute('data-approval-id', target.id);
        const badge = document.getElementById('modalInterlockBadge');
        const equip = document.getElementById('modalEquipment');
        const actionEl = document.getElementById('modalAction');
        const justEl = document.getElementById('modalJustification');
        const fourEyesEl = document.getElementById('modalFourEyesStatus');

        if (badge) badge.innerText = `FOUR-EYES INTERLOCK #${target.id}`;
        if (actionEl) actionEl.innerText = target.request_reason || 'restart_component';
        if (justEl) justEl.innerText = `Parameters: ${target.parameters || '{}'} — Required Approvals: ${target.required_approvals || 1}`;

        if (target.reviewed_by) {
            if (fourEyesEl) {
                fourEyesEl.innerText = `Stage 1/2 Verified by ${target.reviewed_by} | Stage 2 Pending`;
                fourEyesEl.className = 'text-amber font-semibold';
            }
        } else {
            if (fourEyesEl) {
                fourEyesEl.innerText = `Stage 1/2 Review Required (Independent 2-stage verification)`;
                fourEyesEl.className = 'text-cyan font-semibold';
            }
        }
    }

    // Populate immediately if already available from dashboard state
    if (STATE.currentTargetApproval) {
        populateModal(STATE.currentTargetApproval);
    }

    try {
        const res = await api.fetch('/api/v1/approvals');
        if (res.ok) {
            const apprs = await res.json();
            const target = specificId ? apprs.find(a => a.id === specificId) : apprs[0];
            if (target) {
                populateModal(target);
            }
        }
    } catch (e) {
        console.error('Error fetching approval details:', e);
    }
}

function closeApprovalModal() {
    const modal = document.getElementById('approvalModal');
    if (modal) modal.classList.add('hidden');
    const errBox = document.getElementById('modalApprovalError');
    if (errBox) errBox.classList.add('hidden');
}

async function executeModalApproval(action, specificId = null) {
    const errBox = document.getElementById('modalApprovalError');
    let targetId = specificId || (STATE.currentTargetApproval ? STATE.currentTargetApproval.id : null);
    if (!targetId) {
        const modal = document.getElementById('approvalModal');
        if (modal && modal.getAttribute('data-approval-id')) {
            targetId = parseInt(modal.getAttribute('data-approval-id'), 10);
        }
    }
    if (!targetId) {
        const badge = document.getElementById('modalInterlockBadge');
        if (badge && badge.innerText) {
            const m = badge.innerText.match(/#(\d+)/);
            if (m) targetId = parseInt(m[1], 10);
        }
    }
    if (!targetId) {
        try {
            const res = await api.fetch('/api/v1/approvals');
            if (res.ok) {
                const apprs = await res.json();
                if (apprs.length > 0) {
                    STATE.currentTargetApproval = apprs[0];
                    targetId = apprs[0].id;
                }
            }
        } catch (e) {}
    }
    if (!targetId) {
        if (errBox) {
            errBox.innerText = 'POLICY: No pending approval selected or available';
            errBox.classList.remove('hidden');
        }
        appendConsole('POLICY', 'No pending approval selected', 'tag-network');
        return;
    }

    try {
        const res = await api.fetch(`/api/v1/approvals/${targetId}/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rejection_reason: `Operator ${STATE.currentUser?.user_id || 'manual'} review decision` })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Approval action failed' }));
            const detailMsg = err.detail || 'Approval request rejected by policy';
            if (errBox) {
                errBox.innerText = `${res.status === 403 ? '403 FORBIDDEN' : `ERROR (${res.status})`}: ${detailMsg}`;
                errBox.classList.remove('hidden');
            }
            appendConsole(res.status === 403 ? 'HITL-DENIED' : 'ERROR', `${res.status}: ${detailMsg}`, 'tag-network');
            return; // Never close modal silently on failure so operator/supervisor sees explicit error!
        }

        const updated = await res.json();
        closeApprovalModal();

        if (action === 'approve') {
            if (updated.status === 'approved') {
                appendConsole('HITL', `Stage 2/2 Authorization complete (${updated.reviewed_by_2 || STATE.currentUser?.user_id}). High-risk execution resumed!`, 'tag-done');
                setWorkflowStep(7);
                if (updated.run_id) {
                    startRunPolling(updated.run_id);
                }
            } else {
                appendConsole('HITL', `Stage 1/2 Verified by ${updated.reviewed_by}. Awaiting independent Stage 2 Authorizer sign-off.`, 'tag-policy');
                setWorkflowStep(6);
            }
        } else {
            appendConsole('HITL', `Action rejected by ${STATE.currentUser?.user_id || 'reviewer'}. Interlock remains safe.`, 'tag-network');
            setWorkflowStep(1);
        }
        refreshDashboardData();
        if (STATE.activeNav === 'approvals') loadApprovalsView();
    } catch (err) {
        if (errBox) {
            errBox.innerText = `NETWORK ERROR: ${err.message}`;
            errBox.classList.remove('hidden');
        }
        appendConsole('ERROR', `Network error during approval: ${err.message}`, 'tag-network');
    }
}

function previewArtifact(filename, hash = '', size = 0, type = '') {
    const title = document.getElementById('artifactModalTitle');
    const hashEl = document.getElementById('artifactModalHash');
    const info = document.getElementById('artifactModalInfo');
    const modal = document.getElementById('artifactModal');

    if (title) title.innerText = filename;
    if (hashEl) hashEl.innerText = hash || 'Computing SHA-256...';
    if (info) info.innerHTML = `Type: <b class="text-white">${(type || 'FILE').toUpperCase()}</b> | Size: <b class="text-white">${size} B</b> | Workspace: <b class="text-white">MRPL Operations (ID: 1)</b>`;
    if (modal) modal.classList.remove('hidden');
}

function closeArtifactModal() {
    const modal = document.getElementById('artifactModal');
    if (modal) modal.classList.add('hidden');
}

async function openProvenanceModal(sourceId = null) {
    const modal = document.getElementById('provenanceModal');
    if (modal) modal.classList.remove('hidden');
    const body = document.getElementById('provenanceModalBody');
    if (!body) return;
    body.innerHTML = '<div class="text-muted italic py-2">Querying local provenance records...</div>';

    try {
        let targetId = sourceId;
        if (!targetId) {
            const kRes = await api.fetch('/api/v1/knowledge?workspace_id=1');
            if (kRes.ok) {
                const docs = await kRes.json();
                if (docs.length > 0) targetId = docs[0].id;
            }
        }
        if (!targetId) {
            body.innerHTML = '<div class="text-muted italic py-2">No documents indexed in workspace yet.</div>';
            return;
        }

        const pagesRes = await api.fetch(`/api/v1/knowledge/${targetId}/pages`);
        if (pagesRes.ok) {
            const pages = await pagesRes.json();
            if (pages.length === 0) {
                body.innerHTML = '<div class="text-muted italic py-2">No OCR/Vision page extractions stored for this document.</div>';
                return;
            }
            body.innerHTML = '';
            pages.forEach(p => {
                const confText = p.ocr_confidence != null ? `${(p.ocr_confidence * 100).toFixed(1)}%` : (p.extraction_method === 'native' ? 'Native text (not OCR-scored)' : 'Unknown — review required');
                body.innerHTML += `
                    <div class="bg-card p-3 rounded border border-subtle space-y-1.5 font-mono">
                        <div class="flex justify-between items-center text-[10px]">
                            <span class="text-white font-bold">PAGE ${escapeHtml(p.page_number)}</span>
                            <span class="text-green uppercase font-bold text-[9px] bg-green-tint px-1.5 py-0.5 rounded border border-green">${escapeHtml(p.extraction_method)}</span>
                            <span class="text-cyan text-[10px]">Confidence: ${escapeHtml(confText)}</span>
                        </div>
                        <div class="ocr-page-text text-slate-300 text-[11px] bg-terminal p-2 rounded overflow-y-auto leading-relaxed select-text font-mono">
                            ${escapeHtml(p.text_content || '(No text content extracted — inspect the original page)')}
                        </div>
                    </div>
                `;
            });
        } else {
            body.innerHTML = '<div class="text-red py-2">Failed to load provenance records.</div>';
        }
    } catch (err) {
        body.innerHTML = `<div class="text-red py-2">Error: ${escapeHtml(err.message)}</div>`;
    }
}

function closeProvenanceModal() {
    const modal = document.getElementById('provenanceModal');
    if (modal) modal.classList.add('hidden');
}

async function downloadArtifact(id, filename) {
    appendConsole('ARTIFACT', `Downloading verified deliverable '${filename}' (SHA-256 verified)...`, 'tag-system');
    try {
        // Keep bearer credentials out of URLs, browser history, and access logs.
        // api.fetch supplies the Authorization header for this same-origin request.
        const res = await api.fetch(`/api/v1/workspaces/1/artifacts/${id}/download`);
        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            appendConsole('ARTIFACT', `Deliverable '${filename}' downloaded successfully (${blob.size} bytes).`, 'tag-done');
        } else {
            appendConsole('ERROR', `Download failed with HTTP ${res.status}`, 'tag-network');
        }
    } catch (e) {
        appendConsole('ERROR', `Download error: ${e.message}`, 'tag-network');
    }
}

// Live Telemetry & Dashboard Refresh
async function refreshDashboardData() {
    if (!api.getToken()) return;

    try {
        // 1. System Sovereignty & Physical Network
        const sovRes = await api.fetch('/api/v1/system/sovereignty');
        if (sovRes.ok) {
            const sov = await sovRes.json();
            const netBadge = document.getElementById('headerNetworkBadge');
            if (netBadge) {
                if (sov.physical_network_state === 'DISCONNECTED') {
                    netBadge.className = 'pill-strict';
                    netBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-green beacon-active"></span> EXTERNAL NETWORK: DISCONNECTED';
                    netBadge.title = 'Physical interface observation only. Network policy enforcement is reported separately.';
                } else {
                    netBadge.className = 'pill-simulation';
                    const ifaces = (sov.active_external_interfaces || []).join(', ') || 'ACTIVE';
                    netBadge.innerHTML = `EXTERNAL: CONNECTED (${ifaces})`;
                    netBadge.title = 'External physical interface detected. Kernel firewall strictly blocking public egress.';
                }
            }
            const unauthBadge = document.getElementById('unauthCountBadge');
            if (unauthBadge) unauthBadge.innerText = sov.total_blocked_attempts || 0;
        }

        // 2. Approvals
        const apprRes = await api.fetch('/api/v1/approvals');
        if (apprRes.ok) {
            const apprs = await apprRes.json();
            const badge = document.getElementById('navApprovalsBadge');
            if (badge) {
                badge.innerText = apprs.length;
                badge.className = apprs.length > 0
                    ? 'text-[9px] font-mono bg-red-tint text-red border border-red px-1.5 py-0.2 rounded font-bold'
                    : 'text-[9px] font-mono bg-card text-muted border border-subtle px-1.5 py-0.2 rounded font-bold';
            }

            const card = document.getElementById('approvalConsoleCard');
            const riskBadge = document.getElementById('apprRiskBadge');
            const apprAction = document.getElementById('apprAction');
            const apprTarget = document.getElementById('apprTarget');
            const apprJust = document.getElementById('apprJustification');
            const approver1Dot = document.getElementById('approver1Dot');
            const approver1Status = document.getElementById('approver1Status');
            const approver2Dot = document.getElementById('approver2Dot');
            const approver2Status = document.getElementById('approver2Status');
            const apprBtn = document.getElementById('apprReviewBtn');

            if (apprs.length > 0) {
                const topAppr = apprs[0];
                STATE.currentTargetApproval = topAppr;
                if (card) card.className = 'bg-card rounded-lg border border-red/40 p-3.5 flex flex-col gap-2.5';
                if (riskBadge) {
                    riskBadge.className = 'bg-red-tint text-red border border-red px-2 py-0.5 rounded text-[9px] font-extrabold uppercase';
                    riskBadge.innerText = `RISK: ${(topAppr.risk_level || 'HIGH').toUpperCase()}`;
                }
                if (apprAction) {
                    apprAction.className = 'text-slate-100 font-bold';
                    apprAction.innerText = topAppr.request_reason || 'restart_component';
                }
                if (apprTarget) {
                    apprTarget.className = 'text-slate-200';
                    let targetName = 'Industrial Equipment';
                    try {
                        const params = JSON.parse(topAppr.parameters || '{}');
                        targetName = params.component_id || params.equipment_id || params.target || 'P-101A (Centrifugal Pump)';
                    } catch(e) {}
                    apprTarget.innerText = targetName;
                }
                if (apprJust) {
                    apprJust.className = 'text-slate-300 text-[11px] leading-relaxed';
                    apprJust.innerText = `Parameters: ${topAppr.parameters || '{}'} (Requires Dual Four-Eyes Sign-Off)`;
                }

                if (topAppr.reviewed_by) {
                    if (approver1Dot) approver1Dot.className = 'w-4 h-4 rounded-full bg-green text-surface font-bold text-[10px] flex items-center justify-center';
                    if (approver1Status) {
                        approver1Status.innerText = `VERIFIED (${topAppr.reviewed_by})`;
                        approver1Status.className = 'text-[9px] text-green font-semibold';
                    }
                    if (approver2Dot) approver2Dot.className = 'w-4 h-4 rounded-full bg-amber text-surface font-bold text-[10px] flex items-center justify-center';
                    if (approver2Status) {
                        approver2Status.innerText = 'STAGE 2 PENDING';
                        approver2Status.className = 'text-[9px] text-amber font-semibold';
                    }
                } else {
                    if (approver1Dot) approver1Dot.className = 'w-4 h-4 rounded-full bg-amber text-surface font-bold text-[10px] flex items-center justify-center';
                    if (approver1Status) {
                        approver1Status.innerText = 'STAGE 1 PENDING';
                        approver1Status.className = 'text-[9px] text-amber font-semibold';
                    }
                    if (approver2Dot) approver2Dot.className = 'w-4 h-4 rounded-full bg-surface border border-subtle text-muted font-bold text-[10px] flex items-center justify-center';
                    if (approver2Status) {
                        approver2Status.innerText = 'WAITING';
                        approver2Status.className = 'text-[9px] text-muted font-semibold';
                    }
                }

                if (apprBtn) {
                    apprBtn.className = 'w-full bg-red-tint hover:bg-red-tint/80 text-red border border-red hover:border-red-400 font-mono font-bold py-2 rounded text-xs transition cursor-pointer flex items-center justify-center gap-2';
                    apprBtn.innerHTML = '<span>Review Request</span>';
                    apprBtn.disabled = false;
                }
            } else {
                STATE.currentTargetApproval = null;
                if (card) card.className = 'bg-card rounded-lg border border-subtle p-3.5 flex flex-col gap-2.5';
                if (riskBadge) {
                    riskBadge.className = 'bg-surface text-muted border border-subtle px-2 py-0.5 rounded text-[9px] font-bold uppercase';
                    riskBadge.innerText = 'NOMINAL';
                }
                if (apprAction) {
                    apprAction.className = 'text-slate-400 italic';
                    apprAction.innerText = 'None';
                }
                if (apprTarget) {
                    apprTarget.className = 'text-slate-400 italic';
                    apprTarget.innerText = 'No interlock pending';
                }
                if (apprJust) {
                    apprJust.className = 'text-slate-400 text-[11px] leading-relaxed';
                    apprJust.innerText = 'All safety boundaries nominal. Zero high-risk interlocks pending.';
                }
                if (approver1Dot) approver1Dot.className = 'w-4 h-4 rounded-full bg-surface border border-subtle text-muted font-bold text-[10px] flex items-center justify-center';
                if (approver1Status) {
                    approver1Status.innerText = 'NOMINAL';
                    approver1Status.className = 'text-[9px] text-muted font-semibold';
                }
                if (approver2Dot) approver2Dot.className = 'w-4 h-4 rounded-full bg-surface border border-subtle text-muted font-bold text-[10px] flex items-center justify-center';
                if (approver2Status) {
                    approver2Status.innerText = 'NOMINAL';
                    approver2Status.className = 'text-[9px] text-muted font-semibold';
                }
                if (apprBtn) {
                    apprBtn.className = 'w-full bg-card text-muted border border-subtle font-mono font-bold py-2 rounded text-xs transition cursor-not-allowed opacity-50 flex items-center justify-center gap-2';
                    apprBtn.innerHTML = '<span>No Pending Interlocks</span>';
                    apprBtn.disabled = true;
                }
            }
        }

        // 3. Artifacts
        const artRes = await api.fetch('/api/v1/workspaces/1/artifacts');
        if (artRes.ok) {
            const artData = await artRes.json();
            const list = artData.artifacts || [];
            const count = list.length;
            const pill = document.getElementById('artifactCountPill');
            const navBadge = document.getElementById('navArtifactsBadge');
            if (pill) pill.innerText = count;
            if (navBadge) navBadge.innerText = count;

            const tbody = document.getElementById('artifactTableBody');
            if (tbody) {
                tbody.innerHTML = '';
                if (list.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted italic py-4">No verified artifacts generated yet. Run an analysis workflow to produce output deliverables.</td></tr>';
                } else {
                    list.slice(0, 5).forEach(a => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td class="font-medium text-slate-200 flex items-center gap-2">
                                <span class="text-cyan font-bold text-xs">📦</span>
                                <span>${escapeHtml(a.filename)}</span>
                            </td>
                            <td><span class="text-[10px] text-muted uppercase">${escapeHtml(a.artifact_type)}</span></td>
                            <td><span class="text-[10px] text-slate-400">MRPL_OPS_WS</span></td>
                            <td class="text-green text-[10px] max-w-[180px] truncate font-mono" title="${escapeHtml(a.sha256_hash)}">
                                ${escapeHtml(a.sha256_hash.slice(0, 16))}...
                            </td>
                            <td class="text-slate-400 text-[10px]">${escapeHtml((a.created_at || '').slice(11, 19))}</td>
                            <td>
                                <span class="bg-green-tint text-green border border-green px-1.5 py-0.5 rounded text-[9px] font-bold">
                                    REGISTERED
                                </span>
                            </td>
                            <td class="text-right space-x-2">
                                <button data-action="preview-artifact" data-file="${escapeHtml(a.filename)}" data-hash="${escapeHtml(a.sha256_hash)}" data-size="${escapeHtml(a.file_size)}" data-type="${escapeHtml(a.artifact_type)}" class="text-muted hover:text-green cursor-pointer" title="Preview SHA-256">👁</button>
                                <button data-action="download-artifact" data-id="${escapeHtml(a.id)}" data-file="${escapeHtml(a.filename)}" class="text-muted hover:text-green cursor-pointer" title="Download Verified File">📥</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            }
        }

        // 4. Knowledge & Evidence Metadata
        const kRes = await api.fetch('/api/v1/knowledge?workspace_id=1');
        if (kRes.ok) {
            const docs = await kRes.json();
            const provDoc = document.getElementById('provDoc');
            const provPage = document.getElementById('provPage');
            const provEngine = document.getElementById('provEngine');
            if (docs.length > 0) {
                const topDoc = docs[0];
                if (provDoc) {
                    provDoc.innerText = topDoc.original_filename || topDoc.name;
                    provDoc.className = 'text-slate-200 font-bold';
                }
                if (provPage) provPage.innerText = `Indexed (${topDoc.chunk_count || 1} Chunks)`;
                if (provEngine) provEngine.innerText = topDoc.source_type === 'image' ? 'Moondream Vision (Local)' : 'PyMuPDF / ChromaDB';
            } else {
                if (provDoc) {
                    provDoc.innerText = 'None (Standby)';
                    provDoc.className = 'text-slate-400 italic font-normal';
                }
                if (provPage) provPage.innerText = '—';
                if (provEngine) provEngine.innerText = 'PyMuPDF / ChromaDB';
            }
        }
    } catch (e) {
        console.error('Error refreshing dashboard:', e);
    }
}

// View Loaders
async function loadWorkspacesView() {
    const container = document.getElementById('workspacesGrid');
    if (!container) return;

    try {
        const res = await api.fetch('/api/v1/workspaces');
        if (res.ok) {
            const wsList = await res.json();
            container.innerHTML = '';
            wsList.forEach(ws => {
                container.innerHTML += `
                    <div class="bg-card p-4 rounded-lg border border-green space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-white font-bold text-sm">${escapeHtml(ws.name)}</span>
                            <span class="bg-green-tint text-green px-2 py-0.5 rounded text-[10px] font-bold border border-green">LOCAL SCOPE</span>
                        </div>
                        <p class="text-xs text-muted">${escapeHtml(ws.description || 'Isolated refinery operations workspace')}</p>
                        <div class="text-[11px] text-slate-300 pt-2 border-t border-subtle flex justify-between">
                            <span>Operating Mode: <b class="text-green">${escapeHtml((ws.operating_mode || 'local').toUpperCase())}</b></span>
                            <span>ID: <b>${escapeHtml(ws.id)}</b></span>
                        </div>
                    </div>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

async function loadDocumentsView() {
    const tbody = document.getElementById('documentsTableBody');
    if (!tbody) return;

    try {
        const res = await api.fetch('/api/v1/knowledge?workspace_id=1');
        if (res.ok) {
            const docs = await res.json();
            tbody.innerHTML = '';
            if (docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted italic py-4">No documents indexed in workspace yet.</td></tr>';
                return;
            }
            docs.forEach(d => {
                const engine = d.source_type === 'image' ? 'Moondream Vision (Local)' : 'RapidOCR / PyMuPDF (Local)';
                tbody.innerHTML += `
                    <tr>
                        <td class="text-slate-200 font-medium">${escapeHtml(d.original_filename || d.name)}</td>
                        <td><span class="text-muted uppercase">${escapeHtml(d.source_type)}</span></td>
                        <td>${escapeHtml(d.chunk_count || 1)} Chunks</td>
                        <td><span class="text-green font-semibold">${escapeHtml(engine)}</span></td>
                        <td><span class="bg-green-tint text-green px-1.5 py-0.5 rounded text-[9px] font-bold border border-green">${escapeHtml((d.processing_status || 'indexed').toUpperCase())}</span></td>
                        <td class="text-right space-x-2">
                            <button data-action="open-provenance" data-id="${escapeHtml(d.id)}" class="text-cyan hover:underline text-[10px] cursor-pointer">Pages & Provenance</button>
                        </td>
                    </tr>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

async function loadAgentsView() {
    const container = document.getElementById('agentsGrid');
    if (!container) return;

    try {
        const res = await api.fetch('/api/v1/agents?workspace_id=1');
        if (res.ok) {
            const agents = await res.json();
            container.innerHTML = '';
            agents.forEach(a => {
                container.innerHTML += `
                    <div class="bg-card p-4 rounded-lg border border-subtle space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-white font-bold text-sm">${escapeHtml(a.name)}</span>
                            <span class="bg-green-tint text-green px-2 py-0.5 rounded text-[10px]">ID: ${escapeHtml(a.id)}</span>
                        </div>
                        <div class="text-[11px] text-cyan">Model: ${escapeHtml(a.model_name)} | Approval Required: ${a.approval_required ? 'YES (FOUR-EYES)' : 'NO'}</div>
                        <p class="text-xs text-slate-300">${escapeHtml(a.description || 'Autonomous plant reasoning agent.')}</p>
                    </div>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

async function loadApprovalsView() {
    const container = document.getElementById('approvalsListContainer');
    if (!container) return;

    try {
        const res = await api.fetch('/api/v1/approvals');
        if (res.ok) {
            const data = await res.json();
            container.innerHTML = '';
            if (data.length === 0) {
                container.innerHTML = `<div class="text-muted italic py-4">Zero high-risk interlocks pending. All safety parameters nominal.</div>`;
                return;
            }
            data.forEach(req => {
                let stageText = 'Stage 1/2 Supervisor Review Pending';
                if (req.reviewed_by) {
                    stageText = `Stage 1/2 Verified by ${req.reviewed_by} | Stage 2 Plant Authorizer Sign-Off Required`;
                }
                container.innerHTML += `
                    <div class="bg-card p-4 rounded-lg border border-red/40 space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-amber font-bold text-sm">INTERLOCK #${escapeHtml(req.id)} — ${escapeHtml(req.request_reason)}</span>
                            <span class="bg-red-tint text-red border border-red px-2 py-0.5 rounded text-[10px] font-bold">HIGH RISK</span>
                        </div>
                        <div class="text-xs text-slate-300 font-mono bg-terminal p-2 rounded">PARAMS: ${escapeHtml(req.parameters || '{}')}</div>
                        <div class="text-[11px] text-cyan font-semibold">${escapeHtml(stageText)}</div>
                        <div class="flex gap-2 pt-2">
                            <button data-action="quick-approve" data-id="${escapeHtml(req.id)}" class="bg-green hover:bg-emerald-400 text-surface font-bold px-4 py-1.5 rounded text-xs transition cursor-pointer">AUTHORIZE ACTION</button>
                            <button data-action="quick-reject" data-id="${escapeHtml(req.id)}" class="bg-red-tint text-red border border-red font-bold px-4 py-1.5 rounded text-xs transition cursor-pointer">REJECT</button>
                        </div>
                    </div>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

async function loadArtifactsView() {
    const tbody = document.getElementById('fullArtifactsTableBody');
    if (!tbody) return;

    try {
        const res = await api.fetch('/api/v1/workspaces/1/artifacts');
        if (res.ok) {
            const data = await res.json();
            tbody.innerHTML = '';
            const list = data.artifacts || [];
            if (list.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted italic py-4">No artifacts generated in workspace #1 yet.</td></tr>';
                return;
            }
            list.forEach(a => {
                tbody.innerHTML += `
                    <tr>
                        <td class="text-white font-bold">${escapeHtml(a.filename)}</td>
                        <td>${escapeHtml((a.artifact_type || 'FILE').toUpperCase())}</td>
                        <td>${escapeHtml(a.file_size)} B</td>
                        <td class="text-green text-[10px] max-w-[200px] truncate font-mono">${escapeHtml(a.sha256_hash)}</td>
                        <td>${escapeHtml((a.created_at || '').slice(0, 19))}</td>
                        <td><span class="bg-green-tint text-green px-1.5 py-0.5 rounded text-[9px] font-bold border border-green">REGISTERED</span></td>
                        <td class="text-right space-x-2">
                            <button data-action="preview-artifact" data-file="${escapeHtml(a.filename)}" data-hash="${escapeHtml(a.sha256_hash)}" data-size="${escapeHtml(a.file_size)}" data-type="${escapeHtml(a.artifact_type)}" class="text-muted hover:text-green text-[10px] font-bold mr-2 cursor-pointer">METADATA</button>
                            <button data-action="download-artifact" data-id="${escapeHtml(a.id)}" data-file="${escapeHtml(a.filename)}" class="text-green hover:underline text-[10px] font-bold cursor-pointer">DOWNLOAD</button>
                        </td>
                    </tr>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

async function loadAuditView() {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    try {
        const res = await api.fetch('/api/v1/audit?workspace_id=1&limit=50');
        if (res.ok) {
            const auditEvents = await res.json();
            tbody.innerHTML = '';
            if (auditEvents.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted italic py-4">Zero audit events recorded in workspace #1 yet.</td></tr>';
                return;
            }
            auditEvents.forEach(ev => {
                const resClass = (ev.result || '').toUpperCase() === 'SUCCESS' ? 'bg-green-tint text-green border-green' : 'bg-red-tint text-red border-red';
                tbody.innerHTML += `
                    <tr>
                        <td class="font-mono">${escapeHtml((ev.created_at || '').slice(0, 19).replace('T', ' '))}</td>
                        <td class="text-white font-bold">${escapeHtml(ev.actor_id)}</td>
                        <td class="text-slate-400">WS #${escapeHtml(ev.workspace_id || 1)}</td>
                        <td><span class="text-cyan font-bold font-mono">${escapeHtml(ev.action)}</span></td>
                        <td class="text-slate-300 truncate max-w-[280px]" title="${escapeHtml(ev.details || '')}">${ev.resource_type ? `[${escapeHtml(ev.resource_type)}:${escapeHtml(ev.resource_id)}] ` : ''}${escapeHtml(ev.details || '')}</td>
                        <td><span class="px-1.5 py-0.5 rounded text-[9px] font-bold border ${resClass}">${escapeHtml((ev.result || 'OK').toUpperCase())}</span></td>
                    </tr>
                `;
            });
        }
    } catch (e) { console.error(e); }
}

function loadSandboxView() {
    // Sandbox default state
}

async function runSandboxCode() {
    const input = document.getElementById('sandboxCodeInput');
    const out = document.getElementById('sandboxConsoleOutput');
    if (!input || !out) return;

    const code = input.value.trim() || undefined;
    out.innerText = 'Connecting to local Docker daemon...\nAttaching flags: --network=none --read-only --pull=never --memory=512m\nExecuting ephemeral container cognishift/sandbox-python:3.12-v1...';
    appendConsole('SANDBOX', 'Launching hardened container (--network=none, read-only rootfs)...', 'tag-system');

    try {
        const res = await api.fetch('/api/v1/sandbox/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: STATE.workspaceId,
                code: code,
                input_filename: code ? null : 'equipment_readings.csv',
                promote_outputs: true
            })
        });

        if (res.ok) {
            const data = await res.json();
            out.innerText = `Container configuration: network=none, read-only rootfs\nStatus: ${data.status.toUpperCase()} (Exit Code: ${data.exit_code})\nExecution Duration: ${data.duration_ms} ms\nNetwork policy: isolated; egress bytes not measured by this view\n\n--- CONTAINER STDOUT ---\n${data.stdout || '(no stdout)'}\n` + (data.stderr ? `\n--- CONTAINER STDERR ---\n${data.stderr}` : '');
            appendConsole('SANDBOX', `Sandbox result: ${data.status} (Exit code: ${data.exit_code})`, 'tag-tool');
            refreshDashboardData();
        } else {
            const err = await res.json().catch(() => ({ detail: 'Sandbox error' }));
            out.innerText = `CONTAINER EXECUTION NOTICE (${res.status}):\n${JSON.stringify(err, null, 2)}\n\n(Note: If local Docker daemon is not active or image is unavailable, sandbox fails closed as required)`;
            appendConsole('SANDBOX', `Container notice: ${err.detail || 'Service unavailable'}`, 'tag-network');
        }
    } catch (e) {
        out.innerText = `LOCAL CONTAINER DAEMON NOTICE:\n${e.message}\n(Container engine failed closed safely)`;
        appendConsole('SANDBOX', `Container execution notice: ${e.message}`, 'tag-network');
    }
}

async function loadSovereigntyView() {
    try {
        const sovRes = await api.fetch('/api/v1/system/sovereignty');
        if (sovRes.ok) {
            const sov = await sovRes.json();
            const container = document.getElementById('sovereigntyCardsGrid');
            if (container) {
                const netColor = sov.physical_network_state === 'DISCONNECTED' ? 'green' : 'amber';
                const netStatus = sov.physical_network_state === 'DISCONNECTED' ? 'DISCONNECTED' : 'CONNECTED';
                container.innerHTML = `
                    <div class="bg-card p-4 rounded-lg border border-green space-y-2">
                        <div class="text-xs font-bold text-muted uppercase">Network Policy</div>
                        <div class="text-green font-bold text-lg">STRICT / ENFORCED</div>
                        <div class="text-[11px] text-slate-300">Host Firewall: 0 Non-Loopback Outbound Allowed</div>
                    </div>
                    <div class="bg-card p-4 rounded-lg border border-${netColor} space-y-2">
                        <div class="text-xs font-bold text-muted uppercase">Physical Network State</div>
                        <div class="text-${netColor} font-bold text-lg">${netStatus}</div>
                        <div class="text-[11px] text-slate-300">Active Adapters: ${(sov.active_external_interfaces || []).join(', ') || 'None (Isolated)'}</div>
                    </div>
                    <div class="bg-card p-4 rounded-lg border border-amber space-y-2">
                        <div class="text-xs font-bold text-muted uppercase">Docker Sandbox Network</div>
                        <div class="text-amber font-bold text-lg">NONE (ISOLATED)</div>
                        <div class="text-[11px] text-slate-300">Containers launch with --network=none</div>
                    </div>
                `;
            }
        }

        const evRes = await api.fetch('/api/v1/system/network-events');
        if (evRes.ok) {
            const evData = await evRes.json();
            const evs = evData.events || [];
            const ledger = document.getElementById('blockedNetworkLedger');
            if (ledger) {
                ledger.innerHTML = '';
                if (evs.length === 0) {
                    ledger.innerHTML = '<div class="text-muted italic py-2">No egress violations intercepted. Clean perimeter.</div>';
                } else {
                    evs.forEach(ev => {
                        const decision = String(ev.policy_decision || 'UNKNOWN').toUpperCase();
                        const decisionColor = decision === 'BLOCKED' ? 'text-red' : decision === 'ALLOWED' ? 'text-green' : 'text-amber';
                        const host = ev.requested_host || ev.resolved_ip || 'unknown';
                        const port = ev.port == null ? '—' : ev.port;
                        ledger.innerHTML += `
                            <div class="flex justify-between py-0.5 border-b border-subtle">
                                <span class="${decisionColor} font-bold">[${decision}]</span>
                                <span class="text-slate-300">${host}:${port}</span>
                                <span class="text-muted">${ev.component || 'unknown'}</span>
                                <span class="text-dark">${ev.timestamp || ''}</span>
                            </div>
                        `;
                    });
                }
            }
        }
    } catch (e) { console.error(e); }
}

function refreshSovereignty() {
    loadSovereigntyView();
    refreshDashboardData();
}

// Global Event Delegation & Initialization
document.addEventListener('click', (e) => {
    // 1. Navigation items
    const navBtn = e.target.closest('[data-nav]');
    if (navBtn) {
        const view = navBtn.getAttribute('data-nav');
        if (view) switchNav(view);
        return;
    }

    // 2. Action buttons
    const actionEl = e.target.closest('[data-action]');
    if (actionEl) {
        const action = actionEl.getAttribute('data-action');
        if (action === 'open-auth') {
            openAuthModal();
        } else if (action === 'logout') {
            logout();
        } else if (action === 'close-auth') {
            closeAuthModal();
        } else if (action === 'toggle-token-visibility') {
            toggleTokenVisibility();
        } else if (action === 'paste-token') {
            pasteTokenFromClipboard();
        } else if (action === 'demo-persona') {
            authenticateDemoPersona(actionEl.getAttribute('data-persona'));
        } else if (action === 'toggle-user-menu') {
            toggleUserDropdown();
        } else if (action === 'console-pause') {
            toggleConsolePause();
        } else if (action === 'console-clear') {
            clearConsole();
        } else if (action === 'console-submit') {
            executeConsoleCommand(actionEl.getAttribute('data-input') || 'consoleCmdInput');
        } else if (action === 'review-approval') {
            openApprovalModal();
        } else if (action === 'close-approval-modal') {
            closeApprovalModal();
        } else if (action === 'modal-approve') {
            executeModalApproval('approve');
        } else if (action === 'modal-reject') {
            executeModalApproval('reject');
        } else if (action === 'quick-approve') {
            const id = parseInt(actionEl.getAttribute('data-id'), 10);
            executeModalApproval('approve', id);
        } else if (action === 'quick-reject') {
            const id = parseInt(actionEl.getAttribute('data-id'), 10);
            executeModalApproval('reject', id);
        } else if (action === 'preview-artifact') {
            previewArtifact(
                actionEl.getAttribute('data-file'),
                actionEl.getAttribute('data-hash'),
                parseInt(actionEl.getAttribute('data-size') || '0', 10),
                actionEl.getAttribute('data-type')
            );
        } else if (action === 'download-artifact') {
            const id = parseInt(actionEl.getAttribute('data-id'), 10);
            const file = actionEl.getAttribute('data-file');
            downloadArtifact(id, file);
        } else if (action === 'close-artifact-modal') {
            closeArtifactModal();
        } else if (action === 'open-provenance') {
            const id = parseInt(actionEl.getAttribute('data-id'), 10);
            openProvenanceModal(id);
        } else if (action === 'close-provenance-modal') {
            closeProvenanceModal();
        } else if (action === 'run-sandbox') {
            runSandboxCode();
        } else if (action === 'refresh-sovereignty') {
            refreshSovereignty();
        }
        return;
    }

    // Dismiss user dropdown when clicking outside
    const userMenuBtn = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');
    if (userDropdown && userMenuBtn && !userMenuBtn.contains(e.target) && !userDropdown.contains(e.target)) {
        userDropdown.classList.add('hidden');
    }
});

// Expose functions globally for any remaining callers or testing
window.switchNav = switchNav;
window.executeConsoleCommand = executeConsoleCommand;
window.toggleConsolePause = toggleConsolePause;
window.clearConsole = clearConsole;
window.openApprovalModal = openApprovalModal;
window.closeApprovalModal = closeApprovalModal;
window.executeModalApproval = executeModalApproval;
window.previewArtifact = previewArtifact;
window.closeArtifactModal = closeArtifactModal;
window.openProvenanceModal = openProvenanceModal;
window.closeProvenanceModal = closeProvenanceModal;
window.downloadArtifact = downloadArtifact;
window.runSandboxCode = runSandboxCode;
window.refreshSovereignty = refreshSovereignty;
window.openAuthModal = openAuthModal;
window.closeAuthModal = closeAuthModal;
window.logout = logout;
window.authenticateWithToken = authenticateWithToken;
window.toggleTokenVisibility = toggleTokenVisibility;
window.pasteTokenFromClipboard = pasteTokenFromClipboard;
window.updateTokenCharCount = updateTokenCharCount;
window.authenticateDemoPersona = authenticateDemoPersona;
window.handleConsoleControlCommand = handleConsoleControlCommand;

// Form Initialization
function initApp() {
    // 1. Clock
    setInterval(updateClock, 1000);
    updateClock();

    // 2. Auth Modal Form
    const authForm = document.getElementById('authModalForm');
    const authInput = document.getElementById('authModalTokenInput');
    if (authInput) {
        authInput.addEventListener('input', updateTokenCharCount);
    }
    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (authInput) {
                await authenticateWithToken(authInput.value);
            }
        });
    }

    // 3. Document Ingestion Form
    const uploadForm = document.getElementById('docsUploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('docsFileInput');
            const statusDiv = document.getElementById('docsUploadStatus');
            if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                if (statusDiv) statusDiv.innerHTML = '<span class="text-amber">Please select a file to ingest.</span>';
                return;
            }
            const file = fileInput.files[0];
            if (statusDiv) statusDiv.innerHTML = `<span class="text-amber">Ingesting '${file.name}' with local RapidOCR / PyMuPDF...</span>`;
            appendConsole('UPLOAD', `Ingesting '${file.name}' into workspace #1...`, 'tag-upload');

            const formData = new FormData();
            formData.append('workspace_id', STATE.workspaceId);
            formData.append('file', file);

            try {
                const res = await api.fetch('/api/v1/knowledge/upload', {
                    method: 'POST',
                    body: formData
                });
                if (res.ok) {
                    const data = await res.json();
                    if (statusDiv) statusDiv.innerHTML = `<span class="text-green font-bold">✓ Successfully ingested '${data.name}' (${data.chunk_count} chunks indexed in ChromaDB)</span>`;
                    appendConsole('INGEST', `Indexed '${data.name}' with ${data.chunk_count} chunks into ChromaDB (SHA: ${(data.checksum || '').slice(0,12)}...)`, 'tag-done');
                    fileInput.value = '';
                    loadDocumentsView();
                    refreshDashboardData();
                } else {
                    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
                    if (statusDiv) statusDiv.innerHTML = `<span class="text-red font-bold">Ingestion failed: ${err.detail || 'Error'}</span>`;
                    appendConsole('ERROR', `Upload rejected: ${err.detail || 'Error'}`, 'tag-network');
                }
            } catch (err) {
                if (statusDiv) statusDiv.innerHTML = `<span class="text-red font-bold">Error: ${err.message}</span>`;
                appendConsole('ERROR', `Upload error: ${err.message}`, 'tag-network');
            }
        });
    }

    // 4. Command Input Enter Key
    ['consoleCmdInput', 'globalConsoleCmdInput'].forEach((inputId) => {
        const cmdInput = document.getElementById(inputId);
        if (!cmdInput) return;
        cmdInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                executeConsoleCommand(inputId);
            }
        });
    });

    // 5. Initial Auth Check & Telemetry Interval
    loadAuthenticationOptions();
    checkAuth();
    setInterval(refreshDashboardData, 5000);
}

// Start application when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
