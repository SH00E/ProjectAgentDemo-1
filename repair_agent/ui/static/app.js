/**
 * 保障智能助手 - 前端逻辑
 * 使用 SSE (Server-Sent Events) 实现流式输出
 */

// ==================== 全局状态 ====================

const state = {
    isDiagnosing: false,
    currentSource: null,
    analysisText: '',
    solutionText: '',
    searchHistory: []
};

// ==================== DOM 元素 ====================

const elements = {
    // 状态栏
    statusBar: document.getElementById('status-bar'),

    // 诊断
    faultDesc: document.getElementById('fault-desc'),
    faultImage: document.getElementById('fault-image'),
    imagePreview: document.getElementById('image-preview'),
    previewImg: document.getElementById('preview-img'),
    removeImage: document.getElementById('remove-image'),
    btnDiagnose: document.getElementById('btn-diagnose'),
    cotArea: document.getElementById('cot-area'),
    orderArea: document.getElementById('order-area'),

    // 检索
    searchQuery: document.getElementById('search-query'),
    btnSearch: document.getElementById('btn-search'),
    searchResults: document.getElementById('search-results'),
    searchHistoryList: document.getElementById('search-history-list'),

    // 案例
    caseTitle: document.getElementById('case-title'),
    caseText: document.getElementById('case-text'),
    btnAddCase: document.getElementById('btn-add-case'),
    caseResult: document.getElementById('case-result'),
    caseList: document.getElementById('case-list'),

    // 统计
    btnRefreshStats: document.getElementById('btn-refresh-stats'),
    statKbCount: document.getElementById('stat-kb-count'),
    statMemoryCount: document.getElementById('stat-memory-count'),
    statDiagnosisCount: document.getElementById('stat-diagnosis-count'),
    statRunStatus: document.getElementById('stat-run-status'),
    statSessionId: document.getElementById('stat-session-id'),
    componentsList: document.getElementById('components-list'),
    statsRag: document.getElementById('stats-rag'),
    statsMemory: document.getElementById('stats-memory')
};

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initDiagnosis();
    initSearch();
    initCase();
    initStats();
    checkStatus();
    loadSearchHistory();
});

// ==================== 标签页切换 ====================

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;

            // 更新标签按钮状态
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // 更新内容显示
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`tab-${tabName}`).classList.add('active');

            // 切换到案例或统计时加载数据
            if (tabName === 'case') loadCases();
            if (tabName === 'stats') {
                refreshStats();
                // 自动加载可视化
                loadKnowledgeGraph();
                loadVectorSpace();
            }
        });
    });
}

// ==================== 状态检查 ====================

async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        elements.statusBar.textContent = data.message;

        if (data.status === 'ready') {
            elements.statusBar.className = 'status-bar status-ready';
            elements.btnDiagnose.disabled = false;
        } else if (data.status === 'error') {
            elements.statusBar.className = 'status-bar status-error';
        } else {
            elements.statusBar.className = 'status-bar status-loading';
            // 继续轮询
            setTimeout(checkStatus, 2000);
        }
    } catch (e) {
        elements.statusBar.textContent = '❌ 连接失败';
        elements.statusBar.className = 'status-bar status-error';
    }
}

// ==================== 故障诊断 ====================

function initDiagnosis() {
    // 图片预览
    elements.faultImage.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                elements.previewImg.src = e.target.result;
                elements.imagePreview.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }
    });

    // 移除图片
    elements.removeImage.addEventListener('click', () => {
        elements.faultImage.value = '';
        elements.imagePreview.classList.add('hidden');
        elements.previewImg.src = '';
    });

    // 诊断按钮
    elements.btnDiagnose.addEventListener('click', startDiagnosis);

    // 输入框变化时启用按钮
    elements.faultDesc.addEventListener('input', () => {
        elements.btnDiagnose.disabled = !elements.faultDesc.value.trim();
    });

    // Ctrl+Enter 快捷键
    elements.faultDesc.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            if (!elements.btnDiagnose.disabled) {
                startDiagnosis();
            }
        }
    });
}

async function startDiagnosis() {
    if (state.isDiagnosing) return;

    const description = elements.faultDesc.value.trim();
    if (!description) {
        alert('请输入故障描述');
        return;
    }

    state.isDiagnosing = true;
    state.analysisText = '';
    state.solutionText = '';

    // 更新 UI 状态
    elements.btnDiagnose.disabled = true;
    elements.btnDiagnose.textContent = '⏳ 诊断中...';
    elements.cotArea.innerHTML = '<div class="cot-step">⏳ 开始处理...</div>';
    elements.orderArea.classList.add('hidden');
    elements.orderArea.innerHTML = '';

    // 准备表单数据
    const formData = new FormData();
    formData.append('description', description);
    if (elements.faultImage.files[0]) {
        formData.append('image', elements.faultImage.files[0]);
    }

    try {
        const response = await fetch('/api/diagnose', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '请求失败');
        }

        // 使用 ReadableStream 处理 SSE
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // 处理完整的 SSE 事件
            const lines = buffer.split('\n');
            buffer = lines.pop(); // 保留不完整的行

            let eventType = '';
            let eventData = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.substring(7).trim();
                } else if (line.startsWith('data: ')) {
                    eventData = line.substring(6).trim();
                    if (eventType && eventData) {
                        handleSSEEvent(eventType, eventData);
                        eventType = '';
                        eventData = '';
                    }
                }
            }
        }
    } catch (error) {
        appendToCot(`<div class="cot-step" style="color: #dc2626;">❌ 错误: ${error.message}</div>`);
    } finally {
        state.isDiagnosing = false;
        elements.btnDiagnose.disabled = false;
        elements.btnDiagnose.textContent = '🚀 开始诊断';
    }
}

function handleSSEEvent(eventType, dataStr) {
    try {
        const data = JSON.parse(dataStr);

        switch (eventType) {
            case 'step':
                appendToCot(`<div class="cot-step">${escapeHtml(data.text)}</div>`);
                break;

            case 'rag':
                handleRAG(data);
                break;

            case 'analysis':
                handleAnalysis(data);
                break;

            case 'solution_text':
                handleSolutionText(data);
                break;

            case 'diagnosis':
                handleDiagnosis(data);
                break;

            case 'solution':
                handleSolution(data);
                break;

            case 'result':
                handleResult(data);
                break;

            case 'error':
                appendToCot(`<div class="cot-step" style="color: #dc2626;">❌ ${escapeHtml(data.message)}</div>`);
                break;
        }
    } catch (e) {
        console.error('解析 SSE 事件失败:', e, dataStr);
    }
}

function handleRAG(data) {
    if (data.results && data.results.length > 0) {
        let html = `<div class="cot-step-sub">📚 检索到 ${data.total} 条相关记录：</div>`;
        data.results.forEach((r, i) => {
            html += `<div class="cot-rag-item"><strong>${i + 1}.</strong> [${r.score.toFixed(2)}] ${escapeHtml(r.content)}...</div>`;
        });
        appendToCot(html);
    } else {
        appendToCot('<div class="cot-step-sub">📚 知识库暂无匹配记录</div>');
    }
}

function handleAnalysis(data) {
    state.analysisText += data.chunk;

    // 查找或创建分析区域
    let analysisDiv = document.getElementById('cot-analysis');
    if (!analysisDiv) {
        analysisDiv = document.createElement('div');
        analysisDiv.id = 'cot-analysis';
        analysisDiv.innerHTML = '<div class="cot-step">🧠 LLM 分析</div><div class="cot-text"></div>';
        elements.cotArea.appendChild(analysisDiv);
    }

    // 更新文本内容
    const textDiv = analysisDiv.querySelector('.cot-text');
    textDiv.textContent = state.analysisText;

    scrollToBottom();
}

function handleSolutionText(data) {
    state.solutionText += data.chunk;

    // 查找或创建方案区域
    let solutionDiv = document.getElementById('cot-solution');
    if (!solutionDiv) {
        solutionDiv = document.createElement('div');
        solutionDiv.id = 'cot-solution';
        solutionDiv.innerHTML = '<div class="cot-step">🔧 方案推理</div><div class="cot-text"></div>';
        elements.cotArea.appendChild(solutionDiv);
    }

    // 更新文本内容
    const textDiv = solutionDiv.querySelector('.cot-text');
    textDiv.textContent = state.solutionText;

    scrollToBottom();
}

function handleDiagnosis(data) {
    let html = '<div class="cot-step">📋 诊断结果</div>';
    html += `<div class="cot-text">故障类型: <strong>${escapeHtml(data.fault_type)}</strong></div>`;
    html += `<div class="cot-text">紧急程度: ${escapeHtml(data.urgency)}</div>`;
    html += `<div class="cot-text">损伤等级: ${escapeHtml(data.severity_level)} — ${escapeHtml(data.severity_desc)}</div>`;

    if (data.possible_causes && data.possible_causes.length > 0) {
        html += `<div class="cot-text">可能原因: ${data.possible_causes.map(c => escapeHtml(c)).join('、')}</div>`;
    }

    appendToCot(html);
}

function handleSolution(data) {
    let html = `<div class="cot-step">🔧 维修方案（${data.repair_steps.length} 步）</div>`;

    data.repair_steps.forEach(s => {
        html += `<div class="cot-text">${s.step}. ${escapeHtml(s.action)}</div>`;
    });

    if (data.estimated_time) {
        html += `<div class="cot-text" style="margin-top: 8px;">⏱️ 预计 ${escapeHtml(data.estimated_time)} | 难度: ${escapeHtml(data.difficulty)}</div>`;
    }

    appendToCot(html);
}

function handleResult(data) {
    if (data.success && data.work_order) {
        appendToCot('<div class="cot-step">✅ 诊断完成</div>');
        renderWorkOrder(data.work_order);
    }
}

function renderWorkOrder(wo) {
    const info = wo.order_info || {};
    const diag = wo.diagnosis || {};
    const sol = wo.solution || {};
    const sev = diag.severity || {};
    const steps = sol.repair_steps || [];
    const parts = sol.parts_required || [];
    const tools = sol.tools_required || [];
    const warnings = sol.safety_warnings || [];

    const stepsHtml = steps.length > 0
        ? steps.map(s => `${s.step}. ${escapeHtml(s.action)}`).join('<br>')
        : '无';

    const partsHtml = parts.length > 0
        ? parts.map(p => escapeHtml(p.name || '')).join(', ')
        : '无';

    const toolsHtml = tools.length > 0
        ? tools.map(t => escapeHtml(t)).join(', ')
        : '无';

    const warningsHtml = warnings.length > 0
        ? warnings.map(w => escapeHtml(w)).join(' | ')
        : '无';

    const html = `
        <h3>📋 维修工单</h3>
        <table>
            <tr><td>工单编号</td><td><strong>${escapeHtml(info.order_id || 'N/A')}</strong></td></tr>
            <tr><td>创建时间</td><td>${escapeHtml(String(info.created_at || 'N/A').substring(0, 19))}</td></tr>
            <tr><td>状态</td><td><strong>${escapeHtml(wo.status || '待处理')}</strong></td></tr>
            <tr><td>故障描述</td><td>${escapeHtml(wo.fault_description || '无')}</td></tr>
            <tr><td>故障类型</td><td>${escapeHtml(diag.fault_type || '未知')}</td></tr>
            <tr><td>损伤等级</td><td>${escapeHtml(sev.level || '待评估')} — ${escapeHtml(sev.description || '')}</td></tr>
            <tr><td>维修步骤</td><td>${stepsHtml}</td></tr>
            <tr><td>备件</td><td>${partsHtml}</td></tr>
            <tr><td>工具</td><td>${toolsHtml}</td></tr>
            <tr><td>安全警告</td><td>${warningsHtml}</td></tr>
            <tr><td>预计时间</td><td>${escapeHtml(sol.estimated_time || '待评估')}</td></tr>
            <tr><td>难度等级</td><td>${escapeHtml(sol.difficulty || '中等')}</td></tr>
        </table>
    `;

    elements.orderArea.innerHTML = html;
    elements.orderArea.classList.remove('hidden');
}

// ==================== 知识检索 ====================

function initSearch() {
    elements.btnSearch.addEventListener('click', searchKnowledge);
    elements.searchQuery.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchKnowledge();
        }
    });

    // 热门搜索标签
    document.querySelectorAll('.hot-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            elements.searchQuery.value = tag.dataset.query;
            searchKnowledge();
        });
    });
}

async function searchKnowledge() {
    const query = elements.searchQuery.value.trim();
    if (!query) {
        alert('请输入查询内容');
        return;
    }

    elements.btnSearch.disabled = true;
    elements.btnSearch.textContent = '🔍 检索中...';
    elements.searchResults.innerHTML = '<div class="loading-placeholder"><span class="loading-icon">⏳</span><p>正在检索...</p></div>';

    // 添加到搜索历史
    addToSearchHistory(query);

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (data.success && data.results && data.results.length > 0) {
            let html = '';
            data.results.forEach((r, i) => {
                const content = r.content || JSON.stringify(r);
                const score = r.score || 0;
                const keywords = r.keywords || [];
                const source = r.source || '知识库';

                // 高亮关键词
                let highlightedContent = escapeHtml(content.substring(0, 300));
                keywords.forEach(kw => {
                    if (kw) {
                        const regex = new RegExp(escapeRegex(kw), 'gi');
                        highlightedContent = highlightedContent.replace(regex, `<span class="keyword">${escapeHtml(kw)}</span>`);
                    }
                });

                // 相似度等级
                let scoreClass = 'score-low';
                if (score >= 0.8) scoreClass = 'score-high';
                else if (score >= 0.5) scoreClass = 'score-medium';

                html += `
                    <div class="search-result-item">
                        <div class="search-result-header">
                            <div class="search-result-title">📄 结果 ${i + 1}</div>
                            <div class="search-result-score">
                                <div class="score-bar">
                                    <div class="score-fill ${scoreClass}" style="width: ${score * 100}%"></div>
                                </div>
                                <span class="score-text">${(score * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                        <div class="search-result-content">${highlightedContent}${content.length > 300 ? '...' : ''}</div>
                        <div class="search-result-meta">
                            <span>📍 来源: ${escapeHtml(source)}</span>
                        </div>
                    </div>
                `;
            });
            elements.searchResults.innerHTML = html;
        } else {
            elements.searchResults.innerHTML = `
                <div class="search-placeholder">
                    <span class="search-icon">😕</span>
                    <p>未找到相关知识，请尝试其他关键词</p>
                </div>
            `;
        }
    } catch (e) {
        elements.searchResults.innerHTML = `<p style="color: #dc2626;">❌ 检索失败: ${e.message}</p>`;
    } finally {
        elements.btnSearch.disabled = false;
        elements.btnSearch.textContent = '🔍 检索';
    }
}

// 搜索历史管理
function addToSearchHistory(query) {
    // 去重
    state.searchHistory = state.searchHistory.filter(q => q !== query);
    state.searchHistory.unshift(query);
    // 最多保留10条
    if (state.searchHistory.length > 10) {
        state.searchHistory = state.searchHistory.slice(0, 10);
    }
    saveSearchHistory();
    renderSearchHistory();
}

function saveSearchHistory() {
    try {
        localStorage.setItem('searchHistory', JSON.stringify(state.searchHistory));
    } catch (e) {}
}

function loadSearchHistory() {
    try {
        const saved = localStorage.getItem('searchHistory');
        if (saved) {
            state.searchHistory = JSON.parse(saved);
        }
    } catch (e) {}
    renderSearchHistory();
}

function renderSearchHistory() {
    if (!elements.searchHistoryList) return;

    if (state.searchHistory.length === 0) {
        elements.searchHistoryList.innerHTML = '<p class="empty-hint">暂无检索记录</p>';
        return;
    }

    let html = '';
    state.searchHistory.forEach(query => {
        html += `<div class="history-item" onclick="document.getElementById('search-query').value='${escapeHtml(query)}'; searchKnowledge();">📋 ${escapeHtml(query)}</div>`;
    });
    elements.searchHistoryList.innerHTML = html;
}

// ==================== 案例管理 ====================

function initCase() {
    elements.btnAddCase.addEventListener('click', addCase);

    // 模板按钮
    document.querySelectorAll('.btn-template').forEach(btn => {
        btn.addEventListener('click', () => {
            // 移除其他按钮的active状态
            document.querySelectorAll('.btn-template').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const template = btn.dataset.template;
            applyTemplate(template);
        });
    });
}

function applyTemplate(type) {
    const templates = {
        device: {
            title: '电子设备维修案例',
            text: '设备类型：\n故障现象：\n故障原因：\n维修步骤：\n1. \n2. \n3. \n使用工具：\n更换备件：\n维修结果：'
        },
        appliance: {
            title: '家用电器维修案例',
            text: '电器类型：\n品牌型号：\n故障现象：\n故障原因：\n维修步骤：\n1. \n2. \n3. \n使用工具：\n更换备件：\n维修结果：'
        },
        vehicle: {
            title: '汽车维修案例',
            text: '车辆信息：\n故障现象：\n故障码：\n故障原因：\n维修步骤：\n1. \n2. \n3. \n使用工具：\n更换配件：\n维修结果：'
        },
        custom: {
            title: '',
            text: ''
        }
    };

    const template = templates[type];
    if (template) {
        elements.caseTitle.value = template.title;
        elements.caseText.value = template.text;
    }
}

async function addCase() {
    const caseText = elements.caseText.value.trim();
    if (!caseText) {
        alert('请输入案例内容');
        return;
    }

    elements.btnAddCase.disabled = true;
    elements.btnAddCase.textContent = '➕ 添加中...';
    elements.caseResult.textContent = '';
    elements.caseResult.className = 'result-message';

    try {
        const response = await fetch('/api/case', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_text: caseText })
        });

        const data = await response.json();

        if (data.success) {
            elements.caseResult.textContent = `✅ ${data.message}`;
            elements.caseResult.className = 'result-message success';
            elements.caseTitle.value = '';
            elements.caseText.value = '';
            // 刷新案例列表
            loadCases();
        } else {
            elements.caseResult.textContent = `❌ ${data.message}`;
            elements.caseResult.className = 'result-message error';
        }
    } catch (e) {
        elements.caseResult.textContent = `❌ 添加失败: ${e.message}`;
        elements.caseResult.className = 'result-message error';
    } finally {
        elements.btnAddCase.disabled = false;
        elements.btnAddCase.textContent = '➕ 添加案例';
    }
}

async function loadCases() {
    if (!elements.caseList) return;

    elements.caseList.innerHTML = '<div class="loading-placeholder"><span class="loading-icon">⏳</span><p>加载中...</p></div>';

    try {
        const response = await fetch('/api/cases');
        const data = await response.json();

        if (data.success && data.cases && data.cases.length > 0) {
            let html = '';
            data.cases.forEach((c, i) => {
                const content = c.content || c.description || JSON.stringify(c);
                const time = c.timestamp || c.created_at || '';
                const faultType = c.fault_type || '';

                html += `
                    <div class="case-item">
                        <div class="case-item-header">
                            <div class="case-item-title">📋 案例 ${i + 1}</div>
                            <div class="case-item-time">${time ? escapeHtml(String(time).substring(0, 10)) : ''}</div>
                        </div>
                        <div class="case-item-content">${escapeHtml(content.substring(0, 150))}${content.length > 150 ? '...' : ''}</div>
                        ${faultType ? `<div class="case-item-tags"><span class="case-tag">${escapeHtml(faultType)}</span></div>` : ''}
                    </div>
                `;
            });
            elements.caseList.innerHTML = html;
        } else {
            elements.caseList.innerHTML = `
                <div class="loading-placeholder">
                    <span class="loading-icon">📭</span>
                    <p>暂无案例记录</p>
                </div>
            `;
        }
    } catch (e) {
        elements.caseList.innerHTML = `<div class="loading-placeholder"><p style="color: #dc2626;">❌ 加载失败: ${e.message}</p></div>`;
    }
}

// ==================== 系统统计 ====================

function initStats() {
    elements.btnRefreshStats.addEventListener('click', refreshStats);
}

async function refreshStats() {
    elements.btnRefreshStats.disabled = true;
    elements.btnRefreshStats.textContent = '🔄 加载中...';

    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;

            // 更新状态卡片
            const kbStats = stats.knowledge_base?.rag_stats || {};
            const memStats = stats.knowledge_base?.memory_stats || {};

            // 尝试从不同字段获取数据
            elements.statKbCount.textContent = kbStats.total_documents || kbStats.count || '--';
            elements.statMemoryCount.textContent = memStats.total_memories || memStats.count || '--';

            // 会话信息
            elements.statSessionId.textContent = stats.system?.session_id || '--';

            // 组件状态
            const components = stats.components || [];
            let compHtml = '';
            components.forEach(comp => {
                compHtml += `
                    <div class="component-item">
                        <span class="component-icon">${comp.icon || '🔧'}</span>
                        <div class="component-info">
                            <div class="component-name">${escapeHtml(comp.name)}</div>
                            <div class="component-status">${comp.status === 'active' ? '运行中' : '未知'}</div>
                        </div>
                    </div>
                `;
            });
            elements.componentsList.innerHTML = compHtml;

            // 详细信息 - 格式化显示
            const ragText = kbStats.summary || kbStats.description || JSON.stringify(kbStats, null, 2);
            const memText = memStats.summary || memStats.description || JSON.stringify(memStats, null, 2);
            
            // 将换行符转换为HTML换行，并处理Markdown粗体
            elements.statsRag.innerHTML = formatStatsText(ragText);
            elements.statsMemory.innerHTML = formatStatsText(memText);
        } else {
            console.error('获取统计失败:', data.error);
        }
    } catch (e) {
        console.error('获取统计失败:', e);
    } finally {
        elements.btnRefreshStats.disabled = false;
        elements.btnRefreshStats.textContent = '🔄 刷新数据';
    }

    // 同时获取诊断历史
    try {
        const historyResponse = await fetch('/api/history');
        const historyData = await historyResponse.json();

        if (historyData.success) {
            elements.statDiagnosisCount.textContent = historyData.history?.length || 0;
        }
    } catch (e) {
        console.error('获取诊断历史失败:', e);
    }
}

// ==================== 可视化功能 ====================

// 切换可视化部分的展开/折叠
function toggleVizSection(section) {
    const content = document.getElementById(`viz-${section}`);
    const toggle = document.getElementById(`toggle-${section}`);
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.add('expanded');
        
        // 首次展开时加载数据
        if (section === 'knowledge-graph' && !content.dataset.loaded) {
            loadKnowledgeGraph();
            content.dataset.loaded = 'true';
        } else if (section === 'vector-space' && !content.dataset.loaded) {
            loadVectorSpace();
            content.dataset.loaded = 'true';
        }
    } else {
        content.style.display = 'none';
        toggle.classList.remove('expanded');
    }
}

// ==================== 知识图谱可视化 ====================

let kgSimulation = null;

async function loadKnowledgeGraph() {
    const container = document.getElementById('kg-container');
    const statsDiv = document.getElementById('kg-stats');
    
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载知识图谱...</p></div>';
    
    try {
        const response = await fetch('/api/stats/knowledge-graph');
        const result = await response.json();
        
        if (!result.success || !result.data.nodes.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无知识图谱数据</div></div>';
            return;
        }
        
        const { nodes, links, stats } = result.data;
        
        // 显示统计信息
        statsDiv.innerHTML = `
            <strong>📊 统计:</strong> 
            ${stats.aircraft} 飞机型号 | ${stats.incidents} 事故类型 | ${stats.manufacturers} 制造商 | 
            ${stats.total_links} 关系 | ${stats.total_nodes} 节点
        `;
        
        // 渲染图谱
        renderKnowledgeGraph(container, nodes, links);
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

function renderKnowledgeGraph(container, nodes, links) {
    // 清空容器
    container.innerHTML = '';
    
    const width = container.clientWidth || 900;
    const height = 500;
    
    // 颜色映射 (航空领域)
    const colorMap = {
        'Aircraft': '#f87171',     // 红色 - 飞机型号
        'Incident': '#fbbf24',     // 黄色 - 事故类型
        'Manufacturer': '#4ade80', // 绿色 - 制造商
    };
    
    // 创建SVG
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);
    
    // 添加缩放支持
    const g = svg.append('g');
    
    svg.call(d3.zoom()
        .extent([[0, 0], [width, height]])
        .scaleExtent([0.3, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        }));
    
    // 添加箭头定义
    svg.append('defs').selectAll('marker')
        .data(['end'])
        .join('marker')
        .attr('id', 'arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', '#94a3b8')
        .attr('d', 'M0,-5L10,0L0,5');
    
    // 创建力导向模拟
    kgSimulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(150))
        .force('charge', d3.forceManyBody().strength(-500))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(40));
    
    // 绘制边
    const link = g.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('class', 'link')
        .attr('stroke', '#cbd5e1')
        .attr('stroke-width', 1.5)
        .attr('marker-end', 'url(#arrow)');
    
    // 绘制节点组
    const node = g.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));
    
    // 节点圆形 - 统一大小
    node.append('circle')
        .attr('r', 20)
        .attr('fill', d => colorMap[d.type] || '#94a3b8')
        .attr('stroke', '#334155')
        .attr('stroke-width', 1.5);
    
    // 节点标签
    node.append('text')
        .attr('class', 'node-label')
        .attr('dy', 28)
        .text(d => d.label.length > 10 ? d.label.substring(0, 10) + '...' : d.label);
    
    // 节点提示
    node.append('title')
        .text(d => `${d.label}\n类型: ${d.type}`);
    
    // 更新模拟
    kgSimulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    // 拖拽函数 - 节点拖动后固定在松开位置
    function dragStarted(event, d) {
        if (!event.active) kgSimulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    function dragEnded(event, d) {
        if (!event.active) kgSimulation.alphaTarget(0);
        // 保留 fx/fy，让节点固定在松开的位置
        // 双击节点可释放（在节点上添加双击事件）
    }
    
    // 双击节点释放固定
    node.on('dblclick', (event, d) => {
        event.stopPropagation();
        d.fx = null;
        d.fy = null;
        kgSimulation.alphaTarget(0.1).restart();
        // 视觉反馈
        d3.select(event.currentTarget).select('circle')
            .attr('stroke', '#334155')
            .attr('stroke-width', 1.5);
    });
}

// ==================== 向量空间可视化 ====================

async function loadVectorSpace() {
    const container = document.getElementById('vs-container');
    const statsDiv = document.getElementById('vs-stats');
    
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载向量空间...</p></div>';
    
    try {
        const response = await fetch('/api/stats/vector-space');
        const result = await response.json();
        
        if (!result.success || !result.data.points.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无向量数据，请先运行 import_dataset.py</div></div>';
            return;
        }
        
        const { points, stats } = result.data;
        
        // 显示统计信息
        let statsHtml = `<strong>📊 统计:</strong> ${stats.total} 条向量, ${stats.categories} 个类别`;
        if (stats.collections && stats.collections.length > 0) {
            statsHtml += '<br><strong>Qdrant 集合:</strong> ';
            statsHtml += stats.collections.map(c => `${c.name}: ${c.points} points`).join(' | ');
        }
        statsDiv.innerHTML = statsHtml;
        
        // 渲染散点图
        renderVectorSpace(container, points, stats);
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

function renderVectorSpace(container, points, stats) {
    // 清空容器
    container.innerHTML = '';
    
    const width = container.clientWidth || 900;
    const height = 600;
    const margin = { top: 40, right: 200, bottom: 50, left: 70 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    
    // 颜色映射
    const uniqueLabels = stats.labels || [...new Set(points.map(p => p.label))];
    const colorScale = d3.scaleOrdinal()
        .domain(uniqueLabels)
        .range(d3.schemeTableau10.concat(d3.schemeSet3));
    
    // 创建SVG
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // 定义裁剪区域
    svg.append('defs').append('clipPath')
        .attr('id', 'clip')
        .append('rect')
        .attr('width', innerWidth)
        .attr('height', innerHeight);
    
    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // 计算数据范围
    const xExtent = d3.extent(points, d => d.x);
    const yExtent = d3.extent(points, d => d.y);
    
    const xScale = d3.scaleLinear()
        .domain([xExtent[0] - 10, xExtent[1] + 10])
        .range([0, innerWidth]);
    
    const yScale = d3.scaleLinear()
        .domain([yExtent[0] - 10, yExtent[1] + 10])
        .range([innerHeight, 0]);
    
    // 创建缩放后的比例尺
    let newXScale = xScale.copy();
    let newYScale = yScale.copy();
    
    // 添加坐标轴组
    const xAxis = g.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .attr('class', 'x-axis');
    
    const yAxis = g.append('g')
        .attr('class', 'y-axis');
    
    // 坐标轴标签
    g.append('text')
        .attr('x', innerWidth / 2)
        .attr('y', innerHeight + 40)
        .attr('fill', '#475569')
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .text('t-SNE 维度 1');
    
    g.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -50)
        .attr('fill', '#475569')
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .text('t-SNE 维度 2');
    
    // 添加网格组
    const xGrid = g.append('g')
        .attr('class', 'x-grid')
        .attr('transform', `translate(0,${innerHeight})`);
    
    const yGrid = g.append('g')
        .attr('class', 'y-grid');
    
    // 绘制散点的组（带裁剪）
    const dotsGroup = g.append('g')
        .attr('clip-path', 'url(#clip)');
    
    // 创建提示框
    const tooltip = d3.select(container)
        .append('div')
        .attr('class', 'tooltip')
        .style('display', 'none');
    
    // 绘制散点
    const dots = dotsGroup.selectAll('circle')
        .data(points)
        .join('circle')
        .attr('class', 'scatter-point')
        .attr('cx', d => xScale(d.x))
        .attr('cy', d => yScale(d.y))
        .attr('r', 4)
        .attr('fill', d => colorScale(d.label))
        .attr('stroke', 'white')
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.8)
        .on('mouseover', (event, d) => {
            tooltip
                .style('display', 'block')
                .style('left', (event.offsetX + 10) + 'px')
                .style('top', (event.offsetY - 10) + 'px')
                .html(`<strong>类别:</strong> ${d.label}<br><strong>内容:</strong> ${d.text}`);
            
            d3.select(event.target)
                .attr('r', 6)
                .attr('opacity', 1);
        })
        .on('mouseout', (event) => {
            tooltip.style('display', 'none');
            
            d3.select(event.target)
                .attr('r', 4)
                .attr('opacity', 0.8);
        });
    
    // 更新坐标轴和网格
    function updateAxes(transform) {
        newXScale = transform.rescaleX(xScale);
        newYScale = transform.rescaleY(yScale);
        
        xAxis.call(d3.axisBottom(newXScale).ticks(8));
        yAxis.call(d3.axisLeft(newYScale).ticks(8));
        
        xGrid.call(d3.axisBottom(newXScale).ticks(8).tickSize(-innerHeight).tickFormat(''))
            .selectAll('line')
            .attr('stroke', '#e2e8f0')
            .attr('stroke-dasharray', '2,2');
        xGrid.select('.domain').remove();
        
        yGrid.call(d3.axisLeft(newYScale).ticks(8).tickSize(-innerWidth).tickFormat(''))
            .selectAll('line')
            .attr('stroke', '#e2e8f0')
            .attr('stroke-dasharray', '2,2');
        yGrid.select('.domain').remove();
    }
    
    // 初始化坐标轴
    updateAxes(d3.zoomIdentity);
    
    // 添加缩放支持
    const zoom = d3.zoom()
        .extent([[0, 0], [innerWidth, innerHeight]])
        .scaleExtent([0.5, 20])
        .on('zoom', (event) => {
            dotsGroup.attr('transform', event.transform);
            updateAxes(event.transform);
        });
    
    svg.call(zoom);
    
    // 添加图例
    const legend = svg.append('g')
        .attr('class', 'legend')
        .attr('transform', `translate(${width - margin.right + 20}, ${margin.top})`);
    
    const legendTitle = legend.append('text')
        .attr('x', 0)
        .attr('y', -10)
        .attr('font-size', '12px')
        .attr('font-weight', '600')
        .attr('fill', '#1e293b')
        .text('产品类别');
    
    const legendItems = legend.selectAll('.legend-item')
        .data(uniqueLabels)
        .join('g')
        .attr('class', 'legend-item')
        .attr('transform', (d, i) => `translate(0, ${i * 20})`);
    
    legendItems.append('circle')
        .attr('cx', 6)
        .attr('cy', 0)
        .attr('r', 5)
        .attr('fill', d => colorScale(d));
    
    legendItems.append('text')
        .attr('x', 18)
        .attr('y', 4)
        .attr('font-size', '11px')
        .attr('fill', '#475569')
        .text(d => {
            const count = points.filter(p => p.label === d).length;
            return `${d} (${count})`;
        });
}

// ==================== 工具函数 ====================

function formatStatsText(text) {
    if (!text) return '加载中...';
    
    // 如果是对象，尝试提取有意义的信息
    if (typeof text === 'object') {
        // 尝试从对象中提取格式化的文本
        if (text.summary) text = text.summary;
        else if (text.description) text = text.description;
        else text = JSON.stringify(text, null, 2);
    }
    
    // 确保是字符串
    text = String(text);
    
    // 先处理换行符 - 在转义HTML之前
    // 将\n转换为特殊标记
    text = text.replace(/\n/g, '|||NEWLINE|||');
    
    // 转义HTML
    let html = escapeHtml(text);
    
    // 将特殊标记转换为HTML换行
    html = html.replace(/\|\|\|NEWLINE\|\|\|/g, '<br>');
    
    // 处理Markdown粗体 **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // 处理emoji后的冒号，使其更美观
    html = html.replace(/([\u{1F300}-\u{1F9FF}]):\s*/gu, '$1 ');
    
    return html;
}

function appendToCot(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    elements.cotArea.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        elements.cotArea.scrollTop = elements.cotArea.scrollHeight;
    });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
