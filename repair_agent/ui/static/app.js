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
    evidenceArea: document.getElementById('evidence-area'),
    orderArea: document.getElementById('order-area'),

    // 维护
    maintDesc: document.getElementById('maint-desc'),
    maintImage: document.getElementById('maint-image'),
    maintImagePreview: document.getElementById('maint-image-preview'),
    maintPreviewImg: document.getElementById('maint-preview-img'),
    maintRemoveImage: document.getElementById('maint-remove-image'),
    btnMaintenance: document.getElementById('btn-maintenance'),
    maintCotArea: document.getElementById('maint-cot-area'),
    maintEvidenceArea: document.getElementById('maint-evidence-area'),
    maintOrderArea: document.getElementById('maint-order-area'),

    // 检索
    searchQuery: document.getElementById('search-query'),
    btnSearch: document.getElementById('btn-search'),
    searchResults: document.getElementById('search-results'),
    searchHistoryList: document.getElementById('search-history-list'),

    // 案例 - 维修表单
    btnAddRepair: document.getElementById('btn-add-repair'),
    repairResult: document.getElementById('repair-result'),
    
    // 案例 - 维护表单
    btnAddMaint: document.getElementById('btn-add-maint'),
    maintResult: document.getElementById('maint-result'),
    
    // 案例列表
    caseList: document.getElementById('case-list'),

    // 统计
    btnRefreshStats: document.getElementById('btn-refresh-stats'),
    statKbCount: document.getElementById('stat-kb-count'),
    statMemoryCount: document.getElementById('stat-memory-count'),
    statDiagnosisCount: document.getElementById('stat-diagnosis-count'),
    statRunStatus: document.getElementById('stat-run-status'),
    statSessionId: document.getElementById('stat-session-id'),
    componentsList: document.getElementById('components-list'),

    // 智能问答
    qaQuestion: document.getElementById('qa-question'),
    btnAsk: document.getElementById('btn-ask'),
    qaAnswer: document.getElementById('qa-answer'),

    // 系统反馈
    feedbackType: document.getElementById('feedback-type'),
    feedbackContext: document.getElementById('feedback-context'),
    feedbackOutput: document.getElementById('feedback-output'),
    feedbackIssue: document.getElementById('feedback-issue'),
    feedbackCorrect: document.getElementById('feedback-correct'),
    btnSubmitFeedback: document.getElementById('btn-submit-feedback'),
    feedbackResult: document.getElementById('feedback-result'),
    feedbackList: document.getElementById('feedback-list')
};

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initDiagnosis();
    initMaintenance();
    initQA();
    initSearch();
    initCase();
    initFeedback();
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

            case 'neo4j':
                handleNeo4j(data);
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

function handleNeo4j(data) {
    if (data.results && data.results.length > 0) {
        // 在推理过程中显示简要信息
        appendToCot(`<div class="cot-step-sub">🗄️ 从知识图谱找到 ${data.total} 条相关信息</div>`);
        
        // 在证据链区域显示详细信息
        let html = '<div class="evidence-chain">';
        data.results.forEach((r, i) => {
            const typeIcon = r.type === 'Aircraft' ? '🛩️' : r.type === 'Manufacturer' ? '🏭' : r.type === 'IncidentType' ? '⚠️' : '📌';
            const typeLabel = r.type === 'Aircraft' ? '飞机型号' : r.type === 'Manufacturer' ? '制造商' : r.type === 'IncidentType' ? '事故类型' : '实体';
            
            html += `
                <div class="evidence-item neo4j-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${typeIcon} 知识图谱</span>
                        <span class="evidence-type">${typeLabel}</span>
                    </div>
                    <div class="evidence-content"><strong>${escapeHtml(r.name)}</strong></div>
                    <div class="evidence-details">
                        ${r.details?.manufacturers ? `<span class="evidence-tag">🏭 ${r.details.manufacturers.join(', ')}</span>` : ''}
                        ${r.details?.incident_types ? `<span class="evidence-tag">⚠️ ${r.details.incident_types.join(', ')}</span>` : ''}
                        ${r.details?.aircraft_models ? `<span class="evidence-tag">🛩️ ${r.details.aircraft_models.join(', ')}</span>` : ''}
                        ${r.details?.record_count ? `<span class="evidence-tag">📊 ${r.details.record_count} 条记录</span>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        // 追加到证据链区域
        const evidenceArea = document.getElementById('evidence-area');
        if (evidenceArea) {
            evidenceArea.innerHTML = html;
        }
    }
}

function handleRAG(data) {
    if (data.results && data.results.length > 0) {
        // 在推理过程中显示简要信息
        appendToCot(`<div class="cot-step-sub">📚 检索到 ${data.total} 条相关记录</div>`);
        
        // 在证据链区域显示详细信息
        let html = '<div class="evidence-chain">';
        data.results.forEach((r, i) => {
            const sourceIcon = r.source === 'faa' ? '✈️' : r.source === 'maintnet' ? '🔧' : '📖';
            const relevance = r.relevance || '低';
            const relevanceClass = relevance === '高' ? 'relevance-high' : relevance === '中' ? 'relevance-medium' : 'relevance-low';
            const matchTypeLabel = r.match_type === 'keyword' ? '🔑' : '🧠';
            
            html += `
                <div class="evidence-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${sourceIcon} ${escapeHtml(r.source_label)}</span>
                        <span class="relevance-badge ${relevanceClass}">${matchTypeLabel} ${relevance}</span>
                    </div>
                    <div class="evidence-content">${escapeHtml(r.content)}</div>
                    <div class="evidence-details">
                        ${r.aircraft_model ? `<span class="evidence-tag">🛩️ ${escapeHtml(r.aircraft_model)}</span>` : ''}
                        ${r.manufacturer ? `<span class="evidence-tag">🏭 ${escapeHtml(r.manufacturer)}</span>` : ''}
                        ${r.record_id ? `<span class="evidence-tag">🆔 ${escapeHtml(r.record_id)}</span>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        elements.evidenceArea.innerHTML = html;
    } else {
        appendToCot('<div class="cot-step-sub">📚 知识库暂无匹配记录</div>');
        elements.evidenceArea.innerHTML = '<em class="placeholder">未找到相关证据</em>';
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

    // 在证据链区域显示诊断依据
    if (data.evidence_chain && data.evidence_chain.length > 0) {
        let evidenceHtml = '<div class="evidence-chain">';
        evidenceHtml += '<div class="evidence-title">📋 诊断依据（证据链）</div>';
        data.evidence_chain.forEach((ev, i) => {
            const sourceIcon = ev.source === 'faa' ? '✈️' : ev.source === 'maintnet' ? '🔧' : '📖';
            const relevance = ev.relevance || '低';
            const relevanceClass = relevance === '高' ? 'relevance-high' : relevance === '中' ? 'relevance-medium' : 'relevance-low';
            const matchTypeLabel = ev.match_type === 'keyword' ? '🔑' : '🧠';
            
            evidenceHtml += `
                <div class="evidence-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${sourceIcon} ${escapeHtml(ev.source_label)}</span>
                        <span class="relevance-badge ${relevanceClass}">${matchTypeLabel} ${relevance}</span>
                    </div>
                    <div class="evidence-content">${escapeHtml(ev.content)}</div>
                    <div class="evidence-details">
                        ${ev.aircraft_model ? `<span class="evidence-tag">🛩️ ${escapeHtml(ev.aircraft_model)}</span>` : ''}
                        ${ev.manufacturer ? `<span class="evidence-tag">🏭 ${escapeHtml(ev.manufacturer)}</span>` : ''}
                        ${ev.record_id ? `<span class="evidence-tag">🆔 ${escapeHtml(ev.record_id)}</span>` : ''}
                    </div>
                </div>
            `;
        });
        evidenceHtml += '</div>';
        elements.evidenceArea.innerHTML = evidenceHtml;
    }
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
    } else if (!data.success) {
        // 显示错误信息和建议
        let html = `<div class="cot-step" style="color: #f59e0b;">⚠️ ${escapeHtml(data.error || '无法完成诊断')}</div>`;
        if (data.message) {
            html += `<div class="cot-text">${escapeHtml(data.message).replace(/\n/g, '<br>')}</div>`;
        }
        if (data.suggestion) {
            html += `<div class="cot-text" style="color: #3b82f6; margin-top: 12px;">💡 ${escapeHtml(data.suggestion)}</div>`;
        }
        appendToCot(html);
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

// 搜索状态
const searchState = {
    currentQuery: '',
    currentPage: 1,
    pageSize: 20,
    totalPages: 1,
    total: 0
};

async function searchKnowledge(page = 1) {
    const query = elements.searchQuery.value.trim();
    if (!query) {
        alert('请输入查询内容');
        return;
    }

    // 更新搜索状态
    searchState.currentQuery = query;
    searchState.currentPage = page;

    elements.btnSearch.disabled = true;
    elements.btnSearch.textContent = '🔍 检索中...';
    if (page === 1) {
        elements.searchResults.innerHTML = '<div class="loading-placeholder"><span class="loading-icon">⏳</span><p>正在检索...</p></div>';
    }

    // 添加到搜索历史
    if (page === 1) {
        addToSearchHistory(query);
    }

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query: query, 
                page: page, 
                page_size: searchState.pageSize 
            })
        });

        const data = await response.json();

        if (data.success && data.results && data.results.length > 0) {
            // 更新分页状态
            searchState.total = data.total || 0;
            searchState.totalPages = data.total_pages || 1;
            searchState.currentPage = data.page || 1;

            let html = '';
            
            // 显示结果统计
            html += `<div class="search-stats">共找到 ${searchState.total} 条结果，当前第 ${searchState.currentPage}/${searchState.totalPages} 页</div>`;
            
            data.results.forEach((r, i) => {
                const content = r.content || JSON.stringify(r);
                const score = r.score || 0;
                const relevance = r.relevance || '低';  // 高/中/低
                const matchType = r.match_type || 'vector';  // keyword/vector
                const keywords = r.keywords || [];
                const source = r.source || '知识库';
                const aircraftModel = r.aircraft_model || '';
                const manufacturer = r.manufacturer || '';
                const recordId = r.record_id || '';
                
                // 判断来源类型
                let sourceIcon = '📖';
                if (source.includes('FAA')) sourceIcon = '✈️';
                else if (source.includes('MaintNet')) sourceIcon = '🔧';
                else if (source.includes('案例') || recordId.startsWith('CASE_')) sourceIcon = '📝';

                // 高亮关键词
                let highlightedContent = escapeHtml(content.substring(0, 300));
                keywords.forEach(kw => {
                    if (kw) {
                        const regex = new RegExp(escapeRegex(kw), 'gi');
                        highlightedContent = highlightedContent.replace(regex, `<span class="keyword">${escapeHtml(kw)}</span>`);
                    }
                });

                // 相似度等级样式
                let relevanceClass = 'relevance-low';
                let relevanceLabel = '低';
                if (relevance === '高') {
                    relevanceClass = 'relevance-high';
                    relevanceLabel = '高';
                } else if (relevance === '中') {
                    relevanceClass = 'relevance-medium';
                    relevanceLabel = '中';
                }
                
                // 匹配类型标签
                const matchTypeLabel = matchType === 'keyword' ? '🔑 关键词' : '🧠 语义';
                
                // 计算全局序号
                const globalIndex = (searchState.currentPage - 1) * searchState.pageSize + i + 1;

                html += `
                    <div class="search-result-item">
                        <div class="search-result-header">
                            <div class="search-result-title">📄 结果 ${globalIndex}</div>
                            <div class="search-result-score">
                                <span class="relevance-badge ${relevanceClass}">相关度: ${relevanceLabel}</span>
                                <span class="match-type-badge">${matchTypeLabel}</span>
                            </div>
                        </div>
                        <div class="search-result-content">${highlightedContent}${content.length > 300 ? '...' : ''}</div>
                        <div class="search-result-details">
                            ${aircraftModel ? `<span class="search-tag">🛩️ ${escapeHtml(aircraftModel)}</span>` : ''}
                            ${manufacturer ? `<span class="search-tag">🏭 ${escapeHtml(manufacturer)}</span>` : ''}
                            ${recordId ? `<span class="search-tag">🆔 ${escapeHtml(recordId)}</span>` : ''}
                        </div>
                        <div class="search-result-meta">
                            <span>📍 来源: ${escapeHtml(source)}</span>
                        </div>
                    </div>
                `;
            });
            
            // 添加分页控件
            if (searchState.totalPages > 1) {
                html += '<div class="search-pagination">';
                
                // 上一页按钮
                if (searchState.currentPage > 1) {
                    html += `<button class="pagination-btn" onclick="searchKnowledge(${searchState.currentPage - 1})">◀ 上一页</button>`;
                }
                
                // 页码
                const maxVisible = 5;
                let startPage = Math.max(1, searchState.currentPage - Math.floor(maxVisible / 2));
                let endPage = Math.min(searchState.totalPages, startPage + maxVisible - 1);
                
                if (endPage - startPage < maxVisible - 1) {
                    startPage = Math.max(1, endPage - maxVisible + 1);
                }
                
                if (startPage > 1) {
                    html += `<button class="pagination-btn" onclick="searchKnowledge(1)">1</button>`;
                    if (startPage > 2) html += '<span class="pagination-info">...</span>';
                }
                
                for (let i = startPage; i <= endPage; i++) {
                    html += `<button class="pagination-btn ${i === searchState.currentPage ? 'active' : ''}" onclick="searchKnowledge(${i})">${i}</button>`;
                }
                
                if (endPage < searchState.totalPages) {
                    if (endPage < searchState.totalPages - 1) html += '<span class="pagination-info">...</span>';
                    html += `<button class="pagination-btn" onclick="searchKnowledge(${searchState.totalPages})">${searchState.totalPages}</button>`;
                }
                
                // 下一页按钮
                if (searchState.currentPage < searchState.totalPages) {
                    html += `<button class="pagination-btn" onclick="searchKnowledge(${searchState.currentPage + 1})">下一页 ▶</button>`;
                }
                
                html += '</div>';
            }
            
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

// 案例管理状态
const caseState = {
    currentPage: 1,
    pageSize: 10,
    currentFilter: 'all',
    currentCaseType: 'repair'
};

function initCase() {
    // 维修案例添加按钮
    if (elements.btnAddRepair) {
        elements.btnAddRepair.addEventListener('click', addRepairCase);
    }
    
    // 维护案例添加按钮
    if (elements.btnAddMaint) {
        elements.btnAddMaint.addEventListener('click', addMaintenanceCase);
    }

    // 案例类型切换
    document.querySelectorAll('input[name="case-type"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            caseState.currentCaseType = e.target.value;
            toggleCaseForm(e.target.value);
        });
    });

    // 维修模板按钮
    document.querySelectorAll('#repair-form .btn-template').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#repair-form .btn-template').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyRepairTemplate(btn.dataset.template);
        });
    });
    
    // 维护模板按钮
    document.querySelectorAll('#maintenance-form .btn-template').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#maintenance-form .btn-template').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyMaintenanceTemplate(btn.dataset.template);
        });
    });

    // 筛选标签
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            caseState.currentFilter = tab.dataset.filter;
            caseState.currentPage = 1;
            loadCases();
        });
    });
}

function toggleCaseForm(caseType) {
    const repairForm = document.getElementById('repair-form');
    const maintenanceForm = document.getElementById('maintenance-form');

    if (caseType === 'repair') {
        repairForm.classList.remove('hidden');
        maintenanceForm.classList.add('hidden');
    } else {
        repairForm.classList.add('hidden');
        maintenanceForm.classList.remove('hidden');
    }
}

function applyRepairTemplate(type) {
    const templates = {
        aircraft: {
            title: '战机发动机推力下降维修',
            device_type: '某型战机',
            fault_symptom: '发动机在高空出现推力下降，尾喷口温度异常升高',
            fault_cause: '涡轮叶片疲劳裂纹，导致燃气泄漏',
            solution: '1. 拆卸发动机\n2. 检查涡轮叶片\n3. 更换受损叶片\n4. 重新组装测试',
            parts_used: '涡轮叶片组件、密封件',
            technician: '',
            notes: ''
        },
        engine: {
            title: '发动机启动故障',
            device_type: '某型战机',
            fault_symptom: '发动机启动困难，点火后转速上升缓慢',
            fault_cause: '燃油泵压力不足，喷油嘴堵塞',
            solution: '1. 检查燃油泵\n2. 清洁或更换喷油嘴\n3. 测试燃油压力\n4. 重新启动测试',
            parts_used: '喷油嘴、燃油滤清器',
            technician: '',
            notes: ''
        },
        missile: {
            title: '导弹制导系统故障',
            device_type: '某型导弹',
            fault_symptom: '制导系统在测试中出现信号丢失，无法锁定目标',
            fault_cause: '惯性导航单元漂移超标，陀螺仪性能下降',
            solution: '1. 检测惯性导航单元\n2. 校准陀螺仪\n3. 更换故障组件\n4. 系统联调测试',
            parts_used: '陀螺仪组件、连接电缆',
            technician: '',
            notes: '需要在洁净环境下操作'
        },
        custom: {
            title: '',
            device_type: '',
            fault_symptom: '',
            fault_cause: '',
            solution: '',
            parts_used: '',
            technician: '',
            notes: ''
        }
    };

    const template = templates[type];
    if (template) {
        document.getElementById('repair-title').value = template.title || '';
        document.getElementById('repair-device-type').value = template.device_type || '';
        document.getElementById('repair-fault-symptom').value = template.fault_symptom || '';
        document.getElementById('repair-fault-cause').value = template.fault_cause || '';
        document.getElementById('repair-solution').value = template.solution || '';
        document.getElementById('repair-parts').value = template.parts_used || '';
        document.getElementById('repair-technician').value = template.technician || '';
        document.getElementById('repair-notes').value = template.notes || '';
    }
}

function applyMaintenanceTemplate(type) {
    const templates = {
        'oil-change': {
            title: '战机发动机滑油更换',
            device_type: '某型战机',
            maintenance_type: '更换',
            maintenance_cycle: '每500飞行小时或6个月',
            maintenance_standard: '发动机维护手册 Chapter 12',
            solution: '1. 发动机运行至正常工作温度\n2. 关闭发动机，拆卸放油螺塞\n3. 排放旧滑油\n4. 更换滑油滤清器\n5. 安装放油螺塞\n6. 加注新滑油至规定液位\n7. 启动发动机检查是否泄漏',
            parts_used: '滑油滤清器、航空滑油、放油螺塞垫片',
            technician: '',
            notes: ''
        },
        'radar-check': {
            title: '雷达系统定期维护',
            device_type: '某型战机',
            maintenance_type: '定期检查',
            maintenance_cycle: '每100飞行小时',
            maintenance_standard: '雷达维护手册',
            solution: '1. 检查雷达天线外观\n2. 测试雷达发射功率\n3. 检查接收灵敏度\n4. 校准雷达波束\n5. 检查冷却系统\n6. 记录测试数据',
            parts_used: '',
            technician: '',
            notes: '维护时需断开雷达电源'
        },
        'missile-maint': {
            title: '导弹发射系统维护',
            device_type: '某型导弹',
            maintenance_type: '定期检查',
            maintenance_cycle: '每季度或发射前',
            maintenance_standard: '导弹维护规程',
            solution: '1. 检查发射导轨状态\n2. 测试电气连接\n3. 检查液压/气动系统\n4. 测试发射控制信号\n5. 检查安全锁定装置\n6. 记录维护结果',
            parts_used: '密封圈、润滑脂',
            technician: '',
            notes: '严格遵守安全操作规程'
        },
        'custom-maint': {
            title: '',
            device_type: '',
            maintenance_type: '',
            maintenance_cycle: '',
            maintenance_standard: '',
            solution: '',
            parts_used: '',
            technician: '',
            notes: ''
        }
    };

    const template = templates[type];
    if (template) {
        document.getElementById('maint-title').value = template.title || '';
        document.getElementById('maint-device-type').value = template.device_type || '';
        document.getElementById('maint-type').value = template.maintenance_type || '';
        document.getElementById('maint-cycle').value = template.maintenance_cycle || '';
        document.getElementById('maint-standard').value = template.maintenance_standard || '';
        document.getElementById('maint-solution').value = template.solution || '';
        document.getElementById('maint-parts').value = template.parts_used || '';
        document.getElementById('maint-technician').value = template.technician || '';
        document.getElementById('maint-notes').value = template.notes || '';
    }
}

async function addRepairCase() {
    const title = document.getElementById('repair-title').value.trim();
    if (!title) {
        alert('请输入案例标题');
        return;
    }

    const caseData = {
        case_type: 'repair',
        title: title,
        device_type: document.getElementById('repair-device-type').value.trim(),
        fault_symptom: document.getElementById('repair-fault-symptom').value.trim(),
        fault_cause: document.getElementById('repair-fault-cause').value.trim(),
        solution: document.getElementById('repair-solution').value.trim(),
        parts_used: document.getElementById('repair-parts').value.trim(),
        technician: document.getElementById('repair-technician').value.trim(),
        notes: document.getElementById('repair-notes').value.trim()
    };

    const btn = elements.btnAddRepair;
    const result = elements.repairResult;
    
    btn.disabled = true;
    btn.textContent = '➕ 添加中...';
    result.textContent = '';
    result.className = 'result-message';

    try {
        const response = await fetch('/api/case', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(caseData)
        });

        const data = await response.json();

        if (data.success) {
            result.textContent = `✅ ${data.message}`;
            result.className = 'result-message success';
            // 清空表单
            document.getElementById('repair-title').value = '';
            document.getElementById('repair-device-type').value = '';
            document.getElementById('repair-fault-symptom').value = '';
            document.getElementById('repair-fault-cause').value = '';
            document.getElementById('repair-solution').value = '';
            document.getElementById('repair-parts').value = '';
            document.getElementById('repair-technician').value = '';
            document.getElementById('repair-notes').value = '';
            // 刷新案例列表
            caseState.currentPage = 1;
            loadCases();
        } else {
            result.textContent = `❌ ${data.message || data.error}`;
            result.className = 'result-message error';
        }
    } catch (e) {
        result.textContent = `❌ 添加失败: ${e.message}`;
        result.className = 'result-message error';
    } finally {
        btn.disabled = false;
        btn.textContent = '➕ 添加维修案例';
    }
}

async function addMaintenanceCase() {
    const title = document.getElementById('maint-title').value.trim();
    if (!title) {
        alert('请输入案例标题');
        return;
    }

    const caseData = {
        case_type: 'maintenance',
        title: title,
        device_type: document.getElementById('maint-device-type').value.trim(),
        maintenance_type: document.getElementById('maint-type').value,
        maintenance_cycle: document.getElementById('maint-cycle').value.trim(),
        maintenance_standard: document.getElementById('maint-standard').value.trim(),
        solution: document.getElementById('maint-solution').value.trim(),
        parts_used: document.getElementById('maint-parts').value.trim(),
        technician: document.getElementById('maint-technician').value.trim(),
        notes: document.getElementById('maint-notes').value.trim()
    };

    const btn = elements.btnAddMaint;
    const result = elements.maintResult;
    
    btn.disabled = true;
    btn.textContent = '➕ 添加中...';
    result.textContent = '';
    result.className = 'result-message';

    try {
        const response = await fetch('/api/case', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(caseData)
        });

        const data = await response.json();

        if (data.success) {
            result.textContent = `✅ ${data.message}`;
            result.className = 'result-message success';
            // 清空表单
            document.getElementById('maint-title').value = '';
            document.getElementById('maint-device-type').value = '';
            document.getElementById('maint-type').value = '';
            document.getElementById('maint-cycle').value = '';
            document.getElementById('maint-standard').value = '';
            document.getElementById('maint-solution').value = '';
            document.getElementById('maint-parts').value = '';
            document.getElementById('maint-technician').value = '';
            document.getElementById('maint-notes').value = '';
            // 刷新案例列表
            caseState.currentPage = 1;
            loadCases();
        } else {
            result.textContent = `❌ ${data.message || data.error}`;
            result.className = 'result-message error';
        }
    } catch (e) {
        result.textContent = `❌ 添加失败: ${e.message}`;
        result.className = 'result-message error';
    } finally {
        btn.disabled = false;
        btn.textContent = '➕ 添加维护案例';
    }
}

async function loadCases() {
    if (!elements.caseList) return;

    elements.caseList.innerHTML = '<div class="loading-placeholder"><span class="loading-icon">⏳</span><p>加载中...</p></div>';

    try {
        let url = `/api/cases?page=${caseState.currentPage}&page_size=${caseState.pageSize}`;
        if (caseState.currentFilter !== 'all') {
            url += `&case_type=${caseState.currentFilter}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success && data.cases && data.cases.length > 0) {
            let html = '';
            data.cases.forEach((c, i) => {
                const caseType = c.case_type || 'repair';
                const typeLabel = caseType === 'repair' ? '🔧 维修' : '🛠️ 维护';
                const typeClass = caseType === 'repair' ? 'repair' : 'maintenance';
                const title = c.title || `案例 ${i + 1}`;
                const deviceType = c.device_type || '';
                const solution = c.solution || '';
                const partsUsed = c.parts_used || '';
                const technician = c.technician || '';
                const notes = c.notes || '';
                const createdAt = c.created_at || '';

                let fieldsHtml = '';

                if (caseType === 'repair') {
                    const faultSymptom = c.fault_symptom || '';
                    const faultCause = c.fault_cause || '';
                    fieldsHtml = `
                        ${faultSymptom ? `<div class="case-item-field"><strong>⚠️ 故障现象:</strong> ${escapeHtml(faultSymptom)}</div>` : ''}
                        ${faultCause ? `<div class="case-item-field"><strong>🔍 故障原因:</strong> ${escapeHtml(faultCause)}</div>` : ''}
                    `;
                } else {
                    const maintenanceType = c.maintenance_type || '';
                    const maintenanceCycle = c.maintenance_cycle || '';
                    const maintenanceStandard = c.maintenance_standard || '';
                    fieldsHtml = `
                        ${maintenanceType ? `<div class="case-item-field"><strong>📋 维护类型:</strong> ${escapeHtml(maintenanceType)}</div>` : ''}
                        ${maintenanceCycle ? `<div class="case-item-field"><strong>🔄 维护周期:</strong> ${escapeHtml(maintenanceCycle)}</div>` : ''}
                        ${maintenanceStandard ? `<div class="case-item-field"><strong>📐 维护标准:</strong> ${escapeHtml(maintenanceStandard)}</div>` : ''}
                    `;
                }

                html += `
                    <div class="case-item ${typeClass}" data-id="${c.id}">
                        <div class="case-item-header">
                            <div>
                                <span class="case-type-tag ${typeClass}">${typeLabel}</span>
                                <span class="case-item-title">${escapeHtml(title)}</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span class="case-item-time">${createdAt ? escapeHtml(createdAt.substring(0, 10)) : ''}</span>
                                <button class="case-delete-btn" onclick="confirmDeleteCase(${c.id}, '${escapeHtml(title).replace(/'/g, "\\'")}')" title="删除案例">🗑️</button>
                            </div>
                        </div>
                        ${deviceType ? `<div class="case-item-field"><strong>🛩️ 设备类型:</strong> ${escapeHtml(deviceType)}</div>` : ''}
                        ${fieldsHtml}
                        ${solution ? `<div class="case-item-field"><strong>🔧 解决方案:</strong> ${escapeHtml(solution).replace(/\n/g, '<br>')}</div>` : ''}
                        ${partsUsed ? `<div class="case-item-field"><strong>📦 使用备件:</strong> ${escapeHtml(partsUsed)}</div>` : ''}
                        ${technician ? `<div class="case-item-field"><strong>👤 维修/维护人员:</strong> ${escapeHtml(technician)}</div>` : ''}
                        ${notes ? `<div class="case-item-field"><strong>📝 备注:</strong> ${escapeHtml(notes)}</div>` : ''}
                    </div>
                `;
            });
            elements.caseList.innerHTML = html;

            // 渲染分页
            renderPagination(data.total, data.page, data.total_pages);
        } else {
            elements.caseList.innerHTML = `
                <div class="loading-placeholder">
                    <span class="loading-icon">📭</span>
                    <p>暂无案例记录</p>
                </div>
            `;
            document.getElementById('case-pagination').innerHTML = '';
        }
    } catch (e) {
        elements.caseList.innerHTML = `<div class="loading-placeholder"><p style="color: #dc2626;">❌ 加载失败: ${e.message}</p></div>`;
    }
}

function renderPagination(total, currentPage, totalPages) {
    const paginationEl = document.getElementById('case-pagination');
    if (!paginationEl || totalPages <= 1) {
        if (paginationEl) paginationEl.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="pagination-btn" onclick="goToPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>◀ 上一页</button>`;

    // 显示页码
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        html += `<button class="pagination-btn" onclick="goToPage(1)">1</button>`;
        if (startPage > 2) html += `<span class="pagination-info">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="pagination-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span class="pagination-info">...</span>`;
        html += `<button class="pagination-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    html += `<button class="pagination-btn" onclick="goToPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>下一页 ▶</button>`;
    html += `<span class="pagination-info">共 ${total} 条</span>`;

    paginationEl.innerHTML = html;
}

function goToPage(page) {
    caseState.currentPage = page;
    loadCases();
}

function confirmDeleteCase(caseId, caseTitle) {
    // 创建确认对话框
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-content">
            <div class="modal-title">⚠️ 确认删除</div>
            <div class="modal-message">确定要删除案例「${caseTitle}」吗？<br>此操作不可撤销。</div>
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-cancel" onclick="this.closest('.modal-overlay').remove()">取消</button>
                <button class="modal-btn modal-btn-confirm" onclick="deleteCase(${caseId}); this.closest('.modal-overlay').remove()">确认删除</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
}

async function deleteCase(caseId) {
    try {
        const response = await fetch(`/api/case/${caseId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // 重新加载案例列表
            loadCases();
        } else {
            alert(`删除失败: ${data.error || '未知错误'}`);
        }
    } catch (e) {
        alert(`删除失败: ${e.message}`);
    }
}

// ==================== 系统统计 ====================

function initStats() {
    elements.btnRefreshStats.addEventListener('click', refreshStats);
    initVizTabs();
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

            // 从字符串中提取数字
            let kbCount = '--';
            let memCount = '--';
            
            if (typeof kbStats === 'string') {
                // 从 "文档分块数: 8917" 中提取数字
                const kbMatch = kbStats.match(/文档分块数:\s*(\d+)/);
                if (kbMatch) kbCount = kbMatch[1];
            } else {
                kbCount = kbStats.total_documents || kbStats.count || '--';
            }
            
            if (typeof memStats === 'string') {
                // 从 "总记忆数: 0" 中提取数字
                const memMatch = memStats.match(/总记忆数:\s*(\d+)/);
                if (memMatch) memCount = memMatch[1];
            } else {
                memCount = memStats.total_memories || memStats.count || '--';
            }

            elements.statKbCount.textContent = kbCount;
            elements.statMemoryCount.textContent = memCount;

            // 会话信息
            elements.statSessionId.textContent = stats.system?.session_id || stats.session_id || '--';
            
            // 诊断历史 - 从单独的API获取
            try {
                const historyResponse = await fetch('/api/history');
                const historyData = await historyResponse.json();
                if (historyData.success && historyData.history) {
                    // 过滤掉无效的记录
                    const validHistory = historyData.history.filter(h => 
                        h.content && !h.content.includes('未找到')
                    );
                    elements.statDiagnosisCount.textContent = validHistory.length;
                }
            } catch (histErr) {
                console.error('获取诊断历史失败:', histErr);
            }

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

// ==================== 知识图谱标签页切换 ====================

function initVizTabs() {
    document.querySelectorAll('.viz-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const vizName = tab.dataset.viz;
            
            // 更新标签按钮状态
            document.querySelectorAll('.viz-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // 更新面板显示
            document.querySelectorAll('.viz-panel').forEach(p => p.classList.remove('active'));
            document.getElementById(`viz-${vizName}`).classList.add('active');
            
            // 首次展开时加载数据
            const panel = document.getElementById(`viz-${vizName}`);
            if (!panel.dataset.loaded) {
                switch(vizName) {
                    case 'overview': loadKnowledgeGraph(); break;
                    case 'aircraft': loadAircraftView(); break;
                    case 'incident': loadIncidentView(); break;
                    case 'manufacturer': loadManufacturerView(); break;
                    case 'heatmap': loadHeatmapView(); break;
                }
                panel.dataset.loaded = 'true';
            }
        });
    });
}

// ==================== 飞机型号视图 ====================

async function loadAircraftView() {
    const container = document.getElementById('kg-aircraft-container');
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载...</p></div>';
    
    try {
        const response = await fetch('/api/stats/knowledge-graph');
        const result = await response.json();
        
        if (!result.success || !result.data.nodes.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无数据</div></div>';
            return;
        }
        
        const { nodes, links } = result.data;
        const aircraftNodes = nodes.filter(n => n.type === 'Aircraft');
        
        // 按连接数排序
        aircraftNodes.sort((a, b) => {
            const aLinks = links.filter(l => l.source === a.id || l.target === a.id).length;
            const bLinks = links.filter(l => l.source === b.id || l.target === b.id).length;
            return bLinks - aLinks;
        });
        
        // 渲染柱状图
        renderBarChart(container, aircraftNodes.map(n => ({
            label: n.label,
            value: links.filter(l => l.source === n.id || l.target === n.id).length
        })), '飞机型号', '关联数量', '#f87171');
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

// ==================== 事故类型视图 ====================

async function loadIncidentView() {
    const container = document.getElementById('kg-incident-container');
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载...</p></div>';
    
    try {
        const response = await fetch('/api/stats/knowledge-graph');
        const result = await response.json();
        
        if (!result.success || !result.data.nodes.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无数据</div></div>';
            return;
        }
        
        const { nodes, links } = result.data;
        const incidentNodes = nodes.filter(n => n.type === 'Incident');
        
        // 按连接数排序
        incidentNodes.sort((a, b) => {
            const aLinks = links.filter(l => l.source === a.id || l.target === a.id).length;
            const bLinks = links.filter(l => l.source === b.id || l.target === b.id).length;
            return bLinks - aLinks;
        });
        
        // 渲染柱状图
        renderBarChart(container, incidentNodes.map(n => ({
            label: n.label,
            value: links.filter(l => l.source === n.id || l.target === n.id).length
        })), '事故类型', '关联数量', '#fbbf24');
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

// ==================== 制造商视图 ====================

async function loadManufacturerView() {
    const container = document.getElementById('kg-manufacturer-container');
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载...</p></div>';
    
    try {
        const response = await fetch('/api/stats/knowledge-graph');
        const result = await response.json();
        
        if (!result.success || !result.data.nodes.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无数据</div></div>';
            return;
        }
        
        const { nodes, links } = result.data;
        const mfgNodes = nodes.filter(n => n.type === 'Manufacturer');
        
        // 按连接数排序
        mfgNodes.sort((a, b) => {
            const aLinks = links.filter(l => l.source === a.id || l.target === a.id).length;
            const bLinks = links.filter(l => l.source === b.id || l.target === b.id).length;
            return bLinks - aLinks;
        });
        
        // 渲染柱状图
        renderBarChart(container, mfgNodes.map(n => ({
            label: n.label,
            value: links.filter(l => l.source === n.id || l.target === n.id).length
        })), '制造商', '关联数量', '#4ade80');
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

// ==================== 热力图视图 ====================

async function loadHeatmapView() {
    const container = document.getElementById('kg-heatmap-container');
    container.innerHTML = '<div class="viz-loading"><div class="viz-loading-spinner"></div><p>正在加载...</p></div>';
    
    try {
        const response = await fetch('/api/stats/knowledge-graph');
        const result = await response.json();
        
        if (!result.success || !result.data.nodes.length) {
            container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无数据</div></div>';
            return;
        }
        
        const { nodes, links } = result.data;
        const aircraftNodes = nodes.filter(n => n.type === 'Aircraft').slice(0, 10);
        const incidentNodes = nodes.filter(n => n.type === 'Incident').slice(0, 8);
        
        // 构建热力图数据
        const heatmapData = [];
        aircraftNodes.forEach(a => {
            incidentNodes.forEach(inc => {
                const count = links.filter(l => 
                    (l.source === a.id && l.target === inc.id) || 
                    (l.source === inc.id && l.target === a.id)
                ).length;
                heatmapData.push({
                    x: a.label,
                    y: inc.label,
                    value: count
                });
            });
        });
        
        // 渲染热力图
        renderHeatmap(container, heatmapData, aircraftNodes.map(n => n.label), incidentNodes.map(n => n.label));
        
    } catch (error) {
        container.innerHTML = `<div class="viz-empty"><div class="viz-empty-icon">❌</div><div class="viz-empty-text">加载失败: ${error.message}</div></div>`;
    }
}

// ==================== 渲染工具函数 ====================

function renderBarChart(container, data, xLabel, yLabel, color) {
    container.innerHTML = '';
    
    if (data.length === 0) {
        container.innerHTML = '<div class="viz-empty"><div class="viz-empty-icon">📭</div><div class="viz-empty-text">暂无数据</div></div>';
        return;
    }
    
    const width = container.clientWidth || 800;
    const height = 400;
    const margin = { top: 30, right: 30, bottom: 100, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // X轴
    const x = d3.scaleBand()
        .domain(data.map(d => d.label))
        .range([0, innerWidth])
        .padding(0.2);
    
    g.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .attr('transform', 'rotate(-45)')
        .style('text-anchor', 'end')
        .attr('font-size', '11px');
    
    // Y轴
    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.value)])
        .range([innerHeight, 0]);
    
    g.append('g')
        .call(d3.axisLeft(y));
    
    // 柱子
    g.selectAll('rect')
        .data(data)
        .join('rect')
        .attr('x', d => x(d.label))
        .attr('y', d => y(d.value))
        .attr('width', x.bandwidth())
        .attr('height', d => innerHeight - y(d.value))
        .attr('fill', color)
        .attr('rx', 4)
        .append('title')
        .text(d => `${d.label}: ${d.value}`);
    
    // 数值标签
    g.selectAll('.value-label')
        .data(data)
        .join('text')
        .attr('class', 'value-label')
        .attr('x', d => x(d.label) + x.bandwidth() / 2)
        .attr('y', d => y(d.value) - 5)
        .attr('text-anchor', 'middle')
        .attr('font-size', '11px')
        .attr('fill', '#475569')
        .text(d => d.value);
}

function renderHeatmap(container, data, xLabels, yLabels) {
    container.innerHTML = '';
    
    const width = container.clientWidth || 800;
    const height = 400;
    const margin = { top: 30, right: 30, bottom: 100, left: 120 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // X轴
    const x = d3.scaleBand()
        .domain(xLabels)
        .range([0, innerWidth])
        .padding(0.05);
    
    g.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .attr('transform', 'rotate(-45)')
        .style('text-anchor', 'end')
        .attr('font-size', '11px');
    
    // Y轴
    const y = d3.scaleBand()
        .domain(yLabels)
        .range([0, innerHeight])
        .padding(0.05);
    
    g.append('g')
        .call(d3.axisLeft(y));
    
    // 颜色比例
    const maxVal = d3.max(data, d => d.value) || 1;
    const colorScale = d3.scaleSequential(d3.interpolateYlOrRd)
        .domain([0, maxVal]);
    
    // 热力图格子
    g.selectAll('rect')
        .data(data)
        .join('rect')
        .attr('x', d => x(d.x))
        .attr('y', d => y(d.y))
        .attr('width', x.bandwidth())
        .attr('height', y.bandwidth())
        .attr('fill', d => d.value > 0 ? colorScale(d.value) : '#f1f5f9')
        .attr('rx', 2)
        .append('title')
        .text(d => `${d.x} × ${d.y}: ${d.value}`);
    
    // 数值标签
    g.selectAll('.cell-label')
        .data(data.filter(d => d.value > 0))
        .join('text')
        .attr('class', 'cell-label')
        .attr('x', d => x(d.x) + x.bandwidth() / 2)
        .attr('y', d => y(d.y) + y.bandwidth() / 2)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', '11px')
        .attr('fill', d => d.value > maxVal / 2 ? 'white' : '#334155')
        .text(d => d.value);
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

// ==================== 日常维护 ====================

const maintenanceState = {
    isProcessing: false,
    analysisText: '',
    solutionText: ''
};

function initMaintenance() {
    // 图片预览
    if (elements.maintImage) {
        elements.maintImage.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    elements.maintPreviewImg.src = e.target.result;
                    elements.maintImagePreview.classList.remove('hidden');
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 移除图片
    if (elements.maintRemoveImage) {
        elements.maintRemoveImage.addEventListener('click', () => {
            elements.maintImage.value = '';
            elements.maintImagePreview.classList.add('hidden');
            elements.maintPreviewImg.src = '';
        });
    }

    // 维护按钮
    if (elements.btnMaintenance) {
        elements.btnMaintenance.addEventListener('click', startMaintenance);
    }

    // 输入框变化时启用按钮
    if (elements.maintDesc) {
        elements.maintDesc.addEventListener('input', () => {
            elements.btnMaintenance.disabled = !elements.maintDesc.value.trim();
        });

        // Ctrl+Enter 快捷键
        elements.maintDesc.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                if (!elements.btnMaintenance.disabled) {
                    startMaintenance();
                }
            }
        });
    }
}

async function startMaintenance() {
    if (maintenanceState.isProcessing) return;

    const description = elements.maintDesc.value.trim();
    if (!description) {
        alert('请输入维护需求描述');
        return;
    }

    maintenanceState.isProcessing = true;
    maintenanceState.analysisText = '';
    maintenanceState.solutionText = '';

    // 更新 UI 状态
    elements.btnMaintenance.disabled = true;
    elements.btnMaintenance.textContent = '⏳ 处理中...';
    elements.maintCotArea.innerHTML = '<div class="cot-step">⏳ 开始处理维护需求...</div>';
    elements.maintOrderArea.classList.add('hidden');
    elements.maintOrderArea.innerHTML = '';
    elements.maintEvidenceArea.innerHTML = '<em class="placeholder">正在检索维护依据...</em>';

    // 准备表单数据
    const formData = new FormData();
    formData.append('description', description);
    formData.append('mode', 'maintenance');  // 关键：指定维护模式
    if (elements.maintImage.files[0]) {
        formData.append('image', elements.maintImage.files[0]);
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
                        handleMaintenanceSSEEvent(eventType, eventData);
                        eventType = '';
                        eventData = '';
                    }
                }
            }
        }
    } catch (error) {
        appendToMaintCot(`<div class="cot-step" style="color: #dc2626;">❌ 错误: ${error.message}</div>`);
    } finally {
        maintenanceState.isProcessing = false;
        elements.btnMaintenance.disabled = false;
        elements.btnMaintenance.textContent = '🔧 生成维护方案';
    }
}

function handleMaintenanceSSEEvent(eventType, dataStr) {
    try {
        const data = JSON.parse(dataStr);

        switch (eventType) {
            case 'step':
                appendToMaintCot(`<div class="cot-step">${escapeHtml(data.text)}</div>`);
                break;

            case 'neo4j':
                handleMaintenanceNeo4j(data);
                break;

            case 'rag':
                handleMaintenanceRAG(data);
                break;

            case 'analysis':
                handleMaintenanceAnalysis(data);
                break;

            case 'solution_text':
                handleMaintenanceSolutionText(data);
                break;

            case 'diagnosis':
                handleMaintenanceDiagnosis(data);
                break;

            case 'solution':
                handleMaintenanceSolution(data);
                break;

            case 'result':
                handleMaintenanceResult(data);
                break;

            case 'error':
                appendToMaintCot(`<div class="cot-step" style="color: #dc2626;">❌ ${escapeHtml(data.message)}</div>`);
                break;
        }
    } catch (e) {
        console.error('解析 SSE 事件失败:', e, dataStr);
    }
}

function handleMaintenanceNeo4j(data) {
    if (data.results && data.results.length > 0) {
        appendToMaintCot(`<div class="cot-step-sub">🗄️ 从知识图谱找到 ${data.total} 条相关信息</div>`);
        
        let html = '<div class="evidence-chain">';
        data.results.forEach((r, i) => {
            const typeIcon = r.type === 'Aircraft' ? '🛩️' : r.type === 'Manufacturer' ? '🏭' : '📌';
            html += `
                <div class="evidence-item neo4j-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${typeIcon} ${escapeHtml(r.type)}</span>
                    </div>
                    <div class="evidence-content">${escapeHtml(r.name)}</div>
                </div>
            `;
        });
        html += '</div>';
        elements.maintEvidenceArea.innerHTML = html;
    }
}

function handleMaintenanceRAG(data) {
    if (data.results && data.results.length > 0) {
        appendToMaintCot(`<div class="cot-step-sub">📚 检索到 ${data.total} 条相关维护记录</div>`);
        
        let html = '<div class="evidence-chain">';
        data.results.forEach((r, i) => {
            const sourceIcon = r.source === 'faa' ? '✈️' : r.source === 'maintnet' ? '🔧' : r.source === 'user_case' ? '📝' : '📖';
            const relevance = r.relevance || '低';
            const relevanceClass = relevance === '高' ? 'relevance-high' : relevance === '中' ? 'relevance-medium' : 'relevance-low';
            const matchTypeLabel = r.match_type === 'keyword' ? '🔑' : '🧠';
            
            html += `
                <div class="evidence-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${sourceIcon} ${escapeHtml(r.source_label)}</span>
                        <span class="relevance-badge ${relevanceClass}">${matchTypeLabel} ${relevance}</span>
                    </div>
                    <div class="evidence-content">${escapeHtml(r.content)}</div>
                    <div class="evidence-details">
                        ${r.aircraft_model ? `<span class="evidence-tag">🛩️ ${escapeHtml(r.aircraft_model)}</span>` : ''}
                        ${r.record_id ? `<span class="evidence-tag">🆔 ${escapeHtml(r.record_id)}</span>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        elements.maintEvidenceArea.innerHTML = html;
    }
}

function handleMaintenanceAnalysis(data) {
    maintenanceState.analysisText += data.chunk;
    
    let analysisDiv = document.getElementById('maint-analysis');
    if (!analysisDiv) {
        analysisDiv = document.createElement('div');
        analysisDiv.id = 'maint-analysis';
        analysisDiv.innerHTML = '<div class="cot-step">🧠 需求分析</div><div class="cot-text"></div>';
        elements.maintCotArea.appendChild(analysisDiv);
    }
    
    const textDiv = analysisDiv.querySelector('.cot-text');
    textDiv.textContent = maintenanceState.analysisText;
    scrollToMaintBottom();
}

function handleMaintenanceSolutionText(data) {
    maintenanceState.solutionText += data.chunk;
    
    let solutionDiv = document.getElementById('maint-solution');
    if (!solutionDiv) {
        solutionDiv = document.createElement('div');
        solutionDiv.id = 'maint-solution';
        solutionDiv.innerHTML = '<div class="cot-step">🔧 维护方案</div><div class="cot-text"></div>';
        elements.maintCotArea.appendChild(solutionDiv);
    }
    
    const textDiv = solutionDiv.querySelector('.cot-text');
    textDiv.textContent = maintenanceState.solutionText;
    scrollToMaintBottom();
}

function handleMaintenanceDiagnosis(data) {
    let html = '<div class="cot-step">📋 维护分析结果</div>';
    html += `<div class="cot-text">维护类型: <strong>${escapeHtml(data.fault_type)}</strong></div>`;
    html += `<div class="cot-text">优先级: ${escapeHtml(data.urgency)}</div>`;
    html += `<div class="cot-text">复杂度: ${escapeHtml(data.severity_level)} — ${escapeHtml(data.severity_desc)}</div>`;
    
    if (data.possible_causes && data.possible_causes.length > 0) {
        html += `<div class="cot-text">维护要点: ${data.possible_causes.map(c => escapeHtml(c)).join('、')}</div>`;
    }
    
    appendToMaintCot(html);
    
    // 显示维护依据
    if (data.evidence_chain && data.evidence_chain.length > 0) {
        let evidenceHtml = '<div class="evidence-chain">';
        evidenceHtml += '<div class="evidence-title">📋 维护依据</div>';
        data.evidence_chain.forEach((ev, i) => {
            const sourceIcon = ev.source === 'faa' ? '✈️' : ev.source === 'maintnet' ? '🔧' : ev.source === 'user_case' ? '📝' : '📖';
            const relevance = ev.relevance || '低';
            const relevanceClass = relevance === '高' ? 'relevance-high' : relevance === '中' ? 'relevance-medium' : 'relevance-low';
            
            evidenceHtml += `
                <div class="evidence-item">
                    <div class="evidence-header">
                        <span class="evidence-num">#${i + 1}</span>
                        <span class="evidence-source">${sourceIcon} ${escapeHtml(ev.source_label)}</span>
                        <span class="relevance-badge ${relevanceClass}">${relevance}</span>
                    </div>
                    <div class="evidence-content">${escapeHtml(ev.content)}</div>
                </div>
            `;
        });
        evidenceHtml += '</div>';
        elements.maintEvidenceArea.innerHTML = evidenceHtml;
    }
}

function handleMaintenanceSolution(data) {
    let html = `<div class="cot-step">🔧 维护步骤（${data.repair_steps.length} 步）</div>`;
    
    data.repair_steps.forEach(s => {
        html += `<div class="cot-text">${s.step}. ${escapeHtml(s.action)}</div>`;
    });
    
    if (data.estimated_time) {
        html += `<div class="cot-text" style="margin-top: 8px;">⏱️ 预计 ${escapeHtml(data.estimated_time)} | 难度: ${escapeHtml(data.difficulty)}</div>`;
    }
    
    appendToMaintCot(html);
}

function handleMaintenanceResult(data) {
    if (data.success && data.work_order) {
        appendToMaintCot('<div class="cot-step">✅ 维护方案生成完成</div>');
        renderMaintenanceWorkOrder(data.work_order);
    } else if (!data.success) {
        let html = `<div class="cot-step" style="color: #f59e0b;">⚠️ ${escapeHtml(data.error || '无法生成维护方案')}</div>`;
        if (data.message) {
            html += `<div class="cot-text">${escapeHtml(data.message).replace(/\n/g, '<br>')}</div>`;
        }
        appendToMaintCot(html);
    }
}

function renderMaintenanceWorkOrder(order) {
    const orderInfo = order.order_info || {};
    const maintenance = order.maintenance || order.diagnosis || {};
    const solution = order.solution || {};
    
    let html = `
        <div class="order-header">
            <div class="order-title">🔧 维护工单</div>
            <div class="order-meta">
                <span>📋 ${escapeHtml(orderInfo.order_id || 'N/A')}</span>
                <span>📅 ${escapeHtml(orderInfo.created_at || '').substring(0, 10)}</span>
                <span class="order-status">${escapeHtml(order.status || '待执行')}</span>
            </div>
        </div>
        
        <div class="order-section">
            <div class="order-section-title">📝 维护需求</div>
            <div class="order-text">${escapeHtml(order.fault_description || order.maintenance_description || '')}</div>
        </div>
        
        <div class="order-section">
            <div class="order-section-title">🔍 维护分析</div>
            <div class="order-field"><strong>维护类型:</strong> ${escapeHtml(maintenance.fault_type || maintenance.maintenance_type || '未知')}</div>
            <div class="order-field"><strong>复杂度:</strong> ${escapeHtml(maintenance.severity?.level || '待评估')}</div>
            <div class="order-field"><strong>优先级:</strong> ${escapeHtml(maintenance.urgency || '中')}</div>
        </div>
    `;
    
    // 维护步骤
    const steps = solution.repair_steps || solution.maintenance_steps || [];
    if (steps.length > 0) {
        html += `
            <div class="order-section">
                <div class="order-section-title">🔧 维护步骤</div>
                <div class="order-steps">
        `;
        steps.forEach(s => {
            html += `<div class="order-step"><span class="step-num">${s.step}</span> ${escapeHtml(s.action)}</div>`;
        });
        html += '</div></div>';
    }
    
    // 备件/材料
    const parts = solution.parts_required || [];
    if (parts.length > 0) {
        html += `
            <div class="order-section">
                <div class="order-section-title">📦 所需备件/材料</div>
                <div class="order-parts">
        `;
        parts.forEach(p => {
            html += `<div class="order-part">• ${escapeHtml(p.name)} ${p.quantity ? '×' + p.quantity : ''} ${p.specification ? '(' + escapeHtml(p.specification) + ')' : ''}</div>`;
        });
        html += '</div></div>';
    }
    
    // 工具
    const tools = solution.tools_required || [];
    if (tools.length > 0) {
        html += `
            <div class="order-section">
                <div class="order-section-title">🛠️ 所需工具</div>
                <div class="order-tools">${tools.map(t => escapeHtml(t)).join('、')}</div>
            </div>
        `;
    }
    
    // 安全提示
    const warnings = solution.safety_warnings || [];
    if (warnings.length > 0) {
        html += `
            <div class="order-section">
                <div class="order-section-title">⚠️ 安全提示</div>
                <div class="order-warnings">
        `;
        warnings.forEach(w => {
            html += `<div class="order-warning">⚠️ ${escapeHtml(w)}</div>`;
        });
        html += '</div></div>';
    }
    
    // 预计时间和难度
    html += `
        <div class="order-section">
            <div class="order-section-title">📊 评估</div>
            <div class="order-field"><strong>预计时间:</strong> ${escapeHtml(solution.estimated_time || '待评估')}</div>
            <div class="order-field"><strong>难度等级:</strong> ${escapeHtml(solution.difficulty || '中等')}</div>
        </div>
    `;
    
    elements.maintOrderArea.innerHTML = html;
    elements.maintOrderArea.classList.remove('hidden');
}

function appendToMaintCot(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    elements.maintCotArea.appendChild(div);
    scrollToMaintBottom();
}

function scrollToMaintBottom() {
    requestAnimationFrame(() => {
        elements.maintCotArea.scrollTop = elements.maintCotArea.scrollHeight;
    });
}

// ==================== 智能问答 ====================

const qaState = {
    isProcessing: false
};

function initQA() {
    // 提问按钮
    if (elements.btnAsk) {
        elements.btnAsk.addEventListener('click', askQuestion);
    }

    // 输入框
    if (elements.qaQuestion) {
        elements.qaQuestion.addEventListener('input', () => {
            elements.btnAsk.disabled = !elements.qaQuestion.value.trim();
        });

        // Ctrl+Enter 快捷键
        elements.qaQuestion.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                if (!elements.btnAsk.disabled) {
                    askQuestion();
                }
            }
        });
    }

    // 示例问题点击
    document.querySelectorAll('.qa-example').forEach(example => {
        example.addEventListener('click', () => {
            elements.qaQuestion.value = example.dataset.question;
            elements.btnAsk.disabled = false;
            askQuestion();
        });
    });
}

async function askQuestion() {
    if (qaState.isProcessing) return;

    const question = elements.qaQuestion.value.trim();
    if (!question) {
        alert('请输入问题');
        return;
    }

    qaState.isProcessing = true;
    elements.btnAsk.disabled = true;
    elements.btnAsk.textContent = '⏳ 思考中...';
    elements.qaAnswer.innerHTML = '<div class="qa-loading"><span class="loading-icon">🧠</span><p>正在分析问题...</p></div>';

    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        if (data.success) {
            let html = '';
            
            // 关键词解析
            if (data.keywords && data.keywords.length > 0) {
                html += '<div class="qa-section">';
                html += '<h3>🔑 关键词解析</h3>';
                data.keywords.forEach((kw, i) => {
                    html += `
                        <div class="qa-keyword-item">
                            <div class="qa-keyword-title">
                                <span class="qa-keyword-num">${i + 1}</span>
                                <span class="qa-keyword-name">${escapeHtml(kw.keyword)}</span>
                                <span class="qa-keyword-relation">${escapeHtml(kw.relation)}</span>
                            </div>
                            <div class="qa-keyword-explanation">${escapeHtml(kw.explanation)}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            // 综合回答
            html += '<div class="qa-section">';
            html += '<h3>📋 综合解答</h3>';
            html += `<div class="qa-answer-content">${escapeHtml(data.answer).replace(/\n/g, '<br>')}</div>`;
            html += '</div>';
            
            elements.qaAnswer.innerHTML = html;
        } else {
            elements.qaAnswer.innerHTML = `<div class="qa-error">❌ ${escapeHtml(data.error || '回答失败')}</div>`;
        }
    } catch (e) {
        elements.qaAnswer.innerHTML = `<div class="qa-error">❌ 请求失败: ${e.message}</div>`;
    } finally {
        qaState.isProcessing = false;
        elements.btnAsk.disabled = false;
        elements.btnAsk.textContent = '💡 提问';
    }
}

// ==================== 系统反馈 ====================

function initFeedback() {
    // 提交反馈按钮
    if (elements.btnSubmitFeedback) {
        elements.btnSubmitFeedback.addEventListener('click', submitFeedback);
    }

    // 加载反馈历史
    loadFeedbacks();
}

async function submitFeedback() {
    const feedbackType = elements.feedbackType.value;
    const context = elements.feedbackContext.value.trim();
    const systemOutput = elements.feedbackOutput.value.trim();
    const issueDescription = elements.feedbackIssue.value.trim();
    const correctAnswer = elements.feedbackCorrect.value.trim();

    if (!issueDescription) {
        alert('请描述问题');
        return;
    }

    elements.btnSubmitFeedback.disabled = true;
    elements.btnSubmitFeedback.textContent = '📤 提交中...';
    elements.feedbackResult.textContent = '';
    elements.feedbackResult.className = 'result-message';

    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                feedback_type: feedbackType,
                context: context,
                system_output: systemOutput,
                issue_description: issueDescription,
                correct_answer: correctAnswer
            })
        });

        const data = await response.json();

        if (data.success) {
            elements.feedbackResult.textContent = '✅ 感谢您的反馈！';
            elements.feedbackResult.className = 'result-message success';
            
            // 清空表单
            elements.feedbackContext.value = '';
            elements.feedbackOutput.value = '';
            elements.feedbackIssue.value = '';
            elements.feedbackCorrect.value = '';
            
            // 重新加载反馈列表
            loadFeedbacks();
        } else {
            elements.feedbackResult.textContent = `❌ ${data.error || '提交失败'}`;
            elements.feedbackResult.className = 'result-message error';
        }
    } catch (e) {
        elements.feedbackResult.textContent = `❌ 提交失败: ${e.message}`;
        elements.feedbackResult.className = 'result-message error';
    } finally {
        elements.btnSubmitFeedback.disabled = false;
        elements.btnSubmitFeedback.textContent = '📤 提交反馈';
    }
}

async function loadFeedbacks() {
    if (!elements.feedbackList) return;

    try {
        const response = await fetch('/api/feedbacks');
        const data = await response.json();

        if (data.success && data.feedbacks && data.feedbacks.length > 0) {
            let html = '';
            data.feedbacks.forEach(f => {
                const typeLabel = {
                    'diagnosis': '🔍 故障诊断',
                    'maintenance': '🔧 日常维护',
                    'qa': '💡 智能问答',
                    'search': '📚 知识检索',
                    'other': '📝 其他'
                }[f.feedback_type] || '📝 其他';

                html += `
                    <div class="feedback-item">
                        <div class="feedback-header">
                            <span class="feedback-type-badge">${typeLabel}</span>
                            <span class="feedback-time">${f.created_at || ''}</span>
                        </div>
                        <div class="feedback-issue">${escapeHtml(f.issue_description)}</div>
                        ${f.correct_answer ? `<div class="feedback-correct">✅ 正确答案: ${escapeHtml(f.correct_answer)}</div>` : ''}
                    </div>
                `;
            });
            elements.feedbackList.innerHTML = html;
        } else {
            elements.feedbackList.innerHTML = `
                <div class="loading-placeholder">
                    <span class="loading-icon">📭</span>
                    <p>暂无反馈记录</p>
                </div>
            `;
        }
    } catch (e) {
        console.error('加载反馈失败:', e);
    }
}
