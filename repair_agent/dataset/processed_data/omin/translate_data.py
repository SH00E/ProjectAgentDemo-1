# -*- coding: utf-8 -*-
"""
OMIn 数据集中文翻译脚本
将英文维修记录翻译为中文（保留专有名词、缩写）

用法:
    python dataset/processed_data/omin/translate_data.py
"""

import os
import csv
import time
import sys

# 添加 libs 目录到路径（使用本地修改版 hello_agents）
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(_project_root, "libs"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from hello_agents import HelloAgentsLLM

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def translate_text(llm, text, max_retries=3):
    """翻译单条文本"""
    if not text or len(text.strip()) < 5:
        return text
    
    prompt = f"""将以下航空维修英文文本翻译为中文。
要求：
1. 保留专业缩写不翻译（如ACFT, TKOF, PROP, G/S等）
2. 保留飞机型号不翻译（如CESSNA, BEECH, Boeing 737等）
3. 保留专有名词（如人名、地名、机场名）
4. 翻译要简洁准确，符合中文维修报告风格

英文文本：
{text}

中文翻译："""
    
    messages = [{"role": "user", "content": prompt}]
    
    for attempt in range(max_retries):
        try:
            result = llm.invoke(messages)
            return result.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"  [翻译失败] {str(e)[:50]}")
                return text  # 失败时返回原文


def load_existing_translations(output_file):
    """加载已有的翻译结果（用于增量翻译）"""
    existing = {}
    if os.path.exists(output_file):
        with open(output_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("record_id", "")
                if rid:
                    existing[rid] = row
    return existing


def translate_faa_records(llm, sample=None):
    """翻译 FAA 事故记录"""
    input_file = os.path.join(BASE_DIR, "faa", "faa_records.csv")
    output_file = os.path.join(BASE_DIR, "faa", "faa_records_zh.csv")
    
    print("[FAA] 翻译 FAA 事故记录...")
    
    # 加载已有翻译
    existing = load_existing_translations(output_file)
    if existing:
        print(f"  已有 {len(existing)} 条翻译，跳过已翻译的记录")
    
    records = []
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if sample:
        rows = rows[:sample]
    
    total = len(rows)
    translated_count = 0
    
    for i, row in enumerate(rows):
        record_id = row.get("record_id", "")
        
        # 检查是否已有翻译
        if record_id in existing:
            records.append(existing[record_id])
            continue
        
        desc = row.get("description", "")
        desc_zh = translate_text(llm, desc)
        
        record = dict(row)
        record["description_zh"] = desc_zh
        records.append(record)
        translated_count += 1
        
        if translated_count % 20 == 0:
            print(f"  进度: {translated_count} 条新翻译")
            # 每20条保存一次（增量保存）
            _save_csv(records, output_file)
            time.sleep(1)
    
    # 最终保存
    _save_csv(records, output_file)
    print(f"[FAA] 已保存 {len(records)} 条翻译记录到 {output_file}")
    
    return records


def translate_maintnet_records(llm, sample=None):
    """翻译 MaintNet 维修记录"""
    input_file = os.path.join(BASE_DIR, "maintnet", "maintnet_records.csv")
    output_file = os.path.join(BASE_DIR, "maintnet", "maintnet_records_zh.csv")
    
    print("[MaintNet] 翻译 MaintNet 维修记录...")
    
    existing = load_existing_translations(output_file)
    if existing:
        print(f"  已有 {len(existing)} 条翻译，跳过已翻译的记录")
    
    records = []
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if sample:
        rows = rows[:sample]
    
    total = len(rows)
    translated_count = 0
    
    for i, row in enumerate(rows):
        record_id = row.get("record_id", "")
        
        if record_id in existing:
            records.append(existing[record_id])
            continue
        
        problem = row.get("problem", "")
        action = row.get("action", "")
        
        problem_zh = translate_text(llm, problem)
        action_zh = translate_text(llm, action) if action else ""
        
        record = dict(row)
        record["problem_zh"] = problem_zh
        record["action_zh"] = action_zh
        records.append(record)
        translated_count += 1
        
        if translated_count % 20 == 0:
            print(f"  进度: {translated_count} 条新翻译")
            _save_csv(records, output_file)
            time.sleep(1)
    
    _save_csv(records, output_file)
    print(f"[MaintNet] 已保存 {len(records)} 条翻译记录到 {output_file}")
    
    return records


def translate_terms(llm):
    """翻译术语和缩写说明"""
    terms_input = os.path.join(BASE_DIR, "maintnet", "aviation_terms.csv")
    terms_output = os.path.join(BASE_DIR, "maintnet", "aviation_terms_zh.csv")
    
    print("[Terms] 翻译航空术语...")
    
    records = []
    with open(terms_input, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for i, row in enumerate(rows):
        word = row.get("word", "")
        example = row.get("example", "")
        example_zh = translate_text(llm, example)
        
        record = dict(row)
        record["example_zh"] = example_zh
        records.append(record)
    
    if records:
        _save_csv(records, terms_output)
        print(f"[Terms] 已保存 {len(records)} 条翻译术语到 {terms_output}")
    
    return records


def _save_csv(records, output_file):
    """保存 CSV 文件"""
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="翻译 OMIn 数据为中文")
    parser.add_argument("--sample", type=int, help="只翻译前 N 条记录（用于测试）")
    args = parser.parse_args()
    
    print("=" * 60)
    print("OMIn 数据集中文翻译")
    print("=" * 60)
    
    llm = HelloAgentsLLM()
    print(f"[LLM] 初始化完成\n")
    
    # 翻译各类数据
    faa_records = translate_faa_records(llm, sample=args.sample)
    maintnet_records = translate_maintnet_records(llm, sample=args.sample)
    terms = translate_terms(llm)
    
    print("\n" + "=" * 60)
    print("翻译完成")
    print("=" * 60)
    print(f"  FAA 记录:      {len(faa_records)} 条")
    print(f"  MaintNet 记录: {len(maintnet_records)} 条")
    print(f"  术语:          {len(terms)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
