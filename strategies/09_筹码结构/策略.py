# -*- coding: utf-8 -*-
"""
09 筹码结构 —— 信号构造
=======================
复现《行业轮动3.0》筹码分布法（指数维度重构）：
  · 假设每日存量持仓按当日换手率均匀换仓，当日均价(典型价)作为新换仓筹码的持仓成本；
  · 逐日滚动累积各价位筹码分布（旧筹码按 1-换手率 衰减，新筹码按换手率注入）；
  · 阻力筹码 = 持仓成本高于现价的筹码占比；支撑筹码 = 低于现价的筹码占比；
  · 现价相对加权平均持仓成本收益率 = 赚钱效应（盈利/亏损状态）；
  · 对阻力/支撑强度做 Zscore，按阈值 p 出信号：
      盈利 & 支撑强度>p -> 1；亏损 & 阻力强度>p -> -1；否则延续前信号。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index, load_turnover
from src.signal_utils import rolling_zscore
from src.config import PARAMS

NAME = "筹码结构"
REPORT_KEY = "筹码结构"


def _chip_distribution(high, low, close, turn):
    """逐日累积筹码分布，返回 (阻力筹码占比, 支撑筹码占比, 赚钱效应收益率)。"""
    typical = (high + low + close) / 3.0                       # 当日典型价=持仓成本
    n = len(close)
    pmin, pmax = typical.min() * 0.95, typical.max() * 1.05
    step = pmin * 0.005                                        # 价格网格步长≈0.5%
    grid = np.arange(pmin, pmax + step, step)
    dist = np.zeros(len(grid))

    resistance = np.full(n, np.nan)
    support = np.full(n, np.nan)
    profit = np.full(n, np.nan)
    for t in range(n):
        tr = min(max(turn[t], 0.0), 1.0)                      # 当日换手率(分数)
        dist *= (1 - tr)                                       # 旧筹码衰减
        idx = min(int((typical[t] - pmin) / step), len(grid) - 1)
        dist[idx] += tr                                        # 新筹码按成本价注入
        s = dist.sum()
        if s <= 0:
            continue
        c = close[t]
        above = grid > c
        resistance[t] = dist[above].sum() / s                 # 成本高于现价 -> 阻力
        support[t] = dist[~above].sum() / s                   # 成本低于现价 -> 支撑
        profit[t] = c / ((grid * dist).sum() / s) - 1         # 现价/平均成本-1
    return resistance, support, profit


def build_signal(params=None):
    p = params or PARAMS[NAME]
    px = load_index("中证800")[["date", "high", "low", "close"]].set_index("date")
    tn = load_turnover("中证800").set_index("date")["turnover"]
    df = px.join(tn, how="inner").dropna()

    res, sup, prof = _chip_distribution(
        df["high"].values, df["low"].values, df["close"].values,
        (df["turnover"] / 100).values)                        # 换手率 %→分数

    res_z = rolling_zscore(pd.Series(res, index=df.index), p["zscore_window"])
    sup_z = rolling_zscore(pd.Series(sup, index=df.index), p["zscore_window"])
    prof = pd.Series(prof, index=df.index)

    raw = pd.Series(np.nan, index=df.index)
    raw[(prof > 0) & (sup_z > p["p"])] = 1                     # 盈利&支撑强 -> 做多
    raw[(prof < 0) & (res_z > p["p"])] = -1                    # 亏损&阻力强 -> 空仓
    signal = raw.ffill().fillna(0)
    signal.name = "signal"
    return signal
