/**
 * 报告中心功能模块
 */


let currentReports = [];
let currentPage = 0;
const reportsPerPage = 12;

async function loadReports(offset = 0) {
    try {
        const response = await fetch(`/api/reports/list?limit=${reportsPerPage}&offset=${offset}`);
        const result = await response.json();

        if (result.success) {
            currentReports = result.data.reports;
            currentPage = Math.floor(offset / reportsPerPage);
            renderReportsList(result.data);
        } else {
            showNotification('加载报告列表失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error loading reports:', error);
        showNotification('加载报告列表时发生错误', 'error');
    }
}

function renderReportsList(data) {
    const container = document.getElementById('reports-grid');
    if (!container) return;

    if (data.reports.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 48px;">
                <i data-lucide="file-text" style="width: 64px; height: 64px; color: var(--text-tertiary); margin-bottom: 16px;"></i>
                <p class="text-secondary">暂无报告</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    container.innerHTML = data.reports.map(report => `
        <div class="card report-card" data-report-id="${report.id}">
            <div class="card-header">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="file-text" style="width: 20px; height: 20px; color: var(--accent-blue);"></i>
                    <h4 class="card-title" style="font-size: 1rem; margin: 0;">${report.type === 'analysis' ? 'AI分析报告' : '调试数据'}</h4>
                </div>
            </div>
            <div class="card-body">
                <div style="margin-bottom: 12px;">
                    <div style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 4px;">
                        <i data-lucide="clock" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle;"></i>
                        ${formatDate(report.created_at)}
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 4px;">
                        <i data-lucide="link" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle;"></i>
                        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; max-width: 200px; vertical-align: middle;" title="${report.target_url || '未指定目标URL'}">${report.target_url || '未指定目标URL'}</span>
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-tertiary);">
                        大小: ${formatFileSize(report.size)}
                    </div>
                </div>
                <div style="background: var(--bg-hover); padding: 12px; border-radius: 8px; margin-bottom: 12px; max-height: 80px; overflow: hidden;">
                    <p style="font-size: 0.8125rem; color: var(--text-secondary); margin: 0; line-height: 1.4;">
                        ${report.preview.substring(0, 100)}...
                    </p>
                </div>
            </div>
            <div class="card-footer" style="justify-content: space-between;">
                <button class="btn btn-secondary" onclick="viewReport('${report.id}')" style="font-size: 0.875rem; padding: 8px 16px; white-space: nowrap;">
                    <i data-lucide="eye"></i>
                    查看
                </button>
                <button class="btn" onclick="viewReportDebug('${report.id}')" style="font-size: 0.875rem; padding: 8px 16px; white-space: nowrap;">
                    <i data-lucide=\"play-circle\"></i>
                    查看调试会话
                </button>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-icon" onclick="downloadReport('${report.id}')" title="下载" style="width: 36px; height: 36px;">
                        <i data-lucide="download"></i>
                    </button>
                    <button class="btn btn-icon" onclick="deleteReport('${report.id}')" title="删除" style="width: 36px; height: 36px; background: var(--accent-danger); color: white;">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    updatePagination(data);

    lucide.createIcons();
}

async function viewReportDebug(reportId) {
    try {
        const resp = await fetch(`/api/reports/${reportId}`);
        const result = await resp.json();
        if (!result.success) {
            showNotification('获取报告失败：' + result.error, 'error');
            return;
        }
        const report = result.data || {};
        try {
            const url = report.target_url || '';
            let host = '';
            try { host = new URL(url).host; } catch (e) { host = url; }
            const created_at = (report.created_at || '').slice(0,19);
            window.debugViewHint = { host, created_at };
        } catch (e) {}
        if (typeof showPage === 'function') {
            showPage('debug');
        }
    } catch (e) {
        console.error('viewReportDebug error:', e);
    }
}

function updatePagination(data) {
    const paginationContainer = document.getElementById('reports-pagination');
    if (!paginationContainer) return;

    const totalPages = Math.ceil(data.total / reportsPerPage);

    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }

    let paginationHTML = `
        <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 24px;">
            <button class="btn btn-secondary" onclick="loadReports(${Math.max(0, (currentPage - 1) * reportsPerPage)})" ${currentPage === 0 ? 'disabled' : ''}>
                <i data-lucide="chevron-left"></i>
                上一页
            </button>
            <span style="color: var(--text-secondary);">
                第 ${currentPage + 1} / ${totalPages} 页
            </span>
            <button class="btn btn-secondary" onclick="loadReports(${(currentPage + 1) * reportsPerPage})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>
                下一页
                <i data-lucide="chevron-right"></i>
            </button>
        </div>
    `;

    paginationContainer.innerHTML = paginationHTML;
    lucide.createIcons();
}

async function viewReport(reportId) {
    try {
        const response = await fetch(`/api/reports/${reportId}`);
        const result = await response.json();

        if (result.success) {
            showReportModal(result.data);
        } else {
            showNotification('加载报告失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error viewing report:', error);
        showNotification('查看报告时发生错误', 'error');
    }
}

async function downloadReport(reportId) {
    try {
        window.open(`/api/reports/${reportId}/download`, '_blank');
        showNotification('报告下载已开始', 'success');
    } catch (error) {
        console.error('Error downloading report:', error);
        showNotification('下载报告时发生错误', 'error');
    }
}

async function deleteReport(reportId) {
    if (!confirm('确定要删除这个报告吗？此操作不可恢复。')) {
        return;
    }

    try {
        const response = await fetch(`/api/reports/${reportId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('报告已删除', 'success');
            loadReports(currentPage * reportsPerPage);
        } else {
            showNotification('删除报告失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error deleting report:', error);
        showNotification('删除报告时发生错误', 'error');
    }
}

function showReportModal(report) {
    const modal = document.createElement('div');
    modal.id = 'report-modal';
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

    let renderedContent;
    const markedParser = window.markedLib || window.marked;
    if (typeof markedParser !== 'undefined') {
        try {
            markedParser.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
            renderedContent = markedParser.parse(report.content);
        } catch (e) {
            console.error('Markdown parsing error:', e);
            renderedContent = `<pre style="white-space: pre-wrap; overflow-x: auto;">${escapeHtml(report.content)}</pre>`;
        }
    } else {
        console.warn('Marked library not found, displaying raw content');
        renderedContent = `<pre style="white-space: pre-wrap; overflow-x: auto;">${escapeHtml(report.content)}</pre>`;
    }

    modal.innerHTML = `
        <div style="background: var(--bg-secondary); border-radius: 16px; max-width: 900px; width: 100%; max-height: 90vh; overflow: hidden; box-shadow: var(--shadow-xl); display: flex; flex-direction: column;">
            <div style="padding: 24px; border-bottom: 1px solid var(--divider-color); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;">
                <h2 style="margin: 0;">${report.type === 'analysis' ? 'AI 分析报告' : '调试数据'}</h2>
                <button class="btn btn-icon" onclick="closeReportModal()" style="width: 40px; height: 40px;">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div style="padding: 24px; overflow-y: auto; flex: 1; min-height: 0;">
                <div style="margin-bottom: 16px; padding: 16px; background: var(--bg-hover); border-radius: 12px;">
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 0.875rem;">
                        <div>
                            <strong>创建时间:</strong> ${formatDate(report.created_at)}
                        </div>
                        <div>
                            <strong>文件大小:</strong> ${formatFileSize(report.size)}
                        </div>
                        <div style="grid-column: 1 / -1;">
                            <strong>目标 URL:</strong> ${report.target_url || '未指定目标URL'}
                        </div>
                    </div>
                </div>
                <div class="markdown-content" style="background: var(--bg-primary); padding: 24px; border-radius: 12px; font-size: 0.875rem; line-height: 1.6; overflow-x: auto;">
                    <style>
                        .markdown-content h1 { font-size: 1.75rem; margin: 1.5rem 0 1rem 0; font-weight: 600; color: var(--text-primary); }
                        .markdown-content h2 { font-size: 1.5rem; margin: 1.25rem 0 0.75rem 0; font-weight: 600; color: var(--text-primary); }
                        .markdown-content h3 { font-size: 1.25rem; margin: 1rem 0 0.5rem 0; font-weight: 600; color: var(--text-primary); }
                        .markdown-content h4 { font-size: 1.1rem; margin: 0.875rem 0 0.5rem 0; font-weight: 600; color: var(--text-primary); }
                        .markdown-content p { margin: 0.5rem 0; color: var(--text-secondary); }
                        .markdown-content ul, .markdown-content ol { margin: 0.5rem 0 0.5rem 1.5rem; color: var(--text-secondary); }
                        .markdown-content li { margin: 0.25rem 0; }
                        .markdown-content code { background: var(--bg-hover); padding: 2px 6px; border-radius: 4px; font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace; font-size: 0.85em; color: var(--accent-blue); }
                        .markdown-content pre { background: var(--bg-secondary); padding: 16px; border-radius: 8px; overflow-x: auto; margin: 1rem 0; }
                        .markdown-content pre code { background: transparent; padding: 0; color: var(--text-primary); }
                        .markdown-content blockquote { border-left: 4px solid var(--accent-blue); padding-left: 16px; margin: 1rem 0; color: var(--text-secondary); }
                        .markdown-content table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
                        .markdown-content th, .markdown-content td { padding: 8px 12px; border: 1px solid var(--border-color); text-align: left; }
                        .markdown-content th { background: var(--bg-hover); font-weight: 600; color: var(--text-primary); }
                        .markdown-content a { color: var(--accent-blue); text-decoration: none; }
                        .markdown-content a:hover { text-decoration: underline; }
                        .markdown-content hr { border: none; border-top: 1px solid var(--divider-color); margin: 1.5rem 0; }
                        .markdown-content strong { font-weight: 600; color: var(--text-primary); }
                        .markdown-content em { font-style: italic; }
                    </style>
${renderedContent}
                </div>
            </div>
            <div style="padding: 16px 24px; border-top: 1px solid var(--divider-color); display: flex; justify-content: flex-end; gap: 12px; flex-shrink: 0;">
                <button class="btn btn-secondary" onclick="closeReportModal()">关闭</button>
                <button class="btn btn-primary" onclick="downloadReport('${report.id}')">
                    <i data-lucide="download"></i>
                    下载报告
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    lucide.createIcons();

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeReportModal();
        }
    });
}

function closeReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.remove();
    }
}

async function searchReports() {
    const query = document.getElementById('report-search-input').value.trim();

    if (!query) {
        loadReports(0);
        return;
    }

    try {
        const response = await fetch(`/api/reports/search?q=${encodeURIComponent(query)}`);
        const result = await response.json();

        if (result.success) {
            currentReports = result.data.reports;
            renderReportsList({
                reports: result.data.reports,
                total: result.data.total,
                limit: reportsPerPage,
                offset: 0
            });
        } else {
            showNotification('搜索失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error searching reports:', error);
        showNotification('搜索时发生错误', 'error');
    }
}


function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

if (typeof window.pageChangeCallbacks === 'undefined') {
    window.pageChangeCallbacks = [];
}

window.pageChangeCallbacks.push((pageName) => {
    if (pageName === 'reports') {
        loadReports(0);
    }
});
