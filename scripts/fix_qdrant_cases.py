# -*- coding: utf-8 -*-
"""
修复Qdrant中用户案例数据
清空旧的错误数据，从SQLite重新同步

用法:
    python scripts/fix_qdrant_cases.py
"""

import os
import sys
import sqlite3
import time

# 添加 libs 目录到路径
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
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct


# 配置
CASES_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "repair_agent", "memory_data", "cases.db")
QDRANT_COLLECTION = "aviation_knowledge_base"


def init_embedding():
    """初始化 embedding 模型"""
    from hello_agents.memory.embedding import get_text_embedder
    print("[Embedding] Loading model...")
    t0 = time.time()
    embedder = get_text_embedder()
    t1 = time.time()
    print(f"[Embedding] Loaded in {t1-t0:.1f}s, dim={embedder.dimension}")
    return embedder


def delete_user_cases_from_qdrant(client):
    """从Qdrant中删除所有用户案例数据"""
    print("\n[Qdrant] 删除用户案例数据...")
    
    # 查找所有用户案例
    f = Filter(must=[FieldCondition(key="source", match=MatchValue(value="user_case"))])
    
    # 获取所有用户案例的ID
    all_ids = []
    offset = None
    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=f,
            limit=100,
            with_payload=False,
            offset=offset
        )
        points = result[0]
        if not points:
            break
        all_ids.extend([p.id for p in points])
        offset = result[1]
        if offset is None:
            break
    
    if all_ids:
        print(f"  找到 {len(all_ids)} 条用户案例")
        # 批量删除
        batch_size = 100
        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i:i+batch_size]
            client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=batch
            )
            print(f"  已删除 {min(i+batch_size, len(all_ids))}/{len(all_ids)} 条")
        print(f"  ✅ 删除完成")
    else:
        print("  没有找到用户案例数据")


def load_cases_from_sqlite():
    """从SQLite加载所有案例"""
    print("\n[SQLite] 加载案例数据...")
    
    conn = sqlite3.connect(CASES_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM cases ORDER BY id')
    rows = cursor.fetchall()
    conn.close()
    
    print(f"  找到 {len(rows)} 条案例")
    return rows


def sync_cases_to_qdrant(client, embedder, cases):
    """将案例同步到Qdrant"""
    print(f"\n[Qdrant] 同步 {len(cases)} 条案例到 Qdrant...")
    
    points = []
    for i, row in enumerate(cases):
        case_id = row["id"]
        case_type = row["case_type"] if "case_type" in row.keys() else "repair"
        
        # 构建搜索文本
        if case_type == "maintenance":
            search_text = f"{row['title']} | 设备: {row['device_type']} | 维护类型: {row['maintenance_type'] if 'maintenance_type' in row.keys() else ''} | 方案: {row['solution']}"
        else:
            search_text = f"{row['title']} | 设备: {row['device_type']} | 故障: {row['fault_symptom'] or ''} | 原因: {row['fault_cause'] or ''} | 方案: {row['solution']}"
        
        # 生成向量
        vector = embedder.encode(search_text).tolist()
        
        # 构建payload
        point = PointStruct(
            id=int(time.time() * 1000000) + i,  # 使用时间戳+索引作为唯一ID
            vector=vector,
            payload={
                "source": "user_case",
                "case_type": case_type,
                "record_id": f"CASE_{case_id}",
                "content": search_text,
                "text": search_text,
                "aircraft_model": row["device_type"],
                "description": (row["fault_symptom"] if case_type == "repair" else (row["maintenance_type"] if "maintenance_type" in row.keys() else "")) or "",
                "problem": (row["fault_cause"] if case_type == "repair" else (row["maintenance_cycle"] if "maintenance_cycle" in row.keys() else "")) or "",
                "action": row["solution"] or "",
                "memory_type": "rag_chunk",
                "memory_id": f"case_{case_id}",
                "user_id": "rag_user",
                "is_rag_data": True,
                "data_source": "rag_pipeline",
                "rag_namespace": "default"
            }
        )
        points.append(point)
        
        # 每50条批量写入
        if len(points) >= 50:
            client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            print(f"  已同步 {i+1}/{len(cases)} 条")
            points = []
    
    # 写入剩余数据
    if points:
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    
    print(f"  ✅ 同步完成")


def verify_fix(client):
    """验证修复结果"""
    print("\n[验证] 检查CASE_51数据...")
    
    f = Filter(must=[FieldCondition(key="record_id", match=MatchValue(value="CASE_51"))])
    r = client.scroll(collection_name=QDRANT_COLLECTION, scroll_filter=f, limit=1, with_payload=True)
    
    if r[0]:
        p = r[0][0]
        desc = p.payload.get("description", "")
        prob = p.payload.get("problem", "")
        
        print(f"  description: {desc[:50]}...")
        print(f"  problem: {prob[:50]}...")
        
        if desc != prob:
            print("  ✅ description和problem不同，修复成功！")
        else:
            print("  ❌ description和problem仍然相同，修复失败！")
    else:
        print("  ⚠️ CASE_51未找到")


def main():
    print("=" * 60)
    print("修复Qdrant中用户案例数据")
    print("=" * 60)
    
    # 初始化
    embedder = init_embedding()
    
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
    client = QdrantClient(url=qdrant_url, trust_env=not is_local)
    
    # 步骤1: 删除Qdrant中的用户案例数据
    delete_user_cases_from_qdrant(client)
    
    # 步骤2: 从SQLite加载案例
    cases = load_cases_from_sqlite()
    
    # 步骤3: 重新同步到Qdrant
    sync_cases_to_qdrant(client, embedder, cases)
    
    # 步骤4: 验证修复结果
    verify_fix(client)
    
    print("\n" + "=" * 60)
    print("修复完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
