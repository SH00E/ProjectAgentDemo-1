# AGENTS.md

## Project Overview

智能维修诊断系统（装备保障领域）。用户输入故障描述+可选照片，系统检索知识库、调用LLM诊断、评估损伤等级、生成维修工单。

技术栈: Python 3.10+ / hello-agents框架 / DeepSeek LLM / Qdrant向量库 / Neo4j图库 / FastAPI UI

> **注意**: FAA 航空数据（OMIn 数据集）当前导入但不参与诊断检索，主要知识来源为 QA 知识库 + 维修/维护案例。
> 导入时默认跳过 FAA，如需导入加 `--aviation` 标志。

## Quick Start

```bash
conda activate helloagent-1
cd repair_agent
python main.py --mode web      # FastAPI界面 http://127.0.0.1:7860
python main.py --mode test     # 命令行诊断测试

# 导入数据（默认跳过 FAA 航空数据）
python scripts/import_all.py               # 导入案例 + QA 知识库
python scripts/import_all.py --sample 10   # 测试模式
python scripts/import_all.py --aviation    # 含 FAA 全量导入

# 构建 QA 跨章关联（知识图谱连通）
python scripts/build_qa_relations.py --dry-run   # 预览
python scripts/build_qa_relations.py             # 执行
```

## Architecture

```
repair_agent/
├── main.py                  # 入口，argparse CLI（含Windows UTF-8修复）
├── config.py                # 配置（从.env读取）
├── modules/
│   ├── repair_agent.py      # RepairAgent主类，编排完整流程
│   ├── diagnosis_engine.py  # LLM诊断 + 损伤评估
│   ├── knowledge_base.py    # RAG/记忆工具封装
│   └── work_order.py        # 工单生成（纯模板，无外部依赖）
├── prompts/system_prompt.txt # 系统提示词（部分待补充）
├── ui/
│   ├── gradio_app.py        # Gradio界面（main.py --mode web）
│   ├── fastapi_app.py       # FastAPI界面（main.py --mode fastapi）
│   └── demo_*.py            # 独立演示脚本
├── dataset/
│   ├── raw_data/            # 原始数据（nd-crane-trusted_ke等）
│   └── processed_data/      # 处理后的数据
│       └── omin/            # OMIn航空维修数据集
├── knowledge/               # 知识库数据目录（当前为空）
│   ├── manuals/
│   ├── cases/
│   └── fault_codes/
└── memory_data/memory.db    # SQLite记忆存储

scripts/
└── import_aviation.py       # 航空数据→Qdrant+Neo4j 导入脚本
```

流程: 用户输入 -> diagnosis_engine(检索RAG+LLM分析) -> assess_severity -> recommend_solution -> work_order生成

## Key Dependencies

- `hello-agents` (v0.2.9): 提供 `HelloAgentsLLM`, `MemoryTool`, `RAGTool`。这是核心框架，不是本项目代码。
- DeepSeek API: LLM推理（.env中LLM_*配置）
- Qdrant: 向量检索（需启动，端口6333）
- Neo4j: 知识图谱（需启动，端口7687，默认密码12345678）
- Gradio: Web UI

## Known Issues (agent应优先修复)

1. **system_prompt.txt不完整**: "设备类型"部分标注"待知识库建立后补充"。
2. **Embedding**: `.env` 中 `EMBED_API_KEY` 和 `EMBED_BASE_URL` 未填写，当前回退到本地sentence-transformers模型。若需dashscope需要配置并安装`dashscope`包。

## Environment

- Conda env: `helloagent-1`
- `.env`文件位于项目根目录（`agent-repair-version1/.env`），由python-dotenv自动加载
- API密钥已硬编码在.env中（DeepSeek key: `sk-ab650...`）

## Conventions

- 中文注释和日志输出
- 模块间通过依赖注入（构造函数传入rag_tool/memory_tool/llm）
- 工单格式为JSON，通过`format_order_text()`转为可读文本
- LLM调用使用messages格式 `[{role, content}]`，期望返回JSON
- JSON解析有fallback：从```json代码块中提取，失败时返回默认结构

## Pending Features

- 照片分析（当前仅存储到感知记忆，不做视觉分析）
- 设备类型扩展（system_prompt待补充）
- 测试用例和CI
