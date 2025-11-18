/**
 * 提示词配置模块
 */

async function loadPrompts() {
    try {
        const resp = await fetch('/api/config/prompts');
        const result = await resp.json();
        if (!result.success) {
            showNotification('加载提示词失败：' + result.error, 'error');
            return;
        }
        const data = result.data || {};
        const dbg = document.getElementById('prompt-debug');
        const anl = document.getElementById('prompt-analysis');
        if (dbg) dbg.value = data.debug || '';
        if (anl) anl.value = data.analysis || '';
    } catch (e) {
        console.error('loadPrompts error:', e);
        showNotification('加载提示词时发生错误', 'error');
    }
}

async function savePrompts() {
    try {
        const dbg = document.getElementById('prompt-debug')?.value || '';
        const anl = document.getElementById('prompt-analysis')?.value || '';
        const resp = await fetch('/api/config/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ debug: dbg, analysis: anl })
        });
        const result = await resp.json();
        if (result.success) {
            showNotification('提示词已保存', 'success');
        } else {
            showNotification('保存失败：' + result.error, 'error');
        }
    } catch (e) {
        console.error('savePrompts error:', e);
        showNotification('保存提示词时发生错误', 'error');
    }
}

// 页面切换钩子
if (typeof window.pageChangeCallbacks === 'undefined') { window.pageChangeCallbacks = []; }
window.pageChangeCallbacks.push((pageName) => {
    if (pageName === 'prompts') {
        loadPrompts();
    }
});

console.log('Prompts module loaded');

