# -*- coding: utf-8 -*-
"""
工单生成模块
根据诊断结果和维修方案生成结构化工单
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkOrderGenerator:
    """
    工单生成器
    生成JSON格式的维修工单
    """
    
    def __init__(self, prefix: str = "WO"):
        """
        初始化工单生成器
        
        Args:
            prefix: 工单编号前缀
        """
        self.prefix = prefix
        self.order_counter = 0
        logger.info("✅ 工单生成器初始化完成")
    
    def generate(self, description: str, diagnosis: Dict, 
                 solution: Dict, severity: Dict = None, mode: str = "repair") -> Dict[str, Any]:
        """
        生成工单
        
        Args:
            description: 故障/维护描述
            diagnosis: 诊断结果
            solution: 维修/维护方案
            severity: 损伤等级评估
            mode: "repair" = 维修工单, "maintenance" = 维护工单
            
        Returns:
            Dict: 完整的工单
        """
        try:
            # 生成工单ID
            if mode == "maintenance":
                order_id = self._generate_order_id(prefix="MO")
            else:
                order_id = self._generate_order_id()
            
            # 构建工单
            if mode == "maintenance":
                work_order = {
                    "order_info": self._build_order_info(order_id),
                    "maintenance_description": description,
                    "maintenance": self._build_maintenance_section(diagnosis, severity),
                    "solution": self._build_solution_section(solution),
                    "status": "待执行",
                    "metadata": self._build_metadata(mode="maintenance")
                }
            else:
                work_order = {
                    "order_info": self._build_order_info(order_id),
                    "fault_description": description,
                    "diagnosis": self._build_diagnosis_section(diagnosis, severity),
                    "solution": self._build_solution_section(solution),
                    "status": "待处理",
                    "metadata": self._build_metadata()
                }
            
            logger.info(f"✅ 成功生成工单: {order_id} (模式: {mode})")
            return work_order
            
        except Exception as e:
            logger.error(f"❌ 工单生成失败: {e}")
            return {
                "error": str(e),
                "fault_description": description
            }
    
    def _generate_order_id(self, prefix: str = None) -> str:
        """生成工单ID"""
        if prefix is None:
            prefix = self.prefix
        self.order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:6]
        return f"{prefix}-{timestamp}-{unique_id}"
    
    def _build_order_info(self, order_id: str) -> Dict:
        """构建工单基本信息"""
        return {
            "order_id": order_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "priority": "普通",
            "assigned_to": None
        }
    
    def _build_diagnosis_section(self, diagnosis: Dict, 
                                  severity: Dict = None) -> Dict:
        """构建诊断部分"""
        severity = severity or {"level": "待评估", "description": ""}
        
        return {
            "fault_type": diagnosis.get("fault_type", "未知"),
            "possible_causes": diagnosis.get("possible_causes", []),
            "impact": diagnosis.get("impact", "待评估"),
            "urgency": diagnosis.get("urgency", "中"),
            "severity": {
                "level": severity.get("level", "待评估"),
                "description": severity.get("description", ""),
                "priority": severity.get("priority", 2)
            }
        }
    
    def _build_maintenance_section(self, diagnosis: Dict, 
                                    severity: Dict = None) -> Dict:
        """构建维护分析部分"""
        severity = severity or {"level": "待评估", "description": ""}
        
        return {
            "maintenance_type": diagnosis.get("fault_type", "未知"),
            "maintenance_points": diagnosis.get("possible_causes", []),
            "impact": diagnosis.get("impact", "待评估"),
            "urgency": diagnosis.get("urgency", "中"),
            "complexity": {
                "level": severity.get("level", "待评估"),
                "description": severity.get("description", ""),
                "priority": severity.get("priority", 2)
            }
        }
    
    def _build_solution_section(self, solution: Dict) -> Dict:
        """构建维修方案部分"""
        return {
            "repair_steps": solution.get("repair_steps", []),
            "parts_required": solution.get("parts_required", []),
            "tools_required": solution.get("tools_required", []),
            "safety_warnings": solution.get("safety_warnings", []),
            "estimated_time": solution.get("estimated_time", "待评估"),
            "difficulty": solution.get("difficulty", "中等")
        }
    
    def _build_metadata(self, mode: str = "repair") -> Dict:
        """构建元数据"""
        return {
            "generated_by": "RepairAgent",
            "version": "1.0",
            "format": "json",
            "mode": mode
        }
    
    def format_order_text(self, work_order: Dict, mode: str = "repair") -> str:
        """
        将工单格式化为可读文本
        
        Args:
            work_order: 工单数据
            mode: "repair" = 维修工单, "maintenance" = 维护工单
            
        Returns:
            str: 格式化的文本
        """
        lines = []
        
        # 工单标题
        order_info = work_order.get("order_info", {})
        lines.append("=" * 60)
        
        if mode == "maintenance":
            lines.append(f"🔧 维护工单")
            lines.append("=" * 60)
            lines.append(f"工单编号: {order_info.get('order_id', 'N/A')}")
            lines.append(f"创建时间: {order_info.get('created_at', 'N/A')}")
            lines.append(f"状态: {work_order.get('status', 'N/A')}")
            lines.append("")
            
            # 维护描述
            lines.append("【维护需求】")
            lines.append(work_order.get("maintenance_description", "无"))
            lines.append("")
            
            # 维护分析
            maintenance = work_order.get("maintenance", {})
            lines.append("【维护分析】")
            lines.append(f"维护类型: {maintenance.get('maintenance_type', '未知')}")
            lines.append(f"影响评估: {maintenance.get('impact', '待评估')}")
            
            complexity = maintenance.get("complexity", {})
            lines.append(f"复杂度: {complexity.get('level', '待评估')}")
            lines.append(f"说明: {complexity.get('description', '')}")
            
            points = maintenance.get("maintenance_points", [])
            if points:
                lines.append("维护要点:")
                for point in points:
                    lines.append(f"  - {point}")
            lines.append("")
            
            # 维护方案
            solution = work_order.get("solution", {})
            lines.append("【维护方案】")
            
            steps = solution.get("repair_steps", [])
            if steps:
                lines.append("维护步骤:")
                for step in steps:
                    step_num = step.get("step", "?")
                    action = step.get("action", "")
                    tools = step.get("tools", [])
                    notes = step.get("notes", "")
                    lines.append(f"  {step_num}. {action}")
                    if tools:
                        lines.append(f"     工具: {', '.join(tools)}")
                    if notes:
                        lines.append(f"     注意: {notes}")
            lines.append("")
            
            # 材料清单
            parts = solution.get("parts_required", [])
            if parts:
                lines.append("【所需材料/备件】")
                for part in parts:
                    name = part.get("name", "")
                    qty = part.get("quantity", 1)
                    spec = part.get("specification", "")
                    lines.append(f"  - {name} x{qty}")
                    if spec:
                        lines.append(f"    规格: {spec}")
                lines.append("")
            
            # 工具清单
            tools = solution.get("tools_required", [])
            if tools:
                lines.append("【所需工具】")
                for tool in tools:
                    lines.append(f"  - {tool}")
                lines.append("")
            
            # 安全提示
            warnings = solution.get("safety_warnings", [])
            if warnings:
                lines.append("⚠️ 【安全提示】")
                for warning in warnings:
                    lines.append(f"  ⚠️ {warning}")
                lines.append("")
            
            # 其他信息
            lines.append("【评估信息】")
            lines.append(f"预计时间: {solution.get('estimated_time', '待评估')}")
            lines.append(f"难度等级: {solution.get('difficulty', '中等')}")
            
        else:
            # 维修工单格式
            lines.append(f"📋 维修工单")
            lines.append("=" * 60)
            lines.append(f"工单编号: {order_info.get('order_id', 'N/A')}")
            lines.append(f"创建时间: {order_info.get('created_at', 'N/A')}")
            lines.append(f"状态: {work_order.get('status', 'N/A')}")
            lines.append("")
            
            # 故障描述
            lines.append("【故障描述】")
            lines.append(work_order.get("fault_description", "无"))
            lines.append("")
            
            # 诊断结果
            diagnosis = work_order.get("diagnosis", {})
            lines.append("【诊断结果】")
            lines.append(f"故障类型: {diagnosis.get('fault_type', '未知')}")
            lines.append(f"影响评估: {diagnosis.get('impact', '待评估')}")
            
            severity = diagnosis.get("severity", {})
            lines.append(f"损伤等级: {severity.get('level', '待评估')}")
            lines.append(f"等级说明: {severity.get('description', '')}")
            
            causes = diagnosis.get("possible_causes", [])
            if causes:
                lines.append("可能原因:")
                for cause in causes:
                    lines.append(f"  - {cause}")
            lines.append("")
            
            # 维修方案
            solution = work_order.get("solution", {})
            lines.append("【维修方案】")
            
            steps = solution.get("repair_steps", [])
            if steps:
                lines.append("维修步骤:")
                for step in steps:
                    step_num = step.get("step", "?")
                    action = step.get("action", "")
                    tools = step.get("tools", [])
                    notes = step.get("notes", "")
                    lines.append(f"  {step_num}. {action}")
                    if tools:
                        lines.append(f"     工具: {', '.join(tools)}")
                    if notes:
                        lines.append(f"     注意: {notes}")
            lines.append("")
            
            # 备件清单
            parts = solution.get("parts_required", [])
            if parts:
                lines.append("【备件清单】")
                for part in parts:
                    name = part.get("name", "")
                    qty = part.get("quantity", 1)
                    spec = part.get("specification", "")
                    lines.append(f"  - {name} x{qty}")
                    if spec:
                        lines.append(f"    规格: {spec}")
                lines.append("")
            
            # 工具清单
            tools = solution.get("tools_required", [])
            if tools:
                lines.append("【所需工具】")
                for tool in tools:
                    lines.append(f"  - {tool}")
                lines.append("")
            
            # 安全警告
            warnings = solution.get("safety_warnings", [])
            if warnings:
                lines.append("⚠️ 【安全警告】")
                for warning in warnings:
                    lines.append(f"  ⚠️ {warning}")
                lines.append("")
            
            # 其他信息
            lines.append("【其他信息】")
            lines.append(f"预计时间: {solution.get('estimated_time', '待评估')}")
            lines.append(f"难度等级: {solution.get('difficulty', '中等')}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def update_order_status(self, work_order: Dict, 
                            new_status: str) -> Dict:
        """
        更新工单状态
        
        Args:
            work_order: 工单数据
            new_status: 新状态
            
        Returns:
            Dict: 更新后的工单
        """
        valid_statuses = ["待处理", "处理中", "已完成", "已取消"]
        
        if new_status not in valid_statuses:
            logger.warning(f"⚠️ 无效状态: {new_status}，使用默认状态'待处理'")
            new_status = "待处理"
        
        work_order["status"] = new_status
        work_order["order_info"]["updated_at"] = datetime.now().isoformat()
        
        return work_order
