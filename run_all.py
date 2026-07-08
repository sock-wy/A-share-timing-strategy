# -*- coding: utf-8 -*-
"""
一键运行全部已实现子策略，生成各自 report.html，并打印“复现 vs 研报”汇总表。
运行：  python run_all.py
"""
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.data_loader import load_index
from src.backtest import run_backtest
from src.plotting import build_report
from src.config import REPORT_PERF

# 已实现子策略（08 大小单缺数据，跳过）
STRATS = ["01_宏观流动性", "02_信贷预期", "03_中美汇率", "04_中美利差",
          "05_期货基差", "06_期权PCR", "07_融资融券", "09_筹码结构", "10_长端动量"]


def _load(folder):
    path = ROOT / "strategies" / folder / "strategy.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(folder, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    bench = load_index("中证800")
    print(f"\n{'子策略':<10}{'复现年化':>10}{'研报年化':>10}{'复现回撤':>10}{'研报回撤':>10}"
          f"{'复现次数':>8}{'研报次数':>8}")
    print("-" * 66)
    for folder in STRATS:
        mod = _load(folder)
        res = run_backtest(bench, mod.build_signal(), name=mod.NAME)
        build_report(res, mod.REPORT_KEY)
        m, rep = res["metrics"], REPORT_PERF.get(mod.REPORT_KEY, {})
        print(f"{mod.NAME:<10}{m['年化收益率']*100:>9.2f}%{rep.get('年化收益率',0)*100:>9.2f}%"
              f"{m['最大回撤']*100:>9.2f}%{rep.get('最大回撤',0)*100:>9.2f}%"
              f"{m['信号次数']:>8}{rep.get('信号次数','-'):>8}")
    print(f"\n全部报告已生成于 outputs/ 目录。")


if __name__ == "__main__":
    main()
