# -*- coding: utf-8 -*-
"""
10 长端动量 —— 信号构造（风险调整动量 / t 统计量）
==================================================
指数维度：剔除低振幅交易日，对高振幅日涨跌幅做【风险调整】——用 t 统计量衡量趋势
“又强又稳”的程度，再按阈值 p 三态出信号（带延续，低换手）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index_full
from src.signal_utils import threshold_signal
from src.config import PARAMS

NAME = "长端动量"
REPORT_KEY = "长端动量"
INDICATOR_NAME = "风险调整动量(t值)"          # 面板统计用；p 作用在它上（|RAM|>p 触发）
INDEX_DEPENDENT = True   # 信号由标的自身 OHLC 计算，可跨标的复用（默认中证800）


def indicator(params=None, index_name="中证800"):
    """风险调整动量：高振幅交易日涨跌幅的 t 统计量（趋势强度/噪音）。"""
    p = params or PARAMS[NAME]
    df = load_index_full(index_name)[["date", "pct_chg", "amplitude"]].set_index("date").dropna()
    amp = df["amplitude"].values
    ret = df["pct_chg"].values
    n, lb, q = len(df), int(p["lookback"]), float(p["amp_quantile"])
    ram = np.full(n, np.nan)
    for t in range(lb - 1, n):
        a = amp[t - lb + 1: t + 1]
        r = ret[t - lb + 1: t + 1]
        thr = np.nanquantile(a, q)                    # 窗口内振幅分位阈值
        keep = a >= thr                               # 只保留高振幅交易日
        rk = r[keep]
        nk = np.isfinite(rk).sum()
        if nk < 3:
            continue
        sd = np.nanstd(rk)
        if not sd > 0:
            continue
        ram[t] = np.nanmean(rk) * np.sqrt(nk) / sd    # t 统计量 = 风险调整动量
    return pd.Series(ram, index=df.index)


def build_signal(params=None, index_name="中证800"):
    p = params or PARAMS[NAME]
    pv = float(p.get("p", PARAMS[NAME]["p"]))         # 兼容旧参数组（无 p 时取默认）
    signal = threshold_signal(indicator(params, index_name), pv)   # RAM>p做多 / <-p空仓 / 中间延续
    signal.name = "signal"
    return signal
