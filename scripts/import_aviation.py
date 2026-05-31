# -*- coding: utf-8 -*-
"""
航空维修数据集导入脚本
将 OMIn 数据导入 Qdrant（向量检索）和 Neo4j（知识图谱）

用法:
    python scripts/import_aviation.py --sample 10   # 先导入10条测试
    python scripts/import_aviation.py --all          # 全量导入
"""

import os
import sys
import csv
import time
import argparse

# 添加 libs 目录到路径（使用本地修改版 hello_agents）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "libs"))

# 加载 .env
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Windows UTF-8 兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from neo4j import GraphDatabase

# 配置
DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "repair_agent", "dataset", "processed_data", "omin")
QDRANT_COLLECTION = "aviation_knowledge_base"  # 新集合名
VECTOR_SIZE = 384


def read_csv(filename, limit=None):
    """读取 CSV 文件"""
    path = os.path.join(DATASET_DIR, filename)
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            rows.append(row)
    return rows


def init_embedding():
    """初始化 embedding 模型"""
    from hello_agents.memory.embedding import get_text_embedder
    print("[Embedding] Loading model...")
    t0 = time.time()
    embedder = get_text_embedder()
    t1 = time.time()
    print(f"[Embedding] Loaded in {t1-t0:.1f}s, dim={embedder.dimension}")
    return embedder


def init_qdrant(client):
    """创建新的 Qdrant 集合"""
    collections = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in collections:
        print(f"[Qdrant] Collection '{QDRANT_COLLECTION}' already exists, keeping it")
    else:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[Qdrant] Created collection: {QDRANT_COLLECTION}")


def init_neo4j(driver):
    """初始化 Neo4j（创建约束，不清空数据）"""
    with driver.session() as session:
        # 创建航空领域的约束
        constraints = [
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (a:AircraftModel) REQUIRE a.name IS UNIQUE", "AircraftModel.name"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Manufacturer) REQUIRE m.name IS UNIQUE", "Manufacturer.name"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (t:IncidentType) REQUIRE t.name IS UNIQUE", "IncidentType.name"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE", "Location.name"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (r:AviationRecord) REQUIRE r.record_id IS UNIQUE", "AviationRecord.record_id"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (t:AviationTerm) REQUIRE t.word IS UNIQUE", "AviationTerm.word"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (a:AviationAbbr) REQUIRE a.abbreviation IS UNIQUE", "AviationAbbr.abbreviation"),
        ]
        for cypher, label in constraints:
            try:
                session.run(cypher)
                print(f"[Neo4j] Constraint: {label}")
            except Exception as e:
                print(f"[Neo4j] Constraint {label} skipped: {e}")


def build_text_for_embedding(row, source):
    """构建用于 embedding 的文本（优先用中文）"""
    parts = []
    
    if source == "faa":
        desc_zh = row.get("description_zh", "")
        desc_en = row.get("description", "")
        desc = desc_zh if desc_zh else desc_en
        if desc:
            parts.append(desc)
        if row.get("aircraft_model"):
            parts.append(f"飞机型号: {row['aircraft_model']}")
        if row.get("manufacturer"):
            parts.append(f"制造商: {row['manufacturer']}")
    
    elif source == "maintnet":
        problem_zh = row.get("problem_zh", "")
        problem_en = row.get("problem", "")
        problem = problem_zh if problem_zh else problem_en
        if problem:
            parts.append(f"问题: {problem}")
        
        action_zh = row.get("action_zh", "")
        action_en = row.get("action", "")
        action = action_zh if action_zh else action_en
        if action:
            parts.append(f"操作: {action}")
    
    return " | ".join(parts) if parts else f"航空维修记录 ({source})"


def import_faa_to_qdrant(client, model, rows, start_id):
    """导入 FAA 数据到 Qdrant"""
    points = []
    for i, row in enumerate(rows):
        text = build_text_for_embedding(row, "faa")
        vector = model.encode(text).tolist()
        
        point = PointStruct(
            id=start_id + i,
            vector=vector,
            payload={
                "source": "faa",
                "record_id": row.get("record_id", ""),
                "description": row.get("description", ""),
                "description_zh": row.get("description_zh", ""),
                "aircraft_model": row.get("aircraft_model", ""),
                "manufacturer": row.get("manufacturer", ""),
                "accident_type": row.get("accident_type", ""),
                "date": row.get("date", ""),
                "state": row.get("state", ""),
                "text": text
            }
        )
        points.append(point)
    
    # 批量写入
    batch_size = 50
    for j in range(0, len(points), batch_size):
        batch = points[j:j+batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
    
    return len(points)


def import_maintnet_to_qdrant(client, model, rows, start_id):
    """导入 MaintNet 数据到 Qdrant"""
    points = []
    for i, row in enumerate(rows):
        text = build_text_for_embedding(row, "maintnet")
        vector = model.encode(text).tolist()
        
        point = PointStruct(
            id=start_id + i,
            vector=vector,
            payload={
                "source": "maintnet",
                "record_id": row.get("record_id", ""),
                "problem": row.get("problem", ""),
                "problem_zh": row.get("problem_zh", ""),
                "action": row.get("action", ""),
                "action_zh": row.get("action_zh", ""),
                "text": text
            }
        )
        points.append(point)
    
    # 批量写入
    batch_size = 50
    for j in range(0, len(points), batch_size):
        batch = points[j:j+batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
    
    return len(points)


def import_faa_to_neo4j(driver, rows):
    """导入 FAA 数据到 Neo4j"""
    count = 0
    with driver.session() as session:
        for row in rows:
            record_id = row.get("record_id", "")
            if not record_id:
                continue
            
            desc = row.get("description", "")
            desc_zh = row.get("description_zh", "")
            aircraft = row.get("aircraft_model", "").strip()
            manufacturer = row.get("manufacturer", "").strip()
            incident_type = row.get("accident_type", "").strip()
            state = row.get("state", "").strip()
            date = row.get("date", "").strip()
            
            cypher = """
            MERGE (r:AviationRecord {record_id: $record_id})
            SET r.description = $desc,
                r.description_zh = $desc_zh,
                r.date = $date,
                r.source = 'faa'
            
            WITH r
            WHERE $aircraft <> ''
            MERGE (a:AircraftModel {name: $aircraft})
            MERGE (r)-[:INVOLVES_AIRCRAFT]->(a)
            
            WITH r, a
            WHERE $manufacturer <> ''
            MERGE (m:Manufacturer {name: $manufacturer})
            MERGE (a)-[:MANUFACTURED_BY]->(m)
            
            WITH r
            WHERE $incident_type <> ''
            MERGE (t:IncidentType {name: $incident_type})
            MERGE (r)-[:HAS_INCIDENT_TYPE]->(t)
            
            WITH r
            WHERE $state <> ''
            MERGE (l:Location {name: $state})
            MERGE (r)-[:OCCURRED_IN]->(l)
            """
            try:
                session.run(cypher,
                    record_id=record_id,
                    desc=desc[:500],
                    desc_zh=desc_zh[:500] if desc_zh else "",
                    aircraft=aircraft,
                    manufacturer=manufacturer,
                    incident_type=incident_type,
                    state=state,
                    date=date
                )
                count += 1
            except Exception as e:
                print(f"  [Neo4j Error] {record_id}: {e}")
    
    return count


def import_maintnet_to_neo4j(driver, rows):
    """导入 MaintNet 数据到 Neo4j"""
    count = 0
    with driver.session() as session:
        for row in rows:
            record_id = row.get("record_id", "")
            if not record_id:
                continue
            
            problem = row.get("problem", "")
            problem_zh = row.get("problem_zh", "")
            action = row.get("action", "")
            action_zh = row.get("action_zh", "")
            
            cypher = """
            MERGE (r:AviationRecord {record_id: $record_id})
            SET r.problem = $problem,
                r.problem_zh = $problem_zh,
                r.action = $action,
                r.action_zh = $action_zh,
                r.source = 'maintnet'
            """
            try:
                session.run(cypher,
                    record_id=record_id,
                    problem=problem[:500],
                    problem_zh=problem_zh[:500] if problem_zh else "",
                    action=action[:500],
                    action_zh=action_zh[:500] if action_zh else ""
                )
                count += 1
            except Exception as e:
                print(f"  [Neo4j Error] {record_id}: {e}")
    
    return count


def import_terms_to_neo4j(driver):
    """导入术语和缩写到 Neo4j"""
    # 导入术语
    terms_file = os.path.join(DATASET_DIR, "maintnet", "aviation_terms.csv")
    terms_zh_file = os.path.join(DATASET_DIR, "maintnet", "aviation_terms_zh.csv")
    
    terms = []
    if os.path.exists(terms_zh_file):
        terms = read_csv("maintnet/aviation_terms_zh.csv")
    elif os.path.exists(terms_file):
        terms = read_csv("maintnet/aviation_terms.csv")
    
    count = 0
    with driver.session() as session:
        for row in terms:
            word = row.get("word", "")
            example = row.get("example", "")
            example_zh = row.get("example_zh", "")
            
            if not word:
                continue
            
            cypher = """
            MERGE (t:AviationTerm {word: $word})
            SET t.example = $example,
                t.example_zh = $example_zh
            """
            try:
                session.run(cypher, word=word, example=example, example_zh=example_zh or "")
                count += 1
            except Exception as e:
                print(f"  [Neo4j Error] Term {word}: {e}")
    
    # 导入缩写
    abbr_file = os.path.join(DATASET_DIR, "maintnet", "aviation_abbreviations.csv")
    if os.path.exists(abbr_file):
        abbrs = read_csv("maintnet/aviation_abbreviations.csv")
        with driver.session() as session:
            for row in abbrs:
                abbr = row.get("abbreviation", "")
                desc = row.get("full_description", "")
                
                if not abbr:
                    continue
                
                cypher = """
                MERGE (a:AviationAbbr {abbreviation: $abbreviation})
                SET a.full_description = $description
                """
                try:
                    session.run(cypher, abbreviation=abbr, description=desc)
                    count += 1
                except Exception as e:
                    print(f"  [Neo4j Error] Abbr {abbr}: {e}")
    
    return count


def test_qdrant_search(client, model, query, top_k=3):
    """测试 Qdrant 搜索"""
    vector = model.encode(query).tolist()
    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
    ).points
    
    print(f"\n{'='*60}")
    print(f"Qdrant 查询: \"{query}\"")
    print(f"{'='*60}")
    for i, r in enumerate(results, 1):
        p = r.payload
        print(f"\n  [{i}] score={r.score:.4f}")
        print(f"      来源: {p.get('source', '?')}")
        if p.get('description_zh'):
            print(f"      描述: {p['description_zh'][:100]}...")
        elif p.get('problem_zh'):
            print(f"      问题: {p['problem_zh'][:100]}...")


def test_neo4j_query(driver):
    """测试 Neo4j 查询"""
    print(f"\n{'='*60}")
    print("Neo4j 图谱统计 (航空领域)")
    print(f"{'='*60}")
    
    with driver.session() as session:
        for label in ["AviationRecord", "AircraftModel", "Manufacturer", "IncidentType", "Location", "AviationTerm", "AviationAbbr"]:
            cnt = session.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
            print(f"  {label}: {cnt} 个节点")
        
        for rel in ["INVOLVES_AIRCRAFT", "MANUFACTURED_BY", "HAS_INCIDENT_TYPE", "OCCURRED_IN"]:
            cnt = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) as c").single()["c"]
            print(f"  {rel}: {cnt} 条关系")


def main():
    parser = argparse.ArgumentParser(description="Import aviation dataset")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", type=int, help="Import N records per file")
    group.add_argument("--all", action="store_true", help="Import all records")
    args = parser.parse_args()
    
    limit = args.sample if args.sample else None
    
    print("=" * 60)
    print("航空维修数据导入")
    print("=" * 60)
    
    # 初始化
    model = init_embedding()
    
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    init_qdrant(qdrant)
    
    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
    )
    init_neo4j(neo4j_driver)
    
    # 检查是否有中文翻译文件
    faa_file = "faa/faa_records_zh.csv" if os.path.exists(os.path.join(DATASET_DIR, "faa/faa_records_zh.csv")) else "faa/faa_records.csv"
    maintnet_file = "maintnet/maintnet_records_zh.csv" if os.path.exists(os.path.join(DATASET_DIR, "maintnet/maintnet_records_zh.csv")) else "maintnet/maintnet_records.csv"
    
    print(f"\n[数据源]")
    print(f"  FAA: {faa_file}")
    print(f"  MaintNet: {maintnet_file}")
    
    # 导入 FAA
    faa_rows = read_csv(faa_file, limit=limit)
    print(f"\n[FAA] {len(faa_rows)} records")
    
    n_q1 = import_faa_to_qdrant(qdrant, model, faa_rows, 0)
    print(f"  Qdrant: {n_q1} points")
    
    n_n1 = import_faa_to_neo4j(neo4j_driver, faa_rows)
    print(f"  Neo4j: {n_n1} records")
    
    # 导入 MaintNet
    maintnet_rows = read_csv(maintnet_file, limit=limit)
    print(f"\n[MaintNet] {len(maintnet_rows)} records")
    
    n_q2 = import_maintnet_to_qdrant(qdrant, model, maintnet_rows, n_q1)
    print(f"  Qdrant: {n_q2} points")
    
    n_n2 = import_maintnet_to_neo4j(neo4j_driver, maintnet_rows)
    print(f"  Neo4j: {n_n2} records")
    
    # 导入术语和缩写
    print(f"\n[术语和缩写]")
    n_terms = import_terms_to_neo4j(neo4j_driver)
    print(f"  Neo4j: {n_terms} terms/abbreviations")
    
    # 统计
    print(f"\n{'='*60}")
    print(f"导入完成")
    print(f"{'='*60}")
    print(f"  Qdrant 集合: {QDRANT_COLLECTION}")
    print(f"  Qdrant 总点数: {n_q1 + n_q2}")
    print(f"  Neo4j 记录数: {n_n1 + n_n2}")
    print(f"  Neo4j 术语数: {n_terms}")
    print(f"{'='*60}")
    
    # 测试查询
    test_qdrant_search(qdrant, model, "飞机发动机故障")
    test_qdrant_search(qdrant, model, "landing gear problem")
    test_neo4j_query(neo4j_driver)
    
    neo4j_driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
