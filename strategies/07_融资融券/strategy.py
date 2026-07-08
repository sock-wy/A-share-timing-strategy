# -*- coding: utf-8 -*-
"""
07 融资融券 —— 信号构造
=======================
买盘强度 = 融资买入额/流通市值；卖盘强度 = 融券卖出额/流通市值。
用买盘对卖盘做滚动中性化取残差（融资买盘强度“中性”融券卖盘强度），
再取残差短期均值作为买卖强度对比指标：>0 做多、<0 空仓。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_margin, load_float_mktcap
from src.signal_utils import sign_signal
from src.config import PARAMS

NAME = "融资融券"
REPORT_KEY = "融资融券"


def build_signal():
    p = PARAMS[NAME]
    m = load_margin().set_index("date")
    cap = load_float_mktcap().set_index("date")["float_mktcap"]
    df = m.join(cap, how="inner").dropna()

    buy = df["margin_buy"] / df["float_mktcap"]                # 买盘资金强度
    sell = df["short_sell"] / df["float_mktcap"]               # 卖盘资金强度

    # —— 滚动中性化：残差 = buy - (α + β·sell)，β/α 由过去 neutral_window 窗口估计（防未来函数）——
    w = p["neutral_window"]
    beta = buy.rolling(w).cov(sell) / sell.rolling(w).var()
    resid = buy - (buy.rolling(w).mean() + beta * (sell - sell.rolling(w).mean()))

    indicator = resid.rolling(p["short_ma"]).mean()           # 残差短期均值
    signal = sign_signal(indicator, positive_is_long=True)    # 正->做多，负->空仓
    signal.name = "signal"
    return signal
