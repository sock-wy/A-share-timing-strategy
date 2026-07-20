# -*- coding: utf-8 -*-
"""
09 筹码结构 · 进阶2 —— 近邻指数核解耦（支撑看脚下、阻力看头顶）
================================================================
【为什么做进阶2】
原版 支撑+阻力≡1，两者 Zscore 相关性 corr=−1.000，完全镜像 —— 建仓看支撑、平仓看阻力，
其实由同一个变量在管，退化成单因子（≈慢均线穿越）。进阶版(÷成交额)只把 corr 松到 −0.563
（靠共用成交额分母的“量的共模”冲淡，属粗解耦）。进阶2 治本：让支撑只累加“现价下方近处”的
筹码、阻力只累加“现价上方近处”的筹码，两者从源头测不同价格区域，corr 真正打散到 0 附近。

【进阶2 建仓/平仓逻辑（面板顶部展示）】
1. 逐日维护价格网格上的【绝对筹码量】：旧筹码按(1−换手率)衰减，新筹码=当日成交额，
   注入到当日典型价(高+低+收)/3。
2. 近邻指数核（λ = lam_pct×现价 为衰减半径），并在现价上下各留一条平价死区(dead_pct×现价)
   把“刚回本”的平价筹码排除在两侧之外：
       支撑 = Σ_{成本 < 现价−死区} 筹码 · exp(−(现价−成本)/λ) ÷ 当日成交额
       阻力 = Σ_{成本 > 现价+死区} 筹码 · exp(−(成本−现价)/λ) ÷ 当日成交额
   —— 支撑只看脚下近处密度、阻力只看头顶近处密度，物理上是两个东西。
3. 赚钱效应 = 现价 / 加权平均持仓成本 − 1（>0 盈利，<0 亏损）。
4. 对支撑/阻力强度各做滚动 Zscore，按阈值 p 出信号（带延续，降换手）：
       · 建仓：市场盈利 且 支撑强度Zscore > p → 做多；
       · 平仓：市场亏损 且 阻力强度Zscore > p → 空仓；
       · 未触发 → 延续前一状态。

解耦的价值体现在【空仓那一侧】：阻力Z 解耦后能独立报“头顶套牢盘变重”，让平仓由头顶供给
驱动，而不再是“支撑塌了”的同义反复。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index_full, load_turnover
from src.signal_utils import rolling_zscore
from src.config import PARAMS

NAME = "筹码结构进阶2"
REPORT_KEY = "筹码结构"                        # 仍与研报“筹码结构”绩效对照
INDICATOR_NAME = "赚钱效应(现价/均成本−1)"     # 面板统计用：>0 市场盈利、<0 亏损
INDEX_DEPENDENT = True   # 信号由标的自身 OHLC+成交额+换手率计算，可跨标的复用（默认中证800）


def _load_chip(index_name="中证800", params=None):
    p = params or PARAMS[NAME]
    lam_pct = float(p.get("lam_pct", 0.05))
    dead_pct = float(p.get("dead_pct", 0.01))
    idx = load_index_full(index_name)[["date", "high", "low", "close", "amount"]].set_index("date")
    tn = load_turnover(index_name).set_index("date")["turnover"]
    df = idx.join(tn, how="inner").dropna()
    res, sup, prof = _chip_kernel(
        df["high"].values, df["low"].values, df["close"].values,
        (df["turnover"] / 100).values, df["amount"].values, lam_pct, dead_pct)
    return df, res, sup, prof


def indicator(params=None, index_name="中证800"):
    """原始择时指标之一：赚钱效应（现价相对平均持仓成本的收益率）。"""
    df, res, sup, prof = _load_chip(index_name, params)
    return pd.Series(prof, index=df.index)


def _chip_kernel(high, low, close, turn, amount, lam_pct, dead_pct):
    """近邻指数核 + 平价死区：支撑/阻力各只累加现价近处一侧的绝对筹码，÷当日成交额。"""
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
        amt = amount[t]
        if S <= 0 or amt <= 0:
            continue
        lam = max(lam_pct * c, 1e-9)                          # 近邻衰减半径（占价格%）
        dead = dead_pct * c                                   # 平价死区（占价格%）
        below = grid < c - dead                               # 脚下（排除平价带）
        above = grid > c + dead                               # 头顶（排除平价带）
        support[t] = (dist[below] * np.exp(-(c - grid[below]) / lam)).sum() / amt
        resistance[t] = (dist[above] * np.exp(-(grid[above] - c) / lam)).sum() / amt
        profit[t] = c / ((grid * dist).sum() / S) - 1         # 现价/加权平均成本-1
    return resistance, support, profit


def build_signal(params=None, index_name="中证800"):
    p = params or PARAMS[NAME]
    df, res, sup, prof = _load_chip(index_name, params)

    res_z = rolling_zscore(pd.Series(res, index=df.index), p["zscore_window"])
    sup_z = rolling_zscore(pd.Series(sup, index=df.index), p["zscore_window"])
    prof = pd.Series(prof, index=df.index)

    raw = pd.Series(np.nan, index=df.index)
    raw[(prof > 0) & (sup_z > p["p"])] = 1                     # 盈利&支撑强 -> 做多
    raw[(prof < 0) & (res_z > p["p"])] = -1                    # 亏损&阻力强 -> 空仓
    signal = raw.ffill().fillna(0)
    signal.name = "signal"
    return signal
