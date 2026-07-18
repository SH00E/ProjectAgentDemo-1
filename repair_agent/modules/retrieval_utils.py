import re
import os
import sqlite3
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DOMAIN_TERMS = [
    "空地导弹", "空舰导弹", "空射巡航导弹", "制导系统", "控制系统", "动力系统",
    "电气系统", "引战系统", "弹体结构", "电视", "红外", "双模导引头", "导引头",
    "光轴", "光轴偏差", "光轴平行性", "融合偏差", "精确制导", "频综器", "频率综合器",
    "惯性导航", "惯组", "雷达", "数据链", "校准", "更换", "失锁", "漂移", "偏差",
    "天线罩", "透波率", "光纤陀螺", "光纤制导", "图像传输", "本振源", "接收机",
    "伺服阀", "舵机", "作动器", "推进剂", "发动机", "压气机", "叶片", "燃油",
    "引信", "近炸引信", "战斗部", "电连接器", "二次电源", "MOS管", "制冷机",
    "非均匀性校正", "雪花", "条纹", "目标丢失", "掉电", "腐蚀", "卡滞", "脱粘",
    "冷浸", "BIT", "传输时延", "阻尼力", "端面", "接口", "行程", "力校准"
]

IGNORED_TOKENS = {
    "装备型号", "装备名称", "型号", "名称", "系统名称", "部件名称", "相关部件",
    "故障现象", "故障类型", "维护类型", "维护内容", "关键词", "无",
    "故障", "问题", "异常", "维护", "维修", "检查", "检测", "更换", "校准", "清洁",
    "定期", "日常", "怎么", "如何", "需要", "处理", "进行", "一下"
}


def normalize(text: str) -> str:
    for sep in ['-', '_', ' ', '\u3000', '/', '\\', '\u00b7', '\u2022']:
        text = text.replace(sep, '')
    for particle in ['的', '了']:
        text = text.replace(particle, '')
    return text.lower().strip()


def clean_score_tokens(tokens: List[str]) -> List[str]:
    ignored_norms = {normalize(t) for t in IGNORED_TOKENS}
    cleaned = []
    for token in tokens:
        token = str(token).strip()
        if not token or token in IGNORED_TOKENS:
            continue
        if len(token) > 24:
            continue
        if re.fullmatch(r"[A-Za-z]{1,3}|\d{1,3}", token):
            continue
        token_norm = normalize(token)
        if not token_norm or token_norm in ignored_norms:
            continue
        if token not in cleaned:
            cleaned.append(token)
    return cleaned


def split_query_tokens(query: str) -> List[str]:
    tokens = []
    if 2 <= len(query) <= 24 and not re.search(r"[\s,，、/|\-_]", query):
        tokens.append(query)
    for part in re.split(r"[\s,，、/|\-_]+", query):
        part = part.strip()
        if part and 2 <= len(part) <= 24 and part not in tokens:
            tokens.append(part)
    for term in extract_domain_terms(query):
        if term not in tokens:
            tokens.append(term)
    return tokens


def extract_domain_terms(query: str) -> List[str]:
    terms = []
    for term in DOMAIN_TERMS:
        if term in query and term not in terms:
            terms.append(term)
    for term in re.findall(r"[A-Za-z]+-?\d+[A-Za-z0-9-]*", query):
        if term not in terms:
            terms.append(term)
    return terms


def expand_recall_tokens(tokens: List[str]) -> List[str]:
    recall_tokens = list(tokens)
    for part in list(tokens):
        if len(part) >= 4:
            for win_size in [2, 3]:
                for k in range(len(part) - win_size + 1):
                    token = part[k:k + win_size]
                    if token not in recall_tokens:
                        recall_tokens.append(token)
    return recall_tokens


def compute_keyword_score(record: Dict, query_tokens: List[str], full_query: str) -> tuple:
    content = str(record.get("content", ""))
    description = str(record.get("description", ""))
    problem = str(record.get("problem", ""))
    action = str(record.get("action", ""))
    aircraft_model = str(record.get("aircraft_model", ""))
    text = " ".join([content, description, problem, action, aircraft_model])
    text_norm = normalize(text)

    total = len(query_tokens)
    if total == 0:
        return 0.0, 0, 0

    matched = 0
    matched_weight = 0.0
    for token in query_tokens:
        token_norm = normalize(token)
        if not token_norm:
            continue

        field_weight = 0.0
        if token_norm in normalize(aircraft_model):
            field_weight = max(field_weight, 1.6)
        if token_norm in normalize(description):
            field_weight = max(field_weight, 1.35)
        if token_norm in normalize(problem):
            field_weight = max(field_weight, 1.35)
        if token_norm in normalize(action):
            field_weight = max(field_weight, 1.1)
        if token_norm in normalize(content):
            field_weight = max(field_weight, 1.2)

        if field_weight > 0:
            matched += 1
            matched_weight += field_weight

    ratio = matched / total
    weighted_ratio = matched_weight / total

    if matched == total and total > 1:
        boost = 1.5
    elif ratio >= 0.67:
        boost = 1.2
    else:
        boost = 1.0

    full_query_norm = normalize(full_query)
    token_norms = [normalize(t) for t in query_tokens]
    if full_query_norm and full_query_norm not in token_norms and full_query_norm in text_norm:
        boost = max(boost, 1.8)

    score = weighted_ratio * boost
    model_tokens = [t for t in query_tokens if re.search(r"[A-Za-z]+-?\d", t)]
    if model_tokens and not any(normalize(t) in text_norm for t in model_tokens):
        score = min(score, 0.75)
    return score, matched, total



def search_qdrant_keywords(client, collection_name: str, query_tokens: List[str],
                           keyword_results: Dict, exclude_case_type: str = None):
    from qdrant_client.models import Filter, FieldCondition, MatchText

    try:
        keyword_conditions = []
        for qp in query_tokens:
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
            if rid in keyword_results:
                continue
            ct = payload.get("case_type", "")
            if exclude_case_type and ct == exclude_case_type:
                continue
            keyword_results[rid] = {
                "content": payload.get("content", payload.get("text", "")),
                "source": payload.get("source", "unknown"),
                "record_id": rid,
                "aircraft_model": payload.get("aircraft_model", ""),
                "manufacturer": payload.get("manufacturer", ""),
                "description": payload.get("description", "") or payload.get("description_zh", ""),
                "problem": payload.get("problem", "") or payload.get("problem_zh", ""),
                "action": payload.get("action", "") or payload.get("action_zh", ""),
                "case_type": ct,
                "collection": collection_name,
            }
    except Exception as e:
        logger.warning(f"\u5173\u952e\u8bcd\u53ec\u56de\u5931\u8d25({collection_name}): {e}")


def search_sqlite_keywords(cases_db_path: str, score_tokens: List[str], query: str,
                           keyword_results: Dict, exclude_case_type: str = None):
    if not os.path.exists(cases_db_path):
        return
    try:
        raw_tokens = list(score_tokens)
        if query not in raw_tokens:
            raw_tokens.insert(0, query)

        conn = sqlite3.connect(cases_db_path)
        conn.row_factory = sqlite3.Row
        try:
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
                sql = 'SELECT DISTINCT * FROM cases WHERE (' + ' OR '.join(sql_conditions) + ')'
                if exclude_case_type:
                    sql += ' AND case_type != ?'
                    sql_params.append(exclude_case_type)
                cursor.execute(sql, sql_params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        for row in rows:
            case_id = row["id"]
            rid = f"CASE_{case_id}"
            if rid in keyword_results:
                continue
            case_type = row["case_type"] if "case_type" in row.keys() else "repair"
            if case_type == "maintenance":
                content = f"{row['title']} | \u8bbe\u5907: {row['device_type']} | \u7ef4\u62a4\u7c7b\u578b: {row['maintenance_type'] if 'maintenance_type' in row.keys() else ''} | \u65b9\u6848: {row['solution']}"
            else:
                content = f"{row['title']} | \u8bbe\u5907: {row['device_type']} | \u6545\u969c: {row['fault_symptom'] or ''} | \u539f\u56e0: {row['fault_cause'] or ''} | \u65b9\u6848: {row['solution']}"
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
        logger.warning(f"SQLite \u641c\u7d22\u5931\u8d25: {e}")


def vector_fallback_search(client, embedder, query: str, collections: List[str],
                           exclude_case_type: str = None) -> List[Dict]:
    results = {}
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
                if rid in results:
                    continue
                ct = payload.get("case_type", "")
                if exclude_case_type and ct == exclude_case_type:
                    continue
                results[rid] = {
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
                    "total_tokens": 1,
                }
        except Exception:
            pass
    return list(results.values())


def hyde_mqe_search(llm, embedder, client, query: str, collections: List[str],
                    exclude_case_type: str = None, top_k: int = 15) -> List[Dict]:
    """\u4f7f\u7528 HyDE + MQE \u6269\u5c55\u67e5\u8be2\uff0c\u5411\u91cf\u68c0\u7d22\u8865\u5145\u7ed3\u679c"""
    expansions = [query]

    try:
        mqe_prompt = [
            {"role": "system", "content": "\u4f60\u662f\u68c0\u7d22\u67e5\u8be2\u6269\u5c55\u52a9\u624b\u3002\u751f\u6210\u8bed\u4e49\u7b49\u4ef7\u6216\u4e92\u8865\u7684\u591a\u6837\u5316\u67e5\u8be2\u3002\u4f7f\u7528\u4e2d\u6587\uff0c\u7b80\u77ed\uff0c\u907f\u514d\u6807\u70b9\u3002"},
            {"role": "user", "content": f"\u539f\u59cb\u67e5\u8be2\uff1a{query}\n\u8bf7\u7ed9\u51fa3\u4e2a\u4e0d\u540c\u8868\u8ff0\u7684\u67e5\u8be2\uff0c\u6bcf\u884c\u4e00\u4e2a\u3002"}
        ]
        mqe_text = llm.invoke(mqe_prompt)
        for line in (mqe_text or "").splitlines():
            line = line.strip("- \t")
            if line and line not in expansions:
                expansions.append(line)
    except Exception:
        pass

    try:
        hyde_prompt = [
            {"role": "system", "content": "\u6839\u636e\u7528\u6237\u95ee\u9898\uff0c\u5148\u5199\u4e00\u6bb5\u53ef\u80fd\u7684\u7b54\u6848\u6027\u6bb5\u843d\uff0c\u7528\u4e8e\u5411\u91cf\u68c0\u7d22\u7684\u67e5\u8be2\u6587\u6863\uff08\u4e0d\u8981\u5206\u6790\u8fc7\u7a0b\uff09\u3002"},
            {"role": "user", "content": f"\u95ee\u9898\uff1a{query}\n\u8bf7\u76f4\u63a5\u5199\u4e00\u6bb5\u4e2d\u7b49\u957f\u5ea6\u3001\u5ba2\u89c2\u3001\u5305\u542b\u5173\u952e\u672f\u8bed\u7684\u6bb5\u843d\u3002"}
        ]
        hyde_text = llm.invoke(hyde_prompt)
        if hyde_text and hyde_text.strip():
            expansions.append(hyde_text.strip())
    except Exception:
        pass

    per_pool = max(5, (top_k * 3) // max(1, len(expansions)))
    agg = {}
    for q in expansions:
        if not q:
            continue
        try:
            vec = embedder.encode(q).tolist()
            for col_name in collections:
                hits = client.query_points(
                    collection_name=col_name, query=vec, limit=per_pool, with_payload=True
                ).points
                for h in hits:
                    payload = h.payload or {}
                    rid = payload.get("record_id", str(h.id))
                    score = float(h.score)
                    ct = payload.get("case_type", "")
                    if exclude_case_type and ct == exclude_case_type:
                        continue
                    if rid not in agg or score > float(agg[rid].get("score", 0.0)):
                        agg[rid] = {
                            "content": payload.get("content", payload.get("text", "")),
                            "score": score * 0.7,
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
                            "total_tokens": 1,
                        }
        except Exception:
            pass

    merged = list(agg.values())
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:top_k]


def merge_and_sort_results(keyword_results: List[Dict], hyde_results: List[Dict]) -> List[Dict]:
    """\u5408\u5e76\u5173\u952e\u8bcd\u53ec\u56de\u548c HyDE/MQE \u53ec\u56de\u7ed3\u679c\uff0c\u53bb\u91cd\u5e76\u6309\u5206\u6570\u6392\u5e8f"""
    seen = {}
    for r in keyword_results:
        rid = r.get("record_id", id(r))
        if rid not in seen or r.get("score", 0) > seen[rid].get("score", 0):
            seen[rid] = r
    for r in hyde_results:
        rid = r.get("record_id", id(r))
        if rid not in seen or r.get("score", 0) > seen[rid].get("score", 0):
            seen[rid] = r

    merged = list(seen.values())
    merged.sort(key=lambda x: (x.get("matched_tokens", 0), x.get("score", 0)), reverse=True)
    return merged
