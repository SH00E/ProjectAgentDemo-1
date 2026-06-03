# -*- coding: utf-8 -*-
"""
维修智能助手 Web 界面
使用 FastAPI + 原生 HTML/JS 构建，支持 SSE 流式输出
"""

import os
import sys
import json
import time
import random
import logging
import tempfile
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime

from prompts import fmt_prompt

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.repair_agent import RepairAgent

logger = logging.getLogger(__name__)

# ==================== 案例数据库 ====================

CASES_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory_data", "cases.db")

def init_cases_db():
    """初始化案例数据库"""
    os.makedirs(os.path.dirname(CASES_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CASES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT DEFAULT 'repair',
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
        cursor.execute("ALTER TABLE cases ADD COLUMN case_type TEXT DEFAULT 'repair'")
    if 'maintenance_type' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_type TEXT")
    if 'maintenance_cycle' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_cycle TEXT")
    if 'maintenance_standard' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN maintenance_standard TEXT")
    
    conn.commit()
    conn.close()

def save_case_to_db(case_data: Dict) -> int:
    """保存案例到数据库"""
    conn = sqlite3.connect(CASES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cases (case_type, title, device_type, fault_symptom, fault_cause, solution, parts_used, technician, notes, case_text, maintenance_type, maintenance_cycle, maintenance_standard)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case_data.get("case_type", "repair"),
        case_data.get("title", ""),
        case_data.get("device_type", ""),
        case_data.get("fault_symptom", ""),
        case_data.get("fault_cause", ""),
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

def load_cases_from_db(limit: int = 50, offset: int = 0, case_type: str = None) -> Dict:
    """从数据库加载案例（支持分页和类型过滤）"""
    conn = sqlite3.connect(CASES_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 构建查询
    where_clause = ""
    params = []
    
    if case_type and case_type in ('repair', 'maintenance'):
        where_clause = "WHERE case_type = ?"
        params.append(case_type)
    
    # 获取总数
    count_sql = f"SELECT COUNT(*) FROM cases {where_clause}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    # 获取分页数据
    query_params = params + [limit, offset]
    cursor.execute(f'SELECT * FROM cases {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?', query_params)
    rows = cursor.fetchall()
    conn.close()
    
    cases = []
    for row in rows:
        cases.append({
            "id": row["id"],
            "case_type": row["case_type"] if "case_type" in row.keys() else "repair",
            "title": row["title"],
            "device_type": row["device_type"],
            "fault_symptom": row["fault_symptom"],
            "fault_cause": row["fault_cause"],
            "solution": row["solution"],
            "parts_used": row["parts_used"],
            "technician": row["technician"],
            "notes": row["notes"],
            "case_text": row["case_text"],
            "maintenance_type": row["maintenance_type"] if "maintenance_type" in row.keys() else "",
            "maintenance_cycle": row["maintenance_cycle"] if "maintenance_cycle" in row.keys() else "",
            "maintenance_standard": row["maintenance_standard"] if "maintenance_standard" in row.keys() else "",
            "created_at": row["created_at"]
        })
    return {"cases": cases, "total": total}

def delete_case_from_db(case_id: int) -> bool:
    """从数据库删除案例"""
    conn = sqlite3.connect(CASES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_case_by_id(case_id: int) -> Optional[Dict]:
    """根据ID获取案例"""
    conn = sqlite3.connect(CASES_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row["id"],
            "case_type": row["case_type"] if "case_type" in row.keys() else "repair",
            "title": row["title"],
            "device_type": row["device_type"],
            "fault_symptom": row["fault_symptom"],
            "fault_cause": row["fault_cause"],
            "solution": row["solution"],
            "parts_used": row["parts_used"],
            "technician": row["technician"],
            "notes": row["notes"],
            "case_text": row["case_text"],
            "maintenance_type": row["maintenance_type"] if "maintenance_type" in row.keys() else "",
            "maintenance_cycle": row["maintenance_cycle"] if "maintenance_cycle" in row.keys() else "",
            "maintenance_standard": row["maintenance_standard"] if "maintenance_standard" in row.keys() else "",
            "created_at": row["created_at"]
        }
    return None

# 初始化数据库
init_cases_db()

# ==================== 全局状态 ====================

agent_state = {"agent": None, "init_error": None, "initting": False}

def auto_init_agent():
    """初始化 Agent（同步）"""
    if agent_state["agent"] is not None:
        return True
    if agent_state["initting"]:
        return False
    agent_state["initting"] = True
    t0 = time.time()
    try:
        agent_state["agent"] = RepairAgent(user_id="web_user")
        agent_state["init_error"] = None
        elapsed = time.time() - t0
        logger.info(f"✅ Agent 初始化完成（{elapsed:.1f}s）")
        return True
    except Exception as e:
        agent_state["init_error"] = str(e)
        elapsed = time.time() - t0
        logger.error(f"❌ Agent 初始化失败（{elapsed:.1f}s）: {e}")
        return False
    finally:
        agent_state["initting"] = False

# ==================== FastAPI App ====================

app = FastAPI(title="保障智能助手")

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 本地开发模式禁用静态文件缓存
@app.middleware("http")
async def disable_static_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

# ==================== SSE 流式输出 ====================

def sse_event(event: str, data) -> str:
    """格式化 SSE 事件"""
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False)
    elif isinstance(data, str):
        data_str = data
    else:
        data_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data_str}\n\n"

def diagnosis_stream(description: str, image_path: str = None, mode: str = "repair"):
    """诊断/维护流式生成器
    
    mode: "repair" = 故障诊断, "maintenance" = 日常维护
    """
    agent = agent_state["agent"]
    if agent is None:
        yield sse_event("error", {"message": "系统未就绪，请稍候"})
        return

    for kind, data in agent.process_request_stream(description, image_path, mode=mode):
        if kind == "step":
            yield sse_event("step", {"text": data})
        elif kind == "neo4j":
            # 处理 Neo4j 知识图谱结果
            if data:
                results = []
                for r in data:
                    results.append({
                        "type": r.get("type", ""),
                        "name": r.get("name", ""),
                        "details": r
                    })
                yield sse_event("neo4j", {"results": results, "total": len(data)})
            else:
                yield sse_event("neo4j", {"results": [], "total": 0})
        elif kind == "rag":
            if data:
                results = []
                for r in data:
                    # 构建证据链信息
                    source = r.get("source", "unknown")
                    source_label = "FAA事故数据" if source == "faa" else "MaintNet维修数据" if source == "maintnet" else "知识图谱" if source == "neo4j" else "知识库"
                    
                    # 计算相似度等级：基于关键词命中分数
                    final_score = r.get("score", 0)
                    if final_score >= 1.0:
                        relevance = "高"
                    elif final_score >= 0.5:
                        relevance = "中"
                    else:
                        relevance = "低"
                    
                    results.append({
                        "content": r.get("content", str(r))[:200],
                        "score": round(r.get("score", 0), 3),
                        "relevance": relevance,
                        "source": source,
                        "source_label": source_label,
                        "record_id": r.get("record_id", ""),
                        "aircraft_model": r.get("aircraft_model", ""),
                        "manufacturer": r.get("manufacturer", ""),
                        "description": r.get("description", "")[:150],
                        "problem": r.get("problem", "")[:150],
                        "action": r.get("action", "")[:150],
                        "matched_tokens": r.get("matched_tokens", 0),
                        "total_tokens": r.get("total_tokens", 0),
                    })
                yield sse_event("rag", {"results": results, "total": len(data)})
            else:
                yield sse_event("rag", {"results": [], "total": 0})
        elif kind == "analysis":
            yield sse_event("analysis", {"chunk": data})
        elif kind == "solution_text":
            yield sse_event("solution_text", {"chunk": data})
        elif kind == "diagnosis":
            diag = data.get("diagnosis", data)
            sev = data.get("severity", {})
            
            # 获取证据链
            knowledge_refs = data.get("knowledge_references", [])
            evidence_chain = []
            for ref in knowledge_refs:
                source = ref.get("source", "unknown")
                source_label = "FAA事故数据" if source == "faa" else "MaintNet维修数据" if source == "maintnet" else "知识图谱" if source == "neo4j" else "知识库"
                
                # 处理 Neo4j 特有的字段
                details = ref.get("details", {})
                aircraft_models = details.get("aircraft_models", [])
                incident_types = details.get("incident_types", [])
                
                ev_score = ref.get("score", 0)
                if ev_score >= 1.0:
                    ev_rel = "高"
                elif ev_score >= 0.5:
                    ev_rel = "中"
                else:
                    ev_rel = "低"
                evidence_chain.append({
                    "content": ref.get("content", "")[:200],
                    "score": round(ref.get("score", 0), 3),
                    "relevance": ev_rel,
                    "source": source,
                    "source_label": source_label,
                    "record_id": ref.get("record_id", ""),
                    "aircraft_model": ref.get("aircraft_model", "") or (aircraft_models[0] if aircraft_models else ""),
                    "manufacturer": ref.get("manufacturer", ""),
                    "description": ref.get("description", "")[:150],
                    "problem": ref.get("problem", "")[:150],
                    "action": ref.get("action", "")[:150],
                    "case_type": ref.get("case_type", ""),
                    "matched_tokens": ref.get("matched_tokens", 0),
                    "total_tokens": ref.get("total_tokens", 0),
                })
            
            yield sse_event("diagnosis", {
                "fault_type": diag.get("fault_type", "未知"),
                "urgency": diag.get("urgency", "中"),
                "severity_level": sev.get("level", "待评估"),
                "severity_desc": sev.get("description", ""),
                "possible_causes": diag.get("possible_causes", []),
                "evidence_chain": evidence_chain,
                "neo4j_count": data.get("neo4j_count", 0),
                "qdrant_count": data.get("qdrant_count", 0)
            })
        elif kind == "solution":
            steps = data.get("repair_steps", [])
            yield sse_event("solution", {
                "repair_steps": steps,
                "estimated_time": data.get("estimated_time", ""),
                "difficulty": data.get("difficulty", ""),
                "parts_required": data.get("parts_required", []),
                "tools_required": data.get("tools_required", []),
                "safety_warnings": data.get("safety_warnings", [])
            })
        elif kind == "result":
            if data.get("success"):
                wo = data.get("work_order", {})
                yield sse_event("result", {
                    "success": True,
                    "work_order": wo
                })
            else:
                yield sse_event("error", {"message": data.get("error", "未知错误")})

# ==================== API 路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回主页"""
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """返回数据大屏页面"""
    html_path = os.path.join(static_dir, "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if agent_state["agent"] is not None:
        return {"status": "ready", "message": "✅ 保障智能助手已就绪"}
    elif agent_state["initting"]:
        return {"status": "initializing", "message": "⏳ 正在初始化..."}
    elif agent_state["init_error"]:
        return {"status": "error", "message": f"❌ 初始化失败: {agent_state['init_error']}"}
    else:
        return {"status": "not_initialized", "message": "⏳ 等待初始化..."}

@app.post("/api/init")
async def init_agent():
    """手动触发初始化"""
    success = auto_init_agent()
    if success:
        return {"success": True, "message": "✅ 初始化完成"}
    else:
        return {"success": False, "message": f"❌ 初始化失败: {agent_state.get('init_error', '未知错误')}"}

@app.post("/api/diagnose")
async def diagnose(
    description: str = Form(...),
    image: UploadFile = File(None),
    mode: str = Form("repair")
):
    """提交诊断/维护请求，返回 SSE 流
    
    mode: "repair" = 故障诊断, "maintenance" = 日常维护
    """
    if agent_state["agent"] is None:
        return JSONResponse(
            status_code=503,
            content={"error": "系统未就绪，请稍候"}
        )

    if not description.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "请输入描述"}
        )

    # 处理图片
    image_path = None
    if image is not None:
        try:
            # 保存到临时文件
            test_img_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "test_images"
            )
            os.makedirs(test_img_dir, exist_ok=True)

            suffix = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False,
                dir=test_img_dir
            )
            content = await image.read()
            tmp.write(content)
            tmp.close()
            image_path = tmp.name
            logger.info(f"📸 图片已保存: {image_path}")
        except Exception as e:
            logger.warning(f"图片保存失败: {e}")

    return StreamingResponse(
        diagnosis_stream(description, image_path, mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/search")
async def search_knowledge(request: Request):
    """知识检索 - 混合搜索（关键词 + 向量）- 支持分页"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})

    body = await request.json()
    query = body.get("query", "").strip()
    page = body.get("page", 1)
    page_size = body.get("page_size", 20)
    
    # 确保page和page_size是整数
    try:
        page = int(page) if page else 1
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size) if page_size else 20
    except (TypeError, ValueError):
        page_size = 20
    
    if not query:
        return JSONResponse(status_code=400, content={"error": "请输入查询内容"})

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchText, MatchValue
        from hello_agents.memory.embedding import get_text_embedder
        
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
        client = QdrantClient(url=qdrant_url, trust_env=not is_local)
        embedder = get_text_embedder()
        
        def _normalize(text):
            for sep in ['-', '_', ' ', '　', '/', '\\', '·', '•']:
                text = text.replace(sep, '')
            return text.lower().strip()

        def _split_query_tokens(q):
            tokens = [q]
            for sep in [' ', ',', '，', '、', '/', '|', '-', '_']:
                for part in q.split(sep):
                    part = part.strip()
                    if part and len(part) >= 2 and part not in tokens:
                        tokens.append(part)
            for part in list(tokens):
                if len(part) >= 4:
                    for win_size in [2, 3]:
                        for k in range(len(part) - win_size + 1):
                            token = part[k:k+win_size]
                            if token not in tokens:
                                tokens.append(token)
            return tokens

        def _compute_keyword_score(record, query_tokens, full_q):
            text = " ".join([
                str(record.get("content", "")),
                str(record.get("description", "")),
                str(record.get("problem", "")),
                str(record.get("action", "")),
                str(record.get("aircraft_model", ""))
            ])
            text_norm = _normalize(text)
            total = len(query_tokens)
            if total == 0:
                return 0.0, 0, 0
            matched = 0
            for token in query_tokens:
                tn = _normalize(token)
                if tn and tn in text_norm:
                    matched += 1
            ratio = matched / total
            if matched == total and total > 1:
                boost = 1.5
            elif ratio >= 0.67:
                boost = 1.2
            else:
                boost = 1.0
            fq_norm = _normalize(full_q)
            if fq_norm and fq_norm in text_norm:
                boost = max(boost, 1.8)
            return ratio * boost, matched, total

        # 先用LLM提取关键词，再检索
        try:
            llm = agent_state["agent"].llm
            kw_prompt = fmt_prompt("extract_keywords", "user", description=query)
            kw_messages = [
                {"role": "system", "content": fmt_prompt("extract_keywords", "system")},
                {"role": "user", "content": kw_prompt}
            ]
            kw_response = llm.invoke(kw_messages)
            extracted = [k.strip() for k in kw_response.split(",") if k.strip() and k.strip() != "无"]
            if extracted:
                query_tokens = list(extracted)
                # 为每个关键词生成2-3字滑动窗口
                for kw in extracted:
                    if len(kw) >= 4:
                        for win_size in [2, 3]:
                            for k in range(len(kw) - win_size + 1):
                                token = kw[k:k+win_size]
                                if token not in query_tokens:
                                    query_tokens.append(token)
                logger.info(f"📝 提取到关键词: {extracted}")
            else:
                query_tokens = _split_query_tokens(query)
        except Exception as e:
            logger.warning(f"关键词提取失败，使用拆分: {e}")
            query_tokens = _split_query_tokens(query)

        # ===== 关键词召回 =====
        collections = [c.name for c in client.get_collections().collections]
        keyword_results = {}

        for col_name in collections:
            try:
                kw_conditions = []
                for qp in query_tokens:
                    kw_conditions.extend([
                        FieldCondition(key="content", match=MatchText(text=qp)),
                        FieldCondition(key="text", match=MatchText(text=qp)),
                        FieldCondition(key="description", match=MatchText(text=qp)),
                        FieldCondition(key="description_zh", match=MatchText(text=qp)),
                        FieldCondition(key="problem", match=MatchText(text=qp)),
                        FieldCondition(key="problem_zh", match=MatchText(text=qp)),
                        FieldCondition(key="action", match=MatchText(text=qp)),
                        FieldCondition(key="action_zh", match=MatchText(text=qp)),
                    ])
                kw_filter = Filter(should=kw_conditions)
                kw_scroll = client.scroll(
                    collection_name=col_name,
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
                        }
            except Exception as e:
                logger.warning(f"关键词召回失败({col_name}): {e}")

        # ===== SQLite 关键词召回 =====
        try:
            conn = sqlite3.connect(CASES_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            raw_tokens = [query]
            for sep in [' ', ',', '，', '、', '/', '|', '-', '_']:
                for t in query.split(sep):
                    t = t.strip()
                    if t and len(t) >= 2 and t not in raw_tokens:
                        raw_tokens.append(t)
            sql_conditions = []
            sql_params = []
            for qp in raw_tokens:
                lp = f"%{qp}%"
                sql_conditions.append('''(title LIKE ? OR device_type LIKE ? OR fault_symptom LIKE ?
                          OR fault_cause LIKE ? OR solution LIKE ? OR parts_used LIKE ?
                          OR notes LIKE ? OR maintenance_type LIKE ? OR maintenance_cycle LIKE ?
                          OR maintenance_standard LIKE ?)''')
                sql_params.extend([lp] * 10)
            if sql_conditions:
                cursor.execute('SELECT DISTINCT * FROM cases WHERE ' + ' OR '.join(sql_conditions), sql_params)
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                case_id = row["id"]
                rid = f"CASE_{case_id}"
                if rid in keyword_results:
                    continue
                case_type = row["case_type"] if "case_type" in row.keys() else "repair"
                if case_type == "maintenance":
                    content = f"{row['title']} | 设备: {row['device_type']} | 维护类型: {row['maintenance_type'] if 'maintenance_type' in row.keys() else ''} | 周期: {row['maintenance_cycle'] if 'maintenance_cycle' in row.keys() else ''} | 方案: {row['solution']}"
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
                }
        except Exception as e:
            logger.warning(f"SQLite 搜索失败: {e}")

        # ===== 关键词计分 =====
        result_list = list(keyword_results.values())
        for r in result_list:
            score, matched, total = _compute_keyword_score(r, query_tokens, query)
            r["score"] = score
            r["matched_tokens"] = matched
            r["total_tokens"] = total

        # ===== 向量 fallback =====
        if not result_list:
            logger.info("关键词无结果，启动向量 fallback")
            vector_fallback = {}
            for col_name in collections:
                try:
                    vec_q = embedder.encode(query).tolist()
                    res = client.query_points(
                        collection_name=col_name,
                        query=vec_q,
                        limit=20,
                        with_payload=True
                    ).points
                    for r in res:
                        payload = r.payload or {}
                        rid = payload.get("record_id", str(r.id))
                        if rid not in vector_fallback:
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
                                "case_type": payload.get("case_type", ""),
                                "matched_tokens": 0,
                                "total_tokens": len(query_tokens),
                            }
                except Exception:
                    pass
            result_list = list(vector_fallback.values())

        # 排序
        sorted_results = sorted(result_list, key=lambda x: x["score"], reverse=True)
        
        # 计算分页
        total = len(sorted_results)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_results = sorted_results[start_idx:end_idx]
        
        # 格式化结果
        enhanced_results = []
        for r in paged_results:
            source = r.get("source", "unknown")
            source_label = "FAA事故数据" if source == "faa" else "MaintNet维修数据" if source == "maintnet" else "用户案例" if source == "user_case" else "知识库"
            
            final_score = r.get("score", 0)
            if final_score >= 1.0:
                relevance = "高"
            elif final_score >= 0.5:
                relevance = "中"
            else:
                relevance = "低"
            
            enhanced_results.append({
                "content": r.get("content", ""),
                "score": round(r.get("score", 0), 3),
                "relevance": relevance,
                "source": source_label,
                "record_id": r.get("record_id", ""),
                "aircraft_model": r.get("aircraft_model", ""),
                "manufacturer": r.get("manufacturer", ""),
                "description": r.get("description", ""),
                "problem": r.get("problem", ""),
                "action": r.get("action", ""),
                "matched_tokens": r.get("matched_tokens", 0),
                "total_tokens": r.get("total_tokens", 0),
                "keywords": query.split()
            })
        
        return {
            "success": True, 
            "results": enhanced_results, 
            "query": query,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"检索失败: {e}"})

@app.post("/api/case")
async def add_case(request: Request):
    """添加案例"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})

    body = await request.json()
    
    # 支持结构化案例
    case_type = body.get("case_type", "repair").strip()
    case_data = {
        "case_type": case_type,
        "title": body.get("title", "").strip(),
        "device_type": body.get("device_type", "").strip(),
        "fault_symptom": body.get("fault_symptom", "").strip() if case_type == "repair" else "",
        "fault_cause": body.get("fault_cause", "").strip() if case_type == "repair" else "",
        "solution": body.get("solution", "").strip(),
        "parts_used": body.get("parts_used", "").strip(),
        "technician": body.get("technician", "").strip(),
        "notes": body.get("notes", "").strip(),
        "case_text": body.get("case_text", "").strip(),
        "maintenance_type": body.get("maintenance_type", "").strip() if case_type == "maintenance" else "",
        "maintenance_cycle": body.get("maintenance_cycle", "").strip() if case_type == "maintenance" else "",
        "maintenance_standard": body.get("maintenance_standard", "").strip() if case_type == "maintenance" else ""
    }
    
    # 如果只有 case_text，尝试从中提取信息
    if case_data["case_text"] and not case_data["title"]:
        case_data["title"] = case_data["case_text"][:50]
    
    if not case_data["title"] and not case_data["case_text"]:
        return JSONResponse(status_code=400, content={"error": "请输入案例内容"})

    try:
        # 保存到 SQLite
        case_id = save_case_to_db(case_data)
        
        # 同步到 Qdrant 向量库，使其可被检索
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct
            from hello_agents.memory.embedding import get_text_embedder
            
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
            client = QdrantClient(url=qdrant_url, trust_env=not is_local)
            embedder = get_text_embedder()
            
            # 构建可检索的文本
            if case_type == "maintenance":
                search_text = f"{case_data['title']} | 设备: {case_data['device_type']} | 维护类型: {case_data['maintenance_type']} | 方案: {case_data['solution']}"
            else:
                search_text = f"{case_data['title']} | 设备: {case_data['device_type']} | 故障: {case_data['fault_symptom']} | 原因: {case_data['fault_cause']} | 方案: {case_data['solution']}"
            
            vector = embedder.encode(search_text).tolist()
            
            # 获取当前最大ID
            collections = [c.name for c in client.get_collections().collections]
            if "aviation_knowledge_base" in collections:
                # 使用时间戳作为唯一ID
                import time
                point_id = int(time.time() * 1000000)
                
                client.upsert(
                    collection_name="aviation_knowledge_base",
                    points=[PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "source": "user_case",
                            "case_type": case_type,
                            "record_id": f"CASE_{case_id}",
                            "content": search_text,
                            "text": search_text,
                            "aircraft_model": case_data["device_type"],
                            "description": case_data["fault_symptom"] if case_type == "repair" else case_data["maintenance_type"],
                            "problem": case_data["fault_cause"] if case_type == "repair" else case_data["maintenance_cycle"],
                            "action": case_data["solution"],
                            "memory_type": "rag_chunk",
                            "memory_id": f"case_{case_id}",
                            "user_id": "rag_user",
                            "is_rag_data": True,
                            "data_source": "rag_pipeline",
                            "rag_namespace": "default"
                        }
                    )]
                )
                logger.info(f"✅ 案例已同步到 Qdrant: CASE_{case_id} (类型: {case_type})")
        except Exception as e:
            logger.warning(f"⚠️ 案例同步到 Qdrant 失败: {e}")
        
        return {"success": True, "message": "案例添加成功", "case_id": case_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"添加失败: {e}"})

@app.get("/api/cases")
async def get_cases(case_type: str = None, page: int = 1, page_size: int = 20):
    """获取案例列表（支持分页和类型过滤）"""
    try:
        offset = (page - 1) * page_size
        result = load_cases_from_db(limit=page_size, offset=offset, case_type=case_type)
        return {
            "success": True,
            "cases": result["cases"],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
            "total_pages": (result["total"] + page_size - 1) // page_size
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"获取案例失败: {e}"})

@app.delete("/api/case/{case_id}")
async def delete_case(case_id: int):
    """删除案例"""
    try:
        # 先获取案例信息
        case = get_case_by_id(case_id)
        if not case:
            return JSONResponse(status_code=404, content={"error": "案例不存在"})
        
        # 从 SQLite 删除
        deleted = delete_case_from_db(case_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"error": "案例不存在"})
        
        # 从 Qdrant 删除（通过 record_id 查找并删除）
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
            client = QdrantClient(url=qdrant_url, trust_env=not is_local)
            
            collections = [c.name for c in client.get_collections().collections]
            if "aviation_knowledge_base" in collections:
                # 查找并删除对应的向量
                record_id = f"CASE_{case_id}"
                client.delete(
                    collection_name="aviation_knowledge_base",
                    points_selector=Filter(
                        must=[
                            FieldCondition(key="source", match=MatchValue(value="user_case")),
                            FieldCondition(key="record_id", match=MatchValue(value=record_id))
                        ]
                    )
                )
                logger.info(f"✅ 已从 Qdrant 删除案例: {record_id}")
        except Exception as e:
            logger.warning(f"⚠️ 从 Qdrant 删除案例失败: {e}")
        
        return {"success": True, "message": f"案例 {case_id} 已删除"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"删除失败: {e}"})

@app.get("/api/stats")
async def get_stats():
    """获取系统统计"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})
    try:
        stats = agent_state["agent"].get_stats()
        # 增强统计信息
        enhanced_stats = {
            "system": {
                "status": "running",
                "user_id": stats.get("user_id", "N/A"),
                "session_id": stats.get("session_id", "N/A"),
                "uptime": "运行中"
            },
            "knowledge_base": {
                "rag_stats": stats.get("knowledge_base", {}).get("rag_stats", {}),
                "memory_stats": stats.get("knowledge_base", {}).get("memory_stats", {})
            },
            "components": [
                {"name": "RAG 知识库", "status": "active", "icon": "📚"},
                {"name": "记忆系统", "status": "active", "icon": "🧠"},
                {"name": "LLM 诊断", "status": "active", "icon": "🤖"},
                {"name": "工单生成", "status": "active", "icon": "📋"}
            ]
        }
        return {"success": True, "stats": enhanced_stats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"获取统计失败: {e}"})

@app.get("/api/history")
async def get_history():
    """获取诊断历史"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})
    try:
        history = agent_state["agent"].get_diagnosis_history(limit=10)
        return {"success": True, "history": history}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"获取历史失败: {e}"})

@app.get("/api/data-stats")
async def get_data_stats():
    """获取数据资产统计"""
    try:
        conn = sqlite3.connect(CASES_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 案例总数统计
        cursor.execute("SELECT COUNT(*) as total FROM cases")
        total_cases = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as total FROM cases WHERE case_type='repair'")
        repair_cases = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as total FROM cases WHERE case_type='maintenance'")
        maintenance_cases = cursor.fetchone()["total"]
        
        # 故障类型分布（维修案例的故障现象关键词提取）
        cursor.execute("""
            SELECT fault_symptom, COUNT(*) as count 
            FROM cases 
            WHERE case_type='repair' AND fault_symptom != '' 
            GROUP BY fault_symptom 
            ORDER BY count DESC 
            LIMIT 10
        """)
        fault_distribution = [{"name": row["fault_symptom"][:20], "count": row["count"]} for row in cursor.fetchall()]
        
        # 设备类型分布
        cursor.execute("""
            SELECT device_type, COUNT(*) as count 
            FROM cases 
            WHERE device_type != '' 
            GROUP BY device_type 
            ORDER BY count DESC 
            LIMIT 10
        """)
        device_distribution = [{"name": row["device_type"], "count": row["count"]} for row in cursor.fetchall()]
        
        # 维护类型分布
        cursor.execute("""
            SELECT maintenance_type, COUNT(*) as count 
            FROM cases 
            WHERE case_type='maintenance' AND maintenance_type != '' 
            GROUP BY maintenance_type 
            ORDER BY count DESC 
            LIMIT 10
        """)
        maintenance_distribution = [{"name": row["maintenance_type"], "count": row["count"]} for row in cursor.fetchall()]
        
        # 最近添加的案例
        cursor.execute("""
            SELECT id, title, case_type, device_type, created_at 
            FROM cases 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        recent_cases = [{
            "id": row["id"],
            "title": row["title"],
            "case_type": row["case_type"],
            "device_type": row["device_type"],
            "created_at": row["created_at"]
        } for row in cursor.fetchall()]
        
        conn.close()
        
        # 反馈统计
        feedback_total = 0
        try:
            conn_fb = sqlite3.connect(FEEDBACK_DB_PATH)
            cursor_fb = conn_fb.cursor()
            cursor_fb.execute("SELECT COUNT(*) FROM feedback")
            feedback_total = cursor_fb.fetchone()[0]
            conn_fb.close()
        except:
            pass
        
        return {
            "success": True,
            "data": {
                "summary": {
                    "total_cases": total_cases,
                    "repair_cases": repair_cases,
                    "maintenance_cases": maintenance_cases,
                    "feedback_count": feedback_total
                },
                "fault_distribution": fault_distribution,
                "device_distribution": device_distribution,
                "maintenance_distribution": maintenance_distribution,
                "recent_cases": recent_cases
            }
        }
    except Exception as e:
        logger.error(f"获取数据统计失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"获取统计失败: {e}"})

@app.get("/api/stats/knowledge-graph")
async def get_knowledge_graph():
    """获取知识图谱数据 - 简化版，只显示飞机型号、事故类型、制造商"""
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
        )
        
        nodes = []
        links = []
        node_set = set()
        
        with driver.session() as s:
            # 获取 Top 10 高频飞机型号
            top_aircraft = []
            for r in s.run("""
                MATCH (r:AviationRecord)-[:INVOLVES_AIRCRAFT]->(a:AircraftModel)
                RETURN a.name AS a, count(r) AS cnt
                ORDER BY cnt DESC LIMIT 10
            """):
                top_aircraft.append(r["a"])
            
            # 获取 Top 8 事故类型
            top_incidents = []
            for r in s.run("""
                MATCH (r:AviationRecord)-[:HAS_INCIDENT_TYPE]->(t:IncidentType)
                RETURN t.name AS t, count(r) AS cnt
                ORDER BY cnt DESC LIMIT 8
            """):
                top_incidents.append(r["t"])
            
            # 获取 Top 10 制造商
            top_manufacturers = []
            for r in s.run("""
                MATCH (a:AircraftModel)-[:MANUFACTURED_BY]->(m:Manufacturer)
                RETURN m.name AS m, count(a) AS cnt
                ORDER BY cnt DESC LIMIT 10
            """):
                top_manufacturers.append(r["m"])
            
            # 添加飞机型号节点
            for aircraft in top_aircraft:
                nodes.append({"id": aircraft, "type": "Aircraft", "label": aircraft})
                node_set.add(aircraft)
            
            # 添加事故类型节点
            for incident in top_incidents:
                nodes.append({"id": incident, "type": "Incident", "label": incident})
                node_set.add(incident)
            
            # 添加制造商节点
            for mfg in top_manufacturers:
                nodes.append({"id": mfg, "type": "Manufacturer", "label": mfg})
                node_set.add(mfg)
            
            # 获取飞机型号-事故类型关系（通过记录关联）
            for r in s.run("""
                MATCH (a:AircraftModel)<-[:INVOLVES_AIRCRAFT]-(r:AviationRecord)-[:HAS_INCIDENT_TYPE]->(t:IncidentType)
                WHERE a.name IN $aircrafts AND t.name IN $incidents
                RETURN DISTINCT a.name AS a, t.name AS t, count(r) AS cnt
                ORDER BY cnt DESC LIMIT 30
            """, aircrafts=top_aircraft, incidents=top_incidents):
                links.append({"source": r["a"], "target": r["t"], "type": "HAS_INCIDENT", "count": r["cnt"]})
            
            # 获取飞机型号-制造商关系
            for r in s.run("""
                MATCH (a:AircraftModel)-[:MANUFACTURED_BY]->(m:Manufacturer)
                WHERE a.name IN $aircrafts AND m.name IN $manufacturers
                RETURN DISTINCT a.name AS a, m.name AS m
            """, aircrafts=top_aircraft, manufacturers=top_manufacturers):
                links.append({"source": r["a"], "target": r["m"], "type": "MANUFACTURED_BY"})
        
        driver.close()
        
        # 统计信息
        aircraft_count = sum(1 for n in nodes if n["type"] == "Aircraft")
        incident_count = sum(1 for n in nodes if n["type"] == "Incident")
        manufacturer_count = sum(1 for n in nodes if n["type"] == "Manufacturer")
        
        return {
            "success": True,
            "data": {
                "nodes": nodes,
                "links": links,
                "stats": {
                    "aircraft": aircraft_count,
                    "incidents": incident_count,
                    "manufacturers": manufacturer_count,
                    "total_nodes": len(nodes),
                    "total_links": len(links)
                }
            }
        }
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"获取知识图谱失败: {e}"})

@app.get("/api/stats/vector-space")
async def get_vector_space():
    """获取向量空间数据"""
    try:
        import numpy as np
        from sklearn.manifold import TSNE
        from qdrant_client import QdrantClient
        
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
        client = QdrantClient(url=qdrant_url, trust_env=not is_local)
        
        # 优先使用航空数据集合，如果不存在则使用旧集合
        collection_name = "aviation_knowledge_base"
        collections = [c.name for c in client.get_collections().collections]
        if collection_name not in collections:
            collection_name = "rag_knowledge_base"
        
        results = client.scroll(collection_name=collection_name, limit=500, with_vectors=True)
        points = results[0]
        
        if len(points) < 3:
            return {"success": True, "data": {"points": [], "stats": {"total": 0, "categories": 0}}}
        
        vectors, labels, texts = [], [], []
        for pt in points:
            if pt.vector is not None:
                vectors.append(pt.vector)
                p = pt.payload or {}
                # 根据数据源设置标签
                source = p.get("source", "")
                if source == "faa":
                    labels.append("FAA事故记录")
                elif source == "maintnet":
                    labels.append("MaintNet维修记录")
                else:
                    labels.append(p.get("source", p.get("product_category", "?")))
                texts.append(p.get("text", "")[:50])
        
        if len(vectors) < 3:
            return {"success": True, "data": {"points": [], "stats": {"total": 0, "categories": 0}}}
        
        X = np.array(vectors)
        perplexity = min(30, len(X) - 1)
        tsne = TSNE(n_components=2, random_state=42, perplexity=perplexity, max_iter=300)
        X_2d = tsne.fit_transform(X)
        
        # 构造返回数据
        points_data = []
        for i in range(len(X_2d)):
            points_data.append({
                "x": float(X_2d[i, 0]),
                "y": float(X_2d[i, 1]),
                "label": labels[i],
                "text": texts[i]
            })
        
        unique_labels = sorted(set(labels))
        
        # 获取集合统计
        collections_stats = []
        for c in client.get_collections().collections:
            info = client.get_collection(c.name)
            collections_stats.append({"name": c.name, "points": info.points_count})
        
        return {
            "success": True,
            "data": {
                "points": points_data,
                "stats": {
                    "total": len(vectors),
                    "categories": len(unique_labels),
                    "labels": unique_labels,
                    "collections": collections_stats,
                    "collection_used": collection_name
                }
            }
        }
    except Exception as e:
        logger.error(f"获取向量空间失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"获取向量空间失败: {e}"})

# ==================== 智能问答 API ====================

@app.post("/api/ask")
async def ask_question(request: Request):
    """智能问答 - SSE流式输出"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})

    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "请输入问题"})

    def qa_stream():
        try:
            llm = agent_state["agent"].llm
            
            # 第一步：分析问题，提取关键词
            yield sse_event("step", {"text": "🧠 正在分析问题..."})
            
            analysis_prompt = fmt_prompt("fastapi_analysis", "user", question=question)
            analysis_messages = [
                {"role": "system", "content": fmt_prompt("fastapi_analysis", "system")},
                {"role": "user", "content": analysis_prompt}
            ]
            
            analysis_result = llm.invoke(analysis_messages)
            
            # 解析关键词
            try:
                import json
                if "```json" in analysis_result:
                    json_str = analysis_result.split("```json")[1].split("```")[0]
                elif "```" in analysis_result:
                    json_str = analysis_result.split("```")[1].split("```")[0]
                else:
                    json_str = analysis_result
                
                keywords_data = json.loads(json_str.strip())
                keywords = keywords_data.get("keywords", [])
            except Exception as e:
                logger.warning(f"解析关键词失败: {e}")
                keywords = [{"keyword": question[:20], "relation": "核心问题"}]
            
            yield sse_event("step", {"text": f"📝 提取到 {len(keywords)} 个关键词"})
            
            # 第二步：解释每个关键词
            keyword_explanations = []
            for i, kw in enumerate(keywords[:5]):
                if isinstance(kw, str):
                    keyword = kw.strip()
                    relation = "核心概念"
                elif isinstance(kw, dict):
                    keyword = (kw.get("keyword") or kw.get("word") or "").strip()
                    relation = kw.get("relation", "")
                else:
                    continue

                if not keyword:
                    continue
                
                yield sse_event("step", {"text": f"📖 正在解析关键词 [{i+1}/{min(len(keywords), 5)}]: {keyword}"})
                
                explain_prompt = fmt_prompt("fastapi_explain", "user", keyword=keyword)
                explain_messages = [
                    {"role": "system", "content": fmt_prompt("fastapi_explain", "system")},
                    {"role": "user", "content": explain_prompt}
                ]
                
                explanation = llm.invoke(explain_messages)
                keyword_explanations.append({
                    "keyword": keyword,
                    "relation": relation,
                    "explanation": explanation
                })
            
            # 发送关键词解析结果
            yield sse_event("keywords", {"keywords": keyword_explanations})
            
            # 第三步：综合回答原始问题（流式输出）
            yield sse_event("step", {"text": "🧠 正在综合分析并生成回答..."})
            
            explanations_text = '\n'.join(f'- {ke["keyword"]}: {ke["explanation"][:100]}...' for ke in keyword_explanations)
            synthesis_prompt = fmt_prompt("fastapi_synthesis", "user",
                                          question=question,
                                          analysis=explanations_text,
                                          explanations=explanations_text)
            synthesis_messages = [
                {"role": "system", "content": fmt_prompt("fastapi_synthesis", "system")},
                {"role": "user", "content": synthesis_prompt}
            ]
            
            for chunk in llm.stream_invoke(synthesis_messages):
                yield sse_event("answer_chunk", {"chunk": chunk})
            
            yield sse_event("done", {"success": True})
            
        except Exception as e:
            logger.error(f"智能问答失败: {e}")
            yield sse_event("error", {"message": f"问答失败: {str(e)}"})

    return StreamingResponse(
        qa_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ==================== 系统反馈 API ====================

FEEDBACK_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory_data", "feedback.db")

def init_feedback_db():
    """初始化反馈数据库"""
    os.makedirs(os.path.dirname(FEEDBACK_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(FEEDBACK_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_type TEXT NOT NULL,
            context TEXT,
            system_output TEXT,
            issue_description TEXT,
            correct_answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# 初始化反馈数据库
init_feedback_db()

@app.post("/api/feedback")
async def submit_feedback(request: Request):
    """提交系统反馈"""
    body = await request.json()
    
    feedback_type = body.get("feedback_type", "other")
    context = body.get("context", "").strip()
    system_output = body.get("system_output", "").strip()
    issue_description = body.get("issue_description", "").strip()
    correct_answer = body.get("correct_answer", "").strip()
    
    if not issue_description:
        return JSONResponse(status_code=400, content={"error": "请描述问题"})
    
    try:
        conn = sqlite3.connect(FEEDBACK_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feedback (feedback_type, context, system_output, issue_description, correct_answer)
            VALUES (?, ?, ?, ?, ?)
        ''', (feedback_type, context, system_output, issue_description, correct_answer))
        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 同时记录到记忆系统
        try:
            agent = agent_state["agent"]
            if agent:
                memory_content = f"用户反馈 [{feedback_type}] | 问题: {issue_description[:100]}"
                if correct_answer:
                    memory_content += f" | 正确答案: {correct_answer[:100]}"
                
                agent.memory_tool.run({
                    "action": "add",
                    "content": memory_content,
                    "memory_type": "episodic",
                    "importance": 0.9,
                    "topic": "user_feedback",
                    "metadata": {
                        "feedback_id": feedback_id,
                        "feedback_type": feedback_type,
                        "context": context[:200],
                        "issue": issue_description[:200]
                    }
                })
        except Exception as e:
            logger.warning(f"记录反馈到记忆系统失败: {e}")
        
        return {"success": True, "message": "感谢您的反馈！", "feedback_id": feedback_id}
    except Exception as e:
        logger.error(f"保存反馈失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"提交失败: {e}"})

@app.get("/api/feedbacks")
async def get_feedbacks(limit: int = 50):
    """获取反馈列表"""
    try:
        conn = sqlite3.connect(FEEDBACK_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        feedbacks = []
        for row in rows:
            feedbacks.append({
                "id": row["id"],
                "feedback_type": row["feedback_type"],
                "context": row["context"],
                "system_output": row["system_output"],
                "issue_description": row["issue_description"],
                "correct_answer": row["correct_answer"],
                "created_at": row["created_at"],
                "processed": row["processed"]
            })
        
        return {"success": True, "feedbacks": feedbacks}
    except Exception as e:
        logger.error(f"获取反馈失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"获取失败: {e}"})

@app.delete("/api/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int):
    """删除反馈"""
    try:
        conn = sqlite3.connect(FEEDBACK_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            return {"success": True, "message": f"反馈 {feedback_id} 已删除"}
        else:
            return JSONResponse(status_code=404, content={"error": "反馈不存在"})
    except Exception as e:
        logger.error(f"删除反馈失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"删除失败: {e}"})

# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化 Agent"""
    import threading
    thread = threading.Thread(target=auto_init_agent, daemon=True)
    thread.start()

# ==================== 启动函数 ====================

def launch_app(host="127.0.0.1", port=7860):
    """启动 FastAPI 应用"""
    import uvicorn
    print(f"\n{'='*60}")
    print(f"[保障智能助手] FastAPI Web 界面")
    print(f"{'='*60}")
    print(f"启动中...")
    print(f"访问地址: http://{host}:{port}")
    print(f"{'='*60}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    launch_app()
