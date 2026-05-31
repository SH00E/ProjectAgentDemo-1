# ✈️ 航空维修智能助手

基于 RAG + 知识图谱 + 多模态 LLM 的航空维修诊断系统

## 项目结构

```
repair_agent/
├── main.py                    # 主程序入口
├── config.py                  # 配置管理
├── knowledge/                 # 知识库数据（用户后续填充）
│   ├── manuals/              # 维修手册
│   ├── cases/                # 维修案例
│   └── fault_codes/          # 故障码库
├── modules/
│   ├── __init__.py
│   ├── knowledge_base.py     # 知识库管理模块
│   ├── diagnosis_engine.py   # 诊断引擎模块
│   ├── work_order.py         # 工单生成模块
│   └── repair_agent.py       # 维修智能体（整合模块）
├── prompts/
│   └── system_prompt.txt     # 系统提示词
└── ui/
    └── gradio_app.py         # Web界面
```

## 使用方法

### 1. 启动Web界面

```bash
cd repair_agent
python main.py --mode web
```

访问 http://127.0.0.1:7860 即可使用Web界面

### 2. 命令行测试

```bash
cd repair_agent
python main.py --mode test
```

### 3. 知识库管理

```bash
cd repair_agent
python main.py --mode knowledge
```

## 功能说明

### 故障诊断
- 输入故障描述
- 可选上传现场照片
- 系统自动诊断并给出维修方案
- 生成JSON格式工单

### 知识库管理
- 导入维修手册（PDF/Word/Excel）
- 添加维修案例
- 添加故障码
- 检索知识库

### 工单格式

```json
{
  "order_info": {
    "order_id": "WO-20260519-abc123",
    "created_at": "2026-05-19T22:00:00",
    "status": "待处理"
  },
  "fault_description": "故障描述",
  "diagnosis": {
    "fault_type": "故障类型",
    "possible_causes": ["原因1", "原因2"],
    "severity": {"level": "中等", "description": "..."}
  },
  "solution": {
    "repair_steps": [...],
    "parts_required": [...],
    "tools_required": [...],
    "safety_warnings": [...]
  }
}
```

## 环境要求

- Python 3.10+
- Qdrant向量数据库 (localhost:6333)
- Neo4j图数据库 (localhost:7687)
- DeepSeek API密钥

## 后续扩展

1. **知识库填充**: 将维修手册、案例、故障码添加到 `knowledge/` 目录
2. **照片分析**: 集成视觉AI模型进行照片分析
3. **设备类型**: 在 `prompts/system_prompt.txt` 中补充设备类型信息
