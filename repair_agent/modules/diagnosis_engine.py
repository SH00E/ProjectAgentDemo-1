# -*- coding: utf-8 -*-
"""
故障诊断引擎模块
负责故障诊断、损伤评估、方案推荐
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
    结合RAG知识库和LLM进行智能诊断
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
    
    def _retrieve_knowledge(self, query: str) -> List[Dict]:
        """检索相关知识 - 直接使用Qdrant获取完整元数据"""
        try:
            from qdrant_client import QdrantClient
            from hello_agents.memory.embedding import get_text_embedder
            
            # 直接连接Qdrant获取完整结果
            client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
            embedder = get_text_embedder()
            
            # 检查集合是否存在
            collections = [c.name for c in client.get_collections().collections]
            collection_name = "aviation_knowledge_base" if "aviation_knowledge_base" in collections else "rag_knowledge_base"
            
            # 向量化查询
            vector = embedder.encode(query).tolist()
            
            # 搜索
            results = client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=5,
                with_payload=True
            ).points
            
            # 格式化结果
            knowledge_list = []
            for r in results:
                payload = r.payload or {}
                knowledge_list.append({
                    "content": payload.get("content", payload.get("text", "")),
                    "score": r.score,
                    "source": payload.get("source", "unknown"),
                    "record_id": payload.get("record_id", ""),
                    "aircraft_model": payload.get("aircraft_model", ""),
                    "manufacturer": payload.get("manufacturer", ""),
                    "description": payload.get("description", ""),
                    "problem": payload.get("problem", ""),
                    "action": payload.get("action", "")
                })
            
            return knowledge_list
            
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
                        "text": "你是一个专业的消费电子产品维修诊断专家。请分析这张故障照片，用中文回答：1) 这是什么设备？2) 故障现象是什么？3) 损伤程度如何？4) 建议如何处理？请简洁回答。"
                    }
                ]
            }]
            
            response = self.vision_llm.invoke(messages)
            logger.info(f"✅ 图片分析完成")
            return response
            
        except Exception as e:
            logger.warning(f"⚠️ 图片分析失败: {e}")
            return f"（图片分析失败: {str(e)}）"
    
    def diagnose_with_stream(self, description: str, image_path: str = None):
        """
        流式诊断 - 逐步 yield 中间过程
        
        Yields:
            ("step", "步骤描述")  — 进度步骤
            ("rag", knowledge_results) — RAG检索结果
            ("analysis", chunk) — LLM流式分析文本
            ("diagnosis", final_result) — 最终诊断结果
        """
        # 步骤1: 检索知识
        yield ("step", "🔍 正在检索知识库...")
        knowledge_results = self._retrieve_knowledge(description)
        yield ("rag", knowledge_results)
        
        # 步骤2: 分析照片
        image_analysis = ""
        image_stored = False
        if isinstance(image_path, str) and image_path and os.path.exists(image_path):
            if self.vision_llm:
                yield ("step", "👁️ 正在分析现场照片...")
                image_analysis = self._analyze_image(image_path)
                yield ("step", f"📸 照片分析完成")
            else:
                yield ("step", "📸 正在存储现场照片...")
            self._store_image_memory(image_path, description)
            image_stored = True
        
        # 步骤3: LLM流式分析
        yield ("step", "🧠 正在分析故障原因...")
        knowledge_context = ""
        if isinstance(knowledge_results, (list, tuple)) and len(knowledge_results) > 0:
            knowledge_context = "\n\n【参考知识】\n"
            for i, k in enumerate(knowledge_results[:3], 1):
                content = k.get("content", str(k))
                knowledge_context += f"{i}. {content[:500]}\n"
        
        image_context = ""
        if image_analysis:
            image_context = f"\n\n【现场照片分析】\n{image_analysis}\n"
        
        analysis_prompt = f"""你是一个专业的消费电子产品维修诊断专家。请根据以下故障描述，逐步分析可能的原因。

【故障描述】
{description}
{knowledge_context}{image_context}

请按以下格式输出分析过程：
1. 首先识别设备类型和故障现象
2. 然后列出可能的原因（2-3个）
3. 评估紧急程度和对使用的影响
4. 给出初步建议

请用简洁的中文回答。"""

        messages = [
            {"role": "system", "content": "你是一个专业的消费电子产品维修诊断专家。"},
            {"role": "user", "content": analysis_prompt}
        ]
        
        # 流式输出分析过程
        analysis_text = ""
        for chunk in self.llm.stream_invoke(messages):
            analysis_text += chunk
            yield ("analysis", chunk)
        
        # 步骤4: 结构化诊断
        yield ("step", "📋 正在生成结构化诊断...")
        diagnosis_result = self._analyze_with_llm(description, knowledge_results, image_analysis)
        
        # 步骤5: 损伤评估
        severity = self.assess_severity(diagnosis_result)
        
        # 步骤6: 记录
        self._record_diagnosis(description, diagnosis_result, severity)
        
        final = {
            "success": True,
            "description": description,
            "image_stored": image_stored,
            "diagnosis": diagnosis_result,
            "severity": severity,
            "knowledge_references": knowledge_results[:3],
            "analysis_text": analysis_text,
            "timestamp": datetime.now().isoformat()
        }
        yield ("diagnosis", final)
    
    def recommend_solution_stream(self, diagnosis_result: Dict):
        """
        流式推荐维修方案
        
        Yields:
            ("step", "步骤描述")
            ("solution_text", chunk) — LLM流式方案文本
            ("solution", final_solution) — 最终结构化方案
        """
        yield ("step", "🔧 正在生成维修方案...")
        
        fault_type = diagnosis_result.get("fault_type", "未知")
        causes = diagnosis_result.get("possible_causes", [])
        recommended = diagnosis_result.get("recommended_actions", [])
        
        solution_prompt = f"""你是一个专业的消费电子产品维修工程师。请根据以下诊断结果，提供详细的维修方案。

【故障类型】{fault_type}
【可能原因】{', '.join(causes)}
【建议操作】{', '.join(recommended)}

请按以下格式输出：
1. 维修步骤（按顺序列出）
2. 所需工具
3. 所需备件（如有）
4. 安全注意事项
5. 预计维修时间和难度

请用简洁的中文回答。"""

        messages = [
            {"role": "system", "content": "你是一个专业的消费电子产品维修工程师。"},
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
            system_prompt = "你是一个专业的消费电子产品维修诊断专家。请根据用户描述的故障现象进行分析，给出诊断结果。只返回JSON格式。"
            
            user_prompt = f"""请根据以下故障描述进行分析，并给出诊断结果。

【故障描述】
{description}
{knowledge_context}{image_context}

请以JSON格式返回诊断结果，包含以下字段：
{{
    "fault_type": "故障类型（如：屏幕损坏、电源/电池问题、扬声器/音频、外部损坏、内部损坏、软件/固件、配置问题等）",
    "possible_causes": ["可能原因1", "可能原因2", "可能原因3"],
    "impact": "对使用的影响",
    "urgency": "紧急程度（低/中/高）",
    "recommended_actions": ["建议操作1", "建议操作2"]
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
            
            system_prompt = "你是一个专业的消费电子产品维修工程师。请根据诊断结果提供详细的维修方案。只返回JSON格式。"
            
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
            result = self.memory.run({
                "action": "search",
                "query": "故障诊断记录",
                "limit": limit,
                "memory_type": "episodic"
            })
            
            if isinstance(result, str):
                return [{"content": result}]
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取诊断历史失败: {e}")
            return []
