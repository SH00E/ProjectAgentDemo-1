# -*- coding: utf-8 -*-
"""
故障诊断引擎模块
负责故障诊断、损伤评估、方案推荐
支持 Neo4j + Qdrant 循环检索
"""

import os
import json
import random
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from prompts import fmt_prompt, random_reduce_count

logger = logging.getLogger(__name__)


class RepairDiagnosisEngine:
    """
    故障诊断引擎
    结合 Neo4j 知识图谱、Qdrant 向量库和 LLM 进行智能诊断
    """
    
    def __init__(self, rag_tool, memory_tool, llm, vision_llm=None):
        """
        初始化诊断引擎
        
        Args:
            rag_tool: RAGTool实例
            memory_tool: MemoryTool实例
            llm: LLM实例（文本诊断）
            vision_llm: 视觉LLM实例（图片分析，可选）
        """
        self.rag = rag_tool
        self.memory = memory_tool
        self.llm = llm
        self.vision_llm = vision_llm
        self.max_rounds = 2  # 最大检索轮数
        logger.info("✅ 故障诊断引擎初始化完成")
    
    # ==================== 核心诊断功能 ====================
    
    def diagnose(self, description: str, image_path: str = None, mode: str = "repair") -> Dict[str, Any]:
        """
        故障诊断/维护评估
        
        Args:
            description: 故障/维护描述
            image_path: 现场照片路径 (可选)
            mode: "repair" = 故障诊断, "maintenance" = 日常维护
            
        Returns:
            Dict: 诊断结果
        """
        try:
            # 步骤1: 提取关键词并检索
            keywords = self._extract_keywords(description, mode)
            knowledge_results = self._retrieve_knowledge(description, mode, keywords=keywords)
            
            # 步骤2: 分析照片（如果有且视觉模型可用）
            image_analysis = ""
            image_stored = False
            if isinstance(image_path, str) and image_path and os.path.exists(image_path):
                if self.vision_llm:
                    image_analysis = self._analyze_image(image_path)
                self._store_image_memory(image_path, description)
                image_stored = True
            
            # 步骤3: 使用LLM进行诊断分析
            diagnosis_result = self._analyze_with_llm(description, knowledge_results, image_analysis, mode)
            
            # 步骤4: 评估损伤等级
            severity = self.assess_severity(diagnosis_result)
            
            return {
                "success": True,
                "description": description,
                "image_stored": image_stored,
                "diagnosis": diagnosis_result,
                "severity": severity,
                "knowledge_references": knowledge_results[:3],  # 前3条参考
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 故障诊断失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "description": description
            }
    
    def _translate_to_english(self, text: str) -> str:
        """将中文查询翻译为英文，用于向量库搜索"""
        try:
            user_prompt = fmt_prompt("translate", "user", text=text)
            messages = [
                {"role": "system", "content": fmt_prompt("translate", "system")},
                {"role": "user", "content": user_prompt}
            ]
            result = self.llm.invoke(messages)
            return result.strip()
        except Exception as e:
            logger.warning(f"⚠️ 翻译失败: {e}")
            return text

    @staticmethod
    def _normalize(text: str) -> str:
        """去除常见分隔符，用于精确匹配比较"""
        for sep in ['-', '_', ' ', '　', '/', '\\', '·', '•']:
            text = text.replace(sep, '')
        return text.lower().strip()

    @staticmethod
    def split_query_tokens(query: str) -> List[str]:
        """拆分为核心 tokens: 原始查询 + 分隔符拆分，不包含滑动窗口。"""
        tokens = []
        if 2 <= len(query) <= 24:
            tokens.append(query)
        # 按分隔符拆分
        for sep in [' ', ',', '，', '、', '/', '|', '-', '_']:
            for part in query.split(sep):
                part = part.strip()
                if part and 2 <= len(part) <= 24 and part not in tokens:
                    tokens.append(part)
        for term in RepairDiagnosisEngine._extract_domain_terms(query):
            if term not in tokens:
                tokens.append(term)
        return tokens

    @staticmethod
    def _extract_domain_terms(query: str) -> List[str]:
        """提取常见装备维修短语，避免长句查询被滑窗 token 稀释。"""
        terms = []
        domain_terms = [
            "空地导弹", "空舰导弹", "空射巡航导弹", "制导系统", "控制系统", "动力系统",
            "电气系统", "引战系统", "弹体结构", "电视", "红外", "双模导引头", "导引头",
            "光轴", "光轴偏差", "光轴平行性", "融合偏差", "精确制导", "频综器", "频率综合器",
            "惯性导航", "惯组", "雷达", "数据链", "校准", "更换", "失锁", "漂移", "偏差"
        ]
        for term in domain_terms:
            if term in query and term not in terms:
                terms.append(term)
        for term in re.findall(r"[A-Za-z]+-?\d+[A-Za-z0-9-]*", query):
            if term not in terms:
                terms.append(term)
        return terms

    @staticmethod
    def expand_recall_tokens(tokens: List[str]) -> List[str]:
        """扩展召回 tokens；滑动窗口只用于召回，不参与相关性分母。"""
        recall_tokens = list(tokens)
        # 滑动窗口（仅对长度>=4的片段，避免太短的无意义token）
        for part in list(tokens):
            if len(part) >= 4:
                for win_size in [2, 3]:
                    for k in range(len(part) - win_size + 1):
                        token = part[k:k+win_size]
                        if token not in recall_tokens:
                            recall_tokens.append(token)
        return recall_tokens

    @staticmethod
    def compute_keyword_score(record: Dict, query_tokens: List[str], full_query: str) -> tuple:
        """
        统计 query_tokens 中有多少命中了 record 的文本字段
        
        返回: (score, matched_count, total_count)
        """
        content = str(record.get("content", ""))
        description = str(record.get("description", ""))
        problem = str(record.get("problem", ""))
        action = str(record.get("action", ""))
        aircraft_model = str(record.get("aircraft_model", ""))
        text = " ".join([content, description, problem, action, aircraft_model])
        text_norm = RepairDiagnosisEngine._normalize(text)

        total = len(query_tokens)
        if total == 0:
            return 0.0, 0, 0

        matched = 0
        matched_weight = 0.0
        for token in query_tokens:
            token_norm = RepairDiagnosisEngine._normalize(token)
            if not token_norm:
                continue

            field_weight = 0.0
            if token_norm in RepairDiagnosisEngine._normalize(aircraft_model):
                field_weight = max(field_weight, 1.6)
            if token_norm in RepairDiagnosisEngine._normalize(description):
                field_weight = max(field_weight, 1.35)
            if token_norm in RepairDiagnosisEngine._normalize(problem):
                field_weight = max(field_weight, 1.35)
            if token_norm in RepairDiagnosisEngine._normalize(action):
                field_weight = max(field_weight, 1.1)
            if token_norm in RepairDiagnosisEngine._normalize(content):
                field_weight = max(field_weight, 1.2)

            if field_weight > 0:
                matched += 1
                matched_weight += field_weight

        ratio = matched / total
        weighted_ratio = matched_weight / total

        # boost: 全部命中 > 大部分命中 > 部分命中
        if matched == total and total > 1:
            boost = 1.5  # 全部命中
        elif ratio >= 0.67:
            boost = 1.2  # 大部分命中
        else:
            boost = 1.0

        # 额外检查：完整查询作为连续子串出现
        full_query_norm = RepairDiagnosisEngine._normalize(full_query)
        if full_query_norm and full_query_norm in text_norm:
            boost = max(boost, 1.8)

        score = weighted_ratio * boost
        return score, matched, total

    def _search_collection(self, client, collection_name: str, query_parts: List[str],
                           keyword_results: Dict):
        """在单个 Qdrant 集合中做关键词召回（不评分）"""
        from qdrant_client.models import Filter, FieldCondition, MatchText

        kw_found = 0
        try:
            keyword_conditions = []
            for qp in query_parts:
                keyword_conditions.extend([
                    FieldCondition(key="content", match=MatchText(text=qp)),
                    FieldCondition(key="text", match=MatchText(text=qp)),
                    FieldCondition(key="description", match=MatchText(text=qp)),
                    FieldCondition(key="description_zh", match=MatchText(text=qp)),
                    FieldCondition(key="problem", match=MatchText(text=qp)),
                    FieldCondition(key="problem_zh", match=MatchText(text=qp)),
                    FieldCondition(key="action", match=MatchText(text=qp)),
                    FieldCondition(key="action_zh", match=MatchText(text=qp)),
                ])
            kw_filter = Filter(should=keyword_conditions)
            kw_scroll = client.scroll(
                collection_name=collection_name,
                scroll_filter=kw_filter,
                limit=1000,
                with_payload=True
            )
            for point in kw_scroll[0]:
                payload = point.payload or {}
                rid = payload.get("record_id", str(point.id))
                if rid not in keyword_results:
                    keyword_results[rid] = {
                        "content": payload.get("content", payload.get("text", "")),
                        "source": payload.get("source", "unknown"),
                        "record_id": rid,
                        "aircraft_model": payload.get("aircraft_model", ""),
                        "manufacturer": payload.get("manufacturer", ""),
                        "description": payload.get("description", "") or payload.get("description_zh", ""),
                        "problem": payload.get("problem", "") or payload.get("problem_zh", ""),
                        "action": payload.get("action", "") or payload.get("action_zh", ""),
                        "case_type": payload.get("case_type", ""),
                        "collection": collection_name,
                    }
                    kw_found += 1
            logger.info(f"关键词召回({collection_name}): {kw_found} 条")
        except Exception as e:
            logger.warning(f"关键词召回失败({collection_name}): {e}")

    def _retrieve_knowledge(self, query: str, mode: str = "repair", keywords: List[str] = None) -> List[Dict]:
        """检索相关知识 - 关键词计分排序，向量作为 fallback
        
        Args:
            query: 原始查询（用于向量fallback和完整子串匹配）
            mode: "repair" 或 "maintenance"
            keywords: 预提取的关键词列表，如果为None则从query拆分
        """
        try:
            from qdrant_client import QdrantClient
            from hello_agents.memory.embedding import get_text_embedder

            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
            client = QdrantClient(url=qdrant_url, trust_env=not is_local)
            embedder = get_text_embedder()

            # 确定要排除的案例类型
            exclude_case_type = "maintenance" if mode == "repair" else "repair"

            # 使用预提取的关键词计分；滑动窗口只用于召回，避免长句相关性被稀释
            if keywords:
                score_tokens = list(keywords)
                for term in self.split_query_tokens(query):
                    if term not in score_tokens:
                        score_tokens.append(term)
            else:
                score_tokens = self.split_query_tokens(query)
            query_tokens = self.expand_recall_tokens(score_tokens)
            logger.info(f"🔍 计分 tokens ({len(score_tokens)}): {score_tokens[:10]}...")
            logger.info(f"🔍 召回 tokens ({len(query_tokens)}): {query_tokens[:10]}...")

            # ===== 第一步：关键词召回 =====
            collections = [c.name for c in client.get_collections().collections]
            keyword_results = {}
            for col_name in collections:
                try:
                    self._search_collection(client, col_name, query_tokens, keyword_results)
                except Exception as e:
                    logger.warning(f"召回失败({col_name}): {e}")

            # 过滤掉不匹配模式的案例类型
            filtered_out = 0
            for rid in list(keyword_results.keys()):
                ct = keyword_results[rid].get("case_type", "")
                if ct == exclude_case_type:
                    del keyword_results[rid]
                    filtered_out += 1
            if filtered_out > 0:
                logger.info(f"🗂️ 过滤掉 {filtered_out} 条 '{exclude_case_type}' 类型案例")

            # ===== 第二步：SQLite 关键词召回 =====
            try:
                import sqlite3
                cases_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                             "memory_data", "cases.db")
                if os.path.exists(cases_db_path):
                    raw_tokens = list(score_tokens)
                    if query not in raw_tokens:
                        raw_tokens.insert(0, query)

                    conn = sqlite3.connect(cases_db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    sql_conditions = []
                    sql_params = []
                    for qp in raw_tokens:
                        like_param = f"%{qp}%"
                        sql_conditions.append('''(title LIKE ? OR device_type LIKE ? OR fault_symptom LIKE ?
                                  OR fault_cause LIKE ? OR solution LIKE ? OR parts_used LIKE ?
                                  OR notes LIKE ? OR maintenance_type LIKE ? OR maintenance_cycle LIKE ?
                                  OR maintenance_standard LIKE ?)''')
                        sql_params.extend([like_param] * 10)
                    if sql_conditions:
                        sql = 'SELECT DISTINCT * FROM cases WHERE (' + ' OR '.join(sql_conditions) + ') AND case_type != ?'
                        sql_params.append(exclude_case_type)
                        cursor.execute(sql, sql_params)
                    rows = cursor.fetchall()
                    conn.close()
                    for row in rows:
                        case_id = row["id"]
                        rid = f"CASE_{case_id}"
                        if rid in keyword_results:
                            continue
                        case_type = row["case_type"] if "case_type" in row.keys() else "repair"
                        if case_type == "maintenance":
                            content = f"{row['title']} | 设备: {row['device_type']} | 维护类型: {row['maintenance_type'] if 'maintenance_type' in row.keys() else ''} | 方案: {row['solution']}"
                        else:
                            content = f"{row['title']} | 设备: {row['device_type']} | 故障: {row['fault_symptom'] or ''} | 原因: {row['fault_cause'] or ''} | 方案: {row['solution']}"
                        keyword_results[rid] = {
                            "content": content,
                            "source": "user_case",
                            "record_id": rid,
                            "aircraft_model": row["device_type"],
                            "manufacturer": "",
                            "description": (row["fault_symptom"] if case_type == "repair" else (row["maintenance_type"] if "maintenance_type" in row.keys() else "")) or "",
                            "problem": (row["fault_cause"] if case_type == "repair" else (row["maintenance_cycle"] if "maintenance_cycle" in row.keys() else "")) or "",
                            "action": row["solution"] or "",
                            "case_type": case_type,
                            "collection": "sqlite",
                        }
            except Exception as e:
                logger.warning(f"SQLite 搜索失败: {e}")

            # ===== 第三步：关键词计分 =====
            result_list = list(keyword_results.values())
            for r in result_list:
                score, matched, total = self.compute_keyword_score(r, score_tokens, query)
                r["score"] = score
                r["matched_tokens"] = matched
                r["total_tokens"] = total

            # ===== 第四步：如果关键词无结果，用向量 fallback =====
            if not result_list:
                logger.info("📊 关键词无结果，启动向量 fallback...")
                vector_fallback = {}
                for col_name in collections:
                    try:
                        vector_q = embedder.encode(query).tolist()
                        vec_results = client.query_points(
                            collection_name=col_name,
                            query=vector_q,
                            limit=20,
                            with_payload=True
                        ).points
                        for r in vec_results:
                            payload = r.payload or {}
                            rid = payload.get("record_id", str(r.id))
                            if rid not in vector_fallback:
                                ct = payload.get("case_type", "")
                                if ct == exclude_case_type:
                                    continue
                                vector_fallback[rid] = {
                                    "content": payload.get("content", payload.get("text", "")),
                                    "score": 0.45,
                                    "source": payload.get("source", "unknown"),
                                    "record_id": rid,
                                    "aircraft_model": payload.get("aircraft_model", ""),
                                    "manufacturer": payload.get("manufacturer", ""),
                                    "description": payload.get("description", ""),
                                    "problem": payload.get("problem", ""),
                                    "action": payload.get("action", ""),
                                    "case_type": ct,
                                    "collection": col_name,
                                    "matched_tokens": 0,
                                    "total_tokens": len(query_tokens),
                                }
                    except Exception:
                        pass
                result_list = list(vector_fallback.values())
                logger.info(f"📊 向量 fallback: 找到 {len(result_list)} 条")

            # 排序
            result_list.sort(key=lambda x: x["score"], reverse=True)
            logger.info(f"📊 检索完成: 共 {len(result_list)} 条结果")
            return result_list[:50]

        except Exception as e:
            logger.warning(f"⚠️ 知识检索失败: {e}")
            return []
    
    def _query_neo4j(self, keywords: List[str]) -> List[Dict]:
        """
        从 Neo4j 知识图谱查询相关信息
        
        Args:
            keywords: 关键词列表（飞机型号、制造商、故障类型等）
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            from neo4j import GraphDatabase
            
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
            )
            
            results = []
            
            with driver.session() as session:
                for keyword in keywords:
                    keyword = keyword.strip()
                    if not keyword:
                        continue
                    
                    # 查询飞机型号
                    r = session.run("""
                        MATCH (a:AircraftModel)
                        WHERE a.name CONTAINS $keyword
                        OPTIONAL MATCH (a)-[:MANUFACTURED_BY]->(m:Manufacturer)
                        OPTIONAL MATCH (rec:AviationRecord)-[:INVOLVES_AIRCRAFT]->(a)
                        OPTIONAL MATCH (rec)-[:HAS_INCIDENT_TYPE]->(t:IncidentType)
                        RETURN DISTINCT 
                            'Aircraft' AS type,
                            a.name AS name,
                            collect(DISTINCT m.name)[..3] AS manufacturers,
                            collect(DISTINCT t.name)[..5] AS incident_types,
                            count(DISTINCT rec) AS record_count
                        LIMIT 5
                    """, keyword=keyword)
                    
                    for record in r:
                        results.append({
                            "type": "Aircraft",
                            "name": record["name"],
                            "manufacturers": record["manufacturers"],
                            "incident_types": record["incident_types"],
                            "record_count": record["record_count"],
                            "source": "neo4j"
                        })
                    
                    # 查询制造商
                    r = session.run("""
                        MATCH (m:Manufacturer)
                        WHERE m.name CONTAINS $keyword
                        OPTIONAL MATCH (a:AircraftModel)-[:MANUFACTURED_BY]->(m)
                        RETURN DISTINCT 
                            'Manufacturer' AS type,
                            m.name AS name,
                            collect(DISTINCT a.name)[..5] AS aircraft_models,
                            count(DISTINCT a) AS aircraft_count
                        LIMIT 5
                    """, keyword=keyword)
                    
                    for record in r:
                        results.append({
                            "type": "Manufacturer",
                            "name": record["name"],
                            "aircraft_models": record["aircraft_models"],
                            "aircraft_count": record["aircraft_count"],
                            "source": "neo4j"
                        })
                    
                    # 查询事故类型
                    r = session.run("""
                        MATCH (t:IncidentType)
                        WHERE t.name CONTAINS $keyword
                        OPTIONAL MATCH (rec:AviationRecord)-[:HAS_INCIDENT_TYPE]->(t)
                        OPTIONAL MATCH (rec)-[:INVOLVES_AIRCRAFT]->(a:AircraftModel)
                        RETURN DISTINCT 
                            'IncidentType' AS type,
                            t.name AS name,
                            collect(DISTINCT a.name)[..5] AS related_aircraft,
                            count(DISTINCT rec) AS record_count
                        LIMIT 5
                    """, keyword=keyword)
                    
                    for record in r:
                        results.append({
                            "type": "IncidentType",
                            "name": record["name"],
                            "related_aircraft": record["related_aircraft"],
                            "record_count": record["record_count"],
                            "source": "neo4j"
                        })
            
            driver.close()
            return results
            
        except Exception as e:
            logger.warning(f"⚠️ Neo4j 查询失败: {e}")
            return []
    
    def _extract_keywords(self, description: str, mode: str = "repair") -> List[str]:
        """
        从故障/维护描述中提取关键词
        
        Args:
            description: 故障/维护描述
            mode: "repair" = 故障诊断, "maintenance" = 日常维护
            
        Returns:
            List[str]: 关键词列表
        """
        try:
            key_suffix = "_maintenance" if mode == "maintenance" else ""
            user_prompt = fmt_prompt("extract_keywords", f"user{key_suffix}", description=description)
            messages = [
                {"role": "system", "content": fmt_prompt("extract_keywords", f"system{key_suffix}")},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.invoke(messages)
            keywords = [kw.strip() for kw in response.split(",") if kw.strip() and kw.strip() != "无"]
            return keywords[:10] if keywords else ["维护保养"]  # 最多10个关键词，至少返回一个
            
        except Exception as e:
            logger.warning(f"⚠️ 关键词提取失败: {e}")
            # 简单分词作为备选，过滤掉过短的词
            return [w for w in description.split() if len(w) > 1][:5] or ["故障诊断"]
    
    def _store_image_memory(self, image_path: str, description: str):
        """存储照片到感知记忆"""
        try:
            self.memory.run({
                "action": "add",
                "content": f"用户上传故障照片，故障描述: {description}",
                "memory_type": "perceptual",
                "importance": 0.7,
                "modality": "image",
                "file_path": image_path,
                "topic": "fault_photo"
            })
            logger.info(f"✅ 照片已存储到感知记忆: {image_path}")
        except Exception as e:
            logger.warning(f"⚠️ 照片存储失败: {e}")
    
    def _analyze_image(self, image_path: str) -> str:
        """
        调用视觉模型分析故障照片
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            str: 图片分析结果文本
        """
        if not self.vision_llm:
            return ""
        
        try:
            import base64
            
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            
            ext = os.path.splitext(image_path)[1].lower().lstrip(".")
            mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif", "bmp": "bmp"}
            mime_type = mime_map.get(ext, "jpeg")
            
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{mime_type};base64,{b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": fmt_prompt("analyze_image", "user")
                    }
                ]
            }]
            
            response = self.vision_llm.invoke(messages)
            logger.info(f"✅ 图片分析完成")
            return response
            
        except Exception as e:
            logger.warning(f"⚠️ 图片分析失败: {e}")
            return f"（图片分析失败: {str(e)}）"
    
    def diagnose_with_stream(self, description: str, image_path: str = None, mode: str = "repair"):
        """
        流式诊断 - 循环检索流程
        
        Args:
            description: 故障/维护描述
            image_path: 图片路径（可选）
            mode: "repair" = 故障诊断, "maintenance" = 日常维护
        
        流程：
        1. 提取关键词
        2. 查询 Neo4j 知识图谱
        3. 查询 Qdrant 向量库
        4. 检查相关性阈值
        5. LLM 判断是否需要继续检索
        6. 循环（最多2轮）
        7. 最终诊断
        
        Yields:
            ("step", "步骤描述")
            ("rag", knowledge_results) — 检索结果
            ("neo4j", neo4j_results) — 知识图谱结果
            ("analysis", chunk) — LLM流式分析
            ("diagnosis", final_result) — 最终诊断
        """
        all_evidence = []  # 所有证据
        image_analysis = ""
        image_stored = False
        
        # 根据模式调整提示
        mode_label = "维护" if mode == "maintenance" else "维修"
        
        # 处理照片
        if isinstance(image_path, str) and image_path and os.path.exists(image_path):
            if self.vision_llm:
                yield ("step", "👁️ 正在分析现场照片...")
                image_analysis = self._analyze_image(image_path)
                yield ("step", "📸 照片分析完成")
            else:
                yield ("step", "📸 正在存储现场照片...")
            self._store_image_memory(image_path, description)
            image_stored = True
        
        # 第一轮：提取关键词并查询
        yield ("step", "🔍 第1轮：提取关键信息...")
        
        # 提取关键词
        keywords = self._extract_keywords(description, mode)
        yield ("step", f"📝 提取到关键词: {', '.join(keywords[:5])}")
        
        # 查询 Neo4j
        yield ("step", "🗄️ 正在查询知识图谱 (Neo4j)...")
        neo4j_results = self._query_neo4j(keywords)
        if neo4j_results:
            yield ("neo4j", neo4j_results)
            all_evidence.extend([{
                "content": f"[知识图谱] {r.get('name', '')} - 类型: {r.get('type', '')}",
                "score": 0.9,
                "source": "neo4j",
                "source_label": "知识图谱",
                "details": r
            } for r in neo4j_results[:5]])
            yield ("step", f"✅ 从知识图谱找到 {random_reduce_count(len(neo4j_results))} 条相关信息")
        
        # 查询 Qdrant（用提取的关键词检索）
        yield ("step", "📚 正在查询向量知识库 (Qdrant)...")
        qdrant_results = self._retrieve_knowledge(description, mode, keywords=keywords)
        if qdrant_results:
            yield ("rag", qdrant_results)
            all_evidence.extend(qdrant_results[:20])
            yield ("step", f"✅ 从向量库找到 {random_reduce_count(len(qdrant_results))} 条相关记录")
        
        # ========== 相关性检查 ==========
        max_score = max([r.get("score", 0) for r in qdrant_results], default=0)
        has_neo4j = len(neo4j_results) > 0
        
        # 如果向量库分数太低且知识图谱无结果，直接拒绝
        if max_score < 0.3 and not has_neo4j and not image_analysis:
            yield ("step", "⚠️ 未找到相关维修记录")
            yield ("result", {
                "success": False,
                "error": "未找到相关维修记录",
                "message": "当前知识库中没有与您描述匹配的维修记录。请尝试：\n1. 输入更详细的故障描述\n2. 包含设备型号、故障现象等关键信息\n3. 检查输入内容是否与维修领域相关",
                "max_score": max_score,
                "suggestion": "请输入详细的故障描述，例如：CESSNA 172 发动机在起飞后熄火"
            })
            return
        
        # 如果相关性较低，提示用户但仍继续
        if max_score < 0.4:
            yield ("step", f"⚠️ 检索结果相关性较低 ({max_score:.1%})，诊断结果仅供参考")
        
        # LLM 分析第一轮结果，判断是否需要继续
        yield ("step", "🧠 正在分析第一轮检索结果...")
        
        # 构建上下文
        context = self._build_context(description, neo4j_results, qdrant_results, image_analysis, mode)
        
        # LLM 判断是否需要更多信息
        need_more = False
        if len(neo4j_results) < 2 and len(qdrant_results) < 2:
            need_more = True
            yield ("step", "📊 检索结果较少，尝试扩大搜索范围...")
        
        # 第二轮（如果需要）
        if need_more and self.max_rounds >= 2:
            yield ("step", "🔍 第2轮：扩大搜索范围...")
            
            # 使用更宽泛的关键词
            broader_keywords = self._extract_broader_keywords(description, keywords, mode)
            if broader_keywords:
                yield ("step", f"📝 扩展关键词: {', '.join(broader_keywords[:5])}")
                
                # 再次查询 Neo4j
                neo4j_results_2 = self._query_neo4j(broader_keywords)
                if neo4j_results_2:
                    yield ("neo4j", neo4j_results_2)
                    all_evidence.extend([{
                        "content": f"[知识图谱] {r.get('name', '')} - 类型: {r.get('type', '')}",
                        "score": 0.85,
                        "source": "neo4j",
                        "source_label": "知识图谱",
                        "details": r
                    } for r in neo4j_results_2[:3]])
                    yield ("step", f"✅ 第2轮从知识图谱找到 {random_reduce_count(len(neo4j_results_2))} 条信息")
                
                # 再次查询 Qdrant（使用扩展关键词）
                broader_query = f"{description} {' '.join(broader_keywords[:3])}"
                qdrant_results_2 = self._retrieve_knowledge(broader_query, mode, keywords=keywords + broader_keywords)
                if qdrant_results_2:
                    yield ("rag", qdrant_results_2)
                    all_evidence.extend(qdrant_results_2[:10])
                    yield ("step", f"✅ 第2轮从向量库找到 {random_reduce_count(len(qdrant_results_2))} 条记录")
        
        # 最终诊断
        yield ("step", "🧠 正在综合分析所有证据...")
        
        # 流式输出分析过程
        analysis_prompt = self._build_analysis_prompt(description, all_evidence, image_analysis, mode)
        sys_key = f"system{'_maintenance' if mode == 'maintenance' else ''}"
        messages = [
            {"role": "system", "content": fmt_prompt("analysis", sys_key)},
            {"role": "user", "content": analysis_prompt}
        ]
        
        analysis_text = ""
        for chunk in self.llm.stream_invoke(messages):
            analysis_text += chunk
            yield ("analysis", chunk)
        
        # 结构化诊断
        yield ("step", "📋 正在生成结构化诊断...")
        diagnosis_result = self._analyze_with_llm(description, all_evidence, image_analysis, mode)
        
        # 损伤评估
        severity = self.assess_severity(diagnosis_result)
        
        # 去重证据
        unique_evidence = self._deduplicate_evidence(all_evidence)
        
        final = {
            "success": True,
            "description": description,
            "image_stored": image_stored,
            "diagnosis": diagnosis_result,
            "severity": severity,
            "knowledge_references": unique_evidence[:20],
            "analysis_text": analysis_text,
            "neo4j_count": len([e for e in all_evidence if e.get("source") == "neo4j"]),
            "qdrant_count": len([e for e in all_evidence if e.get("source") != "neo4j"]),
            "timestamp": datetime.now().isoformat()
        }
        yield ("diagnosis", final)
    
    def _extract_broader_keywords(self, description: str, original_keywords: List[str], mode: str = "repair") -> List[str]:
        """提取更宽泛的关键词"""
        try:
            key_suffix = "_maintenance" if mode == "maintenance" else ""
            user_prompt = fmt_prompt("extract_broader_keywords", f"user{key_suffix}",
                                     description=description,
                                     keywords=', '.join(original_keywords))
            messages = [
                {"role": "system", "content": fmt_prompt("extract_broader_keywords", f"system{key_suffix}")},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.invoke(messages)
            keywords = [kw.strip() for kw in response.split(",") if kw.strip() and kw.strip() != "无"]
            # 过滤掉已有的关键词
            new_keywords = [kw for kw in keywords if kw not in original_keywords]
            return new_keywords[:5]
            
        except Exception as e:
            logger.warning(f"⚠️ 关键词扩展失败: {e}")
            return []
    
    def _build_context(self, description: str, neo4j_results: List, 
                       qdrant_results: List, image_analysis: str, mode: str = "repair") -> str:
        """构建上下文"""
        desc_label = "维护需求" if mode == "maintenance" else "故障描述"
        context = f"【{desc_label}】\n{description}\n"
        
        if neo4j_results:
            context += "\n\n【知识图谱信息】\n"
            for i, r in enumerate(neo4j_results[:5], 1):
                context += f"{i}. {r.get('name', '')} ({r.get('type', '')})\n"
        
        if qdrant_results:
            context += "\n\n【相似案例】\n"
            for i, r in enumerate(qdrant_results[:5], 1):
                content = r.get("content", "")[:200]
                context += f"{i}. {content}\n"
        
        if image_analysis:
            context += f"\n\n【照片分析】\n{image_analysis}\n"
        
        return context
    
    def _build_analysis_prompt(self, description: str, evidence: List, image_analysis: str, mode: str = "repair") -> str:
        """构建分析提示词"""
        evidence_context = ""
        if evidence:
            evidence_context = "\n\n【检索到的证据】\n"
            for i, e in enumerate(evidence[:10], 1):
                source = e.get("source_label", "未知")
                content = e.get("content", "")[:150]
                evidence_context += f"{i}. [{source}] {content}\n"
        
        image_context = ""
        if image_analysis:
            image_context = f"\n\n【照片分析】\n{image_analysis}\n"
        
        key_suffix = "_maintenance" if mode == "maintenance" else ""
        return fmt_prompt("analysis", f"user{key_suffix}",
                          description=description,
                          evidence_context=evidence_context,
                          image_context=image_context)
    
    def _deduplicate_evidence(self, evidence: List[Dict]) -> List[Dict]:
        """去重证据"""
        seen = set()
        unique = []
        for e in evidence:
            content = e.get("content", "")
            if content and content not in seen:
                seen.add(content)
                unique.append(e)
        return unique
    
    def recommend_solution_stream(self, diagnosis_result: Dict, mode: str = "repair"):
        """
        流式推荐维修/维护方案
        
        Args:
            diagnosis_result: 诊断结果
            mode: "repair" = 维修方案, "maintenance" = 维护方案
        
        Yields:
            ("step", "步骤描述")
            ("solution_text", chunk) — LLM流式方案文本
            ("solution", final_solution) — 最终结构化方案
        """
        if mode == "maintenance":
            yield ("step", "🔧 正在生成维护方案...")
            fault_type = diagnosis_result.get("fault_type", "未知")
            causes = diagnosis_result.get("possible_causes", [])
            recommended = diagnosis_result.get("recommended_actions", [])
            solution_prompt = fmt_prompt("solution_maintenance", "user",
                                         fault_type=fault_type,
                                         causes=', '.join(causes),
                                         recommended=', '.join(recommended))
        else:
            yield ("step", "🔧 正在生成维修方案...")
            fault_type = diagnosis_result.get("fault_type", "未知")
            causes = diagnosis_result.get("possible_causes", [])
            recommended = diagnosis_result.get("recommended_actions", [])
            solution_prompt = fmt_prompt("solution_repair", "user",
                                         fault_type=fault_type,
                                         causes=', '.join(causes),
                                         recommended=', '.join(recommended))

        messages = [
            {"role": "system", "content": fmt_prompt("solution_common", "system")},
            {"role": "user", "content": solution_prompt}
        ]
        
        solution_text = ""
        for chunk in self.llm.stream_invoke(messages):
            solution_text += chunk
            yield ("solution_text", chunk)
        
        # 结构化方案
        solution = self.recommend_solution(diagnosis_result)
        yield ("solution", solution)
    
    def _analyze_with_llm(self, description: str, 
                          knowledge: List[Dict],
                          image_analysis: str = "",
                          mode: str = "repair") -> Dict[str, Any]:
        """使用LLM进行诊断/维护分析"""
        try:
            # 构建知识上下文
            knowledge_context = ""
            if isinstance(knowledge, (list, tuple)) and len(knowledge) > 0:
                knowledge_context = "\n\n【参考知识】\n"
                for i, k in enumerate(knowledge[:3], 1):
                    content = k.get("content", str(k))
                    knowledge_context += f"{i}. {content[:500]}\n"
            
            # 图片分析结果
            image_context = ""
            if image_analysis:
                image_context = f"\n\n【现场照片分析】\n{image_analysis}\n"
            
            # 构建诊断/维护提示词
            key_suffix = "_maintenance" if mode == "maintenance" else ""
            system_prompt = fmt_prompt("diagnosis_structured", f"system{key_suffix}")
            user_prompt = fmt_prompt("diagnosis_structured", f"user{key_suffix}",
                                     description=description,
                                     knowledge_context=knowledge_context,
                                     image_context=image_context)

            # 调用LLM (使用messages格式)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm.invoke(messages)
            
            # 解析JSON响应
            try:
                # 尝试提取JSON
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0]
                
                result = json.loads(json_str.strip())
                return result
            except json.JSONDecodeError:
                # JSON解析失败，返回原始响应
                return {
                    "fault_type": "待分析",
                    "possible_causes": ["需要进一步诊断"],
                    "impact": response[:200],
                    "urgency": "中",
                    "recommended_actions": ["请提供更多详细信息"]
                }
                
        except Exception as e:
            logger.error(f"❌ LLM分析失败: {e}")
            return {
                "fault_type": "分析失败",
                "possible_causes": [f"LLM调用错误: {str(e)}"],
                "impact": "无法评估",
                "urgency": "中",
                "recommended_actions": ["请重试或手动诊断"]
            }
    
    # ==================== 损伤评估 ====================
    
    def assess_severity(self, diagnosis_result: Dict) -> Dict[str, Any]:
        """
        评估损伤等级
        
        Args:
            diagnosis_result: 诊断结果
            
        Returns:
            Dict: 损伤等级评估
        """
        urgency = diagnosis_result.get("urgency", "中")
        
        # 根据紧急程度映射到损伤等级
        severity_map = {
            "低": {
                "level": "轻微",
                "description": "不影响正常使用，可选择性修复",
                "priority": 1,
                "color": "green"
            },
            "中": {
                "level": "中等",
                "description": "可能影响使用或存在安全隐患，建议尽快修复",
                "priority": 2,
                "color": "yellow"
            },
            "高": {
                "level": "严重",
                "description": "严重影响使用或存在安全风险，需要立即修复",
                "priority": 3,
                "color": "red"
            }
        }
        
        return severity_map.get(urgency, severity_map["中"])
    
    # ==================== 方案推荐 ====================
    
    def recommend_solution(self, diagnosis_result: Dict) -> Dict[str, Any]:
        """
        推荐维修方案
        
        Args:
            diagnosis_result: 诊断结果
            
        Returns:
            Dict: 维修方案
        """
        try:
            # 构建方案推荐提示词
            fault_type = diagnosis_result.get("fault_type", "未知")
            causes = diagnosis_result.get("possible_causes", [])
            recommended = diagnosis_result.get("recommended_actions", [])
            
            system_prompt = fmt_prompt("repair_solution_structured", "system")
            user_prompt = fmt_prompt("repair_solution_structured", "user",
                                     fault_type=fault_type,
                                     causes_list='\n'.join(f'- {c}' for c in causes),
                                     recommended_list='\n'.join(f'- {a}' for a in recommended))

            # 调用LLM (使用messages格式)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm.invoke(messages)
            
            # 解析JSON响应
            try:
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0]
                
                result = json.loads(json_str.strip())
                return result
            except json.JSONDecodeError:
                return {
                    "repair_steps": [
                        {"step": 1, "action": response[:200], "tools": [], "notes": ""}
                    ],
                    "parts_required": [],
                    "tools_required": [],
                    "safety_warnings": ["请参考专业维修手册"],
                    "estimated_time": "待评估",
                    "difficulty": "中等"
                }
                
        except Exception as e:
            logger.error(f"❌ 方案推荐失败: {e}")
            return {
                "repair_steps": [],
                "parts_required": [],
                "tools_required": [],
                "safety_warnings": [f"方案生成失败: {str(e)}"],
                "estimated_time": "未知",
                "difficulty": "未知"
            }
    
    # ==================== 记录管理 ====================
    
    def _record_diagnosis(self, description: str, diagnosis: Dict, 
                          severity: Dict):
        """记录诊断过程到记忆"""
        try:
            content = (
                f"故障诊断记录: {description[:100]}... "
                f"| 故障类型: {diagnosis.get('fault_type', '未知')} "
                f"| 损伤等级: {severity.get('level', '未知')}"
            )
            
            self.memory.run({
                "action": "add",
                "content": content,
                "memory_type": "episodic",
                "importance": 0.8,
                "topic": "diagnosis"
            })
        except Exception as e:
            logger.warning(f"⚠️ 诊断记录失败: {e}")
    
    # ==================== 历史查询 ====================
    
    def get_diagnosis_history(self, limit: int = 10) -> List[Dict]:
        """
        获取诊断历史
        
        Args:
            limit: 返回数量
            
        Returns:
            List[Dict]: 历史诊断记录
        """
        try:
            # 搜索维修处理记录
            result = self.memory.run({
                "action": "search",
                "query": "维修处理 工单 故障",
                "limit": limit,
                "memory_type": "episodic"
            })
            
            if isinstance(result, str):
                # 如果返回字符串，可能是没有找到记录
                if "未找到" in result:
                    return []
                return [{"content": result}]
            
            # 如果返回列表，格式化结果
            if isinstance(result, list):
                formatted = []
                for r in result:
                    if isinstance(r, dict):
                        formatted.append(r)
                    else:
                        formatted.append({"content": str(r)})
                return formatted
            
            return []
            
        except Exception as e:
            logger.error(f"❌ 获取诊断历史失败: {e}")
            return []
