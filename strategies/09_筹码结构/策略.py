# -*- coding: utf-8 -*-
"""
09 筹码结构 —— 信号构造（基础版：÷成交额 绝对筹码）
====================================================
按研报原文口径：“将持仓成本高于现价的筹码与成交额比值作为阻力筹码，
将持仓成本低于现价的筹码与成交额比值作为支撑筹码”。
逐日按换手率衰减、按当日成交额注入绝对筹码，支撑/阻力强度 = 对应筹码量 ÷ 当日成交额，
再做滚动 Zscore，配合赚钱效应（盈利/亏损态）按阈值 p 出三态信号。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index_full, load_turnover
from src.signal_utils import rolling_zscore
from src.config import PARAMS

NAME = "筹码结构"
REPORT_KEY = "筹码结构"
INDICATOR_NAME = "赚钱效应(现价/均成本−1)"   # 面板统计用：>0 市场盈利、<0 亏损
INDEX_DEPENDENT = True   # 信号由标的自身 OHLC+成交额+换手率计算，可跨标的复用（默认中证800）


def _load_chip(index_name="中证800"):
    idx = load_index_full(index_name)[["date", "high", "low", "close", "amount"]].set_index("date")
    tn = load_turnover(index_name).set_index("date")["turnover"]
    df = idx.join(tn, how="inner").dropna()
    res, sup, prof = _chip_distribution_abs(
        df["high"].values, df["low"].values, df["close"].values,
        (df["turnover"] / 100).values, df["amount"].values)
    return df, res, sup, prof


def indicator(params=None, index_name="中证800"):
    """原始择时指标之一：赚钱效应（现价相对平均持仓成本的收益率）。"""
    df, res, sup, prof = _load_chip(index_name)
    return pd.Series(prof, index=df.index)


def _chip_distribution_abs(high, low, close, turn, amount):
    """按成交额累积【绝对筹码量】，阻力/支撑强度 = 对应筹码量 ÷ 当日成交额。"""
    typical = (high + low + close) / 3.0                       # 当日典型价=持仓成本
    n = len(close)
    pmin, pmax = typical.min() * 0.90, typical.max() * 1.10
    step = pmin * 0.005                                        # 价格网格步长≈0.5%
    grid = np.arange(pmin, pmax + step, step)
    dist = np.zeros(len(grid))                                 # 绝对筹码量（以成交额计）

    resistance = np.full(n, np.nan)
    support = np.full(n, np.nan)
    profit = np.full(n, np.nan)
    for t in range(n):
        tr = min(max(turn[t], 0.0), 1.0)                      # 当日换手率(分数)
        dist *= (1 - tr)                                       # 旧筹码换手衰减
        idx = min(int((typical[t] - pmin) / step), len(grid) - 1)
        dist[idx] += amount[t]                                # 新筹码按当日成交额注入
        s = dist.sum()
        amt = amount[t]
        if s <= 0 or amt <= 0:
            continue
        c = close[t]
        above = grid > c
        resistance[t] = dist[above].sum() / amt               # 阻力筹码 ÷ 成交额
        support[t] = dist[~above].sum() / amt                 # 支撑筹码 ÷ 成交额
        profit[t] = c / ((grid * dist).sum() / s) - 1         # 现价/加权平均成本-1
    return resistance, support, profit


def build_signal(params=None, index_name="中证800"):
    p = params or PARAMS[NAME]
    df, res, sup, prof = _load_chip(index_name)

    res_z = rolling_zscore(pd.Series(res, index=df.index), p["zscore_window"])
    sup_z = rolling_zscore(pd.Series(sup, index=df.index), p["zscore_window"])
    prof = pd.Series(prof, index=df.index)

    raw = pd.Series(np.nan, index=df.index)
    raw[(prof > 0) & (sup_z > p["p"])] = 1                     # 盈利&支撑强 -> 做多
    raw[(prof < 0) & (res_z > p["p"])] = -1                    # 亏损&阻力强 -> 空仓
    signal = raw.ffill().fillna(0)
    signal.name = "signal"
    return signal
