/**
 * AI_JS_DEBUGGER Frontend Application
 * Main JavaScript file
 */


const AppState = {
    currentPage: 'dashboard',
    theme: 'light',
    socket: null,
    currentSession: null
};

const PROVIDER_DISPLAY_NAMES = {
    'qwen': '通义千问',
    'openai': 'OpenAI GPT',
    'deepseek': 'Deepseek',
    'ernie': '文心一言',
    'spark': '讯飞星火',
    'claude': 'Claude',
    'kimi': 'Kimi',
    'glm': '智谱 GLM',
    'minimax': 'MiniMax',
    'kat': '快手 KAT'
};

const PROVIDER_FALLBACK_MODELS = {
    qwen: ['qwen-plus-2025-01-25', 'qwen-turbo', 'qwen-long'],
    openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini'],
    deepseek: ['deepseek-chat', 'deepseek-reasoner'],
    ernie: ['ernie-4.0', 'ernie-3.5'],
    spark: ['spark-3.5', 'spark-2.0'],
    claude: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
    kimi: ['moonshot-v1-8k', 'moonshot-v1-32k'],
    glm: ['glm-4-plus', 'glm-4-air', 'glm-4-flash'],
    minimax: ['abab6.5-chat', 'abab6.5s-chat'],
    kat: ['kat-8k', 'kat-32k']
};

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return text.replace(/[&<>"']/g, (match) => map[match] || match);
}

let debugAIProviders = [];
let defaultAIProvider = 'qwen';
let aiProviderInitPromise = null;
let customProviderLabels = {};


function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    AppState.theme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
    applyTheme(AppState.theme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');

    if (icon) {
        icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon');
        lucide.createIcons();
    }

    AppState.theme = theme;
    localStorage.setItem('theme', theme);
}

function syncCustomProviderLabels() {
    try {
        customProviderLabels = JSON.parse(localStorage.getItem('customProviderNames') || '{}');
    } catch (e) {
        customProviderLabels = {};
    }
}

function getAIProviderDisplayName(name) {
    const cached = debugAIProviders.find(p => p.name === name);
    if (cached && cached.display_name) {
        return cached.display_name;
    }
    if (customProviderLabels && customProviderLabels[name]) {
        return customProviderLabels[name];
    }
    return PROVIDER_DISPLAY_NAMES[name] || name || '未命名';
}

function getProviderModels(provider) {
    if (!provider) return [];
    const defaults = PROVIDER_FALLBACK_MODELS[provider.name] || [];
    const available = Array.isArray(provider.available_models) ? provider.available_models : [];
    const extras = [provider.model, provider.analysis_model].filter(Boolean);
    return Array.from(new Set([...defaults, ...available, ...extras])).filter(Boolean);
}

async function ensureAIProviderOptions() {
    if (aiProviderInitPromise) return aiProviderInitPromise;
    aiProviderInitPromise = (async () => {
        try {
            const response = await fetch('/api/providers');
            const result = await response.json();
            if (result.success) {
                syncCustomProviderLabels();
                debugAIProviders = (result.data.providers || []).map(p => ({
                    ...p,
                    display_name: p.display_name || getAIProviderDisplayName(p.name)
                }));
                defaultAIProvider = result.data.default || defaultAIProvider;
            }
        } catch (error) {
            console.error('Failed to load AI provider options:', error);
        }
    })();
    return aiProviderInitPromise;
}

async function initAIProviderOptions() {
    await ensureAIProviderOptions();
    refreshAIProviderSelect();
}

function refreshAIProviderSelect(selected) {
    const providerSelect = document.getElementById('ai-provider');
    if (!providerSelect) return;

    if (debugAIProviders.length) {
        providerSelect.innerHTML = debugAIProviders.map(provider => `
            <option value="${provider.name}">${provider.display_name}</option>
        `).join('');
        const target = selected || providerSelect.value || defaultAIProvider || debugAIProviders[0].name;
        providerSelect.value = target;
    }

    if (!providerSelect.dataset.bound) {
        providerSelect.dataset.bound = '1';
        providerSelect.addEventListener('change', () => {
        });
    }
}

function toggleTheme() {
    const newTheme = AppState.theme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
}


function showPage(pageName) {
    const pages = document.querySelectorAll('.page');
    pages.forEach(page => {
        page.style.display = 'none';
        page.style.visibility = 'hidden';  // Extra insurance
    });

    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.style.display = 'block';
        targetPage.style.visibility = 'visible';  // Make sure it's visible
        targetPage.classList.add('fade-in');
    }

    const navLinks = document.querySelectorAll('.sidebar-nav-link');
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-page') === pageName) {
            link.classList.add('active');
        }
    });

    AppState.currentPage = pageName;

    if (window.pageChangeCallbacks) {
        window.pageChangeCallbacks.forEach(callback => {
            try {
                callback(pageName);
            } catch (error) {
                console.error('Page change callback error:', error);
            }
        });
    }
}

window.showPage = showPage;


function initNavbarScroll() {
    const navbar = document.getElementById('navbar');
    const mainContent = document.getElementById('main-content');

    if (mainContent) {
        mainContent.addEventListener('scroll', () => {
            if (mainContent.scrollTop > 10) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }
}


function initBreakpointModeToggle() {
    const radios = document.querySelectorAll('input[name="breakpoint-mode"]');
    const jsConfig = document.getElementById('js-mode-config');
    const xhrConfig = document.getElementById('xhr-mode-config');
    const jsFileInput = document.getElementById('js-file');

    const syncJsFileRequirement = (active) => {
        if (!jsFileInput) return;
        jsFileInput.required = !!active;
        if (!active) {
            jsFileInput.setCustomValidity('');
        }
    };

    radios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'js') {
                jsConfig.style.display = 'block';
                xhrConfig.style.display = 'none';
                syncJsFileRequirement(true);
            } else {
                jsConfig.style.display = 'none';
                xhrConfig.style.display = 'block';
                syncJsFileRequirement(false);
            }
        });
    });

    const initialMode = document.querySelector('input[name="breakpoint-mode"]:checked');
    syncJsFileRequirement(!initialMode || initialMode.value === 'js');
}


function initDebugConfigForm() {
    const form = document.getElementById('debug-config-form');

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const jsFileInput = document.getElementById('js-file');

            const storedDebugConfig = JSON.parse(localStorage.getItem('debugConfig') || '{}');
            const depthInput = document.getElementById('scope-max-depth');
            const totalInput = document.getElementById('scope-max-total');
            const scopeMaxDepth = parseInt(depthInput?.value || storedDebugConfig.scope_max_depth) || 5;
            const scopeMaxTotalProps = parseInt(totalInput?.value || storedDebugConfig.scope_max_total_props) || 15;

            const formData = {
                target_url: document.getElementById('target-url').value,
                browser_type: document.getElementById('browser-type').value,
                breakpoint_mode: document.querySelector('input[name="breakpoint-mode"]:checked').value,
                ai_provider: document.getElementById('ai-provider').value,
                config: {
                    scope_max_depth: scopeMaxDepth,
                    scope_max_total_props: scopeMaxTotalProps
                }
            };

            if (formData.breakpoint_mode === 'js') {
                const jsFileValue = (jsFileInput?.value || '').trim();
                if (!jsFileValue) {
                    if (jsFileInput) {
                        jsFileInput.reportValidity();
                        jsFileInput.focus();
                    }
                    return;
                }
                formData.config.js_file = jsFileValue;
                formData.config.line_number = parseInt(document.getElementById('line-number').value) || 0;
                formData.config.column_number = parseInt(document.getElementById('column-number').value) || 0;
            } else {
                formData.config.xhr_url = document.getElementById('xhr-url').value;
            }

            try {
                const response = await fetch('/debug/session/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const result = await response.json();

                if (result.success) {
                    showNotification('调试会话已创建', 'success');
                    AppState.currentSession = result.data.session_id;

                    await startDebugSession(result.data.session_id);
                } else {
                    showNotification('创建会话失败：' + result.error, 'error');
                }
            } catch (error) {
                console.error('Error creating debug session:', error);
                showNotification('创建会话时发生错误', 'error');
            }
        });
    }
}


async function startDebugSession(sessionId) {
    try {
        if (AppState.socket && AppState.currentSession && AppState.currentSession !== sessionId) {
            try { AppState.socket.emit('leave_debug_session', { session_id: AppState.currentSession }); } catch (e) {}
        }

        showPage('debug');

        AppState.currentSession = sessionId;

        if (typeof startDebugFromConfig === 'function') {
            startDebugFromConfig();
        }

        if (AppState.socket) {
            AppState.socket.emit('join_debug_session', { session_id: sessionId });
            console.log('✅ 已加入WebSocket room:', sessionId);
        }

        const response = await fetch(`/debug/session/${sessionId}/start`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('调试会话已启动', 'success');
        } else {
            if (typeof setStopButtonEnabled === 'function') {
                setStopButtonEnabled(false);
            }
            showNotification('启动会话失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error starting debug session:', error);
        showNotification('启动会话时发生错误', 'error');
        if (typeof setStopButtonEnabled === 'function') {
            setStopButtonEnabled(false);
        }
    }
}


function initWebSocket() {
    if (typeof io === 'undefined') {
        console.error('❌ Socket.IO未加载！WebSocket功能将被禁用');
        console.error('请检查网络连接或使用本地socket.io库');
        showNotification('WebSocket未初始化，将使用轮询模式', 'warning');
        return;
    }

    try {
        console.log('🔌 正在初始化WebSocket连接...');
        AppState.socket = io();
        console.log('✅ WebSocket对象已创建:', AppState.socket);

        AppState.socket.on('connect', () => {
            console.log('WebSocket connected');
            showNotification('已连接到服务器', 'success');

            if (typeof window.onWebSocketConnect === 'function') {
                window.onWebSocketConnect();
            }
        });

        AppState.socket.onAny((eventName, ...args) => {
            console.log(`📡 WebSocket事件: ${eventName}`, args);
        });

        AppState.socket.on('connect_error', (error) => {
            console.warn('WebSocket connection error:', error);

            if (typeof window.onWebSocketError === 'function') {
                window.onWebSocketError(error);
            }
        });

        AppState.socket.on('disconnect', (reason) => {
            console.log('WebSocket disconnected:', reason);
            showNotification('与服务器断开连接', 'warning');

            if (typeof window.onWebSocketDisconnect === 'function') {
                window.onWebSocketDisconnect(reason);
            }
        });

        AppState.socket.on('debug_update', (data) => {
            console.log('Debug update:', data);
        });

        AppState.socket.on('debug_ai_error', (data) => {
            const msg = (data && data.message) ? data.message : 'AI 调用错误';
            showNotification('AI 错误：' + msg, 'warning');
        });

        AppState.socket.on('session_joined', (data) => {
            console.log('Joined session:', data);
        });
    } catch (error) {
        console.error('Failed to initialize WebSocket:', error);
    }
}


async function saveAISettings() {
    const provider = document.getElementById('settings-provider').value;
    const apiKey = document.getElementById('settings-api-key').value;
    const model = document.getElementById('settings-model').value;

    if (!apiKey) {
        showNotification('请输入 API Key', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/config/ai', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                provider: provider,
                api_key: apiKey,
                model: model
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('AI 配置已保存', 'success');
            document.getElementById('settings-api-key').value = '';
        } else {
            showNotification('保存配置失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error saving AI settings:', error);
        showNotification('保存配置时发生错误', 'error');
    }
}


function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 24px;
        background: var(--bg-secondary);
        padding: 16px 24px;
        border-radius: 12px;
        box-shadow: var(--shadow-lg);
        border-left: 4px solid var(--accent-${type === 'success' ? 'success' : type === 'error' ? 'danger' : type === 'warning' ? 'warning' : 'blue'});
        z-index: 10000;
        min-width: 300px;
        animation: slideIn 0.3s ease-out;
    `;

    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);


async function saveBrowserConfig() {
    const chromePath = document.getElementById('chrome-path')?.value || null;
    const edgePath = document.getElementById('edge-path')?.value || null;

    try {
        const response = await fetch('/api/config/browser', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chrome_path: chromePath,
                edge_path: edgePath
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('浏览器配置已保存', 'success');
        } else {
            showNotification('保存失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error saving browser config:', error);
        showNotification('保存配置时发生错误', 'error');
    }
}

async function saveDebugConfig() {
    const autoSave = document.getElementById('auto-save')?.checked || false;
    const saveInterval = parseInt(document.getElementById('save-interval')?.value) || 300;
    const maxDuration = parseInt(document.getElementById('max-duration')?.value) || 600;
    const contextChars = parseInt(document.getElementById('context-chars')?.value) || 150;
    const scopeMaxDepth = parseInt(document.getElementById('scope-max-depth')?.value) || 2;
    const scopeMaxTotal = parseInt(document.getElementById('scope-max-total')?.value) || 15;

    const debugPayload = {
        auto_save: autoSave,
        save_interval: saveInterval,
        max_duration: maxDuration,
        context_chars: contextChars,
        scope_max_depth: scopeMaxDepth,
        scope_max_total_props: scopeMaxTotal
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                debug: debugPayload
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('调试配置已保存', 'success');
            try { localStorage.setItem('debugConfig', JSON.stringify(debugPayload)); } catch (e) {}
        } else {
            showNotification('保存失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error saving debug config:', error);
        showNotification('保存配置时发生错误', 'error');
    }
}

function formatHookSize(bytes) {
    const value = Number(bytes);
    if (!Number.isFinite(value)) return '--';
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatHookTimestamp(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const h = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${d} ${h}:${min}`;
}

function updateHookCheckboxState(enabled) {
    document.querySelectorAll('.hook-file-checkbox').forEach(cb => {
        cb.disabled = !enabled;
    });
}

async function loadHookConfig() {
    const container = document.getElementById('hook-files-list');
    const toggle = document.getElementById('hooks-enabled');
    if (!container || !toggle) return;

    container.innerHTML = '<p class="text-secondary">加载中...</p>';

    try {
        const response = await fetch('/api/hooks');
        const result = await response.json();

        if (!result.success) {
            container.innerHTML = `<p class="text-secondary">加载失败：${escapeHtml(result.error || '未知错误')}</p>`;
            return;
        }

        const data = result.data || {};
        const enabled = data.enabled !== false;
        toggle.checked = enabled;

        if (!toggle.dataset.bound) {
            toggle.addEventListener('change', () => updateHookCheckboxState(toggle.checked));
            toggle.dataset.bound = '1';
        }

        const files = Array.isArray(data.files) ? data.files : [];
        if (!files.length) {
            container.innerHTML = '<p class="text-secondary">hooks 目录下暂无 JS 脚本</p>';
            updateHookCheckboxState(enabled);
            return;
        }

        const listHtml = files.map(file => {
            const checked = file.selected ? 'checked' : '';
            return `
                <label class="hook-file-item" style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom: 1px solid var(--bg-tertiary);">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <input type="checkbox" class="hook-file-checkbox" data-filename="${escapeHtml(file.name)}" ${checked}>
                        <span>${escapeHtml(file.name)}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">
                        ${formatHookSize(file.size)} · ${formatHookTimestamp(file.modified_at)}
                    </div>
                </label>
            `;
        }).join('');

        container.innerHTML = listHtml;
        updateHookCheckboxState(enabled);
    } catch (error) {
        console.error('Failed to load hook config:', error);
        container.innerHTML = '<p class="text-secondary">加载 Hook 配置失败</p>';
    }
}

async function saveHookConfig() {
    const toggle = document.getElementById('hooks-enabled');
    const enabled = toggle ? toggle.checked : true;
    const enabledFiles = Array.from(document.querySelectorAll('.hook-file-checkbox'))
        .filter(cb => cb.checked)
        .map(cb => cb.dataset.filename)
        .filter(Boolean);

    try {
        const response = await fetch('/api/hooks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                enabled,
                enabled_files: enabledFiles
            })
        });

        const result = await response.json();
        if (result.success) {
            showNotification('Hook 配置已保存', 'success');
            await loadHookConfig();
        } else {
            showNotification('保存失败：' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('Failed to save hook config:', error);
        showNotification('保存 Hook 配置时发生错误', 'error');
    }
}

async function loadSettings() {
    try {
        const browserResponse = await fetch('/api/config/browser');
        const browserResult = await browserResponse.json();

        if (browserResult.success) {
            const data = browserResult.data;
            if (document.getElementById('chrome-path')) {
                document.getElementById('chrome-path').value = data.chrome_path || '';
                document.getElementById('edge-path').value = data.edge_path || '';
            }
        }

        const configResponse = await fetch('/api/config');
        const configResult = await configResponse.json();

        if (configResult.success) {
            const debugConfig = configResult.data.debug || {};
            if (document.getElementById('auto-save')) {
                document.getElementById('auto-save').checked = debugConfig.auto_save || false;
                document.getElementById('save-interval').value = debugConfig.save_interval || 300;
                document.getElementById('max-duration').value = debugConfig.max_duration || 600;
                document.getElementById('context-chars').value = debugConfig.context_chars || 150;
                document.getElementById('scope-max-depth').value = debugConfig.scope_max_depth || 2;
                document.getElementById('scope-max-total').value = debugConfig.scope_max_total_props || 15;
            }
            try { localStorage.setItem('debugConfig', JSON.stringify(debugConfig)); } catch (e) {}
        }

        await loadHookConfig();
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}


function fixSettingsPagePosition() {
    const settingsPage = document.getElementById('page-settings');
    const mainContent = document.querySelector('.main-content');

    if (settingsPage && mainContent) {
        if (!mainContent.contains(settingsPage)) {
            console.log('Moving settings page into main-content container');
            mainContent.appendChild(settingsPage);
        }
    }
}


let wsInitAttempts = 0;
const maxWsInitAttempts = 50; // 5秒超时
function tryInitWebSocket() {
    if (typeof io !== 'undefined') {
        initWebSocket();
        return true;
    } else if (wsInitAttempts < maxWsInitAttempts) {
        wsInitAttempts++;
        setTimeout(tryInitWebSocket, 100);
        return false;
    } else {
        console.error('❌ Socket.IO加载超时！将在DOMContentLoaded后继续尝试');
        return false;
    }
}

tryInitWebSocket();


const browserNameMap = {
    chrome: 'Chrome',
    edge: 'Edge'
};

function formatSessionTimestamp(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');

    return `${year}.${month} ${hours}:${minutes}`;
}

async function loadRecentSessions() {
    const container = document.getElementById('recent-sessions-container');
    if (!container) return;

    try {
        const response = await fetch('/debug/sessions');
        const result = await response.json();

        const sessions = result.data?.sessions || [];

        if (!result.success || sessions.length === 0) {
            container.innerHTML = '<p class="text-secondary">暂无调试会话</p>';
            return;
        }

        const sorted = sessions.slice().sort((a, b) => {
            const aTs = new Date(a.updated_at || a.created_at || 0).getTime();
            const bTs = new Date(b.updated_at || b.created_at || 0).getTime();
            return bTs - aTs;
        });

        const recentSessions = sorted.slice(0, 3);
        const sessionsHtml = recentSessions.map(session => {
            const createdAt = formatSessionTimestamp(session.updated_at || session.created_at);
            const status = session.status === 'running' ?
                '<span style="color: var(--accent-success);">● 运行中</span>' :
                '<span style="color: var(--text-tertiary);">● 已结束</span>';
            const browser = browserNameMap[session.browser_type] || session.browser_type || 'Chrome';

            return `
                <div style="padding: 12px; margin-bottom: 8px; background: var(--bg-tertiary); border-radius: 8px; cursor: pointer;"
                     onclick="loadSessionAndStartDebug('${session.id || session.session_id}')">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <strong class="recent-session-url" style="font-size: 0.875rem;">${session.target_url || 'Unknown URL'}</strong>
                        ${status}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">
                        ${createdAt} · ${browser}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = sessionsHtml;
    } catch (error) {
        console.error('Failed to load recent sessions:', error);
        container.innerHTML = '<p class="text-secondary">加载失败</p>';
    }
}

async function loadSessionAndStartDebug(sessionId) {
    try {
        const response = await fetch(`/debug/session/${sessionId}`);
        const result = await response.json();

        if (!result.success || !result.data) {
            showNotification('无法加载会话配置', 'error');
            return;
        }

        await ensureAIProviderOptions();
        const session = result.data;
        const config = session.config || {};
        const mode = session.breakpoint_mode || 'js';

        const targetInput = document.getElementById('target-url');
        if (targetInput) {
            targetInput.value = session.target_url || '';
        }

        const browserSelect = document.getElementById('browser-type');
        if (browserSelect) {
            browserSelect.value = session.browser_type || 'chrome';
        }

        const aiProviderSelect = document.getElementById('ai-provider');
        if (aiProviderSelect) {
            const providerValue = session.ai_provider || defaultAIProvider || aiProviderSelect.value || 'qwen';
            refreshAIProviderSelect(providerValue);
            aiProviderSelect.value = providerValue;
        }

        const breakpointRadios = document.querySelectorAll('input[name="breakpoint-mode"]');
        breakpointRadios.forEach(radio => {
            radio.checked = radio.value === mode;
        });

        const jsModePanel = document.getElementById('js-mode-config');
        const xhrModePanel = document.getElementById('xhr-mode-config');
        if (jsModePanel && xhrModePanel) {
            jsModePanel.style.display = mode === 'js' ? 'block' : 'none';
            xhrModePanel.style.display = mode === 'xhr' ? 'block' : 'none';
        }

        const jsFileInput = document.getElementById('js-file');
        if (jsFileInput) {
            jsFileInput.value = config.js_file || config.js_file_path || '';
        }

        const lineInput = document.getElementById('line-number');
        if (lineInput) {
            lineInput.value = (config.line ?? config.line_number ?? 0);
        }

        const columnInput = document.getElementById('column-number');
        if (columnInput) {
            columnInput.value = (config.column ?? config.column_number ?? 0);
        }

        const xhrInput = document.getElementById('xhr-url');
        if (xhrInput) {
            xhrInput.value = config.xhr_url || config.xhr_url_pattern || '';
        }

        showPage('config');
        showNotification('会话配置已加载', 'success');
    } catch (error) {
        console.error('Failed to load session:', error);
        showNotification('加载会话失败', 'error');
    }
}

window.loadSessionAndStartDebug = loadSessionAndStartDebug;

document.addEventListener('DOMContentLoaded', () => {
    console.log('AI_JS_DEBUGGER initializing...');

    if (!AppState.socket) {
        console.log('⚠️ WebSocket尚未初始化，在DOMContentLoaded时重试...');
        initWebSocket();
    }

    lucide.createIcons();

    fixSettingsPagePosition();

    initTheme();
    initNavbarScroll();
    initBreakpointModeToggle();
    initDebugConfigForm();
    initAIProviderOptions();

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    if (typeof window.pageChangeCallbacks === 'undefined') {
        window.pageChangeCallbacks = [];
    }
    window.pageChangeCallbacks.push((pageName) => {
        if (pageName === 'settings') {
            loadSettings();
        }
        if (pageName === 'dashboard') {
            loadRecentSessions();
        }
    });

    loadRecentSessions();

    console.log('AI_JS_DEBUGGER initialized');
});
