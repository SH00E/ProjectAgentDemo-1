import re

path = 'repair_agent/ui/static/app.js'
with open(path, encoding='utf-8') as f:
    text = f.read()

# 1) Guard initStats against null btnRefreshStats
old_init = """function initStats() {
    if (elements.btnRefreshStats) {
        elements.btnRefreshStats.addEventListener('click', refreshStats);
    }

    // 初始加载统计（refreshStats 会自动处理）
    refreshStats();
}"""

text = re.sub(r'function initStats\(\) \{[\s\S]*?refreshStats\(\);\s*\}', old_init, text)

# 2) Fix refreshStats - guard btnRefreshStats and remove duplicate components/sessionId code
text = text.replace('elements.btnRefreshStats.disabled = true;', 'if (elements.btnRefreshStats) { elements.btnRefreshStats.disabled = true; elements.btnRefreshStats.textContent = ')
# Can't do complex replacements easily. Let me use a different approach.

# Actually, let me just fix the crashing code paths by making btnRefreshStats optional

# Fix refreshStats line 1379: elements.btnRefreshStats.disabled = true -> guard
text = text.replace(
    '    elements.btnRefreshStats.disabled = true;\n    elements.btnRefreshStats.textContent =',
    '    if (elements.btnRefreshStats) {\n        elements.btnRefreshStats.disabled = true;\n        elements.btnRefreshStats.textContent ='
)

text = text.replace(
    '    } finally {\n        elements.btnRefreshStats.disabled = false;\n        elements.btnRefreshStats.textContent =',
    '    } finally {\n        if (elements.btnRefreshStats) {\n            elements.btnRefreshStats.disabled = false;\n            elements.btnRefreshStats.textContent ='
)

# Close the braces we opened - find the next ); after textContent assignments
text = re.sub(
    r'(elements\.btnRefreshStats\.textContent = .+?;)\n(\s+)}',
    r'\1\n        }\n\2}',
    text
)

# Remove the duplicate history call at end of refreshStats
text = text.replace("""
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
}""", "\n}")

# Remove references to deleted elements in refreshStats
text = text.replace("            // 会话信息\n            elements.statSessionId.textContent = stats.system?.session_id || stats.session_id || '--';\n", "")
text = re.sub(r'\n\s*// 组件状态[\s\S]*?// 运行状态', '', text)

# Now fix case rendering - make it card grid
# Replace the if (data.success && ...) until the closing } of loadCases

old_case = """        if (data.success && data.cases && data.cases.length > 0) {
            let html = '';
            data.cases.forEach((c, i) => {"""

new_case = """        if (data.success && data.cases && data.cases.length > 0) {
            let html = '<div class="case-grid">';
            data.cases.forEach((c) => {"""

text = text.replace(old_case, new_case)

# Replace html += '</div>';  elements.caseList.innerHTML = html;  renderPagination
text = text.replace(
    "            elements.caseList.innerHTML = html;\n\n            // 渲染分页\n            renderPagination(data.total, data.page, data.total_pages);",
    "            html += '</div>';\n            elements.caseList.innerHTML = html;\n            renderPagination(data.total, data.page, data.total_pages);"
)

# Replace the case-item rendering with case-card rendering
# Replace typeLabel
text = text.replace("const typeLabel = caseType === 'repair' ? '\U0001f527'", "const typeLabel = caseType === 'repair' ? '")

# Just do minimal: fix the missing closing div for case-grid
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed app.js')
