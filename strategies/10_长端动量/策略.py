# -*- coding: utf-8 -*-
"""
10 长端动量 —— 信号构造
=======================
指数维度：高振幅交易日涨跌幅呈更显著动量，故【剔除低振幅交易日】的涨跌幅后累加，
作为指数长端动量指标：>0 做多、<0 空仓。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index
from src.signal_utils import sign_signal
from src.config import PARAMS

NAME = "长端动量"
REPORT_KEY = "长端动量"


def build_signal(params=None):
    p = params or PARAMS[NAME]
    df = load_index("中证800")[["date", "pct_chg", "amplitude"]].set_index("date").dropna()
    amp = df["amplitude"].values
    ret = df["pct_chg"].values
    n, lb, q = len(df), p["lookback"], p["amp_quantile"]

    momentum = np.full(n, np.nan)
    for t in range(lb - 1, n):
        a = amp[t - lb + 1: t + 1]
        r = ret[t - lb + 1: t + 1]
        thr = np.nanquantile(a, q)                    # 窗口内振幅分位阈值
        keep = a >= thr                               # 只保留高振幅交易日
        momentum[t] = np.nansum(r[keep])              # 剔除低振幅日后的累计涨跌幅

    signal = sign_signal(pd.Series(momentum, index=df.index), positive_is_long=True)
    signal.name = "signal"
    return signal
