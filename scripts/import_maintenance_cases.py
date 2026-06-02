# -*- coding: utf-8 -*-
"""
批量导入维护案例
从 JSON 文件读取维护案例数据，导入到 SQLite 和 Qdrant
"""

import os
import sys
import json
import time
import sqlite3
import argparse

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

# 数据文件路径
DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")
CASES_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "repair_agent", "memory_data", "cases.db")


def load_json_data(filename: str) -> list:
    """从 JSON 文件加载数据"""
    filepath = os.path.join(DATASET_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"✗ 数据文件不存在: {filepath}")
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 支持两种格式：直接数组 或 { "cases": [...] }
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "cases" in data:
            return data["cases"]
        else:
            print(f"✗ JSON 格式错误，应为数组或包含 'cases' 键的对象")
            return []
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        return []


def init_cases_db():
    """初始化案例数据库（确保表结构存在）"""
    os.makedirs(os.path.dirname(CASES_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CASES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT DEFAULT 'maintenance',
            title TEXT NOT NULL,
            device_type TEXT,
            fault_symptom TEXT,
            fault_cause TEXT,
            solution TEXT,
            parts_used TEXT,
            technician TEXT,
            notes TEXT,
            case_text TEXT,
            maintenance_type TEXT,
            maintenance_cycle TEXT,
            maintenance_standard TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 检查是否需要升级旧表结构
    cursor.execute("PRAGMA table_info(cases)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'case_type' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN case_type TEXT DEFAULT 'maintenance'")
    if 'maintenance_type' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_type TEXT")
    if 'maintenance_cycle' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_cycle TEXT")
    if 'maintenance_standard' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_standard TEXT")
    
    conn.commit()
    conn.close()


def save_case_to_db(case_data: dict) -> int:
    """保存案例到数据库"""
    conn = sqlite3.connect(CASES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cases (case_type, title, device_type, solution, parts_used, technician, notes, case_text, maintenance_type, maintenance_cycle, maintenance_standard)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        "maintenance",
        case_data.get("title", ""),
        case_data.get("device_type", ""),
        case_data.get("solution", ""),
        case_data.get("parts_used", ""),
        case_data.get("technician", ""),
        case_data.get("notes", ""),
        case_data.get("case_text", ""),
        case_data.get("maintenance_type", ""),
        case_data.get("maintenance_cycle", ""),
        case_data.get("maintenance_standard", "")
    ))
    case_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return case_id


def sync_to_qdrant(case_id: int, case_data: dict):
    """同步案例到 Qdrant 向量库"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        from hello_agents.memory.embedding import get_text_embedder
        
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
        client = QdrantClient(url=qdrant_url, trust_env=not is_local)
        embedder = get_text_embedder()
        
        # 构建可检索的文本
        search_text = f"{case_data['title']} | 设备: {case_data.get('device_type', '')} | 维护类型: {case_data.get('maintenance_type', '')} | 周期: {case_data.get('maintenance_cycle', '')} | 方案: {case_data.get('solution', '')}"
        vector = embedder.encode(search_text).tolist()
        
        # 检查集合是否存在
        collections = [c.name for c in client.get_collections().collections]
        if "aviation_knowledge_base" in collections:
            # 使用时间戳+ID作为唯一ID
            point_id = int(time.time() * 1000000) + case_id + 100000  # 偏移避免与维修案例冲突
            
            client.upsert(
                collection_name="aviation_knowledge_base",
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "source": "user_case",
                        "case_type": "maintenance",
                        "record_id": f"CASE_{case_id}",
                        "content": search_text,
                        "text": search_text,
                        "aircraft_model": case_data.get("device_type", ""),
                        "description": case_data.get("maintenance_type", ""),
                        "problem": case_data.get("maintenance_cycle", ""),
                        "action": case_data.get("solution", ""),
                        "memory_type": "rag_chunk",
                        "memory_id": f"case_{case_id}",
                        "user_id": "rag_user",
                        "is_rag_data": True,
                        "data_source": "rag_pipeline",
                        "rag_namespace": "default"
                    }
                )]
            )
            return True
    except Exception as e:
        print(f"  ⚠️ 同步到 Qdrant 失败: {e}")
    return False


def import_cases(data_file: str = "maintenance_cases.json", dry_run: bool = False):
    """批量导入维护案例"""
    print("=" * 60)
    print("批量导入维护案例")
    print("=" * 60)
    
    # 加载数据
    cases = load_json_data(data_file)
    if not cases:
        print("没有找到可导入的数据")
        return
    
    print(f"找到 {len(cases)} 条维护案例")
    
    if dry_run:
        print("\n[试运行模式] 以下案例将被导入：")
        for i, case in enumerate(cases, 1):
            print(f"  {i}. {case.get('title', '无标题')} - {case.get('device_type', '未知设备')} [{case.get('maintenance_type', '未知类型')}]")
        return
    
    # 初始化数据库
    init_cases_db()
    
    # 导入案例
    success_count = 0
    fail_count = 0
    
    for i, case in enumerate(cases, 1):
        title = case.get("title", "").strip()
        if not title:
            print(f"  [{i}/{len(cases)}] ✗ 跳过：缺少标题")
            fail_count += 1
            continue
        
        try:
            # 保存到 SQLite
            case_id = save_case_to_db(case)
            
            # 同步到 Qdrant
            qdrant_ok = sync_to_qdrant(case_id, case)
            
            qdrant_status = "✓ Qdrant" if qdrant_ok else "⚠ Qdrant跳过"
            print(f"  [{i}/{len(cases)}] ✓ {title} (ID: {case_id}, {qdrant_status})")
            success_count += 1
            
        except Exception as e:
            print(f"  [{i}/{len(cases)}] ✗ {title}: {e}")
            fail_count += 1
        
        # 短暂延迟，避免 Qdrant ID 冲突
        time.sleep(0.01)
    
    print("\n" + "=" * 60)
    print(f"导入完成: 成功 {success_count} 条, 失败 {fail_count} 条")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="批量导入维护案例")
    parser.add_argument("--file", default="maintenance_cases.json", help="数据文件名（默认: maintenance_cases.json）")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不实际导入")
    args = parser.parse_args()
    
    import_cases(data_file=args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
