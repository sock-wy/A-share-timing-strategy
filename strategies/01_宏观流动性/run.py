# -*- coding: utf-8 -*-
"""运行本子策略：周度 · 中证800 回测 -> 生成 report.html。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))          # 本目录（导入 strategy）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))      # 仓库根（导入 src）

from src.data_loader import load_index
from src.backtest import run_backtest
from src.plotting import build_report
from strategy import build_signal, NAME, REPORT_KEY


def main():
    signal = build_signal()
    result = run_backtest(load_index("中证800"), signal, name=NAME)
    print(f"\n===== {NAME} 复现绩效 =====")
    for k, v in result["metrics"].items():
        print(f"  {k:8s}: {v:.4f}" if isinstance(v, float) else f"  {k:8s}: {v}")
    path = build_report(result, REPORT_KEY)
    print(f"\n报告已生成 -> {path}")
    print(f"逐笔交易 {len(result['trades'])} 笔")


if __name__ == "__main__":
    main()
