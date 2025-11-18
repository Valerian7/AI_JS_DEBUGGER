/**
 * AI 配置管理模块
 */


let aiProviders = [];
let customModels = {}; // 存储自定义模型配置
let providerModelCache = {};
let aiProxies = [];

const providerPresets = {
    openai: {
        displayName: 'OpenAI GPT',
        logo: '/static/assets/provider-logos/openai.svg',
        defaultModels: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini'],
        baseUrl: 'https://api.openai.com/v1'
    },
    claude: {
        displayName: 'Claude',
        logo: '/static/assets/provider-logos/claude.svg',
        defaultModels: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus'],
        baseUrl: 'https://api.anthropic.com/v1'
    },
    deepseek: {
        displayName: 'DeepSeek',
        logo: '/static/assets/provider-logos/deepseek.svg',
        defaultModels: ['deepseek-chat', 'deepseek-reasoner'],
        baseUrl: 'https://api.deepseek.com/v1'
    },
    qwen: {
        displayName: '通义千问',
        logo: '/static/assets/provider-logos/qwen.svg',
        defaultModels: ['qwen-plus-2025-01-25', 'qwen-turbo', 'qwen-long'],
        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    },
    kimi: {
        displayName: 'Kimi (Moonshot)',
        logo: '/static/assets/provider-logos/kimi.svg',
        defaultModels: ['moonshot-v1-8k', 'moonshot-v1-32k'],
        baseUrl: 'https://api.moonshot.cn/v1'
    },
    glm: {
        displayName: '智谱 GLM',
        logo: '/static/assets/provider-logos/glm.svg',
        defaultModels: ['glm-4-plus', 'glm-4-air', 'glm-4-flash'],
        baseUrl: 'https://open.bigmodel.cn/api/paas/v4'
    },
    minimax: {
        displayName: 'MiniMax',
        logo: '/static/assets/provider-logos/minimax.svg',
        defaultModels: ['abab6.5-chat', 'abab6.5s-chat'],
        baseUrl: 'https://api.minimax.chat/v1'
    },
    kat: {
        displayName: '快手 KAT',
        logo: '/static/assets/provider-logos/kat.svg',
        defaultModels: ['kat-8k', 'kat-32k'],
        baseUrl: 'https://api.kuaishou.com/kat/v1',
        requiresVanchin: true
    }
};

const defaultModels = Object.fromEntries(
    Object.entries(providerPresets).map(([key, meta]) => [key, meta.defaultModels || []])
);

async function loadAIProviders() {
    try {
        const response = await fetch('/api/providers');
        const result = await response.json();

        if (result.success) {
            const defaultProvider = result.data.default;
            const customDisplayNames = JSON.parse(localStorage.getItem('customProviderNames') || '{}');
            aiProviders = (result.data.providers || []).map(provider => {
                const preset = providerPresets[provider.name] || {};
                const displayLabel = provider.display_name
                    || customDisplayNames[provider.name]
                    || preset.displayName
                    || provider.name;
                const modelsFromServer = Array.isArray(provider.available_models) ? provider.available_models : [];
                const presetModels = defaultModels[provider.name] || [];
                const combinedModels = Array.from(new Set([
                    ...presetModels,
                    ...modelsFromServer
                ])).filter(Boolean);
                providerModelCache[provider.name] = combinedModels.slice();
                if (!Array.isArray(customModels[provider.name])) {
                    customModels[provider.name] = [];
                }
                const extras = combinedModels.filter(m => !(presetModels.includes(m)));
                customModels[provider.name] = Array.from(new Set([...customModels[provider.name], ...extras]));
                return {
                    ...preset,
                    ...provider,
                    display_name: displayLabel,
                    logo: provider.logo || preset.logo,
                    base_url: provider.base_url || preset.baseUrl || '',
                    available_models: combinedModels,
                    is_default: provider.name === defaultProvider,
                    requires_vanchin: preset.requiresVanchin || false
                };
            });
            try { localStorage.setItem('customModels', JSON.stringify(customModels)); } catch (e) {}
            renderAIProvidersList();
        }
    } catch (error) {
        console.error('Error loading AI providers:', error);
    }
}

function renderAIProvidersList() {
    const container = document.getElementById('ai-providers-list');
    if (!container) return;

    const defaultProvider = aiProviders.find(p => p.is_default) || {};

    let html = `
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0;">已配置的提供商</h3>
            <button class="btn btn-primary" onclick="showAddProviderModal()" style="padding: 8px 16px;">
                <i data-lucide="plus"></i>
                添加新提供商
            </button>
        </div>
        <div class="providers-grid">
    `;

    html += aiProviders.map(provider => {
        const isDefault = provider.is_default || false;
        const isConfigured = provider.configured || false;
        const preset = providerPresets[provider.name] || {};
        const isCustom = provider.custom || !(provider.name in providerPresets);
        const badgeHtml = `
            ${isDefault ? '<span class="badge badge-default"><i data-lucide="star" style="width: 12px; height: 12px;"></i> 默认</span>' : ''}
            ${isCustom ? '<span class="badge badge-custom"><i data-lucide="layers" style="width: 12px; height: 12px;"></i> 自定义</span>' : ''}
            ${isConfigured ? '<span class="badge badge-configured"><i data-lucide="check" style="width: 12px; height: 12px;"></i> 已配置</span>' : ''}
        `;
        const logo = provider.logo || preset.logo;
        const logoContent = logo
            ? `<img src="${logo}" alt="${provider.display_name || provider.name}">`
            : `<span style="color: var(--text-secondary); font-weight: 600;">${(provider.display_name || provider.name || '?').slice(0,2).toUpperCase()}</span>`;

        return `
        <div class="provider-card">
            <div class="provider-card-header">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div class="provider-logo">
                        ${logoContent}
                    </div>
                    <div>
                        <h4 class="card-title" style="margin: 0; font-size: 1rem;">
                            ${provider.display_name || getProviderDisplayName(provider.name)}
                        </h4>
                        <div style="display:flex; gap: 6px; flex-wrap: wrap; margin-top: 4px;">
                            ${badgeHtml}
                        </div>
                    </div>
                </div>
                <div style="display:flex; gap:8px;">
                    ${isConfigured && !isDefault ? `
                        <button class="action-icon" onclick="setDefaultProvider('${provider.name}')" title="设为默认">
                            <i data-lucide="star"></i>
                        </button>
                    ` : ''}
                    <button class="action-icon" onclick="editAIProvider('${provider.name}')" title="配置">
                        <i data-lucide="settings-2"></i>
                    </button>
                    <button class="action-icon" onclick="deleteAIProvider('${provider.name}')" title="删除">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
            <div class="provider-card-body">
                <p style="margin:0; font-size:0.85rem; color: var(--text-secondary);">默认模型</p>
                <p style="margin:4px 0 0; font-size:0.95rem; font-family: var(--font-mono);">${provider.model || '未配置'}</p>
                ${provider.analysis_model ? `
                    <p style="margin:12px 0 0; font-size:0.85rem; color: var(--text-secondary);">分析模型</p>
                    <p style="margin:4px 0 0; font-size:0.95rem; font-family: var(--font-mono);">${provider.analysis_model}</p>
                ` : ''}
            </div>
        </div>
        `;
    }).join('');

    html += '</div>';

    container.innerHTML = html;
    lucide.createIcons();
}

function getProviderDisplayName(name) {
    const preset = providerPresets[name];
    const customDisplayNames = JSON.parse(localStorage.getItem('customProviderNames') || '{}');
    if (customDisplayNames[name]) return customDisplayNames[name];
    if (preset && preset.displayName) return preset.displayName;
    return name;
}

async function editAIProvider(providerName) {
    try {
        const response = await fetch(`/api/config/ai?provider=${providerName}`);
        const result = await response.json();

        if (result.success) {
            showAIConfigModal(providerName, result.data);
        }
    } catch (error) {
        console.error('Error loading AI provider config:', error);
        showNotification('加载配置失败', 'error');
    }
}

function showAIConfigModal(providerName, config) {
    const modal = document.createElement('div');
    modal.id = 'ai-config-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 24px;
    `;

    const preset = providerPresets[providerName] || {};
    const models = defaultModels[providerName] || [];
    const configModels = Array.isArray(config.available_models) ? config.available_models : [];
    const storedCustomList = customModels[providerName] || [];
    const derived = [config.model, config.analysis_model].filter(Boolean);
    customModels[providerName] = Array.from(new Set([
        ...storedCustomList,
        ...configModels.filter(m => !models.includes(m)),
        ...derived.filter(m => !models.includes(m))
    ]));
    try { localStorage.setItem('customModels', JSON.stringify(customModels)); } catch (e) {}
    const allModels = [...new Set([
        ...models,
        ...configModels,
        ...customModels[providerName],
        ...derived
    ])].filter(Boolean);
    const proxyOptions = aiProxies.map(proxy => `
        <option value="${proxy.id}" ${proxy.id === config.proxy_id ? 'selected' : ''}>${proxy.name} (${proxy.type}://${proxy.host}:${proxy.port})</option>
    `).join('');
    const requiresVanchin = preset.requiresVanchin || config.requires_vanchin;

    modal.innerHTML = `
        <div style="background: var(--bg-secondary); border-radius: 16px; max-width: 600px; width: 100%; box-shadow: var(--shadow-xl);">
            <div style="padding: 24px; border-bottom: 1px solid var(--divider-color); display: flex; align-items: center; justify-content: space-between;">
                <h2 style="margin: 0;">配置 ${getProviderDisplayName(providerName)}</h2>
                <button class="btn btn-icon" onclick="closeAIConfigModal()" style="width: 40px; height: 40px;">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div style="padding: 24px;">
                <form id="ai-provider-form" onsubmit="saveAIProviderConfig(event, '${providerName}')">
                    <div class="form-group">
                        <label class="form-label">API Key</label>
                        <input type="password" class="form-input" id="modal-api-key" placeholder="输入 API Key">
                        ${config.api_key ? `<p style=\"font-size: 0.8125rem; color: var(--text-secondary); margin-top: 6px;\">当前已配置：<span style=\"font-family: var(--font-mono);\">${config.api_key}</span></p>` : ''}
                        <p style="font-size: 0.8125rem; color: var(--text-tertiary); margin-top: 4px;">
                            ${getProviderHelpText(providerName)}
                        </p>
                    </div>

                    <div class="form-group">
                        <label class="form-label">调试模型</label>
                        <select class="form-select" id="modal-model" required>
                            ${allModels.map(model => `
                                <option value="${model}" ${model === config.model ? 'selected' : ''}>${model}</option>
                            `).join('')}
                            <option value="__custom__">添加自定义模型...</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label class="form-label">分析模型</label>
                        <select class="form-select" id="modal-analysis-model">
                            ${allModels.map(model => `
                                <option value="${model}" ${model === (config.analysis_model || config.model) ? 'selected' : ''}>${model}</option>
                            `).join('')}
                        </select>
                    </div>

                    <div class="form-group" id="custom-model-input" style="display: none;">
                        <label class="form-label">自定义模型名称</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="text" class="form-input" id="modal-custom-model" placeholder="例如: gpt-4-1106-preview" style="flex: 1;">
                            <button type="button" class="btn btn-primary" onclick="addCustomModel('${providerName}')" style="padding: 8px 16px;">
                                <i data-lucide="plus" style="width: 16px; height: 16px;"></i>
                                添加
                            </button>
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">自定义模型管理</label>
                        <div id="custom-model-section" class="custom-model-panel"></div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">API Base URL</label>
                        <input type="text" class="form-input" id="modal-base-url" placeholder="留空使用官方 API" value="${config.base_url || preset.baseUrl || ''}">
                        <p style="font-size: 0.8125rem; color: var(--text-tertiary); margin-top: 4px;">
                            如使用代理/自建网关，填写完整的 Base URL
                        </p>
                    </div>

                    <div class="form-group">
                        <label class="form-label">网络代理</label>
                        <select class="form-select" id="modal-proxy">
                            <option value="">直接连接（不使用代理）</option>
                            ${proxyOptions || '<option value="" disabled>尚未配置代理</option>'}
                        </select>
                    </div>

                    ${requiresVanchin ? `
                        <div class="form-group">
                            <label class="form-label">Vanchin Endpoint ID</label>
                            <input type="text" class="form-input" id="modal-vanchin" placeholder="快手 KAT 专用" value="${config.vanchin_endpoint_id || ''}">
                        </div>
                    ` : ''}

                    <div style="display: flex; gap: 12px; margin-top: 24px;">
                        <button type="button" class="btn btn-secondary" onclick="closeAIConfigModal()" style="flex: 1;">
                            取消
                        </button>
                        <button type="button" class="btn btn-primary" onclick="testAIConnection('${providerName}')" style="flex: 1;">
                            <i data-lucide="zap"></i>
                            测试连接
                        </button>
                        <button type="submit" class="btn btn-primary" style="flex: 1;">
                            <i data-lucide="save"></i>
                            保存
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    lucide.createIcons();

    modal.dataset.provider = providerName;
    rebuildModelSelects(providerName, config.model, config.analysis_model || config.model);
    updateCustomModelSection(providerName);

    document.getElementById('modal-model').addEventListener('change', (e) => {
        const customInput = document.getElementById('custom-model-input');
        if (e.target.value === '__custom__') {
            customInput.style.display = 'block';
        } else {
            customInput.style.display = 'none';
        }
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeAIConfigModal();
        }
    });
}

function getProviderHelpText(providerName) {
    const helpTexts = {
        'qwen': '从<a href="https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key" target="_blank" style="color: var(--accent-blue);">阿里云</a>获取 API Key',
        'openai': '从<a href="https://platform.openai.com/api-keys" target="_blank" style="color: var(--accent-blue);">OpenAI</a>获取 API Key',
        'deepseek': '从<a href="https://platform.deepseek.com/" target="_blank" style="color: var(--accent-blue);">Deepseek</a>获取 API Key',
        'ernie': '从<a href="https://cloud.baidu.com/" target="_blank" style="color: var(--accent-blue);">百度智能云</a>获取 API Key',
        'spark': '从<a href="https://www.xfyun.cn/" target="_blank" style="color: var(--accent-blue);">讯飞开放平台</a>获取 API Key',
        'claude': '从<a href="https://console.anthropic.com/" target="_blank" style="color: var(--accent-blue);">Anthropic 控制台</a>获取 API Key',
        'kimi': '从<a href="https://platform.moonshot.cn/" target="_blank" style="color: var(--accent-blue);">Moonshot</a>获取 API Key',
        'glm': '从<a href="https://open.bigmodel.cn/" target="_blank" style="color: var(--accent-blue);">智谱 AI</a>获取 API Key',
        'minimax': '从<a href="https://www.minimaxi.com/" target="_blank" style="color: var(--accent-blue);">MiniMax 控制台</a>获取 API Key',
        'kat': '从<a href="https://open.kuaishou.com/" target="_blank" style="color: var(--accent-blue);">快手开放平台</a>申请 API Key 与 Endpoint'
    };
    return helpTexts[providerName] || '请输入您的 API Key';
}

async function saveAIProviderConfig(event, providerName) {
    event.preventDefault();

    const apiKey = document.getElementById('modal-api-key').value;
    let model = document.getElementById('modal-model').value;
    let analysisModel = document.getElementById('modal-analysis-model').value;

    if (model === '__custom__') {
        model = document.getElementById('modal-custom-model').value.trim();
        if (!model) {
            showNotification('请输入自定义模型名称', 'warning');
            return;
        }
        if (!customModels[providerName]) {
            customModels[providerName] = [];
        }
        if (!customModels[providerName].includes(model)) {
            customModels[providerName].push(model);
        }
    }

    const data = {
        provider: providerName,
        model: model,
        analysis_model: analysisModel,
        available_models: Array.from(new Set([
            ...(providerModelCache[providerName] || []),
            ...(customModels[providerName] || [])
        ])).filter(Boolean)
    };
    if (apiKey && apiKey.trim() !== '') {
        data.api_key = apiKey.trim();
    }

    const baseUrlInput = document.getElementById('modal-base-url');
    if (baseUrlInput) {
        data.base_url = baseUrlInput.value.trim();
    }

    const proxySelect = document.getElementById('modal-proxy');
    if (proxySelect) {
        data.proxy_id = proxySelect.value || null;
    }

    const vanchinInput = document.getElementById('modal-vanchin');
    if (vanchinInput) {
        data.vanchin_endpoint_id = vanchinInput.value.trim();
    }

    try {
        const response = await fetch('/api/config/ai', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('配置已保存', 'success');
            closeAIConfigModal();
            loadAIProviders();
        } else {
            showNotification('保存配置失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error saving AI provider config:', error);
        showNotification('保存配置时发生错误', 'error');
    }
}

async function testAIConnection(providerName) {
    const apiKey = document.getElementById('modal-api-key').value.trim();
    const model = document.getElementById('modal-model').value;
    const baseUrl = document.getElementById('modal-base-url')?.value.trim();
    const proxySelect = document.getElementById('modal-proxy');
    const vanchinInput = document.getElementById('modal-vanchin');

    const payload = {
        provider: providerName,
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        proxy_id: proxySelect ? (proxySelect.value || null) : null,
        vanchin_endpoint_id: vanchinInput ? vanchinInput.value.trim() : undefined
    };

    showNotification('正在测试连接...', 'info');

    try {
        const response = await fetch('/api/test-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.success) {
            showNotification('连接测试成功！模型可用。', 'success');
        } else {
            const msg = result.error || '连接测试失败';
            showNotification(msg, 'error');
        }
    } catch (error) {
        console.error('Error testing AI connection:', error);
        showNotification('测试连接时发生错误', 'error');
    }
}

async function loadAIProxies() {
    try {
        const response = await fetch('/api/ai/proxies');
        const result = await response.json();
        if (result.success) {
            aiProxies = result.data.proxies || [];
            renderAIProxyList();
        }
    } catch (error) {
        console.error('Failed to load proxies:', error);
    }
}

function renderAIProxyList() {
    const container = document.getElementById('ai-proxies-list');
    if (!container) return;
    if (!aiProxies.length) {
        container.innerHTML = '<p class="text-secondary" style="text-align:center;">暂无代理配置，点击“添加代理”开始配置</p>';
        return;
    }
    container.innerHTML = aiProxies.map(proxy => `
        <div class="proxy-card">
            <div class="proxy-card-info">
                <strong>${proxy.name}</strong>
                <div style="display:flex; gap:6px; flex-wrap:wrap;">
                    <span class="proxy-chip">${proxy.type.toUpperCase()}</span>
                    <span class="proxy-chip">${proxy.host}:${proxy.port}</span>
                    ${proxy.use_auth ? '<span class="proxy-chip">需要认证</span>' : ''}
                </div>
            </div>
            <div class="proxy-actions">
                <button class="action-icon" title="测试连接" onclick="testProxy('${proxy.id}')">
                    <i data-lucide="zap"></i>
                </button>
                <button class="action-icon" title="编辑" onclick="showProxyModal('${proxy.id}')">
                    <i data-lucide="edit-2"></i>
                </button>
                <button class="action-icon" title="删除" onclick="deleteProxy('${proxy.id}')">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        </div>
    `).join('');
    lucide.createIcons();
}

async function showProxyModal(proxyId) {
    let existing = aiProxies.find(p => p.id === proxyId) || {};
    if (proxyId) {
        try {
            const response = await fetch(`/api/ai/proxies/${proxyId}`);
            const result = await response.json();
            if (result.success) {
                existing = result.data || existing;
            } else {
                showNotification(result.error || '无法加载代理配置', 'error');
            }
        } catch (error) {
            console.error('Failed to load proxy detail:', error);
            showNotification('加载代理配置失败', 'error');
        }
    }

    const isEditing = Boolean(proxyId);
    const hasPassword = Boolean(existing.has_password);

    const modal = document.createElement('div');
    modal.id = 'proxy-modal';
    modal.style.cssText = `
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.45);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 24px;
    `;
    modal.innerHTML = `
        <div style="background: var(--bg-secondary); border-radius: 16px; width: 480px; max-width: 100%; box-shadow: var(--shadow-xl);">
            <div style="padding: 20px; border-bottom: 1px solid var(--divider-color); display:flex; justify-content: space-between; align-items:center;">
                <h3 style="margin:0;">${proxyId ? '编辑代理' : '添加代理'}</h3>
                <button class="btn btn-icon" onclick="closeProxyModal()"><i data-lucide="x"></i></button>
            </div>
            <form id="proxy-form" style="padding: 20px;" onsubmit="saveProxyConfig(event, '${proxyId || ''}')">
                <div class="form-group">
                    <label class="form-label">名称</label>
                    <input type="text" class="form-input" id="proxy-name" value="${existing.name || ''}" required>
                </div>
                <div class="form-group">
                    <label class="form-label">类型</label>
                    <select class="form-select" id="proxy-type" required>
                        ${['http', 'https', 'socks5'].map(type => `<option value="${type}" ${existing.type === type ? 'selected' : ''}>${type.toUpperCase()}</option>`).join('')}
                    </select>
                </div>
                <div style="display:grid; grid-template-columns: 2fr 1fr; gap:12px;">
                    <div class="form-group">
                        <label class="form-label">主机</label>
                        <input type="text" class="form-input" id="proxy-host" value="${existing.host || ''}" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">端口</label>
                        <input type="number" class="form-input" id="proxy-port" value="${existing.port || ''}" required>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    <div class="form-group">
                        <label class="form-label">用户名（可选）</label>
                        <input type="text" class="form-input" id="proxy-username" value="${existing.username || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label" style="display:flex; justify-content:space-between; align-items:center;">
                            <span>密码（可选）</span>
                            ${hasPassword ? '<button type="button" class="text-link" style="font-size:0.8rem;" onclick="clearProxyPassword()">清空</button>' : ''}
                        </label>
                        <input type="password" class="form-input" id="proxy-password"
                               placeholder="${hasPassword ? '已设置，留空则保持' : '请输入密码'}"
                               data-dirty="${isEditing ? '0' : '1'}"
                               value="">
                    </div>
                </div>
                <div style="display:flex; gap:12px; margin-top:20px;">
                    <button type="button" class="btn btn-secondary" onclick="closeProxyModal()" style="flex:1;">取消</button>
                    <button type="button" class="btn btn-primary" onclick="testProxy(null, true)" style="flex:1;">
                        <i data-lucide="zap"></i> 测试
                    </button>
                    <button type="submit" class="btn btn-primary" style="flex:1;">
                        <i data-lucide="save"></i> 保存
                    </button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    lucide.createIcons();
    setupProxyPasswordInput(hasPassword);
}

function closeProxyModal() {
    const modal = document.getElementById('proxy-modal');
    if (modal) modal.remove();
}

async function saveProxyConfig(event, proxyId) {
    event.preventDefault();
    const payload = {
        id: proxyId || undefined,
        name: document.getElementById('proxy-name').value.trim(),
        type: document.getElementById('proxy-type').value,
        host: document.getElementById('proxy-host').value.trim(),
        port: document.getElementById('proxy-port').value,
        username: document.getElementById('proxy-username').value.trim()
    };
    const passwordInput = document.getElementById('proxy-password');
    if (passwordInput) {
        if (passwordInput.dataset.dirty === '1') {
            payload.password = passwordInput.value;
        }
    }
    try {
        const response = await fetch('/api/ai/proxies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.success) {
            showNotification('代理配置已保存', 'success');
            closeProxyModal();
            await loadAIProxies();
            await loadAIProviders();
        } else {
            showNotification(result.error || '保存失败', 'error');
        }
    } catch (error) {
        console.error('Failed to save proxy:', error);
        showNotification('保存代理时发生错误', 'error');
    }
}

function setupProxyPasswordInput(hasPassword) {
    const input = document.getElementById('proxy-password');
    if (!input) return;
    if (hasPassword) {
        input.dataset.hasPassword = '1';
    }
    input.addEventListener('input', () => {
        input.dataset.dirty = '1';
    });
}

function clearProxyPassword() {
    const input = document.getElementById('proxy-password');
    if (!input) return;
    input.value = '';
    input.dataset.dirty = '1';
    input.placeholder = '保存后将清空密码';
}

async function deleteProxy(proxyId) {
    if (!proxyId) return;
    if (!confirm('确定要删除该代理吗？')) return;
    try {
        const response = await fetch(`/api/ai/proxies/${proxyId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            showNotification('代理已删除', 'success');
            await loadAIProxies();
            await loadAIProviders();
        } else {
            showNotification(result.error || '删除失败', 'error');
        }
    } catch (error) {
        console.error('Failed to delete proxy:', error);
        showNotification('删除代理时发生错误', 'error');
    }
}

async function testProxy(proxyId, fromModal = false) {
    let payload = {};
    if (fromModal) {
        payload = {
            name: document.getElementById('proxy-name').value.trim(),
            type: document.getElementById('proxy-type').value,
            host: document.getElementById('proxy-host').value.trim(),
            port: document.getElementById('proxy-port').value,
            username: document.getElementById('proxy-username').value.trim(),
            password: document.getElementById('proxy-password').value
        };
    } else {
        payload.id = proxyId;
    }
    try {
        showNotification('正在测试代理...', 'info');
        const response = await fetch('/api/ai/proxies/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.success) {
            showNotification(result.message || '代理测试成功', 'success');
        } else {
            showNotification(result.error || '代理测试失败', 'error');
        }
    } catch (error) {
        console.error('Failed to test proxy:', error);
        showNotification('代理测试时发生错误', 'error');
    }
}

function rebuildModelSelects(providerName, preferredModel, preferredAnalysis) {
    const modelSelect = document.getElementById('modal-model');
    const analysisSelect = document.getElementById('modal-analysis-model');
    if (!modelSelect || !analysisSelect) return;

    const base = defaultModels[providerName] || [];
    const cache = providerModelCache[providerName] || [];
    const custom = customModels[providerName] || [];
    const models = Array.from(new Set([...base, ...cache, ...custom])).filter(Boolean);

    const prevModel = preferredModel || modelSelect.value;
    const prevAnalysis = preferredAnalysis || analysisSelect.value;

    const optionsHtml = models.map(model => `<option value="${model}">${model}</option>`).join('');
    const customOption = '<option value="__custom__">添加自定义模型...</option>';

    modelSelect.innerHTML = optionsHtml + customOption;
    analysisSelect.innerHTML = optionsHtml;
    analysisSelect.disabled = models.length === 0;

    const ensureValue = (select, desired, fallback) => {
        if (desired && Array.from(select.options).some(opt => opt.value === desired)) {
            select.value = desired;
        } else if (fallback && Array.from(select.options).some(opt => opt.value === fallback)) {
            select.value = fallback;
        } else if (select.options.length > 0) {
            select.selectedIndex = 0;
        }
    };

    if (models.length === 0) {
        modelSelect.value = '__custom__';
        analysisSelect.innerHTML = '';
    } else {
        ensureValue(modelSelect, prevModel, models[0]);
        ensureValue(analysisSelect, prevAnalysis, models[0]);
    }

    const customInput = document.getElementById('custom-model-input');
    if (customInput) {
        customInput.style.display = modelSelect.value === '__custom__' ? 'block' : 'none';
    }
}

function updateCustomModelSection(providerName) {
    const container = document.getElementById('custom-model-section');
    if (!container) return;
    const list = customModels[providerName] || [];
    if (!list.length) {
        container.innerHTML = '<span style="font-size:0.85rem; color: var(--text-secondary);">暂无自定义模型，可通过上方输入添加</span>';
        return;
    }
    container.innerHTML = list.map(model => `
        <span class="custom-model-pill">
            ${model}
            <button type="button" onclick="removeCustomModel('${providerName}', '${model}')" title="删除">
                <i data-lucide="x"></i>
            </button>
        </span>
    `).join('');
    lucide.createIcons();
}

async function persistCustomModels(providerName) {
    const payload = {
        provider: providerName,
        available_models: Array.from(new Set([
            ...(providerModelCache[providerName] || []),
            ...(customModels[providerName] || [])
        ])).filter(Boolean)
    };
    const modelSelect = document.getElementById('modal-model');
    const analysisSelect = document.getElementById('modal-analysis-model');
    if (modelSelect && modelSelect.value && modelSelect.value !== '__custom__') {
        payload.model = modelSelect.value;
    }
    if (analysisSelect && analysisSelect.value) {
        payload.analysis_model = analysisSelect.value;
    }

    try {
        const response = await fetch('/api/config/ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!result.success) {
            console.warn('Failed to update model list:', result.error);
        }
    } catch (error) {
        console.error('Persist custom models failed:', error);
    }
}

function addCustomModel(providerName) {
    const input = document.getElementById('modal-custom-model');
    const modelName = input.value.trim();

    if (!modelName) {
        showNotification('请输入模型名称', 'warning');
        return;
    }

    if (!customModels[providerName]) {
        customModels[providerName] = [];
    }

    if (customModels[providerName].includes(modelName)) {
        showNotification('该模型已存在', 'warning');
        return;
    }

    customModels[providerName].push(modelName);

    localStorage.setItem('customModels', JSON.stringify(customModels));

    if (!providerModelCache[providerName]) {
        providerModelCache[providerName] = [];
    }
    providerModelCache[providerName] = Array.from(new Set([...providerModelCache[providerName], modelName]));

    addModelToLocalStorage(providerName);
    rebuildModelSelects(providerName, modelName, modelName);
    updateCustomModelSection(providerName);
    persistCustomModels(providerName);
    input.value = '';
    document.getElementById('custom-model-input').style.display = 'none';

    showNotification(`已添加模型: ${modelName}`, 'success');
}

function removeCustomModel(providerName, modelName) {
    if (!customModels[providerName]) {
        return;
    }

    const index = customModels[providerName].indexOf(modelName);
    if (index > -1) {
        customModels[providerName].splice(index, 1);
        providerModelCache[providerName] = (providerModelCache[providerName] || []).filter(m => m !== modelName);
        addModelToLocalStorage(providerName);
        rebuildModelSelects(providerName);
        updateCustomModelSection(providerName);
        persistCustomModels(providerName);
        showNotification(`已删除模型: ${modelName}`, 'info');
    }
}

function addModelToLocalStorage(providerName) {
    try {
        localStorage.setItem('customModels', JSON.stringify(customModels));
    } catch (e) {}
}

function closeAIConfigModal() {
    const modal = document.getElementById('ai-config-modal');
    if (modal) {
        modal.remove();
    }
}

async function setDefaultProvider(providerName) {
    try {
        const response = await fetch('/api/config/ai/default', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                provider: providerName
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`${getProviderDisplayName(providerName)} 已设为默认提供商`, 'success');
            loadAIProviders();
        } else {
            showNotification('设置默认提供商失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error setting default provider:', error);
        showNotification('设置默认提供商时发生错误', 'error');
    }
}

async function deleteAIProvider(providerName) {
    const isBuiltIn = ['openai', 'qwen', 'deepseek', 'ernie', 'spark'].includes(providerName);
    const message = `确定要删除提供商 ${getProviderDisplayName(providerName)} 吗？此操作会从配置中移除该提供商。`;

    if (!confirm(message)) {
        return;
    }

    try {
        const response = await fetch(`/api/config/ai/${providerName}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`${getProviderDisplayName(providerName)} 已删除`, 'success');
            loadAIProviders();
        } else {
            showNotification('操作失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error deleting AI provider:', error);
        showNotification('操作时发生错误', 'error');
    }
}

function showAddProviderModal() {
    const modal = document.createElement('div');
    modal.id = 'add-provider-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 24px;
    `;

    modal.innerHTML = `
        <div style="background: var(--bg-secondary); border-radius: 16px; max-width: 600px; width: 100%; box-shadow: var(--shadow-xl);">
            <div style="padding: 24px; border-bottom: 1px solid var(--divider-color); display: flex; align-items: center; justify-content: space-between;">
                <h2 style="margin: 0;">添加新的 AI 提供商</h2>
                <button class="btn btn-icon" onclick="closeAddProviderModal()" style="width: 40px; height: 40px;">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div style="padding: 24px;">
                <form id="add-provider-form" onsubmit="saveNewProvider(event)">
                    <div class="form-group">
                        <label class="form-label">提供商名称</label>
                        <input type="text" class="form-input" id="new-provider-name" placeholder="例如: claude, gemini" required>
                        <p style="font-size: 0.8125rem; color: var(--text-tertiary); margin-top: 4px;">
                            请使用英文名称，不要包含空格
                        </p>
                    </div>

                    <div class="form-group">
                        <label class="form-label">显示名称</label>
                        <input type="text" class="form-input" id="new-provider-display" placeholder="例如: Claude AI, Gemini" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">API Base URL</label>
                        <input type="url" class="form-input" id="new-provider-url" placeholder="https://api.example.com/v1" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">默认模型</label>
                        <input type="text" class="form-input" id="new-provider-model" placeholder="例如: claude-3, gemini-pro" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">API Key（可选）</label>
                        <input type="password" class="form-input" id="new-provider-key" placeholder="稍后在配置中设置">
                    </div>

                    <div style="display: flex; gap: 12px; margin-top: 24px;">
                        <button type="button" class="btn btn-secondary" onclick="closeAddProviderModal()" style="flex: 1;">
                            取消
                        </button>
                        <button type="submit" class="btn btn-primary" style="flex: 1;">
                            <i data-lucide="plus"></i>
                            添加提供商
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    lucide.createIcons();

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeAddProviderModal();
        }
    });
}

function closeAddProviderModal() {
    const modal = document.getElementById('add-provider-modal');
    if (modal) {
        modal.remove();
    }
}

async function saveNewProvider(event) {
    event.preventDefault();

    const name = document.getElementById('new-provider-name').value.trim().toLowerCase();
    const displayName = document.getElementById('new-provider-display').value.trim();
    const baseUrl = document.getElementById('new-provider-url').value.trim();
    const model = document.getElementById('new-provider-model').value.trim();
    const apiKey = document.getElementById('new-provider-key').value.trim();

    if (!/^[a-z0-9_-]+$/.test(name)) {
        showNotification('提供商名称只能包含小写字母、数字、下划线和连字符', 'warning');
        return;
    }

    const customDisplayNames = JSON.parse(localStorage.getItem('customProviderNames') || '{}');
    customDisplayNames[name] = displayName;
    localStorage.setItem('customProviderNames', JSON.stringify(customDisplayNames));

    try {
        const response = await fetch('/api/providers/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                config: {
                    api_key: apiKey,
                    model: model,
                    base_url: baseUrl
                }
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`提供商 ${displayName} 添加成功`, 'success');
            closeAddProviderModal();
            loadAIProviders();
        } else {
            showNotification('添加提供商失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error adding provider:', error);
        showNotification('添加提供商时发生错误', 'error');
    }
}

if (typeof window.pageChangeCallbacks === 'undefined') {
    window.pageChangeCallbacks = [];
}

const savedModels = localStorage.getItem('customModels');
if (savedModels) {
    try {
        customModels = JSON.parse(savedModels);
    } catch (e) {
        console.error('Failed to load custom models:', e);
        customModels = {};
    }
}

window.pageChangeCallbacks.push((pageName) => {
    if (pageName === 'settings') {
        loadAIProxies().then(() => loadAIProviders());
        if (typeof loadSettings === 'function') {
            loadSettings();
        }
    }
});
