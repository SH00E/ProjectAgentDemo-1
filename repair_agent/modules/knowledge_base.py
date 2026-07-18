# -*- coding: utf-8 -*-
"""
维修知识库管理模块
负责维修手册、案例、故障码的导入和检索
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class RepairKnowledgeBase:
    """
    维修知识库管理器
    封装RAGTool和MemoryTool，提供维修领域的知识管理接口
    """
    
    def __init__(self, rag_tool, memory_tool):
        """
        初始化知识库管理器
        
        Args:
            rag_tool: RAGTool实例
            memory_tool: MemoryTool实例
        """
        self.rag = rag_tool
        self.memory = memory_tool
        logger.info("✅ 维修知识库管理器初始化完成")
    
    # ==================== 维修手册管理 ====================
    
    def load_manual(self, file_path: str, device_type: str = None, 
                    metadata: Dict = None) -> Dict[str, Any]:
        """
        导入维修手册
        
        Args:
            file_path: 手册文件路径 (PDF/Word/Excel/Markdown)
            device_type: 设备类型 (如：CESSNA 172, BOEING 737)
            metadata: 额外元数据
            
        Returns:
            Dict: 导入结果
        """
        try:
            if not os.path.exists(file_path):
                return {"success": False, "message": f"文件不存在: {file_path}"}
            
            # 构建元数据
            doc_metadata = {
                "source_type": "manual",
                "device_type": device_type or "未知",
                "import_time": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            # 使用RAGTool导入文档
            result = self.rag.run({
                "action": "add_document",
                "file_path": file_path
            })
            if isinstance(result, str) and "❌" in result:
                logger.error(f"\u26a0\ufe0f RAG\u5bfc\u5165\u5931\u8d25: {result}")
                return {"success": False, "message": f"\u5bfc\u5165\u5931\u8d25: {result}"}
            
            # 记录导入事件到记忆
            filename = os.path.basename(file_path)
            self.memory.run({
                "action": "add",
                "content": f"导入维修手册: {filename} (设备类型: {device_type})",
                "memory_type": "episodic",
                "importance": 0.7,
                "topic": "knowledge_import"
            })
            
            logger.info(f"✅ 成功导入维修手册: {filename}")
            return {
                "success": True,
                "message": f"成功导入维修手册: {filename}",
                "file": filename,
                "device_type": device_type
            }
            
        except Exception as e:
            logger.error(f"❌ 导入维修手册失败: {e}")
            return {"success": False, "message": f"导入失败: {str(e)}"}
    
    def load_manuals_batch(self, file_paths: List[str], 
                           device_type: str = None) -> Dict[str, Any]:
        """
        批量导入维修手册
        
        Args:
            file_paths: 文件路径列表
            device_type: 设备类型
            
        Returns:
            Dict: 导入结果
        """
        results = []
        success_count = 0
        
        for file_path in file_paths:
            result = self.load_manual(file_path, device_type)
            results.append(result)
            if result["success"]:
                success_count += 1
        
        return {
            "success": success_count > 0,
            "message": f"批量导入完成: {success_count}/{len(file_paths)} 成功",
            "results": results
        }
    
    # ==================== 维修案例管理 ====================
    
    def add_case(self, case_text: str, case_id: str = None,
                 metadata: Dict = None) -> Dict[str, Any]:
        """
        添加维修案例
        
        Args:
            case_text: 案例文本内容
            case_id: 案例ID (可选，自动生成)
            metadata: 额外元数据
            
        Returns:
            Dict: 添加结果
        """
        try:
            # 生成案例ID
            if case_id is None:
                case_id = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 构建元数据
            case_metadata = {
                "source_type": "case",
                "case_id": case_id,
                "import_time": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            # 使用RAGTool添加文本
            result = self.rag.run({
                "action": "add_text",
                "text": case_text,
                "document_id": case_id
            })
            if isinstance(result, str) and "❌" in result:
                logger.error(f"\u26a0\ufe0f RAG\u6dfb\u52a0\u6848\u4f8b\u5931\u8d25: {result}")
                return {"success": False, "message": f"\u6dfb\u52a0\u5931\u8d25: {result}"}
            
            # 记录到记忆
            self.memory.run({
                "action": "add",
                "content": f"添加维修案例: {case_id}",
                "memory_type": "episodic",
                "importance": 0.8,
                "topic": "case_add"
            })
            
            logger.info(f"✅ 成功添加维修案例: {case_id}")
            return {
                "success": True,
                "message": f"成功添加维修案例: {case_id}",
                "case_id": case_id
            }
            
        except Exception as e:
            logger.error(f"❌ 添加维修案例失败: {e}")
            return {"success": False, "message": f"添加失败: {str(e)}"}
    
    def add_case_structured(self, case_data: Dict) -> Dict[str, Any]:
        """
        添加结构化维修案例
        
        Args:
            case_data: 结构化案例数据，格式：
                {
                    "title": "案例标题",
                    "device_type": "设备类型",
                    "fault_symptom": "故障现象",
                    "fault_cause": "故障原因",
                    "solution": "解决方案",
                    "parts_used": ["备件1", "备件2"],
                    "technician": "维修人员",
                    "date": "维修日期"
                }
                
        Returns:
            Dict: 添加结果
        """
        try:
            # 将结构化数据转换为文本
            case_text = self._format_case_text(case_data)
            
            # 提取元数据
            metadata = {
                "device_type": case_data.get("device_type"),
                "fault_symptom": case_data.get("fault_symptom"),
                "technician": case_data.get("technician")
            }
            
            return self.add_case(case_text, metadata=metadata)
            
        except Exception as e:
            logger.error(f"❌ 添加结构化案例失败: {e}")
            return {"success": False, "message": f"添加失败: {str(e)}"}
    
    def _format_case_text(self, case_data: Dict) -> str:
        """将结构化案例数据格式化为文本"""
        lines = []
        lines.append(f"【维修案例】{case_data.get('title', '未命名案例')}")
        lines.append(f"设备类型: {case_data.get('device_type', '未知')}")
        lines.append(f"故障现象: {case_data.get('fault_symptom', '无')}")
        lines.append(f"故障原因: {case_data.get('fault_cause', '无')}")
        lines.append(f"解决方案: {case_data.get('solution', '无')}")
        
        parts = case_data.get('parts_used', [])
        if parts:
            lines.append(f"使用备件: {', '.join(parts)}")
        
        lines.append(f"维修人员: {case_data.get('technician', '未知')}")
        lines.append(f"维修日期: {case_data.get('date', '未知')}")
        
        return "\n".join(lines)
    
    # ==================== 故障码管理 ====================
    
    def add_fault_code(self, code: str, meaning: str, 
                       solution: str = None,
                       device_type: str = None) -> Dict[str, Any]:
        """
        添加故障码
        
        Args:
            code: 故障码
            meaning: 故障含义
            solution: 解决方案
            device_type: 设备类型
            
        Returns:
            Dict: 添加结果
        """
        try:
            # 构建故障码文本
            fault_text = f"【故障码】{code}\n含义: {meaning}"
            if solution:
                fault_text += f"\n解决方案: {solution}"
            
            doc_id = f"fault_code_{code}"
            
            # 使用RAGTool添加
            result = self.rag.run({
                "action": "add_text",
                "text": fault_text,
                "document_id": doc_id
            })
            if isinstance(result, str) and "❌" in result:
                logger.error(f"\u26a0\ufe0f RAG\u6dfb\u52a0\u6545\u969c\u7801\u5931\u8d25: {result}")
                return {"success": False, "message": f"\u6dfb\u52a0\u5931\u8d25: {result}"}
            
            logger.info(f"✅ 成功添加故障码: {code}")
            return {
                "success": True,
                "message": f"成功添加故障码: {code}",
                "code": code
            }
            
        except Exception as e:
            logger.error(f"❌ 添加故障码失败: {e}")
            return {"success": False, "message": f"添加失败: {str(e)}"}
    
    # ==================== 知识检索 ====================
    
    def search(self, query: str, limit: int = 5, 
               min_score: float = 0.3) -> List[Dict]:
        """
        检索知识库
        
        Args:
            query: 查询内容
            limit: 返回结果数量
            min_score: 最小相似度分数
            
        Returns:
            List[Dict]: 检索结果列表
        """
        try:
            result = self.rag.run({
                "action": "search",
                "query": query,
                "limit": limit,
                "min_score": min_score,
                "enable_advanced_search": True,
                "include_citations": True
            })

            if isinstance(result, str):
                if "未找到" in result or "❌" in result:
                    return []
                return self._parse_search_result(result)
            if isinstance(result, list):
                return result
            return []
            
        except Exception as e:
            logger.error(f"❌ 知识检索失败: {e}")
            return []
    
    def ask(self, question: str, limit: int = 5) -> str:
        """
        智能问答
        
        Args:
            question: 问题
            limit: 检索结果数量
            
        Returns:
            str: 回答
        """
        try:
            result = self.rag.run({
                "action": "ask",
                "question": question,
                "limit": limit,
                "enable_advanced_search": True,
                "include_citations": True
            })
            return result
            
        except Exception as e:
            logger.error(f"❌ 智能问答失败: {e}")
            return f"问答失败: {str(e)}"
    
    def _parse_search_result(self, result_text: str) -> List[Dict]:
        results = []
        lines = result_text.strip().split("\n")
        current = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith("\U0001f50d") or line.startswith("\U0001f4ca"):
                continue
            if re.match(r"^\d+\.", line):
                if current and current.get("content"):
                    results.append(current)
                current = {"content": line, "score": 0.6}
            elif current is not None:
                if current.get("content"):
                    current["content"] += " " + line
        if current and current.get("content"):
            results.append(current)
        return results if results else [
            {"content": result_text[:200], "score": 0.5}
        ]
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        try:
            rag_stats = self.rag.run({"action": "stats"})
            memory_stats = self.memory.run({"action": "stats"})
            
            return {
                "rag_stats": rag_stats,
                "memory_stats": memory_stats
            }
        except Exception as e:
            return {"error": str(e)}
