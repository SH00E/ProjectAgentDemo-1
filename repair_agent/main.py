# -*- coding: utf-8 -*-
"""
维修智能助手主程序入口
支持Web界面和命令行测试
"""

import os
import sys
import json
import argparse

# Windows控制台UTF-8兼容（hello-agents库的emoji输出需要）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 添加 libs 目录到路径（使用本地修改版 hello_agents）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "libs"))

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def test_diagnosis():
    """测试诊断功能（支持图片）"""
    from modules.repair_agent import RepairAgent
    import glob as glob_mod
    
    print("\n" + "=" * 60)
    print("[Test] Repair Agent - Command Line Test")
    print("=" * 60)
    
    # 初始化Agent
    agent = RepairAgent(user_id="test_user")
    
    # 扫描测试图片
    img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_image")
    image_files = []
    if os.path.isdir(img_dir):
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"):
            image_files.extend(glob_mod.glob(os.path.join(img_dir, ext)))
    
    # 测试用例
    test_cases = [
        {
            "description": "CESSNA 172 发动机在起飞后熄火，滑油压力指示异常低",
            "image_path": None
        },
        {
            "description": "BOEING 737 左侧起落架收放异常，液压系统压力下降",
            "image_path": None
        },
        {
            "description": "BELL 206 直升机主旋翼振动异常，伴随异响",
            "image_path": None
        }
    ]
    
    # 如果有测试图片，添加带图片的测试用例
    if image_files:
        for img in image_files:
            fname = os.path.basename(img)
            test_cases.append({
                "description": f"请分析这张故障照片: {fname}",
                "image_path": img
            })
    
    # 选择测试用例
    print("\nAvailable test cases:")
    for i, case in enumerate(test_cases, 1):
        img_tag = " [📷]" if case["image_path"] else ""
        print(f"  {i}. {case['description'][:50]}...{img_tag}")
    print(f"  0. Custom input")
    
    choice = input(f"\nSelect test case (0-{len(test_cases)}): ").strip()
    
    if choice == "0":
        description = input("Enter fault description: ").strip()
        if not description:
            print("[ERROR] Description cannot be empty")
            return
        
        # 询问是否附带图片
        image_path = None
        if image_files:
            print("\nAvailable images in test_images/:")
            for i, img in enumerate(image_files, 1):
                print(f"  {i}. {os.path.basename(img)}")
            img_choice = input("Select image (number) or press Enter to skip: ").strip()
            if img_choice.isdigit() and 1 <= int(img_choice) <= len(image_files):
                image_path = image_files[int(img_choice) - 1]
        
        if not image_path:
            custom_img = input("Or enter image path (press Enter to skip): ").strip()
            if custom_img and os.path.exists(custom_img):
                image_path = custom_img
        
        test_case = {"description": description, "image_path": image_path}
    elif choice.isdigit() and 1 <= int(choice) <= len(test_cases):
        test_case = test_cases[int(choice) - 1]
    else:
        print("[ERROR] Invalid choice")
        return
    
    # 执行诊断
    print(f"\n[Description] {test_case['description']}")
    if test_case['image_path']:
        print(f"[Image] {test_case['image_path']}")
    print("-" * 60)
    
    result = agent.process_request(
        description=test_case["description"],
        image_path=test_case["image_path"]
    )
    
    # 显示结果
    if result.get("success"):
        print("\n[SUCCESS] Diagnosis completed!\n")
        
        # 诊断结果
        diagnosis = result.get("diagnosis", {})
        diagnosis_data = diagnosis.get("diagnosis", diagnosis)
        print("[Diagnosis Result]")
        print(f"  Fault Type: {diagnosis_data.get('fault_type', 'Unknown')}")
        print(f"  Impact: {diagnosis_data.get('impact', 'Pending')}")
        
        severity = diagnosis.get("severity", {})
        print(f"  Severity: {severity.get('level', 'Pending')}")
        
        # 维修方案
        solution = result.get("solution", {})
        print("\n[Repair Solution]")
        steps = solution.get("repair_steps", [])
        for step in steps[:3]:  # 只显示前3步
            print(f"  {step.get('step', '?')}. {step.get('action', '')}")
        
        # 工单
        print("\n[Work Order]")
        print(result.get("work_order_text", "None"))
        
    else:
        print(f"\n[FAILED] {result.get('error', 'Unknown error')}")


def test_knowledge_management():
    """测试知识库管理"""
    from modules.repair_agent import RepairAgent
    
    print("\n" + "=" * 60)
    print("[Test] Knowledge Base Management")
    print("=" * 60)
    
    agent = RepairAgent(user_id="test_user")
    
    while True:
        print("\nOptions:")
        print("  1. Add repair case")
        print("  2. Add fault code")
        print("  3. Search knowledge base")
        print("  0. Back")
        
        choice = input("\nSelect option (0-3): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            case_text = input("Enter case content: ").strip()
            if case_text:
                result = agent.add_case(case_text)
                print(f"Result: {result}")
        elif choice == "2":
            code = input("Enter fault code: ").strip()
            meaning = input("Enter fault meaning: ").strip()
            solution = input("Enter solution (optional): ").strip()
            if code and meaning:
                result = agent.add_fault_code(code, meaning, solution or None)
                print(f"Result: {result}")
        elif choice == "3":
            query = input("Enter query: ").strip()
            if query:
                results = agent.search_knowledge(query)
                print(f"\nFound {len(results)} results:")
                for i, r in enumerate(results, 1):
                    content = r.get("content", str(r))[:100]
                    print(f"  {i}. {content}...")
        else:
            print("[ERROR] Invalid choice")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Repair Agent")
    parser.add_argument("--mode", choices=["web", "web-gradio", "web-fastapi", "test", "knowledge"],
                        default="web-fastapi", help="Running mode")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=7860, help="Web server port")
    parser.add_argument("--share", action="store_true", help="Create public link")
    
    args = parser.parse_args()
    
    if args.mode in ("web", "web-fastapi"):
        # 启动 FastAPI Web 界面（默认）
        from ui.fastapi_app import launch_app
        launch_app(host=args.host, port=args.port)

    elif args.mode == "web-gradio":
        print("\n" + "=" * 60)
        print("[Repair Agent] Gradio Web Interface")
        print("=" * 60)
        print("Gradio 界面已移除，请使用默认的 FastAPI 界面: python main.py --mode web")
        print("=" * 60)
        
    elif args.mode == "test":
        # 命令
        # 行测试
        test_diagnosis()
        
    elif args.mode == "knowledge":
        # 知识库管理
        test_knowledge_management()


if __name__ == "__main__":
    main()
