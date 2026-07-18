# -*- coding: utf-8 -*-
"""
QA 知识对导入脚本
将 missile guidance / control / simulation 等领域的 QA 对导入 Qdrant + Neo4j

用法:
    python scripts/import_qa_pairs.py --sample 10   # 先导入10条测试
    python scripts/import_qa_pairs.py --all          # 全量导入200条
"""

import os
import sys
import json
import time
import argparse

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "libs"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from neo4j import GraphDatabase

DATASET_FILE = os.path.join(os.path.dirname(__file__), "dataset", "qa_pair.json")
QDRANT_COLLECTION = "aviation_knowledge_base"
VECTOR_SIZE = 384


def load_qa_data(limit=None):
    path = DATASET_FILE
    if not os.path.exists(path):
        print(f" 数据文件不存在: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pairs = []
    for chapter in data.get("chapters", []):
        chapter_no = chapter["chapter_no"]
        chapter_name = chapter["chapter_name"]
        for qa in chapter.get("qa", []):
            if limit and len(pairs) >= limit:
                return pairs
            pairs.append({
                "qa_no": qa["qa_no"],
                "question": qa["question"],
                "answer": qa["answer"],
                "chapter_no": chapter_no,
                "chapter_name": chapter_name,
            })
    return pairs


def init_embedder():
    from hello_agents.memory.embedding import get_text_embedder
    print("[Embedding] Loading model...")
    t0 = time.time()
    embedder = get_text_embedder()
    print(f"[Embedding] Loaded in {time.time() - t0:.1f}s, dim={embedder.dimension}")
    return embedder


def init_qdrant(client):
    collections = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[Qdrant] Created collection: {QDRANT_COLLECTION}")
    else:
        print(f"[Qdrant] Collection '{QDRANT_COLLECTION}' exists, appending")


def init_neo4j(driver):
    with driver.session() as session:
        constraints = [
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (ch:QAChapter) REQUIRE ch.chapter_no IS UNIQUE", "QAChapter.chapter_no"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (q:QAPair) REQUIRE q.qa_no IS UNIQUE", "QAPair.qa_no"),
        ]
        for cypher, label in constraints:
            try:
                session.run(cypher)
                print(f"[Neo4j] Constraint: {label}")
            except Exception as e:
                print(f"[Neo4j] Constraint {label} skipped: {e}")


def import_to_qdrant(client, embedder, pairs):
    print(f"\n[Qdrant] Importing {len(pairs)} QA pairs...")
    points = []
    base_id = int(time.time() * 1000)
    for i, qa in enumerate(pairs):
        content = f"[{qa['chapter_name']}] Q: {qa['question']}\nA: {qa['answer']}"
        vector = embedder.encode(content).tolist()
        points.append(PointStruct(
            id=base_id + i,
            vector=vector,
            payload={
                "source": "qa_pair",
                "record_id": qa["qa_no"],
                "content": content,
                "text": content,
                "question": qa["question"],
                "answer": qa["answer"],
                "chapter_no": qa["chapter_no"],
                "chapter_name": qa["chapter_name"],
                "memory_type": "rag_chunk",
                "memory_id": f"qa_{qa['qa_no']}",
                "user_id": "rag_user",
                "is_rag_data": True,
                "data_source": "rag_pipeline",
                "rag_namespace": "default",
            }
        ))

    batch_size = 50
    for j in range(0, len(points), batch_size):
        batch = points[j:j + batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
        print(f"  Batch {j // batch_size + 1}: {len(batch)} points")

    print(f"[Qdrant] Done: {len(points)} points")
    return len(points)


def import_to_neo4j(driver, pairs):
    print(f"\n[Neo4j] Importing {len(pairs)} QA pairs...")
    chapters_seen = set()
    chapter_count = 0
    qa_count = 0

    with driver.session() as session:
        for qa in pairs:
            ch_no = qa["chapter_no"]
            if ch_no not in chapters_seen:
                chapters_seen.add(ch_no)
                session.run(
                    "MERGE (ch:QAChapter {chapter_no: $chapter_no}) "
                    "SET ch.chapter_name = $chapter_name",
                    chapter_no=ch_no, chapter_name=qa["chapter_name"]
                )
                chapter_count += 1

            session.run(
                "MERGE (q:QAPair {qa_no: $qa_no}) "
                "SET q.question = $question, "
                "    q.answer = $answer, "
                "    q.chapter_no = $chapter_no, "
                "    q.chapter_name = $chapter_name "
                "WITH q "
                "MATCH (ch:QAChapter {chapter_no: $chapter_no}) "
                "MERGE (q)-[:BELONGS_TO]->(ch)",
                qa_no=qa["qa_no"],
                question=qa["question"],
                answer=qa["answer"],
                chapter_no=qa["chapter_no"],
                chapter_name=qa["chapter_name"],
            )
            qa_count += 1

    print(f"[Neo4j] Done: {chapter_count} chapters, {qa_count} QAs")


def main():
    parser = argparse.ArgumentParser(description="Import QA pairs to Qdrant + Neo4j")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Import all QA pairs")
    group.add_argument("--sample", type=int, metavar="N", help="Import first N QA pairs")

    args = parser.parse_args()
    limit = None if args.all else args.sample

    pairs = load_qa_data(limit=limit)
    if not pairs:
        print("No QA data to import.")
        return

    print(f"\n{'=' * 60}")
    print(f"QA Knowledge Import")
    print(f"{'=' * 60}")
    print(f"  Total QA pairs to import: {len(pairs)}")
    print(f"{'=' * 60}")

    embedder = init_embedder()

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
    qdrant = QdrantClient(url=qdrant_url, trust_env=not is_local)
    init_qdrant(qdrant)

    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
    )
    try:
        init_neo4j(neo4j_driver)

        t0 = time.time()
        n_qdrant = import_to_qdrant(qdrant, embedder, pairs)
        n_neo4j = import_to_neo4j(neo4j_driver, pairs)
        t1 = time.time()

        print(f"\n{'=' * 60}")
        print(f"Import Complete")
        print(f"{'=' * 60}")
        print(f"  Qdrant: {n_qdrant} vectors")
        print(f"  Neo4j:  {n_neo4j} QA pairs + {len(set(p['chapter_no'] for p in pairs))} chapters")
        print(f"  Time:   {t1 - t0:.1f}s")
        print(f"{'=' * 60}")
    finally:
        neo4j_driver.close()


if __name__ == "__main__":
    main()
