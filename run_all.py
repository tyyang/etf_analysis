#!/usr/bin/env python3
"""
009805 監控系統 - 一鍵執行全部報告
用法：
  python run_all.py                  # 只抓取數據 + 產生每日報告
  python run_all.py --fetch           # 只抓取數據
  python run_all.py --report          # 只產生每日報告（使用既有數據）
  python run_all.py --weekly          # 執行 fetch+daily+每週報告
  python run_all.py --quarterly       # 執行 fetch+daily+每季報告
  python run_all.py --all             # 執行全部（fetch+daily+週報+季報）
  python run_all.py --help            # 顯示此說明
"""

import subprocess
import sys
from pathlib import Path

from shared import ROOT


def run_script(name: str) -> bool:
    """執行一個腳本"""
    script = ROOT / name
    if not script.exists():
        print(f"❌ 找不到腳本: {script}")
        return False

    print(f"\n{'='*60}")
    print(f"▶ 執行: {name}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, str(script)], capture_output=False)
    return result.returncode == 0


def print_help():
    print(__doc__)


def main():
    args = set(sys.argv[1:])

    if "--help" in args or "-h" in args:
        print_help()
        return

    # 決定執行哪些步驟
    run_all = "--all" in args
    do_fetch = "--fetch" in args or (not args) or run_all
    do_daily = "--report" in args or (not args) or run_all
    do_weekly = "--weekly" in args or run_all
    do_quarterly = "--quarterly" in args or run_all

    # 如果沒有任何 flag 且沒有預設行為 → help
    if not args:
        # default: fetch + daily only
        pass

    success = True

    if do_fetch:
        if not run_script("fetch_indicators.py"):
            success = False
            print("⚠️ 數據抓取有部分失敗，但仍繼續產生報告...")

    if do_daily:
        run_script("daily_report.py")

    if do_weekly:
        run_script("weekly_analysis.py")

    if do_quarterly:
        run_script("quarterly_analysis.py")

    # 列出產生的報告
    reports_dir = ROOT / "reports"
    if reports_dir.exists():
        files = sorted(reports_dir.glob("*.md"))
        if files:
            print(f"\n📁 已產生報告 ({len(files)} 份):")
            for f in files[-5:]:
                print(f"   {f.name}")

    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
