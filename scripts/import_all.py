# -*- coding: utf-8 -*-
"""
一键导入所有数据
包括：航空数据、维修案例、维护案例
"""

import os
import sys
import subprocess

# Windows UTF-8 兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script_name, args=None):
    """运行指定脚本"""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    
    if not os.path.exists(script_path):
        print(f"✗ 脚本不存在: {script_name}")
        return False
    
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"运行: {script_name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"✗ 脚本运行失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 运行出错: {e}")
        return False


def main():
    print("🚀 一键导入所有数据")
    print("=" * 60)
    print("将依次导入：")
    print("  1. 航空维修数据（Qdrant + Neo4j）")
    print("  2. 维修案例数据")
    print("  3. 维护案例数据")
    print("=" * 60)
    
    # 检查是否有 --sample 参数
    sample_args = []
    if len(sys.argv) > 1 and sys.argv[1] == '--sample':
        if len(sys.argv) > 2:
            sample_args = ['--sample', sys.argv[2]]
            print(f"\n[测试模式] 每个文件导入 {sys.argv[2]} 条")
    
    success_count = 0
    fail_count = 0
    
    # 1. 导入航空数据
    print("\n" + "="*60)
    print("[1/3] 导入航空维修数据")
    print("="*60)
    
    aviation_args = sample_args if sample_args else ['--all']
    if run_script('import_aviation.py', aviation_args):
        success_count += 1
    else:
        fail_count += 1
        print("⚠️ 航空数据导入失败，继续...")
    
    # 2. 导入维修案例
    print("\n" + "="*60)
    print("[2/3] 导入维修案例数据")
    print("="*60)
    
    if run_script('import_repair_cases.py'):
        success_count += 1
    else:
        fail_count += 1
        print("⚠️ 维修案例导入失败，继续...")
    
    # 3. 导入维护案例
    print("\n" + "="*60)
    print("[3/3] 导入维护案例数据")
    print("="*60)
    
    if run_script('import_maintenance_cases.py'):
        success_count += 1
    else:
        fail_count += 1
        print("⚠️ 维护案例导入失败")
    
    # 汇总
    print("\n" + "="*60)
    print("📊 导入完成")
    print("="*60)
    print(f"  成功: {success_count}/3")
    print(f"  失败: {fail_count}/3")
    
    if fail_count == 0:
        print("\n✅ 所有数据导入成功！")
    else:
        print(f"\n⚠️ 有 {fail_count} 项导入失败，请检查日志")
    
    print("="*60)


if __name__ == "__main__":
    main()
