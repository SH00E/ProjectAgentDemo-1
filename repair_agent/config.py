# -*- coding: utf-8 -*-
"""
维修智能Agent配置文件
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 知识库配置
KNOWLEDGE_BASE_PATH = str(PROJECT_ROOT / "knowledge")
RAG_NAMESPACE = "repair_kb"
RAG_COLLECTION = "repair_knowledge_base"

# 记忆配置
MEMORY_USER_ID = "repair_user"
MEMORY_TYPES = ["working", "episodic", "semantic", "perceptual"]

# LLM配置 (从环境变量读取)
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "deepseek-v4-pro")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

# Qdrant配置
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# 工单配置
WORK_ORDER_PREFIX = "WO"

# 损伤等级定义
SEVERITY_LEVELS = {
    "轻微": {"description": "不影响正常使用，可选择性修复", "priority": 1},
    "中等": {"description": "可能影响使用或存在安全隐患，建议尽快修复", "priority": 2},
    "严重": {"description": "严重影响使用或存在安全风险，需要立即修复", "priority": 3}
}

logger.debug(f"配置加载完成: 知识库路径={KNOWLEDGE_BASE_PATH}, RAG命名空间={RAG_NAMESPACE}")
