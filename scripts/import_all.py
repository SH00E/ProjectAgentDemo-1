# -*- coding: utf-8 -*-
"""
一键导入所有数据
默认导入：维修案例、维护案例、QA知识库
可选导入：航空FAA数据（--aviation）
"""

import os
import sys
import argparse
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script_name, args=None):
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        print(f" 脚本不存在: {script_name}")
        return False

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    print(f"\n{'=' * 60}")
    print(f"运行: {script_name}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f" 脚本运行失败: {e}")
        return False
    except Exception as e:
        print(f" 运行出错: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="一键导入所有数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/import_all.py                  # 默认导入（不含 FAA 数据）
  python scripts/import_all.py --aviation       # 导入全部（含 FAA 航空数据）
  python scripts/import_all.py --sample 10      # 测试模式，每个数据集导入 10 条
  python scripts/import_all.py --aviation --sample 10  # 含 FAA 的测试模式
        """
    )
    parser.add_argument("--aviation", action="store_true", help="同时导入 FAA 航空维修数据")
    parser.add_argument("--sample", type=int, metavar="N", help="测试模式，每个数据集导入 N 条")
    args = parser.parse_args()

    import_aviation = args.aviation
    sample_n = args.sample
    total_steps = 4 if import_aviation else 3

    print(" 一键导入数据")
    print("=" * 60)
    print("将依次导入：")
    if import_aviation:
        print("  1. 航空 FAA 维修数据（Qdrant + Neo4j）")
    print(f"  {2 if import_aviation else 1}. 维修案例数据")
    print(f"  {3 if import_aviation else 2}. 维护案例数据")
    print(f"  {4 if import_aviation else 3}. QA 知识库数据")
    if not import_aviation:
        print("\n  提示: 加 --aviation 可同时导入 FAA 航空数据")
    print("=" * 60)

    if sample_n:
        print(f"\n[测试模式] 每个数据集导入 {sample_n} 条")

    sample_args = ['--sample', str(sample_n)] if sample_n else None
    success_count = 0
    fail_count = 0
    step = 0

    if import_aviation:
        step += 1
        print(f"\n{'=' * 60}")
        print(f"[{step}/{total_steps}] 导入航空 FAA 维修数据")
        print("=" * 60)
        aviation_args = sample_args if sample_args else ['--all']
        if run_script('import_aviation.py', aviation_args):
            success_count += 1
        else:
            fail_count += 1
            print("  航空数据导入失败，继续...")

    step += 1
    print(f"\n{'=' * 60}")
    print(f"[{step}/{total_steps}] 导入维修案例数据")
    print("=" * 60)
    if run_script('import_repair_cases.py'):
        success_count += 1
    else:
        fail_count += 1
        print("  维修案例导入失败，继续...")

    step += 1
    print(f"\n{'=' * 60}")
    print(f"[{step}/{total_steps}] 导入维护案例数据")
    print("=" * 60)
    if run_script('import_maintenance_cases.py'):
        success_count += 1
    else:
        fail_count += 1
        print("  维护案例导入失败，继续...")

    step += 1
    print(f"\n{'=' * 60}")
    print(f"[{step}/{total_steps}] 导入 QA 知识库数据")
    print("=" * 60)
    qa_args = sample_args if sample_args else ['--all']
    if run_script('import_qa_pairs.py', qa_args):
        success_count += 1
    else:
        fail_count += 1
        print("  QA 知识库导入失败")

    print("\n" + "=" * 60)
    print(" 导入完成")
    print("=" * 60)
    print(f"  成功: {success_count}/{total_steps}")
    print(f"  失败: {fail_count}/{total_steps}")

    if fail_count == 0:
        print("\n 所有数据导入成功！")
    else:
        print(f"\n 有 {fail_count} 项导入失败，请检查日志")

    print("=" * 60)


if __name__ == "__main__":
    main()
