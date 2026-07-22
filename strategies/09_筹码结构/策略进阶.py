# -*- coding: utf-8 -*-
"""
09 筹码结构 · 进阶 —— 深度加权（阻力/支撑=筹码重心离现价多深）
================================================================
不只数"上方有多少套牢筹码"，而是先用绝对价格算出上方筹码的【加权平均价位(重心)】，
再看它离现价多远——即"套牢盘平均压在现价上方多深"。支撑同理看下方重心深度。
阻力=头顶重心深度、支撑=脚下重心深度，两者测不同的东西、天然解耦
（实测 corr(支撑Z,阻力Z)≈−0.15，基础版约 −0.56）；加权平均自带归一化。
三个历史变体中质量最好（最高年化时次胜率 50%，最接近研报 57%）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index_full, load_turnover
from src.signal_utils import rolling_zscore
from src.config import PARAMS

NAME = "筹码结构进阶"
REPORT_KEY = "筹码结构"                        # 仍与研报“筹码结构”绩效对照
INDICATOR_NAME = "赚钱效应(现价/均成本−1)"     # 面板统计用：>0 市场盈利、<0 亏损
INDEX_DEPENDENT = True   # 信号由标的自身 OHLC+成交额+换手率计算，可跨标的复用（默认中证800）


def _load_chip(index_name="中证800", params=None):
    idx = load_index_full(index_name)[["date", "high", "low", "close", "amount"]].set_index("date")
    tn = load_turnover(index_name).set_index("date")["turnover"]
    df = idx.join(tn, how="inner").dropna()
    res, sup, prof = _chip_distribution_moment(
        df["high"].values, df["low"].values, df["close"].values,
        (df["turnover"] / 100).values, df["amount"].values)
    return df, res, sup, prof


def indicator(params=None, index_name="中证800"):
    """原始择时指标之一：赚钱效应（现价相对平均持仓成本的收益率）。"""
    df, res, sup, prof = _load_chip(index_name, params)
    return pd.Series(prof, index=df.index)


def _chip_distribution_moment(high, low, close, turn, amount):
    """阻力/支撑 = 现价上/下方筹码的【加权平均价位相对现价的深度(%)】。"""
    typical = (high + low + close) / 3.0
    n = len(close)
    pmin, pmax = typical.min() * 0.90, typical.max() * 1.10
    step = pmin * 0.005
    grid = np.arange(pmin, pmax + step, step)
    dist = np.zeros(len(grid))                                 # 绝对筹码量（以成交额计）

    resistance = np.full(n, np.nan)
    support = np.full(n, np.nan)
    profit = np.full(n, np.nan)
    for t in range(n):
        tr = min(max(turn[t], 0.0), 1.0)
        dist *= (1 - tr)                                       # 旧筹码换手衰减
        k = min(int((typical[t] - pmin) / step), len(grid) - 1)
        dist[k] += amount[t]                                  # 新筹码按当日成交额注入
        S = dist.sum()
        c = close[t]
        if S <= 0:
            continue
        above = grid > c
        below = grid <= c
        ma = dist[above].sum()
        mb = dist[below].sum()
        if ma > 0:                                             # 上方筹码加权平均价 / 现价 − 1
            resistance[t] = (grid[above] * dist[above]).sum() / ma / c - 1
        if mb > 0:                                             # 1 − 下方筹码加权平均价 / 现价
            support[t] = 1 - (grid[below] * dist[below]).sum() / mb / c
        profit[t] = c / ((grid * dist).sum() / S) - 1         # 现价/全体加权平均成本 − 1
    return resistance, support, profit


def build_signal(params=None, index_name="中证800"):
    p = params or PARAMS[NAME]
    df, res, sup, prof = _load_chip(index_name, params)

    res_z = rolling_zscore(pd.Series(res, index=df.index), p["zscore_window"])
    sup_z = rolling_zscore(pd.Series(sup, index=df.index), p["zscore_window"])
    prof = pd.Series(prof, index=df.index)

    raw = pd.Series(np.nan, index=df.index)
    raw[(prof > 0) & (sup_z > p["p"])] = 1                     # 盈利&支撑深 -> 做多
    raw[(prof < 0) & (res_z > p["p"])] = -1                    # 亏损&阻力深 -> 空仓
    signal = raw.ffill().fillna(0)
    signal.name = "signal"
    return signal
