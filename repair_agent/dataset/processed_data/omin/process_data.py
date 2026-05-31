# -*- coding: utf-8 -*-
"""
OMIn 数据集处理脚本
从原始 nd-crane-trusted_ke 数据中提取并处理为统一格式

用法:
    python dataset/omin/process_data.py
"""

import os
import csv
import json

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "../..", "raw_data", "nd-crane-trusted_ke-0ac3387")
FAA_DIR = os.path.join(BASE_DIR, "faa")
MAINTNET_DIR = os.path.join(BASE_DIR, "maintnet")
RELATIONS_DIR = os.path.join(BASE_DIR, "relations")


def ensure_dirs():
    """确保输出目录存在"""
    for d in [FAA_DIR, MAINTNET_DIR, RELATIONS_DIR]:
        os.makedirs(d, exist_ok=True)


def process_faa_data():
    """
    处理 FAA 事故数据
    提取关键字段: record_id, description, aircraft_type, manufacturer, 
                  accident_type, year, month, day, state, location
    """
    input_file = os.path.join(RAW_DIR, "OMIn_dataset", "data", "FAA_data", "Maintenance_Text_data_nona.csv")
    output_file = os.path.join(FAA_DIR, "faa_records.csv")
    
    print("[FAA] Processing FAA accident/incident data...")
    
    # FAA字段映射 (列名 -> 字段含义)
    # c5 = unique record ID
    # c119 = natural language description (主要文本)
    # c24 = aircraft model
    # c23 = manufacturer
    # c78 = accident type code
    # c7 = year
    # c8 = month  
    # c9 = day
    # c33 = state
    # c34 = city
    # c147 = airport
    
    records = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = row.get("c5", "").strip()
            description = row.get("c119", "").strip()
            
            # 跳过空描述
            if not description or len(description) < 10:
                continue
            
            # 提取日期
            year = row.get("c7", "").strip()
            month = row.get("c8", "").strip()
            day = row.get("c9", "").strip()
            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""
            
            record = {
                "record_id": record_id,
                "description": description,
                "aircraft_model": row.get("c24", "").strip(),
                "manufacturer": row.get("c23", "").strip(),
                "accident_type": row.get("c78", "").strip(),
                "date": date_str,
                "year": year,
                "state": row.get("c33", "").strip(),
                "city": row.get("c34", "").strip(),
                "airport": row.get("c147", "").strip(),
                "source": "faa"
            }
            records.append(record)
    
    # 写入CSV
    if records:
        fieldnames = ["record_id", "description", "aircraft_model", "manufacturer", 
                      "accident_type", "date", "year", "state", "city", "airport", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"[FAA] Saved {len(records)} records to {output_file}")
    
    return records


def process_maintnet_data():
    """
    处理 MaintNet 飞机维修数据
    提取字段: record_id, problem, action, aircraft_type, manufacturer
    """
    input_file = os.path.join(RAW_DIR, "OMIn_dataset", "data", "MaintNet_data", "Aircraft_Annotation_DataFile.csv")
    output_file = os.path.join(MAINTNET_DIR, "maintnet_records.csv")
    
    print("[MaintNet] Processing MaintNet aircraft maintenance data...")
    
    records = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = row.get("IDENT", "").strip()
            problem = row.get("PROBLEM", "").strip()
            action = row.get("ACTION", "").strip()
            
            if not problem:
                continue
            
            record = {
                "record_id": f"MN_{record_id}",
                "problem": problem,
                "action": action,
                "aircraft_model": "",  # MaintNet没有直接提供
                "manufacturer": "",
                "source": "maintnet"
            }
            records.append(record)
    
    # 写入CSV
    if records:
        fieldnames = ["record_id", "problem", "action", "aircraft_model", "manufacturer", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"[MaintNet] Saved {len(records)} records to {output_file}")
    
    return records


def process_maintnet_abbreviations():
    """
    处理 MaintNet 航空缩写数据
    提取字段: code, abbreviation, full_description
    """
    input_file = os.path.join(RAW_DIR, "OMIn_dataset", "data", "MaintNet_data", "Aviation_Abbreviation_Dataset.csv")
    output_file = os.path.join(MAINTNET_DIR, "aviation_abbreviations.csv")
    
    print("[MaintNet] Processing aviation abbreviations...")
    
    records = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("Abbriviation_Code", "").strip()
            abbr = row.get("Abbreviated", "").strip()
            desc = row.get("Standard_Description", "").strip()
            
            if not abbr:
                continue
            
            records.append({
                "code": code,
                "abbreviation": abbr.upper(),
                "full_description": desc,
                "source": "maintnet_abbreviation"
            })
    
    # 写入CSV
    if records:
        fieldnames = ["code", "abbreviation", "full_description", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"[MaintNet] Saved {len(records)} abbreviations to {output_file}")
    
    return records


def process_maintnet_grammar():
    """
    处理 MaintNet 航空语法数据
    提取字段: word, description, compound, lemma, stem, pos
    """
    input_file = os.path.join(RAW_DIR, "OMIn_dataset", "data", "MaintNet_data", "Aviation_grammar_Dataset.csv")
    output_file = os.path.join(MAINTNET_DIR, "aviation_grammar.csv")
    
    print("[MaintNet] Processing aviation grammar...")
    
    records = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row.get("Word", "").strip()
            desc = row.get("Description", "").strip()
            compound = row.get("Compound", "").strip()
            lemma = row.get("Lemma", "").strip()
            stem = row.get("Stem", "").strip()
            pos = row.get("Part of Speech (POS)", "").strip()
            
            if not word:
                continue
            
            records.append({
                "word": word,
                "description": desc,
                "compound": compound,
                "lemma": lemma,
                "stem": stem,
                "pos": pos,
                "source": "maintnet_grammar"
            })
    
    # 写入CSV
    if records:
        fieldnames = ["word", "description", "compound", "lemma", "stem", "pos", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"[MaintNet] Saved {len(records)} grammar entries to {output_file}")
    
    return records


def process_maintnet_terms():
    """
    处理 MaintNet 航空术语库
    提取字段: word, example
    """
    input_file = os.path.join(RAW_DIR, "OMIn_dataset", "data", "MaintNet_data", "Aviation_TermBanks_Dataset.csv")
    output_file = os.path.join(MAINTNET_DIR, "aviation_terms.csv")
    
    print("[MaintNet] Processing aviation term banks...")
    
    records = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row.get("Word", "").strip()
            example = row.get("Example", "").strip()
            
            if not word:
                continue
            
            records.append({
                "word": word,
                "example": example,
                "source": "maintnet_terms"
            })
    
    # 写入CSV
    if records:
        fieldnames = ["word", "example", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"[MaintNet] Saved {len(records)} terms to {output_file}")
    
    return records


def process_rebel_relations():
    """
    处理 REBEL 关系抽取结果
    提取字段: source_id, head, relation, tail, context
    """
    input_file = os.path.join(RAW_DIR, "tool_results", "rebel", "rebel_results_spacy_pipe.csv")
    output_file = os.path.join(RELATIONS_DIR, "rebel_relations.csv")
    
    print("[REBEL] Processing REBEL relation extraction results...")
    
    relations = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = row.get("index", "").strip()
            head = row.get("head", "").strip()
            relation = row.get("relation", "").strip()
            tail = row.get("tail", "").strip()
            context = row.get("input", "").strip()[:200]  # 截断过长的上下文
            
            if not head or not relation or not tail:
                continue
            
            rel = {
                "relation_id": f"REL_{idx}",
                "head": head,
                "relation": relation,
                "tail": tail,
                "context": context,
                "source": "rebel"
            }
            relations.append(rel)
    
    # 写入CSV
    if relations:
        fieldnames = ["relation_id", "head", "relation", "tail", "context", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(relations)
        
        print(f"[REBEL] Saved {len(relations)} relations to {output_file}")
    
    return relations


def process_ner_entities():
    """
    处理 NER 实体识别结果
    从 spaCy large 模型结果中提取实体
    """
    input_file = os.path.join(RAW_DIR, "tool_results", "spacy_entityrecognizer", "spacy_ner_lg.csv")
    output_file = os.path.join(FAA_DIR, "faa_entities.csv")
    
    print("[NER] Processing spaCy NER results...")
    
    entities = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = row.get("c5_id", "").strip()
            text = row.get("c119_input", "").strip()
            ents_str = row.get("entities", "").strip()
            labels_str = row.get("labels", "").strip()
            
            if not ents_str:
                continue
            
            # 解析实体列表（可能是Python列表格式）
            try:
                ents = eval(ents_str) if ents_str.startswith("[") else ents_str.split(",")
                labels = eval(labels_str) if labels_str.startswith("[") else labels_str.split(",")
            except:
                continue
            
            for i, (ent, label) in enumerate(zip(ents, labels)):
                ent = ent.strip().strip("'\"")
                label = label.strip().strip("'\"")
                if ent and len(ent) > 1:
                    entities.append({
                        "entity_id": f"ENT_{record_id}_{i}",
                        "record_id": record_id,
                        "entity_text": ent,
                        "entity_type": label,
                        "source": "spacy_ner"
                    })
    
    # 写入CSV
    if entities:
        fieldnames = ["entity_id", "record_id", "entity_text", "entity_type", "source"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entities)
        
        print(f"[NER] Saved {len(entities)} entities to {output_file}")
    
    return entities


def create_import_config():
    """创建导入配置文件，供后续导入脚本使用"""
    config = {
        "dataset_name": "OMIn Aviation Maintenance",
        "description": "Operations and Maintenance Intelligence Dataset - Aviation domain",
        "sources": {
            "faa": {
                "file": "faa/faa_records.csv",
                "type": "maintenance_records",
                "description": "FAA Accident/Incident Data - maintenance related records"
            },
            "maintnet": {
                "file": "maintnet/maintnet_records.csv", 
                "type": "maintenance_records",
                "description": "MaintNet Aircraft Maintenance Data"
            },
            "abbreviations": {
                "file": "maintnet/aviation_abbreviations.csv",
                "type": "reference_data",
                "description": "Aviation abbreviations (e.g., ACFT=Aircraft)"
            },
            "grammar": {
                "file": "maintnet/aviation_grammar.csv",
                "type": "reference_data",
                "description": "Aviation grammar with POS tags"
            },
            "terms": {
                "file": "maintnet/aviation_terms.csv",
                "type": "reference_data",
                "description": "Aviation terminology with examples"
            },
            "relations": {
                "file": "relations/rebel_relations.csv",
                "type": "knowledge_relations",
                "description": "REBEL extracted relations (head, relation, tail)"
            },
            "entities": {
                "file": "faa/faa_entities.csv",
                "type": "named_entities",
                "description": "spaCy NER extracted entities"
            }
        },
        "neo4j_schema": {
            "node_types": [
                {"label": "Aircraft", "key": "aircraft_model", "description": "飞机型号"},
                {"label": "Manufacturer", "key": "manufacturer", "description": "制造商"},
                {"label": "IncidentType", "key": "accident_type", "description": "事故类型"},
                {"label": "Location", "key": "state", "description": "地点"},
                {"label": "Entity", "key": "entity_text", "description": "NER识别的实体"},
                {"label": "Record", "key": "record_id", "description": "维修记录"},
                {"label": "Term", "key": "word", "description": "航空术语"},
                {"label": "Abbreviation", "key": "abbreviation", "description": "航空缩写"}
            ],
            "relation_types": [
                {"type": "HAS_FAULT", "from": "Record", "to": "IncidentType"},
                {"type": "INVOLVES_AIRCRAFT", "from": "Record", "to": "Aircraft"},
                {"type": "MANUFACTURED_BY", "from": "Aircraft", "to": "Manufacturer"},
                {"type": "OCCURRED_IN", "from": "Record", "to": "Location"},
                {"type": "HAS_ENTITY", "from": "Record", "to": "Entity"},
                {"type": "RELATED_TO", "from": "Entity", "to": "Entity", "description": "REBEL抽取的关系"},
                {"type": "HAS_EXAMPLE", "from": "Term", "to": "Record", "description": "术语在记录中的示例"}
            ]
        },
        "qdrant_config": {
            "collection_name": "rag_knowledge_base",
            "vector_size": 384,
            "distance": "cosine",
            "text_fields": ["description", "problem", "action", "example"]
        }
    }
    
    config_file = os.path.join(BASE_DIR, "import_config.json")
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"[Config] Saved import config to {config_file}")
    return config


def main():
    print("=" * 60)
    print("OMIn Dataset Processing")
    print("=" * 60)
    
    ensure_dirs()
    
    # 处理各类数据
    faa_records = process_faa_data()
    maintnet_records = process_maintnet_data()
    abbreviations = process_maintnet_abbreviations()
    grammar = process_maintnet_grammar()
    terms = process_maintnet_terms()
    relations = process_rebel_relations()
    entities = process_ner_entities()
    
    # 创建导入配置
    config = create_import_config()
    
    # 汇总统计
    print("\n" + "=" * 60)
    print("Processing Summary")
    print("=" * 60)
    print(f"  FAA Records:           {len(faa_records)}")
    print(f"  MaintNet Records:      {len(maintnet_records)}")
    print(f"  Aviation Abbreviations:{len(abbreviations)}")
    print(f"  Aviation Grammar:      {len(grammar)}")
    print(f"  Aviation Terms:        {len(terms)}")
    print(f"  Relations:             {len(relations)}")
    print(f"  Entities:              {len(entities)}")
    print(f"  Total Knowledge Items: {len(faa_records) + len(maintnet_records) + len(abbreviations) + len(grammar) + len(terms)}")
    print("=" * 60)
    print("\nData saved to: ", BASE_DIR)
    print("Next step: Run import script to load into Qdrant + Neo4j")


if __name__ == "__main__":
    main()
