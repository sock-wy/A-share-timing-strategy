# -*- coding: utf-8 -*-
"""
01 宏观流动性 —— 信号构造
=========================
净投放(月度) -> 平滑 -> 滚动Zscore -> 阈值 p 三态信号（>p:1, <-p:-1, 中间延续）

full_window=1（满窗才出信号）：平滑与 Zscore 均要求窗口数据齐全才出值——
头 smooth_window+zscore_window-2 个月无信号（如 9/3 → 2015-11 起才有信号）。
默认 0 = 原口径（min_periods=1 部分窗口即出值，2015-02 起有信号，头几个月的
"平滑"实际是逐渐变长的短均线）。两种口径都无未来函数，差别只在早期信号是否严格。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_macro_liquidity
from src.signal_utils import rolling_zscore, threshold_signal
from src.config import PARAMS

NAME = "宏观流动性"
REPORT_KEY = "宏观流动性"
INDICATOR_NAME = "流动性供给强度(Zscore)"


def indicator(params=None):
    """原始择时指标：平滑净投放的滚动 Zscore（流动性供给强度）。"""
    p = params or PARAMS[NAME]
    full = int(p.get("full_window", 0)) == 1
    net = load_macro_liquidity().set_index("date")["net_injection"]
    sw = int(p["smooth_window"])
    smoothed = net.rolling(sw, min_periods=sw if full else 1).mean()   # 平滑
    z = rolling_zscore(smoothed, p["zscore_window"])                   # 供给强度
    if full:                                                            # Zscore 也要求满窗
        zw = int(p["zscore_window"])
        z = z.where(smoothed.notna())
        z.iloc[:sw + zw - 2] = np.nan
    return z


def build_signal(params=None):
    p = params or PARAMS[NAME]
    signal = threshold_signal(indicator(params).dropna(), p["p"])      # 三态阈值信号
    signal.name = "signal"
    return signal
