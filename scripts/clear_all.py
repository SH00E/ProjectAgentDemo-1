# -*- coding: utf-8 -*-
"""
彻底清空所有数据库
包括：Qdrant 向量库、Neo4j 图库、案例数据库、记忆数据库、QA知识库
只负责清空，不执行导入操作
"""

import os
import sys
import argparse
import sqlite3
import shutil

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
from neo4j import GraphDatabase


def clear_qdrant():
    """清空 Qdrant 中的所有集合"""
    print("\n" + "=" * 60)
    print("[1/4] 清空 Qdrant 向量数据库")
    print("=" * 60)
    
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
        client = QdrantClient(url=qdrant_url, trust_env=not is_local)
        
        # 获取所有集合
        collections = [c.name for c in client.get_collections().collections]
        print(f"当前集合: {collections}")
        
        if not collections:
            print("没有需要删除的集合")
            return
        
        # 删除所有集合
        for collection_name in collections:
            try:
                client.delete_collection(collection_name=collection_name)
                print(f"✓ 删除集合: {collection_name}")
            except Exception as e:
                print(f"✗ 删除集合 {collection_name} 失败: {e}")
        
        print("Qdrant 清空完成")
    except Exception as e:
        print(f"✗ Qdrant 连接失败: {e}")


def clear_neo4j():
    """清空 Neo4j 中的所有节点、关系、约束、索引"""
    print("\n" + "=" * 60)
    print("[2/4] 清空 Neo4j 图数据库")
    print("=" * 60)
    
    try:
        neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
        )
        
        with neo4j_driver.session() as session:
            # 先统计当前数据
            count_result = session.run("MATCH (n) RETURN count(n) as count").single()
            print(f"当前节点数量: {count_result['count']}")
            
            # 删除所有关系
            session.run("MATCH ()-[r]->() DELETE r")
            print("✓ 删除所有关系")
            
            # 删除所有节点
            session.run("MATCH (n) DELETE n")
            print("✓ 删除所有节点")
            
            # 删除所有约束
            try:
                constraints = session.run("SHOW CONSTRAINTS").data()
                for constraint in constraints:
                    constraint_name = constraint.get("name", "")
                    if constraint_name:
                        try:
                            session.run(f"DROP CONSTRAINT {constraint_name}")
                            print(f"✓ 删除约束: {constraint_name}")
                        except Exception as e:
                            print(f"- 跳过约束 {constraint_name}: {e}")
            except Exception as e:
                print(f"- 获取约束列表失败: {e}")
            
            # 删除所有索引
            try:
                indexes = session.run("SHOW INDEXES").data()
                for index in indexes:
                    index_name = index.get("name", "")
                    if index_name:
                        try:
                            session.run(f"DROP INDEX {index_name}")
                            print(f"✓ 删除索引: {index_name}")
                        except Exception as e:
                            print(f"- 跳过索引 {index_name}: {e}")
            except Exception as e:
                print(f"- 获取索引列表失败: {e}")
        
        neo4j_driver.close()
        print("Neo4j 清空完成")
    except Exception as e:
        print(f"✗ Neo4j 连接失败: {e}")


def clear_cases_db():
    """清空案例数据库"""
    print("\n" + "=" * 60)
    print("[3/4] 清空案例数据库")
    print("=" * 60)
    
    cases_db_path = os.path.join(
        os.path.dirname(__file__), "..", "repair_agent", "memory_data", "cases.db"
    )
    
    if not os.path.exists(cases_db_path):
        print(f"案例数据库不存在，跳过: {cases_db_path}")
        return
    
    try:
        conn = sqlite3.connect(cases_db_path)
        cursor = conn.cursor()
        
        # 统计当前记录数
        cursor.execute("SELECT COUNT(*) FROM cases")
        count = cursor.fetchone()[0]
        print(f"当前案例数量: {count}")
        
        # 删除所有案例
        cursor.execute("DELETE FROM cases")
        conn.commit()
        print(f"✓ 删除所有案例 ({count} 条)")
        
        # 重置自增ID
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='cases'")
            conn.commit()
            print("✓ 重置案例ID序列")
        except Exception:
            pass
        
        conn.close()
        print("案例数据库清空完成")
    except Exception as e:
        print(f"✗ 清空案例数据库失败: {e}")


def clear_memory_db():
    """清空记忆数据库"""
    print("\n" + "=" * 60)
    print("[4/4] 清空记忆数据库")
    print("=" * 60)
    
    # 两个可能的 memory.db 路径
    memory_db_paths = [
        os.path.join(os.path.dirname(__file__), "..", "memory_data", "memory.db"),
        os.path.join(os.path.dirname(__file__), "..", "repair_agent", "memory_data", "memory.db")
    ]
    
    for memory_db_path in memory_db_paths:
        memory_db_path = os.path.normpath(memory_db_path)
        
        if not os.path.exists(memory_db_path):
            print(f"记忆数据库不存在，跳过: {memory_db_path}")
            continue
        
        print(f"\n处理: {memory_db_path}")
        
        try:
            conn = sqlite3.connect(memory_db_path)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"  当前表: {tables}")
            
            # 删除所有表的数据
            for table in tables:
                if table == 'sqlite_sequence':
                    continue
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    cursor.execute(f"DELETE FROM {table}")
                    print(f"  ✓ 清空表 {table} ({count} 条)")
                except Exception as e:
                    print(f"  - 跳过表 {table}: {e}")
            
            # 重置自增ID
            try:
                cursor.execute("DELETE FROM sqlite_sequence")
                conn.commit()
                print("  ✓ 重置ID序列")
            except Exception:
                pass
            
            conn.close()
            print(f"  ✓ 记忆数据库清空完成")
        except Exception as e:
            print(f"  ✗ 清空记忆数据库失败: {e}")


def clear_qa():
    """仅清空 QA 知识库数据（Qdrant + Neo4j）"""
    print("\n" + "=" * 60)
    print("[5/5] 清空 QA 知识库")
    print("=" * 60)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url

    # Qdrant: 仅删除 source=qa_pair 的点
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = QdrantClient(url=qdrant_url, trust_env=not is_local)
        collections = [c.name for c in client.get_collections().collections]
        for col_name in collections:
            try:
                client.delete(
                    collection_name=col_name,
                    points_selector=Filter(
                        must=[FieldCondition(key="source", match=MatchValue(value="qa_pair"))]
                    )
                )
                print(f"  Qdrant ({col_name}): QA 对已删除")
            except Exception as e:
                print(f"  Qdrant ({col_name}): 跳过 - {e}")
    except Exception as e:
        print(f"  Qdrant 连接失败: {e}")

    # Neo4j: 仅删除 QAChapter/QAPair 节点 + 约束
    try:
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
        )
        try:
            with driver.session() as session:
                r = session.run("MATCH (q:QAPair) RETURN count(q) AS c").single()
                qa_count = r["c"] if r else 0
                r = session.run("MATCH (ch:QAChapter) RETURN count(ch) AS c").single()
                ch_count = r["c"] if r else 0
                print(f"  当前: {ch_count} 章节, {qa_count} QA 对")

                session.run("MATCH (q:QAPair)-[r:BELONGS_TO]->(ch:QAChapter) DELETE r")
                session.run("MATCH (q:QAPair) DELETE q")
                session.run("MATCH (ch:QAChapter) DELETE ch")
                print(f"  已删除所有 QA 章节和 QA 对")

                for cypher in [
                    "DROP CONSTRAINT QAPair_qa_no IF EXISTS",
                    "DROP CONSTRAINT QAChapter_chapter_no IF EXISTS",
                ]:
                    try:
                        session.run(cypher)
                        print(f"  删除约束: {cypher}")
                    except Exception:
                        pass
        finally:
            driver.close()
    except Exception as e:
        print(f"  Neo4j 连接失败: {e}")

    print("QA 知识库清空完成")


def main():
    parser = argparse.ArgumentParser(
        description="彻底清空所有数据库（Qdrant、Neo4j、案例库、记忆库、QA知识库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python clear_all.py              # 清空所有数据库
  python clear_all.py --qdrant     # 只清空 Qdrant
  python clear_all.py --neo4j      # 只清空 Neo4j
  python clear_all.py --cases      # 只清空案例数据库
  python clear_all.py --memory     # 只清空记忆数据库
  python clear_all.py --qa         # 只清空 QA 知识库
  python clear_all.py --qdrant --neo4j  # 只清空向量库和图库
        """
    )
    parser.add_argument("--qdrant", action="store_true", help="只清空 Qdrant")
    parser.add_argument("--neo4j", action="store_true", help="只清空 Neo4j")
    parser.add_argument("--cases", action="store_true", help="只清空案例数据库")
    parser.add_argument("--memory", action="store_true", help="只清空记忆数据库")
    parser.add_argument("--qa", action="store_true", help="只清空 QA 知识库")
    parser.add_argument("--all", action="store_true", help="清空所有数据库（默认）")
    args = parser.parse_args()
    
    if not (args.qdrant or args.neo4j or args.cases or args.memory or args.qa or args.all):
        args.all = True
    
    print("🗑️  数据库彻底清空工具")
    print("=" * 60)
    print("警告：此操作将删除所有数据，不可恢复！")
    print("=" * 60)
    
    if args.all or args.qdrant:
        clear_qdrant()
    
    if args.all or args.neo4j:
        clear_neo4j()
    
    if args.all or args.cases:
        clear_cases_db()
    
    if args.all or args.memory:
        clear_memory_db()
    
    if args.qa:
        clear_qa()
    
    print("\n" + "=" * 60)
    print("✅ 所有清空操作完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
