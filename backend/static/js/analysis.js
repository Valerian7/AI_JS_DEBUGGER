/**
 * AI 分析功能模块
 * 实现流式显示和 Markdown 渲染
 */


let currentAnalysisSession = null;
let analysisContent = '';
let isAnalyzing = false;
let streamBuffer = '';
let typingInterval = null;


async function startAIAnalysis(debugContext) {
    if (isAnalyzing) {
        showNotification('已有分析正在进行中', 'warning');
        return;
    }

    if (!AppState.currentSession) {
        showNotification('请先创建调试会话', 'warning');
        return;
    }

    isAnalyzing = true;
    analysisContent = '';
    streamBuffer = '';

    const progressIndicator = document.getElementById('analysis-progress');
    if (progressIndicator) {
        progressIndicator.style.display = 'block';
    }

    updateAnalysisStatus('分析中...');

    enableAnalysisControls(true, false);

    const contentEl = document.getElementById('analysis-content');
    if (contentEl) {
        contentEl.innerHTML = '';
    }

    const cursor = document.getElementById('typing-cursor');
    if (cursor) {
        cursor.style.display = 'inline';
    }

    try {
        const response = await fetch(`/debug/session/${AppState.currentSession}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                context: debugContext
            })
        });

        if (!response.ok) {
            throw new Error('分析请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            streamBuffer += chunk;

            const lines = streamBuffer.split('\n');
            streamBuffer = lines.pop() || ''; // 保留不完整的行

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);

                    if (data === '[DONE]') {
                        finishAnalysis();
                        return;
                    }

                    try {
                        const jsonData = JSON.parse(data);

                        if (jsonData.content) {
                            appendAnalysisContent(jsonData.content);
                        }

                        if (jsonData.error) {
                            throw new Error(jsonData.error);
                        }
                    } catch (e) {
                        console.error('Error parsing stream data:', e);
                    }
                }
            }
        }

        finishAnalysis();
    } catch (error) {
        console.error('AI analysis error:', error);
        showNotification('AI 分析失败：' + error.message, 'error');
        stopAnalysis();
    }
}

function appendAnalysisContent(text) {
    analysisContent += text;

    displayWithTypewriterEffect(text);
}

function displayWithTypewriterEffect(newText) {
    const contentEl = document.getElementById('analysis-content');
    if (!contentEl) return;

    if (typeof marked !== 'undefined') {
        contentEl.innerHTML = marked.parse(analysisContent);
    } else {
        contentEl.textContent = analysisContent;
    }

    const cardBody = contentEl.closest('.card-body');
    if (cardBody) {
        cardBody.scrollTop = cardBody.scrollHeight;
    }
}

function finishAnalysis() {
    isAnalyzing = false;

    const progressIndicator = document.getElementById('analysis-progress');
    if (progressIndicator) {
        progressIndicator.style.display = 'none';
    }

    const cursor = document.getElementById('typing-cursor');
    if (cursor) {
        cursor.style.display = 'none';
    }

    updateAnalysisStatus('完成');

    enableAnalysisControls(false, true);

    const contentEl = document.getElementById('analysis-content');
    if (contentEl && typeof marked !== 'undefined') {
        contentEl.innerHTML = marked.parse(analysisContent);
    }

    showNotification('AI 分析完成', 'success');
}

function stopAnalysis() {
    if (!isAnalyzing) return;

    isAnalyzing = false;

    const progressIndicator = document.getElementById('analysis-progress');
    if (progressIndicator) {
        progressIndicator.style.display = 'none';
    }

    const cursor = document.getElementById('typing-cursor');
    if (cursor) {
        cursor.style.display = 'none';
    }

    updateAnalysisStatus('已停止');

    enableAnalysisControls(false, analysisContent.length > 0);

    showNotification('AI 分析已停止', 'info');
}

async function exportAnalysis() {
    if (!analysisContent) {
        showNotification('没有可导出的内容', 'warning');
        return;
    }

    try {
        const blob = new Blob([analysisContent], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `ai-analysis-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        URL.revokeObjectURL(url);

        showNotification('报告已导出', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showNotification('导出失败', 'error');
    }
}

function enableAnalysisControls(stopEnabled, exportEnabled) {
    const stopBtn = document.getElementById('analysis-stop-btn');
    if (stopBtn) {
        stopBtn.disabled = !stopEnabled;
    }

    const exportBtn = document.getElementById('analysis-export-btn');
    if (exportBtn) {
        exportBtn.disabled = !exportEnabled;
    }
}

function updateAnalysisStatus(status) {
    const statusEl = document.getElementById('analysis-status');
    if (statusEl) {
        statusEl.textContent = status;
    }
}


if (typeof window.pageChangeCallbacks === 'undefined') {
    window.pageChangeCallbacks = [];
}

window.pageChangeCallbacks.push((pageName) => {
    if (pageName === 'analysis') {
        if (AppState.currentSession && !isAnalyzing && !analysisContent) {
        }

        lucide.createIcons();
    }
});


document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (AppState.socket) {
            AppState.socket.on('debug_paused', (data) => {
                if (data) {
                    window.lastDebugContext = data;
                }
            });

            AppState.socket.on('ai_analysis_start', () => {
                if (!isAnalyzing) {
                    startAIAnalysis(window.lastDebugContext);
                }
            });

            AppState.socket.on('ai_analysis_chunk', (data) => {
                if (data.content) {
                    appendAnalysisContent(data.content);
                }
            });

            AppState.socket.on('ai_analysis_complete', () => {
                finishAnalysis();
            });

            AppState.socket.on('ai_analysis_error', (data) => {
                showNotification('AI 分析错误：' + data.error, 'error');
                stopAnalysis();
            });
        }
    }, 1000);
});


const analysisStyles = document.createElement('style');
analysisStyles.textContent = `
    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0; }
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    .spin-icon {
        animation: spin 1s linear infinite;
    }

    #analysis-content {
        font-size: 0.9375rem;
        line-height: 1.7;
    }

    #analysis-content h1:first-child,
    #analysis-content h2:first-child,
    #analysis-content h3:first-child {
        margin-top: 0;
    }

    #analysis-content code {
        background: var(--bg-hover);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: var(--font-mono);
        font-size: 0.875em;
    }

    #analysis-content pre {
        background: var(--bg-hover);
        padding: 16px;
        border-radius: 8px;
        overflow-x: auto;
        margin: 16px 0;
    }

    #analysis-content pre code {
        background: transparent;
        padding: 0;
    }

    #analysis-content ul,
    #analysis-content ol {
        padding-left: 24px;
    }

    #analysis-content li {
        margin: 8px 0;
    }

    #analysis-content blockquote {
        border-left: 4px solid var(--accent-blue);
        padding-left: 16px;
        margin: 16px 0;
        color: var(--text-secondary);
        font-style: italic;
    }

    #analysis-content table {
        border-collapse: collapse;
        width: 100%;
        margin: 16px 0;
    }

    #analysis-content table th,
    #analysis-content table td {
        border: 1px solid var(--divider-color);
        padding: 8px 12px;
        text-align: left;
    }

    #analysis-content table th {
        background: var(--bg-hover);
        font-weight: 600;
    }

    #analysis-content a {
        color: var(--accent-blue);
        text-decoration: none;
    }

    #analysis-content a:hover {
        text-decoration: underline;
    }

    #analysis-content img {
        max-width: 100%;
        height: auto;
        border-radius: 8px;
        margin: 12px 0;
    }
`;
document.head.appendChild(analysisStyles);

console.log('Analysis module loaded');
