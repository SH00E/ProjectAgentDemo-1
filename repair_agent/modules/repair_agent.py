# -*- coding: utf-8 -*-
"""
维修智能体模块
整合知识库、诊断引擎、工单生成器
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from hello_agents.tools import MemoryTool, RAGTool
from hello_agents import HelloAgentsLLM

from .knowledge_base import RepairKnowledgeBase
from .diagnosis_engine import RepairDiagnosisEngine
from .work_order import WorkOrderGenerator

logger = logging.getLogger(__name__)


class RepairAgent:
    """
    维修智能体
    整合知识库管理、故障诊断、工单生成
    """
    
    def __init__(self, user_id: str = "repair_user"):
        """
        初始化维修智能体
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 初始化工具
        self._init_tools()
        
        # 初始化模块
        self._init_modules()
        
        logger.info(f"✅ 维修智能体初始化完成 (用户: {user_id})")
        print(f"✅ 维修智能体初始化完成")
        print(f"   用户ID: {user_id}")
        print(f"   会话ID: {self.session_id}")
    
    def _init_tools(self):
        """初始化工具"""
        # 记忆工具
        self.memory_tool = MemoryTool(
            user_id=self.user_id,
            memory_types=["working", "episodic", "semantic", "perceptual"]
        )
        
        # RAG工具 - 使用航空数据集合
        knowledge_base_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "knowledge"
        )
        
        # 检查航空数据集合是否存在
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        collections = [c.name for c in qdrant.get_collections().collections]
        collection_name = "aviation_knowledge_base" if "aviation_knowledge_base" in collections else "rag_knowledge_base"
        
        self.rag_tool = RAGTool(
            knowledge_base_path=knowledge_base_path,
            collection_name=collection_name,
            rag_namespace="default"
        )
        
        print(f"✅ RAG工具使用集合: {collection_name}")
        
        # LLM
        self.llm = HelloAgentsLLM()
        
        # 视觉LLM（MiMo-V2.5 多模态，用于图片分析）
        self.vision_llm = None
        vision_key = os.getenv("VISION_API_KEY", "").strip()
        if vision_key and vision_key != "你的小米API密钥":
            try:
                self.vision_llm = HelloAgentsLLM(
                    model=os.getenv("VISION_MODEL_ID", "mimo-v2.5"),
                    api_key=vision_key,
                    base_url=os.getenv("VISION_BASE_URL", "https://api.xiaomimimo.com/v1"),
                )
                print("✅ 视觉模型已启用 (MiMo-V2.5)")
            except Exception as e:
                logger.warning(f"⚠️ 视觉模型初始化失败: {e}")
        else:
            print("ℹ️ 视觉模型未配置（图片分析功能不可用）")
        
        print("✅ 工具初始化完成 (MemoryTool, RAGTool, LLM)")
    
    def _init_modules(self):
        """初始化模块"""
        # 知识库管理
        self.knowledge_base = RepairKnowledgeBase(
            rag_tool=self.rag_tool,
            memory_tool=self.memory_tool
        )
        
        # 诊断引擎
        self.diagnosis_engine = RepairDiagnosisEngine(
            rag_tool=self.rag_tool,
            memory_tool=self.memory_tool,
            llm=self.llm,
            vision_llm=self.vision_llm
        )
        
        # 工单生成器
        self.work_order_generator = WorkOrderGenerator()
        
        print("✅ 模块初始化完成 (知识库, 诊断引擎, 工单生成器)")
    
    # ==================== 核心功能 ====================
    
    def process_request(self, description: str, 
                        image_path: str = None) -> Dict[str, Any]:
        """
        处理用户请求 - 完整的诊断流程
        
        Args:
            description: 故障描述
            image_path: 现场照片路径 (可选)
            
        Returns:
            Dict: 包含诊断结果、维修方案、工单
        """
        try:
            print(f"\n{'='*60}")
            print(f"🔧 开始处理维修请求")
            print(f"{'='*60}")
            
            # 步骤1: 故障诊断
            print(f"\n📋 步骤1: 故障诊断...")
            diagnosis_result = self.diagnosis_engine.diagnose(
                description, image_path
            )
            
            if not diagnosis_result.get("success"):
                return {
                    "success": False,
                    "error": diagnosis_result.get("error", "诊断失败")
                }
            
            # 步骤2: 推荐维修方案
            print(f"🔧 步骤2: 生成维修方案...")
            solution = self.diagnosis_engine.recommend_solution(
                diagnosis_result.get("diagnosis", {})
            )
            
            # 步骤3: 生成工单
            print(f"📋 步骤3: 生成维修工单...")
            work_order = self.work_order_generator.generate(
                description=description,
                diagnosis=diagnosis_result.get("diagnosis", {}),
                solution=solution,
                severity=diagnosis_result.get("severity")
            )
            
            # 步骤4: 记录到记忆
            print(f"💾 步骤4: 保存记录...")
            self._record_process(description, diagnosis_result, work_order)
            
            # 格式化输出
            order_text = self.work_order_generator.format_order_text(work_order)
            
            print(f"\n✅ 处理完成!")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "description": description,
                "diagnosis": diagnosis_result,
                "solution": solution,
                "work_order": work_order,
                "work_order_text": order_text
            }
            
        except Exception as e:
            logger.error(f"❌ 处理请求失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_request_stream(self, description: str, image_path: str = None):
        """
        流式处理用户请求 - 逐步 yield 中间过程和最终结果
        
        Yields:
            ("step", "步骤描述")
            ("rag", knowledge_results)
            ("analysis", chunk) — LLM流式分析
            ("solution_text", chunk) — LLM流式方案
            ("result", final_dict) — 最终完整结果
        """
        try:
            # 流式诊断
            diagnosis_result = None
            for kind, data in self.diagnosis_engine.diagnose_with_stream(description, image_path):
                if kind == "diagnosis":
                    diagnosis_result = data
                else:
                    yield (kind, data)
            
            if not diagnosis_result or not diagnosis_result.get("success"):
                yield ("result", {"success": False, "error": "诊断失败"})
                return
            
            # 流式推荐方案
            solution = None
            for kind, data in self.diagnosis_engine.recommend_solution_stream(
                diagnosis_result.get("diagnosis", {})
            ):
                if kind == "solution":
                    solution = data
                else:
                    yield (kind, data)
            
            # 生成工单
            yield ("step", "📋 正在生成维修工单...")
            work_order = self.work_order_generator.generate(
                description=description,
                diagnosis=diagnosis_result.get("diagnosis", {}),
                solution=solution,
                severity=diagnosis_result.get("severity")
            )
            
            # 记录
            self._record_process(description, diagnosis_result, work_order)
            
            order_text = self.work_order_generator.format_order_text(work_order)
            
            yield ("result", {
                "success": True,
                "description": description,
                "diagnosis": diagnosis_result,
                "solution": solution,
                "work_order": work_order,
                "work_order_text": order_text
            })
            
        except Exception as e:
            logger.error(f"❌ 处理请求失败: {e}")
            yield ("result", {"success": False, "error": str(e)})
    
    def _record_process(self, description: str, diagnosis: Dict, 
                        work_order: Dict):
        """记录处理过程"""
        try:
            order_id = work_order.get("order_info", {}).get("order_id", "N/A")
            fault_type = diagnosis.get("diagnosis", {}).get("fault_type", "未知")
            
            self.memory_tool.run({
                "action": "add",
                "content": f"完成维修处理: {description[:50]}... | 工单: {order_id} | 故障类型: {fault_type}",
                "memory_type": "episodic",
                "importance": 0.9,
                "topic": "repair_process"
            })
        except Exception as e:
            logger.warning(f"⚠️ 记录处理过程失败: {e}")
    
    # ==================== 知识库管理接口 ====================
    
    def load_manual(self, file_path: str, device_type: str = None) -> Dict:
        """导入维修手册"""
        return self.knowledge_base.load_manual(file_path, device_type)
    
    def add_case(self, case_text: str, case_id: str = None) -> Dict:
        """添加维修案例"""
        return self.knowledge_base.add_case(case_text, case_id)
    
    def add_case_structured(self, case_data: Dict) -> Dict:
        """添加结构化维修案例"""
        return self.knowledge_base.add_case_structured(case_data)
    
    def add_fault_code(self, code: str, meaning: str, 
                       solution: str = None) -> Dict:
        """添加故障码"""
        return self.knowledge_base.add_fault_code(code, meaning, solution)
    
    # ==================== 查询接口 ====================
    
    def search_knowledge(self, query: str, limit: int = 5) -> List[Dict]:
        """检索知识库"""
        return self.knowledge_base.search(query, limit)
    
    def ask(self, question: str) -> str:
        """智能问答"""
        return self.knowledge_base.ask(question)
    
    def get_diagnosis_history(self, limit: int = 10) -> List[Dict]:
        """获取诊断历史"""
        return self.diagnosis_engine.get_diagnosis_history(limit)
    
    # ==================== 统计接口 ====================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "knowledge_base": self.knowledge_base.get_stats()
        }
