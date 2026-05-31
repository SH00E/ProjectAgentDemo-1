# -*- coding: utf-8 -*-
"""
维修智能助手 Web 界面
使用 FastAPI + 原生 HTML/JS 构建，支持 SSE 流式输出
"""

import os
import sys
import json
import time
import logging
import tempfile
from typing import Dict

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.repair_agent import RepairAgent

logger = logging.getLogger(__name__)

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

def diagnosis_stream(description: str, image_path: str = None):
    """诊断流式生成器"""
    agent = agent_state["agent"]
    if agent is None:
        yield sse_event("error", {"message": "系统未就绪，请稍候"})
        return

    for kind, data in agent.process_request_stream(description, image_path):
        if kind == "step":
            yield sse_event("step", {"text": data})
        elif kind == "neo4j":
            # 处理 Neo4j 知识图谱结果
            if data:
                results = []
                for r in data[:5]:
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
                for r in data[:5]:
                    # 构建证据链信息
                    source = r.get("source", "unknown")
                    source_label = "FAA事故数据" if source == "faa" else "MaintNet维修数据" if source == "maintnet" else "知识图谱" if source == "neo4j" else "知识库"
                    
                    results.append({
                        "content": r.get("content", str(r))[:200],
                        "score": r.get("score", 0),
                        "source": source,
                        "source_label": source_label,
                        "record_id": r.get("record_id", ""),
                        "aircraft_model": r.get("aircraft_model", ""),
                        "manufacturer": r.get("manufacturer", ""),
                        "description": r.get("description", "")[:150],
                        "problem": r.get("problem", "")[:150],
                        "action": r.get("action", "")[:150]
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
            for ref in knowledge_refs[:8]:
                source = ref.get("source", "unknown")
                source_label = "FAA事故数据" if source == "faa" else "MaintNet维修数据" if source == "maintnet" else "知识图谱" if source == "neo4j" else "知识库"
                
                # 处理 Neo4j 特有的字段
                details = ref.get("details", {})
                aircraft_models = details.get("aircraft_models", [])
                incident_types = details.get("incident_types", [])
                
                evidence_chain.append({
                    "content": ref.get("content", "")[:200],
                    "score": ref.get("score", 0),
                    "source": source,
                    "source_label": source_label,
                    "record_id": ref.get("record_id", ""),
                    "aircraft_model": ref.get("aircraft_model", "") or (aircraft_models[0] if aircraft_models else ""),
                    "manufacturer": ref.get("manufacturer", ""),
                    "description": ref.get("description", "")[:150],
                    "problem": ref.get("problem", "")[:150],
                    "action": ref.get("action", "")[:150],
                    "neo4j_type": details.get("type", ""),
                    "incident_types": incident_types[:3]
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
    image: UploadFile = File(None)
):
    """提交诊断请求，返回 SSE 流"""
    if agent_state["agent"] is None:
        return JSONResponse(
            status_code=503,
            content={"error": "系统未就绪，请稍候"}
        )

    if not description.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "请输入故障描述"}
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
        diagnosis_stream(description, image_path),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/search")
async def search_knowledge(request: Request):
    """知识检索"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})

    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "请输入查询内容"})

    try:
        results = agent_state["agent"].search_knowledge(query, limit=5)
        # 增强结果格式
        enhanced_results = []
        for r in results:
            content = r.get("content", str(r))
            score = r.get("score", 0)
            # 提取关键词
            keywords = query.split()
            enhanced_results.append({
                "content": content,
                "score": score,
                "keywords": keywords,
                "source": r.get("source", "知识库"),
                "timestamp": r.get("timestamp", "")
            })
        return {"success": True, "results": enhanced_results, "query": query}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"检索失败: {e}"})

@app.post("/api/case")
async def add_case(request: Request):
    """添加案例"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})

    body = await request.json()
    case_text = body.get("case_text", "").strip()
    if not case_text:
        return JSONResponse(status_code=400, content={"error": "请输入案例内容"})

    try:
        r = agent_state["agent"].add_case(case_text)
        if r.get("success"):
            return {"success": True, "message": r.get("message", "添加成功")}
        else:
            return {"success": False, "message": r.get("message", "添加失败")}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"添加失败: {e}"})

@app.get("/api/cases")
async def get_cases():
    """获取案例列表（从诊断历史中提取）"""
    if agent_state["agent"] is None:
        return JSONResponse(status_code=503, content={"error": "系统未就绪"})
    try:
        history = agent_state["agent"].get_diagnosis_history(limit=20)
        return {"success": True, "cases": history}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"获取案例失败: {e}"})

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
        
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        
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
