# -*- coding: utf-8 -*-
"""
QA 知识图谱跨章关联构建脚本
基于共享领域术语，自动创建 QAPair 之间的 RELATED_TO 关系

用法:
    python scripts/build_qa_relations.py --dry-run   # 预览，不实际创建
    python scripts/build_qa_relations.py             # 执行创建
"""

import os
import sys
import re
import argparse

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "libs"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from neo4j import GraphDatabase

DOMAIN_TERMS = [
    "陀螺仪", "角速度", "姿态角", "四元数", "欧拉角", "方向余弦矩阵",
    "科里奥利力", "驱动模态", "检测模态", "MEMS", "零偏", "比例因子",
    "自动驾驶仪", "控制回路", "角速度内环", "姿态回路", "增益调度",
    "执行机构", "舵机", "伺服阀", "作动器", "混控矩阵",
    "IMU", "加速度计", "惯性测量", "惯性导航", "惯组", "捷联",
    "标定", "时间同步", "采样周期", "延迟", "滤波",
    "导引头", "目标跟踪", "锁定", "红外", "电视", "双模", "光轴",
    "传感器融合", "卡尔曼滤波", "状态估计", "观测器",
    "制导律", "比例导引", "中制导", "末制导", "弹道",
    "六自由度", "仿真", "蒙特卡洛", "随机种子",
    "推进系统", "推力", "燃料", "比冲", "质量变化",
    "气动", "升力", "阻力", "动压", "攻角",
    "故障注入", "容错", "冗余", "降级",
    "实时仿真", "硬件在环", "软件在环", "模型在环",
    "配置管理", "场景", "模型", "验证", "确认",
    "数据链", "通信", "延迟", "带宽", "传输",
    "温度补偿", "振动", "噪声", "量化", "分辨率",
    "柔性弹体", "结构模态", "弯曲", "弹性",
    "飞行包线", "马赫数", "高度", "速度",
    "制导精度", "CEP", "脱靶量", "命中概率",
    "导弹", "弹体", "弹道导弹", "巡航导弹",
    "控制系统", "电气系统", "动力系统", "引战系统",
    "频综器", "频率综合器", "本振源", "接收机",
    "光纤陀螺", "光纤制导", "天线罩", "透波率",
    "近炸引信", "战斗部", "电连接器", "二次电源",
    "MOS管", "制冷机", "非均匀性校正", "漂移", "失锁",
    "数据传输", "图像传输", "制冷", "雪花", "条纹",
    "惯性", "稳定", "阻尼", "谐振", "共振",
    "耦合", "交叉轴", "安装矩阵", "坐标系",
]

CONNECTION_WEIGHTS = {
    "direct_match": 1.0,
    "domain_match": 0.7,
}


def extract_terms(text):
    """提取文本中命中的领域术语"""
    hits = set()
    text_lower = text.lower()
    for term in DOMAIN_TERMS:
        if term.lower() in text_lower:
            hits.add(term)
    return hits


def load_qa_pairs(session):
    """从 Neo4j 加载所有 QAPair"""
    result = session.run("""
        MATCH (q:QAPair)-[:BELONGS_TO]->(ch:QAChapter)
        RETURN q.qa_no AS qa_no, q.question AS question, q.answer AS answer,
               ch.chapter_no AS chapter_no, ch.chapter_name AS chapter_name
        ORDER BY q.qa_no
    """)
    return [record.data() for record in result]


def build_relations(session, pairs, min_shared_terms=2, dry_run=False):
    """基于共享领域术语创建 RELATED_TO 关系"""
    total_pairs = len(pairs)
    print(f"\n{'=' * 60}")
    print(f"Analyzing {total_pairs} QA pairs for cross-chapter connections...")
    print(f"Minimum shared terms: {min_shared_terms}")
    print(f"{'=' * 60}")

    # 预计算每个 QA 对的术语集合
    pair_terms = {}
    for p in pairs:
        text = p["question"] + " " + p["answer"] + " " + p["chapter_name"]
        pair_terms[p["qa_no"]] = {
            "terms": extract_terms(text),
            "chapter_no": p["chapter_no"],
            "chapter_name": p["chapter_name"],
        }

    # 遍历所有跨章配对
    connections_found = 0
    connections_by_chapter = {}

    for i in range(total_pairs):
        pi = pairs[i]
        ti = pair_terms[pi["qa_no"]]

        for j in range(i + 1, total_pairs):
            pj = pairs[j]

            if pi["chapter_no"] == pj["chapter_no"]:
                continue

            tj = pair_terms[pj["qa_no"]]
            shared = ti["terms"] & tj["terms"]

            if len(shared) >= min_shared_terms:
                connections_found += 1
                key = (pi["chapter_no"], pj["chapter_no"])
                connections_by_chapter[key] = connections_by_chapter.get(key, 0) + 1

                if not dry_run:
                    session.run(
                        """
                        MATCH (q1:QAPair {qa_no: $qa1}), (q2:QAPair {qa_no: $qa2})
                        MERGE (q1)-[:RELATED_TO {terms: $terms}]->(q2)
                        """,
                        qa1=pi["qa_no"],
                        qa2=pj["qa_no"],
                        terms=", ".join(sorted(shared)[:8]),
                    )

                if dry_run and connections_found <= 20:
                    print(f"  [{pi['qa_no']}] <-> [{pj['qa_no']}] "
                          f"({pi['chapter_name']} ↔ {pj['chapter_name']}): {sorted(shared)}")

    print(f"\n{'=' * 60}")
    if dry_run:
        print(f"[DRY RUN] Would create {connections_found} cross-chapter connections")
    else:
        print(f"Created {connections_found} cross-chapter connections")
    print(f"{'=' * 60}")

    if connections_by_chapter:
        print("\nChapter bridge summary (top 15):")
        sorted_chapters = sorted(connections_by_chapter.items(), key=lambda x: -x[1])
        for (ch1, ch2), count in sorted_chapters[:15]:
            name1 = next((p["chapter_name"] for p in pairs if p["chapter_no"] == ch1), "?")
            name2 = next((p["chapter_name"] for p in pairs if p["chapter_no"] == ch2), "?")
            print(f"  Ch{ch1}({name1}) ↔ Ch{ch2}({name2}): {count} connections")

    return connections_found


def main():
    parser = argparse.ArgumentParser(description="Build cross-chapter QA relations in Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    parser.add_argument("--min-terms", type=int, default=2, help="Minimum shared terms (default: 2)")
    parser.add_argument("--clear", action="store_true", help="Remove existing RELATED_TO relations first")
    args = parser.parse_args()

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678")),
    )

    try:
        with driver.session() as session:
            if args.clear:
                r = session.run("MATCH (:QAPair)-[r:RELATED_TO]->(:QAPair) RETURN count(r) AS c").single()
                existing = r["c"] if r else 0
                if existing:
                    session.run("MATCH (:QAPair)-[r:RELATED_TO]->(:QAPair) DELETE r")
                    print(f"Cleared {existing} existing RELATED_TO relations")

            pairs = load_qa_pairs(session)
            if not pairs:
                print("No QA pairs found in Neo4j. Run import_qa_pairs.py first.")
                return

            build_relations(session, pairs, min_shared_terms=args.min_terms, dry_run=args.dry_run)

            # 统计最终关系数
            r = session.run("MATCH (:QAPair)-[r:RELATED_TO]->(:QAPair) RETURN count(r) AS c").single()
            count = r["c"] if r else 0
            print(f"\nTotal RELATED_TO relationships in graph: {count}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
