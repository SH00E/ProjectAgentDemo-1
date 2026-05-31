# OMIn Dataset (Operations and Maintenance Intelligence)

航空维修领域数据集，用于构建维修知识图谱和向量检索库。

## 目录结构

```
dataset/
├── raw_data/                            # 原始数据（不动）
│   └── nd-crane-trusted_ke-0ac3387/     # Notre Dame 原始项目
│
└── processed_data/                      # 处理后的数据
    └── omin/                            # OMIn 数据集
        ├── process_data.py              # 数据处理脚本
        ├── import_config.json           # 导入配置
        ├── README.md                    # 本文件
        │
        ├── faa/                         # FAA 事故数据
        │   ├── faa_records.csv          # 2,748 条维修事故记录
        │   └── faa_entities.csv         # 3,940 个 NER 识别的实体
        │
        ├── maintnet/                    # MaintNet 维修数据
        │   ├── maintnet_records.csv     # 6,169 条飞机维修记录
        │   ├── aviation_abbreviations.csv # 65 个航空缩写
        │   ├── aviation_grammar.csv     # 57 个航空术语定义
        │   └── aviation_terms.csv       # 100 个航空术语
        │
        └── relations/                   # 关系数据
            └── rebel_relations.csv      # 4,763 条 REBEL 抽取的关系
```

## 数据说明

### FAA Records (`faa/faa_records.csv`)
FAA 航空事故/事件报告，包含维修相关记录。

| 字段 | 说明 |
|------|------|
| record_id | 唯一记录ID |
| description | 事故描述文本 |
| aircraft_model | 飞机型号 |
| manufacturer | 制造商 |
| accident_type | 事故类型代码 |
| date | 日期 |
| state | 州 |
| city | 城市 |
| airport | 机场 |

### MaintNet Records (`maintnet/maintnet_records.csv`)
飞机维修记录，包含问题描述和维修操作。

| 字段 | 说明 |
|------|------|
| record_id | 记录ID (MN_前缀) |
| problem | 问题描述 |
| action | 维修操作 |
| aircraft_model | 飞机型号 |
| manufacturer | 制造商 |

### Aviation Abbreviations (`maintnet/aviation_abbreviations.csv`)
航空缩写对照表。

| 字段 | 说明 |
|------|------|
| code | 编号 |
| abbreviation | 缩写 (如 ACFT) |
| full_description | 全称 (如 Aircraft) |

### Aviation Grammar (`maintnet/aviation_grammar.csv`)
航空术语语法信息。

| 字段 | 说明 |
|------|------|
| word | 词语 |
| description | 描述 |
| compound | 复合词 |
| lemma | 词元 |
| stem | 词干 |
| pos | 词性 |

### Aviation Terms (`maintnet/aviation_terms.csv`)
航空术语及示例。

| 字段 | 说明 |
|------|------|
| word | 术语 |
| example | 使用示例 |

### REBEL Relations (`relations/rebel_relations.csv`)
REBEL 模型抽取的实体关系三元组。

| 字段 | 说明 |
|------|------|
| relation_id | 关系ID |
| head | 头实体 |
| relation | 关系类型 |
| tail | 尾实体 |
| context | 上下文 |

### NER Entities (`faa/faa_entities.csv`)
spaCy NER 识别的命名实体。

| 字段 | 说明 |
|------|------|
| entity_id | 实体ID |
| record_id | 所属记录ID |
| entity_text | 实体文本 |
| entity_type | 实体类型 (PERSON, ORG, GPE等) |

## 数据统计

| 数据类型 | 数量 |
|----------|------|
| FAA 维修事故记录 | 2,748 条 |
| MaintNet 维修记录 | 6,169 条 |
| 航空缩写 | 65 个 |
| 航空语法 | 57 条 |
| 航空术语 | 100 个 |
| REBEL 关系 | 4,763 条 |
| NER 实体 | 3,940 个 |
| **总计** | **9,139 条知识项** |

## 重新生成数据

```bash
python repair_agent/dataset/processed_data/omin/process_data.py
```

## 数据来源

- FAA: [ASIAS Accident/Incident Data](https://av-info.faa.gov/dd_sublevel.asp?Folder=%5CAID)
- MaintNet: [MaintNet Project](https://arxiv.org/abs/2005.12443)
- NLP Tools: [nd-crane/trusted_ke](https://github.com/nd-crane/trusted_ke)
