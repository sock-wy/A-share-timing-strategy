# -*- coding: utf-8 -*-
"""
公共运行器
==========
每个子策略的 run.py 只需把自己的 strategy 模块传进来即可，逻辑统一在此。
"""
import importlib.util
from pathlib import Path

from .data_loader import load_index
from .backtest import run_backtest
from .plotting import build_report
from .config import BACKTEST, ROOT


def load_strategy(folder, filename="策略.py"):
    """按目录名加载该子策略模块（folder 如 '01_宏观流动性'）。

    filename 默认 '策略.py'（原版）；传 '策略进阶.py' 可加载同目录下的进阶版构造，
    二者互不影响（09/10 各有原版与进阶版两套建仓/平仓逻辑）。
    """
    path = ROOT / "strategies" / folder / filename
    spec = importlib.util.spec_from_file_location(f"{Path(filename).stem}_{folder}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_signal_for(mod, params=None, index_name="中证800"):
    """按标的生成信号：INDEX_DEPENDENT 策略（筹码结构/长端动量）用标的自身 OHLC 计算，
    其余（宏观/跨境/衍生品/资金流）为全市场信号，与标的无关（只是换个标的回测持有）。"""
    if getattr(mod, "INDEX_DEPENDENT", False):
        return mod.build_signal(params, index_name=index_name)
    return mod.build_signal(params)


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
