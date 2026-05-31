# 保障智能助手 - 智能维修诊断系统

基于 RAG + 知识图谱 + 多模态 LLM 的航空维修诊断系统

## 快速开始

### 环境要求

- Python 3.10+
- Conda 环境: `helloagent-1`
- Qdrant 向量数据库 (端口 6333)
- Neo4j 图数据库 (端口 7687)

### 1. 安装依赖

```bash
# 先安装 PyTorch（根据你的环境选择）
# GPU 版本 (CUDA 12.1，推荐):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CPU 版本 (无显卡或 Mac):
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 再安装其他依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

### 3. 启动数据库

```bash
# 启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 启动 Neo4j
docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/12345678 neo4j
```

### 4. 导入航空数据

```bash
# 测试导入 10 条
python scripts/import_aviation.py --sample 10

# 全量导入 (~9k 条)
python scripts/import_aviation.py --all
```

### 5. 启动应用

```bash
# FastAPI 界面 (推荐)
python main.py --mode web

# 访问: http://127.0.0.1:7860
```

## 项目结构

```
agent-repair-version1/
├── main.py                          # 入口
├── .env                             # 环境变量配置
├── requirements.txt                 # Python 依赖
│
├── repair_agent/
│   ├── modules/
│   │   ├── repair_agent.py          # 主类
│   │   ├── diagnosis_engine.py      # LLM 诊断
│   │   ├── knowledge_base.py        # RAG/记忆工具
│   │   └── work_order.py            # 工单生成
│   │
│   ├── ui/
│   │   ├── fastapi_app.py           # FastAPI 界面
│   │   └── static/                  # 前端文件
│   │
│   ├── dataset/
│   │   ├── raw_data/                # 原始数据
│   │   └── processed_data/omin/     # 处理后的航空数据
│   │
│   └── memory_data/memory.db        # SQLite 记忆存储
│
└── scripts/
    └── import_aviation.py           # 数据导入脚本
```

## 数据库说明

### Qdrant 向量库

| 集合名 | 用途 |
|--------|------|
| `aviation_knowledge_base` | 航空维修知识库 (新建) |
| `rag_knowledge_base` | 旧家电维修数据 (可保留) |

### Neo4j 图数据库

**航空领域节点类型：**
- `AviationRecord` - 维修记录
- `AircraftModel` - 飞机型号
- `Manufacturer` - 制造商
- `IncidentType` - 事故类型
- `Location` - 地点
- `AviationTerm` - 航空术语
- `AviationAbbr` - 航空缩写

**关系类型：**
- `INVOLVES_AIRCRAFT` - 涉及飞机
- `MANUFACTURED_BY` - 制造商
- `HAS_INCIDENT_TYPE` - 事故类型
- `OCCURRED_IN` - 发生地点

## 部署到服务器

### 方式一：直接部署

```bash
# 1. 克隆代码
git clone <repo-url>
cd agent-repair-version1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env
cp .env.example .env
vim .env  # 填入 API 密钥和数据库地址

# 4. 导入数据
python scripts/import_aviation.py --all

# 5. 启动服务
python main.py --mode web
```

### 方式二：Docker 部署

```bash
# 构建镜像
docker build -t repair-agent .

# 运行容器
docker run -d \
  -p 7860:7860 \
  -e QDRANT_URL=http://qdrant:6333 \
  -e NEO4J_URI=bolt://neo4j:7687 \
  repair-agent
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页 |
| `/api/status` | GET | 系统状态 |
| `/api/diagnose` | POST | 提交诊断 (SSE 流式) |
| `/api/search` | POST | 知识检索 |
| `/api/stats` | GET | 系统统计 |
| `/api/history` | GET | 诊断历史 |

## 常见问题

**Q: 如何重新导入数据？**
```bash
# 清空旧数据并重新导入
python scripts/import_aviation.py --all
```

**Q: 如何添加新的数据源？**
1. 将原始数据放入 `dataset/raw_data/`
2. 在 `dataset/processed_data/omin/process_data.py` 添加处理逻辑
3. 在 `scripts/import_aviation.py` 添加导入逻辑

**Q: 如何切换 LLM 模型？**
编辑 `.env` 文件中的 `LLM_MODEL_ID` 和 `LLM_BASE_URL`

## License

MIT
