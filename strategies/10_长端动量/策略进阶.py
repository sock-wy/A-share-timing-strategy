# -*- coding: utf-8 -*-
"""
10 长端动量 · 进阶版 —— 风险调整动量（t 统计量）+ 三态延续
============================================================
【为什么做进阶版】
原版 = “剔除低振幅日的涨跌幅累加 > 0 做多”。它是纯累计涨跌幅，在震荡/急跌市里
频繁假突破（约 50% 胜率、高换手），无法复现研报“22 笔、次均 60 天、68% 胜率、
踏空 2015/2018/2022 大跌”的低换手趋势曲线。研报《长端动量2.0》是**量价因子**，
更可能对动量做了**风险调整**并让信号**持续化**。

【进阶版建仓 / 平仓逻辑（面板顶部展示）】
1. 在回看窗口 lookback 内，取振幅分位 amp_quantile 定阈值，仅保留高振幅交易日。
2. 计算这些高振幅日涨跌幅的 **t 统计量**（风险调整动量）：
       RAM = mean(高振幅日涨跌幅) × √n / std(高振幅日涨跌幅)
   —— 趋势“又强又稳”时 RAM 大；急跌/震荡时高振幅日涨跌方向发散、std 大，RAM 被压回 0。
3. **三态阈值 p（带延续，降换手）**：
       · RAM > p    → 建仓（满仓做多中证800）；
       · RAM < -p   → 平仓（空仓）；
       · |RAM| ≤ p  → 延续前一状态（不动，避免单周毛刺来回切）。

直觉：把“涨了多少”换成“涨得多显著”。急跌里高振幅日有涨有跌、离散度大，t 值上不去，
自然踏空下跌；单边趋势里高振幅日方向一致、t 值高且持续，于是低换手长期持有。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index
from src.signal_utils import threshold_signal
from src.config import PARAMS

NAME = "长端动量进阶"
REPORT_KEY = "长端动量"                       # 仍与研报“长端动量”绩效对照
INDICATOR_NAME = "风险调整动量(t值)"          # 面板统计用；p 作用在它上（|RAM|>p 触发）


def indicator(params=None):
    """风险调整动量：高振幅交易日涨跌幅的 t 统计量（趋势强度/噪音）。"""
    p = params or PARAMS[NAME]
    df = load_index("中证800")[["date", "pct_chg", "amplitude"]].set_index("date").dropna()
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


def build_signal(params=None):
    p = params or PARAMS[NAME]
    signal = threshold_signal(indicator(params), p["p"])   # RAM>p做多 / <-p空仓 / 中间延续
    signal.name = "signal"
    return signal
