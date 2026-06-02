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

### 4. 导入数据

**方式一：一键导入所有数据（推荐）**
```bash
# 全量导入
python scripts/import_all.py

# 测试导入（每个文件只导入 10 条）
python scripts/import_all.py --sample 10
```

**方式二：分步导入**
```bash
# 导入航空数据
python scripts/import_aviation.py --all

# 导入维修案例
python scripts/import_repair_cases.py

# 导入维护案例
python scripts/import_maintenance_cases.py
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
│   └── memory_data/
│       └── cases.db                 # 案例数据库
│
├── memory_data/
│   └── memory.db                    # 记忆数据库（系统运行时生成）
│
└── scripts/
    ├── import_all.py                # 一键导入所有数据
    ├── clear_all.py                 # 彻底清空所有数据库
    ├── import_aviation.py           # 航空数据导入
    ├── import_repair_cases.py       # 批量导入维修案例
    ├── import_maintenance_cases.py  # 批量导入维护案例
    └── dataset/
        ├── repair_cases.json        # 维修案例数据
        └── maintenance_cases.json   # 维护案例数据
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
| `/api/case` | POST | 添加案例 |
| `/api/cases` | GET | 获取案例列表（支持分页和类型过滤） |
| `/api/case/{id}` | DELETE | 删除案例 |
| `/api/stats` | GET | 系统统计 |
| `/api/history` | GET | 诊断历史 |

**案例管理 API 参数：**

```
GET /api/cases?page=1&page_size=20&case_type=repair
  - page: 页码（默认 1）
  - page_size: 每页数量（默认 20）
  - case_type: 案例类型过滤（repair/maintenance，不填返回全部）
```

## 常见问题

**Q: 如何彻底清空数据库重新开始？**
```bash
# 清空所有数据库（Qdrant + Neo4j + 案例库 + 记忆库）
python scripts/clear_all.py

# 只清空特定数据库
python scripts/clear_all.py --qdrant   # 只清空 Qdrant
python scripts/clear_all.py --neo4j    # 只清空 Neo4j
python scripts/clear_all.py --cases    # 只清空案例数据库
python scripts/clear_all.py --memory   # 只清空记忆数据库

# 清空后一键重新导入所有数据
python scripts/import_all.py
```

**Q: 如何一键导入所有数据？**
```bash
# 全量导入（航空数据 + 维修案例 + 维护案例）
python scripts/import_all.py

# 测试导入（每个文件只导入 10 条）
python scripts/import_all.py --sample 10
```

**Q: 如何批量导入案例？**

1. 编辑 `scripts/dataset/repair_cases.json` 或 `scripts/dataset/maintenance_cases.json`
2. 运行导入命令：
```bash
python scripts/import_repair_cases.py
python scripts/import_maintenance_cases.py
```

**Q: 案例数据格式是什么？**

维修案例格式：
```json
{
    "cases": [
        {
            "title": "案例标题",
            "device_type": "设备类型",
            "fault_symptom": "故障现象",
            "fault_cause": "故障原因",
            "solution": "解决方案",
            "parts_used": "使用备件",
            "technician": "维修人员",
            "notes": "备注"
        }
    ]
}
```

维护案例格式：
```json
{
    "cases": [
        {
            "title": "案例标题",
            "device_type": "设备类型",
            "maintenance_type": "维护类型（定期检查/更换/润滑/校准/清洁/其他）",
            "maintenance_cycle": "维护周期",
            "maintenance_standard": "维护标准/规范",
            "solution": "操作步骤",
            "parts_used": "使用备件/材料",
            "technician": "维护人员",
            "notes": "备注"
        }
    ]
}
```

**Q: 如何添加新的数据源？**
1. 将原始数据放入 `dataset/raw_data/`
2. 在 `dataset/processed_data/omin/process_data.py` 添加处理逻辑
3. 在 `scripts/import_aviation.py` 添加导入逻辑

**Q: 如何切换 LLM 模型？**
编辑 `.env` 文件中的 `LLM_MODEL_ID` 和 `LLM_BASE_URL`

## License

MIT
