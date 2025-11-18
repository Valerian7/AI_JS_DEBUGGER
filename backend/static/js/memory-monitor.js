/**
 * Memory Monitor Module
 * 内存监控和管理功能
 */


let memoryUpdateInterval = null;

/**
 * 初始化内存监控
 */
function initMemoryMonitor() {
    updateMemoryStatus();

    memoryUpdateInterval = setInterval(updateMemoryStatus, 5000);
}

/**
 * 更新内存状态显示
 */
async function updateMemoryStatus() {
    try {
        const response = await fetch('/system/memory');
        const result = await response.json();

        if (result.success) {
            const data = result.data;
            const percent = data.system.percent;

            const percentElement = document.getElementById('memory-percent');
            if (percentElement) {
                percentElement.textContent = `${percent.toFixed(1)}%`;
            }

            const barElement = document.getElementById('memory-bar');
            if (barElement) {
                barElement.style.width = `${percent}%`;

                if (percent > 85) {
                    barElement.style.backgroundColor = 'var(--accent-danger)';
                    percentElement.style.color = 'var(--accent-danger)';
                } else if (percent > 70) {
                    barElement.style.backgroundColor = 'var(--accent-warning)';
                    percentElement.style.color = 'var(--accent-warning)';
                } else {
                    barElement.style.backgroundColor = 'var(--accent-success)';
                    percentElement.style.color = 'var(--text-primary)';
                }
            }

            if (percent > 85 && !document.getElementById('memory-warning')) {
                showMemoryWarning();
            }
        }
    } catch (error) {
        console.error('Failed to update memory status:', error);
    }
}

/**
 * 清理内存
 */
async function clearMemory() {
    const button = event.currentTarget;

    button.disabled = true;
    const originalContent = button.innerHTML;
    button.innerHTML = '<i data-lucide="loader" style="width: 14px; height: 14px; animation: spin 1s linear infinite;"></i> 清理中...';

    try {
        const response = await fetch('/system/memory/clear', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            showNotification(`内存清理完成，回收了 ${result.data.objects_collected} 个对象`, 'success');

            updateMemoryStatus();
        } else {
            showNotification('内存清理失败：' + result.error, 'error');
        }
    } catch (error) {
        console.error('Failed to clear memory:', error);
        showNotification('内存清理时发生错误', 'error');
    } finally {
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalContent;
            lucide.createIcons();
        }, 1000);
    }
}

/**
 * 显示内存警告
 */
function showMemoryWarning() {
    const warning = document.createElement('div');
    warning.id = 'memory-warning';
    warning.style.cssText = `
        position: fixed;
        top: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--accent-danger);
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: var(--shadow-lg);
        z-index: 10001;
        display: flex;
        align-items: center;
        gap: 12px;
    `;

    warning.innerHTML = `
        <i data-lucide="alert-triangle" style="width: 20px; height: 20px;"></i>
        <span>内存使用率过高，建议清理内存以避免性能问题</span>
        <button onclick="clearMemory(); this.parentElement.remove();" style="
            background: white;
            color: var(--accent-danger);
            border: none;
            padding: 4px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
        ">立即清理</button>
        <button onclick="this.parentElement.remove();" style="
            background: transparent;
            color: white;
            border: 1px solid white;
            padding: 4px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        ">忽略</button>
    `;

    document.body.appendChild(warning);
    lucide.createIcons();

    setTimeout(() => {
        if (document.getElementById('memory-warning')) {
            warning.remove();
        }
    }, 10000);
}

/**
 * 停止内存监控
 */
function stopMemoryMonitor() {
    if (memoryUpdateInterval) {
        clearInterval(memoryUpdateInterval);
        memoryUpdateInterval = null;
    }
}

if (!document.getElementById('memory-monitor-styles')) {
    const style = document.createElement('style');
    style.id = 'memory-monitor-styles';
    style.textContent = `
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .btn-sm {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            transition: all 0.2s;
        }

        .btn-sm:hover:not(:disabled) {
            background: var(--bg-hover);
            transform: translateY(-1px);
        }

        .btn-sm:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
    `;
    document.head.appendChild(style);
}

document.addEventListener('DOMContentLoaded', () => {
    initMemoryMonitor();
});

window.addEventListener('beforeunload', () => {
    stopMemoryMonitor();
});