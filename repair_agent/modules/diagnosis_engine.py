# -*- coding: utf-8 -*-
"""
故障诊断引擎模块
负责故障诊断、损伤评估、方案推荐
支持 Neo4j + Qdrant 循环检索
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

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
    
    def diagnose(self, description: str, image_path: str = None) -> Dict[str, Any]:
        """
        故障诊断
        
        Args:
            description: 故障描述
            image_path: 现场照片路径 (可选)
            
        Returns:
            Dict: 诊断结果
        """
        try:
            # 步骤1: 检索相关知识
            knowledge_results = self._retrieve_knowledge(description)
            
            # 步骤2: 分析照片（如果有且视觉模型可用）
            image_analysis = ""
            image_stored = False
            if isinstance(image_path, str) and image_path and os.path.exists(image_path):
                if self.vision_llm:
                    image_analysis = self._analyze_image(image_path)
                self._store_image_memory(image_path, description)
                image_stored = True
            
            # 步骤3: 使用LLM进行诊断分析
            diagnosis_result = self._analyze_with_llm(description, knowledge_results, image_analysis)
            
            # 步骤4: 评估损伤等级
            severity = self.assess_severity(diagnosis_result)
            
            # 步骤5: 记录诊断过程到记忆
            self._record_diagnosis(description, diagnosis_result, severity)
            
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
            prompt = f"""将以下中文维修故障描述翻译为简洁的英文，保留专业术语，只返回翻译结果不要其他内容：

{text}"""
            messages = [
                {"role": "system", "content": "You are a translator. Translate Chinese to English concisely."},
                {"role": "user", "content": prompt}
            ]
            result = self.llm.invoke(messages)
            return result.strip()
        except Exception as e:
            logger.warning(f"⚠️ 翻译失败: {e}")
            return text

    def _retrieve_knowledge(self, query: str) -> List[Dict]:
        """检索相关知识 - 混合搜索（关键词 + 向量）"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchText
            from hello_agents.memory.embedding import get_text_embedder
            
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
            client = QdrantClient(url=qdrant_url, trust_env=not is_local)
            embedder = get_text_embedder()
            
            collections = [c.name for c in client.get_collections().collections]
            collection_name = "aviation_knowledge_base" if "aviation_knowledge_base" in collections else "rag_knowledge_base"
            
            # 分离关键词结果和向量结果
            keyword_results = {}
            vector_results = {}
            
            # ==================== 1. 关键词搜索（Qdrant）====================
            try:
                keyword_filter = Filter(
                    should=[
                        FieldCondition(key="content", match=MatchText(text=query)),
                        FieldCondition(key="text", match=MatchText(text=query)),
                        FieldCondition(key="description", match=MatchText(text=query)),
                        FieldCondition(key="description_zh", match=MatchText(text=query)),
                        FieldCondition(key="problem", match=MatchText(text=query)),
                        FieldCondition(key="problem_zh", match=MatchText(text=query)),
                        FieldCondition(key="action", match=MatchText(text=query)),
                        FieldCondition(key="action_zh", match=MatchText(text=query)),
                    ]
                )
                
                keyword_scroll = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=keyword_filter,
                    limit=20,
                    with_payload=True
                )
                
                for point in keyword_scroll[0]:
                    payload = point.payload or {}
                    rid = payload.get("record_id", str(point.id))
                    keyword_results[rid] = {
                        "content": payload.get("content", payload.get("text", "")),
                        "score": 0.9,
                        "match_type": "keyword",
                        "source": payload.get("source", "unknown"),
                        "record_id": rid,
                        "aircraft_model": payload.get("aircraft_model", ""),
                        "manufacturer": payload.get("manufacturer", ""),
                        "description": payload.get("description", "") or payload.get("description_zh", ""),
                        "problem": payload.get("problem", "") or payload.get("problem_zh", ""),
                        "action": payload.get("action", "") or payload.get("action_zh", "")
                    }
            except Exception as e:
                logger.warning(f"Qdrant 关键词搜索失败: {e}")
            
            # ==================== 1.5 关键词搜索（SQLite）====================
            try:
                import sqlite3
                cases_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory_data", "cases.db")
                if os.path.exists(cases_db_path):
                    conn = sqlite3.connect(cases_db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    like_query = f"%{query}%"
                    cursor.execute('''
                        SELECT * FROM cases 
                        WHERE title LIKE ? 
                           OR device_type LIKE ?
                           OR fault_symptom LIKE ?
                           OR fault_cause LIKE ?
                           OR solution LIKE ?
                           OR parts_used LIKE ?
                           OR notes LIKE ?
                           OR maintenance_type LIKE ?
                           OR maintenance_cycle LIKE ?
                           OR maintenance_standard LIKE ?
                    ''', [like_query] * 10)
                    
                    rows = cursor.fetchall()
                    conn.close()
                    
                    for row in rows:
                        case_id = row["id"]
                        rid = f"CASE_{case_id}"
                        case_type = row["case_type"] if "case_type" in row.keys() else "repair"
                        
                        if case_type == "maintenance":
                            content = f"{row['title']} | 设备: {row['device_type']} | 维护类型: {row['maintenance_type'] if 'maintenance_type' in row.keys() else ''} | 方案: {row['solution']}"
                        else:
                            content = f"{row['title']} | 设备: {row['device_type']} | 故障: {row['fault_symptom']} | 原因: {row['fault_cause']} | 方案: {row['solution']}"
                        
                        keyword_results[rid] = {
                            "content": content,
                            "score": 0.95,
                            "match_type": "keyword",
                            "source": "user_case",
                            "record_id": rid,
                            "aircraft_model": row["device_type"],
                            "manufacturer": "",
                            "description": row["fault_symptom"] if case_type == "repair" else (row["maintenance_type"] if "maintenance_type" in row.keys() else ""),
                            "problem": row["fault_cause"] if case_type == "repair" else (row["maintenance_cycle"] if "maintenance_cycle" in row.keys() else ""),
                            "action": row["solution"]
                        }
            except Exception as e:
                logger.warning(f"SQLite 关键词搜索失败: {e}")
            
            # ==================== 2. 向量搜索 ====================
            try:
                vector_cn = embedder.encode(query).tolist()
                results_cn = client.query_points(
                    collection_name=collection_name,
                    query=vector_cn,
                    limit=20,
                    with_payload=True
                ).points
                
                for r in results_cn:
                    payload = r.payload or {}
                    rid = payload.get("record_id", str(r.id))
                    if rid not in keyword_results:
                        vector_results[rid] = {
                            "content": payload.get("content", payload.get("text", "")),
                            "score": r.score,
                            "match_type": "vector",
                            "source": payload.get("source", "unknown"),
                            "record_id": rid,
                            "aircraft_model": payload.get("aircraft_model", ""),
                            "manufacturer": payload.get("manufacturer", ""),
                            "description": payload.get("description", ""),
                            "problem": payload.get("problem", ""),
                            "action": payload.get("action", "")
                        }
            except Exception as e:
                logger.warning(f"向量搜索失败: {e}")
            
            # ==================== 3. 如果是中文，翻译后再次搜索 ====================
            has_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)
            if has_chinese:
                try:
                    query_en = self._translate_to_english(query)
                    logger.info(f"📝 翻译查询: {query} -> {query_en}")
                    
                    vector_en = embedder.encode(query_en).tolist()
                    results_en = client.query_points(
                        collection_name=collection_name,
                        query=vector_en,
                        limit=20,
                        with_payload=True
                    ).points
                    
                    for r in results_en:
                        payload = r.payload or {}
                        rid = payload.get("record_id", str(r.id))
                        if rid not in keyword_results and rid not in vector_results:
                            vector_results[rid] = {
                                "content": payload.get("content", payload.get("text", "")),
                                "score": r.score,
                                "match_type": "vector_en",
                                "source": payload.get("source", "unknown"),
                                "record_id": rid,
                                "aircraft_model": payload.get("aircraft_model", ""),
                                "manufacturer": payload.get("manufacturer", ""),
                                "description": payload.get("description", ""),
                                "problem": payload.get("problem", ""),
                                "action": payload.get("action", "")
                            }
                except Exception as e:
                    logger.warning(f"翻译查询失败: {e}")
            
            # ==================== 4. 合并结果 ====================
            all_results = {**keyword_results, **vector_results}
            sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
            return sorted_results[:20]
            
        except Exception as e:
            logger.warning(f"⚠️ 知识检索失败: {e}")
            # 回退到RAG工具
            try:
                result = self.rag.run({
                    "action": "search",
                    "query": query,
                    "limit": 5,
                    "min_score": 0.2
                })
                if isinstance(result, str):
                    return [{"content": result, "score": 0.5, "source": "rag"}]
                elif isinstance(result, list):
                    return result
            except:
                pass
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
    
    def _extract_keywords(self, description: str) -> List[str]:
        """
        从故障描述中提取关键词
        
        Args:
            description: 故障描述
            
        Returns:
            List[str]: 关键词列表
        """
        try:
            prompt = f"""请从以下故障描述中提取关键词，用于知识图谱查询。
            
【故障描述】
{description}

请提取以下类型的关键词（每类1-3个，用逗号分隔）：
1. 设备型号（如鹰击-83、东风-15、歼-20等）
2. 制造商或研制单位名称
3. 故障类型或现象（如信号丢失、推力下降、液压泄漏等）
4. 相关部件名称（如制导系统、发动机、雷达等）

只返回关键词，用逗号分隔，不要其他内容。"""

            messages = [
                {"role": "system", "content": "你是一个关键词提取助手。"},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.invoke(messages)
            keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
            return keywords[:10]  # 最多10个关键词
            
        except Exception as e:
            logger.warning(f"⚠️ 关键词提取失败: {e}")
            # 简单分词作为备选
            return description.split()[:5]
    
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
                        "text": "你是一个专业的航空维修诊断专家。请分析这张故障照片，用中文回答：1) 这是什么设备/部件？2) 故障现象是什么？3) 损伤程度如何？4) 建议如何处理？请简洁回答。"
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
        keywords = self._extract_keywords(description)
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
            yield ("step", f"✅ 从知识图谱找到 {len(neo4j_results)} 条相关信息")
        
        # 查询 Qdrant
        yield ("step", "📚 正在查询向量知识库 (Qdrant)...")
        qdrant_results = self._retrieve_knowledge(description)
        if qdrant_results:
            yield ("rag", qdrant_results)
            all_evidence.extend(qdrant_results[:5])
            yield ("step", f"✅ 从向量库找到 {len(qdrant_results)} 条相关记录")
        
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
        context = self._build_context(description, neo4j_results, qdrant_results, image_analysis)
        
        # LLM 判断是否需要更多信息
        need_more = False
        if len(neo4j_results) < 2 and len(qdrant_results) < 2:
            need_more = True
            yield ("step", "📊 检索结果较少，尝试扩大搜索范围...")
        
        # 第二轮（如果需要）
        if need_more and self.max_rounds >= 2:
            yield ("step", "🔍 第2轮：扩大搜索范围...")
            
            # 使用更宽泛的关键词
            broader_keywords = self._extract_broader_keywords(description, keywords)
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
                    yield ("step", f"✅ 第2轮从知识图谱找到 {len(neo4j_results_2)} 条信息")
                
                # 再次查询 Qdrant（使用不同角度的查询）
                broader_query = f"{description} {' '.join(broader_keywords[:3])}"
                qdrant_results_2 = self._retrieve_knowledge(broader_query)
                if qdrant_results_2:
                    yield ("rag", qdrant_results_2)
                    all_evidence.extend(qdrant_results_2[:3])
                    yield ("step", f"✅ 第2轮从向量库找到 {len(qdrant_results_2)} 条记录")
        
        # 最终诊断
        yield ("step", "🧠 正在综合分析所有证据...")
        
        # 流式输出分析过程
        analysis_prompt = self._build_analysis_prompt(description, all_evidence, image_analysis)
        messages = [
            {"role": "system", "content": "你是一个专业的装备保障诊断专家，精通飞机、导弹等装备的故障诊断。"},
            {"role": "user", "content": analysis_prompt}
        ]
        
        analysis_text = ""
        for chunk in self.llm.stream_invoke(messages):
            analysis_text += chunk
            yield ("analysis", chunk)
        
        # 结构化诊断
        yield ("step", "📋 正在生成结构化诊断...")
        diagnosis_result = self._analyze_with_llm(description, all_evidence, image_analysis)
        
        # 损伤评估
        severity = self.assess_severity(diagnosis_result)
        
        # 记录
        self._record_diagnosis(description, diagnosis_result, severity)
        
        # 去重证据
        unique_evidence = self._deduplicate_evidence(all_evidence)
        
        final = {
            "success": True,
            "description": description,
            "image_stored": image_stored,
            "diagnosis": diagnosis_result,
            "severity": severity,
            "knowledge_references": unique_evidence[:10],
            "analysis_text": analysis_text,
            "neo4j_count": len([e for e in all_evidence if e.get("source") == "neo4j"]),
            "qdrant_count": len([e for e in all_evidence if e.get("source") != "neo4j"]),
            "timestamp": datetime.now().isoformat()
        }
        yield ("diagnosis", final)
    
    def _extract_broader_keywords(self, description: str, original_keywords: List[str]) -> List[str]:
        """提取更宽泛的关键词"""
        try:
            prompt = f"""基于以下故障描述和已提取的关键词，请提供更宽泛的搜索关键词。

【故障描述】
{description}

【已提取关键词】
{', '.join(original_keywords)}

请提供相关的上位概念或同义词（如 "CESSNA" -> "aircraft", "engine failure" -> "engine"）。
只返回关键词，用逗号分隔，不要其他内容。"""

            messages = [
                {"role": "system", "content": "你是一个关键词扩展助手。"},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.invoke(messages)
            keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
            # 过滤掉已有的关键词
            new_keywords = [kw for kw in keywords if kw not in original_keywords]
            return new_keywords[:5]
            
        except Exception as e:
            logger.warning(f"⚠️ 关键词扩展失败: {e}")
            return []
    
    def _build_context(self, description: str, neo4j_results: List, 
                       qdrant_results: List, image_analysis: str) -> str:
        """构建上下文"""
        context = f"【故障描述】\n{description}\n"
        
        if neo4j_results:
            context += "\n\n【知识图谱信息】\n"
            for i, r in enumerate(neo4j_results[:5], 1):
                context += f"{i}. {r.get('name', '')} ({r.get('type', '')})\n"
        
        if qdrant_results:
            context += "\n\n【相似案例】\n"
            for i, r in enumerate(qdrant_results[:3], 1):
                content = r.get("content", "")[:200]
                context += f"{i}. {content}\n"
        
        if image_analysis:
            context += f"\n\n【照片分析】\n{image_analysis}\n"
        
        return context
    
    def _build_analysis_prompt(self, description: str, evidence: List, image_analysis: str) -> str:
        """构建分析提示词"""
        evidence_context = ""
        if evidence:
            evidence_context = "\n\n【检索到的证据】\n"
            for i, e in enumerate(evidence[:8], 1):
                source = e.get("source_label", "未知")
                content = e.get("content", "")[:150]
                evidence_context += f"{i}. [{source}] {content}\n"
        
        image_context = ""
        if image_analysis:
            image_context = f"\n\n【照片分析】\n{image_analysis}\n"
        
        return f"""你是一个专业的维修诊断专家。请根据以下信息进行综合分析。

【故障描述】
{description}
{evidence_context}{image_context}

⚠️ 重要原则：
1. 只基于检索到的证据进行分析，不要编造信息
2. 如果证据不足以支撑诊断，请明确告知"信息不足，无法给出可靠诊断"
3. 不要猜测或虚构维修记录中不存在的信息
4. 引用证据时请注明来源

请按以下步骤分析：
1. 识别故障类型和严重程度（基于证据）
2. 分析可能的原因（引用检索到的记录）
3. 评估影响
4. 给出维修建议

如果证据不足，请直接说明需要补充哪些信息。

请用简洁的中文回答。"""
    
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
            
            solution_prompt = f"""你是一个专业的航空维护工程师。请根据以下维护需求分析，提供详细的维护方案。

【维护类型】{fault_type}
【维护要点】{', '.join(causes)}
【建议操作】{', '.join(recommended)}

请按以下格式输出：
1. 维护步骤（按顺序列出，参考AMM手册）
2. 所需工具
3. 所需材料/备件（含件号，如有）
4. 安全注意事项
5. 预计维护时间和难度
6. 维护标准/验收标准

请用简洁的中文回答。"""
        else:
            yield ("step", "🔧 正在生成维修方案...")
            
            fault_type = diagnosis_result.get("fault_type", "未知")
            causes = diagnosis_result.get("possible_causes", [])
            recommended = diagnosis_result.get("recommended_actions", [])
            
            solution_prompt = f"""你是一个专业的装备保障工程师。请根据以下诊断结果，提供详细的维修方案。

【故障类型】{fault_type}
【可能原因】{', '.join(causes)}
【建议操作】{', '.join(recommended)}

请按以下格式输出：
1. 维修步骤（按顺序列出，参考技术手册）
2. 所需工具
3. 所需备件（含件号，如有）
4. 安全注意事项
5. 预计维修时间和难度
6. 是否需要特殊批准

请用简洁的中文回答。"""

        messages = [
            {"role": "system", "content": "你是一个专业的装备保障工程师。"},
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
                          image_analysis: str = "") -> Dict[str, Any]:
        """使用LLM进行诊断分析"""
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
            
            # 构建诊断提示词
            system_prompt = "你是一个专业的维修诊断专家。请根据用户描述的故障现象和检索到的证据进行分析。只返回JSON格式。重要：只基于提供的证据分析，不要编造信息。"
            
            user_prompt = f"""请根据以下故障描述进行分析，并给出诊断结果。

【故障描述】
{description}
{knowledge_context}{image_context}

⚠️ 重要原则：
1. 只基于提供的参考知识进行分析
2. 如果参考知识为空或与故障无关，将 possible_causes 设为 ["信息不足，无法确定"]
3. 不要编造或猜测不存在的维修记录

请以JSON格式返回诊断结果，包含以下字段：
{{
    "fault_type": "故障类型",
    "possible_causes": ["可能原因1", "可能原因2"],
    "impact": "对使用的影响",
    "urgency": "紧急程度（低/中/高）",
    "recommended_actions": ["建议操作1", "建议操作2"],
    "confidence": "置信度（高/中/低）"
}}

请只返回JSON格式，不要有其他内容。"""

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
            
            system_prompt = "你是一个专业的装备保障工程师。请根据诊断结果提供详细的维修方案。只返回JSON格式。"
            
            user_prompt = f"""请根据以下诊断结果，提供详细的维修方案。

【故障类型】
{fault_type}

【可能原因】
{chr(10).join(f'- {c}' for c in causes)}

【建议操作】
{chr(10).join(f'- {a}' for a in recommended)}

请以JSON格式返回维修方案，包含以下字段：
{{
    "repair_steps": [
        {{"step": 1, "action": "操作描述", "tools": ["所需工具"], "notes": "注意事项"}},
        {{"step": 2, "action": "操作描述", "tools": ["所需工具"], "notes": "注意事项"}}
    ],
    "parts_required": [
        {{"name": "备件名称", "quantity": 1, "specification": "规格型号"}}
    ],
    "tools_required": ["工具1", "工具2"],
    "safety_warnings": ["安全警告1", "安全警告2"],
    "estimated_time": "预计维修时间",
    "difficulty": "难度等级（简单/中等/困难）"
}}

请只返回JSON格式，不要有其他内容。"""

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
