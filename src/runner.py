# -*- coding: utf-8 -*-
"""
公共运行器
==========
每个子策略的 run.py 只需把自己的 strategy 模块传进来即可，逻辑统一在此。
"""
from .data_loader import load_index
from .backtest import run_backtest
from .plotting import build_report
from .config import BACKTEST


def run_strategy(mod, benchmark=None):
    """运行一个子策略模块（需含 build_signal / NAME / REPORT_KEY）。"""
    benchmark = benchmark or BACKTEST["benchmark"]
    signal = mod.build_signal()
    result = run_backtest(load_index(benchmark), signal, name=mod.NAME)
    print(f"\n===== {mod.NAME} 复现绩效（基准 {benchmark}）=====")
    for k, v in result["metrics"].items():
        print(f"  {k:8s}: {v:.4f}" if isinstance(v, float) else f"  {k:8s}: {v}")
    path = build_report(result, mod.REPORT_KEY)
    print(f"\n报告已生成 -> {path}")
    print(f"逐笔交易 {len(result['trades'])} 笔")
    return result
