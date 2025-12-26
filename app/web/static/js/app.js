/**
 * FeatherFlow 前端应用逻辑
 */

// 状态管理
let currentTaskId = null;
let pollInterval = null;
const POLL_INTERVAL_MS = 2000; // 2秒轮询

// DOM 元素
const elements = {
    crawlForm: document.getElementById('crawlForm'),
    keywordsInput: document.getElementById('keywords'),
    submitBtn: document.getElementById('submitBtn'),
    submitBtnText: document.querySelector('#submitBtn .btn-text'),
    taskStatus: document.getElementById('taskStatus'),
    statusBadge: document.getElementById('statusBadge'),
    taskId: document.getElementById('taskId'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    currentKeyword: document.getElementById('currentKeyword'),
    logContainer: document.getElementById('logContainer'),
    clearLogsBtn: document.getElementById('clearLogsBtn'),
    tasksTableBody: document.querySelector('#tasksTable tbody'),
    quickBtns: document.querySelectorAll('.quick-btn')
};

// 初始化
function init() {
    // 绑定事件
    elements.crawlForm.addEventListener('submit', handleSubmit);
    elements.clearLogsBtn.addEventListener('click', clearLogs);

    // 快捷关键词按钮
    elements.quickBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const keywords = btn.dataset.keywords;
            elements.keywordsInput.value = keywords;
        });
    });

    // 加载最近任务列表
    loadRecentTasks();
}

// 处理表单提交
async function handleSubmit(e) {
    e.preventDefault();

    const keywords = elements.keywordsInput.value.trim();
    if (!keywords) {
        addLog('请输入关键词', 'error');
        return;
    }

    // 获取选中的爬取模式
    const crawlModeInput = document.querySelector('input[name="crawlMode"]:checked');
    const forceRestart = crawlModeInput && crawlModeInput.value === 'restart';

    // 禁用提交按钮
    setSubmitDisabled(true);

    try {
        // 创建任务
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keywords,
                force_restart: forceRestart
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '创建任务失败');
        }

        // 保存任务 ID
        currentTaskId = data.task_id;

        // 显示状态面板
        showTaskStatus();
        updateTaskInfo(data);

        addLog(`任务已创建：${data.task_id}`, 'info');
        addLog(`共 ${data.total_keywords} 个关键词等待处理`, 'info');

        // 开始轮询
        startPolling();

        // 清空输入框
        elements.keywordsInput.value = '';

    } catch (error) {
        addLog(`错误：${error.message}`, 'error');
        setSubmitDisabled(false);
    }
}

// 开始轮询任务状态
function startPolling() {
    // 清除旧的轮询
    if (pollInterval) {
        clearInterval(pollInterval);
    }

    // 立即查询一次
    pollTaskStatus();

    // 定时轮询
    pollInterval = setInterval(pollTaskStatus, POLL_INTERVAL_MS);
}

// 停止轮询
function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// 轮询任务状态
async function pollTaskStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/tasks/${currentTaskId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '获取任务状态失败');
        }

        // 更新 UI
        updateTaskUI(data);

        // 检查任务是否完成
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            stopPolling();
            setSubmitDisabled(false);

            // 重新加载任务列表
            setTimeout(loadRecentTasks, 1000);
        }

    } catch (error) {
        console.error('轮询任务状态失败:', error);
    }
}

// 更新任务 UI
function updateTaskUI(task) {
    // 更新状态徽章
    elements.statusBadge.textContent = getStatusText(task.status);
    elements.statusBadge.className = `status-badge ${task.status}`;

    // 更新任务 ID
    elements.taskId.textContent = `任务ID: ${task.task_id}`;

    // 更新进度条
    const progress = task.total_keywords > 0
        ? (task.keyword_index / task.total_keywords) * 100
        : 0;
    elements.progressFill.style.width = `${progress}%`;
    elements.progressText.textContent = `${task.keyword_index}/${task.total_keywords}`;

    // 更新当前关键词
    if (task.current_keyword) {
        elements.currentKeyword.textContent = `正在处理：${task.current_keyword}`;
    } else if (task.status === 'completed') {
        elements.currentKeyword.textContent = '所有关键词已处理完成';
    } else if (task.status === 'failed') {
        elements.currentKeyword.textContent = `任务失败：${task.error || '未知错误'}`;
    } else if (task.status === 'cancelled') {
        elements.currentKeyword.textContent = '任务已取消';
    } else {
        elements.currentKeyword.textContent = '';
    }

    // 更新日志
    if (task.logs && task.logs.length > 0) {
        const currentLogs = Array.from(elements.logContainer.querySelectorAll('.log-entry'))
            .map(el => el.textContent);

        // 只添加新日志
        const newLogs = task.logs.filter(log => !currentLogs.includes(log));
        newLogs.forEach(log => {
            const logType = getLogType(log);
            addLog(log, logType, false);
        });
    }
}

// 获取状态文本
function getStatusText(status) {
    const statusMap = {
        'pending': '准备中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败',
        'cancelled': '已取消'
    };
    return statusMap[status] || status;
}

// 获取日志类型
function getLogType(log) {
    if (log.includes('失败') || log.includes('错误') || log.includes('拦截')) {
        return 'error';
    } else if (log.includes('完成') || log.includes('成功')) {
        return 'success';
    } else if (log.includes('警告') || log.includes('退避')) {
        return 'warning';
    }
    return 'info';
}

// 添加日志
function addLog(message, type = 'info', scroll = true) {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;

    // 添加时间戳
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    logEntry.textContent = `[${timestamp}] ${message}`;

    elements.logContainer.appendChild(logEntry);

    // 自动滚动到底部
    if (scroll) {
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    }

    // 限制日志数量
    const maxLogs = 100;
    while (elements.logContainer.children.length > maxLogs) {
        elements.logContainer.removeChild(elements.logContainer.firstChild);
    }
}

// 清空日志
function clearLogs() {
    elements.logContainer.innerHTML = '<div class="log-entry log-info">日志已清空</div>';
}

// 显示任务状态面板
function showTaskStatus() {
    elements.taskStatus.style.display = 'block';
}

// 隐藏任务状态面板
function hideTaskStatus() {
    elements.taskStatus.style.display = 'none';
}

// 设置提交按钮状态
function setSubmitDisabled(disabled) {
    elements.submitBtn.disabled = disabled;
    if (disabled) {
        elements.submitBtnText.innerHTML = '<span class="loading"></span>执行中...';
    } else {
        elements.submitBtnText.textContent = '开始爬取';
    }
}

// 更新任务初始信息
function updateTaskInfo(data) {
    elements.statusBadge.textContent = '准备中';
    elements.statusBadge.className = 'status-badge pending';
    elements.taskId.textContent = `任务ID: ${data.task_id}`;
    elements.progressFill.style.width = '0%';
    elements.progressText.textContent = `0/${data.total_keywords}`;
    elements.currentKeyword.textContent = '';
}

// 加载最近任务列表
async function loadRecentTasks() {
    try {
        const response = await fetch('/api/tasks?limit=10');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '加载任务列表失败');
        }

        renderTasksTable(data);

    } catch (error) {
        console.error('加载任务列表失败:', error);
    }
}

// 渲染任务表格
function renderTasksTable(tasks) {
    const tbody = elements.tasksTableBody;

    if (!tasks || tasks.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="5">暂无任务记录</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = tasks.map(task => `
        <tr>
            <td class="task-id-cell">${task.task_id.substring(0, 8)}...</td>
            <td>${task.keywords.join(', ')}</td>
            <td><span class="task-status-text ${task.status}">${getStatusText(task.status)}</span></td>
            <td>${task.keyword_index}/${task.total_keywords}</td>
            <td>${formatDateTime(task.created_at)}</td>
        </tr>
    `).join('');
}

// 格式化日期时间
function formatDateTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    // 小于 1 分钟
    if (diff < 60000) {
        return '刚刚';
    }

    // 小于 1 小时
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} 分钟前`;
    }

    // 小于 1 天
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} 小时前`;
    }

    // 显示日期
    return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
